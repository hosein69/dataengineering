# -*- coding: utf-8 -*-
"""تابلوی متریال‌ها و بارنامه‌های بحرانی — منطق خالص + قالب HTML مستقل.

این ماژول هیچ محاسبه‌ی بحرانی بودن تازه‌ای نمی‌سازد؛ طبقه بحرانی (s40)،
روزهای رسوب (s60/s70)، مهلت و مانده تعهد (s50/s56) و پیوند مبلغی بارنامه با
ثبت سفارش (s59) را در یک نما کنار هم می‌گذارد تا مدیر در یک صفحه ببیند:

    کدام متریال خط را متوقف می‌کند یا می‌کند، روی کدام بارنامه است،
    آن بارنامه کجاست، چند روز رسوب دارد، به کدام ثبت سفارش با چه ارزشی
    وصل است و تعهد ارزی‌اش چند روز مهلت دارد.

قواعد:
  * دانه‌ها جدا می‌مانند: جدول متریال یک ردیف برای هر متریال، جدول بارنامه یک
    ردیف برای هر بارنامه؛ مبلغ‌ها هرگز روی ردیف‌های متریال جمع زده نمی‌شوند.
  * نامعلوم «—» نمایش داده می‌شود، نه صفر.
  * رنگ هر سطح از ``gsi.design.tokens.STATUS_SCALE`` می‌آید و همیشه با برچسب.
"""
from __future__ import annotations

import html
import math
import zlib
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from ..design import icons as I
from ..design import tokens as T
from ..i18n import columns as C

#: سطوح بحرانی به ترتیب شدت → کلید وضعیت در سیستم طراحی
LEVELS: Dict[str, tuple] = {
    "STOCKOUT": ("stockout", "توقف خط", 0),
    "CRITICAL": ("critical", "بحرانی", 1),
    "BECOMING_CRITICAL": ("serious", "در حال بحرانی شدن", 2),
    "WATCH": ("warning", "تحت نظر", 3),
    "SAFE": ("good", "ایمن", 4),
    "NO_CONSUMPTION": ("neutral", "بدون مصرف", 5),
    "UNKNOWN": ("unknown", "نامشخص", 6),
}
#: سطوحی که به‌طور پیش‌فرض «بحرانی» شمرده می‌شوند
DEFAULT_LEVELS = ("STOCKOUT", "CRITICAL", "BECOMING_CRITICAL")


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    t = str(v).strip()
    return "" if t.lower() in ("nan", "none", "nat", "<na>") else t


