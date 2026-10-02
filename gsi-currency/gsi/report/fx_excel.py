# -*- coding: utf-8 -*-
"""سه خروجی Excel چرخه ارز: ریز مالی ثبت سفارش، پرونده‌ها به تفکیک مرحله، اقلام بحرانی.

هر سه از مدل مشترک :mod:`gsi.report.fx_insight` ساخته می‌شوند، پس همان عددی را
دارند که Studio و HTML نشان می‌دهند. قواعد:

* هر شیت یک دانه دارد و مبلغ فقط در دانه خودش است؛ جمع زدن ستون مبلغ هیچ
  شیتی چندبار شمردن نمی‌سازد. جمع‌ها همیشه به تفکیک ارزند.
* نامعلوم خانه خالی است، نه صفر.
* شیت «سلسله‌مراتب» با گروه‌بندی سطرهای Excel ساخته شده: مرحله ← ثبت سفارش ←
  سفارش ← متریال (و بارنامه). با دکمه‌های ۱ تا ۴ کنار سطرها سطح دلخواه باز یا
  بسته می‌شود.
* راست‌چین (نسخه انگلیسی چپ‌به‌راست)، سرستون فیروزه‌ای، فونت سازمانی
  (``tokens.FONT_EXCEL``) و عنوان ستون‌ها به زبانی که کاربر در Studio انتخاب کرده است.
"""
from __future__ import annotations

import io
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from ..core.excel_text import keep_text
from ..design import excel as dx
from ..design import tokens as T
from ..i18n import columns as C
from . import critical_board as CB
from . import fx_insight as X

SHEET_EN = {
    "خلاصه": "Summary", "خلاصه مراحل": "Stages", "ارزش به تفکیک ارز": "Value by currency",
    "ثبت سفارش‌ها": "Registrations", "سلسله‌مراتب": "Hierarchy", "سفارش‌ها": "Orders", "متریال‌ها": "Materials",
    "بارنامه‌ها": "B-Ls", "جریان پول": "Money flow", "جمع به تفکیک ارز": "Totals by currency",
    "رویدادهای مبلغی": "Money events", "مراحل چرخه": "Lifecycle", "تصمیم‌های مالی": "Financial decisions",
    "صف تخصیص": "Allocation queue", "بحرانی به تفکیک مرحله": "Critical by stage",
    "سلسله‌مراتب بحرانی": "Critical hierarchy", "متریال‌های بحرانی": "Critical materials",
    "بارنامه‌های بحرانی": "Critical B-Ls", "ماتریس مرحله × سطح": "Stage x level",
}
#: ستون‌هایی که با رنگ وضعیت نمایش داده می‌شوند
_STATUS_COLS = {"سطح بحرانی": "level", "بدترین سطح بحرانی": "level", "سطح": "level",
                "وضعیت مرحله": "stage", "وضعیت پیوند": "link", "وضعیت تطبیق": "recon", "ترخیص": "clear",
                "وضعیت ترخیص": "clear"}
_AMOUNT_WORDS = ("ارزش", "مبلغ", "مانده", "حمل‌شده", "تعهد", "رفع‌شده", "پرداخت", "خرید ارز", "تخصیص", "درخواست تخصیص")
_LEVEL_BY_LABEL = {v[1]: k for k, v in CB.LEVELS.items()}


def _tone(kind: str, value: Any) -> str:
    v = X.s(value)
    if not v:
        return ""
    if kind == "level":
        code = v if v in CB.LEVELS else _LEVEL_BY_LABEL.get(v, "")
        return CB.LEVELS[code][0] if code else ""
    if kind == "stage":
        return X.STATUS_TONE.get(v, "")
    if kind == "link":
        return X.LINK_TONE.get(v, "")
    if kind == "recon":
        return {"هم‌خوان": "good", "شکاف شاهد": "warning", "مغایرت": "critical"}.get(v, "unknown")
    if kind == "clear":
        return X.CLEAR_TONE.get(v, "")
    return ""


def _clean(v: Any) -> Any:
    """NaN/NaT ← خانه خالی؛ نامعلوم هرگز صفر نمی‌شود."""
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return v.item()
        except Exception:
            return v
    return v


