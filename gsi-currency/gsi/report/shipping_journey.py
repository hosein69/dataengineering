# -*- coding: utf-8 -*-
"""مسیر شواهد هر بارنامه (R10، مالک ۱۴۰۵/۰۷/۰۸): نمای تصویری وضعیت حمل، کوتاژ و ترخیص.

هدف: هر کس گزارش حمل را ببیند، بی‌متن و بی‌نام بردن از کسی، بداند هر بارنامه کجاست و کدام بخش
مسیرش روشن، ضمنی، متعارض یا بی‌شاهد است. فقط وضعیت نشان داده می‌شود؛ هیچ ستونی مقصر یا مسئول
نمی‌سازد و نام شخص در این نما نیست.

الگوریتم (قاعده مالک: «اگر شک داری انجام نده»):

1. **ایستگاه‌ها** به ترتیب مسیر کالا: مبدأ، حرکت، ورود، تخلیه، ترخیصیه، کوتاژ، ترخیص جزئی،
   ترخیص کامل، رسید انبار SAP.
2. **شاهد هر ایستگاه** فقط از ستون‌هایی که همان رویداد را ثبت می‌کنند (:data:`DATED`,
   :data:`UNDATED`, :data:`FLAGS`)، با نام منبع. تاریخ‌های متفاوت برای یک ایستگاه (میان دو منبع یا
   در یک منبع) «متعارض» است و هیچ‌کدام برگزیده نمی‌شود.
3. **ترخیص** همان قاعده R9 سه گزارش: فقط پرچم ترخیص وضعیت می‌سازد؛ تاریخ یا ادعای کارشناس بدون
   پرچم «متعارض» است.
4. **عبور ضمنی** فقط وقتی منطقاً قطعی است (:data:`IMPLIES`): مثلاً ترخیص بدون ورود ممکن نیست. ایستگاه
   ضمنی تاریخ ندارد و شاهد شمرده نمی‌شود. کوتاژ و ترخیصیه ورود را ثابت نمی‌کنند (اظهار پیش از ورود
   ممکن است)، پس از آن‌ها چیزی استنتاج نمی‌شود.
5. **رسید انبار SAP** فقط وقتی به بارنامه نسبت داده می‌شود که سفارش‌های بارنامه در فایل کارشناسان
   تنها همین یک بارنامه را داشته باشند، هیچ ردیف دیگری همان سفارش × متریال را زیر بارنامه دیگری نیاورد،
   قلم PO مشترک نباشد و تاریخ رسید پیش از ورود/تخلیه نباشد؛ وگرنه «قابل نسبت دادن نیست».
6. **کشف فرایند**: گراف گذار مستقیم (directly-follows) از ایستگاه‌های تاریخ‌دار هر بارنامه، با شمار و
   میانه روز؛ «اثر انگشت شواهد» (کدام ایستگاه‌ها شاهد دارند) و وارونگی ترتیب فقط برای جفت‌های قطعی.
7. **نظریه بازی‌ها**: سهم هر فایل در روشن کردن وضعیت با **ارزش شپلی** بازی پوشش (هر خانه بارنامه ×
   ایستگاه که چند منبع شاهدش هستند میان همان منبع‌ها برابر تقسیم می‌شود؛ برای بازی اجتماع این
   دقیقاً ارزش شپلی است) و شمار خانه‌هایی که فقط یک منبع دارند (اگر آن فایل نباشد، ابهام برمی‌گردد).
   این سهمِ داده است، نه ارزیابی افراد.
"""
from __future__ import annotations

import html
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from ..core.jalali import CalendarEngine, format_jalali
from ..design import icons as I
from ..design import tokens as T
from . import fx_insight as X

# ═══════════════════════════════ ایستگاه‌ها و منبع‌ها ═══════════════════════════════
#: (کد، برچسب فارسی، برچسب انگلیسی، آیکن)
STATIONS: Tuple[Tuple[str, str, str, str], ...] = (
    ("ORIGIN", "مبدأ", "Origin", "home"),
    ("SHIP", "حرکت", "Shipped", "ship"),
    ("ARRIVE", "ورود", "Arrival", "flag"),
    ("DISCHARGE", "تخلیه", "Discharge", "box"),
    ("DO", "ترخیصیه", "Delivery order", "doc_check"),
    ("COTAGE", "کوتاژ", "Cotage", "stamp"),
    ("PARTIAL", "ترخیص جزئی", "Partial clearance", "layers"),
    ("CLEAR", "ترخیص کامل", "Full clearance", "check"),
    ("RECEIPT", "رسید انبار", "Warehouse receipt", "warehouse"),
)
CODES = [s[0] for s in STATIONS]
IDX = {c: i for i, c in enumerate(CODES)}
FA_OF = {s[0]: s[1] for s in STATIONS}
EN_OF = {s[0]: s[2] for s in STATIONS}
ICON_OF = {s[0]: s[3] for s in STATIONS}

#: منبع ← نام فایل (همان نام‌های قرارداد منبع)
SOURCES: Dict[str, str] = {"bl": "BLs Tracking", "cl": "Clearance", "cot": "Cottage Tracking",
                           "exp": "Commercial Expert Data", "sap": "SAP GR"}

