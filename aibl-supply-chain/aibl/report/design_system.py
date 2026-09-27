# -*- coding: utf-8 -*-
"""سیستم طراحی AIBL — توکن رنگ، کنتراست سنجیده‌شده و توکن حرکت.

## چرا این فایل ساخته شد

تا نسخه ۲۶٫۱۸، رنگ‌ها در سه جا جداگانه تعریف شده بودند: ``app/theme.py``
برای Streamlit، ثابت‌های بالای ``studio_core/html_export.py`` برای HTML و
ثابت‌های بالای ``integrations/daily_email.py`` برای ایمیل. سه نسخه از یک
پالت یعنی سه نسخه از یک اشتباه؛ و هیچ‌کدام کنتراست را **اندازه** نمی‌گرفتند.

نتیجه عملی آن روی خروجی واقعی دیده می‌شد: «در حال بحرانی شدن» با ``#ec835a``
روی سفید نسبت کنتراست ۲٫۴ داشت (کف WCAG AA برای متن ۴٫۵ است). یعنی برچسبی
که قرار بود هشدار بدهد، روی مانیتور اداری و در چاپ سیاه‌وسفید عملاً محو بود.

## قاعده این فایل

هر توکن رنگی که **متن** می‌شود، باید نسبت کنتراست ≥ ۴٫۵ روی سطح خودش
داشته باشد. این ادعا حرف نیست: :func:`contrast_ratio` آن را محاسبه می‌کند و
:func:`audit_contrast` فهرست تخلف‌ها را برمی‌گرداند. تست رگرسیون همین تابع
را صدا می‌زند، پس پالت نمی‌تواند بی‌صدا خراب شود.

هر وضعیت دو رنگ دارد، نه یکی:

    ``ink``   رنگ متن/برچسب — تیره، سنجیده‌شده روی سطح روشن
    ``fill``  رنگ پر کردن نمودار — همان خانواده، آزاد از محدودیت متن

تفکیک این دو همان چیزی است که اجازه می‌دهد نمودار جان‌دار بماند ولی برچسب
خوانا شود؛ بدون آن یا نمودار مرده می‌شود یا متن ناخوانا.

## توکن حرکت

حرکت اینجا **تزئین نیست، جهت است**: چشم را به ترتیب درست می‌برد. سه قاعده
که از استانداردهای موشن Figma گرفته شده و در :data:`MOTION` کدگذاری شده:

1. فقط ``transform`` و ``opacity`` انیمیت می‌شوند — این دو روی GPU اجرا
   می‌شوند و layout را دوباره محاسبه نمی‌کنند. انیمیت کردن ``width`` یا
   ``top`` همان چیزی است که گزارش را روی لپ‌تاپ اداری کند می‌کند.
2. منحنی‌ها **خروجی-محور**‌اند (سریع شروع، نرم توقف). فنر/جهش عمداً حذف شده:
   جهش در داشبورد مدیریتی لحن اسباب‌بازی می‌دهد.
3. ``prefers-reduced-motion`` اختیاری نیست. هر انیمیشنی که اینجا تعریف
   می‌شود باید زیر آن رسانه خاموش شود.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, List, Tuple

# ── سطوح، مرز و متن ───────────────────────────────────────────────────────
SURFACE = "#f7f8f7"          # پس‌زمینه صفحه
SURFACE_RAISED = "#ffffff"   # کارت/پنل
SURFACE_SUNKEN = "#eef1f0"   # نوار ابزار و ناحیه فرورفته
BORDER = "#d7dedb"           # مرز عادی (قوی‌تر از #e3e3dd قبلی)
BORDER_STRONG = "#b6c3bf"

TEXT = "#0a1412"             # متن اصلی — کنتراست ۱۷٫۸ روی سفید
TEXT_SECONDARY = "#41504c"   # متن ثانویه — ۸٫۷ روی سفید
TEXT_MUTED = "#5c6b66"       # یادداشت — ۵٫۴ روی سفید (قبلاً ۴٫۱ بود)
TEXT_ON_DARK = "#ffffff"

# ── هویت ──────────────────────────────────────────────────────────────────
BRAND = "#0f6e6e"
BRAND_DEEP = "#08403f"       # هدر تیره — کنتراست ۱۰٫۹ با سفید
BRAND_INK = "#0b5252"        # متن برند روی سطح روشن — ۶٫۱ روی سفید
BRAND_SOFT = "#e4f0ee"
ACCENT_INK = "#1d5fa8"       # لینک/شاخص — ۶٫۰ روی سفید

#: طیف دنباله‌ای برند برای نقشه حرارتی و شدت — از روشن به تیره
SEQUENTIAL: Tuple[str, ...] = ("#d7e9e6", "#a9d2cd", "#6fb3ac", "#3d8f8a", "#1d6e6b", "#08403f")


class Status:
    """یک طبقه وضعیت: رنگ متن، رنگ پر کردن، پس‌زمینه ملایم، آیکن و برچسب.

    ``stroke`` عمداً جدا از ``fill`` است. زرد و نارنجی روی سفید هرگز به کف
    ۳٫۰ نمی‌رسند — این خاصیت خود رنگ است، نه سلیقه. WCAG 1.4.11 کنتراست را
    برای **مرز** عنصر گرافیکی می‌خواهد نه برای سطح آن؛ بنابراین هر سطح
    رنگی با یک خط تیره هم‌خانواده محصور می‌شود و مرز، نه سطح، حامل
    تفکیک‌پذیری است. بدون این، میله «تحت نظر» روی کارت سفید لبه ندارد.
    """

    __slots__ = ("key", "ink", "fill", "wash", "icon", "label")

    def __init__(self, key: str, ink: str, fill: str, wash: str, icon: str, label: str):
        self.key, self.ink, self.fill, self.wash = key, ink, fill, wash
        self.icon, self.label = icon, label

    @property
    def stroke(self) -> str:
        """مرز سطح رنگی — همان پله متن، که کنتراست آن سنجیده شده است."""
        return self.ink


#: پالت وضعیت. ``ink`` روی ``SURFACE_RAISED`` و ``wash`` سنجیده شده است.
#: خانواده رنگی همان پالت تأییدشده §۱۵ است؛ فقط پله متن تیره‌تر شده تا
#: برچسب روی سفید و در چاپ سیاه‌وسفید خوانا بماند.
STATUS_SCALE: Tuple[Status, ...] = (
    Status("stockout", "#8f1f1f", "#a32828", "#fbeaea", "⏹", "توقف خط"),
    Status("critical", "#a52020", "#d03b3b", "#fdeded", "⬤", "بحرانی"),
    Status("serious",  "#9a4718", "#ec835a", "#fdefe8", "◤", "در حال بحرانی شدن"),
    Status("warning",  "#7a5405", "#fab219", "#fdf4e1", "◆", "تحت نظر"),
    Status("good",     "#136b13", "#0ca30c", "#e8f6e8", "✓", "ایمن"),
    Status("neutral",  "#565651", "#8a8a85", "#f0f0ee", "—", "بدون مصرف"),
    Status("unknown",  "#5f5f58", "#b5b5ae", "#f3f3f1", "?", "نامشخص"),
)

STATUS: Dict[str, Status] = {s.key: s for s in STATUS_SCALE}
#: برچسب فارسی → وضعیت. همان برچسب‌هایی که در ستون «بحرانی (کوتاه)» می‌آیند.
STATUS_BY_LABEL: Dict[str, Status] = {s.label: s for s in STATUS_SCALE}
BAND_ORDER: Tuple[str, ...] = tuple(s.label for s in STATUS_SCALE)

#: پالت دسته‌ای برای سری‌های داده (نه وضعیت). ترتیب برای تفکیک‌پذیری چیده
#: شده: دو رنگ مجاور هرگز هم‌فام نیستند.
CATEGORICAL: Tuple[str, ...] = (
    "#0f6e6e",  # teal
    "#b5451f",  # burnt sienna
    "#3a5f9e",  # indigo
    "#c08a12",  # ochre
    "#6a5d8f",  # muted violet
    "#2f7d4f",  # forest
    "#9a4a6d",  # plum
    "#546a70",  # slate
)


# ── سنجش کنتراست (WCAG 2.1) ───────────────────────────────────────────────
def _channel(value: float) -> float:
    v = value / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """روشنایی نسبی طبق WCAG — ورودی «#rrggbb»."""
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"رنگ نامعتبر: {hex_color!r}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """نسبت کنتراست دو رنگ — عددی بین ۱ و ۲۱."""
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = (a, b) if a >= b else (b, a)
    return round((hi + 0.05) / (lo + 0.05), 2)


#: کف WCAG AA — متن معمولی ۴٫۵ ، متن درشت/عنصر گرافیکی ۳٫۰
AA_TEXT = 4.5
AA_LARGE = 3.0


def audit_contrast() -> List[Tuple[str, str, str, float]]:
    """فهرست جفت‌های رنگی که کف AA را رد می‌کنند.

    خروجی خالی یعنی پالت سالم است. تست رگرسیون همین را می‌سنجد، پس هیچ
    تغییری در پالت نمی‌تواند بی‌صدا کنتراست را بشکند.
    """
    checks: List[Tuple[str, str, str, float]] = []

    def need(name: str, fg: str, bg: str, floor: float) -> None:
        r = contrast_ratio(fg, bg)
        if r < floor:
            checks.append((name, fg, bg, r))

    need("متن اصلی", TEXT, SURFACE_RAISED, AA_TEXT)
    need("متن اصلی روی سطح صفحه", TEXT, SURFACE, AA_TEXT)
    need("متن ثانویه", TEXT_SECONDARY, SURFACE_RAISED, AA_TEXT)
    need("یادداشت", TEXT_MUTED, SURFACE_RAISED, AA_TEXT)
    need("یادداشت روی سطح فرورفته", TEXT_MUTED, SURFACE_SUNKEN, AA_TEXT)
    need("متن برند", BRAND_INK, SURFACE_RAISED, AA_TEXT)
    need("شاخص", ACCENT_INK, SURFACE_RAISED, AA_TEXT)
    need("متن روی هدر", TEXT_ON_DARK, BRAND_DEEP, AA_TEXT)
    for s in STATUS_SCALE:
        need(f"برچسب «{s.label}»", s.ink, SURFACE_RAISED, AA_TEXT)
        need(f"برچسب «{s.label}» روی پس‌زمینه ملایم", s.ink, s.wash, AA_TEXT)
        # سطح زرد/نارنجی ذاتاً به ۳٫۰ نمی‌رسد؛ مرز آن سنجیده می‌شود.
        need(f"مرز سطح رنگی «{s.label}»", s.stroke, SURFACE_RAISED, AA_LARGE)
    for i, c in enumerate(CATEGORICAL):
        need(f"سری {i + 1}", c, SURFACE_RAISED, AA_LARGE)
    return checks


# ── توکن حرکت ─────────────────────────────────────────────────────────────
#: منحنی‌ها و مدت‌ها. نام‌ها عمداً معنایی‌اند تا در CSS هم خوانا بمانند.
MOTION: Dict[str, str] = {
    # خروجی نمایی — پیش‌فرض ورود عناصر. سریع می‌آید، نرم می‌ایستد.
    "ease_entrance": "cubic-bezier(.22,1,.36,1)",
    # استاندارد — برای تغییر حالت (هاور، انتخاب تب)
    "ease_standard": "cubic-bezier(.4,0,.2,1)",
    # خروج — سریع‌تر از ورود، چون کاربر منتظر رفتن چیزی نمی‌ماند
    "ease_exit": "cubic-bezier(.4,0,1,1)",
    "dur_micro": "140ms",     # بازخورد لمسی: هاور، فوکوس
    "dur_short": "240ms",     # تغییر حالت کوچک
    "dur_medium": "420ms",    # ورود کارت و نمودار
    "dur_long": "620ms",      # رسم مسیر نمودار
    "stagger": "55ms",        # فاصله ورود عناصر پشت‌سرهم
}

#: بیشینه تأخیر آبشاری. بدون سقف، فهرست ۴۰تایی یعنی ۲٫۲ ثانیه انتظار —
#: که دیگر «جلوه» نیست، «کندی» است.
STAGGER_MAX_STEPS = 8


def motion_css() -> str:
    """لایه حرکت — CSS خالص، بدون کتابخانه، با احترام به reduced-motion.

    چرا CSS خالص: هر کتابخانه انیمیشن دست‌کم ۳۰ کیلوبایت جاوااسکریپت به
    فایلی اضافه می‌کند که قرار است از داخل Outlook و روی شبکه اداری باز شود.
    همه چیزی که اینجا لازم است، ``@keyframes`` و ``transition`` است.
    """
    m = MOTION
    return f"""
