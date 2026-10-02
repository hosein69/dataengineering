# -*- coding: utf-8 -*-
"""مرحله ۴۱ — تحویل هر سفارش × متریال از شیت GR فایل SAP، و «نقص داده» هر ردیف.

## چرا

قاعده مالک (۱۴۰۵/۰۷): هر ردیف فایل کارشناسان باید در همه گزارش‌ها بیاید، حتی
اگر متریالش در Oracle نباشد. چنین ردیفی موجودی و نیاز روزانه ندارد، پس وضعیت
بحرانی‌اش «نامشخص» است و **ممکن است بحرانی باشد**؛ باید دیده شود و گفته شود داده
کدام فایل کم است. تحویل هر سفارش از SAP (شیت GR) خوانده می‌شود.

## زنجیره اتصال (فقط تطبیق دقیق؛ هیچ fuzzy join)

    فایل کارشناسان: سفارش × متریال × PR × قلم PR   (moghavemat/order_material_pr_item)
        → SAP شیت po: همان PR و همان قلم PR  (اگر قلم PR خالی بود: همان PR و همان متریال)
        → SAP شیت GR: همان PO و همان قلم PO

## حساب حرکت‌ها (نوع حرکت SAP)

    تحویل‌شده به انبار = 101 − 102 + 105 − 106 − 122 + 123
    در انبار بلوکه/QC    = 103 − 104 − 105 + 106
    برگشت به فروشنده    = 122 − 123

103 و 105 یک کالا هستند (ورود به بلوکه، بعد آزادسازی)؛ جمع ساده مقدار علامت‌دار
آن را دو بار می‌شمرد. نوع حرکت ناشناخته در هیچ جمعی نمی‌آید و شمارش می‌شود.

## نیاز روزانه

GR فقط رسید کالا دارد (ورود، آزادسازی، برگشت)، نه مصرف؛ پس نیاز روزانه از آن
ساخته نمی‌شود. نیاز روزانه فقط از Oracle است و اگر نبود، «نقص داده» همان را می‌گوید.

## دانه

همه ستون‌های این مرحله در دانه **سفارش × متریال** هستند. اگر یک قلم PO به دو
سفارش × متریال برسد (PR مشترک)، مقدار قابل تقسیم نیست: روی هر دو ردیف می‌ماند و
``GR_DLV_SHARED`` سفارش‌های دیگر را نام می‌برد؛ جمع زدنش روی ردیف‌ها مجاز نیست.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, GROUP_DETAIL, GROUP_MAIN,
                   PipelineContext, Stage, register)

#: وضعیت اتصال GR → برچسب فارسی
LINK_FA = {
    "LINKED": "تحویل در GR ثبت شده",
    "PO_NO_GR": "PO هست؛ هنوز GR ندارد",
    "PR_NOT_IN_PO": "PR این ردیف در شیت po نیست",
    "NO_PR": "PR در فایل کارشناسان خالی است",
    "NO_SAP_GR": "فایل SAP یا شیت GR بارگذاری نشد",
}
DELIVERED = {"101": 1, "102": -1, "105": 1, "106": -1, "122": -1, "123": 1}
BLOCKED = {"103": 1, "104": -1, "105": -1, "106": 1}
RETURNED = {"122": 1, "123": -1}

COLS = ["GR_DLV_LINK", "GR_DLV_LINK_FA", "GR_DLV_PO_LINES", "GR_DLV_DELIVERED_QTY",
        "GR_DLV_BLOCKED_QTY", "GR_DLV_RETURNED_QTY", "GR_DLV_LAST_DATE", "GR_DLV_DOCS",
        "GR_DLV_UNCLASSIFIED", "GR_DLV_SHARED", "ORACLE_HAS_MATERIAL", "DATA_GAP_FILES",
        "CRITICALITY_NOTE"]

MAYBE_CRITICAL = "نامشخص؛ ممکن است بحرانی باشد (نقص داده)"


def _s(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    t = str(v).strip()
    return "" if t.lower() in {"nan", "none", "<na>", "nat"} else t


def _item(v: Any) -> str:
    t = _s(v)
    try:
        f = float(t)
        if f.is_integer():
            t = str(int(f))
    except ValueError:
        pass
    return t.lstrip("0") or ("0" if t else "")


def _col(df: Optional[pd.DataFrame], *names: str) -> pd.Series:
    if df is None:
        return pd.Series(dtype=object)
    for n in names:
        if n in df.columns:
            return df[n].map(_s)
    return pd.Series([""] * len(df), index=df.index, dtype=object)


def _movement(v: Any) -> str:
    t = _s(v)
    return t.lstrip("0") or t


def file_label(ctx: Any, source: str, fallback: str) -> str:
    """نام فایل واقعی بارگذاری‌شده (``_SOURCE_FILE``)، وگرنه نام قراردادی منبع."""
    for frame in ((getattr(ctx, "sources", None) or {}).get(source) or {}).values():
        if isinstance(frame, pd.DataFrame) and "_SOURCE_FILE" in frame.columns:
            names = [n for n in dict.fromkeys(frame["_SOURCE_FILE"].map(_s)) if n]
            if names:
                return "، ".join(names[:2])
    try:
        from ..config.sources import get_source
        spec = get_source(source)
        names = spec.opt("file_names") or []
        if names:
            return str(names[0])
        if spec.opt("pattern"):
            return str(spec.opt("pattern")).strip("*").strip() + ".xlsx"
    except Exception:
        pass
    return fallback


def gr_delivery(keys: pd.DataFrame, ompi: Optional[pd.DataFrame], po: Optional[pd.DataFrame],
                gr: Optional[pd.DataFrame]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """تحویل هر (سفارش، متریال) از GR. ``keys`` ستون‌های KEY_ORDER و KEY_MATERIAL دارد.

    خروجی: (سفارش، متریال) → ستون‌های GR_DLV_*. نبود GR ← NO_SAP_GR، نه صفر."""
    pairs = list(dict.fromkeys(zip(_col(keys, "KEY_ORDER"), _col(keys, "KEY_MATERIAL"))))
    have_gr = gr is not None and not gr.empty
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # سفارش × متریال → [(PR، قلم PR)]
    prs: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    if ompi is not None and not ompi.empty:
        for o, m, pr, it in zip(_col(ompi, "KEY_ORDER"), _col(ompi, "KEY_MATERIAL"), _col(ompi, "KEY_PR"),
                                _col(ompi, "MOGH_PR_ITEM", "PR_ITEM").map(_item)):
            if o and m and pr:
                prs.setdefault((o, m), [])
                if (pr, it) not in prs[(o, m)]:
                    prs[(o, m)].append((pr, it))
    by_pr_item: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    by_pr_mat: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    if po is not None and not po.empty:
        pr_col = _col(po, "SAP_PO_PR").where(_col(po, "SAP_PO_PR").ne(""), _col(po, "KEY_PR"))
        for p_, pit, mat, ponum, poit in zip(pr_col, _col(po, "SAP_PR_ITEM").map(_item), _col(po, "KEY_MATERIAL"),
                                             _col(po, "KEY_PO"), _col(po, "SAP_PO_ITEM").map(_item)):
            if not p_ or not ponum:
                continue
            line = (ponum, poit)
            if pit:
                by_pr_item.setdefault((p_, pit), []).append(line)
            if mat:
                by_pr_mat.setdefault((p_, mat), []).append(line)
    moves: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    if have_gr:
        qty = pd.to_numeric(gr["SAP_GR_QTY"] if "SAP_GR_QTY" in gr else pd.Series(dtype=float), errors="coerce")
        date = _col(gr, "SAP_GR_POSTING_DATE_ISO", "SAP_GR_POSTING_DATE")
        doc = _col(gr, "SAP_GR_MATERIAL_DOC")
        for i, (ponum, poit, mv) in enumerate(zip(_col(gr, "KEY_PO"), _col(gr, "SAP_PO_ITEM").map(_item),
                                                  _col(gr, "SAP_GR_MOVEMENT_TYPE").map(_movement))):
            if ponum:
                q = qty.iloc[i] if i < len(qty) else float("nan")
                moves.setdefault((ponum, poit), []).append(
                    {"mv": mv, "qty": abs(float(q)) if pd.notna(q) else None,
                     "date": date.iloc[i] if len(date) else "", "doc": doc.iloc[i] if len(doc) else ""})

    lines_of: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for o, m in pairs:
        lines: List[Tuple[str, str]] = []
        for pr, it in prs.get((o, m), []):
            found = by_pr_item.get((pr, it), []) if it else []
            if not found:
                found = by_pr_mat.get((pr, m), [])
            lines += [x for x in found if x not in lines]
        lines_of[(o, m)] = lines
    users: Dict[Tuple[str, str], List[str]] = {}
    for (o, m), lines in lines_of.items():
        for line in lines:
            users.setdefault(line, [])
            if o not in users[line]:
                users[line].append(o)

    for o, m in pairs:
        rec: Dict[str, Any] = {c: None for c in COLS[:11]}
        rec.update({"GR_DLV_PO_LINES": "", "GR_DLV_LAST_DATE": "", "GR_DLV_DOCS": "", "GR_DLV_SHARED": "",
                    "GR_DLV_UNCLASSIFIED": 0})
        lines = lines_of.get((o, m), [])
        if not have_gr:
            code = "NO_SAP_GR"
        elif not prs.get((o, m)):
            code = "NO_PR"
        elif not lines:
            code = "PR_NOT_IN_PO"
        else:
            mv = [x for line in lines for x in moves.get(line, [])]
            code = "LINKED" if mv else "PO_NO_GR"
            if mv:
                def total(table: Dict[str, int]) -> Optional[float]:
                    hits = [table[x["mv"]] * x["qty"] for x in mv if x["mv"] in table and x["qty"] is not None]
                    return float(sum(hits)) if hits else 0.0
                rec["GR_DLV_DELIVERED_QTY"] = total(DELIVERED)
                rec["GR_DLV_BLOCKED_QTY"] = total(BLOCKED)
                rec["GR_DLV_RETURNED_QTY"] = total(RETURNED)
                known = set(DELIVERED) | set(BLOCKED)
                rec["GR_DLV_UNCLASSIFIED"] = sum(1 for x in mv if x["mv"] not in known or x["qty"] is None)
                dates = sorted(d for d in (x["date"] for x in mv) if d)
                rec["GR_DLV_LAST_DATE"] = dates[-1] if dates else ""
                rec["GR_DLV_DOCS"] = "، ".join(dict.fromkeys(x["doc"] for x in mv if x["doc"]))
        rec["GR_DLV_LINK"] = code
        rec["GR_DLV_LINK_FA"] = LINK_FA[code]
        rec["GR_DLV_PO_LINES"] = "، ".join(f"{p}/{i}" if i else p for p, i in lines)
        shared = [x for line in lines for x in users.get(line, []) if x != o]
        rec["GR_DLV_SHARED"] = "، ".join(dict.fromkeys(shared))
        out[(o, m)] = rec
    return out


def data_gaps(row: Dict[str, Any], oracle_has: bool, files: Dict[str, str]) -> str:
    """متن «نقص داده» یک ردیف: کدام داده در کدام فایل نیست. خالی یعنی نقصی دیده نشد."""
    gaps: List[str] = []
    ora, sap, exp = files["oracle"], files["sap"], files["moghavemat"]
    if not oracle_has:
        gaps.append(f"{ora}: متریال نیست (موجودی ایران‌خودرو/ساپکو و نیاز روزانه نامعلوم)")
    else:
        need = pd.to_numeric(pd.Series([row.get("DAILY_NEED")]), errors="coerce").iloc[0]
        if pd.isna(need):
            gaps.append(f"{ora}: نیاز روزانه خالی است")
        stock = [row.get("STOCK_IKCO"), row.get("STOCK_SAPCO")]
        if all(pd.isna(pd.to_numeric(pd.Series([x]), errors="coerce").iloc[0]) for x in stock):
            gaps.append(f"{ora}: موجودی ایران‌خودرو و ساپکو خالی است")
    link = row.get("GR_DLV_LINK")
    if link == "NO_SAP_GR":
        gaps.append(f"{sap}: شیت GR بارگذاری نشد (تحویل نامعلوم)")
    elif link == "NO_PR":
        gaps.append(f"{exp}: PR خالی است (اتصال به SAP ممکن نیست)")
    elif link == "PR_NOT_IN_PO":
        gaps.append(f"{sap}: PR این ردیف در شیت po نیست (تحویل نامعلوم)")
    return " | ".join(gaps)


#: R10 (مالک، ۱۴۰۵/۰۷/۰۸): پارت‌های فایل کارشناسان برای گزارش حمل و ترخیص، حتی بی‌بارنامه.
SHIPMENT_COLS = {
    "KEY_ORDER": "KEY_ORDER", "KEY_MATERIAL": "KEY_MATERIAL", "MATERIAL_DESC": "MOGH_MATERIAL_DESC",
    "PART_NO": "MOGH_PART_NO_PARTIAL", "PART_STATE": "MOGH_PART_STATE", "PART_STATE_FA": "MOGH_PART_STATE_FA",
    "ORDER_STATUS_RAW": "MOGH_ORDER_STATUS", "QTY_IN_PART": "MOGH_QTY_IN_PART", "CLEARED_QTY": "MOGH_CLEARED_QTY",
    "UOM": "MOGH_UOM", "BL": "MOGH_BL_NO", "BL_SUSPECT": "MOGH_BL_SUSPECT", "MODE": "MOGH_TRANSPORT_MODE",
    "TRANSPORT_NO": "MOGH_TRANSPORT_NO", "CARRIER": "MOGH_CARRIER", "SCHEDULED_SHIP": "MOGH_SCHEDULED_SHIP",
    "PO_SENT_DATE": "MOGH_PO_SENT_DATE", "STAGE_FA": "MOGH_STAGE_FA", "LOGISTICS_NOTE": "MOGH_LOGISTICS_NOTE",
    "ROW_NO": "MOGH_ROW_NO",
}


def expert_shipments(lines: Optional[pd.DataFrame], df: pd.DataFrame) -> pd.DataFrame:
    """یک ردیف برای هر ردیف پارت فایل کارشناسان (همان دانه فایل)، با سطح بحرانی، کارشناس و نقص داده
    همان سفارش × متریال از مارت. ردیف بی‌بارنامه هم می‌ماند؛ هیچ مقداری ساخته یا جمع نمی‌شود."""
    if lines is None or not isinstance(lines, pd.DataFrame) or lines.empty:
        return pd.DataFrame(columns=list(SHIPMENT_COLS) + ["CRIT_CODE", "EXPERT", "DATA_GAP_FILES"])
    out = pd.DataFrame({k: (lines[c].map(_s) if c in lines.columns and k not in ("QTY_IN_PART", "CLEARED_QTY")
                            else pd.to_numeric(lines[c], errors="coerce") if c in lines.columns else None)
                        for k, c in SHIPMENT_COLS.items()}).reset_index(drop=True)
    pairs = pd.DataFrame({"o": _col(df, "KEY_ORDER"), "m": _col(df, "KEY_MATERIAL"),
                          "c": _col(df, "کد طبقه بحرانی"), "e": _col(df, "CANONICAL_EXPERT"),
                          "g": _col(df, "DATA_GAP_FILES")}).drop_duplicates(subset=["o", "m"])
    look = {(o, m): (c, e, g) for o, m, c, e, g in pairs.itertuples(index=False)}
    info = [look.get((o, m), ("", "", "")) for o, m in zip(out["KEY_ORDER"], out["KEY_MATERIAL"])]
    out["CRIT_CODE"] = [i[0] for i in info]
    out["EXPERT"] = [i[1] for i in info]
    out["DATA_GAP_FILES"] = [i[2] for i in info]
    return out


@register
class SapGrDeliveryStage(Stage):
    name = "sap_gr_delivery"
    title = "تحویل هر سفارش × متریال از SAP GR و نقص داده هر ردیف"
    order = 41
    tolerant = True
    requires = ["KEY_ORDER", "KEY_MATERIAL", "کد طبقه بحرانی"]
    provides = list(COLS)

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        keys = pd.DataFrame({"KEY_ORDER": _col(df, "KEY_ORDER"), "KEY_MATERIAL": _col(df, "KEY_MATERIAL")},
                            index=df.index)
        gr = ctx.sheet("sap", "goods_receipts")
        info = gr_delivery(keys, ctx.sheet("moghavemat", "order_material_pr_item"), ctx.sheet("sap", "po_items"),
                           gr if isinstance(gr, pd.DataFrame) else None)
        oracle = ctx.sheet("oracle", "main")
        oracle_mats = set(_col(oracle, "KEY_MATERIAL")) - {""} if isinstance(oracle, pd.DataFrame) else set()
        files = {"oracle": file_label(ctx, "oracle", "Oracle.xlsx"),
                 "sap": file_label(ctx, "sap", "GS_Full Chain.xlsx"),
                 "moghavemat": file_label(ctx, "moghavemat", "Commercial Expert Data.xlsx")}
        recs = [info.get((o, m), {}) for o, m in zip(keys["KEY_ORDER"], keys["KEY_MATERIAL"])]
        for c in COLS[:11]:
            if c == "ORACLE_HAS_MATERIAL":
                continue
            df[c] = [r.get(c) for r in recs]
        df["ORACLE_HAS_MATERIAL"] = keys["KEY_MATERIAL"].isin(oracle_mats).to_numpy()
        rows = df.to_dict("records")
        df["DATA_GAP_FILES"] = [data_gaps(r, bool(r["ORACLE_HAS_MATERIAL"]), files) for r in rows]
        unknown = _col(df, "کد طبقه بحرانی").eq("UNKNOWN")
        df["CRITICALITY_NOTE"] = [MAYBE_CRITICAL if u else "" for u in unknown]
        counts = pd.Series([r.get("GR_DLV_LINK") for r in recs]).value_counts().to_dict()
        log.info(f"📦 [GR] تحویل سفارش × متریال از {files['sap']}: {counts}؛ "
                 f"بدون Oracle={int((~df['ORACLE_HAS_MATERIAL']).sum())}، "
                 f"وضعیت بحرانی نامشخص={int(unknown.sum())} ردیف (در گزارش‌ها با «ممکن است بحرانی» می‌آیند)")
        ctx.extras["gr_delivery_files"] = files
        ctx.extras["expert_shipments"] = expert_shipments(ctx.sheet("moghavemat", "lines"), df)
        return df

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("CRITICALITY_NOTE", "هشدار وضعیت بحرانی", 26, GROUP_MAIN, order=58),
            ColumnSpec("DATA_GAP_FILES", "نقص داده (کدام فایل)", 44, GROUP_MAIN, wrap=True, order=59),
            ColumnSpec("GR_DLV_LINK_FA", "وضعیت تحویل SAP GR", 22, GROUP_DETAIL, order=72),
            ColumnSpec("GR_DLV_DELIVERED_QTY", "تحویل‌شده به انبار (GR)", 16, GROUP_DETAIL, fmt=FMT_DECIMAL,
                       order=73),
            ColumnSpec("GR_DLV_BLOCKED_QTY", "در انبار بلوکه/QC (GR)", 16, GROUP_DETAIL, fmt=FMT_DECIMAL, order=74),
            ColumnSpec("GR_DLV_LAST_DATE", "آخرین تاریخ GR", 14, GROUP_DETAIL, order=75),
            ColumnSpec("GR_DLV_PO_LINES", "PO/قلم (SAP)", 20, GROUP_ANALYTIC, order=98),
            ColumnSpec("GR_DLV_SHARED", "قلم PO مشترک با سفارش", 18, GROUP_ANALYTIC, order=99),
        ]