#: ستون تاریخی که خود رویداد ایستگاه را ثبت می‌کند
DATED: Tuple[Tuple[str, str, str], ...] = (
    ("SHIP", "bl", "BL_BL_DATE"),
    ("ARRIVE", "cl", "CL_ARRIVAL_DATE"),
    ("DISCHARGE", "bl", "BL_DISCHARGE_DATE"),
    ("DO", "bl", "BL_DO_DATE"),
    ("COTAGE", "cl", "CL_COTAGE_DATE"), ("COTAGE", "cot", "COT_COTAGE_DATE"),
    ("PARTIAL", "cl", "CL_PARTIAL_CLEAR_DATE"), ("PARTIAL", "cot", "COT_PARTIAL_DATE_1"),
    ("CLEAR", "cl", "CL_CLEAR_DATE"), ("CLEAR", "cot", "COT_FULL_CLEAR_DATE"),
)
#: ستونی که رخ دادن ایستگاه را ثابت می‌کند ولی تاریخش تاریخ ایستگاه نیست
UNDATED: Tuple[Tuple[str, str, str], ...] = (
    ("SHIP", "bl", "BL_BL_DELIVERY_DATE"),       # بارنامه تحویل شده ← کالا بار شده
    ("DISCHARGE", "bl", "BL_WAREHOUSE_RECEIPT"),  # قبض انبار بندر ← کالا تخلیه شده
    ("COTAGE", "cl", "CL_COTAGE_NO"), ("COTAGE", "cot", "COT_NO"),
)
#: پرچم وضعیت (قاعده R9: فقط پرچم ترخیص وضعیت ترخیص را می‌سازد)
FLAGS: Tuple[Tuple[str, str, str], ...] = (
    ("PARTIAL", "cl", "IS_PARTIAL_CLEARED"),
    ("CLEAR", "cl", "IS_FULL_CLEARED"), ("CLEAR", "cl", "CL_CLEAR_DONE_NO_DATE"),
)
#: وضعیت پارت کارشناس ← ایستگاهی که کارشناس ادعا می‌کند
EXPERT_AT = {"AT_SUPPLIER": "ORIGIN", "READY": "ORIGIN", "IN_TRANSIT": "SHIP", "IN_CUSTOMS": "ARRIVE",
             "CLEARED": "CLEAR"}

#: ایستگاه ← ایستگاه‌های بعدی‌ای که رخ دادنشان این یکی را منطقاً قطعی می‌کند
IMPLIES: Dict[str, Tuple[str, ...]] = {
    "SHIP": ("ARRIVE", "DISCHARGE", "PARTIAL", "CLEAR"),
    "ARRIVE": ("DISCHARGE", "PARTIAL", "CLEAR"),
    "COTAGE": ("PARTIAL", "CLEAR"),
}
#: فقط حمل دریایی: تخلیه پیش از ترخیص قطعی است
IMPLIES_SEA: Dict[str, Tuple[str, ...]] = {"DISCHARGE": ("PARTIAL", "CLEAR")}

#: جفت‌هایی که ترتیبشان قطعی است؛ تاریخ دومی پیش از اولی ← «وارونگی ترتیب»
ORDER_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("SHIP", "ARRIVE"), ("SHIP", "DISCHARGE"), ("SHIP", "CLEAR"), ("ARRIVE", "DISCHARGE"),
    ("ARRIVE", "PARTIAL"), ("ARRIVE", "CLEAR"), ("DISCHARGE", "CLEAR"), ("COTAGE", "PARTIAL"), ("COTAGE", "CLEAR"),
)

# حالت‌های خانه
DATED_S, UNDATED_S, CONFLICT_S, IMPLIED_S, NONE_S, UNATTR_S, PART_S = (
    "dated", "undated", "conflict", "implied", "none", "unattributed", "partial")
STATE_FA = {DATED_S: "شاهد با تاریخ", UNDATED_S: "شاهد بی‌تاریخ", CONFLICT_S: "شواهد متعارض",
            IMPLIED_S: "عبور ضمنی (منطقی، بی‌تاریخ)", NONE_S: "بی‌شاهد", UNATTR_S: "رسید هست، قابل نسبت دادن نیست",
            PART_S: "رسید بخشی از اقلام"}
NOT_STARTED = "بی‌شاهد مسیر"

