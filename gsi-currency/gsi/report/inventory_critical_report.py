# -*- coding: utf-8 -*-
"""کنترل موجودی و اقلام بحرانی — خروجی مستقل برای رسیدگی به تفکیک متریال، سفارش و بارنامه.

این ماژول بحرانی بودن را دوباره حساب نمی‌کند. سطح هر ردیف همان «کد طبقه بحرانی»
موتور criticality است (با ترمیم دفاعی ``ensure_criticality_columns``)، جدول پایه
متریال از :func:`gsi.report.critical_board.critical_materials` و وضعیت ترخیص و رسوب
بارنامه از :func:`gsi.report.critical_board.critical_bls` می‌آید؛ مقدار پارت‌های
کارشناسی (نزد سازنده / آماده حمل / در راه / در گمرک) همان ستون‌های ``MOGH_QTY_*``
آداپتور کارشناسان است که در دانه **سفارش × متریال** یکتا و بعد به ازای متریال جمع
می‌شود (:func:`gsi.studio_core.grain.grain_key_series`).

قواعد:
  * هر نما یک ردیف برای هر کلید خودش دارد (متریال / سفارش / بارنامه)؛ کارت‌ها
    شمار یکتای همین نماها هستند، نه شمار ردیف جدول تخت.
  * نامعلوم «—» است، هرگز صفر. متریالی که هیچ داده موجودی ندارد «شکاف پوشش» است.
  * هیچ منبعی نمی‌گوید کدام بارنامه کدام متریال را آورده؛ بارنامه به سفارش وصل است.
    پس عنوان‌ها «متریال‌های سفارش‌های این بارنامه» و «بارنامه‌های سفارش‌های این متریال»اند.
  * مبلغی در این گزارش جمع زده نمی‌شود.
"""
from __future__ import annotations

import functools
import html
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from ..core.jalali import CalendarEngine
from ..design import icons as I
from ..design import brand as _BRAND
from ..i18n import columns as C
from ..studio_core.grain import grain_key_series
from . import critical_board as CB

# ═══════════════════════════════ عنوان‌ها ═══════════════════════════════
TITLE = "کنترل موجودی و اقلام بحرانی"
MAT_BLS = "بارنامه‌های سفارش‌های این متریال"
MAT_ORDERS = "سفارش‌های این متریال"
BL_ORDERS = "سفارش‌های این بارنامه"
BL_MATS = "متریال‌های سفارش‌های این بارنامه"
BL_CRIT_MATS = "متریال‌های بحرانی سفارش‌های این بارنامه"
BL_MIN_RES = "کمترین مقاومت متریال سفارش‌ها (روز)"
ORDER_BLS = "بارنامه‌های این سفارش"
NO_DATA = "داده‌ای برای این گزارش نیست"

#: وضعیت پارت‌های کارشناسی: (ستون فایل کارشناسان، جایگزین در مارت، عنوان)
QTY_STATES = (
    ("MOGH_QTY_AT_SUPPLIER", "SUPPLIER_QTY", "نزد سازنده"),
    ("MOGH_QTY_READY", "READY_QTY", "آماده حمل"),
    ("MOGH_QTY_IN_TRANSIT", "IN_TRANSIT_QTY", "در راه"),
    ("MOGH_QTY_IN_CUSTOMS", "IN_CUSTOMS_QTY", "در گمرک"),
    ("MOGH_QTY_STATE_UNKNOWN", "EXPERT_INV_UNKNOWN_QTY", "وضعیت نامشخص"),
)
QTY_LABELS = [q[2] for q in QTY_STATES]
CONFLICT_COLS = ("MOGH_INVENTORY_CONFLICT", "EXPERT_INV_CONFLICT")

#: وضعیت داده موجودی یک متریال
INV_FULL = "Oracle و کارشناس"
INV_ORACLE = "فقط Oracle"
INV_EXPERT = "فقط کارشناس"
INV_NONE = "بدون داده موجودی"

#: نوع بررسی‌های کنترل موجودی (به ترتیب اهمیت)
CHK_CONFLICT = "تعارض مقدار کارشناس"
CHK_NO_DATA = "متریال بدون داده موجودی"
CHK_NO_ORACLE = "بدون موجودی Oracle"
CHK_NO_NEED = "بدون نیاز روزانه (مقاومت نامعلوم)"
CHK_STOCK_CRIT = "موجودی دارد ولی بحرانی است"
CHK_UNKNOWN_STATE = "مقدار پارت با وضعیت نامشخص"
CHK_MAYBE_CRIT = "وضعیت بحرانی نامشخص (ممکن است بحرانی)"
CHECK_ORDER = (CHK_CONFLICT, CHK_NO_DATA, CHK_MAYBE_CRIT, CHK_STOCK_CRIT, CHK_NO_ORACLE, CHK_NO_NEED,
               CHK_UNKNOWN_STATE)

#: R10 — نقص داده و تحویل SAP GR (مرحله ۴۱، دانه سفارش × متریال)
GAP = "نقص داده (کدام فایل)"
GR_LINK = "وضعیت تحویل SAP GR"
GR_DLV = "تحویل‌شده به انبار (GR)"
GR_BLK = "در انبار بلوکه/QC (GR)"
GR_DATE = "آخرین تاریخ GR"
GR_LABELS = (GR_DLV, GR_BLK)
MAYBE_CRIT = "نامشخص؛ ممکن است بحرانی باشد"
KPI_MAYBE = "متریال با وضعیت نامشخص (ممکن است بحرانی)"

MAT_COLS = ["متریال", "شرح", "سطح", "کد سطح", "مقاومت (روز)", "موجودی ایران‌خودرو", "موجودی ساپکو",
            "نیاز روزانه", *QTY_LABELS, GR_DLV, GR_BLK, GR_DATE, "پوشش داده کارشناس", "وضعیت داده موجودی", GAP,
            "تعداد سفارش", MAT_ORDERS,
            MAT_BLS, "ثبت سفارش‌ها", "کجاست", "کارشناس", "مالک قطعه", "اقدام پیشنهادی"]
ORDER_COLS = ["سفارش", "سطح", "کد سطح", "تعداد متریال", "متریال‌ها", "متریال‌های بحرانی", "کمترین مقاومت (روز)",
              "ثبت سفارش‌ها", ORDER_BLS, "کارشناس", "اداره", "کجاست", "مرحله", "اقدام بعدی", "مسئول اقدام",
              "مهلت اقدام"]
BL_COLS = ["بارنامه", "سطح", "کد سطح", "بارنامه بحرانی", BL_ORDERS, BL_MATS, BL_CRIT_MATS, BL_MIN_RES,
           "کجاست", "ترخیص", "تاریخ تخلیه", "روز از تخلیه", "روزهای رسوب", "ثبت سفارش", "کارشناس", "اقدام بعدی"]
