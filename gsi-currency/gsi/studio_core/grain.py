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

__contract__ = 2   # case_rows — s50/s60/s85 و گزارش‌ها به آن تکیه دارند

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .semantic_metrics import currency_column, get_metric, infer_kind_from_name, registered_grain

#: نام منطقی دانه → ستون کلید آن در جدول اصلی
GRAIN_KEYS: Dict[str, str] = {
    "BL": "KEY_BL",
    "ORDER": "KEY_ORDER",
    "REG": "KEY_REG",
    "MATERIAL": "KEY_MATERIAL",
    "PR": "KEY_PR",
    "EMP": "KEY_EMP",
    # R8: دانه مرکب سفارش×متریال (ردیف فایل کارشناسان). ستون کلیدش مجازی است و
    # اگر در جدول نباشد از KEY_ORDER + KEY_MATERIAL ساخته می‌شود (grain_key_series).
    "ORDER_MATERIAL": "KEY_ORDER_MATERIAL",
}

#: R8: اجزای کلیدهای مرکب — کلید مجازی از همین ستون‌ها ساخته می‌شود.
COMPOSITE_GRAIN_PARTS: Dict[str, tuple] = {
    "ORDER_MATERIAL": ("KEY_ORDER", "KEY_MATERIAL"),
}

GRAIN_FA: Dict[str, str] = {
    "BL": "بارنامه", "ORDER": "سفارش", "REG": "ثبت سفارش",
    "MATERIAL": "متریال", "PR": "درخواست خرید", "EMP": "پرسنلی",
    "ORDER_MATERIAL": "سفارش × متریال",   # R8
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
    # V26.20 — ستون‌های فنی Supply Position. بدون این‌ها دانه‌شان ROW فرض
    # می‌شد و یک قطعه که روی سه بارنامه پخش است، «موجودی کل تأییدشده»‌اش
    # سه برابر جمع می‌خورد. دانه اعلام‌شده خود مرحله ۳۸: Order × Material.
    # R8: مقدار پارت‌های کارشناسی در دانه سفارش×متریال است، نه متریال: یکتاسازی
    # بر متریال، مقدار سفارش دوم همان متریال را حذف می‌کرد و بر سفارش (پیشوند
    # MOGH) متریال دوم همان سفارش را.
    "SUPPLIER_QTY": "ORDER_MATERIAL",
    "READY_QTY": "ORDER_MATERIAL",
    "IN_TRANSIT_QTY": "ORDER_MATERIAL",
    "IN_CUSTOMS_QTY": "ORDER_MATERIAL",
    "EXPERT_CLEARED_PART_QTY": "ORDER_MATERIAL",
    "EXPERT_INV_UNKNOWN_QTY": "ORDER_MATERIAL",
    "SUPPLY_EXPERT_STOCK": "ORDER_MATERIAL",
    "موجودی نزد سازنده": "ORDER_MATERIAL",
    "موجودی آماده حمل": "ORDER_MATERIAL",
    # موجودی Oracle در دانه متریال است.
    "STOCK_IKCO": "MATERIAL",
    "STOCK_SAPCO": "MATERIAL",
    "DAILY_NEED": "MATERIAL",
    "SUPPLY_ORACLE_STOCK": "MATERIAL",
    # R8: جمع کل = Oracle (متریال) + کارشناس (سفارش×متریال). جمع ردیفی‌اش در هیچ
    # دانه‌ای درست نیست (موجودی Oracle به ازای هر سفارش تکرار می‌شود)؛ در
    # semantic_metrics «نسبتی» (غیرقابل جمع) ثبت شده و فقط در دانه ردیف مرحله ۳۸
    # (سفارش×متریال) یکتا می‌شود.
    # R10: تحویل SAP GR در دانه سفارش × متریال (مرحله ۴۱)؛ قلم PO مشترک بین دو
    # سفارش روی هر دو می‌ماند، پس جمع ردیفی آن مجاز نیست.
    "GR_DLV_DELIVERED_QTY": "ORDER_MATERIAL",
    "GR_DLV_BLOCKED_QTY": "ORDER_MATERIAL",
    "GR_DLV_RETURNED_QTY": "ORDER_MATERIAL",
    "SUPPLY_TOTAL_CONFIRMED": "ORDER_MATERIAL",
    "SUPPLY_TOTAL_LOWER_BOUND": "ORDER_MATERIAL",
    "حداقل موجودی قابل اثبات": "ORDER_MATERIAL",
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
    """نوع ستون از رجیستری معنایی یا نام ستون؛ بدون heuristic توزیع عدد.

    ``series`` برای سازگاری API حفظ شده اما عمداً در تشخیص نوع استفاده نمی‌شود؛
    یکتا/صحیح/بزرگ بودن یک مبلغ دلیل شناسه بودن آن نیست.
    """
    spec = get_metric(str(column))
    if spec:
        return spec.kind
    return infer_kind_from_name(str(column))


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


#: R8: پیشوندهای ستونی که دانه‌شان با پیشوند سورس یکی نیست (به ترتیب، طولانی‌تر اول).
#: BLREG_BL_* روی جفت (بارنامه، ثبت سفارش) و BLREG_REG_* روی ثبت سفارش نوشته
#: می‌شوند (s59._write_columns)؛ MOGH_QTY_* مقدار پارت یک ردیف سفارش×متریال است.
#: BLREG_STATUS/BLREG_FLAGS متنی‌اند و دانه ردیف می‌مانند.
PREFIX_GRAIN_RULES = (
    ("BLREG_BL_", "BL"),
    ("BLREG_REG_", "REG"),
    ("MOGH_QTY_", "ORDER_MATERIAL"),
    ("MOGH_INVENTORY_", "ORDER_MATERIAL"),
)


_DERIVED_SOURCES: Optional[Dict[str, List[str]]] = None


def _derived_sources() -> Dict[str, List[str]]:
    """R8: {ستون دامنه‌ای s20: کاندیدهای سورس} — import تنبل تا چرخه import نسازد."""
    global _DERIVED_SOURCES
    if _DERIVED_SOURCES is None:
        try:
            from ..stages.s20_derive import DERIVED
            _DERIVED_SOURCES = {str(t): list(c) for t, (c, _d, _n) in DERIVED.items()}
        except Exception:
            return {}
    return _DERIVED_SOURCES


def column_grain(column: str, prefix_map: Optional[Dict[str, str]] = None,
                 _seen: Optional[set] = None) -> str:
    """دانه‌ی یک ستون: نام دانه سورس، یا ``ROW`` برای ستون محاسباتی."""
    col = str(column)
    explicit = registered_grain(col)
    if explicit:
        return explicit
    if col in DERIVED_GRAIN:
        return DERIVED_GRAIN[col]
    for pre, g in PREFIX_GRAIN_RULES:        # R8
        if col.startswith(pre):
            return g
    pm = prefix_map if prefix_map is not None else prefix_grain_map()
    # R8: ستون مشتق s20 (BALANCE، CB_VALUE، ALLOCATED_AMOUNT، ...) دانه سورس
    # مبدأش را به ارث می‌برد؛ وگرنه ROW فرض می‌شد و روی fan-out بارنامه چند برابر
    # جمع می‌خورد. کاندید اول (اولویت s20) که دانه معلوم دارد ملاک است.
    for name, key in GRAIN_KEYS.items():   # کلید کانونی (KEY_EMP هم در DERIVED است)
        if col == key:
            return name
    srcs = _derived_sources().get(col)
    if srcs:
        seen = set(_seen or ()) | {col}
        for src in srcs:
            if src in seen:
                continue
            g = column_grain(src, pm, seen)
            if g != ROW_GRAIN:
                return g
    pref = col.split("_", 1)[0]
    if pref in pm:
        return pm[pref]
    # کلیدهای کانونی خودشان معرف دانه‌اند
    for name, key in GRAIN_KEYS.items():
        if col == key:
            return name
    return ROW_GRAIN


#: 29.15.11 — هر Order×Material فایل کارشناسان ردیف خودش را دارد. متریال دوم به
#: بعد یک سفارش (``ADDITIONAL``) واقعیت‌های سطح سفارش را فقط **تکرار** می‌کند
#: (ثبت سفارش، تعهد، فرایند) و بارنامه‌اش عمداً خالی است (بارنامه فقط روی ردیف
#: اول سفارش می‌نشیند؛ معلوم نیست این متریال روی کدام بارنامه است).
ITEM_ROLE_COL = "MOGH_ITEM_ROLE"
MATERIAL_ONLY_ROLES = ("ADDITIONAL",)


def case_rows(df: pd.DataFrame) -> pd.DataFrame:
    """ردیف‌هایی که پرونده (سفارش / ثبت سفارش / بارنامه) را حمل می‌کنند.

    هر سنجه‌ای که واقعیت سطح پرونده را می‌شمارد — تعداد تعهد، میانگین روز
    رسوب، انطباق فرایند، تعداد بارنامه — روی همین ردیف‌ها حساب می‌شود؛ وگرنه
    سفارشی با سه متریال سه تعهد و سه پرونده فرایندی نشان می‌داد. سنجه‌های
    متریال‌محور (بحرانی، مقاومت، موجودی، ریسک ردیف) همه ردیف‌ها را می‌شمارند.
    ردیف بدون سفارش (``NO_ORDER``) پرونده مستقل است و می‌ماند.
    """
    if df is None or ITEM_ROLE_COL not in df.columns:
        return df
    return df[~df[ITEM_ROLE_COL].astype(str).isin(MATERIAL_ONLY_ROLES)]


def _dedup(df: pd.DataFrame, grain: str) -> pd.DataFrame:
    """یکتاسازی بر اساس کلید دانه.

    ردیف‌هایی که کلیدشان تهی است، موجودیت مستقل‌اند و **حذف نمی‌شوند** —
    وگرنه داده‌ی بدون کلید بی‌صدا از گزارش می‌افتاد. استثنا: ردیف متریال
    افزوده در دانه بارنامه، که بارنامه‌اش عمداً خالی است و بارنامه مستقلی نیست.
    """
    k = grain_key_series(df, grain)   # R8: کلید مرکب سفارش×متریال هم
    if k is None:
        return df
    if grain == "BL" and ITEM_ROLE_COL in df.columns:
        keep = (~df[ITEM_ROLE_COL].astype(str).isin(MATERIAL_ONLY_ROLES)).values
        df, k = df[keep], k[keep]
    has = (k != "").values
    keyed, kk = df[has], k[has]
    unkeyed = df[~has]
    return pd.concat([keyed[~kk.duplicated().values], unkeyed], axis=0)


def _key_text(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})


