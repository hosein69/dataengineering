# -*- coding: utf-8 -*-
"""پالت — همه از نظام «آکوا» (`report/aqua.py`) می‌آید.

نام‌های عمومی این کلاس دست‌نخورده مانده‌اند تا هیچ مصرف‌کننده‌ای نشکند؛
فقط مقدارها از یک منبع واحد می‌آیند. پیش از این، اکسل AIBL یک سبز داشت،
HRPerf سبزی دیگر، و HTML سبز سوم — سه فایل کنار هم، سه محصول به‌نظر
می‌رسیدند.

رنگ‌های وضعیت هم از آکوا می‌آیند و همان‌هایی‌اند که در HTML و داشبورد
به‌کار می‌روند؛ همه با کنتراست سنجیده‌شده روی سطح واقعیِ خودشان.
"""
from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from . import aqua

FONT_BODY = aqua.FONT_XLSX
FONT_TITLE = aqua.FONT_XLSX

_T = aqua.xlsx_theme(False)
_S = aqua.xlsx_theme(False)


class LuxuryPalette:
    #: چهار پلهٔ سطح — از روشن به تیره، برای سطرهای تودرتو
    GREEN_L1 = aqua.IRANIAN["200"].lstrip("#")
    GREEN_L2 = aqua.TEAL["300"].lstrip("#")
    GREEN_L3 = aqua.TEAL["100"].lstrip("#")
    GREEN_L4 = aqua.TEAL["50"].lstrip("#")

    AMBER_HEADER = aqua.IRANIAN["900"].lstrip("#")   # هدر جدول
    AMBER_FILL = aqua.AMBER["50"].lstrip("#")        # هایلایت گرم
    CRITICAL_FILL = "F7DEDC"

    TEXT_DARK = aqua.INK.lstrip("#")
    TEXT_MUTED = aqua.TEAL["700"].lstrip("#")
    TEXT_LIGHT = "F4FBF7"

    STATUS_CRITICAL = _S["critical"]
    STATUS_WARNING = _S["serious"]
    STATUS_WATCH = _S["warning"]
    STATUS_GOOD = _S["good"]
    STATUS_INACTIVE = aqua.OTHER_LIGHT.lstrip("#")
    STATUS_CRITICAL_FILL = "F7DEDC"
    STATUS_WARNING_FILL = "FBE7D8"
    STATUS_WATCH_FILL = aqua.AMBER["50"].lstrip("#")
    STATUS_GOOD_FILL = "DDEFDE"
    STATUS_INACTIVE_FILL = "E6EDE9"

    BORDER_LIGHT = aqua.TEAL["500"].lstrip("#")

    @classmethod
    def font_header(cls, level: int = 1) -> Font:
        size = 11 if level == 1 else (10 if level == 2 else 9)
        return Font(name=FONT_BODY, size=size, bold=True, color=cls.TEXT_LIGHT)

    @classmethod
    def font_title(cls, size: int = 16) -> Font:
        return Font(name=FONT_TITLE, size=size, bold=True, color=cls.TEXT_MUTED)

    @classmethod
    def font_body(cls, bold: bool = False) -> Font:
        return Font(name=FONT_BODY, size=10, bold=bold, color=cls.TEXT_DARK)

    @classmethod
    def font_kpi(cls) -> Font:
        return Font(name=FONT_BODY, size=18, bold=True, color=cls.TEXT_MUTED)

    @classmethod
    def fill_header(cls) -> PatternFill:
        return PatternFill("solid", fgColor=cls.AMBER_HEADER)

    @classmethod
    def fill_row_level(cls, level: int) -> PatternFill:
        mapping = {1: cls.GREEN_L1, 2: cls.GREEN_L2, 3: cls.GREEN_L3, 4: cls.GREEN_L4}
        return PatternFill("solid", fgColor=mapping.get(level, cls.GREEN_L4))

    @classmethod
    def fill(cls, color: str) -> PatternFill:
        return PatternFill("solid", fgColor=color)

    @classmethod
    def thin_border(cls) -> Border:
        side = Side(style="thin", color=cls.BORDER_LIGHT)
        return Border(left=side, right=side, top=side, bottom=side)

    @staticmethod
    def align(h: str = "right", wrap: bool = False) -> Alignment:
        return Alignment(horizontal=h, vertical="center", wrap_text=wrap)


NUM_FORMAT_CURRENCY = "#,##0.00"
NUM_FORMAT_INT = "#,##0"
NUM_FORMAT_PCT = "0.0"
