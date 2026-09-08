# -*- coding: utf-8 -*-
"""دانه‌بندی (grain) ستون‌ها — تا جمع‌ها دوباره‌شماری نکنند.

## چرا این ماژول لازم است

جدول اصلی در دانه‌ی **بارنامه × متریال** است، ولی سورس‌ها روی شش دانه‌ی
مختلف می‌چسبند (`sources.yaml → join_on`):

    BL · ORDER · REG · MATERIAL · PR · EMP

وقتی یک ستون در دانه‌ی درشت‌تر (مثلاً «مانده تعهد» که در سطح **ثبت سفارش**
یکتاست) روی جدولی با دانه‌ی ریزتر join می‌شود، مقدارش در هر ردیف **تکرار**
می‌گردد. جمع ساده روی ردیف‌ها آن را چند برابر می‌کند:

    یک ثبت سفارش با ۳ بارنامه ⇒ جمع ساده = ۳ برابر مقدار واقعی

این خطا بی‌صدا است — عدد بزرگ‌تر می‌شود ولی هیچ استثنایی رخ نمی‌دهد. در
یک گزارش مدیریتی «جمع مانده تعهد»، یعنی گزارش غلط.

## قرارداد این ماژول

``safe_agg`` پیش از تجمیع، بر اساس **کلید دانه‌ی همان ستون** یکتاسازی
می‌کند. ``integrity_report`` تفاوت جمع ساده و جمع درست را صریح گزارش
می‌دهد، تا هیچ عددی بدون ردپا در گزارش ننشیند.
"""
from __future__ import annotations

__contract__ = 1

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

#: نام منطقی دانه → ستون کلید آن در جدول اصلی
GRAIN_KEYS: Dict[str, str] = {
    "BL": "KEY_BL",
    "ORDER": "KEY_ORDER",
    "REG": "KEY_REG",
    "MATERIAL": "KEY_MATERIAL",
    "PR": "KEY_PR",
    "EMP": "KEY_EMP",
}

GRAIN_FA: Dict[str, str] = {
    "BL": "بارنامه", "ORDER": "سفارش", "REG": "ثبت سفارش",
    "MATERIAL": "متریال", "PR": "درخواست خرید", "EMP": "پرسنلی",
    "ROW": "ردیف (دانه جدول)",
}

#: ستون‌های محاسباتی که در دانه‌ی خود ردیف‌اند (خروجی stageها)
ROW_GRAIN = "ROW"

#: ستون‌های محاسباتی فارسی که دانه‌شان از سورس مبدأ به ارث می‌رسد.
#: بدون این نگاشت، «مانده تعهد» دانه‌ی ردیف فرض می‌شد و در تولید — که یک
#: ثبت سفارش چند بارنامه دارد — جمعش چند برابر می‌شد.
DERIVED_GRAIN: Dict[str, str] = {
    "مانده تعهد": "REG",
    "جریمه برآوردی": "REG",
    "مهلت قانونی رفع تعهد": "REG",
    "روزهای تأخیر": "REG",
    "تعهد اولیه": "REG",
    "مقاومت (روز)": "MATERIAL",
    "مقاومت انبار (روز)": "MATERIAL",
    "نیاز روزانه": "MATERIAL",
    "موجودی کل قابل احتساب": "MATERIAL",
    "موجودی ایران خودرو": "MATERIAL",
    "موجودی ساپکو": "MATERIAL",
    "موجودی در راه": "MATERIAL",
    "موجودی در گمرک": "MATERIAL",
    "روزهای رسوب": "BL",
}

# ── تشخیص «سنجه» از «شناسه» و «نسبت» ──────────────────────────────────────
# جمع زدن شماره سفارش بی‌معناست، و جمع «مقاومت (روز)» هم بی‌معناست چون نرخ
# است نه مقدار انباشتنی. هر دو در نسخه اول همین ماژول به‌اشتباه جمع می‌شدند.
_IDENT_PAT = re.compile(
    r"^(KEY_|CANONICAL_)|(_NO|_CODE|_ID|_KEY)$|شماره|کد |^کد$|کلید|کوتاژ|تعرفه"
    r"|بارنامه|پرونده|رهگیری|No\.$|Number$", re.IGNORECASE)
_RATIO_PAT = re.compile(
    r"درصد|نرخ|٪|%|مقاومت|امتیاز|ratio|pct|rate|score|share|سهم|میانگین"
    r"|throughput|روز\)|days?$", re.IGNORECASE)

