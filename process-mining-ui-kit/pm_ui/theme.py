# -*- coding: utf-8 -*-
"""لایهٔ تزریق CSS — راست‌به‌چپ‌سازی کامل، فونت فارسی، و بازنویسی ظاهر پیش‌فرض Streamlit.

## فونت — چرا قبلاً واقعاً IRANSans نمایش داده نمی‌شد

نسخهٔ قبلی این فایل با فرض «فایل IRANSansWeb را خودتان در ``static/fonts/``
می‌گذارید» نوشته شده بود؛ تا وقتی آن فایل واقعاً آن‌جا نبود (و نیست — فونت
IRANSans دارایی مجوزدار است، در مخزن کد قابل توزیع نیست)، ``FontSource``
پیش‌فرض هیچ ``@font-face``ای تزریق نمی‌کرد و مرورگر بی‌صدا تا انتهای صف
فونت می‌رفت تا به Tahoma/Arial سیستمی برسد — نتیجه، ظاهری که اصلاً شبیه
دیزاین‌سیستم فارسی نبود.

برای رفع این مشکل، **Vazirmatn** (فونت سوم در اولویت درخواستی خودتان،
متن‌باز با مجوز SIL OFL) همراه این پروژه در ``static/fonts/Vazirmatn-Variable.woff2``
است و همیشه، بدون هیچ تنظیمی، تزریق می‌شود — نه چیزی که باید خودتان تهیه
کنید. ترتیب اولویت فونت (``tokens.FONT_STACK``) دست‌نخورده می‌ماند:
IRANSansWeb → Yekan Bakh → Vazirmatn → سیستمی؛ اگر فایل مجوزدار IRANSans/
Yekan Bakh را هم با ``FontSource.LOCAL_STATIC`` اضافه کنید، همان‌ها در
اولویت اول می‌نشینند و Vazirmatn فقط پشتیبان است. اگر اضافه نکنید،
Vazirmatn — نه Tahoma — چیزی است که واقعاً دیده می‌شود.

## گزینه‌های ``FontSource`` (برای IRANSansWeb/Yekan Bakh مجوزدار)

    SYSTEM_ONLY    پیش‌فرض. فقط Vazirmatn (همراه پروژه) + فونت سیستمی.
    LOCAL_STATIC   علاوه بر Vazirmatn، فایل‌های IRANSansWeb/YekanBakh را هم
                   از ``static/fonts/`` می‌خواند (باید خودتان اضافه کنید).
    NETWORK_SHARE  مثل بالا، ولی از یک شیرِ شبکهٔ داخلی/اینترانت سازمانی.
"""
from __future__ import annotations

__contract__ = 1

from enum import Enum

from . import tokens as T

#: مسیر فونت متن‌باز همراه پروژه — نسبت به ریشهٔ اجرای Streamlit (همان‌جا که
#: ``static/`` سرو می‌شود). مجوز: SIL OFL — نگاه کنید به
#: ``static/fonts/Vazirmatn-OFL.txt``.
BUNDLED_VAZIRMATN_PATH = "app/static/fonts/Vazirmatn-Variable.woff2"


class FontSource(str, Enum):
    SYSTEM_ONLY = "system_only"
    LOCAL_STATIC = "local_static"
    NETWORK_SHARE = "network_share"


def _bundled_font_face() -> str:
    """Vazirmatn همراه پروژه — فونت متغیر، یک فایل برای همهٔ وزن‌ها (۱۰۰ تا ۹۰۰)."""
    return f"""
@font-face {{
  font-family: 'Vazirmatn';
  src: url('{BUNDLED_VAZIRMATN_PATH}') format('woff2-variations'),
       url('{BUNDLED_VAZIRMATN_PATH}') format('woff2');
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}}"""


def _font_face_block(source: FontSource, base_url: str) -> str:
    faces = [_bundled_font_face()]
    if source == FontSource.SYSTEM_ONLY:
        return "\n".join(faces)

    base = base_url.rstrip("/")
    # «IRANSansWeb» دقیقاً همان فونتی است که در خودِ فایل فیگمای دیزاین‌سیستم
    # (GSI Foundations) استفاده شده — نودهای متنی آن‌جا با وزن‌های
    # IRANSansWeb:Regular/IRANSansWeb:Bold ساخته شده‌اند. این‌ها دارایی
    # مجوزدارند و باید خودتان در ``static/fonts/`` بگذارید (نگاه کنید به
    # ``static/fonts/README_FA.md``)؛ اگر نگذارید، Vazirmatn بالا جایگزینشان می‌شود.
    weights = (("Regular", 400), ("Medium", 500), ("Bold", 700), ("Black", 800))
    web_weights = (("Regular", 400), ("Bold", 700))
    for name, weight in web_weights:
        faces.append(f"""
@font-face {{
  font-family: 'IRANSansWeb';
  src: url('{base}/IRANSansWeb-{name}.woff2') format('woff2');
  font-weight: {weight};
  font-style: normal;
  font-display: swap;
}}""")
    for family, filestem in (("IRANSansX", "IRANSansX"), ("YekanBakh", "YekanBakh")):
        for name, weight in weights:
            faces.append(f"""
@font-face {{
  font-family: '{family}';
  src: url('{base}/{filestem}-{name}.woff2') format('woff2');
  font-weight: {weight};
  font-style: normal;
  font-display: swap;
}}""")
    return "\n".join(faces)


