# -*- coding: utf-8 -*-
"""شیت نمودارهای تحلیلی — نمودارهای بومی اکسل، نه تصویر.

## چرا بومی و نه تصویر

نمودار تصویری در اکسل مرده است: نه فیلتر می‌شود، نه drill-down دارد، نه با
به‌روزرسانی داده عوض می‌شود. نمودارهای اینجا به سلول‌های داده **متصل**‌اند،
پس اگر مدیری ردیفی را فیلتر یا ویرایش کند، نمودار همان لحظه به‌روز می‌شود.

## اصل طراحی

هر نمودار باید به یک سؤال تصمیم‌ساز جواب بدهد. نموداری که فقط «قشنگ» باشد
و تصمیمی را عوض نکند، حذف شده است. به همین دلیل اینجا خبری از نمودار سه‌بعدی،
عقربه‌ای و گرادیان تزئینی نیست.

| نمودار | سؤالی که جواب می‌دهد |
|---|---|
| توزیع طبقه بحرانی | چند قطعه در آستانه توقف خط است؟ |
| ده قطعه کم‌مقاومت | کدام قطعات را همین امروز باید پیگیری کرد؟ |
| مقاومت انبار در برابر کل | چقدر از نجاتمان به کالای در راه بند است؟ |
| مانده تعهد بر حسب مهلت | چه مبلغی و تا چه تاریخی در معرض جریمه است؟ |
| گلوگاه فرآیند | کدام گام بیشترین زمان را می‌خورد؟ |
| توزیع ریسک | ترکیب سبد ریسک چه شکلی است؟ |
| بار کاری سازمانی | کار روی کدام واحد تلنبار شده؟ |
"""
from __future__ import annotations

__contract__ = 1

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl.chart import BarChart, DoughnutChart, LineChart, Reference, Series
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.marker import Marker
from openpyxl.chart.text import RichText
from openpyxl.drawing.text import Paragraph, ParagraphProperties, CharacterProperties, Font as DrawingFont
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.fill import PatternFillProperties, SolidColorFillProperties
from openpyxl.utils import get_column_letter

from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from ..design import excel as dx
from ..design import tokens as T
from .palette import LuxuryPalette as P
from .financial_summary import commitment_status_summary

SHEET_CHARTS = "۱۱. نمودارهای تحلیلی"

#: پالت نمودارها — همان طیف دسته‌ای HTML، تا یک سری در Excel و در گزارش وب
#: یک رنگ داشته باشد. هشت رنگ با فاصله *روشنایی* از هم جدا شده‌اند، نه فقط
#: فام؛ بنابراین در چاپ سیاه‌وسفید و برای کاربر کوررنگ هم تفکیک‌پذیرند.
SERIES_COLORS = list(dx.SERIES_COLORS)

#: نگاشت برچسب فارسی وضعیت → رنگ نشانه (``fill``). قبلاً این‌ها هگز دستی
#: بودند (``F1C40F`` / ``F39C12`` / ``27AE60``) که با هیچ خروجی دیگری یکی
#: نبودند؛ حالا مستقیم از :data:`gsi.design.tokens.STATUS` می‌آیند.
_BAND_FILLS = dict(dx.STATUS_FILLS)

#: چیدمان: (ردیف، ستون) لنگر هر نمودار روی شیت
_ANCHORS = ["B2", "M2", "B23", "M23", "B44", "M44", "B65"]


def _font_rich(size: int = 820, bold: bool = False) -> RichText:
    cp = CharacterProperties(
        sz=size, b=bold, lang="fa-IR", rtl=True,
        latin=DrawingFont(typeface="IRANSans Light"),
        ea=DrawingFont(typeface="IRANSans Light"),
        cs=DrawingFont(typeface="IRANSans Light"),
    )
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp, rtl=True, algn="r"))])


