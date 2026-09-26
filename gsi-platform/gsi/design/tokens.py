# -*- coding: utf-8 -*-
"""GSI Design System — لایه ۱: توکن‌های پایه (UI Basics).

## چرا این فایل وجود دارد

تا پیش از این، پالت در چهار جای مستقل تعریف شده بود:

    app/theme.py                      برای Streamlit
    gsi/report/palette.py             برای Excel
    gsi/studio_core/html_export.py    برای HTML
    gsi/integrations/daily_email.py   برای ایمیل

چهار نسخه از یک پالت یعنی چهار نسخه از یک اشتباه. وقتی «تحت نظر» در HTML
زرد روشن بود و در Excel زرد تیره، هیچ‌کدام غلط نبودند — ولی گزارش یک صدا
نداشت. این ماژول تنها منبع حقیقت رنگ، فاصله، تایپ و حرکت است و هر چهار
خروجی از آن می‌خوانند.

## قاعده‌های غیرقابل‌مذاکره

**۱) کنتراست ادعا نمی‌شود، اندازه گرفته می‌شود.** :func:`audit` نسبت هر
توکن متنی را طبق WCAG 2.1 حساب می‌کند و فهرست تخلف برمی‌گرداند. تست
رگرسیون روی فهرست خالی قفل است، پس پالت نمی‌تواند بی‌صدا خراب شود.

**۲) هر وضعیت سه رنگ دارد، نه یکی.**

    ink    متن و مرز — تیره، سنجیده‌شده روی سطح روشن
    fill   سطح نمودار — همان خانواده، آزاد از محدودیت متن
    wash   پس‌زمینه ملایم برچسب

طلایی و زرد هرگز روی سفید به کف ۳:۱ نمی‌رسند؛ این خاصیت خود رنگ است نه
سلیقه. طبق WCAG 1.4.11 کنتراست برای **مرز** عنصر گرافیکی لازم است، پس هر
سطح رنگی با ``ink`` هم‌خانواده محصور می‌شود و مرز حامل تفکیک‌پذیری است.

**۳) رنگ هرگز تنها حامل معنا نیست.** هر وضعیت آیکن و برچسب متنی هم دارد،
چون ۸٪ مردان کوررنگی قرمز-سبز دارند و گزارش سیاه‌وسفید هم چاپ می‌شود.

**۴) شبکه ۴ پیکسلی.** همه فاصله‌ها مضرب ۴ هستند. این همان چیزی است که
Auto Layout فیگما و CSS را روی یک ریتم نگه می‌دارد و «چشمی ۱۳ پیکسل» را
از گزارش حذف می‌کند.

## هویت GSI

    Navy   داده و اعتماد    — سطح مرجع، متن، هدر
    Teal   فرآیند و جریان   — کنش، مسیر، پیوند
    Gold   تصمیم            — لحظه‌ای که از کاربر کاری خواسته می‌شود

طلایی عمداً کمیاب است: اگر همه‌جا باشد، دیگر «تصمیم» را علامت نمی‌زند.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, List, NamedTuple, Tuple

# ═══════════════════════════════════════════════════════════════════════════
# ۱) رنگ — سطح، متن، مرز
# ═══════════════════════════════════════════════════════════════════════════
SURFACE_PAGE = "#f6f8f9"
SURFACE_RAISED = "#ffffff"
SURFACE_SUNKEN = "#eef2f4"
SURFACE_INVERSE = "#0b1f33"

# Editorial surfaces: used sparingly for narrative/learning/annotation, never as
# the default table/form background. They create a paper feeling without turning
# the product into a decorative theme.
SURFACE_PAPER = "#f7f3e8"
SURFACE_PAPER_SOFT = "#fbf8f1"
PAPER_RULE = "#dfd4bd"
PENCIL = "#7c766b"
AQUA_MIST = "#eaf6f4"
LAPIS_WASH = "#eef2f8"

BORDER = "#dbe3e7"          # مرز تزئینی ظرف — حامل معنا نیست
#: مرز عنصر تعاملی (input, select, دکمه ثانویه). طبق WCAG 1.4.11 مرزِ یک
#: کنترل باید ≥۳:۱ باشد، وگرنه کاربر لبه فیلد را روی مانیتور اداری نمی‌بیند.
#: مقدار قبلی ``#b9c6cd`` نسبت ۱٫۷۵ داشت و روی صفحهٔ روشن عملاً محو بود.
BORDER_STRONG = "#7d919e"   # ۳٫۲۷ روی سفید، ۳٫۰۷ روی سطح صفحه
BORDER_FOCUS = "#0a7c86"

TEXT = "#0b1f33"            # ۱۶٫۶۹ روی سفید — خودِ Navy برند
TEXT_SECONDARY = "#3d5163"  # ۸٫۲۲
TEXT_MUTED = "#5a6b79"      # ۵٫۵۱
TEXT_ON_DARK = "#ffffff"
TEXT_ON_BRAND = "#ffffff"

# ── هویت ──────────────────────────────────────────────────────────────────
BRAND_NAVY = "#0b1f33"      # Data / Trust
BRAND_TEAL = "#0a7c86"      # Process / Flow — ۴٫۹۵ روی سفید، متن‌پذیر
BRAND_GOLD = "#c79a4a"      # Decision — سطحی است، نه متنی
TEAL_INK = "#076670"        # ۶٫۶۸ — متن/مرز teal
GOLD_INK = "#7a5a15"        # ۶٫۳۶ — متن/مرز gold
TEAL_WASH = "#e7f1f2"
GOLD_WASH = "#faf3e4"
NAVY_WASH = "#e8ecf1"

#: طیف دنباله‌ای teal برای شدت/نقشه حرارتی — روشن به تیره
SEQUENTIAL: Tuple[str, ...] = (
    "#d8e9eb", "#a9d2d6", "#71b5bc", "#3f97a0", "#187e88", "#0b5a63",
)


class Status(NamedTuple):
    """یک طبقه وضعیت با هر سه نقش رنگی، آیکن و برچسب."""
    key: str
    ink: str      # متن و مرز
    fill: str     # سطح نمودار
    wash: str     # پس‌زمینه ملایم
    icon: str
    label: str

    @property
    def stroke(self) -> str:
        """مرز سطح رنگی — همان پله متن، که کنتراستش سنجیده شده."""
        return self.ink


#: ترتیب از بحرانی‌ترین به بی‌اثرترین؛ همین ترتیب در راهنما و نمودار می‌آید.
STATUS_SCALE: Tuple[Status, ...] = (
    Status("stockout", "#8f1f1f", "#a32828", "#fbeaea", "⏹", "توقف خط"),
    Status("critical", "#a52020", "#d03b3b", "#fdeded", "⬤", "بحرانی"),
    Status("serious",  "#9a4718", "#e07b4f", "#fdefe8", "◤", "در حال بحرانی شدن"),
    Status("warning",  "#7a5a15", "#e0a52e", "#fbf3e2", "◆", "تحت نظر"),
    Status("good",     "#136b13", "#1d8f4e", "#e8f6ec", "✓", "ایمن"),
    Status("neutral",  "#4f5f6b", "#8b9aa5", "#eef1f3", "—", "بدون مصرف"),
    Status("unknown",  "#56646f", "#adb9c2", "#f1f3f5", "?", "نامشخص"),
)
STATUS: Dict[str, Status] = {s.key: s for s in STATUS_SCALE}
STATUS_BY_LABEL: Dict[str, Status] = {s.label: s for s in STATUS_SCALE}
BAND_ORDER: Tuple[str, ...] = tuple(s.label for s in STATUS_SCALE)

#: پالت دسته‌ای برای سری داده (نه وضعیت). دو رنگ مجاور هرگز هم‌فام نیستند.
#:
#: نسخه قبلی (teal/sienna/indigo/gold-ink/violet/forest/plum/slate) چهار
#: مورد را زیر کف Chroma داشت (OKLCH C < 0.10 — یعنی خاکستری خوانده
#: می‌شد و کار تفکیک هویت را انجام نمی‌داد) و یک جفت مجاور (slate↔plum)
#: زیر کف تفکیک‌پذیری کوررنگی بود. با ``scripts/validate_palette.js``
#: (اسکیل dataviz) بازتنظیم شد: همان خانواده رنگ برند حفظ شده، فقط اشباع و
#: ترتیب اصلاح شده تا هر هشت‌تایی روی سطح روشن و تیره از هر پنج آزمون
#: (باند روشنایی، کف اشباع، تفکیک کوررنگی، کف دید عادی، کنتراست) عبور کند.
CATEGORICAL: Tuple[str, ...] = (
    "#049aa4",  # teal — هویت
    "#b5451f",  # burnt sienna
    "#1f8f4f",  # forest
    "#b8860b",  # gold
    "#7b52c9",  # violet
    "#c0392b",  # red
    "#3a5f9e",  # indigo
    "#9a4a6d",  # plum
)

# ═══════════════════════════════════════════════════════════════════════════
# ۲) فاصله — شبکه ۴ پیکسلی (پایه Auto Layout)
# ═══════════════════════════════════════════════════════════════════════════
#: نام معنایی → پیکسل. همان نام‌ها در فیگما روی padding/gap می‌نشینند.
SPACE: Dict[str, int] = {
    "none": 0, "3xs": 2, "2xs": 4, "xs": 8, "sm": 12, "md": 16,
    "lg": 20, "xl": 24, "2xl": 32, "3xl": 40, "4xl": 48, "5xl": 64,
}

#: padding استاندارد هر ظرف — تا «۱۳ پیکسل چشمی» در گزارش نباشد.
PAD_CARD = SPACE["md"]
PAD_PANEL = SPACE["lg"]
PAD_PAGE = SPACE["md"]

# ═══════════════════════════════════════════════════════════════════════════
# ۳) تایپوگرافی
# ═══════════════════════════════════════════════════════════════════════════
#: پشته فونت. IRANSans اول؛ اگر نبود، فونت سیستمی فارسی‌خوان.
FONT_STACK = ("'IRANSansWeb','IRANSansX','IRANSans','YekanBakh','Yekan Bakh',"
              "'Vazirmatn',Tahoma,'Segoe UI',Arial,sans-serif")
FONT_STACK_NUM = ("'IRANSansWeb','IRANSans','Segoe UI',Tahoma,Arial,sans-serif")
FONT_EXCEL = "IRANSans Light"


class TypeStyle(NamedTuple):
    size: int          # px
    weight: int
    line: float        # ضریب line-height
    track: float = 0   # letter-spacing (px)


#: مقیاس تایپ.
#:
#: قاعده ارتفاع خط دو سطح دارد و این تفکیک عمدی است:
#:   • **متن جاری** (body، small، caption) هرگز زیر ۱٫۵ نمی‌رود. فارسی به
#:     فضای عمودی بیشتری از لاتین نیاز دارد (کشیدگی، زیرنویس «ی» و «ج»)
#:     و WCAG 1.4.12 هم همین ۱٫۵ را برای متن پاراگرافی می‌خواهد.
#:   • **تیتر و عدد درشت** (display، h1، h2، metric) عمداً فشرده‌ترند؛ در
#:     اندازه بزرگ، ۱٫۵ تیتر را از هم می‌پاشد و بلوک متنی نمی‌سازد.
#: ``BODY_STYLES`` مرز این دو را صریح نگه می‌دارد تا تست بتواند بسنجد.
TYPE: Dict[str, TypeStyle] = {
    "display": TypeStyle(32, 700, 1.35, 0),
    "h1":      TypeStyle(25, 700, 1.40, 0),
    "h2":      TypeStyle(20, 700, 1.45, 0),
    "h3":      TypeStyle(17, 700, 1.50),
    "h4":      TypeStyle(15, 700, 1.55),
    "body-lg": TypeStyle(14, 400, 1.75),
    "body":    TypeStyle(13, 400, 1.75),
    "small":   TypeStyle(12, 400, 1.65),
    "caption": TypeStyle(11, 400, 1.55),
    "overline": TypeStyle(11, 700, 1.40, 0),
    "metric":  TypeStyle(26, 700, 1.20, 0),
    "metric-sm": TypeStyle(19, 700, 1.25, 0),
}

#: سبک‌هایی که «متن جاری» شمرده می‌شوند و کف ۱٫۵ ارتفاع خط دارند.
BODY_STYLES: Tuple[str, ...] = ("body-lg", "body", "small", "caption")
#: کف ارتفاع خط برای متن جاری (WCAG 1.4.12 + خوانایی فارسی).
BODY_LINE_MIN = 1.5

# ═══════════════════════════════════════════════════════════════════════════
# ۴) شعاع، ارتفاع، مرز
# ═══════════════════════════════════════════════════════════════════════════
RADIUS: Dict[str, int] = {"none": 0, "sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}

#: سایه‌ها عمداً کم‌رنگ و کم‌تعدادند: گزارش مدیریتی سند است، نه اپ موبایل.
ELEVATION: Dict[str, str] = {
    "flat": "none",
    "raised": "0 1px 2px rgba(11,31,51,.06), 0 1px 3px rgba(11,31,51,.04)",
    "overlay": "0 8px 24px rgba(11,31,51,.10)",
    "lifted": "0 12px 32px rgba(11,31,51,.13)",
}

# ═══════════════════════════════════════════════════════════════════════════
# ۵) حرکت — جهت، نه تزئین
# ═══════════════════════════════════════════════════════════════════════════
MOTION: Dict[str, str] = {
    "ease_entrance": "cubic-bezier(.22,1,.36,1)",   # خروجی نمایی
    "ease_standard": "cubic-bezier(.4,0,.2,1)",
    "ease_exit": "cubic-bezier(.4,0,1,1)",
    "dur_micro": "140ms",
    "dur_short": "220ms",
    "dur_medium": "400ms",
    "dur_long": "600ms",
    "stagger": "50ms",
}
#: سقف تأخیر آبشاری — بدون آن، فهرست بلند یعنی انتظار، نه جلوه.
STAGGER_MAX = 8
#: مهلت ایمنی نمایان‌سازی؛ هیچ محتوایی نباید برای همیشه نامرئی بماند.
REVEAL_FAILSAFE_MS = 1400

# ═══════════════════════════════════════════════════════════════════════════
# ۶) نقاط شکست — Responsive
# ═══════════════════════════════════════════════════════════════════════════
#: نام → حداقل عرض (px). همین نام‌ها در فیگما روی فریم‌ها می‌نشینند.
BREAKPOINT: Dict[str, int] = {"sm": 480, "md": 768, "lg": 1024, "xl": 1440}
CONTAINER_MAX = 1520

# ═══════════════════════════════════════════════════════════════════════════
# سنجش کنتراست (WCAG 2.1)
# ═══════════════════════════════════════════════════════════════════════════
AA_TEXT = 4.5      # متن معمولی
AA_LARGE = 3.0     # متن درشت و عنصر گرافیکی
AAA_TEXT = 7.0


def _chan(v: float) -> float:
    s = v / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    """روشنایی نسبی طبق WCAG — ورودی «#rrggbb» یا «rrggbb»."""
    h = str(hex_color).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"رنگ نامعتبر: {hex_color!r}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)