EN: Dict[str, str] = {
    **{v: EN_OF[k] for k, v in FA_OF.items()},
    STATE_FA[DATED_S]: "Evidence with date", STATE_FA[UNDATED_S]: "Evidence without date",
    STATE_FA[CONFLICT_S]: "Conflicting evidence", STATE_FA[IMPLIED_S]: "Passed by logic (no date)",
    STATE_FA[NONE_S]: "No evidence", STATE_FA[UNATTR_S]: "Receipt exists, cannot be tied to this B/L",
    STATE_FA[PART_S]: "Receipt for some items", NOT_STARTED: "No route evidence",
    "مسیر شواهد": "Evidence route", "بارنامه": "B/L", "روشنی مسیر": "Route clarity",
    "ایستگاه متعارض": "Conflicting stations", "وارونگی ترتیب": "Order reversals",
    "کارشناس عقب‌تر از شواهد": "Expert status behind evidence", "کارشناس جلوتر از شواهد": "Expert status ahead of evidence",
    "ایستگاه فعلی": "Current station", "ایستگاه بعدی": "Next station", "روز در ایستگاه": "Days at station",
    "گذار مستقیم": "Directly-follows", "سهم هر فایل در روشن کردن وضعیت": "Each file's share in clarifying status",
    "تنها شاهد": "Only evidence", "اثر انگشت شواهد": "Evidence fingerprints", "منبع": "Source",
    "سهم شپلی": "Shapley share", "خانه با تنها یک منبع": "Cells with a single source",
    "ادعای کارشناس": "Expert's status", "میانه روز": "Median days", "بیشینه روز": "Max days",
    "شمار": "Count", "از": "From", "به": "To", "شواهد": "Evidence", "وضعیت": "State",
}


# ═══════════════════════════════ کمکی ═══════════════════════════════
def _d(v: Any) -> Optional[date]:
    if not X.s(v):
        return None
    try:
        return CalendarEngine.parse(v)
    except Exception:
        return None


#: ستون مشتق مارت که فقط از همان یک ستون منبع ساخته می‌شود (s20)؛ وقتی ستون خام منتشر نشده است
DERIVED_ALIAS = {"BL_DISCHARGE_DATE": "DISCHARGE_DATE", "CL_ARRIVAL_DATE": "ARRIVAL_DATE", "BL_DO_DATE": "DO_DATE",
                 "CL_PARTIAL_CLEAR_DATE": "PARTIAL_CLEAR_DATE"}


def _vals(g: pd.DataFrame, col: str) -> List[Any]:
    if col not in g.columns:
        col = DERIVED_ALIAS.get(col, col)
    return [v for v in g[col].tolist() if X.s(v)] if col in g.columns else []


def _jal(d: Optional[date]) -> str:
    return format_jalali(d) if d else ""


@dataclass
class Journey:
    """خروجی الگوریتم برای یک دامنه: یک ردیف برای هر بارنامه و جمع‌بندی‌های فرایندی."""
    rows: pd.DataFrame
    flow: pd.DataFrame
    variants: pd.DataFrame
    sources: pd.DataFrame
    kpis: Dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.rows.empty


ROW_COLS = ["بارنامه", "ایستگاه فعلی", "ایستگاه بعدی", "روز در ایستگاه", "ادعای کارشناس"] + \
           [FA_OF[c] for c in CODES]
FLOW_COLS = ["از", "به", "شمار", "میانه روز", "بیشینه روز"]
SOURCE_COLS = ["منبع", "سهم شپلی", "خانه با تنها یک منبع"]


def empty_journey() -> Journey:
    return Journey(pd.DataFrame(columns=ROW_COLS), pd.DataFrame(columns=FLOW_COLS),
                   pd.DataFrame(columns=["اثر انگشت شواهد", "شمار"]), pd.DataFrame(columns=SOURCE_COLS), {})


# ═══════════════════════════════ الگوریتم ═══════════════════════════════
def _expert_by_bl(extras: Any) -> Dict[str, List[str]]:
    try:
        ship = extras.get("expert_shipments") if extras is not None else None
    except Exception:
        ship = None
    out: Dict[str, List[str]] = defaultdict(list)
    if isinstance(ship, pd.DataFrame) and not ship.empty and {"BL", "PART_STATE"} <= set(ship.columns):
        for bl, st in zip(ship["BL"].map(X.s), ship["PART_STATE"].map(X.s)):
            if bl and st in EXPERT_AT:
                out[bl].append(st)
    return out


def _receipt(g: pd.DataFrame, bl: str, pair_bls: Dict[tuple, set], floor: Optional[date]) -> Tuple[str, Optional[date]]:
    """رسید انبار SAP برای بارنامه، فقط با نسبت دادن قطعی (بند ۵ الگوریتم)."""
    if not {"KEY_ORDER", "KEY_MATERIAL", "GR_DLV_DELIVERED_QTY"} <= set(g.columns):
        return NONE_S, None
    pairs = g.drop_duplicates(subset=["KEY_ORDER", "KEY_MATERIAL"])
    qty = pd.to_numeric(pairs["GR_DLV_DELIVERED_QTY"], errors="coerce")
    got = qty.gt(0)
    if not bool(got.any()):
        return NONE_S, None
    sole = True
    for _, r in pairs.iterrows():
        key = (X.s(r.get("KEY_ORDER")), X.s(r.get("KEY_MATERIAL")))
        n = X.n(r.get("MOGH_BL_COUNT"))
        if not key[0] or not key[1] or n != 1 or pair_bls.get(key, set()) != {bl} or X.s(r.get("GR_DLV_SHARED")):
            sole = False
            break
    dates = [d for d in (_d(v) for v in pairs.loc[got, "GR_DLV_LAST_DATE"] if "GR_DLV_LAST_DATE" in pairs) if d]
    last = max(dates) if dates else None
    if not sole or last is None or (floor is not None and last < floor):
        return UNATTR_S, None
    return (DATED_S if bool(got.all()) else PART_S), last