def grain_key_series(df: pd.DataFrame, grain: str) -> Optional[pd.Series]:
    """R8: کلید دانه هر ردیف به صورت رشته ('' = بی‌کلید)؛ ``None`` اگر ستونی نیست.

    برای دانه مرکب (ORDER_MATERIAL) اگر ستون مجازی در جدول نباشد از اجزایش
    ساخته می‌شود؛ اگر یکی از اجزا (مثلاً KEY_ORDER) اصلاً در جدول نباشد، با اجزای
    موجود یکتا می‌شود. ردیفی که یکی از اجزای موجودش خالی است بی‌کلید است و می‌ماند.
    """
    key = GRAIN_KEYS.get(grain)
    if not key:
        return None
    if key in df.columns:
        return _key_text(df[key])
    parts = [c for c in COMPOSITE_GRAIN_PARTS.get(grain, ()) if c in df.columns]
    if not parts:
        return None
    cols = [_key_text(df[c]) for c in parts]
    # R8: جزء خالی (مثلاً ردیف بی‌سفارش) یعنی موجودیت مستقل؛ یکتاسازی نمی‌شود.
    blank = pd.Series(False, index=df.index)
    for c in cols:
        blank |= c.eq("")
    out = cols[0]
    for c in cols[1:]:
        out = out + "\x1f" + c
    return out.where(~blank, "")