def contrast(fg: str, bg: str) -> float:
    """نسبت کنتراست دو رنگ — عددی بین ۱ و ۲۱."""
    a, b = luminance(fg), luminance(bg)
    hi, lo = (a, b) if a >= b else (b, a)
    return round((hi + 0.05) / (lo + 0.05), 2)


def excel(hex_color: str) -> str:
    """«#rrggbb» → «RRGGBB» برای openpyxl."""
    return str(hex_color).lstrip("#").upper()


class Violation(NamedTuple):
    name: str
    fg: str
    bg: str
    ratio: float
    floor: float


def audit() -> List[Violation]:
    """فهرست جفت‌های رنگی که کف WCAG را رد می‌کنند.

    خروجی خالی یعنی پالت سالم است. این تابع را تست رگرسیون صدا می‌زند،
    پس هیچ تغییری در پالت نمی‌تواند بی‌صدا کنتراست را بشکند.
    """
    out: List[Violation] = []

    def need(name: str, fg: str, bg: str, floor: float) -> None:
        r = contrast(fg, bg)
        if r < floor:
            out.append(Violation(name, fg, bg, r, floor))

    for surf_name, surf in (("کارت", SURFACE_RAISED), ("صفحه", SURFACE_PAGE),
                            ("فرورفته", SURFACE_SUNKEN)):
        need(f"متن اصلی روی {surf_name}", TEXT, surf, AA_TEXT)
        need(f"متن ثانویه روی {surf_name}", TEXT_SECONDARY, surf, AA_TEXT)
        need(f"یادداشت روی {surf_name}", TEXT_MUTED, surf, AA_TEXT)
    need("متن روی سطح تیره", TEXT_ON_DARK, SURFACE_INVERSE, AA_TEXT)
    need("متن روی Navy", TEXT_ON_BRAND, BRAND_NAVY, AA_TEXT)
    need("متن روی Teal", TEXT_ON_BRAND, BRAND_TEAL, AA_TEXT)
    need("Teal به‌عنوان متن", BRAND_TEAL, SURFACE_RAISED, AA_TEXT)
    need("Teal ink", TEAL_INK, SURFACE_RAISED, AA_TEXT)
    need("Gold ink", GOLD_INK, SURFACE_RAISED, AA_TEXT)
    need("Teal ink روی wash", TEAL_INK, TEAL_WASH, AA_TEXT)
    need("Gold ink روی wash", GOLD_INK, GOLD_WASH, AA_TEXT)
    need("مرز فوکوس", BORDER_FOCUS, SURFACE_RAISED, AA_LARGE)
    need("مرز پررنگ", BORDER_STRONG, SURFACE_RAISED, AA_LARGE)

    for s in STATUS_SCALE:
        need(f"برچسب «{s.label}»", s.ink, SURFACE_RAISED, AA_TEXT)
        need(f"برچسب «{s.label}» روی wash", s.ink, s.wash, AA_TEXT)
        # سطح زرد/نارنجی ذاتاً به ۳:۱ نمی‌رسد؛ مرزش سنجیده می‌شود.
        need(f"مرز سطح «{s.label}»", s.stroke, SURFACE_RAISED, AA_LARGE)
    for i, c in enumerate(CATEGORICAL, 1):
        need(f"سری {i}", c, SURFACE_RAISED, AA_LARGE)
    return out