def build(bl_rows: pd.DataFrame, dossiers: pd.DataFrame, extras: Any, as_of: date, full_label: str) -> Journey:
    """مسیر شواهد هر بارنامه و جمع‌بندی‌های فرایندی؛ ``bl_rows`` ردیف‌های مارت با ``CANONICAL_BL``.

    ``dossiers`` پرونده‌های گزارش حمل است؛ وضعیت ترخیص (پرچم‌ها) و روش حمل از همان‌جا خوانده می‌شود تا
    این نما با کارت‌ها و جدول‌های گزارش یک عدد بدهد."""
    if bl_rows is None or bl_rows.empty or dossiers is None or dossiers.empty:
        return empty_journey()
    expert = _expert_by_bl(extras)
    pair_bls: Dict[tuple, set] = defaultdict(set)
    if {"KEY_ORDER", "KEY_MATERIAL"} <= set(bl_rows.columns):
        for o, m, b in zip(bl_rows["KEY_ORDER"].map(X.s), bl_rows["KEY_MATERIAL"].map(X.s), bl_rows["CANONICAL_BL"]):
            pair_bls[(o, m)].add(b)
    parts = {b: g for b, g in bl_rows.groupby("CANONICAL_BL", sort=False)}

    rows, cells_src, fingerprints = [], [], Counter()
    edges: Dict[tuple, List[int]] = defaultdict(list)
    k = Counter()
    for _, dz in dossiers.iterrows():
        bl = X.s(dz["بارنامه"])
        g = parts.get(bl, bl_rows.iloc[0:0])
        modes = {X.s(v).upper() for v in _vals(g, "TRANSPORT_MODE")}
        sea = modes == {"SEA"}
        other = bool(modes) and "SEA" not in modes
        full = X.s(dz.get("وضعیت ترخیص")) == full_label
        partial_flag = any(X.truthy(v) for v in _vals(g, "IS_PARTIAL_CLEARED"))
        cell: Dict[str, Dict[str, Any]] = {c: {"state": NONE_S, "date": None, "src": []} for c in CODES}
        # ── شاهد مستقیم
        for st, src, col in DATED:
            ds = sorted({d for d in (_d(v) for v in _vals(g, col)) if d})
            for d in ds:
                cell[st]["src"].append((src, _jal(d)))
        for st, src, col in UNDATED:
            if _vals(g, col):
                cell[st]["src"].append((src, ""))
        for st, src, col in FLAGS:
            if any(X.truthy(v) for v in _vals(g, col)):
                cell[st]["src"].append((src, ""))
        claims = sorted({EXPERT_AT[s] for s in expert.get(bl, [])}, key=IDX.get)
        for c in claims:
            if c in ("SHIP", "ARRIVE"):
                cell[c]["src"].append(("exp", ""))
        for c in CODES:
            x = cell[c]
            dates = sorted({d for _, d in x["src"] if d})
            if not x["src"]:
                continue
            if len(dates) > 1:
                x["state"] = CONFLICT_S
            else:
                x["state"] = DATED_S if dates else UNDATED_S
                x["date"] = _d(dates[0]) if dates else None
        # ── ترخیص: فقط پرچم (R9)
        clear_claim = "CLEAR" in claims
        if full:
            if clear_claim:
                cell["CLEAR"]["src"].append(("exp", ""))
        elif cell["CLEAR"]["src"] or clear_claim:
            if clear_claim:
                cell["CLEAR"]["src"].append(("exp", ""))
            cell["CLEAR"].update(state=CONFLICT_S, date=None)
        if not partial_flag and not full and cell["PARTIAL"]["src"]:
            cell["PARTIAL"].update(state=CONFLICT_S, date=None)
        reached = {c for c in CODES if cell[c]["state"] in (DATED_S, UNDATED_S)
                   or (cell[c]["state"] == CONFLICT_S and c not in ("PARTIAL", "CLEAR"))}
        if full:
            reached.add("CLEAR")
        if partial_flag:
            reached.add("PARTIAL")
        # ── رسید انبار SAP
        floor = max([d for d in (cell["ARRIVE"]["date"], cell["DISCHARGE"]["date"]) if d], default=None)
        rs, rd = _receipt(g, bl, pair_bls, floor)
        if rs != NONE_S:
            cell["RECEIPT"].update(state=rs, date=rd)
            if rs in (DATED_S, PART_S):
                cell["RECEIPT"]["src"].append(("sap", _jal(rd)))
                reached.add("RECEIPT")
        # ── عبور ضمنی
        imp = dict(IMPLIES)
        if sea:
            imp.update(IMPLIES_SEA)
        for st, later in imp.items():
            if cell[st]["state"] == NONE_S and any(l in reached for l in later):
                cell[st]["state"] = IMPLIED_S
        # ── وارونگی ترتیب
        rev = set()
        for a, b in ORDER_PAIRS:
            da, db = cell[a]["date"], cell[b]["date"]
            if cell[a]["state"] == DATED_S and cell[b]["state"] == DATED_S and da and db and db < da:
                rev |= {a, b}
        # ── ایستگاه فعلی و بعدی
        pos = [c for c in CODES if c in reached or cell[c]["state"] == IMPLIED_S]
        cur = max(pos, key=IDX.get) if pos else ""
        nxt = ""
        start = IDX[cur] + 1 if cur else IDX["SHIP"]
        for c in CODES[start:]:
            if c in ("PARTIAL", "ORIGIN") or (other and c in ("DISCHARGE", "DO")):
                continue
            if c == "RECEIPT" and not full:
                continue
            if c == "CLEAR" and full:
                continue
            if c not in reached and cell[c]["state"] != IMPLIED_S:
                nxt = c
                break
        cur_date = cell[cur]["date"] if cur else None
        days = (as_of - cur_date).days if cur_date and as_of >= cur_date else None
        claim_pos = max((IDX[c] for c in claims), default=None)
        cur_pos = IDX[cur] if cur else -1
        # ── شمارش‌ها
        k["bl"] += 1
        for c in CODES:
            if c == "ORIGIN":
                continue
            s = cell[c]["state"]
            if c in ("PARTIAL", "RECEIPT") and s == NONE_S:
                continue
            if IDX[c] <= cur_pos or s != NONE_S:
                k["cells"] += 1
                k["dated"] += int(s in (DATED_S, PART_S))
            k["conflict"] += int(s == CONFLICT_S)
            srcs = {src for src, _ in cell[c]["src"]}
            if srcs:
                cells_src.append(srcs)
        k["reversal"] += int(bool(rev))
        if claim_pos is not None and claim_pos < cur_pos:
            k["expert_behind"] += 1
        if claim_pos is not None and claim_pos > cur_pos:
            k["expert_ahead"] += 1
        fingerprints[tuple(c for c in CODES[1:] if cell[c]["state"] in (DATED_S, UNDATED_S, CONFLICT_S, PART_S))] += 1
        seq = sorted([c for c in CODES if cell[c]["state"] in (DATED_S, PART_S) and cell[c]["date"]],
                     key=lambda c: (cell[c]["date"], IDX[c]))
        for a, b in zip(seq, seq[1:]):
            edges[(a, b)].append((cell[b]["date"] - cell[a]["date"]).days)
        rows.append({
            "بارنامه": bl, "ایستگاه فعلی": FA_OF.get(cur, NOT_STARTED), "ایستگاه بعدی": FA_OF.get(nxt, ""),
            "روز در ایستگاه": days,
            "ادعای کارشناس": "، ".join(FA_OF[c] for c in claims),
            **{FA_OF[c]: _cell_text(cell[c]) for c in CODES},
            "_CUR": cur, "_NEXT": nxt, "_CELLS": cell, "_REV": rev, "_CLAIMS": claims,
            "_FILTER_DATE": X.s(dz.get("_FILTER_DATE")), "_CRIT": X.s(dz.get("بحرانی")),
        })
    flow = pd.DataFrame([{"از": FA_OF[a], "به": FA_OF[b], "شمار": len(v),
                          "میانه روز": float(pd.Series(v).median()), "بیشینه روز": int(max(v)),
                          "_A": a, "_B": b} for (a, b), v in edges.items()])
    if not flow.empty:
        flow = flow.sort_values(["_A", "شمار"], key=lambda s: s.map(IDX) if s.name == "_A" else -s).reset_index(drop=True)
    else:
        flow = pd.DataFrame(columns=FLOW_COLS)
    variants = pd.DataFrame([{"اثر انگشت شواهد": " · ".join(FA_OF[c] for c in fp) or NOT_STARTED, "شمار": n, "_FP": fp}
                             for fp, n in fingerprints.most_common()])
    share: Dict[str, float] = defaultdict(float)
    sole: Counter = Counter()
    for srcs in cells_src:
        for s in srcs:
            share[s] += 1.0 / len(srcs)
        if len(srcs) == 1:
            sole[next(iter(srcs))] += 1
    total = sum(share.values())
    sources = pd.DataFrame([{"منبع": SOURCES[s], "سهم شپلی": round(100 * share.get(s, 0.0) / total, 1) if total else 0.0,
                             "خانه با تنها یک منبع": int(sole.get(s, 0)), "_K": s} for s in SOURCES])
    sources = sources.sort_values("سهم شپلی", ascending=False).reset_index(drop=True)
    kpis = {"bl": k["bl"], "clarity": round(100 * k["dated"] / k["cells"]) if k["cells"] else None,
            "conflict": k["conflict"], "reversal": k["reversal"], "expert_behind": k["expert_behind"],
            "expert_ahead": k["expert_ahead"]}
    return Journey(pd.DataFrame(rows), flow, variants, sources, kpis)


