# -*- coding: utf-8 -*-
"""بازرس رابطه‌ها (Join Diagnostics) — «کجا ریلیشن نشده؟»

## مسئله‌ای که این ابزار حل می‌کند

خط لوله می‌گوید «۰ ردیف منطبق» ولی **نمی‌گوید چرا**. سه علت کاملاً متفاوت
خروجی یکسانی دارند:

    ۱. فایل اصلاً پیدا نشد            → الگوی فایل غلط است
    ۲. فایل هست ولی ستون کلید نبود    → نگاشت ستون غلط است
    ۳. هر دو کلید هست ولی هم‌شکل نیست → نرمال‌سازی کلید غلط است
       (مثلاً «503110D» در یک سورس و «503110-D» یا «0503110» در سورس دیگر)

بدون تفکیک این سه، کاربر مجبور است حدس بزند. این ابزار هر سه را با **نمونه
واقعی کلیدها از دو طرف** تفکیک می‌کند و می‌گوید کدام‌یک است.

## اجرا

    python -m gsi.diagnose              گزارش کنسولی
    python -m gsi.diagnose --excel      + فایل اکسل تشخیصی در پوشه خروجی
"""
from __future__ import annotations

__contract__ = 2

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd

from .adapters import discover as discover_adapters
from .adapters.base import (KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_PR, KEY_REG, KEY_REG_FILE)
from .config.settings import SETTINGS
from .config.sources import MERGE_ORDER, SOURCES, get_source
from .dataio.logging_setup import log

_KEY_BY_JOIN = {"BL": KEY_BL, "ORDER": KEY_ORDER, "REG": KEY_REG,
                "REG_FILE": KEY_REG_FILE, "PR": KEY_PR,
                "EMP": KEY_EMP, "MATERIAL": KEY_MATERIAL}

# کلیدهای مرکب دانه هستند، نه یک ستون ساده برای join با جدول پایه.
_COMPOSITE_BY_JOIN = {
    "ORDER_MATERIAL": (KEY_ORDER, KEY_MATERIAL),
}

# تشخیص علت: کد → (عنوان فارسی، اقدام پیشنهادی)
CAUSES = {
    "FILE_MISSING": ("فایل پیدا نشد",
                     "الگوی pattern در config/sources.yaml را با نام واقعی فایل تطبیق دهید."),
    "SHEET_EMPTY": ("فایل هست ولی شیت خالی است",
                    "نام شیت را در sources.yaml بررسی کنید."),
    "KEY_COLUMN_MISSING": ("ستون کلید در سورس پیدا نشد",
                           "فهرست کاندیدهای ستون کلید را در adapter همان سورس اضافه کنید."),
    "KEY_ALL_EMPTY": ("ستون کلید هست ولی همه مقادیر تهی یا نامعتبرند",
                      "تابع نرمال‌سازی کلید (clean_bl / clean_part_no) مقادیر را رد می‌کند."),
    "NO_OVERLAP": ("هر دو طرف کلید دارند ولی هیچ اشتراکی ندارند",
                   "شکل کلید در دو سورس یکی نیست — نمونه‌ها را در جدول زیر مقایسه کنید."),
    "PARTIAL": ("پوشش محدود/جزئی",
                "این وضعیت لزوماً خطا نیست؛ سورس ممکن است فقط زیرمجموعه‌ای از بیزینس را پوشش دهد. نمونه‌های unmatched را بررسی کنید."),
    "GRAIN_DUPLICATE": ("نقض دانه/کلید مرکب",
                        "کلید مرکب یکتا نیست؛ قبل از هر join علت تکرارها را در سطح ردیف بررسی کنید."),
    "GRAIN_OK": ("دانه ترکیبی سالم", ""),
    "KNOWN_INCOMPLETE_SOURCE": ("سورس ناقصِ شناخته‌شده — فعلاً خارج از ارزیابی",
                                "تا تکمیل سورس اقدامی لازم نیست؛ این رابطه در سلامت کل لحاظ نمی‌شود."),
    "HEALTHY_LIMITED_SCOPE": ("Join سالم؛ دامنه‌ی سورس محدود است",
                              "نیازی به اصلاح کلید نیست؛ Base Coverage فقط دامنه‌ی بیزینسی سورس را نشان می‌دهد."),
    "HEALTHY_WITH_GAPS": ("Join عمدتاً سالم با unmatched محدود",
                            "unmatchedهای باقی‌مانده ثبت شده‌اند؛ تا اثبات علت، هیچ تطبیق خودکاری انجام نشود."),
    "SOURCE_MATCH_REVIEW": ("بخشی معنادار از رکوردهای سورس resolve نشده‌اند",
                            "unmatchedهای سورس را بر اساس scope/normalization/namespace بررسی کنید؛ Base Coverage معیار خرابی نیست."),
    "SOURCE_MATCH_LOW": ("نرخ resolve سورس پایین است",
                         "ابتدا semantics کلید و population سورس را بررسی کنید؛ هیچ fuzzy/strip خودکاری اعمال نشود."),
    "NO_COMMON_EVIDENCE": ("هیچ شاهد مشترک اثبات‌شده‌ای وجود ندارد",
                           "رابطه را نامعتبر فرض نکنید؛ semantics کلید، population و بازه زمانی دو طرف را با raw evidence بررسی کنید."),
    "OK": ("سالم", ""),
}