def _n(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _col(df: pd.DataFrame, *names: str) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def _first(values: Iterable[Any]) -> str:
    return next((_s(v) for v in values if _s(v)), "")


def _pair(df: pd.DataFrame, value_col: str, ccy_cols: Sequence[str]) -> Tuple[Optional[float], str]:
    """مبلغ و ارز از **یک** ردیف: اولین ردیفی که مبلغ دارد، با ارز همان ردیف.

    تا دور ۷ مبلغ از اولین ردیفِ دارای مبلغ و ارز از اولین ردیفِ دارای ارز برداشته می‌شد؛
    مبلغی که ارزش نامعلوم بود برچسب ارز ردیف دیگری می‌گرفت."""
    if value_col not in df.columns:
        return None, ""
    ccy_col = next((c for c in ccy_cols if c in df.columns), None)
    ccys = df[ccy_col] if ccy_col else pd.Series([""] * len(df), index=df.index, dtype=object)
    for v, c in zip(df[value_col], ccys):
        x = _n(v)
        if x is not None:
            return x, _s(c)
    return None, ""


#: R8: عنوان صادق ستون بارنامه در جدول متریال (رابطه بارنامه↔متریال در منبع نیست)
BL_OF_ORDERS = "بارنامه‌های سفارش این متریال"
#: R8: عنوان صادق متریال و مقاومت در جدول بارنامه (از سفارش‌های روی بارنامه)
MATS_OF_BL_ORDERS = "متریال بحرانی سفارش‌های این بارنامه"
MIN_RES_OF_BL_ORDERS = "کمترین مقاومت متریال سفارش‌ها (روز)"

#: R8: ترجمه عنوان‌های تازه تا واژه‌نامه (gsi/i18n/glossary_fa_en.py) آن‌ها را بگیرد؛
#: setdefault است، پس ورودی واژه‌نامه اگر اضافه شود مقدم است.
R8_GLOSSARY = {
    "بارنامه‌های سفارش": "Order B/Ls",
    BL_OF_ORDERS: "B/Ls of this material's orders",
    "متریال‌های سفارش": "Order materials",
    MATS_OF_BL_ORDERS: "Critical materials of this B/L's orders",
    MIN_RES_OF_BL_ORDERS: "Min resistance of order materials (days)",
    "بارنامه دارای سفارش بحرانی": "B/L with a critical order",
    "علت بحرانی بودن سفارش‌های این بارنامه": "Why this B/L's orders are critical",
    "بدترین سطح بحرانی سفارش‌های بارنامه": "Worst criticality of the B/L's orders",
    # R10: متریال با وضعیت نامشخص و تحویل SAP GR
    "متریال‌های با وضعیت نامشخص (ممکن است بحرانی)": "Materials with unknown status (may be critical)",
    "متریال با وضعیت نامشخص (ممکن است بحرانی)": "Materials with unknown status (may be critical)",
    "نقص داده (کدام فایل)": "Data gap (which file)",
    "تحویل‌شده به انبار (GR)": "Delivered to warehouse (GR)",
    "در انبار بلوکه/QC (GR)": "In blocked/QC stock (GR)",
    "وضعیت تحویل SAP GR": "SAP GR delivery status",
    "آخرین تاریخ GR": "Last GR date",
    "هشدار وضعیت بحرانی": "Criticality warning",
    "PO/قلم (SAP)": "PO/item (SAP)",
    "قلم PO مشترک با سفارش": "PO item shared with order",
    "تحویل در GR ثبت شده": "Delivery recorded in GR",
    "PO هست؛ هنوز GR ندارد": "PO exists; no GR yet",
    "PR این ردیف در شیت po نیست": "This row's PR is not in the po sheet",
    "PR در فایل کارشناسان خالی است": "PR is blank in the experts' file",
    "فایل SAP یا شیت GR بارگذاری نشد": "SAP file or GR sheet not loaded",
    "نامشخص؛ ممکن است بحرانی باشد": "Unknown; may be critical",
    "متریال نیست (موجودی ایران‌خودرو/ساپکو و نیاز روزانه نامعلوم)":
        "material not present (IKCO/SAPCO stock and daily need unknown)",
    "نیاز روزانه خالی است": "daily need is blank",
    "موجودی ایران‌خودرو و ساپکو خالی است": "IKCO and SAPCO stock are blank",
    "شیت GR بارگذاری نشد (تحویل نامعلوم)": "GR sheet not loaded (delivery unknown)",
    "PR خالی است (اتصال به SAP ممکن نیست)": "PR is blank (cannot link to SAP)",
    "PR این ردیف در شیت po نیست (تحویل نامعلوم)": "this row's PR is not in the po sheet (delivery unknown)",
    "نامشخص؛ ممکن است بحرانی باشد (نقص داده)": "Unknown; may be critical (data gap)",
    ("این متریال‌ها در فایل کارشناسان هستند ولی داده لازم برای سنجش بحرانی بودن (موجودی یا نیاز روزانه "
     "Oracle) ندارند؛ ممکن است بحرانی باشند. ستون «نقص داده» می‌گوید کدام داده در کدام فایل نیست."):
        ("These materials are in the experts' file but lack the data needed to judge criticality (Oracle stock or "
         "daily need); they may be critical. The data gap column names which data is missing from which file."),
}
for _fa, _en in R8_GLOSSARY.items():
    C._GLOSS.setdefault(C._norm(_fa), _en)
    C._GLOSS_REV.setdefault(_en.lower(), _fa)

#: پیام پیوند بارنامه‌ای که چند ثبت سفارش دارد (همان متن مرحله پیوند بارنامه ↔ ثبت سفارش)
_MULTI_REG = "بارنامه به {0} ثبت سفارش وصل است؛ سهم هر یک در منبع نیست"


def _min_num(values: Iterable[Any]) -> Optional[float]:
    xs = [x for x in (_n(v) for v in values) if x is not None]
    return min(xs) if xs else None


def _max_num(values: Iterable[Any]) -> Optional[float]:
    xs = [x for x in (_n(v) for v in values) if x is not None]
    return max(xs) if xs else None


def _join(values: Iterable[Any], sep: str = "، ", limit: int = 8) -> str:
    seen: List[str] = []
    for v in values:
        t = _s(v)
        if t and t not in seen:
            seen.append(t)
    more = len(seen) - limit
    return sep.join(seen[:limit]) + (f" و {more} مورد دیگر" if more > 0 else "")


def _order_key(df: pd.DataFrame) -> Optional[pd.Series]:
    """R8: کلید سفارش هر ردیف (CANONICAL_ORDER، سپس KEY_ORDER)؛ بدون ستون سفارش None."""
    if "CANONICAL_ORDER" not in df.columns and "KEY_ORDER" not in df.columns:
        return None
    a = _col(df, "CANONICAL_ORDER").map(_s)
    return a.where(a.ne(""), _col(df, "KEY_ORDER").map(_s))


def _order_bls(df: pd.DataFrame, okey: pd.Series) -> Dict[str, List[str]]:
    """R8: {سفارش: بارنامه‌هایش} — شاهد رابطه بارنامه↔سفارش است، نه بارنامه↔متریال."""
    bl = _col(df, "CANONICAL_BL", "KEY_BL").map(_s)
    out: Dict[str, List[str]] = {}
    for o, b in zip(okey, bl):
        if o and b and b not in out.setdefault(o, []):
            out[o].append(b)
    return out


def level_rank(code: str) -> int:
    return LEVELS.get(code, LEVELS["UNKNOWN"])[2]


def level_label(code: str) -> str:
    return LEVELS.get(code, LEVELS["UNKNOWN"])[1]


# ═══════════════════════════════ جدول متریال ═══════════════════════════════
def critical_materials(df: pd.DataFrame, levels: Sequence[str] = DEFAULT_LEVELS) -> pd.DataFrame:
    """یک ردیف برای هر متریال بحرانی، با بارنامه‌های سفارش‌هایش و ثبت سفارش‌ها.

    R8: هیچ منبعی نمی‌گوید کدام بارنامه کدام متریال را حمل می‌کند؛ پس ستون
    بارنامه «بارنامه‌های سفارش این متریال» است (از همه ردیف‌های همان سفارش‌ها)."""
    cols = ["متریال", "شرح", "سطح", "کد سطح", "مقاومت (روز)", "موجودی ایران‌خودرو", "موجودی ساپکو",
            "نیاز روزانه", "در راه", "در گمرک", BL_OF_ORDERS, "ثبت سفارش‌ها", "کجاست",
            "مالک قطعه", "اقدام پیشنهادی"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    mat = _col(df, "KEY_MATERIAL", "CANONICAL_PART_NO").map(_s)
    code = _col(df, "کد طبقه بحرانی").map(_s)
    okey = _order_key(df)
    order_bls = _order_bls(df, okey) if okey is not None else {}
    work = df.assign(_M=mat, _C=code, _O=okey if okey is not None else "")
    work = work[(work["_M"] != "") & work["_C"].isin(levels)]
    rows = []
    for m, g in work.groupby("_M"):
        # R8: بارنامه‌های سفارش‌های این متریال؛ بی‌ستون سفارش فقط بارنامه روی خود ردیف
        if okey is not None:
            bls_of = [b for o in dict.fromkeys(g["_O"]) if o for b in order_bls.get(o, [])]
        else:
            bls_of = list(_col(g, "CANONICAL_BL", "KEY_BL"))
        c = min(g["_C"], key=level_rank)
        rows.append({
            "متریال": m,
            "شرح": _first(_col(g, "MATERIAL_DESC", "CANONICAL_GOODS_DESC")),
            "سطح": level_label(c), "کد سطح": c,
            "مقاومت (روز)": _min_num(_col(g, "مقاومت (روز)")),
            "موجودی ایران‌خودرو": _max_num(_col(g, "موجودی ایران خودرو", "STOCK_IKCO")),
            "موجودی ساپکو": _max_num(_col(g, "موجودی ساپکو", "STOCK_SAPCO")),
            "نیاز روزانه": _max_num(_col(g, "نیاز روزانه", "DAILY_NEED")),
            "در راه": _max_num(_col(g, "موجودی در راه", "IN_TRANSIT_QTY")),
            "در گمرک": _max_num(_col(g, "موجودی در گمرک", "IN_CUSTOMS_QTY")),
            "بارنامه‌های سفارش این متریال": _join(bls_of),
            "ثبت سفارش‌ها": _join(_col(g, "KEY_REG")),
            "کجاست": _join(_col(g, "STATUS_WHERE")),
            "مالک قطعه": _join(_col(g, "PART_OWNER")),
            "اقدام پیشنهادی": _first(_col(g, "اقدام پیشنهادی مقاومت")),
        })
    out = pd.DataFrame(rows, columns=cols)
    if not out.empty:
        out["_r"] = out["کد سطح"].map(level_rank)
        out = out.sort_values(["_r", "مقاومت (روز)"], na_position="last").drop(columns="_r")
    return out.reset_index(drop=True)


# ═════════════════════ R10: متریال با وضعیت نامشخص (ممکن است بحرانی) ═════════════════════
WATCH_TITLE = "متریال‌های با وضعیت نامشخص (ممکن است بحرانی)"
WATCH_NOTE = ("این متریال‌ها در فایل کارشناسان هستند ولی داده لازم برای سنجش بحرانی بودن (موجودی یا نیاز روزانه "
              "Oracle) ندارند؛ ممکن است بحرانی باشند. ستون «نقص داده» می‌گوید کدام داده در کدام فایل نیست.")
WATCH_COLS = ["متریال", "شرح", "سفارش‌ها", "نقص داده (کدام فایل)", "تحویل‌شده به انبار (GR)", "در انبار بلوکه/QC (GR)",
              "وضعیت تحویل SAP GR", "کجاست", "کارشناس"]


def gap_text(text: Any, lang: str = "fa") -> str:
    """متن «نقص داده» («فایل: شرح | فایل: شرح») در زبان گزارش؛ نام فایل همان می‌ماند."""
    t = _s(text)
    if lang != C.EN or not t:
        return t
    parts = []
    for part in t.split(" | "):
        f, sep, what = part.partition(": ")
        parts.append(f"{f}: {C.phrase(what.strip(), lang)}" if sep else C.phrase(part, lang))
    return " | ".join(parts)


def watch_materials(df: pd.DataFrame) -> pd.DataFrame:
    """یک ردیف برای هر متریال با کد UNKNOWN؛ تحویل GR جمع قلم‌های PO یکتا (مرحله ۴۱)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=WATCH_COLS)
    mat = _col(df, "KEY_MATERIAL", "CANONICAL_PART_NO").map(_s)
    code = _col(df, "کد طبقه بحرانی").map(_s)
    code = code.where(code.isin(list(LEVELS)), "UNKNOWN")
    okey = _order_key(df)
    work = df.assign(_M=mat, _C=code, _O=okey if okey is not None else "")
    work = work[(work["_M"] != "") & work["_C"].eq("UNKNOWN")]
    rows = []
    for m, g in work.groupby("_M", sort=False):
        lines = g.drop_duplicates(subset=["_O"])
        if "GR_DLV_PO_LINES" in lines.columns:
            lines = lines[lines["GR_DLV_PO_LINES"].map(_s).ne("")].drop_duplicates(subset=["GR_DLV_PO_LINES"])
        else:
            lines = lines.iloc[0:0]
        dlv = [x for x in (_n(v) for v in _col(lines, "GR_DLV_DELIVERED_QTY")) if x is not None]
        blk = [x for x in (_n(v) for v in _col(lines, "GR_DLV_BLOCKED_QTY")) if x is not None]
        gaps = [p for p in dict.fromkeys(x.strip() for v in _col(g, "DATA_GAP_FILES") for x in _s(v).split(" | ")) if p]
        rows.append({
            "متریال": m, "شرح": _first(_col(g, "MATERIAL_DESC", "CANONICAL_GOODS_DESC")),
            "سفارش‌ها": _join(g["_O"]), "نقص داده (کدام فایل)": " | ".join(gaps),
            "تحویل‌شده به انبار (GR)": float(sum(dlv)) if dlv else None,
            "در انبار بلوکه/QC (GR)": float(sum(blk)) if blk else None,
            "وضعیت تحویل SAP GR": _join(_col(g, "GR_DLV_LINK_FA")),
            "کجاست": _join(_col(g, "STATUS_WHERE")), "کارشناس": _join(_col(g, "CANONICAL_EXPERT")),
        })
    return pd.DataFrame(rows, columns=WATCH_COLS)


# ═══════════════════════════════ جدول بارنامه ═══════════════════════════════
def critical_bls(df: pd.DataFrame, levels: Sequence[str] = DEFAULT_LEVELS) -> pd.DataFrame:
    """یک ردیف برای هر بارنامه بحرانی، با پیوند ثبت سفارش، مکان و تعهد ارزی."""
    cols = ["بارنامه", "سطح", "کد سطح", MATS_OF_BL_ORDERS, "علت", MIN_RES_OF_BL_ORDERS,
            "کجاست", "روزهای رسوب", "ترخیص", "ثبت سفارش", "ارزش فاکتور", "ارز فاکتور",
            "ارزش ثبت سفارش", "ارز ثبت سفارش", "حمل‌شده از ثبت سفارش (٪)", "وضعیت پیوند",
            "مانده تعهد", "ارز تعهد", "روز تا مهلت تعهد", "مرحله چرخه ارز", "کارشناس", "اقدام بعدی"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    bl = _col(df, "CANONICAL_BL", "KEY_BL").map(_s)
    code = _col(df, "BL_CRITICAL_LEVEL").map(_s)
    # R8: مقاومت از همه ردیف‌های سفارش‌های روی بارنامه (FIRST و ADDITIONAL)، نه فقط ردیف بارنامه
    okey = _order_key(df)
    res_by_order: Dict[str, Optional[float]] = {}
    if okey is not None:
        for o, x in zip(okey, _col(df, "مقاومت (روز)")):
            v = _n(x)
            if o and v is not None:
                res_by_order[o] = v if res_by_order.get(o) is None else min(res_by_order[o], v)
    work = df.assign(_B=bl, _C=code, _O=okey if okey is not None else "")
    work = work[(work["_B"] != "") & work["_C"].isin(levels)]
    rows = []
    for b, g in work.groupby("_B"):
        if okey is not None:
            min_res = _min_num([res_by_order.get(o) for o in dict.fromkeys(g["_O"]) if o]
                               + list(_col(g[g["_O"].eq("")], "مقاومت (روز)")))
        else:
            min_res = _min_num(_col(g, "مقاومت (روز)"))
        c = min(g["_C"], key=level_rank)
        full = any(v is True or _s(v).lower() in ("true", "1") for v in _col(g, "IS_FULL_CLEARED"))
        partial = any(v is True or _s(v).lower() in ("true", "1") for v in _col(g, "IS_PARTIAL_CLEARED"))
        # مبلغ فاکتور سطح بارنامه است؛ ارزش، حمل‌شده و مانده تعهد سطح ثبت سفارش‌اند و فقط وقتی
        # بارنامه یک ثبت سفارش دارد روی ردیفش می‌نشینند، هر مبلغ با ارز همان ردیف
        inv = ("BLREG_BL_INVOICE_VALUE", ("BLREG_BL_CURRENCY",)) if "BLREG_BL_INVOICE_VALUE" in g.columns \
            else ("INVOICE_VALUE", ("INVOICE_CURRENCY",))
        inv_value, inv_ccy = _pair(g, *inv)
        reg_keys = _col(g, "KEY_REG").map(_s)
        regs = [r for r in dict.fromkeys(reg_keys) if r]
        rg = g[reg_keys.eq(regs[0])] if len(regs) == 1 else g.iloc[0:0]
        reg_value, reg_ccy = _pair(rg, "BLREG_REG_VALUE", ("BLREG_REG_CURRENCY",))
        balance, balance_ccy = _pair(rg, "مانده تعهد", ("NTSW_CURRENCY", "FX_NTSW_CURRENCY"))
        link_status = (_MULTI_REG.format(len(regs)) if len(regs) > 1
                       else _first(_col(rg if regs else g, "BLREG_STATUS")))
        rows.append({
            "بارنامه": b, "سطح": level_label(c), "کد سطح": c,
            # R8: بدون جایگزین «متریال روی ردیف بارنامه» — آن رابطه شاهد ندارد
            "متریال بحرانی سفارش‌های این بارنامه": _first(_col(g, "BL_CRITICAL_MATERIALS")),
            "علت": _first(_col(g, "BL_CRITICAL_REASON")),
            "کمترین مقاومت متریال سفارش‌ها (روز)": min_res,
            "کجاست": _join(_col(g, "STATUS_WHERE")),
            "روزهای رسوب": _max_num(_col(g, "روزهای رسوب")),
            "ترخیص": "ترخیص کامل" if full else ("ترخیص جزئی" if partial else "ترخیص نشده"),
            "ثبت سفارش": _join(_col(g, "KEY_REG")),
            "ارزش فاکتور": inv_value,
            "ارز فاکتور": inv_ccy,
            "ارزش ثبت سفارش": reg_value,
            "ارز ثبت سفارش": reg_ccy,
            "حمل‌شده از ثبت سفارش (٪)": _n(_first(_col(rg, "BLREG_REG_SHIPPED_PCT"))),
            "وضعیت پیوند": link_status,
            "مانده تعهد": balance,
            "ارز تعهد": balance_ccy,
            "روز تا مهلت تعهد": _min_num(_col(g, "FX_DAYS_REMAINING")),
            "مرحله چرخه ارز": _first(_col(g, "LIFECYCLE_STAGE", "FX_CURRENT_STAGE")),
            "کارشناس": _first(_col(g, "CANONICAL_EXPERT")),
            "اقدام بعدی": _first(_col(g, "NEXT_ACTION_TITLE", "اقدام هشدار ترکیبی")),
        })
    out = pd.DataFrame(rows, columns=cols)
    if not out.empty:
        out["_r"] = out["کد سطح"].map(level_rank)
        out = out.sort_values(["_r", MIN_RES_OF_BL_ORDERS, "روزهای رسوب"],
                              ascending=[True, True, False], na_position="last").drop(columns="_r")
    return out.reset_index(drop=True)


def summary(materials: pd.DataFrame, bls: pd.DataFrame) -> Dict[str, int]:
    def count(frame: pd.DataFrame, code: str) -> int:
        return int(frame["کد سطح"].eq(code).sum()) if not frame.empty else 0
    return {
        "متریال توقف خط": count(materials, "STOCKOUT"),
        "متریال بحرانی": count(materials, "CRITICAL"),
        "متریال در حال بحرانی شدن": count(materials, "BECOMING_CRITICAL"),
        "بارنامه بحرانی": len(bls),
        "بارنامه ترخیص‌نشده": int(bls["ترخیص"].ne("ترخیص کامل").sum()) if not bls.empty else 0,
    }


# ═══════════════════════════════ قالب HTML ═══════════════════════════════
def _fmt(v: Any, nd: int = 0) -> str:
    x = _n(v)
    if x is None:
        t = _s(v)
        return html.escape(t) if t else "—"
    return f"{x:,.{nd}f}"


def _badge(code: str, lang: str = "fa") -> str:
    key, label, _ = LEVELS.get(code, LEVELS["UNKNOWN"])
    st = T.STATUS[key]
    return (f'<span class="cb-badge" style="color:{st.ink};background:{st.wash};border-color:{st.ink}">'
            f'{st.icon} {html.escape(C.phrase(label, lang))}</span>')


def _meter(pct: Optional[float], uid: str = "", lang: str = "fa") -> str:
    """گیج حلقه‌ای کوچک؛ نامعلوم «—» با حلقه خط‌چین، نه صفر."""
    tone = "critical" if pct is not None and pct > 100.5 else "brand"
    text = f"{pct:.0f}%" if lang == C.EN and pct is not None else ""
    return f'<div class="cb-ring">{I.ring(pct, 48, 5, tone=tone, uid=uid, text=text)}</div>'


LEVEL_ICON = {"STOCKOUT": "stop", "CRITICAL": "alert", "BECOMING_CRITICAL": "trend", "WATCH": "eye",
              "SAFE": "check", "NO_CONSUMPTION": "dot", "UNKNOWN": "dot"}
LEVEL_TONE = {"STOCKOUT": "danger", "CRITICAL": "critical", "BECOMING_CRITICAL": "serious", "SAFE": "good"}


def _board_parts(df: pd.DataFrame, levels: Sequence[str] = DEFAULT_LEVELS, lang: str = "fa") -> Dict[str, Any]:
    """اجزای تابلو (KPI، کارت متریال، جدول بارنامه) برای صفحه مستقل و تکه قابل جاسازی."""

    def L(t: str) -> str:
        if lang == C.EN:
            return f"<bdi>{html.escape(C.label(t, lang))}</bdi>"
        return html.escape(t)

    def V(t: Any) -> str:  # مقدار شمارشی (کجاست، ترخیص، مرحله) در زبان گزارش
        return html.escape(C.phrase(t, lang))

    mats = critical_materials(df, levels)
    bls = critical_bls(df, levels)
    kp = summary(mats, bls)
    watch = watch_materials(df) if "UNKNOWN" not in levels else pd.DataFrame(columns=WATCH_COLS)
    if not watch.empty:
        kp["متریال با وضعیت نامشخص (ممکن است بحرانی)"] = len(watch)
    kicons = ["stop", "alert", "trend", "ship", "box"]
    kpi_html = "".join(I.kpi_tile(kicons[i % len(kicons)], C.label(k, lang) if lang == C.EN else k, f"{v:,}",
                                  tone="critical" if v else "brand")
                       for i, (k, v) in enumerate(kp.items()))

    def mat_card(r: pd.Series) -> str:
        res = _n(r["مقاومت (روز)"])
        code = r["کد سطح"]
        gauge = I.ring(None if res is None else min(res, 20.0) / 20.0 * 100, 78, 7,
                       tone=LEVEL_TONE.get(code, "brand"), uid="m" + str(zlib.crc32(str(r["متریال"]).encode())),
                       text=("—" if res is None else f"{res:,.1f}"))
        return (f'<article class="cb-card" data-level="{code}">'
                f'<header>{I.icon_tile(LEVEL_ICON.get(code, "dot"), LEVEL_TONE.get(code, "brand"), 18)}'
                f'{_badge(code, lang)}<span class="cb-key">{html.escape(r["متریال"])}</span></header>'
                f'<h3>{html.escape(r["شرح"] or "—")}</h3>'
                f'<div class="cb-big">{gauge}<span>{L("مقاومت (روز)")}<br><small>{L("آستانه بحرانی")}: 20</small></span></div>'
                f'<dl><dt>{L("موجودی ایران خودرو")} / {L("موجودی ساپکو")}</dt><dd>{_fmt(r["موجودی ایران‌خودرو"])} / {_fmt(r["موجودی ساپکو"])}</dd>'
                f'<dt>{L("نیاز روزانه")}</dt><dd>{_fmt(r["نیاز روزانه"])}</dd>'
                f'<dt>{L("در راه")} / {L("در گمرک")}</dt><dd>{_fmt(r["در راه"])} / {_fmt(r["در گمرک"])}</dd>'
                f'<dt>{L(BL_OF_ORDERS)}</dt><dd class="ltr">{html.escape(r[BL_OF_ORDERS] or "—")}</dd>'
                f'<dt>{L("ثبت سفارش")}</dt><dd class="ltr">{html.escape(r["ثبت سفارش‌ها"] or "—")}</dd>'
                f'<dt>{L("کجاست")}</dt><dd>{V(r["کجاست"]) or "—"}</dd>'
                f'<dt>{L("مالک")}</dt><dd>{html.escape(r["مالک قطعه"] or "—")}</dd></dl>'
                + (f'<p class="cb-action">{V(r["اقدام پیشنهادی"])}</p>' if r["اقدام پیشنهادی"] else "")
                + '</article>')

    def bl_row(r: pd.Series) -> str:
        days = _n(r["روز تا مهلت تعهد"])
        bal = _n(r["مانده تعهد"])
        en = lang == C.EN
        if bal is not None and abs(bal) < 0.01:
            dl = "Settled" if en else "رفع تعهد شده"
        elif days is None:
            dl = "—"
        elif days < 0:
            dl = f'<b class="cb-over">{abs(days):,.0f} {"days overdue" if en else "روز گذشته"}</b>'
        else:
            dl = f'{days:,.0f} {"days" if en else "روز"}'
        return ("<tr>"
                f'<td>{_badge(r["کد سطح"], lang)}</td>'
                f'<td class="ltr"><b>{html.escape(r["بارنامه"])}</b></td>'
                f'<td>{html.escape(r[MATS_OF_BL_ORDERS] or "—")}</td>'
                f'<td>{_fmt(r[MIN_RES_OF_BL_ORDERS], 1)}</td>'
                f'<td>{V(r["کجاست"]) or "—"}<br><small>{V(r["ترخیص"])}</small></td>'
                f'<td>{_fmt(r["روزهای رسوب"])}</td>'
                f'<td class="ltr">{html.escape(r["ثبت سفارش"] or "—")}</td>'
                f'<td class="num">{_fmt(r["ارزش فاکتور"], 2)} <small>{html.escape(r["ارز فاکتور"])}</small></td>'
                f'<td class="num">{_fmt(r["ارزش ثبت سفارش"], 2)} <small>{html.escape(r["ارز ثبت سفارش"])}</small></td>'
                f'<td>{_meter(_n(r["حمل‌شده از ثبت سفارش (٪)"]), "b" + str(zlib.crc32(str(r["بارنامه"]).encode())), lang)}<small>{V(r["وضعیت پیوند"])}</small></td>'
                f'<td class="num">{_fmt(r["مانده تعهد"], 2)} <small>{html.escape(r["ارز تعهد"])}</small></td>'
                f"<td>{dl}</td>"
                f'<td>{V(r["مرحله چرخه ارز"]) or "—"}</td>'
                f'<td>{V(r["اقدام بعدی"]) or "—"}<br><small>{html.escape(r["کارشناس"] or "")}</small></td>'
                "</tr>")

    cards = "".join(mat_card(r) for _, r in mats.iterrows()) or f'<p class="cb-empty">{L("متریال بحرانی")}: 0</p>'
    rows = "".join(bl_row(r) for _, r in bls.iterrows())
    heads = ["سطح", "بارنامه", MATS_OF_BL_ORDERS, MIN_RES_OF_BL_ORDERS, "کجاست", "روزهای رسوب", "ثبت سفارش",
             "ارزش فاکتور", "ارزش ثبت سفارش", "حمل‌شده از ثبت سفارش (٪)", "مانده تعهد", "مهلت رفع تعهد",
             "مرحله چرخه ارز", "اقدام بعدی"]
    thead = "".join(f"<th>{L(h)}</th>" for h in heads)
    table = (f'<div class="cb-table"><table><thead><tr>{thead}</tr></thead><tbody>{rows}</tbody></table></div>'
             if rows else f'<p class="cb-empty">{L("بارنامه بحرانی")}: 0</p>')
    watch_html = ""
    if not watch.empty:
        wheads = "".join(f"<th>{L(h)}</th>" for h in WATCH_COLS)
        wrows = "".join(
            "<tr>" + "".join(
                f'<td class="{"ltr" if h == "متریال" else "num" if "(GR)" in h else ""}">'
                f'{_fmt(r[h]) if "(GR)" in h else (V(r[h]) if h in ("کجاست", "وضعیت تحویل SAP GR") else html.escape(gap_text(r[h], lang) if h == "نقص داده (کدام فایل)" else _s(r[h]))) or "—"}</td>'
                for h in WATCH_COLS) + "</tr>"
            for _, r in watch.iterrows())
        watch_html = (f'<section class="cb-section cb-watch"><h2>{I.icon_tile("search", "serious", 18)}{L(WATCH_TITLE)}</h2>'
                      f'<p class="cb-muted" style="font-size:12px;margin:-6px 0 10px">{L(WATCH_NOTE)}</p>'
                      f'<div class="cb-table"><table><thead><tr>{wheads}</tr></thead><tbody>{wrows}</tbody></table></div>'
                      '</section>')
    level_names = ("، " if lang != C.EN else ", ").join(
        C.label(level_label(c), lang) if lang == C.EN else level_label(c) for c in levels)
    return {"L": L, "kpis": kpi_html, "cards": cards, "table": table, "level_names": level_names, "watch": watch_html}


def critical_css() -> str:
    """شیوه‌نامه تابلو؛ متغیرهای رنگ از ``gsi.design.css.stylesheet`` یا ظرف ``.gx`` می‌آیند."""
    return f"""
.cb-wrap{{max-width:var(--container);margin:0 auto;padding:24px 16px 48px}}
.cb-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;
  background:var(--raised);border-radius:var(--r-xl);padding:20px 24px;box-shadow:var(--e-raised)}}