FOLLOW_COLS = ["اولویت", "سطح", "کد سطح", "متریال", "شرح", "مقاومت (روز)", "سفارش", ORDER_BLS, "در راه", "در گمرک",
               GR_DLV, GR_BLK, GR_DATE, GR_LINK, GAP, "کجاست", "مرحله", "کارشناس مسئول", "اداره", "اقدام بعدی", "مسئول اقدام", "مهلت اقدام",
               "اقدام پیشنهادی"]
CHECK_COLS = ["بررسی", "متریال", "سفارش", "سطح", "کد سطح", "جزئیات"]

NOTE_MAT = ("یک ردیف برای هر متریال. موجودی ایران‌خودرو/ساپکو و نیاز روزانه از Oracle (دانه متریال)؛ نزد سازنده، آماده حمل، در راه و در گمرک از فایل کارشناسان، یک بار برای هر سفارش × متریال و جمع روی سفارش‌های همان متریال. «پوشش داده کارشناس» = سفارش‌های دارای مقدار / همه سفارش‌های این متریال. نامعلوم «—» است، نه صفر. بارنامه‌ها به سفارش وصل‌اند؛ اینکه کدام بارنامه این متریال را آورده در منبع نیست.")
NOTE_ORD = ("یک ردیف برای هر سفارش: بدترین سطح بحرانی متریال‌هایش، کمترین مقاومت، ثبت سفارش‌ها، بارنامه‌ها، کارشناس و اداره، جای فعلی پرونده و اقدام بعدی.")
NOTE_BL = ("یک ردیف برای هر بارنامه. بارنامه بحرانی است اگر دست‌کم یکی از سفارش‌های رویش متریال بحرانی داشته باشد. متریال‌ها و مقاومت از همه ردیف‌های سفارش‌های این بارنامه می‌آیند، نه از خود بارنامه. «روز از تخلیه» = تاریخ مرجع − تاریخ تخلیه؛ بدون تاریخ تخلیه «—».")
NOTE_FU = ("هر متریال بحرانی در هر سفارش یک ردیف؛ کمترین مقاومت اول. کارشناس و اداره مسئول، جای فعلی پرونده، مقدار در راه و در گمرک همین سفارش × متریال و اقدام بعدی. بعد از آن‌ها ردیف‌هایی که وضعیت بحرانی‌شان نامشخص است (مثلاً متریال در Oracle نیست) با «ممکن است بحرانی» و نام فایلی که داده‌اش کم است. تحویل از شیت GR فایل SAP است: تحویل‌شده = 101−102+105−106−122+123، بلوکه/QC = 103−104−105+106.")
NOTE_CHK = ("تعارض مقدار کارشناس (یک پارت با دو وضعیت)، متریال بدون هیچ داده موجودی (شکاف پوشش، نه صفر)، متریال بحرانی که موجودی Oracle دارد، و متریال بدون موجودی Oracle یا نیاز روزانه.")
NOTE_LEGAL = ("قواعد: نامعلوم هرگز صفر نیست؛ شمارش‌ها یکتا بر متریال، سفارش و بارنامه‌اند؛ مقدار پارت‌ها یک بار برای هر سفارش × متریال شمرده می‌شود؛ بارنامه به سفارش وصل است و رابطه بارنامه با متریال در منبع نیست؛ مبلغی جمع زده نشده است.")
NOTE_UNIQUE = "شمارش یکتا بر متریال، سفارش و بارنامه؛ نه ردیف"

#: ترجمه عنوان‌های تازه برای حالت انگلیسی؛ ``setdefault`` است، پس ورودی واژه‌نامه اصلی مقدم است.
INV_GLOSSARY = {
    NOTE_MAT: ("One row per material. IKCO/SAPCO stock and daily need come from Oracle (material grain); at supplier, "
               "ready to ship, in transit and in customs come from the experts' file, counted once per order × material "
               "and summed over that material's orders. Expert data coverage = orders with a quantity / all orders of "
               "this material. Unknown is shown as —, never 0. B/Ls attach to orders; which B/L carried this material "
               "is not in the source."),
    NOTE_ORD: ("One row per order: worst criticality of its materials, minimum resistance, registrations, B/Ls, "
               "expert and department, where the case is now, and the next action."),
    NOTE_BL: ("One row per B/L. A B/L is critical when at least one order on it has a critical material. Materials "
              "and resistance come from all rows of the orders on this B/L, not from the B/L itself. Days since "
              "discharge = reference date − discharge date; without a discharge date it is —."),
    NOTE_FU: ("One row per critical material per order, lowest resistance first, with the responsible expert and "
              "department, where the case is, in-transit and in-customs quantity of this order × material, and the "
              "next action. Rows whose criticality is unknown (for example the material is not in Oracle) follow as "
              "'may be critical', naming the file that lacks the data. Delivery comes from the SAP GR sheet: "
              "delivered = 101−102+105−106−122+123, blocked/QC = 103−104−105+106."),
    GAP: "Data gap (which file)", GR_LINK: "SAP GR delivery status", GR_DLV: "Delivered to warehouse (GR)",
    GR_BLK: "In blocked/QC stock (GR)", GR_DATE: "Last GR date", MAYBE_CRIT: "Unknown; may be critical",
    KPI_MAYBE: "Materials with unknown status (may be critical)",
    CHK_MAYBE_CRIT: "Unknown criticality (may be critical)",
    NOTE_CHK: ("Expert quantity conflicts (one part in two states), materials with no inventory data at all (a "
               "coverage gap, not zero), critical materials that do have Oracle stock, and materials without Oracle "
               "stock or daily need."),
    NOTE_LEGAL: ("Rules: unknown is never zero; counts are unique by material, order and B/L; part quantities are "
                 "counted once per order × material; a B/L attaches to an order and the B/L-to-material relation is "
                 "not in the source; no amounts are summed."),
    NOTE_UNIQUE: "Unique counts by material, order and B/L, not rows",
    "سطوح بحرانی": "Critical levels",
    TITLE: "Inventory control and critical items",
    MAT_BLS: "B/Ls of this material's orders",
    MAT_ORDERS: "Orders of this material",
    BL_ORDERS: "Orders on this B/L",
    BL_MATS: "Materials of this B/L's orders",
    BL_CRIT_MATS: "Critical materials of this B/L's orders",
    ORDER_BLS: "B/Ls of this order",
    NO_DATA: "No data for this report",
    INV_FULL: "Oracle and expert", INV_ORACLE: "Oracle only", INV_EXPERT: "Expert only", INV_NONE: "No inventory data",
    CHK_CONFLICT: "Expert quantity conflict", CHK_NO_DATA: "Material with no inventory data",
    CHK_NO_ORACLE: "No Oracle stock", CHK_NO_NEED: "No daily need (resistance unknown)",
    CHK_STOCK_CRIT: "Has stock but critical", CHK_UNKNOWN_STATE: "Part quantity with unknown state",
    "وضعیت نامشخص": "Unknown state", "پوشش داده کارشناس": "Expert data coverage",
    "وضعیت داده موجودی": "Inventory data status", "تعداد سفارش": "Orders", "تعداد متریال": "Materials",
    "متریال‌ها": "Materials", "متریال‌های بحرانی": "Critical materials", "کمترین مقاومت (روز)": "Min resistance (days)",
    "ثبت سفارش‌ها": "Registrations", "مسئول اقدام": "Action owner", "مهلت اقدام": "Action due",
    "بارنامه بحرانی": "Critical B/L", "روز از تخلیه": "Days since discharge", "کارشناس مسئول": "Responsible expert",
    "اولویت": "Priority", "بررسی": "Check", "جزئیات": "Details", "رسیدگی": "Follow-up",
    "بررسی‌های موجودی": "Inventory checks", "متریال‌ها (کنترل موجودی)": "Materials (inventory)",
    "سفارش‌ها": "Orders", "بارنامه‌ها": "B/Ls", "خلاصه": "Summary",
    "سفارش با متریال بحرانی": "Orders with a critical material",
    "بارنامه با سفارش بحرانی": "B/Ls with a critical order",
    "بارنامه بحرانی ترخیص‌نشده": "Critical B/Ls not cleared",
    "متریال در گزارش": "Materials in report", "سفارش×متریال با تعارض": "Order×material conflicts",
    "فهرست رسیدگی (کمترین مقاومت اول)": "Follow-up list (lowest resistance first)",
    "کنترل موجودی": "Inventory control", "جستجو در این جدول": "Filter this table",
    "بله": "Yes", "خیر": "No", "کد سطح": "Level code",
    "متریال‌ها به تفکیک موجودی و بحرانی بودن": "Materials by inventory and criticality",
    "سفارش‌ها و بدترین سطح بحرانی متریال‌هایشان": "Orders and the worst criticality of their materials",
    "بارنامه‌ها و سفارش‌های رویشان": "B/Ls and the orders on them",
    "Excel کنترل موجودی و اقلام بحرانی": "Inventory control and critical items Excel",
}
for _fa, _en in INV_GLOSSARY.items():
    C._GLOSS.setdefault(C._norm(_fa), _en)
    C._GLOSS_REV.setdefault(_en.lower(), _fa)

