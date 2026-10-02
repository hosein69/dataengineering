"""Pipeline persistence boundary; calculations remain owned by business stages."""
from pathlib import Path
import json
import time
import pandas as pd
from ..dataio.logging_setup import log
from .store import Warehouse
from .reliability import validate_sources, schema_drift_checks, source_runtime_checks, Check, BLOCK, DEGRADED
from .quality_gate import sqlite_foreign_key_check, sqlite_integrity_check, evaluate
from .business_dwh import build as build_business_dwh

def _record_source_history(wh,pipeline,rid,result):
    """سوابق ردیف‌های منبع و دفتر تغییرات این اجرا؛ خطایش انتشار را متوقف نمی‌کند.

    سورسی که این بار خوانده نشد (جایگزین از Snapshot قبلی یا بدون فایل) مشاهده تازه‌ای
    نیست و سوابقش دست نمی‌خورد. اگر ثبت شکست بخورد، تراکنشش برمی‌گردد و اجرای بعدی
    تغییرات را از آخرین وضعیت ثبت‌شده می‌سنجد؛ چیزی گم نمی‌شود، فقط به اجرای بعدی می‌افتد.
    """
    from .history import record_history
    fresh=[k for k,v in pipeline.sources.items() if v and k not in pipeline.source_fallbacks]
    _t=time.perf_counter(); log.info("🧾 [history] START")
    try:
        out=record_history(wh,rid,fresh,log=log)
    except Exception as ex:
        log.error(f"⚠️ [history] ثبت سوابق منبع انجام نشد؛ اجرای بعدی از آخرین وضعیت ثبت‌شده ادامه می‌دهد: {ex}",
                  exc_info=True)
        return Check('source/history','SOURCE_HISTORY',DEGRADED,False,{'error':f'{type(ex).__name__}: {ex}'})
    summary=out['summary']
    result.extras['source_history']=summary
    wh.audit('source_history',{'summary':summary,
                               'frames':{k:v for k,v in out['frames'].items() if v.get('mode')!='same'}},actor='system')
    log.info(f"🧾 [history] DONE {time.perf_counter()-_t:.2f}s | {summary['frames']} فریم، "
             f"{summary['unchanged_frames']} بدون تغییر | تازه {summary['new']} · تغییر {summary['changed']} "
             f"({summary['fields']} فیلد) · رفته {summary['gone']} · برگشته {summary['back']}")
    return Check('source/history','SOURCE_HISTORY',DEGRADED,True,summary)