def inject_global_css(*, font_source: FontSource = FontSource.SYSTEM_ONLY,
                       font_base_url: str = "app/static/fonts") -> str:
    """CSS سراسری را می‌سازد. خروجی را با ``st.markdown(..., unsafe_allow_html=True)`` تزریق کنید."""
    fonts = _font_face_block(font_source, font_base_url)
    css = f"""<style>
{fonts}

:root {{
  --page:{T.SURFACE_PAGE}; --card:{T.SURFACE_RAISED}; --sunken:{T.SURFACE_SUNKEN};
  --ink:{T.INK}; --ink-2:{T.INK_SOFT}; --ink-3:{T.INK_MUTED};
  --border:{T.BORDER}; --border-strong:{T.BORDER_STRONG};
  --aqua:{T.AQUA_700}; --aqua-light:{T.AQUA_500}; --aqua-wash:{T.AQUA_WASH};
  --radius-md:{T.RADIUS['md']}px; --radius-lg:{T.RADIUS['lg']}px;
  --shadow-card:{T.SHADOW_CARD}; --shadow-hover:{T.SHADOW_CARD_HOVER};
  --font:{T.FONT_STACK};
}}

/* ── ۱) راست‌به‌چپ کامل + فونت روی همهٔ عناصر Streamlit ─────────────────────
   Streamlit کلاس‌های داخلی‌اش را هش می‌کند و بین نگارش‌ها ناپایدارند، پس
   انتخابگر عام لازم است تا هیچ ویجتی روی فونت لاتین پیش‌فرض نماند. */
html, body, .stApp, .stApp *, [data-testid], [data-testid] *,
[class*="st-"], [class*="st-"] * {{
  font-family: var(--font) !important;
  direction: rtl;
}}
code, pre, kbd, samp, [data-testid="stCode"] * {{
  font-family: {T.FONT_STACK_MONO} !important; direction: ltr;
}}
html {{ direction: rtl; }}
.stApp {{ background: var(--page); }}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{ direction: rtl; }}

/* اعداد فارسی‌شده هم باید هم‌تراز راست بمانند، نه اینکه چون رقم‌اند چپ‌چین شوند */
[data-testid="stMetricValue"], .pm-num {{
  unicode-bidi: plaintext; font-variant-numeric: tabular-nums;
}}

/* ── ۲) مخفی‌سازی و بازآرایی ظاهر پیش‌فرض Streamlit ────────────────────── */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; box-shadow: none; }}
div[data-testid="stDecoration"] {{ display: none; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}
[data-testid="stStatusWidget"] {{ visibility: hidden; }}
[data-testid="stMainBlockContainer"] {{
  padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: {T.CONTAINER_MAX}px;
}}
[data-testid="stSidebar"] {{
  background: var(--card); border-left: 1px solid var(--border);
}}

/* ── ۳) کارت‌ها و کانتینرها — ظاهر لوکس سازمانی ────────────────────────── */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); box-shadow: var(--shadow-card);
  transition: box-shadow .25s ease, transform .25s ease;
}}
div[data-testid="stDataFrame"] {{
  border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--border);
}}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
.stTabs [data-baseweb="tab"] {{ color: var(--ink-2) !important; font-weight: 600; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ color: var(--aqua) !important; }}

/* ── ۴) دکمه‌ها و ویجت‌ها ────────────────────────────────────────────── */
.stButton>button, .stDownloadButton>button {{
  border-radius: var(--radius-md); font-weight: 600;
  border: 1px solid var(--border-strong); color: var(--ink) !important;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
  transform: translateY(-1px); box-shadow: var(--shadow-hover);
  border-color: var(--aqua);
}}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {{
  background: var(--aqua); border-color: var(--aqua); color: #fff !important;
}}
[data-baseweb="tag"] {{ background: var(--aqua) !important; }}
[data-baseweb="tag"] * {{ color: #fff !important; }}
[data-testid="stMetricLabel"] {{ color: var(--ink-2) !important; }}
[data-testid="stMetricValue"] {{ color: var(--ink) !important; }}
.stAlert {{ border-radius: var(--radius-md); }}

/* ── ۵) کاهش حرکت برای کاربران حساس ─────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; animation: none !important; }}
}}
</style>"""
    return css


def apply(*, font_source: FontSource = FontSource.SYSTEM_ONLY,
          font_base_url: str = "app/static/fonts") -> None:
    """میان‌بر: ``inject_global_css`` را می‌سازد و مستقیماً با ``st.markdown`` تزریق می‌کند.

    باید همان ابتدای اسکریپت صفحه، بلافاصله بعد از ``st.set_page_config``
    فراخوانی شود.
    """
    import streamlit as st  # وارد کردن دیرهنگام: این ماژول بدون Streamlit هم قابل تست بماند
    st.markdown(inject_global_css(font_source=font_source, font_base_url=font_base_url),
                unsafe_allow_html=True)


def page_config(title: str = "پلتفرم هوش فرآیندی", icon: str = "🧭") -> None:
    """پیکربندی اولیهٔ صفحه — Wide layout، منوی کاربری فارسی، بستن سایدبار پیش‌فرض باز."""
    import streamlit as st
    st.set_page_config(
        page_title=title, page_icon=icon, layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": "ساخته‌شده با سامانهٔ طراحی داخلی — بدون اتکا به اینترنت."},
    )