# سلامت join از دید SOURCE سنجیده می‌شود، نه از Base Coverage.
# Base Coverage فقط دامنه‌ی بیزینسی سورس را نشان می‌دهد.
SOURCE_MATCH_HEALTHY = 0.98
SOURCE_MATCH_MOSTLY = 0.90
SOURCE_MATCH_REVIEW = 0.70

# سورس‌هایی که کاربر صریحاً ناقص/در حال تکمیل اعلام کرده است. این‌ها در تشخیص
# دیده می‌شوند ولی نه خطا محسوب می‌شوند و نه Publish/QA را گمراه می‌کنند.
def _known_incomplete(src: str, frame: str) -> bool:
    try:
        spec = get_source(src)
    except Exception:
        return False
    return str(spec.opt("diagnostic_status", "")).strip().lower() == "known_incomplete"

# انتظار cardinality در سطح relation. این metadata برای تشخیص است و هیچ join
# خودکاری را تغییر نمی‌دهد.
RELATION_CARDINALITY = {
    ("moghavemat", "main", KEY_ORDER): "M:1 (یک Order canonical برای هر رکورد سورس)",
    ("doccheck", "main", KEY_ORDER): "M:1 (چند سند می‌تواند به یک Order تعلق داشته باشد)",
    ("fx_transaction", "main", KEY_REG): "M:1 (چند تراکنش می‌تواند به یک REG تعلق داشته باشد)",
    ("credit", "main", KEY_REG): "M:1 (چند رکورد اعتباری می‌تواند به یک REG تعلق داشته باشد)",
    ("ntsw", "commitment", KEY_REG): "M:1",
    ("ntsw", "allocation", KEY_REG): "M:1",
    ("ntsw", "import_license", KEY_REG_FILE): "M:1",
    ("ilappend", "main", KEY_REG_FILE): "M:1",
    ("abbasi", "main", KEY_BL): "1:1 preferred",
    ("sata", "main", KEY_BL): "M:1",
    ("clearance", "main", KEY_BL): "M:1 (رویداد/ردیف‌های متعدد مجاز)",
    ("cotage", "main", KEY_BL): "M:1 (رویداد/ردیف‌های متعدد مجاز)",
}