def _fmt_for(col: str, values: List[Any]) -> Optional[str]:
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    if "(٪)" in col or col.endswith("٪"):
        return dx.NUM_PCT
    if any(w in col for w in _AMOUNT_WORDS) or "PI" in col:
        return dx.NUM_CURRENCY
    if all(float(v).is_integer() for v in nums):
        return dx.NUM_INT
    return dx.NUM_CURRENCY


#: ستون‌هایی که متن خود برنامه را دارند: نام رویداد پول، معنا و علت تصمیم مالی، اقدام
#: پیشنهادی و بعدی، شاهد مرحله و علت بحرانی. مقدار منبعی که معادل ندارد همان می‌ماند.
_PROGRAM_TEXT_COLS = frozenset({
    "رویداد", "یادداشت", "معنای مبلغ", "علت احتمالی", "مالک فرایند", "اقدام پیشنهادی", "شاهد لازم",
    "اقدام بعدی", "مرحله چرخه ارز", "علت", "شاهد",
})
_ENUM_COLS = X.ENUM_COLS | _PROGRAM_TEXT_COLS


def _localize(col: str, v: Any, lang: str) -> Any:
    """حالت انگلیسی: برچسب رابط (مرحله، سطح، وضعیت) و متن خود برنامه ترجمه می‌شود و فهرست
    کدها ویرگول لاتین می‌گیرد. داده (نام کالا، کارشناس، متن آزاد) دست نمی‌خورد."""
    if lang != C.EN or not isinstance(v, str):
        return v
    if col in _ENUM_COLS:
        return X.tr(v, lang)
    if "، " in v and not C.is_persian(v.replace("، ", "")):
        return v.replace("، ", ", ")
    return v


def _title(name: str, lang: str) -> str:
    t = SHEET_EN.get(name, X.tr(name, C.EN)) if lang == C.EN else name
    for ch in '[]:*?/\\':
        t = t.replace(ch, "-")
    return t[:31]


