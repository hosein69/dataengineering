# -*- coding: utf-8 -*-
"""پالت Excel — اکنون از سیستم طراحی GSI مشتق می‌شود.

## چه چیزی عوض شد و چرا

این فایل قبلاً یک پالت **مستقل** داشت (`GREEN_L1…L4`, `AMBER_HEADER`,
`STATUS_*`) که هیچ ارتباطی با رنگ‌های HTML و ایمیل نداشت. نتیجه‌اش این
بود که «تحت نظر» در Excel ``F1C40F`` بود و در HTML ``fab219`` — دو زرد
متفاوت برای یک معنا. هیچ‌کدام غلط نبود؛ ولی گزارش یک صدا نداشت.

حالا هر مقدار از :mod:`gsi.design.tokens` می‌آید. نام‌های قدیمی **دست‌نخورده
باقی مانده‌اند** تا هفت ماژول مصرف‌کننده (`dashboard`, `charts`, `insight`,
`supply_views`, `system_health`, `extracts`) بدون تغییر کار کنند — فقط
رنگی که می‌گیرند، رنگ سنجیده‌شده است.

سه مقدار قبلی کف WCAG را رد می‌کردند و حالا جایگزین شده‌اند:

    STATUS_WATCH     F1C40F  (۱٫۷)  →  7A5A15  (۶٫۴)
    STATUS_WARNING   F39C12  (۱٫۹)  →  9A4718  (۶٫۴)
    STATUS_GOOD      27AE60  (۲٫۸)  →  136B13  (۶٫۷)

این‌ها **رنگ متن** هستند؛ رنگ سطح (fill) همچنان زنده و رنگی است و از
``design.tokens.STATUS[...].fill`` می‌آید.
"""
from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from ..design import excel as dx
from ..design import tokens as T

FONT_BODY = T.FONT_EXCEL
FONT_TITLE = T.FONT_EXCEL

_MAP = dx.legacy_palette_map()


class LuxuryPalette:
    """پالت Excel، مشتق از توکن‌های سیستم طراحی.

    نام‌ها برای سازگاری حفظ شده‌اند؛ مقادیر از یک منبع می‌آیند.
    """

    # ── طیف سطوح (از طیف دنباله‌ای teal) ──
    GREEN_L1 = _MAP["GREEN_L1"]
    GREEN_L2 = _MAP["GREEN_L2"]
    GREEN_L3 = _MAP["GREEN_L3"]
    GREEN_L4 = _MAP["GREEN_L4"]

    # ── سر ستون و سطوح تأکیدی ──
    AMBER_HEADER = _MAP["AMBER_HEADER"]      # Navy برند
    AMBER_FILL = _MAP["AMBER_FILL"]
    CRITICAL_FILL = _MAP["CRITICAL_FILL"]

    # ── متن ──
    TEXT_DARK = _MAP["TEXT_DARK"]
    TEXT_MUTED = _MAP["TEXT_MUTED"]
    TEXT_LIGHT = _MAP["TEXT_LIGHT"]

    # ── وضعیت: متن (ink) ──
    STATUS_CRITICAL = _MAP["STATUS_CRITICAL"]
    STATUS_WARNING = _MAP["STATUS_WARNING"]
    STATUS_WATCH = _MAP["STATUS_WATCH"]
    STATUS_GOOD = _MAP["STATUS_GOOD"]
    STATUS_INACTIVE = _MAP["STATUS_INACTIVE"]

    # ── وضعیت: پس‌زمینه ملایم (wash) ──
    STATUS_CRITICAL_FILL = _MAP["STATUS_CRITICAL_FILL"]
    STATUS_WARNING_FILL = _MAP["STATUS_WARNING_FILL"]
    STATUS_WATCH_FILL = _MAP["STATUS_WATCH_FILL"]
    STATUS_GOOD_FILL = _MAP["STATUS_GOOD_FILL"]
    STATUS_INACTIVE_FILL = _MAP["STATUS_INACTIVE_FILL"]

    BORDER_LIGHT = _MAP["BORDER_LIGHT"]
    BORDER_STRONG = dx.X(T.BORDER_STRONG)

    # ── هویت GSI، برای کدی که مستقیم برند می‌خواهد ──
    BRAND_NAVY = dx.X(T.BRAND_NAVY)
    BRAND_TEAL = dx.X(T.BRAND_TEAL)
    BRAND_GOLD = dx.X(T.BRAND_GOLD)

    @classmethod
    def font_header(cls, level: int = 1) -> Font:
        size = {1: dx.SIZE_H3, 2: dx.SIZE_BODY}.get(level, dx.SIZE_SMALL)
        return Font(name=FONT_BODY, size=size, bold=True, color=cls.TEXT_LIGHT)

    @classmethod
    def font_title(cls, size: int = 16) -> Font:
        return Font(name=FONT_TITLE, size=size, bold=True, color=cls.BRAND_NAVY)

    @classmethod
    def font_body(cls, bold: bool = False) -> Font:
        return Font(name=FONT_BODY, size=dx.SIZE_BODY, bold=bold, color=cls.TEXT_DARK)

    @classmethod
    def font_kpi(cls) -> Font:
        return Font(name=FONT_BODY, size=dx.SIZE_KPI, bold=True, color=cls.BRAND_NAVY)

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
    def thin_border(cls, color: str = "") -> Border:
        side = Side(style="thin", color=color or cls.BORDER_LIGHT)
        return Border(left=side, right=side, top=side, bottom=side)

    @staticmethod
    def align(h: str = "right", wrap: bool = False) -> Alignment:
        return Alignment(horizontal=h, vertical="center", wrap_text=wrap)


NUM_FORMAT_CURRENCY = dx.NUM_CURRENCY
NUM_FORMAT_INT = dx.NUM_INT
NUM_FORMAT_PCT = dx.NUM_PCT
NUM_FORMAT_DATE = dx.NUM_DATE
