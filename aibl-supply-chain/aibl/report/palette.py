# -*- coding: utf-8 -*-
"""پالت لوکس سبز/نعنایی — طبق §۱۵ بدون هیچ تغییری حفظ شده است."""
from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

FONT_BODY = "IRANSans Light"
FONT_TITLE = "IRANSans Light"


class LuxuryPalette:
    GREEN_L1 = "95C3B6"
    GREEN_L2 = "A0C9BD"
    GREEN_L3 = "ABCFC5"
    GREEN_L4 = "B6D5CC"

    AMBER_HEADER = "406057"
    AMBER_FILL = "C0DCD4"
    CRITICAL_FILL = "FADBD8"

    TEXT_DARK = "111917"
    TEXT_MUTED = "406057"
    TEXT_LIGHT = "F4F9F7"

    STATUS_CRITICAL = "C0392B"
    STATUS_WARNING = "F39C12"
    STATUS_WATCH = "F1C40F"
    STATUS_GOOD = "27AE60"
    STATUS_INACTIVE = "95A5A6"
    STATUS_CRITICAL_FILL = "FADBD8"
    STATUS_WARNING_FILL = "FDEBD0"
    STATUS_WATCH_FILL = "FCF3CF"
    STATUS_GOOD_FILL = "D5F5E3"
    STATUS_INACTIVE_FILL = "EAEDED"

    BORDER_LIGHT = "A0C9BD"

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