class JoinDiagnostics:
    """بدون اجرای کامل خط لوله، وضعیت هر رابطه را می‌سنجد."""

    def __init__(self) -> None:
        self.sources: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.base: Optional[pd.DataFrame] = None
        self.rows: List[Dict[str, Any]] = []
        self.samples: List[Dict[str, Any]] = []
        self.unmatched_details: List[Dict[str, Any]] = []

    # ── بارگذاری ──
    def load(self) -> None:
        for key, cls in discover_adapters().items():
            try:
                self.sources[key] = cls().load()
            except Exception as ex:
                log.error(f"❌ [{key}] adapter شکست خورد: {ex}")
                self.sources[key] = {}
        self.base = self.sources.get("abbasi", {}).get("main")

    # ── سنجش یک رابطه ──
    @staticmethod
    def _clean_set(df: Optional[pd.DataFrame], col: str, *, material: bool = False) -> set:
        if df is None or col not in df.columns:
            return set()
        from .core.text import clean_key, clean_part_no
        norm = clean_part_no if material else clean_key
        vals = {norm(v) for v in df[col].tolist()}
        return {v for v in vals if v}

    def _left_keys_for(self, src: str, frame: str, key: str) -> set:
        """مرجع درست هر رابطه بر اساس semantics بیزینس، نه یک base عمومی.

        REG و REG_FILE عمداً جدا هستند. برای NTSW، Import Licence هاب داخلی
        است و commitment/allocation باید ابتدا با REG همان شیت سنجیده شوند.
        """
        if key == KEY_REG_FILE:
            if src == "ilappend":
                return self._clean_set(self.sources.get("ntsw", {}).get("import_license"), KEY_REG_FILE)
            return self._clean_set(self.sources.get("ilappend", {}).get("main"), KEY_REG_FILE)
        if key == KEY_REG:
            if src == "ntsw" and frame in {"commitment", "allocation", "allocation_rows"}:
                return self._clean_set(self.sources.get("ntsw", {}).get("import_license"), KEY_REG)
            # universe ثبت سفارش از شواهد مستقیم، بدون REG_FILE
            out = set()
            for s, f, c in [
                ("ntsw", "import_license", KEY_REG),
                ("sata", "main", "SATA_KEY_REG"),
                ("ilappend", "main", "IL_KEY_REG"),
            ]:
                out |= self._clean_set(self.sources.get(s, {}).get(f), c)
            return out
        if key == KEY_PR:
            out = self._clean_set(self.sources.get("moghavemat", {}).get("lines"), KEY_PR)
            if not out:
                out = self._clean_set(self.sources.get("moghavemat", {}).get("main"), "MOGH_KEY_PR")
            return out
        if key == KEY_MATERIAL:
            out = self._clean_set(self.sources.get("moghavemat", {}).get("inventory"), KEY_MATERIAL, material=True)
            if not out:
                out = self._clean_set(self.sources.get("moghavemat", {}).get("lines"), KEY_MATERIAL, material=True)
            return out
        if key == KEY_EMP:
            out = self._clean_set(self.sources.get("moghavemat", {}).get("main"), "MOGH_KEY_EMP")
            out |= self._clean_set(self.sources.get("moghavemat", {}).get("lines"), "MOGH_KEY_EMP")
            return out
        # BL / ORDER مرجع عملیاتی Abbasi است.
        return self._clean_set(self.base, key)

    def _check_composite(self, src: str, frame: str, join_on: str) -> Dict[str, Any]:
        parts = _COMPOSITE_BY_JOIN[join_on]
        spec = get_source(src)
        df = self.sources.get(src, {}).get(frame)
        row: Dict[str, Any] = {
            "سورس": src, "فریم": frame, "کلید": "+".join(parts),
            "الگوی فایل": spec.pattern, "پوشه": spec.folder,
            "ردیف سورس": 0, "کلید معتبر در سورس": 0, "کلید یکتا در سورس": 0,
            "کلید یکتا در جدول پایه": 0, "اشتراک کلید": 0,
            "Source Match (٪)": None, "Base Coverage (٪)": None, "پوشش (٪)": None,
            "Grain Uniqueness (٪)": None,
            "Semantic": "VALIDATED", "Cardinality": "COMPOSITE_GRAIN_UNIQUENESS",
            "Cardinality Health": "UNKNOWN", "Scope Alignment": "SELF_GRAIN",
            "Temporal Alignment": "NOT_ASSESSED", "شدت": "INFO",
            "علت": "GRAIN_OK", "اقدام": "",
        }
        if df is None or df.empty:
            row["علت"] = "SHEET_EMPTY"
            return row
        row["ردیف سورس"] = len(df)
        missing = [c for c in parts if c not in df.columns]
        if missing:
            row["علت"] = "KEY_COLUMN_MISSING"
            row["اقدام"] = "ستون(های) دانه موجود نیست: " + ", ".join(missing)
            return row
        tmp = df[list(parts)].copy()
        for c in parts:
            tmp[c] = tmp[c].fillna("").astype(str).str.strip()
        valid = tmp[(tmp[list(parts)] != "").all(axis=1)]
        row["کلید معتبر در سورس"] = len(valid)
        unique = valid.drop_duplicates(list(parts))
        row["کلید یکتا در سورس"] = len(unique)
        row["اشتراک کلید"] = len(unique)
        row["Grain Uniqueness (٪)"] = round(len(unique) / max(len(valid), 1) * 100, 1)
        dup = len(valid) - len(unique)
        if dup:
            row["علت"] = "GRAIN_DUPLICATE"
            row["Cardinality Health"] = "VIOLATION"
            row["شدت"] = "ERROR"
            row["اقدام"] = f"{dup} ردیف تکراری روی دانه {' + '.join(parts)}؛ dedupe کورکورانه ممنوع است."
        else:
            row["Cardinality Health"] = "OK"
        return row

    @staticmethod
    def _shape_key(value: Any) -> str:
        """فقط برای تشخیص candidate؛ هرگز برای join واقعی استفاده نمی‌شود."""
        import re
        s = str(value or "").strip().upper()
        return re.sub(r"[^0-9A-Z]", "", s)

    def _order_unmatched_breakdown(self, src: str, frame: str, rset: set, lk: set) -> Dict[str, int]:
        """unmatched سفارش را بدون ساخت relation جعلی دسته‌بندی و ثبت می‌کند.

        NORMALIZATION_CANDIDATE فقط candidate است؛ در Core هیچ join جدیدی نمی‌سازد.
        OUTSIDE_BASE_SCOPE یعنی Order در یک شاهد مستقیم دیگر دیده شده ولی در Abbasi فعلی نیست.
        UNRESOLVED یعنی هنوز شاهد کافی برای توضیح وجود ندارد.
        """
        unmatched = {x for x in rset - lk if str(x).strip()}
        if not unmatched:
            return {"NORMALIZATION_CANDIDATE": 0, "OUTSIDE_BASE_SCOPE": 0, "UNRESOLVED": 0}

        base_shape: Dict[str, set] = {}
        for x in lk:
            base_shape.setdefault(self._shape_key(x), set()).add(str(x))

        evidence_by_order: Dict[str, set] = {}
        for s, f, c in [
            ("moghavemat", "main", KEY_ORDER),
            ("moghavemat", "lines", KEY_ORDER),
            ("doccheck", "main", KEY_ORDER),
            ("fx_transaction", "main", KEY_ORDER),
            ("credit", "main", KEY_ORDER),
            ("ilappend", "main", KEY_ORDER),
            ("ntsw", "import_license", KEY_ORDER),
        ]:
            if s == src and f == frame:
                continue
            vals = self._clean_set(self.sources.get(s, {}).get(f), c)
            for v in vals:
                evidence_by_order.setdefault(v, set()).add(f"{s}/{f}")

        counts = {"NORMALIZATION_CANDIDATE": 0, "OUTSIDE_BASE_SCOPE": 0, "UNRESOLVED": 0}
        for x in sorted(unmatched):
            shp = self._shape_key(x)
            candidates = sorted(base_shape.get(shp, set())) if shp else []
            if candidates and str(x) not in lk:
                category = "NORMALIZATION_CANDIDATE"
                evidence = "base_shape=" + ",".join(candidates[:5])
            elif x in evidence_by_order:
                category = "OUTSIDE_BASE_SCOPE"
                evidence = "seen_in=" + ",".join(sorted(evidence_by_order[x]))
            else:
                category = "UNRESOLVED"
                evidence = ""
            counts[category] += 1
            self.unmatched_details.append({
                "سورس": src, "فریم": frame, "کلید": KEY_ORDER,
                "کلید جورنشده": str(x), "طبقه": category,
                "شاهد/کاندید": evidence,
                "اقدام": {
                    "NORMALIZATION_CANDIDATE": "بررسی دستی punctuation/format؛ auto-match ممنوع",
                    "OUTSIDE_BASE_SCOPE": "بررسی scope/زمان Abbasi؛ رکورد حذف نشود",
                    "UNRESOLVED": "نیازمند شاهد یا Rule جدید؛ در unresolved باقی بماند",
                }[category],
            })
        return counts

    @staticmethod
    def _scope_label(source_match: float, base_coverage: float) -> str:
        if source_match >= SOURCE_MATCH_MOSTLY:
            return "ALIGNED" if base_coverage >= 0.50 else "LIMITED_SCOPE"
        return "NEEDS_SCOPE_REVIEW"

    def _check(self, src: str, frame: str, join_on: str) -> Dict[str, Any]:
        if join_on in _COMPOSITE_BY_JOIN:
            return self._check_composite(src, frame, join_on)
        spec = get_source(src)
        key = _KEY_BY_JOIN.get(join_on, KEY_BL)
        right = self.sources.get(src, {}).get(frame)
        left = self.base

        row: Dict[str, Any] = {
            "سورس": src, "فریم": frame, "کلید": key,
            "الگوی فایل": spec.pattern, "پوشه": spec.folder,
            "ردیف سورس": 0, "کلید معتبر در سورس": 0, "کلید یکتا در سورس": 0,
            "کلید یکتا در جدول پایه": 0, "اشتراک کلید": 0,
            "Source Match (٪)": 0.0, "Base Coverage (٪)": 0.0,
            "پوشش (٪)": 0.0,  # alias قدیمی برای backward compatibility = Base Coverage
            "Semantic": "VALIDATED", "Cardinality": RELATION_CARDINALITY.get((src, frame, key), "UNSPECIFIED"),
            "Cardinality Health": "UNKNOWN", "Scope Alignment": "UNKNOWN",
            "Temporal Alignment": "NOT_ASSESSED", "شدت": "INFO",
            "علت": "OK", "اقدام": "",
        }

        if _known_incomplete(src, frame):
            row["علت"] = "KNOWN_INCOMPLETE_SOURCE"
            row["Semantic"] = "NOT_ASSESSED"
            row["Scope Alignment"] = "SOURCE_INCOMPLETE"
            row["شدت"] = "INFO"
            if right is not None:
                row["ردیف سورس"] = len(right)
                if key in right.columns:
                    rk0 = right[key].astype(str).str.strip()
                    rk0 = rk0[rk0 != ""]
                    row["کلید معتبر در سورس"] = int(len(rk0))
                    row["کلید یکتا در سورس"] = int(rk0.nunique())
            return row

        if right is None or len(right) == 0:
            exists = os.path.isdir(spec.folder)
            row["علت"] = "FILE_MISSING" if not exists or not self.sources.get(src) else "SHEET_EMPTY"
            row["شدت"] = "ERROR"
            return row

        row["ردیف سورس"] = len(right)
        if key not in right.columns:
            row["علت"] = "KEY_COLUMN_MISSING"
            return row

        from .core.text import clean_key, clean_part_no
        norm = clean_part_no if key == KEY_MATERIAL else clean_key
        rk_clean = right[key].map(norm)
        rk_clean = rk_clean[rk_clean.astype(str).str.strip().ne("")]
        row["کلید معتبر در سورس"] = int(len(rk_clean))
        row["کلید یکتا در سورس"] = int(rk_clean.nunique())
        if len(rk_clean) == 0:
            row["علت"] = "KEY_ALL_EMPTY"
            row["شدت"] = "ERROR"
            self._sample(src, frame, key, set(), set(right[key].astype(str)))
            return row

        # مرجع رابطه بر اساس semantics بیزینس انتخاب می‌شود؛ یک جدول پایه
        # عمومی برای REG/REG_FILE/PR/MATERIAL معتبر نیست.
        lk = self._left_keys_for(src, frame, key)
        if not lk:
            row["علت"] = "KEY_ALL_EMPTY"
            row["اقدام"] = (f"مرجع معتبر برای {key} ساخته نشد؛ "
                            "ابتدا هاب/سورس تغذیه‌کننده همان کلید را بررسی کنید.")
            return row
        rset = {v for v in rk_clean.tolist() if v}
        row["کلید یکتا در جدول پایه"] = len(lk)
        overlap = lk & rset
        row["اشتراک کلید"] = len(overlap)
        source_match = len(overlap) / max(len(rset), 1)
        base_coverage = len(overlap) / max(len(lk), 1)
        row["Source Match (٪)"] = round(source_match * 100, 1)
        row["Base Coverage (٪)"] = round(base_coverage * 100, 1)
        row["پوشش (٪)"] = row["Base Coverage (٪)"]
        row["Scope Alignment"] = self._scope_label(source_match, base_coverage)
        duplicate_keys = max(row["کلید معتبر در سورس"] - row["کلید یکتا در سورس"], 0)
        expectation = row["Cardinality"]
        if expectation.startswith("1:1") and duplicate_keys:
            row["Cardinality Health"] = f"REVIEW:{duplicate_keys}_REPEATED_ROWS"
        else:
            row["Cardinality Health"] = "OK"

        if not overlap:
            row["علت"] = "NO_COMMON_EVIDENCE"
            row["Semantic"] = "UNPROVEN"
            row["شدت"] = "ERROR"
        elif source_match >= SOURCE_MATCH_HEALTHY:
            if base_coverage < 0.50:
                row["علت"] = "HEALTHY_LIMITED_SCOPE"
            else:
                row["علت"] = "OK"
            row["شدت"] = "INFO"
        elif source_match >= SOURCE_MATCH_MOSTLY:
            row["علت"] = "HEALTHY_WITH_GAPS"
            row["شدت"] = "INFO"
        elif source_match >= SOURCE_MATCH_REVIEW:
            row["علت"] = "SOURCE_MATCH_REVIEW"
            row["شدت"] = "WARNING"
        else:
            row["علت"] = "SOURCE_MATCH_LOW"
            row["شدت"] = "WARNING"

        if key == KEY_ORDER and src in {"moghavemat", "doccheck"}:
            bd = self._order_unmatched_breakdown(src, frame, rset, lk)
            row["Unmatched-NormalizationCandidate"] = bd["NORMALIZATION_CANDIDATE"]
            row["Unmatched-OutsideBaseScope"] = bd["OUTSIDE_BASE_SCOPE"]
            row["Unmatched-Unresolved"] = bd["UNRESOLVED"]
            if sum(bd.values()):
                row["اقدام"] = (
                    f"unmatched: normalization_candidate={bd['NORMALIZATION_CANDIDATE']} | "
                    f"outside_base_scope={bd['OUTSIDE_BASE_SCOPE']} | unresolved={bd['UNRESOLVED']}. "
                    "هیچ تطبیق fuzzy یا حذف punctuation به‌صورت خودکار انجام نشود."
                )

        if source_match < 1.0:
            self._sample(src, frame, key, lk - rset, rset - lk)
        return row

    #: کدام سورس/ستون کلید مشتق را تغذیه می‌کند (هم‌راستا با pipeline._ensure_key)
    DERIVED_SOURCES = {
        KEY_MATERIAL: [("moghavemat", "inventory", KEY_MATERIAL),
                       ("moghavemat", "lines", KEY_MATERIAL)],
        KEY_REG:      [("ntsw", "import_license", KEY_REG),
                       ("sata", "main", "SATA_KEY_REG"),
                       ("ilappend", "main", "IL_KEY_REG"),
                       ("fx_transaction", "main", "FX_KEY_REG"),
                       ("credit", "main", "CRD_KEY_REG")],
        KEY_REG_FILE: [("ntsw", "import_license", KEY_REG_FILE),
                       ("ilappend", "main", KEY_REG_FILE)],
        KEY_PR:       [("moghavemat", "lines", KEY_PR),
                       ("moghavemat", "main", "MOGH_KEY_PR")],
        KEY_EMP:      [("moghavemat", "main", "MOGH_KEY_EMP"),
                       ("ilappend", "main", "IL_KEY_EMP")],
    }

    def _derived_left_keys(self, key: str) -> set:
        """کلید مشتق را از سورس‌های تغذیه‌کننده بازسازی می‌کند."""
        from .core.text import clean_key, clean_part_no
        norm = clean_part_no if key == KEY_MATERIAL else clean_key
        out: set = set()
        for src, frame, col in self.DERIVED_SOURCES.get(key, []):
            df = self.sources.get(src, {}).get(frame)
            if df is None or col not in df.columns:
                continue
            vals = {norm(v) for v in df[col]}
            out |= {v for v in vals if v}
        return out

    def _sample(self, src: str, frame: str, key: str,
                only_left: set, only_right: set, n: int = 6) -> None:
        """نمونه کلیدهای دو طرف که با هم جور نشدند — قلب تشخیص."""
        l = sorted(str(x) for x in list(only_left)[:200])[:n]
        r = sorted(str(x) for x in list(only_right)[:200])[:n]
        for i in range(max(len(l), len(r))):
            self.samples.append({
                "سورس": src, "فریم": frame, "کلید": key,
                "نمونه کلید در جدول پایه": l[i] if i < len(l) else "",
                "نمونه کلید در سورس": r[i] if i < len(r) else "",
            })

    # ── اجرای کامل ──
    def run(self) -> pd.DataFrame:
        self.load()
        checked = set()
        for src in list(MERGE_ORDER) + [s for s in SOURCES if s not in MERGE_ORDER]:
            if src in checked or src not in SOURCES:
                continue
            checked.add(src)
            spec = get_source(src)
            frames = (spec.frame_map() if hasattr(spec, "frame_map")
                      else {"main": spec.join_on})
            available = set(self.sources.get(src, {}).keys())
            for frame, join_on in frames.items():
                if frame not in available and available:
                    continue          # این سورس فریم دیگری دارد؛ نبودِ این یکی خطا نیست
                # IL Append در بیزینس ابتدا با شماره پرونده به Import Licence وصل می‌شود؛
                # مقایسه مستقیم آن با REG جدول پایه، همان خطای مفهومی نسخه قبل بود.
                if src == "ilappend" and frame == "main":
                    self.rows.append(self._check(src, frame, "REG_FILE"))
                else:
                    self.rows.append(self._check(src, frame, join_on))
        # NTSW: هاب Import Licence و سپس دو Fact روی REG.
        if self.sources.get("ntsw", {}).get("import_license") is not None:
            self.rows.append(self._check("ntsw", "import_license", "REG_FILE"))
        for frame in ("commitment", "allocation"):
            if self.sources.get("ntsw", {}).get(frame) is not None:
                self.rows.append(self._check("ntsw", frame, "REG"))
        return pd.DataFrame(self.rows)

    # ── پوشش ستون‌های حیاتی ──
    def critical_columns(self) -> pd.DataFrame:
        """آیا ستون‌هایی که KPIها به آن‌ها وابسته‌اند، اصلاً پر شده‌اند؟"""
        # mode=optional_direct یعنی نبود/تهی بودن ستون «خطای adapter» نیست؛
        # در فایل رسمی چنین فیلد مستقیمی ممکن است اصلاً وجود نداشته باشد.
        want = [
            ("ORC_STOCK_IKCO", "oracle", "main", "موجودی ایران‌خودرو — صورت کسر مقاومت", "required"),
            ("ORC_STOCK_SAPCO", "oracle", "main", "موجودی ساپکو — صورت کسر مقاومت", "required"),
            ("ORC_DAILY_NEED", "oracle", "main", "نیاز روزانه — مخرج کسر مقاومت", "required"),
            ("MOGH_SUPPLIER_STOCK_QTY", "moghavemat", "inventory", "موجودی مستقیم نزد سازنده — جزء Supply Position", "optional_direct"),
            ("MOGH_SUPPLIER_STOCK_QTY_DERIVED", "moghavemat", "inventory", "موجودی مشتق نزد سازنده از Quantity In Order/Part — با basis قابل ممیزی", "derived"),
            ("MOGH_IN_TRANSIT_QTY", "moghavemat", "inventory", "موجودی مستقیم در راه — فقط اگر صریحاً در سورس ثبت شده باشد", "optional_direct"),
            ("MOGH_IN_CUSTOMS_QTY", "moghavemat", "inventory", "موجودی مستقیم در گمرک — فقط اگر صریحاً در سورس ثبت شده باشد", "optional_direct"),
            ("KEY_MATERIAL", "moghavemat", "inventory", "کلید Order×Material Commercial Expert — اتصال به Oracle", "required"),
            ("KEY_MATERIAL", "oracle", "main", "کلید متریال Oracle — اتصال مقاومت", "required"),
            ("BL_DISCHARGE_DATE", "abbasi", "main", "تاریخ تخلیه — مبنای روزهای رسوب", "required"),
            ("CL_CLEAR_DATE", "clearance", "main", "تاریخ مؤثر ترخیص کامل از تاریخ بارگیری نهایی", "required"),
            ("NTSW_INITIAL_COMMIT", "ntsw", "commitment", "ارزش اولیه تعهد — ورودی معتبر CB_VALUE", "required"),
            ("NTSW_BALANCE", "ntsw", "commitment", "مانده تعهد — مبنای جریمه", "required"),
            ("NTSW_COMMIT_DATE", "ntsw", "commitment", "تاریخ CB — مبنای مهلت قانونی", "required"),
            ("SATA_NO", "sata", "main", "کد ساتا — شاهد گمرکی", "required"),
            ("COT_NO", "cotage", "main", "کوتاژ — شاهد گمرکی", "required"),
            ("MOGH_ADDITIONAL_DATA", "moghavemat", "lines", "وضعیت بازرگانی/لجستیک خام؛ main نسخه parsed را نگه می‌دارد", "required"),
            ("DOC_SUBMIT_DATE", "doccheck", "main", "تاریخ ارائه اسناد", "required"),
            ("FX_AMOUNT", "fx_transaction", "main", "مبلغ خرید ارز — شاهد جریان مالی؛ CB_VALUE الزاماً ستون FX نیست", "required"),
        ]
        out = []
        for col, src, frame, why, mode in want:
            df = self.sources.get(src, {}).get(frame)
            if df is None or len(df) == 0:
                out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                            "ردیف": 0, "پرشده": 0, "نرخ پر بودن (٪)": 0.0,
                            "وضعیت": "❌ سورس در دسترس نیست"})
                continue
            if col not in df.columns:
                status = ("ℹ️ فیلد مستقیم در سورس رسمی موجود نیست؛ صفر فرض نشود"
                          if mode == "optional_direct" else
                          "❌ ستون مورد انتظار ساخته نشد (نگاشت/قرارداد adapter)")
                out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                            "ردیف": len(df), "پرشده": 0, "نرخ پر بودن (٪)": 0.0,
                            "وضعیت": status})
                continue
            col_s = df[col]
            if pd.api.types.is_numeric_dtype(col_s):
                # ⚠️ برای ستون عددی، صفر یک مقدار معتبر است نه فقدان مقدار.
                # «مانده تعهد = ۰» یعنی رفع تعهد شده، نه اینکه داده نیست.
                filled = int(col_s.notna().sum())
                nonzero = int((col_s.fillna(0) != 0).sum())
            else:
                t = col_s.astype(str).str.strip().replace(
                    {"nan": "", "None": "", "NaT": "", "<NA>": "", "*": ""})
                filled = int(t.ne("").sum())
                nonzero = filled
            pct = round(filled / max(len(df), 1) * 100, 1)
            pct_nz = round(nonzero / max(len(df), 1) * 100, 1)
            if mode == "optional_direct" and pct == 0:
                status = "ℹ️ مقدار مستقیم ثبت نشده؛ Missing است نه Zero و نه خطای adapter"
            elif mode == "derived" and pct > 0:
                status = "✅ مشتق قابل ممیزی (basis در inventory ذخیره شده)"
            else:
                status = ("✅ سالم" if pct >= 50 else
                          "⚠️ کم" if pct > 0 else "❌ همه تهی — قرارداد/نگاشت را بررسی کنید")
            if pct >= 50 and pct_nz < 20:
                status = "✅ پر است (اکثراً صفر — و صفر مقدار معتبری است)"
            out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                        "ردیف": len(df), "پرشده": filled,
                        "نرخ پر بودن (٪)": pct, "نرخ غیرصفر (٪)": pct_nz,
                        "وضعیت": status})
        return pd.DataFrame(out)

    # ── ستون‌های واقعی هر سورس، برای تطبیق دستی ──
    def raw_headers(self) -> pd.DataFrame:
        out = []
        for src, frames in self.sources.items():
            for frame, df in frames.items():
                if df is None or len(df) == 0:
                    continue
                out.append({"سورس": src, "فریم": frame, "ردیف": len(df),
                            "تعداد ستون": len(df.columns),
                            "ستون‌ها": " | ".join(str(c) for c in list(df.columns)[:40])})
        return pd.DataFrame(out)


