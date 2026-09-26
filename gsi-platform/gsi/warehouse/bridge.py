"""Pipeline persistence boundary; calculations remain owned by business stages."""
from pathlib import Path
import time
import pandas as pd
from ..dataio.logging_setup import log
from .store import Warehouse
from .reliability import validate_sources, schema_drift_checks, source_runtime_checks, Check, BLOCK, DEGRADED
from .quality_gate import sqlite_checks, evaluate
from .business_dwh import build as build_business_dwh

def run_pipeline(pipeline,build_report,version):
    wh=Warehouse()
    with wh.run({'reference_date':str(pipeline.today),'version':version}) as rid:
        from gsi.config.sources import _yaml_path
        configured=Path(_yaml_path())
        if configured.exists():wh.blob(configured.read_bytes(),configured.name,'configuration',str(configured))
        for root in ('config','rules'):
            for path in (Path(__file__).parents[1]/root).glob('*.yaml'):
                wh.blob(path.read_bytes(),path.name,'configuration',str(path))
        result=pipeline._run_warehouse(False)

        # ---- EARLY PUBLICATION GATE -------------------------------------------------
        # Source/grain/process/partition failures are knowable before Business DWH.
        # Never spend minutes rebuilding the DWH for a run that is already unsafe to
        # publish. Diagnostics are recorded on the completed run; wh.publish() below
        # raises the same QualityGateBlockedError and leaves the previous snapshot live.
        checks=validate_sources(pipeline.sources)
        checks.extend(schema_drift_checks(wh,pipeline.sources,rid))
        checks.extend(source_runtime_checks(pipeline))
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
            log.info(f"🏗️ [business-dwh] DONE {time.perf_counter()-_t:.2f}s | {dwh_counts}")
            result.extras['business_dwh_counts']=dwh_counts
            result.extras['warehouse_run_id']=rid
            wh.audit('report_run',{'rows':len(result.df),'report':result.dashboard_path})

            # SQLite checks run after DWH mutation; record the complete gate again.
            with wh.db() as c:
                checks.extend(sqlite_checks(c))
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
                log.info(f"📗 [excel-report] DONE {time.perf_counter()-_t:.2f}s | {result.dashboard_path}")
        else:
            result.extras['warehouse_run_id']=rid
            log.error("🛑 [quality-gate] EARLY BLOCK — Business DWH/Excel skipped because publication is already unsafe: "
                      + " | ".join(pre_gate.blocking_codes))

    # Both report and DWH pointers move together. On an early or late gate failure
    # publish raises QualityGateBlockedError here; the previous good snapshot stays live.
    _t=time.perf_counter(); log.info("📌 [publish] START")
    wh.publish(rid,slots=('report','dwh'))
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

def report_metadata(res):
    Warehouse().audit('report_metadata',{'report':res.dashboard_path,'counts':res.counts,'extras':{k:v for k,v in res.extras.items() if not isinstance(v,pd.DataFrame)}})