def audit_report() -> str:
    """گزارش متنی کنتراست — برای Dev Handoff و بازبینی طراحی."""
    bad = audit()
    lines = ["GSI Design System — Accessibility audit (WCAG 2.1)", ""]
    lines.append(f"وضعیت: {'PASS' if not bad else 'FAIL'} — {len(bad)} تخلف")
    lines.append("")
    lines.append(f"{'توکن':38s} {'نسبت':>7s}  کف")
    lines.append("-" * 60)
    for s in STATUS_SCALE:
        lines.append(f"{'برچسب ' + s.label:38s} {contrast(s.ink, SURFACE_RAISED):7.2f}  {AA_TEXT}")
    for n, v in (("متن اصلی", TEXT), ("متن ثانویه", TEXT_SECONDARY),
                 ("یادداشت", TEXT_MUTED), ("Teal ink", TEAL_INK), ("Gold ink", GOLD_INK)):
        lines.append(f"{n:38s} {contrast(v, SURFACE_RAISED):7.2f}  {AA_TEXT}")
    for b in bad:
        lines.append(f"FAIL  {b.name} — {b.ratio} < {b.floor}")
    return "\n".join(lines)

# Report-cluster accents: identity only; status colors retain their existing meaning.
CLUSTER_ACCENTS = {
    "purchase_1": "#08675F", "purchase_2": "#07564F", "logistics": "#195C75",
    "finance": "#515589", "followup": "#785A22", "process": "#326257", "custom": "#455B68",
}