def _apply_chart_font(ch: Any) -> None:
    """فونت همه متن‌های نمودار را به IRANSans Light تنظیم می‌کند."""
    try:
        if ch.title and ch.title.tx and ch.title.tx.rich and ch.title.tx.rich.p:
            for para in ch.title.tx.rich.p:
                para.pPr = ParagraphProperties(rtl=True, algn="r", defRPr=CharacterProperties(
                    sz=1050, b=True, lang="fa-IR", rtl=True,
                    latin=DrawingFont(typeface="IRANSans Light"),
                    ea=DrawingFont(typeface="IRANSans Light"),
                    cs=DrawingFont(typeface="IRANSans Light")))
                if para.r:
                    for run in para.r:
                        run.rPr = CharacterProperties(sz=1050, b=True, lang="fa-IR", rtl=True,
                            latin=DrawingFont(typeface="IRANSans Light"),
                            ea=DrawingFont(typeface="IRANSans Light"),
                            cs=DrawingFont(typeface="IRANSans Light"))
        for axis in (getattr(ch, "x_axis", None), getattr(ch, "y_axis", None)):
            if axis is not None:
                axis.txPr = _font_rich()
        if getattr(ch, "legend", None) is not None:
            try: ch.legend.txPr = _font_rich(size=760)
            except Exception: pass
        if getattr(ch, "dataLabels", None) is not None:
            try: ch.dataLabels.txPr = _font_rich(size=760)
            except Exception: pass
    except Exception as exc:
        log.debug("chart font styling skipped: %s", exc)


def _style_chart(ch: Any, title: str, height: float = 9.0,
                 width: float = 17.5) -> None:
    """ظاهر یکدست، کم‌تراکم و مناسب صفحه نمایش/چاپ."""
    ch.title = title
    ch.height = height
    ch.width = width
    ch.style = 2
    ch.roundedCorners = False
    if getattr(ch, "y_axis", None) is not None:
        ch.y_axis.delete = False
    if getattr(ch, "x_axis", None) is not None:
        ch.x_axis.delete = False
    _apply_chart_font(ch)

def _color_series(ch: Any, colors: Optional[List[str]] = None) -> None:
    palette = colors or SERIES_COLORS
    for i, s in enumerate(ch.series):
        s.graphicalProperties = GraphicalProperties(solidFill=palette[i % len(palette)])
        s.graphicalProperties.line.solidFill = palette[i % len(palette)]


class ChartData:
    """جدول کمکی پشت نمودارها.

    نمودار اکسل به سلول نیاز دارد، پس داده تجمیع‌شده در ناحیه‌ای کنار
    نمودارها نوشته می‌شود. این ناحیه عمداً پنهان نمی‌شود تا هر عددی که
    نمودار نشان می‌دهد، قابل ردیابی باشد — همان اصل «هیچ عدد بی‌منبع».
    """

    def __init__(self, ws: Any, start_col: int = 22) -> None:
        self.ws = ws
        self.col = start_col
        self.row = 1

    def write(self, title: str, labels: List[Any],
              series: Dict[str, List[Any]]) -> Tuple[int, int, int, int]:
        """جدول را می‌نویسد و مختصات (ردیف اول، ستون اول، ردیف آخر، ستون آخر)."""
        r0, c0 = self.row, self.col
        cell = self.ws.cell(row=r0, column=c0, value=title)
        cell.font = P.font_body(bold=True)
        self.ws.cell(row=r0 + 1, column=c0, value="عنوان").font = P.font_body(bold=True)
        for j, name in enumerate(series, start=1):
            self.ws.cell(row=r0 + 1, column=c0 + j,
                         value=name).font = P.font_body(bold=True)
        for i, lab in enumerate(labels, start=2):
            self.ws.cell(row=r0 + i, column=c0, value=lab)
            for j, vals in enumerate(series.values(), start=1):
                v = vals[i - 2] if i - 2 < len(vals) else 0
                self.ws.cell(row=r0 + i, column=c0 + j,
                             value=None if v is None else float(v))
        last_row = r0 + 1 + len(labels)
        last_col = c0 + len(series)
        self.row = last_row + 2
        return r0 + 1, c0, last_row, last_col