#: نوع سنجه → آیا جمع کردن معنا دارد
KIND_ADDITIVE = "additive"     # جمع معنا دارد (مبلغ، تعداد، وزن)
KIND_RATIO = "ratio"           # فقط میانگین/کمینه/بیشینه
KIND_IDENTIFIER = "identifier"  # هرگز تجمیع نشود
KIND_FA = {KIND_ADDITIVE: "انباشتنی", KIND_RATIO: "نسبتی",
           KIND_IDENTIFIER: "شناسه"}


def measure_kind(column: str, series: Optional["pd.Series"] = None) -> str:
    """نوع یک ستون عددی: انباشتنی / نسبتی / شناسه."""
    col = str(column)
    if _IDENT_PAT.search(col):
        return KIND_IDENTIFIER
    if _RATIO_PAT.search(col):
        return KIND_RATIO
    if series is not None:
        try:
            s = pd.to_numeric(series, errors="coerce").dropna()
            # اگر تقریباً همه مقادیر یکتا و صحیح‌اند، به شناسه شبیه‌تر است
            if len(s) >= 5 and s.nunique() / len(s) > 0.95 and (s % 1 == 0).all() \
                    and s.min() > 1000:
                return KIND_IDENTIFIER
        except Exception:
            pass
    return KIND_ADDITIVE


def summable(df: "pd.DataFrame", columns: List[str]) -> List[str]:
    """فقط ستون‌هایی که جمع زدنشان معنا دارد."""
    out = []
    for c in columns:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not s.notna().any():
            continue
        if measure_kind(c, df[c]) == KIND_ADDITIVE:
            out.append(c)
    return out


def preferred_agg(column: str, series: Optional["pd.Series"] = None) -> str:
    """تجمیع پیش‌فرضِ بامعنا برای یک ستون."""
    k = measure_kind(column, series)
    return {KIND_ADDITIVE: "sum", KIND_RATIO: "mean",
            KIND_IDENTIFIER: "nunique"}[k]


def prefix_grain_map() -> Dict[str, str]:
    """{پیشوند سورس: نام دانه} — از همان رجیستری‌ای که pipeline می‌خواند."""
    out: Dict[str, str] = {}
    try:
        from ..adapters import REGISTRY, discover
        discover()
    except Exception:
        return out
    for key, cls in REGISTRY.items():
        prefix = getattr(cls, "prefix", "") or ""
        if not prefix:
            continue
        try:
            join_on = getattr(cls().spec, "join_on", None)
        except Exception:
            join_on = None
        if join_on in GRAIN_KEYS:
            out[prefix] = join_on
    return out


def column_grain(column: str, prefix_map: Optional[Dict[str, str]] = None) -> str:
    """دانه‌ی یک ستون: نام دانه سورس، یا ``ROW`` برای ستون محاسباتی."""
    col = str(column)
    if col in DERIVED_GRAIN:
        return DERIVED_GRAIN[col]
    pm = prefix_map if prefix_map is not None else prefix_grain_map()
    pref = col.split("_", 1)[0]
    if pref in pm:
        return pm[pref]
    # کلیدهای کانونی خودشان معرف دانه‌اند
    for name, key in GRAIN_KEYS.items():
        if col == key:
            return name
    return ROW_GRAIN


def _dedup(df: pd.DataFrame, grain: str) -> pd.DataFrame:
    """یکتاسازی بر اساس کلید دانه.

    ردیف‌هایی که کلیدشان تهی است، موجودیت مستقل‌اند و **حذف نمی‌شوند** —
    وگرنه داده‌ی بدون کلید بی‌صدا از گزارش می‌افتاد.
    """
    key = GRAIN_KEYS.get(grain)
    if not key or key not in df.columns:
        return df
    k = df[key].astype(str).str.strip()
    keyed = df[k != ""]
    unkeyed = df[k == ""]
    return pd.concat([keyed.drop_duplicates(subset=[key]), unkeyed], axis=0)


def safe_agg(df: pd.DataFrame, column: str, how: str = "sum",
             prefix_map: Optional[Dict[str, str]] = None) -> float:
    """تجمیع بدون دوباره‌شماری — پیش از محاسبه بر دانه‌ی ستون یکتا می‌شود."""
    if column not in df.columns or df.empty:
        return 0.0
    grain = column_grain(column, prefix_map)
    base = df if grain == ROW_GRAIN else _dedup(df, grain)
    s = pd.to_numeric(base[column], errors="coerce")
    if how == "count":
        return float(s.notna().sum())
    if how == "nunique":
        return float(base[column].astype(str).replace("", pd.NA).nunique())
    val = getattr(s, how)()
    return float(val) if pd.notna(val) else 0.0


