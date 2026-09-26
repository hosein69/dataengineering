# -*- coding: utf-8 -*-
"""ارکستراتور — عمداً «لاغر».

این فایل هیچ منطق کسب‌وکاری ندارد و نباید داشته باشد. کارش فقط این است:

    قوانین → کشف سورس‌ها → ادغام → اجرای مرحله‌ها → افراز → گزارش

منطق در سه جای مستقل زندگی می‌کند و هر سه بدون لمس این فایل قابل تغییرند:
    gsi/rules/*.yaml     اعداد و قواعد
    gsi/config/sources.yaml   کدام سورس، از کجا، با کدام کلید
    gsi/stages/*.py      هر گام فرآیند، با ورودی/خروجی/ستون‌های اعلام‌شده

اگر مجبور شدید برای افزودن یک قابلیت این فایل را عوض کنید، یعنی طراحی
جایی اشتباه است — نه اینکه فایل ناقص است.
"""
from __future__ import annotations

__contract__ = 3

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .adapters import discover as discover_adapters
from .adapters.base import (KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER,
                            KEY_PR, KEY_REG)
from .config.settings import SETTINGS
from .config.authority import policy_dict, policy_label
from .config.sources import MERGE_ORDER, get_source
from .core.text import clean_key, clean_order_ref, clean_part_no, is_empty_val
from .dataio.logging_setup import log
from .dataio.merge import safe_merge, RowExplosionError
from .report.dashboard import ExcelDashboardBuilder
from .report.extracts import write_audit_report, write_expert_extracts
from .resolve.canonical import CanonicalEntityResolver
from .resolve.partition import partition
from .resolve.population import build_primary_population
from . import health
from .resolve.commercial_coverage import apply as apply_commercial_coverage
from .resolve.commercial_coverage import kpi as commercial_kpi
from .rulebook import get_rulebook
from .stages import (PipelineContext, collect_columns, describe, discover as
                     discover_stages, log_plan, validate_graph)
from .version import PACKAGE_VERSION, check_contracts

from .dataio.join_keys import _key_column

_KEY_BY_JOIN = {"BL": KEY_BL, "ORDER": KEY_ORDER, "REG": KEY_REG,
                "EMP": KEY_EMP, "MATERIAL": KEY_MATERIAL, "PR": KEY_PR}


def frames_of(spec) -> Dict[str, str]:
    """{نام فریم: کلید اتصال} — سازگار با نسخه‌های قدیمی SourceSpec.

    اگر ``config/sources.py`` قدیمی باشد و متد ``frame_map`` نداشته باشد،
    به‌جای AttributeError مبهم، به رفتار تک‌فریمی برمی‌گردد و هشدار می‌دهد.
    """
    fn = getattr(spec, "frame_map", None)
    if callable(fn):
        return fn()
    frames = getattr(spec, "frames", None)
    if frames:
        return dict(frames)
    log.warning(f"⚠️ [{spec.key}] SourceSpec نسخه قدیمی است (بدون frame_map). "
                f"فقط فریم main ادغام می‌شود. → python -m gsi.doctor")
    return {"main": getattr(spec, "join_on", "BL")}


@dataclass
class PipelineResult:
    df: pd.DataFrame
    main: pd.DataFrame
    to_resolve: pd.DataFrame
    excluded: pd.DataFrame
    counts: Dict[str, int]
    audit: pd.DataFrame
    extras: Dict[str, Any] = field(default_factory=dict)
    mogh_lines: pd.DataFrame = field(default_factory=pd.DataFrame)
    dashboard_path: str = ""
    extract_paths: List[str] = field(default_factory=list)


