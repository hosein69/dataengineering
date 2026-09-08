# -*- coding: utf-8 -*-
"""شیت بینش چهارلایه و تحلیل چرخه عمر متریال.

## شیت بینش — چهار لایه با دکمه «+»

سلسله‌مراتب outline اکسل، از کل به جزء:

    لایه ۱  معاونت                    ← مدیر ارشد اینجا می‌ایستد
      لایه ۲  مدیریت                  ← مدیر میانی باز می‌کند
        لایه ۳  کارشناس               ← سرپرست باز می‌کند
          لایه ۴  محاسبات پیشرفته     ← کسی که دنبال «چرا» است

لایه چهارم عمداً پیش‌فرض بسته است: کسی که فقط عدد می‌خواهد نباید با فرمول
مواجه شود، ولی کسی که دلیل می‌خواهد باید بتواند تا ته برود بدون خروج از فایل.

هر لایه کل چرخه خرید را پوشش می‌دهد: PR → سفارش → ثبت سفارش → تخصیص →
خرید ارز → حمل → گمرک → ترخیص → رفع تعهد.

## شیت تحلیل متریال

برای هر متریال، وضعیت هر پنج حلقه زنجیره کنار هم می‌آید تا معلوم شود
حلقهٔ پاره کجاست، به‌علاوه دو نمودار پراکنش:
  • مقاومت در برابر روزهای رسوب (کدام قطعه هم بحرانی است هم گیر کرده)
  • مانده تعهد در برابر روزهای تأخیر (کجا جریمه انباشته می‌شود)
"""
from __future__ import annotations

__contract__ = 1

from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.utils import get_column_letter

from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from openpyxl.styles import Font

from .palette import LuxuryPalette as P


def _font(color: str, size: int = 11, bold: bool = False) -> Font:
    """فونت گزارش با رنگ و اندازه دلخواه (openpyxl 3.x متد copy ندارد)."""
    return Font(name="IRANSans Light", size=size, bold=bold, color=color)

SHEET_INSIGHT = "۱۲. بینش چندلایه"
SHEET_MATERIAL = "۱۳. تحلیل چرخه عمر متریال"

# ── پالت: آکوا، طیف سبز، سفید، خاکستری ──
AQUA_DEEP = "0F6E6E"     # عنوان لایه ۱
AQUA = "1E9E9E"          # لایه ۲
AQUA_SOFT = "7FC9C2"     # لایه ۳
GREEN_SOFT = "D9EDE7"    # پس‌زمینه لایه ۳
GREY_TEXT = "5A6B6B"     # لایه ۴ (محاسبات)
GREY_BG = "F2F5F5"
WHITE = "FFFFFF"

#: مراحل چرخه خرید که در هر لایه شمرده می‌شوند
LIFECYCLE = [
    ("PR", "درخواست خرید", "KEY_PR"),
    ("ORDER", "سفارش", "CANONICAL_ORDER"),
    ("REG", "ثبت سفارش", "KEY_REG"),
    ("ALLOC", "تخصیص ارز", "ALLOC_STATUS"),
    ("FX", "خرید ارز", "BUY_DATE"),
    ("BL", "بارنامه", "CANONICAL_BL"),
    ("DISCHARGE", "تخلیه", "DISCHARGE_DATE"),
    ("COTAGE", "کوتاژ", "COTAGE_NO"),
    ("CLEAR", "ترخیص", "FULL_CLEAR_DATE"),
    ("RELEASE", "رفع تعهد", "مانده تعهد"),
]


def _filled(series: pd.Series, invert: bool = False) -> int:
    """تعداد ردیف‌هایی که این مرحله را واقعاً طی کرده‌اند."""
    s = series.astype(str).str.strip()
    mask = s.ne("") & ~s.isin(["nan", "None", "0", "0.0", "NaT", "نامشخص"])
    return int((~mask).sum() if invert else mask.sum())


def _stage_counts(g: pd.DataFrame) -> List[int]:
    out = []
    for code, _, col in LIFECYCLE:
        if col not in g.columns:
            out.append(0)
        elif code == "RELEASE":
            # رفع تعهد یعنی مانده صفر شده باشد
            bal = pd.to_numeric(g[col], errors="coerce").fillna(0)
            out.append(int((bal <= 0).sum()))
        else:
            out.append(_filled(g[col]))
    return out