_s, _n, _first = CB._s, CB._n, CB._first
#: فهرست‌ها در این گزارش برای رسیدگی کامل‌تر از تابلو می‌مانند (تا ۳۰ مورد در هر خانه)
_join = functools.partial(CB._join, limit=30)
_LEVEL_BY_LABEL = {v[1]: k for k, v in CB.LEVELS.items()}


# ═══════════════════════════════ مدل ═══════════════════════════════
@dataclass
class InventoryModel:
    ref_date: str = ""
    levels: tuple = CB.DEFAULT_LEVELS
    materials: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=MAT_COLS))
    orders: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ORDER_COLS))
    bls: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=BL_COLS))
    followup: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=FOLLOW_COLS))
    checks: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=CHECK_COLS))
    kpis: Dict[str, int] = field(default_factory=dict)
    source_rows: int = 0
    quantity_source: str = ""

    @property
    def empty(self) -> bool:
        return self.materials.empty and self.orders.empty and self.bls.empty


def _coalesce(df: pd.DataFrame, *names: str) -> pd.Series:
    """اولین مقدار غیرخالی هر ردیف از میان ستون‌های موجود (نه فقط اولین ستون موجود)."""
    out = pd.Series([""] * len(df), index=df.index, dtype=object)
    for n in names:
        if n in df.columns:
            v = df[n].map(_s)
            out = out.where(out.ne(""), v)
    return out


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    from ..studio_core.runtime_data import ensure_criticality_columns
    work = ensure_criticality_columns(df)
    code = work["کد طبقه بحرانی"].map(_s) if "کد طبقه بحرانی" in work else pd.Series("", index=work.index)
    work["کد طبقه بحرانی"] = code.where(code.isin(list(CB.LEVELS)), "UNKNOWN")
    ok = CB._order_key(work)
    work["_O"] = ok if ok is not None else ""
    work["_M"] = CB._col(work, "KEY_MATERIAL", "CANONICAL_PART_NO").map(_s)
    work["_B"] = _coalesce(work, "CANONICAL_BL", "KEY_BL")
    work["_C"] = work["کد طبقه بحرانی"]
    work["_R"] = pd.to_numeric(CB._col(work, "مقاومت (روز)"), errors="coerce")
    work["_GAP"] = CB._col(work, "DATA_GAP_FILES").map(_s)
    return work


def _gap_parts(values: Iterable[Any]) -> List[str]:
    """قطعه‌های یکتای «نقص داده» (هر ردیف چند قطعه با « | » دارد)."""
    return [p for p in dict.fromkeys(x.strip() for v in values for x in _s(v).split(" | ")) if p]


def _gr_row(r: Any) -> Dict[str, Any]:
    return {GR_DLV: _n(r.get("GR_DLV_DELIVERED_QTY")), GR_BLK: _n(r.get("GR_DLV_BLOCKED_QTY")),
            GR_DATE: _s(r.get("GR_DLV_LAST_DATE")), GR_LINK: _s(r.get("GR_DLV_LINK_FA"))}