def unique_count(df: pd.DataFrame, keys, blank_counts: bool = True) -> int:
    """R8: شمار موجودیت یکتا بر ستون(های) کلید؛ ردیف بی‌کلید هر کدام یکی شمرده می‌شود.

    شمار «پرونده/تعهد/بارنامه» هرگز نباید شمار ردیف باشد، چون ردیف اول هر
    سفارش به ازای هر بارنامه تکرار می‌شود. ``blank_counts=False`` ردیف بی‌کلید را
    نمی‌شمارد (مثلاً «بارنامه» وقتی ردیف بارنامه ندارد).
    """
    if df is None or len(df) == 0:
        return 0
    keys = [keys] if isinstance(keys, str) else list(keys)
    keys = [c for c in keys if c in df.columns]
    if not keys:
        return int(len(df))
    k = entity_key(df, keys)
    blank = k.str.startswith("\x1e#")
    return int(k[~blank].nunique()) + (int(blank.sum()) if blank_counts else 0)


def entity_key(df: pd.DataFrame, keys) -> pd.Series:
    """R8: کلید موجودیت هر ردیف؛ ردیف بی‌کلید کلید یکتای خودش را می‌گیرد (مستقل شمرده می‌شود)."""
    keys = [keys] if isinstance(keys, str) else list(keys)
    keys = [c for c in keys if c in df.columns]
    rowid = pd.Series(["\x1e#%d" % i for i in range(len(df))], index=df.index)
    if not keys:
        return rowid
    cols = [_key_text(df[c]) for c in keys]
    blank = pd.Series(False, index=df.index)
    for c in cols:
        blank |= c.eq("")
    k = cols[0]
    for c in cols[1:]:
        k = k + "\x1f" + c
    return k.where(~blank, rowid)


def unique_counts_by(df: pd.DataFrame, by: str, keys) -> pd.Series:
    """R8: به ازای هر مقدار ``by``، شمار موجودیت یکتا (به‌جای ``value_counts`` ردیفی)."""
    if df is None or len(df) == 0 or by not in df.columns:
        return pd.Series(dtype="int64")
    k = entity_key(df, keys)
    return k.groupby(df[by]).nunique().sort_values(ascending=False).astype("int64")