def naive_agg(df: pd.DataFrame, column: str, how: str = "sum") -> float:
    """همان تجمیع، ولی روی ردیف‌های خام — فقط برای مقایسه و گزارش صحت."""
    if column not in df.columns or df.empty:
        return 0.0
    s = pd.to_numeric(df[column], errors="coerce")
    if how == "count":
        return float(s.notna().sum())
    if how == "nunique":
        return float(df[column].astype(str).replace("", pd.NA).nunique())
    val = getattr(s, how)()
    return float(val) if pd.notna(val) else 0.0


def fanout(df: pd.DataFrame) -> pd.DataFrame:
    """ضریب تکرار هر دانه در جدول فعلی. ضریب > ۱ یعنی خطر دوباره‌شماری."""
    rows = []
    for name, key in GRAIN_KEYS.items():
        if key not in df.columns:
            continue
        k = df[key].astype(str).str.strip()
        nz = int((k != "").sum())
        uq = int(k[k != ""].nunique())
        rows.append({
            "دانه": GRAIN_FA.get(name, name), "کلید": key,
            "ردیف دارای کلید": nz, "مقدار یکتا": uq,
            "ضریب تکرار": round(nz / uq, 2) if uq else 0.0,
        })
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class IntegrityRow:
    column: str
    label: str
    grain: str
    rows: int
    unique_keys: int
    naive_sum: float
    safe_sum: float

    @property
    def overstated(self) -> float:
        return self.naive_sum - self.safe_sum

    @property
    def ok(self) -> bool:
        return abs(self.overstated) < 1e-6


def integrity_report(df: pd.DataFrame, columns: List[str],
                     labels: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """برای هر ستون عددی: جمع ساده در برابر جمع درست دانه‌ای.

    این جدول همراه گزارش می‌رود؛ هر عددی که در سند آمده اینجا ردپای
    محاسباتی‌اش هست.
    """
    pm = prefix_grain_map()
    labels = labels or {}
    out: List[dict] = []
    for c in columns:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not s.notna().any():
            continue
        kind = measure_kind(c, df[c])
        grain = column_grain(c, pm)
        key = GRAIN_KEYS.get(grain)
        uq = int(df[key].astype(str).str.strip().replace("", pd.NA).nunique()) \
            if key and key in df.columns else len(df)
        if kind == KIND_IDENTIFIER:
            # شناسه هرگز جمع نمی‌شود؛ فقط شمار یکتا معنا دارد.
            out.append({
                "فیلد": labels.get(c, c), "ستون": c, "نوع": KIND_FA[kind],
                "دانه": GRAIN_FA.get(grain, grain),
                "ردیف": len(df), "کلید یکتا": uq,
                "جمع ساده (ردیفی)": None, "جمع درست (دانه‌ای)": None,
                "اختلاف": None, "وضعیت": "— شناسه، جمع نمی‌شود",
            })
            continue
        how = "mean" if kind == KIND_RATIO else "sum"
        r = IntegrityRow(c, labels.get(c, c), grain, len(df), uq,
                         naive_agg(df, c, how), safe_agg(df, c, how, pm))
        out.append({
            "فیلد": r.label, "ستون": r.column, "نوع": KIND_FA[kind],
            "دانه": GRAIN_FA.get(r.grain, r.grain),
            "ردیف": r.rows, "کلید یکتا": r.unique_keys,
            ("جمع ساده (ردیفی)" if how == "sum" else "میانگین ساده"): round(r.naive_sum, 2),
            ("جمع درست (دانه‌ای)" if how == "sum" else "میانگین دانه‌ای"): round(r.safe_sum, 2),
            "اختلاف": round(r.overstated, 2),
            "وضعیت": "✔ یکسان" if r.ok else "⚠ دوباره‌شماری",
        })
    return pd.DataFrame(out)


def summarize(df: pd.DataFrame, columns: List[str],
              labels: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """خلاصه‌ی درست هر ستون عددی برای سربرگ گزارش (جمع/میانگین دانه‌ای)."""
    pm = prefix_grain_map()
    labels = labels or {}
    rows = []
    for c in columns:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        if not s.notna().any():
            continue
        kind = measure_kind(c, df[c])
        if kind == KIND_IDENTIFIER:
            continue
        grain = column_grain(c, pm)
        rows.append({
            "فیلد": labels.get(c, c),
            "نوع": KIND_FA[kind],
            "دانه": GRAIN_FA.get(grain, grain),
            # جمعِ ستون نسبتی بی‌معناست و عمداً خالی می‌ماند.
            "جمع": round(safe_agg(df, c, "sum", pm), 2) if kind == KIND_ADDITIVE else None,
            "میانگین": round(safe_agg(df, c, "mean", pm), 2),
            "کمینه": round(safe_agg(df, c, "min", pm), 2),
            "بیشینه": round(safe_agg(df, c, "max", pm), 2),
        })
    return pd.DataFrame(rows)