class Pipeline:

    def __init__(self, today: Optional[date] = None) -> None:
        self.today = today or SETTINGS.today
        self.rb = get_rulebook(reload=True, as_of=self.today)
        self.resolver = CanonicalEntityResolver()
        self.sources: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.stages = discover_stages()
        self.ctx = PipelineContext(rb=self.rb, today=self.today,
                                   resolver=self.resolver)
        self.moghavemat_available = False
        self.source_failures: Dict[str, Dict[str, Any]] = {}
        self.source_fallbacks: Dict[str, Dict[str, Any]] = {}
        self.merge_failures: List[Dict[str, Any]] = []
        self.ctx.extras['source_authority_policy'] = policy_dict()
        self.ctx.extras['source_authority_label'] = policy_label()

    # ═══════ ۰) اعتبارسنجی پیش از خواندن هر داده‌ای ═══════
    def preflight(self) -> None:
        issues = check_contracts()
        if issues:
            for i in issues:
                log.error(f"❌ اختلاف نسخه فایل: {i.message}")
            raise RuntimeError(
                "نسخه فایل‌های پکیج با هم نمی‌خواند. فقط فایل‌های بالا را "
                "به‌روزرسانی کنید — نیازی به جایگزینی کل پکیج نیست. "
                "برای گزارش کامل: python -m gsi.doctor")

        errors = [i for i in self.rb.validate() if i.level == "error"]
        if errors:
            for e in errors:
                log.error(f"❌ قانون نامعتبر [{e.pack}] {e.path}: {e.message}")
            raise ValueError("کتابخانه قوانین خطای ساختاری دارد؛ اجرا متوقف شد.")

        base_cols = list(_KEY_BY_JOIN.values()) + [
            "MOGH_PRESENT", "COT_DATE", "NTSW_ALLOC_DATE", "ORC_STATUS"]
        warnings = validate_graph(self.stages, base_cols)
        for w in warnings:
            log.warning(f"⚠️ گراف فرآیند: {w}")

        log_plan(self.stages)
        log.info(f"📚 قوانین: {len(self.rb.packs)} بسته | "
                 f"{len(self.rb.needs_verification())} قاعده نیازمند تطبیق")

    # ═══════ ۱) بارگذاری ═══════
    def load_sources(self) -> None:
        """Load adapters independently; one broken branch must not hide the rest.

        On failure we first try the last *published* standardized frame for that
        source. Such a fallback is explicitly marked stale and is later evaluated
        by the publication quality gate. If no fallback exists the source becomes
        empty, but loading of independent adapters continues so diagnostics are
        complete before any decision to publish.
        """
        from .warehouse.store import Warehouse
        wh = Warehouse()
        registry = discover_adapters()
        for key, cls in registry.items():
            try:
                self.sources[key] = cls().load()
            except Exception as ex:  # isolate the damaged source branch
                detail = {"error": f"{type(ex).__name__}: {ex}"}
                try:
                    fallback, meta = wh.published_frames(key)
                except Exception as fx:
                    fallback, meta = {}, None
                    detail["fallback_error"] = f"{type(fx).__name__}: {fx}"
                if fallback:
                    self.sources[key] = fallback
                    for name, data in fallback.items():
                        data.attrs.setdefault('source_origin_run', (meta or {}).get('run_id'))
                        wh.frame(data, 'standardized', key + '/' + name)
                    self.source_fallbacks[key] = {**detail, **(meta or {}),
                                                  "frames": sorted(fallback),
                                                  "mode": "last_published_standardized"}
                    log.warning(f"🕰️ [{key}] واکشی جدید ناموفق بود؛ آخرین Snapshot منتشرشده استفاده شد.")
                else:
                    self.sources[key] = {}
                    self.source_failures[key] = {**detail, "mode": "unavailable_no_fallback"}
                    log.error(f"❌ [{key}] سورس جداگانه ناموفق شد؛ سایر شاخه‌ها ادامه می‌یابند: {ex}")
        self.ctx.sources = self.sources
        self.ctx.extras['source_failures'] = dict(self.source_failures)
        self.ctx.extras['source_fallbacks'] = dict(self.source_fallbacks)
        loaded = [k for k, v in self.sources.items() if v]
        log.info(f"📦 {len(loaded)} از {len(registry)} سورس برای ادامه Run آماده است: {loaded}")

    def _sheet(self, source: str, frame: str = "main") -> Optional[pd.DataFrame]:
        return self.sources.get(source, {}).get(frame)

    # ═══════ ۲) ادغام ═══════
    def build_base(self) -> pd.DataFrame:
        # V29.7.4: the report population is created by tier-1 business sources.
        # Abbasi/SATA may enrich those cases, but must never create an otherwise
        # absent business row. This separates population authority from merge order.
        df, pop_diag, pop_meta = build_primary_population(self.sources)
        self.ctx.extras['primary_population'] = pop_meta
        if not pop_diag.empty:
            self.ctx.extras['ntsw_order_reg_conflicts'] = pop_diag
            log.warning(f"⚠️ NTSW ORDER→REG: {len(pop_diag)} نگاشت هم‌درجه مبهم؛ REGها مستقل حفظ شدند و رابطه حدس زده نشد.")
        log.info(f"🧱 جمعیت اصلی Tier-1: {len(df)} ردیف | "
                 f"{pop_meta['unique_primary_orders']} سفارش | "
                 f"{pop_meta['unique_primary_regs']} ثبت سفارش | "
                 f"{pop_meta['abbasi_enrichment_rows']} شاهد بارنامه عباسی.")

        mogh = self._sheet("moghavemat")
        self.moghavemat_available = mogh is not None and not mogh.empty

        for src in MERGE_ORDER:
            spec = get_source(src)
            for frame_name, join_on in frames_of(spec).items():
                if src == "moghavemat" and frame_name == "main":
                    continue
                right = self._sheet(src, frame_name)
                if right is None or right.empty:
                    continue
                key = _key_column(join_on) or _KEY_BY_JOIN.get(join_on, KEY_BL)
                for k in (key if isinstance(key, list) else [key]):
                    df = self._ensure_key(df, k)
                key_cols = key if isinstance(key, list) else [key]
                if any(k not in df.columns for k in key_cols):
                    log.warning(f"⚠️ [{src}/{frame_name}] کلید {key} ساخته نشد؛ ادغام رد شد.")
                    continue
                drop = [k for k in _KEY_BY_JOIN.values()
                        if k not in key_cols and k in right.columns]
                label = src if frame_name == "main" else f"{src}/{frame_name}"
                try:
                    df = safe_merge(
                        df, right.drop(columns=drop, errors="ignore"),
                        key, label, keep_by=spec.dedupe_by,
                        zero_match_degraded=(
                            str(spec.opt("diagnostic_status", "")).strip().lower()
                            != "known_incomplete"
                        ),
                    )
                except RowExplosionError as ex:
                    item={"contract":f"merge/{label}","source":src,"frame":frame_name,
                          "key":key_cols,"error":str(ex),"rows_before":len(df)}
                    self.merge_failures.append(item)
                    log.error(f"🧯 [{label}] ادغام ناامن قرنطینه شد؛ شاخه‌های بعدی ادامه می‌یابند: {ex}")
                    continue

        # Tier-1 NTSW REG evidence was attached while constructing the population.
        # Re-materialize REG only after secondary SATA enrichment is present so
        # authority ordering can choose NTSW first and use SATA only for blanks.
        # Build REG after the NTSW authority bridge, so config/keys.yaml sees
        # NTSW_KEY_REG before SATA_KEY_REG and the tier-1 value wins.
        df = self._ensure_key(df, KEY_REG, force=True)
        for sheet, label, keep in (("commitment", "ntsw_commitment", "NTSW_COMMIT_DATE"),
                                   ("allocation", "ntsw_allocation", "NTSW_ALLOC_DATE")):
            right = self._sheet("ntsw", sheet)
            if right is not None and not right.empty:
                try:
                    df = safe_merge(df, right, KEY_REG, label, keep_by=keep)
                except RowExplosionError as ex:
                    self.merge_failures.append({"contract":f"merge/{label}","source":"ntsw",
                                                "frame":sheet,"key":[KEY_REG],"error":str(ex),
                                                "rows_before":len(df)})
                    log.error(f"🧯 [{label}] ادغام ناامن قرنطینه شد و Run برای ممیزی ادامه یافت: {ex}")
        return df

    def _ensure_key(self, df: pd.DataFrame, key: str, force: bool = False) -> pd.DataFrame:
        """کلید مشتق را دقیقاً پیش از نخستین استفاده می‌سازد.

        منبع تعریف: ``config/keys.yaml``. اگر کلیدی آنجا تعریف شده باشد،
        همان مسیر استفاده می‌شود؛ در غیر این صورت به رفتار پیش‌فرض
        برمی‌گردیم تا نسخه‌های قدیمی هم کار کنند.
        """
        from .config.keys import get_keys
        kr = get_keys()
        name = next((n for n, s_ in kr.keys.items() if s_.column == key), None)
        if name and not kr.get(name).is_composite:
            have = (key in df.columns
                    and df[key].astype(str).str.strip().ne("").any())
            if force:
                # Re-materialize from the declared authority order after a higher-tier
                # source has been attached. Preserve an existing valid key only where
                # none of the declared source columns can supply a value. This is used
                # for REG after the NTSW authority bridge so an earlier SATA technical
                # key cannot survive as the report truth.
                old = df[key].copy() if key in df.columns else pd.Series("", index=df.index, dtype=object)
                df = kr.build(df, name)
                blank = df[key].astype(str).str.strip().eq("")
                if blank.any():
                    df.loc[blank, key] = old.loc[blank]
                return df
            if not have:
                return kr.build(df, name)
            return df
        return self._ensure_key_legacy(df, key)

    def _ensure_key_legacy(self, df: pd.DataFrame, key: str) -> pd.DataFrame:
        if key in df.columns and df[key].astype(str).str.strip().ne("").any():
            return df
        if key == KEY_MATERIAL:
            df[KEY_MATERIAL] = self._first_nonempty(
                df, ["MOGH_MATERIAL", "MOGH_MFR_PART_NO"]).map(clean_part_no)
            n = int(df[KEY_MATERIAL].astype(str).str.strip().ne("").sum())
            log.info(f"🔑 کلید متریال ساخته شد — {n} از {len(df)} ردیف معتبر.")
        elif key == KEY_PR:
            df[KEY_PR] = self._first_nonempty(df, ["MOGH_KEY_PR", "MOGH_PR_NO"]).map(clean_key)
        elif key == KEY_REG:
            # ⚠️ ترتیب مهم است: «ثبت سفارش» ساتا ۱۰۰٪ پر است و کلید واقعی NTSW
            # است. «شماره پرونده ثبت سفارش» فایل IL عدد دیگری است و کلید نیست.
            df[KEY_REG] = self._first_nonempty(
                df, ["SATA_KEY_REG", "FX_KEY_REG", "CRD_KEY_REG", "IL_KEY_REG"]).map(clean_key)
            n = int(df[KEY_REG].astype(str).str.strip().ne("").sum())
            log.info(f"🔑 کلید ثبت سفارش ساخته شد — {n} از {len(df)} ردیف "
                     f"({df[KEY_REG].nunique()} کد یکتا)")
        return df

    @staticmethod
    def _first_nonempty(df: pd.DataFrame, names: List[str], default: Any = "") -> pd.Series:
        out = pd.Series([default] * len(df), index=df.index, dtype="object")
        for n in names:
            if n in df.columns:
                need = out.map(is_empty_val)
                out.loc[need] = df[n].loc[need]
        return out

    # ═══════ ۳) اجرای مرحله‌ها ═══════
    def run_stages(self, df: pd.DataFrame) -> pd.DataFrame:
        for st in self.stages:
            missing = [c for c in st.requires if c not in df.columns]
            if missing:
                msg = (f"مرحله «{st.name}» متوقف شد: ستون‌های {missing} در داده نیستند. "
                       f"این ستون‌ها را باید مرحله‌ای پیش از ترتیب {st.order} تولید کند.")
                if st.tolerant:
                    log.warning(f"⚠️ {msg} (مرحله رد شد)")
                    continue
                raise RuntimeError(msg)
            n_before, c_before = len(df), len(df.columns)
            before = df
            try:
                with health.current().timed_stage(st.name, st.title, st.order,
                                                  n_before, c_before) as box:
                    # copy: هر مرحله ده‌ها ستون اضافه می‌کند و بدون آن pandas
                    # قاب را تکه‌تکه نگه می‌دارد و PerformanceWarning می‌دهد.
                    box["df"] = df = st.run(df, self.ctx).copy()
                if len(df) != n_before and st.name != "sort":
                    raise RuntimeError(
                        f"مرحله «{st.name}» تعداد سطرها را عوض کرد "
                        f"({n_before} → {len(df)}). مرحله‌ها نباید سطر اضافه/حذف کنند.")
                health.check_key_integrity(st.name, df)
            except Exception as ex:
                # V29.7.5 — شاخه‌های tolerant باید واقعاً ایزوله باشند. قبلاً
                # tolerant فقط نبودن requires را تحمل می‌کرد ولی exception داخل
                # خود stage کل Run و تمام جریان‌های مستقل را متوقف می‌کرد.
                if not st.tolerant:
                    raise
                df = before.copy()
                for c in st.provides:
                    if c not in df.columns:
                        df[c] = pd.NA
                item = {"stage": st.name, "title": st.title, "order": st.order,
                        "error": f"{type(ex).__name__}: {ex}", "rows_preserved": len(df)}
                self.ctx.extras.setdefault("stage_failures", []).append(item)
                log.error(f"🧯 مرحله tolerant «{st.name}» قرنطینه شد؛ سایر جریان‌ها ادامه می‌یابند: {ex}")
        health.log_slowest_stages(log)
        return df

    # ═══════ اجرا ═══════
    def run(self, build_report: bool = True) -> PipelineResult:
        from .warehouse.bridge import run_pipeline
        return run_pipeline(self,build_report,PACKAGE_VERSION)

    def _run_warehouse(self, build_report: bool = True) -> PipelineResult:
        bar = "=" * 90
        log.info(f"{bar}\n🚀 GSI {PACKAGE_VERSION} — تاریخ مرجع: {self.today}\n{bar}")
        health.reset()
        self.preflight()
        self.load_sources()
        df = self.build_base()
        df = self.run_stages(df)
        lines = self._sheet("moghavemat", "lines")
        # پوشش Commercial Expert Data باید روی **کل جریان اصلی** سنجیده شود،
        # نه فقط part.main؛ چون سفارشِ فاقد مقاومت/سند نیز ممکن است در M3
        # و «تعیین تکلیف» قرار بگیرد و نباید از شمارش جا بیفتد.
        # این پرچم فقط پوشش سورس را گزارش می‌کند؛ هیچ کارشناس خریدی از روی
        # فقدان رکورد ساخته نمی‌شود و موتور بحرانی از آن استفاده نمی‌کند.
        df = apply_commercial_coverage(df, lines, self.ctx)
        part = partition(df, self.moghavemat_available)

        res = PipelineResult(part.df, part.main, part.to_resolve, part.excluded,
                             part.counts, self.resolver.audit_df(),
                             extras=self.ctx.extras,
                             mogh_lines=lines if lines is not None else pd.DataFrame())
        from .warehouse.bridge import persist_result,report_metadata
        persist_result(res)

        if build_report:
            res.dashboard_path = self.build_report(res)
            res.extract_paths = write_expert_extracts(res.main, SETTINGS.expert_extracts_dir)
            write_audit_report(res.audit, os.path.join(
                SETTINGS.OUTPUT_DIR, "GSI_Data_Conflicts_Audit.xlsx"))
        report_metadata(res)
        log.info("✅ هسته محاسباتی پایان یافت؛ کنترل کیفیت، Business DWH و انتشار Snapshot ادامه دارد.")
        return res

    # ═══════ گزارش ═══════
    def build_report(self, res: PipelineResult, path: str | None = None) -> str:
        # خروجی رسمی روزانه: تاریخ در ابتدای نام + نام ثابت، داخل پوشه همان روز.
        path = path or SETTINGS.daily_report_path(self.today)
        b = ExcelDashboardBuilder(path)
        main = res.main
        active = main[~main["IS_CANCELLED"].astype(bool)] if "IS_CANCELLED" in main else main

        # KPIها را خود مرحله‌ها اعلام می‌کنند — این فایل چیزی نمی‌داند
        kpis: Dict[str, tuple] = {}
        for st in self.stages:
            try:
                kpis.update(st.kpis(active, self.ctx))
            except Exception as ex:
                log.warning(f"⚠️ KPI مرحله «{st.name}» ساخته نشد: {ex}")

        uniq_bl = int(active["CANONICAL_BL"].replace("", np.nan).nunique())
        uniq_ord = int(active["CANONICAL_ORDER"].replace("", np.nan).nunique())
        kpis.update({
            "سفارش‌های یکتا در جریان": (uniq_ord, "بر اساس CANONICAL_ORDER"),
            "سفارش خارج از Commercial Expert Data": commercial_kpi(
                res.df, int(res.extras.get("missing_commercial_order_count", 0))),
            "بارنامه‌های یکتا": (uniq_bl, "بر اساس CANONICAL_BL، نه تعداد ردیف"),
            "ردیف‌های ابطالی (خارج از KPI)": (
                int(main.get("IS_CANCELLED", pd.Series(dtype=bool)).sum()),
                "طبق status_lexicon.yaml"),
        })

        narrative = (
            f"گزارش حاکمیت داده GSI {PACKAGE_VERSION}: {uniq_ord} سفارش و {uniq_bl} "
            f"بارنامه یکتا همسان‌سازی شد. {len(res.to_resolve)} ردیف جهت تعیین تکلیف "
            f"جدا شد و {len(res.audit)} تعارض داده ثبت گردید. "
            f"{len(self.stages)} مرحله فرآیند اجرا شد؛ "
            f"{len(self.rb.needs_verification())} قاعده نیازمند تطبیق با بخشنامه است. "
            f"سیاست اعتبار کل گزارش: {policy_label()}."
        )

        specs = collect_columns(self.stages)
        rows = b.build_matrix(main, specs)
        b.build_executive(kpis, narrative, rows)
        b.build_to_resolve(res.to_resolve, main_df=res.df)
        b.build_commitment(main)
        b.build_scorecard(active)
        # مستندات ریاضی را هم خود مرحله‌ها اعلام می‌کنند
        math_docs: Dict[str, Dict[str, Any]] = {}
        for st in self.stages:
            try:
                math_docs.update(st.math_docs(self.ctx))
            except Exception as ex:
                log.warning(f"⚠️ مستندات ریاضی مرحله «{st.name}» ساخته نشد: {ex}")
        math_docs["ممیزی"] = {"تعارضات ثبت‌شده": len(res.audit),
                              "قواعد نیازمند تطبیق": len(self.rb.needs_verification())}
        b.build_math(math_docs)
        # قرارداد Workbook ثابت 17 شیت است. حتی اگر سورس اختیاری
        # Commercial Expert Data در دسترس نباشد، شیت 7 باید به‌صورت
        # empty-state باقی بماند تا شماره‌گذاری/قرارداد خروجی تغییر نکند.
        b.build_order_lines(res.mogh_lines)
        b.build_rulebook_sheet(self.rb)
        b.build_criticality(main)
        b.build_process(res.extras, describe(self.stages))
        # نمودارها آخرین شیت‌اند تا شماره‌گذاری با ترتیب واقعی بخواند
        b.build_charts(main, res.extras)
        b.build_insight(main)
        b.build_material(main)
        b.build_supply_views(main)
        b.build_system_health()
        return b.save()


def main() -> PipelineResult:
    return Pipeline().run()


if __name__ == "__main__":
    main()