def _cell_text(x: Dict[str, Any], lang: str = "fa") -> str:
    """متن خانه برای Excel و راهنمای شناور: حالت · منبع تاریخ."""
    src = " | ".join(f"{SOURCES[s]}{(' ' + d) if d else ''}" for s, d in x["src"])
    return _t(STATE_FA[x["state"]], lang) + (f" · {src}" if src else "")


def export_frame(j: Journey, lang: str = "fa") -> pd.DataFrame:
    """جدول Excel/Studio: یک ردیف برای هر بارنامه، متن هر ایستگاه = حالت · فایل و تاریخ."""
    if j.rows.empty:
        return pd.DataFrame(columns=ROW_COLS)
    out = j.rows[ROW_COLS].copy()
    out["روز در ایستگاه"] = pd.array([None if v is None or pd.isna(v) else int(v) for v in out["روز در ایستگاه"]],
                                     dtype="Int64")
    for c in CODES:
        out[FA_OF[c]] = [_cell_text(x[c], lang) for x in j.rows["_CELLS"]]
    if lang == "en":
        for col in ("ایستگاه فعلی", "ایستگاه بعدی"):
            out[col] = out[col].map(lambda v: _t(v, lang))
        out["ادعای کارشناس"] = out["ادعای کارشناس"].map(lambda v: ", ".join(_t(p, lang) for p in v.split("، ") if p))
    return out