def _header_cells(ws, row: int, labels: List[str]) -> None:
    for j, lab in enumerate(labels, 1):
        c = ws.cell(row=row, column=j, value=lab)
        c.font = dx.font(size=dx.SIZE_BODY, bold=True, color=T.TEXT_ON_BRAND)
        c.fill = dx.fill(T.BRAND_TEAL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = dx.border(T.TEAL_INK)
    ws.row_dimensions[row].height = 30


def _side(lang: str, v: Any = None) -> str:
    """فارسی: شیت راست‌به‌چپ و همه‌چیز راست‌چین؛ انگلیسی: شیت چپ‌به‌راست، متن چپ و عدد راست."""
    if lang == C.EN and not (isinstance(v, (int, float)) and not isinstance(v, bool)):
        return "left"
    return "right"


def _banner(ws, title: str, note: str, width: int, lang: str = C.FA) -> int:
    """دو سطر بالای شیت: عنوان و توضیح. شماره سطر سرستون را برمی‌گرداند."""
    width = max(width, 4)
    ws.sheet_view.rightToLeft = lang != C.EN
    ws.cell(row=1, column=1, value=title)
    dx.apply(ws.cell(row=1, column=1), dx.title_style())
    ws.cell(row=1, column=1).alignment = dx.align(_side(lang))
    for j in range(2, width + 1):
        ws.cell(row=1, column=j).fill = dx.fill(T.BRAND_NAVY)
    ws.row_dimensions[1].height = 28
    if note:
        c = ws.cell(row=2, column=1, value=note)
        c.font = dx.font(size=dx.SIZE_SMALL, color=T.TEXT_SECONDARY, italic=True)
        c.alignment = Alignment(horizontal=_side(lang), vertical="center", wrap_text=False)
        return 4
    return 3


def _widths(ws, frame_cols: List[str], rows: List[List[Any]], start_col: int = 1) -> None:
    for j, col in enumerate(frame_cols, start_col):
        vals = [len(str(col))] + [len(str(r[j - start_col])) for r in rows[:200] if r[j - start_col] is not None]
        ws.column_dimensions[get_column_letter(j)].width = min(max(max(vals) + 3, 10), 44)


def add_frame(wb: Workbook, name: str, frame: pd.DataFrame, lang: str = C.FA, title: str = "", note: str = "") -> None:
    """یک DataFrame را با سبک مشترک به شیت تازه تبدیل می‌کند (راست‌چین، فیلتر، سطر ثابت)."""
    ws = wb.create_sheet(_title(name, lang))
    frame = frame if frame is not None else pd.DataFrame()
    cols = [str(c) for c in frame.columns]
    labels = [X.tr(c, lang) for c in cols]
    head = _banner(ws, X.tr(title, lang) or (SHEET_EN.get(name, name) if lang == C.EN else name), X.tr(note, lang),
                   len(cols), lang)
    if not cols:
        ws.cell(row=head, column=1, value="—")
        return
    _header_cells(ws, head, labels)
    rows = [[_clean(v) for v in r] for r in frame.itertuples(index=False, name=None)]
    if lang == C.EN:  # نام مرحله، سطح و وضعیت‌ها برچسب رابط‌اند، نه داده
        rows = [[_localize(c, v, lang) for c, v in zip(cols, r)] for r in rows]
    fmts = [_fmt_for(c, [r[j] for r in rows]) for j, c in enumerate(cols)]
    kinds = [_STATUS_COLS.get(c) for c in cols]
    for i, r in enumerate(rows, head + 1):
        zebra = dx.zebra_fill(i)
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = dx.font(size=dx.SIZE_SMALL + 0)
            c.alignment = Alignment(horizontal=_side(lang, v), vertical="center", wrap_text=isinstance(v, str) and len(v) > 40)
            if fmts[j - 1] and isinstance(v, (int, float)) and not isinstance(v, bool):
                c.number_format = fmts[j - 1]
            tone = _tone(kinds[j - 1], v) if kinds[j - 1] else ""
            if tone and tone in T.STATUS:
                dx.apply(c, dx.status_style(tone))
            elif zebra is not None:
                c.fill = zebra
    if not rows:
        ws.cell(row=head + 1, column=1, value="—")
    last = head + max(len(rows), 1)
    ws.auto_filter.ref = f"A{head}:{get_column_letter(len(cols))}{last}"
    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    _widths(ws, labels, rows)


def add_key_values(wb: Workbook, name: str, pairs: List[tuple], lang: str = C.FA, title: str = "", note: str = "") -> None:
    """شیت «فیلد | مقدار» برای خلاصه یک ثبت سفارش."""
    ws = wb.create_sheet(_title(name, lang))
    head = _banner(ws, X.tr(title or name, lang), X.tr(note, lang), 2, lang)
    _header_cells(ws, head, [C.label("فیلد", lang) if lang == C.EN else "فیلد",
                             C.label("مقدار", lang) if lang == C.EN else "مقدار"])
    for i, (k, v) in enumerate(pairs, head + 1):
        a = ws.cell(row=i, column=1, value=X.tr(k, lang))
        a.font = dx.font(bold=True, color=T.TEXT_SECONDARY)
        a.fill = dx.fill(T.SURFACE_SUNKEN)
        b = ws.cell(row=i, column=2, value=_localize(k, _clean(v), lang))
        b.font = dx.font()
        b.alignment = Alignment(horizontal=_side(lang, _clean(v)), vertical="center", wrap_text=True)
        if isinstance(_clean(v), (int, float)) and not isinstance(v, bool):
            b.number_format = _fmt_for(k, [_clean(v)]) or dx.NUM_CURRENCY
        tone = _tone(_STATUS_COLS.get(k, ""), v) if _STATUS_COLS.get(k) else ""
        if tone in T.STATUS:
            dx.apply(b, dx.status_style(tone))
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 70


# ═══════════════════════════ سلسله‌مراتب ═══════════════════════════
HIER_COLS = ["سطح", "مرحله", "ثبت سفارش", "سفارش", "متریال / بارنامه", "شرح / وضعیت", "روز در مرحله", "مبلغ", "ارز",
             "حمل‌شده (٪)", "سطح بحرانی", "مقاومت (روز)", "کجاست"]
_KIND_FA = {"stage": "مرحله", "reg": "ثبت سفارش", "order": "سفارش", "mat": "متریال", "bl": "بارنامه"}


def hierarchy_rows(fx: X.FxData, stages: Optional[Sequence[str]] = None, critical_only: bool = False,
                   levels: Sequence[str] = CB.DEFAULT_LEVELS) -> List[tuple]:
    """(سطح گروه، نوع، ردیف) — هر مبلغ فقط روی ردیف دانه خودش."""
    out: List[tuple] = []
    for st in X.explorer(fx, critical_only=critical_only, levels=levels):
        if stages is not None and st["code"] not in stages:
            continue
        if not st["count"]:
            continue
        out.append((0, "stage", {"سطح": "مرحله", "مرحله": st["label"],
                                 "شرح / وضعیت": f'{st["count"]:,} ثبت سفارش', "_count": st["count"]}))
        for r in st["regs"]:
            out.append((1, "reg", {"سطح": "ثبت سفارش", "مرحله": st["label"], "ثبت سفارش": r.get("KEY_REG"),
                                   "شرح / وضعیت": r.get("STAGE_STATUS"), "روز در مرحله": X.n(r.get("STAGE_DAYS")),
                                   "مبلغ": X.n(r.get("REG_VALUE")), "ارز": r.get("REG_CURRENCY"),
                                   "حمل‌شده (٪)": X.n(r.get("SHIPPED_PCT")), "سطح بحرانی": r.get("CRITICAL_LEVEL_FA")}))
            for o in r["orders"]:
                out.append((2, "order", {"سطح": "سفارش", "مرحله": st["label"], "ثبت سفارش": r.get("KEY_REG"),
                                         "سفارش": o["key"], "شرح / وضعیت": o["status"], "مبلغ": o["pi_value"],
                                         "ارز": o["pi_currency"], "سطح بحرانی": o["level_fa"]}))
                for m in o["materials"]:
                    out.append((3, "mat", {"سطح": "متریال", "مرحله": st["label"], "ثبت سفارش": r.get("KEY_REG"),
                                           "سفارش": o["key"], "متریال / بارنامه": m["key"], "شرح / وضعیت": m["desc"],
                                           "سطح بحرانی": m["level_fa"], "مقاومت (روز)": m["resistance"],
                                           "کجاست": m["where"]}))
            if not critical_only:
                for b in r["bls"]:
                    out.append((2, "bl", {"سطح": "بارنامه", "مرحله": st["label"], "ثبت سفارش": r.get("KEY_REG"),
                                          "متریال / بارنامه": b["key"], "شرح / وضعیت": b["status"], "مبلغ": b["value"],
                                          "ارز": b["currency"], "حمل‌شده (٪)": b["share_pct"],
                                          "سطح بحرانی": b["level_fa"], "کجاست": b["where"]}))
    return out


def add_hierarchy(wb: Workbook, fx: X.FxData, lang: str = C.FA, stages: Optional[Sequence[str]] = None,
                  critical_only: bool = False, levels: Sequence[str] = CB.DEFAULT_LEVELS,
                  name: str = "سلسله‌مراتب") -> None:
    ws = wb.create_sheet(_title(name, lang))
    ws.sheet_properties.outlinePr.summaryBelow = False
    note = ("دکمه‌های ۱ تا ۴ کنار سطرها سطح را باز یا بسته می‌کنند. مبلغ هر سطر فقط مال همان سطر است "
            "(ثبت سفارش: ارزش ثبت سفارش، سفارش: ارزش PI، بارنامه: ارزش فاکتور)؛ جمع ستون مبلغ معنا ندارد.")
    head = _banner(ws, X.tr(name, lang), X.tr(note, lang), len(HIER_COLS), lang)
    labels = [X.tr(c, lang) for c in HIER_COLS]
    _header_cells(ws, head, labels)
    rows = hierarchy_rows(fx, stages, critical_only, levels)
    matrix = []
    fills = {0: dx.fill(T.TEAL_WASH), 1: dx.fill(T.SURFACE_SUNKEN)}
    for i, (lvl, kind, rec) in enumerate(rows, head + 1):
        vals = [_clean(rec.get(c)) for c in HIER_COLS]
        if lang == C.EN:
            vals = [_localize(c, v, lang) for c, v in zip(HIER_COLS, vals)]
            desc = HIER_COLS.index("شرح / وضعیت")
            if kind == "stage":
                vals[desc] = f'Registrations: {rec.get("_count", 0):,}'
            elif kind != "mat":  # شرح متریال داده است؛ بقیه وضعیت‌اند
                vals[desc] = X.tr(vals[desc], lang) if isinstance(vals[desc], str) else vals[desc]
        matrix.append(vals)
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = dx.font(size=dx.SIZE_SMALL, bold=lvl <= 1, color=T.TEAL_INK if lvl == 0 else T.TEXT)
            c.alignment = Alignment(horizontal=_side(lang, v), vertical="center", indent=lvl if j <= 5 else 0)
            if lvl in fills:
                c.fill = fills[lvl]
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                c.number_format = dx.NUM_PCT if "٪" in HIER_COLS[j - 1] else (
                    dx.NUM_CURRENCY if HIER_COLS[j - 1] == "مبلغ" else dx.NUM_INT)
        tone = _tone("level", rec.get("سطح بحرانی"))
        if tone in T.STATUS:
            dx.apply(ws.cell(row=i, column=HIER_COLS.index("سطح بحرانی") + 1), dx.status_style(tone))
        if lvl:
            ws.row_dimensions[i].outline_level = lvl
    if not rows:
        ws.cell(row=head + 1, column=1, value="—")
    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    _widths(ws, labels, matrix or [[None] * len(HIER_COLS)])


# ═══════════════════════════ کتاب‌ها ═══════════════════════════
def _book() -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    return wb


def _bytes(wb: Workbook) -> bytes:
    keep_text(wb)                      # متن منبع «=…» (شرح کالا، شماره سفارش) فرمول نشود
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _regs_in(fx: X.FxData, stages: Optional[Sequence[str]]) -> List[str]:
    t = fx.reg_table
    if stages is not None:
        t = t[t["STAGE_CODE"].isin(stages)]
    return t["KEY_REG"].tolist()


PRINCIPLES = ("قواعد: نامعلوم خانه خالی است، نه صفر · جمع فقط داخل یک ارز · هر مبلغ فقط در دانه خودش "
              "(ثبت سفارش، سفارش، بارنامه) و روی ردیف متریال تکرار نمی‌شود.")


def _stage_summary_fa(fx: X.FxData, stages: Optional[Sequence[str]], critical_only: bool = False,
                      levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    s = X.stage_summary(fx, critical_only, levels)
    if stages is not None:
        s = s[s["STAGE_CODE"].isin(stages)]
    return s.rename(columns={"STAGE": "مرحله", "REGISTRATIONS": "ثبت سفارش", "SHARE_PCT": "سهم (٪)",
                             "DAYS_MEDIAN": "میانه روز در مرحله", "DAYS_MAX": "بیشترین روز در مرحله",
                             "OVERDUE": "سررسید گذشته", "WITH_GAPS": "با گام بدون شاهد",
                             "CRITICAL_REGS": "ثبت سفارش با متریال بحرانی", "CRITICAL_MATERIALS": "متریال بحرانی",
                             "ORDERS": "سفارش", "BLS": "بارنامه"}).drop(columns=["STAGE_CODE"])


def _stage_values_fa(fx: X.FxData, stages: Optional[Sequence[str]], critical_only: bool = False,
                     levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    v = X.stage_values(fx, critical_only, levels)
    if stages is not None:
        v = v[v["STAGE_CODE"].isin(stages)]
    return v.rename(columns={"STAGE": "مرحله", "CURRENCY": "ارز", "REGISTRATIONS": "ثبت سفارش",
                             "REG_VALUE": "ارزش ثبت سفارش", "UNKNOWN_VALUE_REGS": "ثبت سفارش با ارزش نامعلوم",
                             "SHIPPED_VALUE": "حمل‌شده", "UNSHIPPED_VALUE": "مانده حمل‌نشده",
                             "OVERSHIPPED_REGS": "حمل بیش از ارزش",
                             "UNSHIPPED_UPPER_BOUND_REGS": "ثبت سفارش با مانده حداکثری"}).drop(columns=["STAGE_CODE"])


def stage_workbook(fx: X.FxData, stages: Optional[Sequence[str]] = None, lang: str = C.FA) -> bytes:
    """«کدام پرونده‌ها در کدام مرحله‌اند»: خلاصه، ارزش به تفکیک ارز، ثبت سفارش‌ها، سلسله‌مراتب و دانه‌ها."""
    wb = _book()
    regs = _regs_in(fx, stages)
    label = "، ".join(X.STAGE_FA.get(c, c) for c in stages) if stages else "همه مراحل"
    title = f"پرونده‌ها به تفکیک مرحله — {label}" + (f" — {fx.ref_date}" if fx.ref_date else "")
    add_frame(wb, "خلاصه مراحل", _stage_summary_fa(fx, stages), lang, title=title, note=PRINCIPLES)
    add_frame(wb, "ارزش به تفکیک ارز", _stage_values_fa(fx, stages), lang,
              note="ارز نامعلوم ردیف جدا دارد و جمع زده نمی‌شود. «حمل بیش از ارزش» از مانده کم نمی‌شود. "
                   "مانده ثبت سفارشی که بخشی از حملش نامعلوم است حداکثر است.")
    rt = fx.reg_table[fx.reg_table["KEY_REG"].isin(regs)]
    add_frame(wb, "ثبت سفارش‌ها", X.reg_display(rt), lang)
    add_hierarchy(wb, fx, lang, stages=stages)
    add_frame(wb, "سفارش‌ها", X.orders_frame(fx, regs), lang, note="دانه سفارش؛ ارزش PI یک بار برای هر سفارش.")
    add_frame(wb, "متریال‌ها", X.materials_frame(fx, regs), lang, note="دانه سفارش × متریال؛ بدون مبلغ.")
    add_frame(wb, "بارنامه‌ها", X.bls_frame(fx, regs), lang, note="دانه بارنامه × ثبت سفارش؛ ارزش فاکتور به ارز خود بارنامه.")
    return _bytes(wb)


def _path_frame(fx: X.FxData, regs: Iterable[str]) -> pd.DataFrame:
    state_fa = {"done": "انجام شد", "current": "مرحله جاری", "gap": "بدون شاهد (پیش از مرحله جاری)", "todo": "مانده"}
    rows = [{"ثبت سفارش": r, "مرحله": p["label"], "وضعیت": p["status"], "حالت": state_fa.get(p["state"], p["state"]),
             "تاریخ/مهلت": p["date"], "شاهد": p["evidence"]} for r in regs for p in X.path(fx, r)]
    return pd.DataFrame(rows, columns=["ثبت سفارش", "مرحله", "وضعیت", "حالت", "تاریخ/مهلت", "شاهد"])


def _ledger_fa(fx: X.FxData, regs: Iterable[str]) -> pd.DataFrame:
    keep = set(regs)
    lg = X.ledger(fx)
    lg = lg[lg["KEY_REG"].map(X.s).isin(keep)]
    return lg.rename(columns={"KEY_REG": "ثبت سفارش", "EVENT_FA": "رویداد", "EVENT_DATE": "تاریخ", "AMOUNT": "مبلغ",
                              "CURRENCY": "ارز", "SOURCE": "منبع", "REFERENCE": "مرجع", "STATUS": "وضعیت",
                              "NOTE": "یادداشت"})


def _decisions_fa(fx: X.FxData, regs: Iterable[str]) -> pd.DataFrame:
    keep = set(regs)
    d = X.decisions(fx)
    d = d[d["KEY_REG"].map(X.s).isin(keep)]
    return d.rename(columns={"KEY_REG": "ثبت سفارش", "CURRENCY": "ارز", "STAGE_CODE": "مرحله",
                             "OBSERVED_GAP_AMOUNT": "مبلغ شکاف مشاهده‌شده", "AMOUNT_MEANING": "معنای مبلغ",
                             "POSSIBLE_CAUSE": "علت احتمالی", "PROCESS_OWNER": "مالک فرایند",
                             "SUGGESTED_ACTION": "اقدام پیشنهادی", "EVIDENCE_GAP": "شاهد لازم",
                             "DECISION_STATUS": "وضعیت تصمیم"})


def _queue_fa(fx: X.FxData, regs: Iterable[str]) -> pd.DataFrame:
    keep = set(regs)
    q = fx.queue
    if q.empty:
        return pd.DataFrame(columns=["ثبت سفارش"])
    q = q[q["KEY_REG"].map(X.s).isin(keep)].copy()
    q["QUEUE_STATE"] = q["QUEUE_STATE"].map(lambda v: X.QUEUE_FA.get(X.s(v), X.s(v)))
    q["CRITICAL_LEVEL"] = q["CRITICAL_LEVEL"].map(lambda v: CB.level_label(X.s(v)) if X.s(v) else "")
    names = {"KEY_REG": "ثبت سفارش", "QUEUE_STATE": "وضعیت صف", "QUEUE_RANK": "رتبه صف", "QUEUE_ENTER_DATE": "ورود به صف",
             "WAIT_DAYS": "روز انتظار", "OPEN_AMOUNT": "مبلغ باز", "CURRENCY": "ارز", "REQUESTS_OPEN": "درخواست باز",
             "REQUESTS_ALLOCATED": "تخصیص‌یافته", "REQUESTS_REJECTED": "ردشده", "ORDERS": "سفارش‌ها",
             "CRITICAL_LEVEL": "بحرانی بودن سفارش", "CRITICAL_MATERIALS": "متریال بحرانی", "EXPERT": "کارشناس"}
    return q[[c for c in names if c in q.columns]].rename(columns=names)


def registration_workbook(fx: X.FxData, regs: Optional[Sequence[str]] = None, lang: str = C.FA) -> bytes:
    """ریز مالی یک یا چند ثبت سفارش. ``regs=None`` یعنی همه (قالب بلند با ستون ثبت سفارش)."""
    wb = _book()
    regs = list(regs) if regs is not None else fx.reg_table["KEY_REG"].tolist()
    single = len(regs) == 1
    rt = fx.reg_table[fx.reg_table["KEY_REG"].isin(regs)]
    stamp = f" — {fx.ref_date}" if fx.ref_date else ""
    if single and not rt.empty:
        r = rt.iloc[0]
        pairs = [(fa, r[k]) for k, fa in X.REG_COLUMNS_FA.items() if k in r.index]
        add_key_values(wb, "خلاصه", pairs, lang, title=f"{X.tr('ریز مالی ثبت سفارش', lang)} {regs[0]}{stamp}",
                       note=PRINCIPLES)
    else:
        add_frame(wb, "خلاصه", X.reg_display(rt), lang, title=f"ریز مالی ثبت سفارش‌ها{stamp}", note=PRINCIPLES)
    money = X.money_display(fx, regs)
    add_frame(wb, "جریان پول", money, lang,
              note="هر ردیف یک ثبت سفارش در یک ارز است؛ خانه خالی یعنی شاهد نیست. حمل‌شده فقط از بارنامه‌های هم‌ارز.")
    if not single:
        raw = X.money(fx)
        raw = raw[raw["KEY_REG"].isin(regs)]
        add_frame(wb, "جمع به تفکیک ارز", X.money_totals_display(raw), lang,
                  note="جمع هر گام فقط داخل یک ارز؛ ارز نامعلوم ردیف جدا و بی‌جمع دارد؛ "
                       "ستون «بی‌شاهد» تعداد ثبت سفارش‌های بدون آن گام است.")
    add_frame(wb, "رویدادهای مبلغی", _ledger_fa(fx, regs), lang)
    add_frame(wb, "بارنامه‌ها", X.bls_frame(fx, regs), lang, note="ارزش فاکتور به ارز خود بارنامه؛ سهم از ارزش ثبت سفارش هم‌ارز.")
    add_frame(wb, "سفارش‌ها", X.orders_frame(fx, regs), lang, note="ارزش PI یک بار برای هر سفارش.")
    add_frame(wb, "متریال‌ها", X.materials_frame(fx, regs), lang, note="بدون مبلغ؛ مبلغ در دانه سفارش و بارنامه است.")
    add_frame(wb, "مراحل چرخه", _path_frame(fx, regs), lang)
    add_frame(wb, "تصمیم‌های مالی", _decisions_fa(fx, regs), lang, note="مبلغ شکاف‌ها جمع‌پذیر نیستند.")
    add_frame(wb, "صف تخصیص", _queue_fa(fx, regs), lang)
    return _bytes(wb)


def critical_workbook(fx: X.FxData, df: Optional[pd.DataFrame], levels: Sequence[str] = CB.DEFAULT_LEVELS,
                      stages: Optional[Sequence[str]] = None, lang: str = C.FA) -> bytes:
    """اقلام بحرانی با همان بینش مرحله‌ای: ماتریس مرحله × سطح، سلسله‌مراتب و تابلوی بحرانی."""
    wb = _book()
    regs = _regs_in(fx, stages)
    keep = set(regs)
    label = "، ".join(X.STAGE_FA.get(c, c) for c in stages) if stages else "همه مراحل"
    lv = "، ".join(CB.level_label(c) for c in levels)
    title = f"اقلام بحرانی به تفکیک مرحله — {label}" + (f" — {fx.ref_date}" if fx.ref_date else "")
    matrix = X.critical_by_stage(fx, levels)
    if stages is not None:
        matrix = matrix[matrix["مرحله"].isin([X.STAGE_FA.get(c, c) for c in stages])]
    note = (f"Levels: {', '.join(X.tr(CB.level_label(c), lang) for c in levels)}. Counted at order × material grain."
            if lang == C.EN else f"سطوح: {lv}. شمارش در دانه سفارش × متریال.")
    add_frame(wb, "ماتریس مرحله × سطح", matrix, lang, title=title, note=note)
    mf = X.materials_frame(fx, regs, critical_only=True, levels=levels)
    add_frame(wb, "بحرانی به تفکیک مرحله", mf, lang, note="هر ردیف یک متریال بحرانی در یک سفارش؛ مرحله از ثبت سفارش آن.")
    add_hierarchy(wb, fx, lang, stages=stages, critical_only=True, levels=levels, name="سلسله‌مراتب بحرانی")
    mats = CB.critical_materials(df, levels) if df is not None else pd.DataFrame()
    bls = CB.critical_bls(df, levels) if df is not None else pd.DataFrame()
    if stages is not None and not mats.empty:
        mats = mats[mats["ثبت سفارش‌ها"].map(lambda v: bool(set(X.s(v).split("، ")) & keep))]
    if stages is not None and not bls.empty:
        bls = bls[bls["ثبت سفارش"].map(lambda v: bool(set(X.s(v).split("، ")) & keep))]
    add_frame(wb, "متریال‌های بحرانی", mats.drop(columns=["کد سطح"], errors="ignore"), lang,
              note="یک ردیف برای هر متریال (بارنامه‌های سفارش‌های این متریال و ثبت سفارش‌ها؛ اینکه کدام بارنامه این متریال را آورده در سورس نیست).")
    add_frame(wb, "بارنامه‌های بحرانی", bls.drop(columns=["کد سطح"], errors="ignore"), lang,
              note="یک ردیف برای هر بارنامه؛ ارزش فاکتور به ارز خود بارنامه.")
    rt = fx.reg_table[fx.reg_table["KEY_REG"].isin(regs) & fx.reg_table["CRITICAL_LEVEL"].isin(levels)]
    add_frame(wb, "ثبت سفارش‌ها", X.reg_display(rt), lang, note="ثبت سفارش‌هایی که دست‌کم یک متریال بحرانی دارند.")
    return _bytes(wb)
