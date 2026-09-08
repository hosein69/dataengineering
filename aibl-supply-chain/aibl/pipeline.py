# -*- coding: utf-8 -*-
"""ارکستراتور — عمداً «لاغر».

این فایل هیچ منطق کسب‌وکاری ندارد و نباید داشته باشد. کارش فقط این است:

    قوانین → کشف سورس‌ها → ادغام → اجرای مرحله‌ها → افراز → گزارش

منطق در سه جای مستقل زندگی می‌کند و هر سه بدون لمس این فایل قابل تغییرند:
    aibl/rules/*.yaml     اعداد و قواعد
    aibl/config/sources.yaml   کدام سورس، از کجا، با کدام کلید
    aibl/stages/*.py      هر گام فرآیند، با ورودی/خروجی/ستون‌های اعلام‌شده

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
from .config.sources import MERGE_ORDER, get_source
from .core.text import clean_key, clean_order_ref, clean_part_no, is_empty_val
from .dataio.logging_setup import log
from .dataio.merge import safe_merge
from .report.dashboard import ExcelDashboardBuilder
from .report.extracts import write_audit_report, write_expert_extracts
from .resolve.canonical import CanonicalEntityResolver
from .resolve.partition import partition
from .rulebook import get_rulebook
from .stages import (PipelineContext, collect_columns, describe, discover as
                     discover_stages, log_plan, validate_graph)
from .version import PACKAGE_VERSION, check_contracts

def _key_column(join_on: str):
    """نام ستون کلید از رجیستری ``config/keys.yaml``.

    برای کلید مرکب، فهرست ستون‌های اجزا برگردانده می‌شود تا safe_merge
    بتواند روی چند ستون هم‌زمان ادغام کند.
    """
    from .config.keys import get_keys
    kr = get_keys()
    try:
        spec = kr.get(join_on)
    except KeyError:
        log.error(f"❌ کلید «{join_on}» در config/keys.yaml تعریف نشده است.")
        return None
    if spec.is_composite:
        return [kr.get(p).column if p in kr.keys else p for p in spec.parts]
    return spec.column


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
                f"فقط فریم main ادغام می‌شود. → python -m aibl.doctor")
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

    # ═══════ ۰) اعتبارسنجی پیش از خواندن هر داده‌ای ═══════
    def preflight(self) -> None:
        issues = check_contracts()
        if issues:
            for i in issues:
                log.error(f"❌ اختلاف نسخه فایل: {i.message}")
            raise RuntimeError(
                "نسخه فایل‌های پکیج با هم نمی‌خواند. فقط فایل‌های بالا را "
                "به‌روزرسانی کنید — نیازی به جایگزینی کل پکیج نیست. "
                "برای گزارش کامل: python -m aibl.doctor")

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
        registry = discover_adapters()
        for key, cls in registry.items():
            self.sources[key] = cls().load()
        self.ctx.sources = self.sources
        loaded = [k for k, v in self.sources.items() if v]
        log.info(f"📦 {len(loaded)} از {len(registry)} سورس بارگذاری شد: {loaded}")

    def _sheet(self, source: str, frame: str = "main") -> Optional[pd.DataFrame]:
        return self.sources.get(source, {}).get(frame)

    # ═══════ ۲) ادغام ═══════
    def build_base(self) -> pd.DataFrame:
        base = self._sheet("abbasi")
        if base is None or base.empty:
            raise RuntimeError("فایل مبدأ (abbasi/BLs Tracking) در دسترس نیست.")
        df = base.copy()
        df[KEY_ORDER] = df[KEY_ORDER].map(clean_order_ref)
        log.info(f"🧱 جدول پایه: {len(df)} ردیف، "
                 f"{int(df[KEY_BL].ne('').sum())} بارنامه معتبر.")

        mogh = self._sheet("moghavemat")
        self.moghavemat_available = mogh is not None and not mogh.empty

        for src in MERGE_ORDER:
            spec = get_source(src)
            for frame_name, join_on in frames_of(spec).items():
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
                df = safe_merge(df, right.drop(columns=drop, errors="ignore"),
                                key, label, keep_by=spec.dedupe_by)

        df = self._ensure_key(df, KEY_REG)
        for sheet, label, keep in (("commitment", "ntsw_commitment", "NTSW_COMMIT_DATE"),
                                   ("allocation", "ntsw_allocation", "NTSW_ALLOC_DATE")):
            right = self._sheet("ntsw", sheet)
            if right is not None and not right.empty:
                df = safe_merge(df, right, KEY_REG, label, keep_by=keep)
        return df

    def _ensure_key(self, df: pd.DataFrame, key: str) -> pd.DataFrame:
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
            n_before = len(df)
            df = st.run(df, self.ctx)
            # هر مرحله ده‌ها ستون اضافه می‌کند؛ بدون این، pandas قاب را
            # تکه‌تکه نگه می‌دارد و PerformanceWarning می‌دهد.
            df = df.copy()
            if len(df) != n_before and st.name != "sort":
                raise RuntimeError(
                    f"مرحله «{st.name}» تعداد سطرها را عوض کرد "
                    f"({n_before} → {len(df)}). مرحله‌ها نباید سطر اضافه/حذف کنند.")
        return df

    # ═══════ اجرا ═══════
    def run(self, build_report: bool = True) -> PipelineResult:
        log.info("=" * 90)
        log.info(f"🚀 AIBL {PACKAGE_VERSION} — تاریخ مرجع: {self.today}")
        log.info("=" * 90)
        self.preflight()
        self.load_sources()
        df = self.build_base()
        df = self.run_stages(df)
        part = partition(df, self.moghavemat_available)
        lines = self._sheet("moghavemat", "lines")

        res = PipelineResult(part.df, part.main, part.to_resolve, part.excluded,
                             part.counts, self.resolver.audit_df(),
                             extras=self.ctx.extras,
                             mogh_lines=lines if lines is not None else pd.DataFrame())
        if build_report:
            res.dashboard_path = self.build_report(res)
            res.extract_paths = write_expert_extracts(res.main, SETTINGS.expert_extracts_dir)
            write_audit_report(res.audit, os.path.join(
                SETTINGS.OUTPUT_DIR, "AIBL_Data_Conflicts_Audit.xlsx"))
        log.info("🏁 خط لوله با موفقیت پایان یافت.")
        return res

    # ═══════ گزارش ═══════
    def build_report(self, res: PipelineResult) -> str:
        # خروجی رسمی روزانه: تاریخ در ابتدای نام + نام ثابت، داخل پوشه همان روز.
        path = SETTINGS.daily_report_path(self.today)
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
            "بارنامه‌های یکتا": (uniq_bl, "بر اساس CANONICAL_BL، نه تعداد ردیف"),
            "ردیف‌های ابطالی (خارج از KPI)": (
                int(main.get("IS_CANCELLED", pd.Series(dtype=bool)).sum()),
                "طبق status_lexicon.yaml"),
        })

        narrative = (
            f"گزارش حاکمیت داده AIBL {PACKAGE_VERSION}: {uniq_ord} سفارش و {uniq_bl} "
            f"بارنامه یکتا همسان‌سازی شد. {len(res.to_resolve)} ردیف جهت تعیین تکلیف "
            f"جدا شد و {len(res.audit)} تعارض داده ثبت گردید. "
            f"{len(self.stages)} مرحله فرآیند اجرا شد؛ "
            f"{len(self.rb.needs_verification())} قاعده نیازمند تطبیق با بخشنامه است."
        )

        specs = collect_columns(self.stages)
        rows = b.build_matrix(main, specs)
        b.build_executive(kpis, narrative, rows)
        b.build_to_resolve(res.to_resolve)
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
        if not res.mogh_lines.empty:
            b.build_order_lines(res.mogh_lines)
        b.build_rulebook_sheet(self.rb)
        b.build_criticality(main)
        b.build_process(res.extras, describe(self.stages))
        # نمودارها آخرین شیت‌اند تا شماره‌گذاری با ترتیب واقعی بخواند
        b.build_charts(main, res.extras)
        b.build_insight(main)
        b.build_material(main)
        return b.save()


def main() -> PipelineResult:
    return Pipeline().run()


if __name__ == "__main__":
    main()