def _write_row(ws, r: int, level: int, label: str, counts: List[int],
               metrics: Dict[str, Any], n_cols: int) -> None:
    """یک ردیف در سلسله‌مراتب، با تورفتگی و رنگ متناسب با عمق."""
    style = {
        1: (AQUA_DEEP, WHITE, True, 12),
        2: (AQUA, WHITE, True, 11),
        3: (GREEN_SOFT, "1A3C3C", False, 11),
        4: (GREY_BG, GREY_TEXT, False, 10),
    }[level]
    bg, fg, bold, size = style
    indent = "    " * (level - 1)

    c = ws.cell(row=r, column=1, value=f"{indent}{label}")
    c.font = _font(fg, size, bold)
    c.alignment = P.align("right")

    for i, v in enumerate(counts, start=2):
        cc = ws.cell(row=r, column=i, value=v)
        cc.font = _font(fg, size, bold)
        cc.alignment = P.align("center")

    col = 2 + len(counts)
    for v in metrics.values():
        cc = ws.cell(row=r, column=col, value=v)
        cc.font = _font(fg, size, bold)
        cc.alignment = P.align("center")
        col += 1

    for i in range(1, n_cols + 1):
        cell = ws.cell(row=r, column=i)
        cell.fill = P.fill(bg)
        cell.border = P.thin_border()
    ws.row_dimensions[r].outlineLevel = level - 1
    if level >= 3:
        ws.row_dimensions[r].hidden = level == 4


def _metrics(g: pd.DataFrame) -> Dict[str, Any]:
    def m(col: str, fn: str = "mean") -> Any:
        if col not in g.columns:
            return 0
        s = pd.to_numeric(g[col], errors="coerce")
        if s.notna().sum() == 0:
            return 0
        return round(float(getattr(s, fn)()), 1)
    crit = 0
    if "کد طبقه بحرانی" in g.columns:
        crit = int(g["کد طبقه بحرانی"].isin(["STOCKOUT", "CRITICAL"]).sum())
    return {
        "پرونده": len(g),
        "بحرانی": crit,
        "میانگین مقاومت": m("مقاومت (روز)"),
        "میانگین رسوب": m("روزهای رسوب"),
        "مانده تعهد": m("مانده تعهد", "sum"),
        "میانگین ریسک": m("امتیاز ریسک"),
    }


def _advanced(g: pd.DataFrame) -> List[tuple]:
    """لایه چهارم — «چرا»، نه «چقدر»."""
    rb = get_rulebook()
    out: List[tuple] = []

    def num(c: str) -> pd.Series:
        return pd.to_numeric(g.get(c), errors="coerce")

    total = max(len(g), 1)
    stages = _stage_counts(g)
    # نرخ تبدیل هر مرحله به مرحله بعد — قیف واقعی
    for i in range(len(LIFECYCLE) - 1):
        a, b = stages[i], stages[i + 1]
        if a > 0:
            drop = round((a - b) / a * 100, 1)
            if drop >= 25:
                out.append((f"افت قیف: {LIFECYCLE[i][1]} ← {LIFECYCLE[i + 1][1]}",
                            f"{drop}٪ ({a} → {b})",
                            "بیشترین ریزش زنجیره در همین گام است"))
    res = num("مقاومت (روز)")
    if res.notna().sum():
        out.append(("چارک اول مقاومت (روز)", round(float(res.quantile(0.25)), 1),
                    "یک‌چهارم قطعات زیر این عدد قرار دارند"))
        out.append(("میانه مقاومت (روز)", round(float(res.median()), 1),
                    "مقاوم‌تر از میانگین در برابر مقادیر پرت"))
    stuck = num("روزهای رسوب")
    if stuck.notna().sum():
        out.append(("صدک ۹۰ روزهای رسوب", round(float(stuck.quantile(0.90)), 1),
                    f"آستانه رسوب شدید: {rb.demurrage_critical_days()} روز"))
    bal, over = num("مانده تعهد").fillna(0), num("روزهای تأخیر").fillna(0)
    exposed = float(bal[over > 0].sum())
    if bal.sum() > 0:
        out.append(("مانده تعهد معوق", round(exposed, 0),
                    f"{round(exposed / max(float(bal.sum()), 1) * 100, 1)}٪ کل مانده"))
    pen = num("جریمه برآوردی").fillna(0)
    if pen.sum() > 0:
        out.append(("جریمه برآوردی", round(float(pen.sum()), 0),
                    "پلکانی طبق fx_governance.yaml"))
    if "امتیاز انطباق (٪)" in g.columns:
        conf = num("امتیاز انطباق (٪)")
        if conf.notna().sum():
            out.append(("میانگین انطباق فرآیند (٪)", round(float(conf.mean()), 1),
                        "۱۰۰ یعنی اجرای کامل مطابق چرخه عمر"))
    blocked = int(g.get("IS_BLOCKED", pd.Series(dtype=bool)).astype(bool).sum())
    if blocked:
        out.append(("پرونده بلوکه", blocked,
                    "منتظر ثبت سفارش، تخصیص یا خرید ارز"))
    return out