def run_pipeline(pipeline,build_report,version):
    wh=Warehouse()
    timings={}
    with wh.run({'reference_date':str(pipeline.today),'version':version}) as rid:
        from gsi.config.sources import _yaml_path
        configured=Path(_yaml_path())
        if configured.exists():wh.blob(configured.read_bytes(),configured.name,'configuration',str(configured))
        for root in ('config','rules'):
            for path in (Path(__file__).parents[1]/root).glob('*.yaml'):
                wh.blob(path.read_bytes(),path.name,'configuration',str(path))
        _t=time.perf_counter()
        result=pipeline._run_warehouse(False)
        timings['core']=round(time.perf_counter()-_t,3)
        trust_snapshot(result)
        _t=time.perf_counter()
        history_check=_record_source_history(wh,pipeline,rid,result)
        timings['history']=round(time.perf_counter()-_t,3)

        # ---- EARLY PUBLICATION GATE -------------------------------------------------
        # Source/grain/process/partition failures are knowable before Business DWH.
        # Never spend minutes rebuilding the DWH for a run that is already unsafe to
        # publish. Diagnostics are recorded on the completed run; wh.publish() below
        # raises the same QualityGateBlockedError and leaves the previous snapshot live.
        checks=validate_sources(pipeline.sources)
        checks.extend(schema_drift_checks(wh,pipeline.sources,rid))
        checks.extend(source_runtime_checks(pipeline))
        checks.append(history_check)
        ps = result.extras.get('process_evidence_summary', {}) or {}
        checks.append(Check('process/evidence','PROCESS_ROW_PRESERVATION',BLOCK,
                            bool(ps.get('row_preservation_ok')),
                            {'expected_native_rows':ps.get('expected_native_rows',0),
                             'preserved_source_observations':ps.get('preserved_source_observations',0),
                             'candidate_frame_rows':ps.get('candidate_frame_rows',0),
                             'physical_ref_dedup_rows':ps.get('physical_ref_dedup_rows',0),
                             'physical_ref_collision_count':ps.get('physical_ref_collision_count',0),
                             'missing_source_ref_count':ps.get('missing_source_ref_count',0),
                             'unexpected_source_ref_count':ps.get('unexpected_source_ref_count',0),
                             'missing_source_ref_sample':ps.get('missing_source_ref_sample',[]),
                             'unexpected_source_ref_sample':ps.get('unexpected_source_ref_sample',[]),
                             'orphan_no_business_key':ps.get('orphan_no_business_key',0)}))
        dc = result.extras.get('derive_coverage', {}) or {}
        if dc:
            checks.append(Check('derive/coverage','DERIVED_SOURCE_COVERAGE',DEGRADED,
                                not dc.get('unreachable_targets'),
                                {k: dc.get(k) for k in ('unreachable_targets','declared_unmeasured','rows')}))
            if dc.get('unknown_defaulted_to_zero'):
                checks.append(Check('derive/unknown','UNKNOWN_COERCED_TO_ZERO',DEGRADED,False,
                                    {'targets':dc['unknown_defaulted_to_zero'],
                                     'note':'unexpected compatibility path; business values must preserve Missing'}))
        total=len(result.df)
        bucket_total=len(result.main)+len(result.to_resolve)+len(result.excluded)
        checks.append(Check('pipeline/final_partition','ROW_PRESERVATION',BLOCK,total==bucket_total,
                            {'df_rows':total,'main':len(result.main),'to_resolve':len(result.to_resolve),
                             'excluded':len(result.excluded),'delta':total-bucket_total}))

        wh.record_quality(rid,checks)
        pre_gate=evaluate(checks)
        result.extras['quality_gate_passed']=pre_gate.passed
        result.extras['quality_gate_blocking_codes']=list(pre_gate.blocking_codes)
        if pre_gate.passed:
            _t=time.perf_counter(); log.info("🏗️ [business-dwh] START")
            dwh_counts=build_business_dwh(wh,pipeline.sources,rid)
            timings['business_dwh']=round(time.perf_counter()-_t,3)
            log.info(f"🏗️ [business-dwh] DONE {time.perf_counter()-_t:.2f}s | {dwh_counts}")
            result.extras['business_dwh_counts']=dwh_counts
            result.extras['warehouse_run_id']=rid
            checks.append(Check('business-dwh/entities', 'EMPTY_BUSINESS_DWH', BLOCK,
                                int(dwh_counts.get('entities', 0)) > 0,
                                {'entities': dwh_counts.get('entities', 0),
                                 'source_rows': dwh_counts.get('source_rows', 0)}))
            _conf = dict(dwh_counts.get('grain_conflicts') or {})
            checks.append(Check('business-dwh/facts', 'DWH_FACT_GRAIN_CONFLICT', BLOCK, not _conf,
                                {'tables': _conf,
                                 'action': 'two source rows share one natural key with different values; '
                                           'the table was not rebuilt and its previous versions stay open'}))
            checks.append(Check('business-dwh/relations', 'ORPHAN_BUSINESS_RELATIONS', BLOCK,
                                int(dwh_counts.get('orphan_relations', 0)) == 0,
                                {'orphan_relations': dwh_counts.get('orphan_relations', 0)}))
            wh.audit('report_run',{'rows':len(result.df),'report':result.dashboard_path})

            # SQLite checks run after DWH mutation; record the complete gate again.
            # Normal production refreshes use quick_check; full integrity_check is
            # opt-in via GSI_SQLITE_FULL_INTEGRITY_CHECK=1 for release/forensic QA.
            _sqlite_t = time.perf_counter()
            log.info("🔎 [sqlite-checks] START")
            with wh.db() as c:
                _fk_t = time.perf_counter()
                log.info("🔗 [sqlite-checks] foreign_key_check START")
                checks.append(sqlite_foreign_key_check(c))
                log.info(f"🔗 [sqlite-checks] foreign_key_check DONE {time.perf_counter()-_fk_t:.2f}s")

                _integrity_t = time.perf_counter()
                log.info("⚡ [sqlite-checks] integrity START")
                integrity_check = sqlite_integrity_check(c)
                checks.append(integrity_check)
                mode = integrity_check.detail.get('mode', 'quick')
                log.info(f"⚡ [sqlite-checks] integrity DONE {time.perf_counter()-_integrity_t:.2f}s | mode={mode}")
            timings['sqlite_checks']=round(time.perf_counter()-_sqlite_t,3)
            log.info(f"🔎 [sqlite-checks] DONE {time.perf_counter()-_sqlite_t:.2f}s")
            _t=time.perf_counter(); log.info("🛡️ [quality-gate] START")
            wh.record_quality(rid,checks)
            gate=evaluate(checks)
            log.info(f"🛡️ [quality-gate] DONE {time.perf_counter()-_t:.2f}s | passed={gate.passed} | blocking={list(gate.blocking_codes)}")
            result.extras['quality_gate_passed']=gate.passed
            result.extras['quality_gate_blocking_codes']=list(gate.blocking_codes)
            if gate.passed and build_report:
                _t=time.perf_counter(); log.info("📗 [excel-report] START")
                from gsi.config.settings import SETTINGS
                from gsi.report.extracts import write_expert_extracts, write_audit_report
                destination = Path(SETTINGS.OUTPUT_DIR) / 'runs' / rid
                destination.mkdir(parents=True, exist_ok=True)
                result.dashboard_path = pipeline.build_report(result, path=str(destination / 'GSI_Report.xlsx'))
                result.extract_paths = write_expert_extracts(result.main, str(destination / 'extracts'))
                write_audit_report(result.audit, str(destination / 'GSI_Data_Conflicts_Audit.xlsx'))
                report_metadata(result)
                timings['excel_report']=round(time.perf_counter()-_t,3)
                log.info(f"📗 [excel-report] DONE {time.perf_counter()-_t:.2f}s | {result.dashboard_path}")
        else:
            result.extras['warehouse_run_id']=rid
            log.error("🛑 [quality-gate] EARLY BLOCK — Business DWH/Excel skipped because publication is already unsafe: "
                      + " | ".join(pre_gate.blocking_codes))
            # هر بند بستن با جزئیاتش (مثلاً کدام فایل ترخیص و کدام ستون)، تا علت در همین لاگ باشد.
            from .reliability import blocking as _blocking
            for _c in _blocking(checks):
                log.error("   ↳ %s:%s %s", _c.contract, _c.code,
                          json.dumps(_c.detail, ensure_ascii=False, default=str)[:4000])
        wh.record_timings(rid,timings)

    # Both report and DWH pointers move together. On an early or late gate failure
    # publish raises QualityGateBlockedError here; the previous good snapshot stays live.
    _t=time.perf_counter(); log.info("📌 [publish] START")
    try:
        wh.publish(rid,slots=('report','dwh'))
    finally:
        # WAL را پس از هر اجرا به فایل اصلی برمی‌گرداند تا کنار فایل انبار بزرگ نشود.
        wh.checkpoint()
    timings['publish']=round(time.perf_counter()-_t,3)
    wh.record_timings(rid,timings)
    log.info(f"📌 [publish] DONE {time.perf_counter()-_t:.2f}s | run_id={rid}")
    log.info("🏁 اجرای کامل GSI با موفقیت پایان یافت و Snapshot جدید منتشر شد.")
    return result