# ═══════════════════════════════ نمایش (فقط HTML و CSS؛ Studio SVG را حذف می‌کند) ═══════════════════════════════
def _t(text: str, lang: str) -> str:
    return EN.get(text, text) if lang == "en" else text


def _e(text: str, lang: str) -> str:
    return html.escape(_t(text, lang))


def _dot(x: Dict[str, Any], code: str, cur: str, nxt: str, rev: set, claims: List[str], lang: str) -> str:
    cls = ["jd", "s-" + x["state"]]
    if code == cur:
        cls.append("is-cur")
    if code == nxt:
        cls.append("is-next")
    if code in rev:
        cls.append("is-rev")
    if code in claims:
        cls.append("has-x")
    tip = _t(STATE_FA[x["state"]], lang)
    src = " | ".join(f"{SOURCES[s]}{(' ' + d) if d else ''}" for s, d in x["src"])
    if src:
        tip += " · " + src
    if code in claims:
        tip += " · " + _t("ادعای کارشناس", lang)
    return f'<span class="{" ".join(cls)}" title="{html.escape(tip, quote=True)}"></span>'


def legend(lang: str) -> str:
    items = [(DATED_S, ""), (UNDATED_S, ""), (IMPLIED_S, ""), (CONFLICT_S, ""), (NONE_S, ""), (UNATTR_S, "")]
    out = "".join(f'<span class="jl"><span class="jd s-{s}"></span>{_e(STATE_FA[s], lang)}</span>' for s, _ in items)
    out += f'<span class="jl"><span class="jd s-dated is-cur"></span>{_e("ایستگاه فعلی", lang)}</span>'
    out += f'<span class="jl"><span class="jd s-none is-next"></span>{_e("ایستگاه بعدی", lang)}</span>'
    out += f'<span class="jl"><span class="jd s-none has-x"></span>{_e("ادعای کارشناس", lang)}</span>'
    out += f'<span class="jl"><span class="jd s-dated is-rev"></span>{_e("وارونگی ترتیب", lang)}</span>'
    return f'<div class="j-legend">{out}</div>'


def metro(j: Journey, lang: str, k_wrap: Callable[[str, str], str]) -> str:
    """خط مترو: هر ایستگاه با شمار بارنامه‌هایی که اکنون آنجا هستند (حباب به نسبت شمار)."""
    cur = Counter(j.rows["_CUR"]) if not j.rows.empty else Counter()
    top = max(cur.values(), default=1)
    stops = []
    start = cur.get("", 0)
    if start:
        stops.append(("", "dot", NOT_STARTED, start))
    stops += [(c, ICON_OF[c], FA_OF[c], cur.get(c, 0)) for c in CODES if c != "ORIGIN"]
    html_stops = []
    for code, ic, lab, n in stops:
        size = 26 + int(34 * (n / top)) if n else 18
        bub = (f'<span class="jm-b{" is-zero" if not n else ""}" style="width:{size}px;height:{size}px">'
               f'<b class="mi-kpi-val">{n:,}</b></span>')
        html_stops.append(f'<div class="jm-s">{k_wrap("j" + (code or "START"), bub)}'
                          f'<span class="jm-i">{I.icon(ic, 18)}</span><span class="jm-l">{_e(lab, lang)}</span></div>')
    return f'<div class="jm">{"".join(html_stops)}</div>'


def flow_view(j: Journey, lang: str) -> str:
    """گراف گذار مستقیم به شکل نوار: ضخامت = شمار بارنامه، عدد = میانه روز."""
    if j.flow.empty:
        return ""
    top = max(int(j.flow["شمار"].max()), 1)
    rows = []
    for _, r in j.flow.iterrows():
        w = 8 + 92 * r["شمار"] / top
        back = IDX[r["_B"]] < IDX[r["_A"]]
        rows.append(f'<div class="jf-r{" is-back" if back else ""}"><span class="jf-n">{I.icon(ICON_OF[r["_A"]], 16)}'
                    f'{_e(FA_OF[r["_A"]], lang)}</span><span class="jf-bar"><i style="width:{w:.0f}%"></i>'
                    f'<b>{int(r["شمار"]):,}</b></span><span class="jf-n">{I.icon(ICON_OF[r["_B"]], 16)}'
                    f'{_e(FA_OF[r["_B"]], lang)}</span><span class="jf-d">{r["میانه روز"]:,.0f}'
                    f'<small>{_e("میانه روز", lang)}</small></span></div>')
    return f'<div class="jf">{"".join(rows)}</div>'


