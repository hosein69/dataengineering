# -*- coding: utf-8 -*-
"""Global RTL/Farsi CSS for the process UI.

The live GSI Figma Foundations use IRANSansWeb. Font binaries are deliberately
not distributed in this package. ``SYSTEM_ONLY`` uses the configured CSS font
stack; ``LOCAL_STATIC``/``NETWORK_SHARE`` may reference organization-licensed
IRANSansWeb/YekanBakh files supplied by the organization itself.
"""
from __future__ import annotations

__contract__ = 2

from enum import Enum
from . import tokens as T


class FontSource(str, Enum):
    SYSTEM_ONLY = "system_only"
    LOCAL_STATIC = "local_static"
    NETWORK_SHARE = "network_share"


def _font_face_block(source: FontSource, base_url: str) -> str:
    if source == FontSource.SYSTEM_ONLY:
        return ""
    base = base_url.rstrip("/")
    faces = []
    for name, weight in (("Regular", 400), ("Medium", 500), ("Bold", 700)):
        faces.append(f"""
@font-face {{
  font-family: 'IRANSansWeb';
  src: url('{base}/IRANSansWeb-{name}.woff2') format('woff2');
  font-weight: {weight}; font-style: normal; font-display: swap;
}}""")
    for family, filestem in (("IRANSansX", "IRANSansX"), ("YekanBakh", "YekanBakh")):
        for name, weight in (("Regular", 400), ("Medium", 500), ("Bold", 700)):
            faces.append(f"""
@font-face {{
  font-family: '{family}';
  src: url('{base}/{filestem}-{name}.woff2') format('woff2');
  font-weight: {weight}; font-style: normal; font-display: swap;
}}""")
    return "\n".join(faces)


def inject_global_css(*, font_source: FontSource = FontSource.SYSTEM_ONLY,
                      font_base_url: str = "app/static/fonts") -> str:
    fonts = _font_face_block(font_source, font_base_url)
    return f"""<style>
{fonts}
:root {{
  --page:{T.SURFACE_PAGE}; --card:{T.SURFACE_RAISED}; --sunken:{T.SURFACE_SUNKEN};
  --ink:{T.INK}; --ink-2:{T.INK_SOFT}; --ink-3:{T.INK_MUTED}; --border:{T.BORDER};
  --border-strong:{T.BORDER_STRONG}; --aqua:{T.AQUA_700}; --aqua-light:{T.AQUA_500};
  --aqua-wash:{T.AQUA_WASH}; --radius-md:{T.RADIUS['md']}px; --radius-lg:{T.RADIUS['lg']}px;
  --shadow-card:{T.SHADOW_CARD}; --shadow-hover:{T.SHADOW_CARD_HOVER}; --font:{T.FONT_STACK};
}}
html, body, .stApp, .stApp *, [data-testid], [data-testid] *, [class*="st-"], [class*="st-"] * {{
  font-family:var(--font)!important; direction:rtl; letter-spacing:0;
}}
code, pre, kbd, samp, [data-testid="stCode"] * {{font-family:{T.FONT_STACK_MONO}!important;direction:ltr}}
html{{direction:rtl}} .stApp{{background:var(--page)}} [data-testid="stAppViewContainer"],[data-testid="stMain"]{{direction:rtl}}
[data-testid="stMetricValue"],.pm-num{{unicode-bidi:plaintext;font-variant-numeric:tabular-nums}}
#MainMenu{{visibility:hidden}} footer{{visibility:hidden}} header[data-testid="stHeader"]{{background:transparent;box-shadow:none}}
div[data-testid="stDecoration"]{{display:none}} [data-testid="stToolbar"],[data-testid="stStatusWidget"]{{visibility:hidden}}
[data-testid="stMainBlockContainer"]{{padding-top:1.4rem;padding-bottom:2.5rem;max-width:{T.CONTAINER_MAX}px}}
[data-testid="stSidebar"]{{background:var(--card);border-left:1px solid var(--border)}}
div[data-testid="stVerticalBlockBorderWrapper"]{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-card);transition:box-shadow .25s ease,transform .25s ease}}
div[data-testid="stDataFrame"]{{border-radius:var(--radius-md);overflow:hidden;border:1px solid var(--border)}}
.stTabs [data-baseweb="tab-list"]{{gap:4px}} .stTabs [data-baseweb="tab"]{{color:var(--ink-2)!important;font-weight:600}}
.stTabs [data-baseweb="tab"][aria-selected="true"]{{color:var(--aqua)!important}}
.stButton>button,.stDownloadButton>button{{border-radius:var(--radius-md);font-weight:600;border:1px solid var(--border-strong);color:var(--ink)!important;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}}
.stButton>button:hover,.stDownloadButton>button:hover{{transform:translateY(-1px);box-shadow:var(--shadow-hover);border-color:var(--aqua)}}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{{background:var(--aqua);border-color:var(--aqua);color:#fff!important}}
[data-baseweb="tag"]{{background:var(--aqua)!important}} [data-baseweb="tag"] *{{color:#fff!important}}
[data-testid="stMetricLabel"]{{color:var(--ink-2)!important}} [data-testid="stMetricValue"]{{color:var(--ink)!important}} .stAlert{{border-radius:var(--radius-md)}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important;animation:none!important}}}}
</style>"""


def apply(*, font_source: FontSource = FontSource.SYSTEM_ONLY, font_base_url: str = "app/static/fonts") -> None:
    import streamlit as st
    st.markdown(inject_global_css(font_source=font_source, font_base_url=font_base_url), unsafe_allow_html=True)


def page_config(title: str = "پلتفرم هوش فرآیندی", icon: str = "🧭") -> None:
    import streamlit as st
    st.set_page_config(page_title=title, page_icon=icon, layout="wide", initial_sidebar_state="expanded",
                       menu_items={"About": "ساخته‌شده با سامانهٔ طراحی داخلی — بدون اتکا به اینترنت."})