def _gr_by_material(work: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """تحویل GR هر متریال: جمع روی قلم‌های PO یکتا (قلم مشترک دو سفارش یک بار)."""
    if "GR_DLV_PO_LINES" not in work.columns:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    w = work[work["_M"].ne("")].drop_duplicates(subset=["_M", "_O"])
    for m, g in w.groupby("_M", sort=False):
        g = g[g["GR_DLV_PO_LINES"].map(_s).ne("")].drop_duplicates(subset=["GR_DLV_PO_LINES"])
        dlv = [x for x in (_n(v) for v in CB._col(g, "GR_DLV_DELIVERED_QTY")) if x is not None]
        blk = [x for x in (_n(v) for v in CB._col(g, "GR_DLV_BLOCKED_QTY")) if x is not None]
        dates = sorted(d for d in CB._col(g, "GR_DLV_LAST_DATE").map(_s) if d)
        out[m] = {GR_DLV: float(sum(dlv)) if dlv else None, GR_BLK: float(sum(blk)) if blk else None,
                  GR_DATE: dates[-1] if dates else ""}
    return out


def _worst(codes: Iterable[str]) -> str:
    codes = [c for c in codes if c]
    return min(codes, key=CB.level_rank) if codes else "UNKNOWN"


def _txt_num(v: Any, nd: int = 0) -> str:
    x = _n(v)
    return "—" if x is None else f"{x:,.{nd}f}"


def _min_res(values: Iterable[Any]) -> Optional[float]:
    return CB._min_num(values)


# ─────────────── مقدار پارت‌ها در دانه سفارش × متریال ───────────────
def _positions(work: pd.DataFrame, extras: Any = None) -> tuple:
    """(جدول سفارش × متریال با پنج مقدار پارت و تعارض، منبع مقدار).

    ردیف تکراری همان سفارش × متریال (پخش شدن روی چند بارنامه) یک بار شمرده می‌شود.
    اگر مارت ستون مقدار ندارد، دفتر ``expert_material_positions`` (همان دانه) خوانده
    می‌شود و فقط جفت‌های حاضر در همین داده نگه داشته می‌شوند."""
    cols = {lab: next((c for c in (a, b) if c in work.columns), None) for a, b, lab in QTY_STATES}
    conflict = next((c for c in CONFLICT_COLS if c in work.columns), None)
    source = "flat"
    src = work
    if not any(cols.values()):
        pos = None
        try:
            pos = extras.get("expert_material_positions") if extras is not None else None
        except Exception:
            pos = None
        if not isinstance(pos, pd.DataFrame) or pos.empty or "KEY_MATERIAL" not in pos:
            return pd.DataFrame(columns=["_M", "_O", *QTY_LABELS, "تعارض", "_KNOWN"]), ""
        pos = pos.copy()
        pos["_M"] = pos["KEY_MATERIAL"].map(_s)
        pos["_O"] = CB._col(pos, "KEY_ORDER").map(_s)
        pairs = set(zip(work["_M"], work["_O"]))
        src = pos[[p in pairs for p in zip(pos["_M"], pos["_O"])]]
        cols = {lab: next((c for c in (a, b) if c in src.columns), None) for a, b, lab in QTY_STATES}
        conflict = next((c for c in CONFLICT_COLS if c in src.columns), None)
        source = "expert_material_positions"
    frame = pd.DataFrame({"_M": src["_M"].values, "_O": src["_O"].values}, index=src.index)
    for lab, c in cols.items():
        frame[lab] = pd.to_numeric(src[c], errors="coerce") if c else float("nan")
    frame["تعارض"] = src[conflict].map(_s) if conflict else ""
    frame = frame[frame["_M"].ne("")]
    if frame.empty:
        return pd.DataFrame(columns=["_M", "_O", *QTY_LABELS, "تعارض", "_KNOWN"]), source
    key_src = src.loc[frame.index].assign(KEY_ORDER=frame["_O"], KEY_MATERIAL=frame["_M"])
    key = grain_key_series(key_src[["KEY_ORDER", "KEY_MATERIAL"]], "ORDER_MATERIAL")
    keyed = frame[key.ne("")]
    # هر جفت سفارش × متریال یک بار؛ ``first`` اولین مقدار معلوم هر ستون را برمی‌دارد
    agg = {lab: "first" for lab in QTY_LABELS}
    agg.update({"تعارض": lambda s: _first(s)})
    grouped = keyed.groupby(["_M", "_O"], sort=False).agg(agg).reset_index() if not keyed.empty else keyed
    out = pd.concat([grouped, frame[key.eq("")]], ignore_index=True)
    out["_KNOWN"] = out[QTY_LABELS].notna().any(axis=1)
    return out.reset_index(drop=True), source


# ─────────────────────────── نمای متریال ───────────────────────────
def material_view(work: pd.DataFrame, pos: pd.DataFrame, levels: Sequence[str]) -> pd.DataFrame:
    base = CB.critical_materials(work, tuple(CB.LEVELS))
    if base.empty:
        return pd.DataFrame(columns=MAT_COLS)
    base = base.drop(columns=["در راه", "در گمرک"], errors="ignore").rename(columns={CB.BL_OF_ORDERS: MAT_BLS})
    # اگر مارت ستون موجودی Oracle ندارد، critical_materials «—» نشان می‌دهد؛ صفر نمی‌شود.
    sums = {}
    if not pos.empty:
        g = pos.groupby("_M", sort=False)
        sums = {lab: g[lab].sum(min_count=1) for lab in QTY_LABELS}
        known = g["_KNOWN"].sum()
        total = g.size()
    orders_by_mat = {m: [o for o in dict.fromkeys(g_["_O"]) if o] for m, g_ in work.groupby("_M") if m}
    experts = {m: _join(g_["CANONICAL_EXPERT"]) for m, g_ in work.groupby("_M")} \
        if "CANONICAL_EXPERT" in work else {}
    gr = _gr_by_material(work)
    gaps = {m: _join(_gap_parts(g_["_GAP"]), sep=" | ") for m, g_ in work.groupby("_M") if m}
    rows = []
    for _, r in base.iterrows():
        m = r["متریال"]
        rec = r.to_dict()
        for lab in QTY_LABELS:
            v = sums[lab].get(m) if sums else None
            rec[lab] = None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)
        if sums and m in total.index:
            rec["پوشش داده کارشناس"] = f"{int(known.get(m, 0))}/{int(total[m])}"
        else:
            rec["پوشش داده کارشناس"] = ""
        has_oracle = _n(r["موجودی ایران‌خودرو"]) is not None or _n(r["موجودی ساپکو"]) is not None
        has_expert = any(rec[lab] is not None for lab in QTY_LABELS)
        rec["وضعیت داده موجودی"] = (INV_FULL if has_oracle and has_expert else INV_ORACLE if has_oracle
                                   else INV_EXPERT if has_expert else INV_NONE)
        orders = orders_by_mat.get(m, [])
        rec["تعداد سفارش"] = len(orders)
        rec[MAT_ORDERS] = _join(orders)
        rec["کارشناس"] = experts.get(m, "")
        rec.update(gr.get(m, {GR_DLV: None, GR_BLK: None, GR_DATE: ""}))
        rec[GAP] = gaps.get(m, "")
        if rec.get("کد سطح") == "UNKNOWN" and not rec.get("اقدام پیشنهادی"):
            rec["اقدام پیشنهادی"] = MAYBE_CRIT
        rows.append(rec)
    return pd.DataFrame(rows, columns=MAT_COLS).reset_index(drop=True)


# ─────────────────────────── نمای سفارش ───────────────────────────
def order_view(work: pd.DataFrame, levels: Sequence[str]) -> pd.DataFrame:
    w = work[work["_O"].ne("")]
    if w.empty:
        return pd.DataFrame(columns=ORDER_COLS)
    w = w.assign(_DEPT=_coalesce(w, "ORG_DEPT", "CRD_DEPARTMENT"),
                 _STAGE=_coalesce(w, "ORDER_STAGE_FA", "MOGH_STAGE_FA", "STATUS_STAGE"),
                 _ACT=_coalesce(w, "NEXT_ACTION_TITLE", "اقدام هشدار ترکیبی"))
    rows = []
    for o, g in w.groupby("_O", sort=False):
        code = _worst(g["_C"])
        mats = [m for m in dict.fromkeys(g["_M"]) if m]
        crit = [m for m in dict.fromkeys(g.loc[g["_C"].isin(levels), "_M"]) if m]
        rows.append({
            "سفارش": o, "سطح": CB.level_label(code), "کد سطح": code,
            "تعداد متریال": len(mats), "متریال‌ها": _join(mats), "متریال‌های بحرانی": _join(crit),
            "کمترین مقاومت (روز)": _min_res(g["_R"]),
            "ثبت سفارش‌ها": _join(CB._col(g, "KEY_REG")), ORDER_BLS: _join(g["_B"]),
            "کارشناس": _join(CB._col(g, "CANONICAL_EXPERT")), "اداره": _join(g["_DEPT"]),
            "کجاست": _join(CB._col(g, "STATUS_WHERE")), "مرحله": _first(g["_STAGE"]),
            "اقدام بعدی": _first(g["_ACT"]), "مسئول اقدام": _first(CB._col(g, "NEXT_ACTION_OWNER")),
            "مهلت اقدام": _first(CB._col(g, "NEXT_ACTION_DUE_DATE")),
        })
    out = pd.DataFrame(rows, columns=ORDER_COLS)
    out["_r"] = out["کد سطح"].map(CB.level_rank)
    return out.sort_values(["_r", "کمترین مقاومت (روز)"], na_position="last").drop(columns="_r").reset_index(drop=True)