def _print(df: pd.DataFrame, title: str) -> None:
    print("\n" + "═" * 78)
    print(title)
    print("═" * 78)
    if df.empty:
        print("   (خالی)")
        return
    with pd.option_context("display.width", 200, "display.max_colwidth", 46):
        print(df.to_string(index=False))


def main() -> int:
    print("═" * 78)
    print("GSI — بازرس رابطه‌ها: کجا ریلیشن برقرار نشده؟")
    print("═" * 78)

    d = JoinDiagnostics()
    joins = d.run()

    view = joins.copy()
    view["تشخیص"] = view["علت"].map(lambda c: CAUSES.get(c, ("?", ""))[0])
    view["اقدام لازم"] = [r["اقدام"] or CAUSES.get(r["علت"], ("", ""))[1]
                          for _, r in joins.iterrows()]
    display_cols = ["سورس", "فریم", "کلید", "ردیف سورس", "کلید یکتا در سورس",
                    "اشتراک کلید", "Source Match (٪)", "Base Coverage (٪)",
                    "Semantic", "Cardinality", "Cardinality Health", "Scope Alignment",
                    "Temporal Alignment", "تشخیص"]
    _print(view[[c for c in display_cols if c in view.columns]],
           "۱) Relation Health Contract — سلامت رابطه، دامنه و semantics")

    informational = {"OK", "GRAIN_OK", "HEALTHY_LIMITED_SCOPE", "HEALTHY_WITH_GAPS", "KNOWN_INCOMPLETE_SOURCE"}
    broken = view[~view["علت"].isin(informational)]
    if not broken.empty:
        print("\n🔧 اقدامات لازم:")
        for _, r in broken.iterrows():
            print(f"   • [{r['سورس']}/{r['فریم']}] {r['تشخیص']}")
            print(f"     ← {r['اقدام لازم']}")
            if r["علت"] == "FILE_MISSING":
                print(f"     ← الگوی فعلی: {r['الگوی فایل']}")
                print(f"     ← پوشه: {r['پوشه']}")

    samples = pd.DataFrame(d.samples)
    _print(samples, "۲) نمونه کلیدهایی که جور نشدند (شکل دو طرف را مقایسه کنید)")

    unmatched_details = pd.DataFrame(d.unmatched_details)
    _print(unmatched_details, "۲.۱) کالبدشکافی Orderهای جورنشده — بدون auto-match")

    cols = d.critical_columns()
    _print(cols[["ستون", "سورس", "نرخ پر بودن (٪)", "نرخ غیرصفر (٪)",
                 "وضعیت", "کاربرد"]],
           "۳) پر بودن ستون‌های حیاتی — علت صفر شدن KPIها")

    if "--headers" in sys.argv:
        _print(d.raw_headers(), "۴) ستون‌های واقعی هر سورس")

    if "--excel" in sys.argv:
        os.makedirs(SETTINGS.OUTPUT_DIR, exist_ok=True)
        path = os.path.join(SETTINGS.OUTPUT_DIR, "GSI_Join_Diagnostics.xlsx")
        with pd.ExcelWriter(path) as w:
            view.to_excel(w, sheet_name="وضعیت رابطه‌ها", index=False)
            samples.to_excel(w, sheet_name="کلیدهای جورنشده", index=False)
            unmatched_details.to_excel(w, sheet_name="تحلیل unmatched سفارش", index=False)
            cols.to_excel(w, sheet_name="ستون‌های حیاتی", index=False)
            d.raw_headers().to_excel(w, sheet_name="هدرهای واقعی", index=False)
        print(f"\n📄 گزارش تشخیصی: {path}")

    informational = {"OK", "GRAIN_OK", "HEALTHY_LIMITED_SCOPE", "HEALTHY_WITH_GAPS", "KNOWN_INCOMPLETE_SOURCE"}
    n_review = int((~view["علت"].isin(informational)).sum())
    n_error = int(view["شدت"].isin(["ERROR", "BLOCKER", "FATAL"]).sum()) if "شدت" in view.columns else n_review
    n_warn = int(view["شدت"].eq("WARNING").sum()) if "شدت" in view.columns else 0
    n_known = int(view["علت"].eq("KNOWN_INCOMPLETE_SOURCE").sum())
    n_limited = int(view["علت"].eq("HEALTHY_LIMITED_SCOPE").sum())
    print("\n" + "═" * 78)
    print(f"نتیجه: {len(view) - n_review - n_known} رابطه سالم/اطلاعاتی | {n_warn} هشدار | {n_error} خطای اثبات‌شده | {n_known} سورس ناقصِ شناخته‌شده")
    if n_limited:
        print(f"       {n_limited} رابطه Join سالم با دامنه محدود (Base Coverage پایین، بدون خطای کلید)")
    print("═" * 78)
    # هشدارهای scope/unmatched برای تشخیص هستند و به‌تنهایی command را fail نمی‌کنند.
    # فقط ERROR/BLOCKER/FATAL کد خروج 1 می‌دهد.
    return 1 if n_error else 0


if __name__ == "__main__":
    sys.exit(main())