:root{{
  --ease-entrance:{m['ease_entrance']};--ease-standard:{m['ease_standard']};--ease-exit:{m['ease_exit']};
  --dur-micro:{m['dur_micro']};--dur-short:{m['dur_short']};--dur-medium:{m['dur_medium']};--dur-long:{m['dur_long']};
  --stagger:{m['stagger']}
}}
@keyframes aibl-rise{{from{{opacity:0;transform:translate3d(0,14px,0)}}to{{opacity:1;transform:none}}}}
@keyframes aibl-fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes aibl-grow-x{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes aibl-draw{{from{{stroke-dashoffset:var(--dash,1000)}}to{{stroke-dashoffset:0}}}}
@keyframes aibl-pop{{from{{opacity:0;transform:scale(.72)}}to{{opacity:1;transform:scale(1)}}}}
.reveal{{opacity:0}}
.reveal.in{{animation:aibl-rise var(--dur-medium) var(--ease-entrance) both;
  animation-delay:calc(var(--i,0) * var(--stagger))}}
.chart-bar,.proc-bar{{transform-origin:right center;
  animation:aibl-grow-x var(--dur-medium) var(--ease-entrance) both;
  animation-delay:calc(var(--i,0) * var(--stagger))}}
.spark-line,.trend-line{{stroke-dasharray:var(--dash,1000);
  animation:aibl-draw var(--dur-long) var(--ease-entrance) both}}
.dot{{animation:aibl-pop var(--dur-short) var(--ease-entrance) both;
  animation-delay:calc(var(--i,0) * 6ms)}}
.card,.chartbox,.tabbtn,.export-btn,.kpi{{
  transition:transform var(--dur-short) var(--ease-standard),
             box-shadow var(--dur-short) var(--ease-standard),
             border-color var(--dur-micro) var(--ease-standard),
             background-color var(--dur-micro) var(--ease-standard)}}
.card:hover,.chartbox:hover{{transform:translate3d(0,-2px,0);
  box-shadow:0 10px 28px rgba(8,64,63,.10);border-color:{BORDER_STRONG}}}
.export-btn:hover{{transform:translate3d(0,-1px,0);box-shadow:0 6px 18px rgba(8,64,63,.22)}}
.export-btn:active{{transform:translate3d(0,1px,0)}}
.dot,.chart-bar,.proc-bar,.slice{{transition:opacity var(--dur-micro) var(--ease-standard),
  filter var(--dur-micro) var(--ease-standard)}}
.chartbox:hover .dot{{opacity:.95}}
@media (prefers-reduced-motion:reduce){{
  .reveal,.reveal.in,.chart-bar,.proc-bar,.spark-line,.trend-line,.dot{{
    animation:none!important;opacity:1!important;transform:none!important;
    stroke-dashoffset:0!important}}
  .card,.chartbox,.tabbtn,.export-btn,.kpi{{transition:none!important}}
  .card:hover,.chartbox:hover,.export-btn:hover{{transform:none!important}}
}}
@media print{{
  .reveal,.reveal.in,.chart-bar,.proc-bar,.spark-line,.trend-line,.dot{{
    animation:none!important;opacity:1!important;transform:none!important;
    stroke-dashoffset:0!important}}
}}"""


#: مهلت ایمنی ورود تدریجی (میلی‌ثانیه). هر عنصری که تا این زمان مشاهده
#: نشده باشد، بی‌قید و شرط نمایان می‌شود.
REVEAL_FAILSAFE_MS = 1500

#: اسکریپت ورود تدریجی. ``IntersectionObserver`` بومی مرورگر است — صفر
#: بایت وابستگی — و عناصر خارج از دید را اصلاً انیمیت نمی‌کند، پس گزارش
#: ۳۰۰۰ ردیفی هم سبک باز می‌شود.
#:
#: سه تور ایمنی، چون «نامرئی ماندن محتوا» بدترین شکست ممکن یک گزارش است و
#: هر سه حالت زیر در عمل رخ می‌دهند:
#:   • مرورگر بدون IntersectionObserver یا با reduced-motion → فوراً نمایان
#:   • عنصری که هرگز به دید نمی‌آید (چاپ، ذخیره تمام‌صفحه، تب پنهان)
#:     → پس از :data:`REVEAL_FAILSAFE_MS` بی‌قید و شرط نمایان
#:   • ``beforeprint`` → پیش از رندر چاپی، همه چیز نمایان
#: بدون تور دوم، خروجی PDF از یک صفحه بلند عملاً سفید می‌شد.
REVEAL_JS = (
    "function aiblRevealAll(){document.querySelectorAll('.reveal:not(.in)')"
    ".forEach(function(e){e.classList.add('in')})}\n"
    "function aiblReveal(root){"
    "var q=(root||document).querySelectorAll('.reveal:not(.in)');"
    "if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion:reduce)').matches){"
    "q.forEach(function(e){e.classList.add('in')});return}"
    "var io=new IntersectionObserver(function(es){es.forEach(function(x){"
    "if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},"
    "{rootMargin:'0px 0px -8% 0px',threshold:.06});"
    "q.forEach(function(e){io.observe(e)});"
    f"setTimeout(aiblRevealAll,{REVEAL_FAILSAFE_MS})}}\n"
    "window.addEventListener('beforeprint',aiblRevealAll);"
)