def _build_charts(self, df: "pd.DataFrame", ctx_extras: Optional[Dict] = None) -> None:
    """شیت ۱۱ — هفت نمودار متصل به داده زنده."""
    rb = get_rulebook()
    ws = self._new_sheet(SHEET_CHARTS)
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFGHIJKLMNOPQRSTU", [3] + [11] * 20):
        ws.column_dimensions[col].width = w

    ws["B1"] = "نمودارهای تحلیلی — پاسخ به تصمیم‌های کلیدی"
    ws["B1"].font = P.font_title(14)

    data = ChartData(ws)
    anchors = list(_ANCHORS)
    n_charts = 0

    def num(col: str) -> pd.Series:
        return pd.to_numeric(df.get(col), errors="coerce")

    # ── ۱) توزیع طبقه بحرانی ──
    if "بحرانی (کوتاه)" in df.columns:
        bands = rb.get("criticality.bands", []) or []
        order = [b.get("short_fa", b["code"]) for b in
                 sorted(bands, key=lambda b: b.get("sort", 99))]
        counts = df["بحرانی (کوتاه)"].value_counts()
        labels = [o for o in order if o in counts.index]
        vals = [int(counts[o]) for o in labels]
        if labels:
            label_display = {"توقف خط": "توقف", "بحرانی": "بحرانی", "در حال بحرانی شدن": "در آستانه",
                             "تحت نظر": "تحت نظر", "ایمن": "ایمن", "بدون مصرف": "غیرفعال", "نامشخص": "غیرفعال"}
            chart_labels = [label_display.get(str(x), str(x)) for x in labels]
            r1, c1, r2, c2 = data.write("وضعیت بحرانی متریال", chart_labels,
                                        {"تعداد": vals})
            ch = BarChart()
            ch.type, ch.grouping = "col", "clustered"
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "وضعیت بحرانی متریال — توزیع")
            ch.dataLabels = DataLabelList()
            ch.dataLabels.showVal = True
            ch.legend = None
            # رنگ هر ستون از خود قوانین می‌آید، نه سلیقه
            # رنگ هر ستون از خود rules/criticality.yaml می‌آید، نه سلیقه:
            # قرمزِ «توقف خط» همان رنگی است که در شیت‌های دیگر هم دیده می‌شود.
            _unknown = dx.X(T.STATUS["unknown"].fill)
            fills = {b.get("short_fa", b["code"]): b.get("color", _unknown)
                     for b in bands}
            fills.update(_BAND_FILLS)
            from openpyxl.chart.marker import DataPoint as _DP
            pts = []
            for i, lab in enumerate(labels):
                dp = _DP(idx=i)
                dp.graphicalProperties = GraphicalProperties(
                    solidFill=fills.get(lab, "406057"))
                pts.append(dp)
            ch.series[0].data_points = pts
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    # ── ۲) ده قطعه کم‌مقاومت ──
    if "مقاومت (روز)" in df.columns and "KEY_MATERIAL" in df.columns:
        sub = df[["KEY_MATERIAL", "مقاومت (روز)"]].copy()
        sub["مقاومت (روز)"] = pd.to_numeric(sub["مقاومت (روز)"], errors="coerce")
        sub = sub.dropna().sort_values("مقاومت (روز)").head(10)
        if not sub.empty:
            r1, c1, r2, c2 = data.write(
                "ده قطعه با کمترین مقاومت", list(sub["KEY_MATERIAL"].astype(str)),
                {"مقاومت (روز)": list(sub["مقاومت (روز)"])})
            ch = BarChart()
            ch.type, ch.grouping = "bar", "clustered"     # افقی: نام قطعه خواناتر
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "۱۰ متریال کم‌مقاومت")
            ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
            ch.legend = None
            _color_series(ch, [dx.X(T.STATUS["critical"].fill)])
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    # ── ۳) مقاومت انبار در برابر مقاومت کل ──
    if {"مقاومت انبار (روز)", "مقاومت (روز)"} <= set(df.columns):
        sub = df[["KEY_MATERIAL", "مقاومت انبار (روز)", "مقاومت (روز)"]].copy()
        for c in ("مقاومت انبار (روز)", "مقاومت (روز)"):
            sub[c] = pd.to_numeric(sub[c], errors="coerce")
        sub = sub.dropna().sort_values("مقاومت (روز)").head(10)
        if not sub.empty and (sub["مقاومت (روز)"] - sub["مقاومت انبار (روز)"]).abs().sum() > 0:
            r1, c1, r2, c2 = data.write(
                "انبار در برابر کل", list(sub["KEY_MATERIAL"].astype(str)),
                {"مقاومت انبار": list(sub["مقاومت انبار (روز)"]),
                 "با در راه و گمرک": list(sub["مقاومت (روز)"])})
            ch = BarChart()
            ch.type, ch.grouping = "col", "clustered"
            ch.add_data(Reference(ws, min_col=c1 + 1, max_col=c2, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "مقاومت انبار و کل")
            _color_series(ch, [dx.X(T.STATUS["neutral"].fill), SERIES_COLORS[2]])
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    # ── ۴) مانده تعهد بر حسب فاصله تا مهلت ──
    # دانه نمودار REG×Currency است؛ مقدار ناشناخته هرگز صفر/تسویه فرض نمی‌شود.
    if "مانده تعهد" in df.columns:
        summary, diag = commitment_status_summary(df)
        if not summary.empty:
            labels = [f"{r.currency} · {r.status}" for r in summary.itertuples(index=False)]
            vals = [float(x) for x in summary["amount"]]
            counts = [int(x) for x in summary["count"]]
            r1, c1, r2, c2 = data.write("مانده تعهد بر حسب وضعیت مهلت و ارز", labels,
                                        {"مانده تعهد": vals, "تعداد پرونده": counts})
            ch = BarChart()
            ch.type, ch.grouping = "col", "clustered"
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "مانده تعهد ارزی — تفکیک ارز")
            ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
            ch.legend = None
            _color_series(ch, [dx.X(T.STATUS["critical"].fill)])
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

        excluded = sum(diag.values())
        if excluded:
            note_row = max(2, data.row)
            ws.cell(row=note_row, column=data.col,
                    value=("کنترل کیفیت نمودار تعهد: "
                           f"{diag['unknown']} ثبت با مانده نامشخص، "
                           f"{diag['conflict']} ثبت دارای مغایرت، "
                           f"{diag['missing_key_or_currency']} ردیف با کلید/ارز ناقص؛ "
                           "در مبلغ نمودار وارد نشده‌اند.")).font = P.font_body(bold=True)

    # ── ۵) گلوگاه فرآیند ──
    bott = (ctx_extras or {}).get("bottlenecks")
    if bott is not None and not getattr(bott, "empty", True):
        b = bott.head(8)
        val_col = next((c for c in b.columns if "میانگین" in c), None)
        has_pair = {"از فعالیت", "به فعالیت"} <= set(b.columns)
        if val_col and has_pair:
            labels = [f"{a} ← {c}" for a, c in
                      zip(b["از فعالیت"].astype(str), b["به فعالیت"].astype(str))]
            r1, c1, r2, c2 = data.write(
                "گلوگاه‌های فرآیند", labels,
                {"میانگین (روز)": list(pd.to_numeric(b[val_col], errors="coerce").fillna(0))})
            ch = BarChart()
            ch.type, ch.grouping = "bar", "clustered"
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "گلوگاه فرآیند")
            ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
            ch.legend = None
            _color_series(ch, [dx.X(T.STATUS["warning"].fill)])
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    # ── ۶) توزیع طبقه ریسک ──
    if "طبقه ریسک" in df.columns:
        counts = df["طبقه ریسک"].value_counts()
        if len(counts):
            r1, c1, r2, c2 = data.write("توزیع طبقه ریسک",
                                        [str(x) for x in counts.index],
                                        {"تعداد": [int(v) for v in counts.values]})
            ch = DoughnutChart(holeSize=55)
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "ترکیب سبد ریسک", height=8.8, width=12.5)
            ch.dataLabels = DataLabelList(); ch.dataLabels.showPercent = True
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    # ── ۷) بار کاری سازمانی ──
    org_col = next((c for c in ("ORG_DEPT", "ORG_VICE") if c in df.columns), None)
    if org_col:
        counts = df[org_col].astype(str).replace("", "نامشخص").value_counts().head(8)
        if len(counts):
            r1, c1, r2, c2 = data.write("بار کاری بر حسب مدیریت",
                                        [str(x) for x in counts.index],
                                        {"تعداد پرونده": [int(v) for v in counts.values]})
            ch = BarChart()
            ch.type, ch.grouping = "bar", "clustered"
            ch.add_data(Reference(ws, min_col=c1 + 1, min_row=r1, max_row=r2),
                        titles_from_data=True)
            ch.set_categories(Reference(ws, min_col=c1, min_row=r1 + 1, max_row=r2))
            _style_chart(ch, "بار کاری سازمانی")
            ch.dataLabels = DataLabelList(); ch.dataLabels.showVal = True
            ch.legend = None
            _color_series(ch, [dx.X(T.STATUS["good"].fill)])
            _apply_chart_font(ch)
            ws.add_chart(ch, anchors[n_charts]); n_charts += 1

    ws["B1"].value = (f"نمودارهای تحلیلی — {n_charts} نمودار، همه متصل به داده زنده "
                      f"(جدول‌های پشتیبان در ستون‌های V به بعد)")
    log.info(f"📊 شیت «{SHEET_CHARTS}» ساخته شد — {n_charts} نمودار بومی اکسل.")
    return n_charts