def first_key(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """R8: نخستین ستون کلید موجود و دارای مقدار از میان کاندیدها."""
    for c in candidates:
        if c in df.columns and _key_text(df[c]).ne("").any():
            return c
    return None


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


def currency_breakdown(df: pd.DataFrame, column: str, how: str = "sum",
                       prefix_map: Optional[Dict[str, str]] = None,
                       dedupe: bool = True) -> Optional[dict]:
    """مبلغ پولی به تفکیک کد ارز، پس از یکتاسازی دانه (``dedupe=False``: روی ردیف‌های خام).

    ``None`` یعنی این ستون در این داده ستون ارز ندارد و رفتار قدیم (یک عدد) می‌ماند.
    ارزی که کد شناخته‌شده ندارد («نامشخص»، «حواله»، خالی) گروه نمی‌سازد و ردیفش فقط شمرده
    می‌شود تا بیرون ماندنش گفته شود.
    """
    ccy = currency_column(df.columns, column) if column in df.columns else None
    if ccy is None:
        return None
    grain = column_grain(column, prefix_map)
    base = df if (not dedupe or grain == ROW_GRAIN) else _dedup(df, grain)
    from ..finance.registration import currency_coder
    code_of = currency_coder()
    values = pd.to_numeric(base[column], errors="coerce")
    codes = base[ccy].map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else code_of(v))
    has = values.notna()
    known = has & codes.ne("")
    totals = {str(code): float(getattr(v, how)())
              for code, v in values[known].groupby(codes[known], sort=True)}
    return {"currency_column": ccy, "totals": totals, "unknown_rows": int((has & ~known).sum())}


def single_currency(b: Optional[dict]) -> Optional[str]:
    """کد تنها ارز وقتی همه مبلغ‌ها یک ارز معلوم دارند؛ وگرنه ``None``."""
    if not b or b["unknown_rows"] or len(b["totals"]) != 1:
        return None
    return next(iter(b["totals"]))


def currency_breakdown_text(b: dict) -> str:
    text = " | ".join(f"{v:,.2f} {c}" for c, v in sorted(b["totals"].items())) or "—"
    if b["unknown_rows"]:
        text += f" · {b['unknown_rows']:,} ردیف با ارز نامعلوم خارج از جمع"
    return text


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
        _ks = grain_key_series(df, grain)   # R8: کلید مرکب هم
        uq = int(_ks.replace("", pd.NA).nunique()) if _ks is not None else len(df)
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
        safe_b = currency_breakdown(df, c, how, pm) if kind == KIND_ADDITIVE else None
        if safe_b is not None and single_currency(safe_b) is None:
            # مبلغ چند ارز یا با ارز نامعلوم یک عدد نمی‌شود؛ جمع هر ارز جدا گزارش می‌شود
            naive_b = currency_breakdown(df, c, how, pm, dedupe=False)
            same = naive_b["totals"] == safe_b["totals"]
            out.append({
                "فیلد": labels.get(c, c), "ستون": c, "نوع": KIND_FA[kind],
                "دانه": GRAIN_FA.get(grain, grain), "ردیف": len(df), "کلید یکتا": uq,
                "جمع ساده (ردیفی)": None, "جمع درست (دانه‌ای)": None, "اختلاف": None,
                "وضعیت": ("✔ یکسان" if same else "⚠ دوباره‌شماری")
                         + "؛ چند ارز، جمع درست به تفکیک ارز: " + currency_breakdown_text(safe_b),
            })
            continue
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
        b = currency_breakdown(df, c, "sum", pm) if kind == KIND_ADDITIVE else None
        mixed = b is not None and single_currency(b) is None
        row = {
            "فیلد": labels.get(c, c),
            "نوع": KIND_FA[kind],
            "دانه": GRAIN_FA.get(grain, grain),
            # جمعِ ستون نسبتی بی‌معناست و عمداً خالی می‌ماند. مبلغ چند ارز یا با ارز نامعلوم
            # هم یک عدد ندارد: جمع، میانگین، کمینه و بیشینه‌اش خالی و جمع هر ارز جدا می‌آید.
            "جمع": round(safe_agg(df, c, "sum", pm), 2) if kind == KIND_ADDITIVE and not mixed else None,
            "میانگین": None if mixed else round(safe_agg(df, c, "mean", pm), 2),
            "کمینه": None if mixed else round(safe_agg(df, c, "min", pm), 2),
            "بیشینه": None if mixed else round(safe_agg(df, c, "max", pm), 2),
        }
        if b is not None:
            row["ارز"] = single_currency(b) or ""
            row["جمع به تفکیک ارز"] = currency_breakdown_text(b)
        rows.append(row)
    return pd.DataFrame(rows)
