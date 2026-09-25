# -*- coding: utf-8 -*-
"""لایهٔ تزریق CSS — راست‌به‌چپ‌سازی کامل، فونت فارسی، و بازنویسی ظاهر پیش‌فرض Streamlit.

## نکتهٔ حیاتی محیط شما

این پلتفرم **کاملاً آفلاین** اجرا می‌شود (فقط فولدر شبکه + ایمیل اوتلوک
سازمانی، بدون سرور و بدون اینترنت مستقیم). بنابراین فونت‌ها را نمی‌توان از
Google Fonts یا هر CDN عمومی گرفت. سه راه پشتیبانی می‌شود که با
``FontSource`` انتخاب می‌کنید:

    LOCAL_STATIC   فایل‌های woff2 را در ``static/fonts/`` این پروژه بگذارید؛
                   Streamlit از نگارش ۱٫۳۱ به بعد پوشهٔ ``static/`` کنار
                   اسکریپت اصلی را روی مسیر ``app/static/...`` سرو می‌کند.
    NETWORK_SHARE  اگر فونت‌ها روی یک شیرِ شبکهٔ داخلی/سرور اینترانت
                   سازمانی در دسترس‌اند، آدرس آن را در ``base_url`` بدهید
                   (همان الگوی «فراخوانی از طریق URL» که خواسته شده،
                   منتها روی شبکهٔ داخلی به‌جای اینترنت).
    SYSTEM_ONLY    هیچ ``@font-face`` تزریق نمی‌شود و فقط به فونت‌های
                   از‌پیش‌نصب‌شدهٔ ویندوز سازمانی (Tahoma) بازمی‌گردد —
                   همیشه کار می‌کند، فقط ظاهر لوکس IRANSans را ندارد.

پیش‌فرض ``SYSTEM_ONLY`` است تا داشبورد هرگز به‌خاطر فونت گم‌شده نشکند؛ به‌محض
این‌که فایل فونت را در دسترس گذاشتید، ``FontSource`` را عوض کنید.
"""
from __future__ import annotations

__contract__ = 1

from enum import Enum
from typing import Optional

from . import tokens as T


class FontSource(str, Enum):
    SYSTEM_ONLY = "system_only"
    LOCAL_STATIC = "local_static"
    NETWORK_SHARE = "network_share"


def _font_face_block(source: FontSource, base_url: str) -> str:
    if source == FontSource.SYSTEM_ONLY:
        return ""
    base = base_url.rstrip("/")
    # «IRANSansWeb» دقیقاً همان فونتی است که در خودِ فایل فیگمای دیزاین‌سیستم
    # (GSI Foundations) استفاده شده — نودهای متنی آن‌جا با وزن‌های
    # IRANSansWeb:Regular/IRANSansWeb:Bold ساخته شده‌اند. IRANSansX/YekanBakh
    # به‌عنوان جایگزین نگه داشته شده‌اند، برای وقتی فایل وب‌فونت اصلی در
    # دسترس نیست.
    weights = (("Regular", 400), ("Medium", 500), ("Bold", 700), ("Black", 800))
    web_weights = (("Regular", 400), ("Bold", 700))
    faces = []
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