# ─────────────────────────── نمای بارنامه ───────────────────────────
def _days_since(date_text: str, ref_date: str) -> Optional[int]:
    if not date_text or not ref_date:
        return None
    return CalendarEngine.days_between(date_text, ref_date)


def bl_view(work: pd.DataFrame, levels: Sequence[str], ref_date: str = "") -> pd.DataFrame:
    w = work[work["_B"].ne("")]
    if w.empty:
        return pd.DataFrame(columns=BL_COLS)
    # ترخیص، کجاست و رسوب از تابلوی بحرانی (همه سطح‌ها، تا هر بارنامه یک ردیف داشته باشد)
    cbw = work.assign(BL_CRITICAL_LEVEL="UNKNOWN")
    cb = CB.critical_bls(cbw, ("UNKNOWN",)).set_index("بارنامه")
    by_order = {o: g for o, g in work[work["_O"].ne("")].groupby("_O", sort=False)}
    w = w.assign(_DIS=_coalesce(w, "DISCHARGE_DATE", "BL_DISCHARGE_DATE"),
                 _ACT=_coalesce(w, "NEXT_ACTION_TITLE", "اقدام هشدار ترکیبی"))
    rows = []
    for b, g in w.groupby("_B", sort=False):
        orders = [o for o in dict.fromkeys(g["_O"]) if o]
        # همه ردیف‌های سفارش‌های روی بارنامه (ردیف‌های افزوده بی‌بارنامه هم) + ردیف بی‌سفارش خود بارنامه
        parts = [by_order[o] for o in orders if o in by_order] + [g[g["_O"].eq("")]]
        ow = pd.concat(parts) if parts else g
        code = _worst(ow["_C"])
        mats = [m for m in dict.fromkeys(ow["_M"]) if m]
        crit = [m for m in dict.fromkeys(ow.loc[ow["_C"].isin(levels), "_M"]) if m]
        dis = _first(g["_DIS"])
        info = cb.loc[b] if b in cb.index else None
        if isinstance(info, pd.DataFrame):
            info = info.iloc[0]
        rasoob = _n(info["روزهای رسوب"]) if info is not None and dis else None
        rows.append({
            "بارنامه": b, "سطح": CB.level_label(code), "کد سطح": code,
            "بارنامه بحرانی": "بله" if code in levels else "خیر",
            BL_ORDERS: _join(orders), BL_MATS: _join(mats), BL_CRIT_MATS: _join(crit),
            BL_MIN_RES: _min_res(ow["_R"]),
            "کجاست": info["کجاست"] if info is not None else _join(CB._col(g, "STATUS_WHERE")),
            "ترخیص": info["ترخیص"] if info is not None else "",
            "تاریخ تخلیه": dis, "روز از تخلیه": _days_since(dis, ref_date), "روزهای رسوب": rasoob,
            "ثبت سفارش": _join(CB._col(g, "KEY_REG")), "کارشناس": _join(CB._col(g, "CANONICAL_EXPERT")),
            "اقدام بعدی": _first(g["_ACT"]),
        })
    out = pd.DataFrame(rows, columns=BL_COLS)
    out["_r"] = out["کد سطح"].map(CB.level_rank)
    out = out.sort_values(["_r", BL_MIN_RES, "روز از تخلیه"], ascending=[True, True, False], na_position="last")
    return out.drop(columns="_r").reset_index(drop=True)


# ─────────────────────────── فهرست رسیدگی ───────────────────────────
def followup_view(work: pd.DataFrame, pos: pd.DataFrame, levels: Sequence[str]) -> pd.DataFrame:
    """هر متریال بحرانی در هر سفارش یک ردیف، کمترین مقاومت اول، با مسئول و اقدام بعدی.

    R10: ردیف‌های با وضعیت بحرانی نامشخص (مثلاً متریال در Oracle نیست) هم می‌آیند، بعد از
    بحرانی‌ها، با «ممکن است بحرانی» و نقص داده‌شان؛ هیچ ردیف فایل کارشناسان پنهان نمی‌ماند."""
    watch = tuple(levels) + (() if "UNKNOWN" in levels else ("UNKNOWN",))
    w = work[work["_C"].isin(watch) & work["_M"].ne("")]
    if w.empty:
        return pd.DataFrame(columns=FOLLOW_COLS)
    w = w.assign(_DEPT=_coalesce(w, "ORG_DEPT", "CRD_DEPARTMENT"),
                 _STAGE=_coalesce(w, "ORDER_STAGE_FA", "MOGH_STAGE_FA", "STATUS_STAGE"),
                 _ACT=_coalesce(w, "NEXT_ACTION_TITLE", "اقدام هشدار ترکیبی"),
                 _DESC=_coalesce(w, "MATERIAL_DESC", "CANONICAL_GOODS_DESC"))
    order_bls = {o: _join(g["_B"]) for o, g in work[work["_O"].ne("")].groupby("_O", sort=False)}
    qty = {(m, o): r for m, o, r in zip(pos["_M"], pos["_O"], pos.to_dict("records"))} if not pos.empty else {}
    rows = []
    for (m, o), g in w.groupby(["_M", "_O"], sort=False):
        code = _worst(g["_C"])
        q = qty.get((m, o), {})
        rows.append({
            "سطح": CB.level_label(code), "کد سطح": code, "متریال": m, "شرح": _first(g["_DESC"]),
            "مقاومت (روز)": _min_res(g["_R"]), "سفارش": o, ORDER_BLS: order_bls.get(o, ""),
            "در راه": _n(q.get("در راه")), "در گمرک": _n(q.get("در گمرک")),
            **_gr_row(g.iloc[0]), GAP: _join(_gap_parts(g["_GAP"]), sep=" | "),
            "کجاست": _join(CB._col(g, "STATUS_WHERE")), "مرحله": _first(g["_STAGE"]),
            "کارشناس مسئول": _join(CB._col(g, "CANONICAL_EXPERT")), "اداره": _join(g["_DEPT"]),
            "اقدام بعدی": _first(g["_ACT"]), "مسئول اقدام": _first(CB._col(g, "NEXT_ACTION_OWNER")),
            "مهلت اقدام": _first(CB._col(g, "NEXT_ACTION_DUE_DATE")),
            "اقدام پیشنهادی": _first(CB._col(g, "اقدام پیشنهادی مقاومت")) or (MAYBE_CRIT if code == "UNKNOWN" else ""),
        })
    out = pd.DataFrame(rows)
    out["_r"] = out["کد سطح"].map(CB.level_rank)
    out["_u"] = ~out["کد سطح"].isin(levels)
    out = out.sort_values(["_u", "مقاومت (روز)", "_r"], na_position="last").drop(columns=["_r", "_u"])
    out = out.reset_index(drop=True)
    out["اولویت"] = range(1, len(out) + 1)
    return out[FOLLOW_COLS]