.cb-head .mi-tile{{width:54px;height:54px;border-radius:18px}} .cb-title{{display:flex;gap:14px;align-items:center}}
.cb-head h1{{font-size:22px;color:var(--text)}} .cb-head p{{color:var(--text-2);font-size:12px;margin-top:4px}}
.cb-kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}}
.cb-kpi{{background:var(--raised);border-radius:var(--r-lg);padding:14px 16px;box-shadow:var(--e-raised);display:grid;gap:2px}}
.cb-kpi span{{font-size:11.5px;color:var(--text-2)}} .cb-kpi b{{font-size:26px;color:var(--teal-ink)}}
.cb-section{{margin-top:26px}} .cb-section>h2{{font-size:17px;color:var(--text);margin-bottom:12px;display:flex;gap:10px;align-items:center}}
.cb-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}}
.cb-card{{background:var(--raised);border-radius:var(--r-xl);padding:16px;box-shadow:var(--e-raised);display:grid;gap:8px}}
.cb-card header{{display:flex;align-items:center;gap:10px}} .cb-card header .cb-key{{margin-inline-start:auto}}
.cb-card h3{{font-size:14px;color:var(--text)}} .cb-key{{direction:ltr;font-weight:800;color:var(--teal-ink);font-size:12px}}
.cb-big{{display:flex;align-items:center;gap:14px}} .cb-big .mi-ring{{margin:0}} .cb-big span{{font-size:12px;color:var(--text-2)}}
.cb-ring{{display:flex;justify-content:flex-start}} .cb-ring .mi-ring{{margin:0}}
.cb-card dl{{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:12px;margin:0}}
.cb-card dt{{color:var(--text-3)}} .cb-card dd{{margin:0;color:var(--text)}}
.cb-action{{font-size:12px;background:var(--teal-wash);color:var(--teal-ink);border-radius:var(--r-md);padding:8px 10px}}
.cb-badge{{display:inline-flex;align-items:center;gap:6px;border:1px solid;border-radius:var(--r-pill);
  padding:2px 10px;font-size:11.5px;font-weight:800;white-space:nowrap}}