def sources_view(j: Journey, lang: str) -> str:
    """سهم شپلی هر فایل (نوار) و خانه‌هایی که فقط همان فایل شاهدشان است (عدد)."""
    if j.sources.empty or not j.sources["سهم شپلی"].sum():
        return ""
    rows = []
    for _, r in j.sources.iterrows():
        rows.append(f'<div class="js-r"><span class="js-n">{html.escape(r["منبع"])}</span><span class="js-bar">'
                    f'<i style="width:{r["سهم شپلی"]:.1f}%"></i><b>{r["سهم شپلی"]:.0f}٪</b></span>'
                    f'<span class="js-sole" title="{html.escape(_t("خانه با تنها یک منبع", lang), quote=True)}">'
                    f'{I.icon("alert", 14)}{int(r["خانه با تنها یک منبع"]):,}</span></div>')
    return f'<div class="js">{"".join(rows)}</div>'


def fingerprint_view(j: Journey, lang: str, top: int = 8) -> str:
    if j.variants.empty:
        return ""
    out = []
    for _, r in j.variants.head(top).iterrows():
        fp = set(r["_FP"])
        dots = "".join(f'<span class="jd {"s-dated" if c in fp else "s-none"}" title="{_e(FA_OF[c], lang)}"></span>'
                       for c in CODES[1:])
        out.append(f'<div class="jv-r"><span class="jv-d">{dots}</span><b>{int(r["شمار"]):,}</b></div>')
    head = "".join(f'<span class="jv-h" title="{_e(FA_OF[c], lang)}">{I.icon(ICON_OF[c], 14)}</span>'
                   for c in CODES[1:])
    return f'<div class="jv"><div class="jv-r jv-head"><span class="jv-d">{head}</span><b></b></div>{"".join(out)}</div>'