# ─────────────────────────── بررسی‌های موجودی ───────────────────────────
def checks_view(mats: pd.DataFrame, pos: pd.DataFrame, levels: Sequence[str]) -> pd.DataFrame:
    level_of = dict(zip(mats["متریال"], mats["کد سطح"])) if not mats.empty else {}
    rows: List[Dict[str, Any]] = []

    def add(kind: str, m: str, o: str, detail: str) -> None:
        code = level_of.get(m, "UNKNOWN")
        rows.append({"بررسی": kind, "متریال": m, "سفارش": o, "سطح": CB.level_label(code), "کد سطح": code,
                     "جزئیات": detail})

    if not pos.empty:
        for _, r in pos[pos["تعارض"].map(_s).ne("")].iterrows():
            add(CHK_CONFLICT, r["_M"], r["_O"], _s(r["تعارض"]))
    for _, r in mats.iterrows():
        m, status = r["متریال"], r["وضعیت داده موجودی"]
        gap = _s(r.get(GAP, ""))
        if r["کد سطح"] == "UNKNOWN" and "UNKNOWN" not in levels:
            add(CHK_MAYBE_CRIT, m, "", MAYBE_CRIT + (f" — نقص داده: {gap}" if gap else ""))
        if status == INV_NONE:
            add(CHK_NO_DATA, m, "", "نه موجودی Oracle (ایران‌خودرو/ساپکو) و نه مقدار پارت کارشناس ثبت شده است")
        elif status == INV_EXPERT:
            add(CHK_NO_ORACLE, m, "", "موجودی ایران‌خودرو و ساپکو در Oracle نیست؛ فقط مقدار پارت کارشناس")
        if _n(r["نیاز روزانه"]) is None and status != INV_NONE:
            add(CHK_NO_NEED, m, "", "نیاز روزانه ثبت نشده؛ مقاومت قابل محاسبه نیست")
        stock = [x for x in (_n(r["موجودی ایران‌خودرو"]), _n(r["موجودی ساپکو"])) if x is not None]
        if r["کد سطح"] in levels and stock and sum(stock) > 0:
            res = _n(r["مقاومت (روز)"])
            add(CHK_STOCK_CRIT, m, "",
                f"موجودی Oracle {sum(stock):,.0f}؛ نیاز روزانه {_txt_num(r['نیاز روزانه'])}؛ "
                f"مقاومت {'—' if res is None else f'{res:,.1f}'} روز")
    if not pos.empty:
        for _, r in pos[pos["وضعیت نامشخص"].fillna(0) > 0].iterrows():
            add(CHK_UNKNOWN_STATE, r["_M"], r["_O"], f"{r['وضعیت نامشخص']:,.0f} واحد بدون Order Status شناخته‌شده")
    out = pd.DataFrame(rows, columns=CHECK_COLS)
    if not out.empty:
        out["_k"] = out["بررسی"].map({k: i for i, k in enumerate(CHECK_ORDER)})
        out["_r"] = out["کد سطح"].map(CB.level_rank)
        out = out.sort_values(["_k", "_r", "متریال"]).drop(columns=["_k", "_r"])
    return out.reset_index(drop=True)


# ─────────────────────────── ورودی ───────────────────────────
def build_model(df: Optional[pd.DataFrame], extras: Any = None, ref_date: str = "",
                levels: Sequence[str] = CB.DEFAULT_LEVELS) -> InventoryModel:
    """مدل مشترک Studio، HTML و Excel. ``levels`` سطح‌هایی است که «بحرانی» شمرده می‌شوند."""
    levels = tuple(levels) or CB.DEFAULT_LEVELS
    model = InventoryModel(ref_date=_s(ref_date), levels=levels)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        model.kpis = _kpis(model)
        return model
    work = _prepare(df)
    pos, source = _positions(work, extras)
    model.source_rows = len(df)
    model.quantity_source = source
    model.materials = material_view(work, pos, levels)
    model.orders = order_view(work, levels)
    model.bls = bl_view(work, levels, model.ref_date)
    model.followup = followup_view(work, pos, levels)
    model.checks = checks_view(model.materials, pos, levels)
    model.kpis = _kpis(model, pos)
    return model


def _kpis(model: InventoryModel, pos: Optional[pd.DataFrame] = None) -> Dict[str, int]:
    """شمار یکتا: هر نما یک ردیف برای هر کلید دارد، پس شمار ردیف نما = شمار یکتای کلید."""
    lv = model.levels
    m, o, b = model.materials, model.orders, model.bls
    crit_bls = b[b["کد سطح"].isin(lv)] if not b.empty else b
    conflicts = 0
    if pos is not None and not pos.empty:
        conflicts = int(pos.loc[pos["تعارض"].map(_s).ne(""), ["_M", "_O"]].drop_duplicates().shape[0])
    return {
        "متریال در گزارش": int(m["متریال"].nunique()) if not m.empty else 0,
        "متریال بحرانی": int(m.loc[m["کد سطح"].isin(lv), "متریال"].nunique()) if not m.empty else 0,
        KPI_MAYBE: int(m.loc[m["کد سطح"].eq("UNKNOWN"), "متریال"].nunique()) if not m.empty and "UNKNOWN" not in lv
        else 0,
        "سفارش با متریال بحرانی": int(o.loc[o["کد سطح"].isin(lv), "سفارش"].nunique()) if not o.empty else 0,
        "بارنامه با سفارش بحرانی": int(crit_bls["بارنامه"].nunique()) if not b.empty else 0,
        "بارنامه بحرانی ترخیص‌نشده": int(crit_bls.loc[crit_bls["ترخیص"].ne("ترخیص کامل"), "بارنامه"].nunique())
        if not b.empty else 0,
        CHK_NO_DATA: int(m["وضعیت داده موجودی"].eq(INV_NONE).sum()) if not m.empty else 0,
        "سفارش×متریال با تعارض": conflicts,
    }


# ═══════════════════════════════ HTML ═══════════════════════════════
def _H():
    from . import fx_html as H
    return H