def _build_insight(self, df: "pd.DataFrame") -> None:
    """شیت ۱۲ — بینش چهارلایه، از معاونت تا محاسبات."""
    ws = self._new_sheet(SHEET_INSIGHT)
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.outlinePr.summaryBelow = False

    stage_names = [fa for _, fa, _ in LIFECYCLE]
    metric_names = ["پرونده", "بحرانی", "میانگین مقاومت", "میانگین رسوب",
                    "مانده تعهد", "میانگین ریسک"]
    headers = ["سلسله‌مراتب"] + stage_names + metric_names
    n_cols = len(headers)

    ws.cell(row=1, column=1,
            value="بینش چندلایه — از معاونت تا محاسبات پیشرفته").font = P.font_title(14)
    ws.cell(row=2, column=1,
            value="با «+» کنار هر ردیف، یک لایه عمیق‌تر می‌شوید. "
                  "لایه چهارم (محاسبات) پیش‌فرض بسته است.").font = P.font_body()

    hr = 4
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=hr, column=i, value=h)
        c.font = P.font_header(1)
        c.fill = P.fill(AQUA_DEEP)
        c.alignment = P.align("center", wrap=True)
    ws.row_dimensions[hr].height = 34
    ws.column_dimensions["A"].width = 42
    for i in range(2, n_cols + 1):
        ws.column_dimensions[get_column_letter(i)].width = 13
    ws.freeze_panes = ws.cell(row=hr + 1, column=2)

    r = hr + 1
    vice_col = "ORG_VICE" if "ORG_VICE" in df.columns else None
    dept_col = "ORG_DEPT" if "ORG_DEPT" in df.columns else None
    exp_col = "CANONICAL_EXPERT" if "CANONICAL_EXPERT" in df.columns else None

    def blank(v: Any) -> str:
        s = str(v).strip()
        return "نامشخص" if s in ("", "nan", "None") else s

    # ── لایه ۰: کل سازمان ──
    _write_row(ws, r, 1, "کل سازمان", _stage_counts(df), _metrics(df), n_cols)
    r += 1

    groups = ([(k, g) for k, g in df.groupby(df[vice_col].map(blank), sort=False)]
              if vice_col else [("کل سازمان", df)])
    for vice, gv in groups:
        _write_row(ws, r, 2, f"معاونت: {vice}", _stage_counts(gv), _metrics(gv), n_cols)
        r += 1
        depts = ([(k, g) for k, g in gv.groupby(gv[dept_col].map(blank), sort=False)]
                 if dept_col else [(vice, gv)])
        for dept, gd in depts:
            _write_row(ws, r, 3, f"مدیریت: {dept}", _stage_counts(gd),
                       _metrics(gd), n_cols)
            r += 1
            experts = ([(k, g) for k, g in gd.groupby(gd[exp_col].map(blank), sort=False)]
                       if exp_col else [(dept, gd)])
            for exp, ge in experts:
                _write_row(ws, r, 4, f"کارشناس: {exp}", _stage_counts(ge),
                           _metrics(ge), n_cols)
                r += 1
                for label, val, why in _advanced(ge):
                    c = ws.cell(row=r, column=1, value=f"            ▸ {label}")
                    c.font = _font(GREY_TEXT, 9)
                    c.alignment = P.align("right")
                    v = ws.cell(row=r, column=2, value=val)
                    v.font = _font(AQUA_DEEP, 9, True)
                    v.alignment = P.align("center")
                    w = ws.cell(row=r, column=3, value=why)
                    w.font = _font(GREY_TEXT, 9)
                    w.alignment = P.align("right", wrap=True)
                    ws.merge_cells(start_row=r, start_column=3,
                                   end_row=r, end_column=min(8, n_cols))
                    for i in range(1, n_cols + 1):
                        ws.cell(row=r, column=i).fill = P.fill(GREY_BG)
                    ws.row_dimensions[r].outlineLevel = 4
                    ws.row_dimensions[r].hidden = True
                    r += 1

    log.info(f"📄 شیت «{SHEET_INSIGHT}» ساخته شد — {r - hr - 1} ردیف در چهار لایه.")