def matrix(j: Journey, lang: str, frame: Optional[pd.DataFrame], attrs: Callable[[Any], str],
           crit_yes: str, max_rows: int = 600) -> str:
    """یک ردیف برای هر بارنامه: نقطه هر ایستگاه، ایستگاه فعلی و بعدی، ادعای کارشناس و روز در ایستگاه."""
    rows = j.rows if frame is None else frame
    if rows.empty:
        return ""
    order = rows.assign(_P=rows["_CUR"].map(lambda c: IDX.get(c, -1))).sort_values(
        ["_P", "روز در ایستگاه"], ascending=[True, False], na_position="last")
    head = ('<th></th><th>' + _e("بارنامه", lang) + "</th>"
            + "".join(f'<th class="jc" title="{_e(FA_OF[c], lang)}">{I.icon(ICON_OF[c], 16)}</th>' for c in CODES)
            + f'<th>{I.icon("clock", 16)}</th><th>{I.icon("flow", 16)}</th>')
    body = []
    for _, r in order.head(max_rows).iterrows():
        bl = r["بارنامه"]
        cells = "".join(f'<td class="jc">{_dot(r["_CELLS"][c], c, r["_CUR"], r["_NEXT"], r["_REV"], r["_CLAIMS"], lang)}</td>'
                        for c in CODES)
        days = r["روز در ایستگاه"]
        dtxt = "" if days is None or pd.isna(days) else f"{int(days):,}"
        bar = (f'<span class="jdays"><i style="width:{min(100, int(days) / 1.8):.0f}%"></i><b>{dtxt}</b></span>'
               if dtxt else '<span class="gx-na">—</span>')
        nxt = (f'<span title="{_e(FA_OF[r["_NEXT"]], lang)}">{I.icon(ICON_OF[r["_NEXT"]], 16)}</span>'
               if r["_NEXT"] else '<span class="gx-na">—</span>')
        mark = '<span class="jcrit"></span>' if r["_CRIT"] == crit_yes else ""
        d = html.escape(X.s(r["_FILTER_DATE"]), quote=True)
        body.append(f'<tr data-d="{d}" data-cur="{html.escape(r["_CUR"] or "START")}"{attrs(r)}><td>{mark}</td>'
                    f'<td><b class="gx-key">{html.escape(bl)}</b></td>{cells}<td>{bar}</td><td>{nxt}</td></tr>')
    whole = ' data-whole="1"' if len(order) <= max_rows else ""
    return (f'<div class="gx-tbl sc-filterable j-mx" data-key="journey"{whole}><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def css() -> str:
    teal, ink, sunk, mut = T.TEAL_PALETTE, T.TEAL_INK, T.SURFACE_SUNKEN, T.TEXT_MUTED
    crit, warn = T.STATUS["critical"], T.STATUS["warning"]
    return f"""
.jm{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:6px;margin:8px 0 14px;position:relative;padding:6px 4px 2px}}
.jm-s{{flex:1 1 72px;display:flex;flex-direction:column;align-items:center;gap:4px;position:relative;min-width:64px}}
.jm-s:not(:last-child)::after{{content:"";position:absolute;bottom:31px;inset-inline-start:calc(50% + 12px);width:calc(100% - 18px);
  height:3px;border-radius:3px;background:{teal[1]}}}
.jm-b{{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:{ink};color:{T.SURFACE_RAISED};
  box-shadow:{T.ELEVATION['raised']}}}
.jm-b .mi-kpi-val{{font-size:13px;font-weight:800;color:inherit}}
.jm-b.is-zero{{background:{sunk};color:{mut}}}
.jm-i{{color:{ink};display:inline-flex}} .jm-l{{font-size:11px;font-weight:700;color:{T.TEXT_SECONDARY};white-space:nowrap}}
.jd{{display:inline-block;width:14px;height:14px;border-radius:50%;box-sizing:border-box;vertical-align:middle;position:relative}}
.jd.s-dated{{background:{ink}}}
.jd.s-partial{{background:linear-gradient(90deg,{ink} 50%,{sunk} 50%);border:2px solid {ink}}}
.jd.s-undated{{background:{teal[2]}}}
.jd.s-implied{{border:2px solid {teal[3]};background:transparent}}
.jd.s-conflict{{background:repeating-linear-gradient(45deg,{warn.fill} 0 3px,{T.SURFACE_RAISED} 3px 6px);border:2px solid {warn.ink}}}
.jd.s-none{{border:2px dotted {T.BORDER};background:transparent}}
.jd.s-unattributed{{border:2px dashed {mut};background:transparent}}
.jd.is-cur{{box-shadow:0 0 0 3px {teal[0]},0 0 0 5px {ink}}}
.jd.is-next{{border:2px dashed {ink}}}
.jd.is-rev{{outline:2px solid {crit.fill};outline-offset:2px}}
.jd.has-x::after{{content:"";position:absolute;top:-7px;inset-inline-end:-6px;width:7px;height:7px;transform:rotate(45deg);
  background:{warn.fill};border:1px solid {warn.ink}}}
.j-mx td.jc,.j-mx th.jc{{text-align:center;padding-inline:4px}}
.jcrit{{display:inline-block;width:8px;height:8px;border-radius:50%;background:{crit.fill}}}
.jdays{{display:inline-flex;align-items:center;gap:6px;min-width:90px}}
.jdays i{{display:block;height:6px;border-radius:4px;background:{teal[4]};min-width:3px}}
.jdays b{{font-variant-numeric:tabular-nums;font-size:12px}}
.j-legend{{display:flex;flex-wrap:wrap;gap:12px;margin:6px 0 10px;font-size:11px;color:{mut}}}
.j-legend .jl{{display:inline-flex;gap:6px;align-items:center}}
.jf{{display:grid;gap:6px;margin:6px 0 14px}}
.jf-r{{display:grid;grid-template-columns:minmax(100px,140px) 1fr minmax(100px,140px) 70px;gap:8px;align-items:center;font-size:12px}}
.jf-n{{display:inline-flex;gap:6px;align-items:center;color:{T.TEXT_SECONDARY};font-weight:700}}
.jf-bar{{position:relative;height:14px;border-radius:8px;background:{sunk}}}
.jf-bar i{{display:block;height:100%;border-radius:8px;background:linear-gradient(270deg,{teal[3]},{teal[7]})}}
.jf-r.is-back .jf-bar i{{background:repeating-linear-gradient(45deg,{warn.fill} 0 4px,{warn.wash} 4px 8px)}}
.jf-bar b{{position:absolute;inset-inline-end:6px;top:-1px;font-size:11px}}
.jf-d{{font-weight:800;color:{ink};font-variant-numeric:tabular-nums}} .jf-d small{{display:block;font-weight:400;font-size:10px;color:{mut}}}
.js{{display:grid;gap:6px;margin:6px 0 14px}}
.js-r{{display:grid;grid-template-columns:minmax(120px,170px) 1fr 70px;gap:8px;align-items:center;font-size:12px}}
.js-n{{font-weight:700;color:{T.TEXT_SECONDARY}}}
.js-bar{{position:relative;height:14px;border-radius:8px;background:{sunk}}}
.js-bar i{{display:block;height:100%;border-radius:8px;background:{teal[5]}}}
.js-bar b{{position:absolute;inset-inline-end:6px;top:-1px;font-size:11px}}
.js-sole{{display:inline-flex;gap:4px;align-items:center;color:{warn.ink};font-weight:800}}
.jv{{display:grid;gap:4px;margin:6px 0 14px}}
.j-notes summary{{cursor:pointer;color:{mut};list-style:none;display:inline-flex}}
.jv-r{{display:flex;gap:10px;align-items:center;font-size:12px}}
.jv-d{{display:inline-flex;gap:8px}} .jv-h{{display:inline-flex;width:14px;justify-content:center;color:{ink}}}
"""