def _css_icons(fn: Callable) -> Callable:
    """آیکن بدون SVG تا Studio (``st.html``) و HTML ارسالی یک نشانه‌گذاری داشته باشند."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with I.css_icons():
            return fn(*args, **kwargs)
    return wrapper


def L(text: str, lang: str = C.FA) -> str:
    return _H().L(text, lang)


def _num(nd: int = 0) -> Callable:
    def cell(v: Any, _r: Any) -> str:
        x = _n(v)
        return '<span class="gx-na">—</span>' if x is None else f'<span class="gx-num">{x:,.{nd}f}</span>'
    return cell


def _level_cell(lang: str) -> Callable:
    def cell(v: Any, _r: Any) -> str:
        return _H().level_badge(_LEVEL_BY_LABEL.get(_s(v), "UNKNOWN"), lang)
    return cell


def _text_cell(lang: str) -> Callable:
    def cell(v: Any, _r: Any) -> str:
        t = _s(v)
        if not t:
            return '<span class="gx-na">—</span>'
        body = html.escape(C.phrase(t, lang))
        return f'<span class="inv-w">{body}</span>' if len(t) > 36 else body
    return cell


def _gap_cell(lang: str) -> Callable:
    def cell(v: Any, _r: Any) -> str:
        t = CB.gap_text(v, lang)
        return f'<span class="inv-w">{html.escape(t)}</span>' if t else '<span class="gx-na">—</span>'
    return cell


_NUMERIC = {"مقاومت (روز)": 1, "کمترین مقاومت (روز)": 1, BL_MIN_RES: 1, "موجودی ایران‌خودرو": 0, GR_DLV: 0, GR_BLK: 0,
            "موجودی ساپکو": 0, "نیاز روزانه": 0, "تعداد سفارش": 0, "تعداد متریال": 0, "روز از تخلیه": 0,
            "روزهای رسوب": 0, "اولویت": 0, **{lab: 0 for lab in QTY_LABELS}}
_PROGRAM_TEXT = {"وضعیت داده موجودی", "بررسی", "بارنامه بحرانی", "اقدام پیشنهادی", "مرحله", "اقدام بعدی", GR_LINK}


def _table(frame: pd.DataFrame, lang: str, max_rows: int, filter_box: bool, key: str) -> str:
    H = _H()
    shown = frame.drop(columns=["کد سطح"], errors="ignore")
    cells: Dict[str, Callable] = {c: _num(nd) for c, nd in _NUMERIC.items() if c in shown.columns}
    if "سطح" in shown.columns:
        cells["سطح"] = _level_cell(lang)
    for c in _PROGRAM_TEXT & set(shown.columns):
        cells[c] = _text_cell(lang)
    if GAP in shown.columns:
        cells[GAP] = _gap_cell(lang)
    body = H.table(shown, lang, cells=cells, max_rows=max_rows)
    if frame.empty or not filter_box:
        return body
    return (f'<div class="inv-filter"><input type="search" class="inv-q" data-inv="{key}" '
            f'placeholder="{html.escape(C.phrase("جستجو در این جدول", lang), quote=True)}" '
            f'aria-label="{html.escape(C.phrase("جستجو در این جدول", lang), quote=True)}"></div>'
            f'<div class="inv-t" id="inv-{key}">{body}</div>')


def _head(icon: str, title: str, note: str, lang: str, tone: str = "brand", count: Optional[int] = None) -> str:
    c = f'<small>{count:,}</small>' if count is not None else ""
    return (f'<div class="gx-sec">{I.icon_tile(icon, tone, 18)}<h3>{L(title, lang)}</h3>{c}</div>'
            f'<p class="gx-note">{L(note, lang)}</p>')


@_css_icons
def kpis_section(model: InventoryModel, lang: str = C.FA) -> str:
    if model.empty:
        return f'<div class="gx-empty inv-nodata">{L(NO_DATA, lang)}</div>'
    icons = ["box", "alert", "stamp", "ship", "customs", "search", "flag"]
    tiles = []
    for i, (k, v) in enumerate(model.kpis.items()):
        tone = "critical" if v and i > 0 else "brand"
        tiles.append(I.kpi_tile(icons[i % len(icons)], C.label(k, lang) if lang == C.EN else k, f"{v:,}", tone=tone))
    lv = (", " if lang == C.EN else "، ").join(C.phrase(CB.level_label(c), lang) for c in model.levels)
    return (f'<div class="mi-kpis">{"".join(tiles)}</div>'
            f'<p class="gx-note">{L("سطوح بحرانی", lang)}: {html.escape(lv)} · '
            f'{L(NOTE_UNIQUE, lang)}</p>')


@_css_icons
def materials_section(model: InventoryModel, lang: str = C.FA, max_rows: int = 500, filter_box: bool = False) -> str:
    note = NOTE_MAT
    return (f'<div class="gx-part inv-part">{_head("box", "متریال‌ها به تفکیک موجودی و بحرانی بودن", note, lang, count=len(model.materials))}'
            f'{_table(model.materials, lang, max_rows, filter_box, "mat")}</div>')


@_css_icons
def orders_section(model: InventoryModel, lang: str = C.FA, max_rows: int = 500, filter_box: bool = False) -> str:
    note = NOTE_ORD
    return (f'<div class="gx-part inv-part">{_head("stamp", "سفارش‌ها و بدترین سطح بحرانی متریال‌هایشان", note, lang, count=len(model.orders))}'
            f'{_table(model.orders, lang, max_rows, filter_box, "ord")}</div>')


@_css_icons
def bls_section(model: InventoryModel, lang: str = C.FA, max_rows: int = 500, filter_box: bool = False) -> str:
    note = NOTE_BL
    return (f'<div class="gx-part inv-part">{_head("ship", "بارنامه‌ها و سفارش‌های رویشان", note, lang, count=len(model.bls))}'
            f'{_table(model.bls, lang, max_rows, filter_box, "bl")}</div>')


@_css_icons
def followup_section(model: InventoryModel, lang: str = C.FA, max_rows: int = 500, filter_box: bool = False) -> str:
    note = NOTE_FU
    return (f'<div class="gx-part inv-part">{_head("flag", "فهرست رسیدگی (کمترین مقاومت اول)", note, lang, "critical", len(model.followup))}'
            f'{_table(model.followup, lang, max_rows, filter_box, "fu")}</div>')


@_css_icons
def checks_section(model: InventoryModel, lang: str = C.FA, max_rows: int = 500, filter_box: bool = False) -> str:
    note = NOTE_CHK
    chk = model.checks
    chips = ""
    if not chk.empty:
        H = _H()
        counts = chk["بررسی"].value_counts()
        chips = '<div class="inv-chips">' + "".join(
            H.pill(f"{C.phrase(k, lang)}: {int(counts[k]):,}", "critical" if k in (CHK_CONFLICT, CHK_NO_DATA) else "warning", lang)
            for k in CHECK_ORDER if k in counts.index) + "</div>"
    return (f'<div class="gx-part inv-part">{_head("search", "بررسی‌های موجودی", note, lang, count=len(chk))}'
            f'{chips}{_table(chk, lang, max_rows, filter_box, "chk")}</div>')


SECTIONS = (("box", "متریال‌ها (کنترل موجودی)", materials_section), ("stamp", "سفارش‌ها", orders_section),
            ("ship", "بارنامه‌ها", bls_section), ("flag", "رسیدگی", followup_section),
            ("search", "بررسی‌های موجودی", checks_section))


def inv_css() -> str:
    return """