def persist_result(res):
    """Persist pipeline result once; do not deserialize it back immediately.

    Older releases wrote every mart frame to SQLite and then immediately called
    ``read_frame`` only to prove it could be read.  With the real GSI payload
    (wide ``df`` plus Event Log / Action Queue / FX ledgers) this doubled the
    serialization cost exactly before Streamlit rerendered after the official
    Excel was saved.  Correctness is already protected by the transaction, row
    counts, schema metadata, SQLite integrity checks and publish quality gate.

    A full round-trip can still be enabled for release/forensic QA with
    ``GSI_DWH_VERIFY_ROUNDTRIP=1`` without penalising every production run.
    """
    import os
    wh=Warehouse()
    verify = os.environ.get('GSI_DWH_VERIFY_ROUNDTRIP','').strip().lower() in ('1','true','yes','on')
    for name in ('df','main','to_resolve','excluded','audit','mogh_lines'):
        value = getattr(res,name)
        fid = wh.frame(value,'mart',name)
        if verify:
            wh.read_frame(fid)

    # Dedicated source-grain material evidence index.  This is intentionally
    # independent from the Abbasi/BL base population: searching a material code
    # must find every Commercial Expert row carrying that code, even when its
    # Order is not yet linked to the main mart.  It is evidence only and is never
    # fed into KPI calculations.
    lines = getattr(res, 'mogh_lines', None)
    if isinstance(lines, pd.DataFrame) and not lines.empty and 'KEY_MATERIAL' in lines.columns:
        from .material_search import build_material_evidence
        evidence = build_material_evidence(lines)
        fid = wh.frame(evidence, 'mart', 'material_evidence')
        if verify:
            wh.read_frame(fid)
    for name,value in list(res.extras.items()):
        if isinstance(value,pd.DataFrame):
            fid = wh.frame(value,'mart','extras/'+name)
            if verify:
                wh.read_frame(fid)

def trust_snapshot(res):
    """Record the data-trust summary for this run so the trend line exists.

    Written for *every* completed run, including one whose publication is later
    blocked: a blocked run is still a real observation of the data's condition,
    and dropping it would put a hole in the improvement curve exactly where
    something went wrong.
    """
    summary = (res.extras or {}).get('trust_summary')
    if not summary:
        return
    try:
        Warehouse().audit('trust_snapshot', summary)
    except Exception as ex:                      # never fail a run over telemetry
        log.warning(f"⚠️ [data-trust] ثبت عکس اعتماد داده انجام نشد: {ex}")


def report_metadata(res):
    Warehouse().audit('report_metadata',{'report':res.dashboard_path,'counts':res.counts,'extras':{k:v for k,v in res.extras.items() if not isinstance(v,pd.DataFrame)}})