def _build_material(self, df: "pd.DataFrame") -> None:
    """شیت ۱۳ — چرخه عمر هر متریال + دو نمودار پراکنش."""
    ws = self._new_sheet(SHEET_MATERIAL)
    ws.sheet_view.showGridLines = False

    ws["A1"] = "تحلیل چرخه عمر متریال — حلقه پاره کجاست؟"
    ws["A1"].font = P.font_title(14)
    ws["A2"] = ("هر ستون یک حلقه از زنجیره است. اولین ستون خالی، همان جایی "
                "است که پرونده متوقف شده.")
    ws["A2"].font = P.font_body()

    headers = (["کد متریال", "شرح کالا", "طبقه بحرانی", "مقاومت (روز)",
                "نیاز روزانه", "موجودی کل"]
               + [fa for _, fa, _ in LIFECYCLE]
               + ["اولین حلقه پاره", "روزهای رسوب", "مانده تعهد", "امتیاز ریسک"])
    hr = 4
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=hr, column=i, value=h)
        c.font = P.font_header(1)
        c.fill = P.fill(AQUA_DEEP)
        c.alignment = P.align("center", wrap=True)
    ws.row_dimensions[hr].height = 36
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 22
    for i in range(4, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 12
    ws.freeze_panes = ws.cell(row=hr + 1, column=3)
    ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(headers))}{hr}"

    key = "KEY_MATERIAL" if "KEY_MATERIAL" in df.columns else None
    if key is None:
        log.warning("⚠️ شیت متریال: کلید متریال موجود نیست.")
        return

    rows = []
    r = hr + 1
    for mat, g in df[df[key].astype(str).str.strip() != ""].groupby(key, sort=False):
        counts = _stage_counts(g)
        broken = next((fa for (code, fa, _), n in zip(LIFECYCLE, counts) if n == 0),
                      "— کامل —")
        res = pd.to_numeric(g.get("مقاومت (روز)"), errors="coerce").min()
        stuck = pd.to_numeric(g.get("روزهای رسوب"), errors="coerce").max()
        bal = pd.to_numeric(g.get("مانده تعهد"), errors="coerce").sum()
        risk = pd.to_numeric(g.get("امتیاز ریسک"), errors="coerce").max()
        vals = ([mat,
                 str(g.get("CANONICAL_GOODS_DESC", pd.Series([""])).iloc[0]),
                 str(g.get("طبقه بحرانی", pd.Series([""])).iloc[0]),
                 None if pd.isna(res) else float(res),
                 float(pd.to_numeric(g.get("نیاز روزانه"), errors="coerce").max() or 0),
                 float(pd.to_numeric(g.get("موجودی کل قابل احتساب"),
                                     errors="coerce").max() or 0)]
                + counts
                + [broken,
                   0 if pd.isna(stuck) else float(stuck),
                   0 if pd.isna(bal) else float(bal),
                   0 if pd.isna(risk) else float(risk)])
        for i, v in enumerate(vals, start=1):
            ws.cell(row=r, column=i, value=v)
        # حلقه‌های طی‌شده سبز، حلقه پاره قرمز کم‌رنگ
        for j, n in enumerate(counts, start=7):
            cell = ws.cell(row=r, column=j)
            cell.fill = P.fill(GREEN_SOFT if n else "F7D6D2")
            cell.alignment = P.align("center")
        for i in range(1, len(headers) + 1):
            ws.cell(row=r, column=i).border = P.thin_border()
        rows.append((r, res, stuck, bal))
        r += 1

    last = r - 1
    if last <= hr:
        return

    # ── نمودار پراکنش ۱: مقاومت در برابر رسوب ──
    i_res = headers.index("مقاومت (روز)") + 1
    i_stuck = headers.index("روزهای رسوب") + 1
    i_bal = headers.index("مانده تعهد") + 1

    sc = ScatterChart()
    sc.title = "مقاومت در برابر روزهای رسوب — ربع پایین‌راست خطرناک‌ترین است"
    sc.style = 2
    sc.x_axis.title = "روزهای رسوب"
    sc.y_axis.title = "مقاومت (روز)"
    sc.height, sc.width = 9.5, 17
    xs = Reference(ws, min_col=i_stuck, min_row=hr + 1, max_row=last)
    ys = Reference(ws, min_col=i_res, min_row=hr, max_row=last)
    s = Series(ys, xs, title_from_data=True)
    s.marker = Marker(symbol="circle", size=9)
    s.marker.graphicalProperties = GraphicalProperties(solidFill=AQUA)
    s.graphicalProperties.line.noFill = True          # فقط نقطه، بدون خط
    sc.series.append(s)
    ws.add_chart(sc, f"A{last + 3}")

    # ── نمودار پراکنش ۲: مانده تعهد در برابر رسوب ──
    sc2 = ScatterChart()
    sc2.title = "مانده تعهد در برابر رسوب — کجا جریمه انباشته می‌شود؟"
    sc2.style = 2
    sc2.x_axis.title = "روزهای رسوب"
    sc2.y_axis.title = "مانده تعهد"
    sc2.height, sc2.width = 9.5, 17
    ys2 = Reference(ws, min_col=i_bal, min_row=hr, max_row=last)
    s2 = Series(ys2, xs, title_from_data=True)
    s2.marker = Marker(symbol="diamond", size=9)
    s2.marker.graphicalProperties = GraphicalProperties(solidFill="C88B3A")
    s2.graphicalProperties.line.noFill = True
    sc2.series.append(s2)
    ws.add_chart(sc2, f"L{last + 3}")

    log.info(f"📄 شیت «{SHEET_MATERIAL}» ساخته شد — {last - hr} متریال، ۲ نمودار پراکنش.")