.cb-badge i{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.cb-table{{overflow:auto;background:var(--raised);border-radius:var(--r-lg);box-shadow:var(--e-raised)}}
.cb-table table{{width:100%;border-collapse:collapse;font-size:12px;min-width:1280px}}
.cb-table th{{position:sticky;top:0;background:var(--sunken);color:var(--text-2);text-align:start;padding:10px;white-space:nowrap}}
.cb-table td{{padding:10px;border-top:1px solid var(--border);vertical-align:top;min-width:88px}}
.cb-table td:last-child{{min-width:240px}} .cb-table td:nth-child(5){{min-width:120px}} .cb-table td:nth-child(10){{min-width:150px}}
.cb-table small{{display:block;margin-top:4px}} .cb-pct{{font-weight:700;color:var(--text-2)}}
.cb-table tr:hover td{{background:var(--teal-wash)}}
.cb-meter{{display:block;height:8px;border-radius:var(--r-pill);background:var(--sunken);box-shadow:var(--e-inset);overflow:hidden;min-width:90px}}
.cb-meter i{{display:block;height:100%;border-radius:var(--r-pill)}}
.cb-over{{color:var(--st-critical-ink)}} .cb-muted,.cb-empty{{color:var(--text-3)}}
.ltr{{direction:ltr;text-align:right}} [dir="ltr"] .ltr{{text-align:left}} .num{{font-variant-numeric:tabular-nums;white-space:nowrap}}
small{{color:var(--text-3)}}
{I.minimal_css()}
@media print{{.cb-card,.cb-kpi,.cb-head,.cb-table{{box-shadow:none;border:1px solid var(--border)}}}}
"""


def critical_fragment(df: pd.DataFrame, levels: Sequence[str] = DEFAULT_LEVELS, lang: str = "fa") -> str:
    """تکه قابل جاسازی تابلو (بدون سربرگ صفحه) برای Studio و گزارش چرخه ارز."""
    p = _board_parts(df, levels, lang)
    L = p["L"]
    return (f'<style>{critical_css()}</style><div class="mi-kpis" style="margin-top:12px">{p["kpis"]}</div>'
            f'<section class="cb-section"><h2>{I.icon_tile("alert", "critical", 18)}{L("متریال‌های بحرانی")}</h2>'
            f'<div class="cb-grid">{p["cards"]}</div></section>'
            f'<section class="cb-section"><h2>{I.icon_tile("ship", size=18)}{L("بارنامه‌های بحرانی")}</h2>{p["table"]}</section>'
            f'{p["watch"]}')


def build_critical_html(df: pd.DataFrame, ref_date: str = "", title: str = "تابلوی متریال‌ها و بارنامه‌های بحرانی",
                        levels: Sequence[str] = DEFAULT_LEVELS, lang: str = "fa") -> str:
    """قالب HTML مستقل، راست‌چین و مینیمال — بدون هیچ فایل یا اسکریپت بیرونی.

    ``lang="en"`` عنوان ستون‌ها، برچسب‌ها و سرفصل‌ها را انگلیسی یک‌دست می‌کند
    (مقادیر سلول‌ها همان داده منبع می‌مانند). فونت ایران‌سنس سازمان، اگر پیدا
    شود، داخل فایل جاسازی می‌شود (``gsi.design.fonts``)."""
    from ..design.css import stylesheet
    from ..design.fonts import html_font_css

    if lang == C.EN and title == "تابلوی متریال‌ها و بارنامه‌های بحرانی":
        title = C.label(title, lang)
    p = _board_parts(df, levels, lang)
    L, kpi_html, cards, table, level_names = p["L"], p["kpis"], p["cards"], p["table"], p["level_names"]
    css = critical_css()
    page_dir = 'lang="en" dir="ltr"' if lang == C.EN else 'lang="fa" dir="rtl"'
    return (f'<!DOCTYPE html><html {page_dir}><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{html_font_css()}{stylesheet()}{css}</style></head><body>'
            f'<main class="cb-wrap"><section class="cb-head"><div class="cb-title">{I.icon_tile("alert", size=26, active=True)}'
            f'<div><h1>{html.escape(title)}</h1>'
            f'<p>{L("سطوح بحرانی")}: {html.escape(level_names)}'
            + (f" · {L('تاریخ مرجع')} {html.escape(ref_date)}" if ref_date else "")
            + '</p></div></div></section>'
            f'<div class="mi-kpis" style="margin-top:18px">{kpi_html}</div>'
            f'<section class="cb-section"><h2>{I.icon_tile("alert", "critical", 18)}{L("متریال‌های بحرانی")}</h2><div class="cb-grid">{cards}</div></section>'
            f'<section class="cb-section"><h2>{I.icon_tile("ship", size=18)}{L("بارنامه‌های بحرانی")}</h2>{table}</section>'
            f'{p["watch"]}</main></body></html>')