.inv-filter{display:flex;justify-content:flex-start;margin:4px 0 6px}
.gx .inv-q,.inv-q{font:inherit;font-size:12px;padding:7px 12px;border-radius:999px;border:1px solid var(--border,#d5e8e8);
  width:320px!important;max-width:100%;background:#fff;color:inherit}
.inv-chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px}
.inv-w{display:inline-block;min-width:220px;white-space:normal}
.inv-nodata{font-size:15px;font-weight:700}
.inv-part .gx-tbl td{min-width:84px;max-width:360px;white-space:normal}
@media print{.inv-filter{display:none}}
"""


_FILTER_JS = ("<script>document.querySelectorAll('.inv-q').forEach(function(q){q.addEventListener('input',function(){"
              "var v=q.value.trim().toLowerCase(),t=document.getElementById('inv-'+q.dataset.inv);if(!t)return;"
              "t.querySelectorAll('tbody tr').forEach(function(r){r.style.display=!v||r.textContent.toLowerCase()"
              ".indexOf(v)>=0?'':'none';});});});</script>")


@_css_icons
def build_html(model: InventoryModel, title: str = "", lang: str = C.FA, embed_excel: bool = True,
               embed_fonts: Optional[bool] = None, max_rows: int = 500) -> str:
    """صفحه HTML مستقل و آفلاین (بدون CDN): کارت‌ها و پنج زبانه متریال / سفارش / بارنامه / رسیدگی / بررسی."""
    from ..design import fonts as F
    from ..design.css import stylesheet
    H = _H()
    title = title or C.phrase(TITLE, lang)
    font_css = F.html_font_css() if (embed_fonts is None or embed_fonts) else ""
    sub = (f'{L("تاریخ مرجع", lang)} <span class="ltr">{html.escape(model.ref_date)}</span>' if model.ref_date else "")
    dl = ""
    if embed_excel and not model.empty:
        dl = H.data_link(build_excel(model, lang), f"GSI_INVENTORY_CRITICAL_{model.ref_date or 'report'}.xlsx",
                         "Excel کنترل موجودی و اقلام بحرانی", lang=lang)
    if model.empty:
        body = kpis_section(model, lang)
    else:
        panes = [fn(model, lang, max_rows=max_rows, filter_box=True) for _, _, fn in SECTIONS]
        names = [(ic, t) for ic, t, _ in SECTIONS]
        body = kpis_section(model, lang) + H.tabs_html(panes, lang, key="inv", names=names)
    page_dir = 'lang="en" dir="ltr"' if lang == C.EN else 'lang="fa" dir="rtl"'
    legal = NOTE_LEGAL
    return (f'<!DOCTYPE html><html {page_dir}><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{font_css}{stylesheet()}{H.css()}{inv_css()}</style></head><body class="gx gx-page"><main class="gx-wrap">'
            f'{_BRAND.band_raw(html.escape(title), sub_html=sub, eyebrow_html=" · ".join(L(x, lang) for x in ("کنترل موجودی", "متریال", "سفارش", "بارنامه")), side_html=f"<div class=gx-chips>{dl}</div>", tag=L(_BRAND.TAGLINE_FA, lang))}'
            f'{body}<p class="gx-legal">{L(legal, lang)}</p></main>{_FILTER_JS}</body></html>')


# ═══════════════════════════════ Excel ═══════════════════════════════
SHEETS = ("خلاصه", "متریال‌ها", "سفارش‌ها", "بارنامه‌ها", "رسیدگی", "بررسی‌های موجودی")


def build_excel(model: InventoryModel, lang: str = C.FA) -> bytes:
    """کتاب Excel: خلاصه، متریال‌ها، سفارش‌ها، بارنامه‌ها، رسیدگی و بررسی‌ها؛ سرستون فارسی و شیت راست‌به‌چپ."""
    from . import fx_excel as XL
    wb = XL._book()
    lv = "، ".join(CB.level_label(c) for c in model.levels)
    pairs = [("گزارش", TITLE), ("تاریخ مرجع", model.ref_date or "—"), ("سطوح بحرانی", lv)]
    if model.empty:
        pairs.append(("وضعیت", NO_DATA))
    pairs += [(k, v) for k, v in model.kpis.items()]
    pairs.append(("قاعده", "شمارش یکتا بر متریال، سفارش و بارنامه؛ مقدار پارت یک بار برای هر سفارش × متریال؛ "
                           "نامعلوم خالی است، نه صفر؛ بارنامه به سفارش وصل است، نه به متریال."))
    XL.add_key_values(wb, "خلاصه", pairs, lang, title=TITLE + (f" — {model.ref_date}" if model.ref_date else ""))
    drop = ["کد سطح"]
    XL.add_frame(wb, "متریال‌ها", model.materials.drop(columns=drop, errors="ignore"), lang,
                 note="یک ردیف برای هر متریال؛ مقدار پارت‌ها جمع سفارش × متریال‌های یکتا؛ خانه خالی = نامعلوم.")
    XL.add_frame(wb, "سفارش‌ها", model.orders.drop(columns=drop, errors="ignore"), lang,
                 note="یک ردیف برای هر سفارش.")
    XL.add_frame(wb, "بارنامه‌ها", model.bls.drop(columns=drop, errors="ignore"), lang,
                 note="یک ردیف برای هر بارنامه؛ متریال‌ها از سفارش‌های روی بارنامه‌اند، نه از خود بارنامه.")
    XL.add_frame(wb, "رسیدگی", model.followup.drop(columns=drop, errors="ignore"), lang,
                 note="متریال بحرانی در هر سفارش؛ کمترین مقاومت اول؛ بعد ردیف‌های با وضعیت نامشخص "
                      "(ممکن است بحرانی) با نقص داده. تحویل از شیت GR فایل SAP.")
    XL.add_frame(wb, "بررسی‌های موجودی", model.checks.drop(columns=drop, errors="ignore"), lang,
                 note="تعارض مقدار کارشناس، شکاف پوشش داده موجودی و متریال بحرانی با موجودی.")
    return XL._bytes(wb)


def write_report(model: InventoryModel, out_dir: Any, lang: str = C.FA) -> Dict[str, str]:
    """HTML و Excel را کنار هم می‌نویسد؛ {نوع: مسیر}."""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"GSI_INVENTORY_CRITICAL_{model.ref_date.replace('/', '-') or 'report'}_{lang}"
    h = out / f"{stem}.html"
    x = out / f"{stem}.xlsx"
    h.write_text(build_html(model, lang=lang), encoding="utf-8")
    x.write_bytes(build_excel(model, lang))
    return {"html": str(h), "excel": str(x)}
