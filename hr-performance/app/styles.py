# -*- coding: utf-8 -*-
"""CSS داشبورد — راست‌به‌چپ، واکنش‌گر به موس، بدون وابستگی به JS.

⚠️ هرگز ``position`` را روی ``.stApp`` بازنویسی نکنید. Streamlit خودش آن
را ``absolute; inset:0`` می‌گذارد و ``#stAppViewContainer`` ارتفاعش را از
همان می‌گیرد؛ با ``relative`` ارتفاع صفر می‌شود و چون ``overflow`` آن
``hidden`` است کل صفحه سفیدِ خالی رندر می‌شود.
"""
from __future__ import annotations

from hrperf.report import alborz as _AL
from hrperf.report.theme import (BORDER, BRAND, BRAND_DEEP, FONT_STACK, RAISED,
                                 SURFACE, TEXT, TEXT2, TEXT3)


def css() -> str:
    return f"""<style>
/* نام‌های مختلف نصبِ ایران‌سنس را به یک خانواده گره می‌زنیم؛ اگر هیچ‌کدام
   نبود، مرورگر بی‌صدا به گزینهٔ بعدی زنجیره می‌رود. نام‌های خط‌تیره‌دار
   (PostScript) برای مک‌اند: Font Book فایل را با همان نام ثبت می‌کند،
   نه با نامِ کاملی که ویندوز نشان می‌دهد. */
@font-face {{ font-family:'IRANSans'; font-style:normal; font-weight:400;
  src: local('IRANSans'), local('IRANSansWeb'), local('IRAN Sans'),
       local('IRANSansX'), local('IRANSans Regular'), local('IRANSansWeb(FaNum)'),
       local('IRANSansX-Regular'), local('IRANSansWeb-Regular'); }}
@font-face {{ font-family:'IRANSans'; font-style:normal; font-weight:700;
  src: local('IRANSans Bold'), local('IRANSansWeb Bold'), local('IRANSansX Bold'),
       local('IRAN Sans Bold'), local('IRANSansX-Bold'), local('IRANSansWeb-Bold'); }}
@font-face {{ font-family:'IRANSans Light'; font-style:normal; font-weight:300;
  src: local('IRANSans Light'), local('IRANSansWeb Light'),
       local('IRANSansX Light'), local('IRAN Sans Light'),
       local('IRANSansX-Light'), local('IRANSansWeb-Light'); }}

:root{{color-scheme:light;
--brand:{BRAND};--deep:{BRAND_DEEP};--surface:{SURFACE};--raised:{RAISED};
--border:{BORDER};--text:{TEXT};--t2:{TEXT2};--t3:{TEXT3}}}
/* `body *` تنها انتخابگری است که پرتال‌های baseweb (منو و پاپ‌آور، که
   بیرون از `.stApp` رندر می‌شوند) را هم می‌گیرد. */
html,body,body *{{font-family:{FONT_STACK}!important}}
html,body,.stApp{{direction:rtl}}
.stApp{{background:
  radial-gradient(1100px 560px at 88% -10%, #e8f0fb 0%, transparent 58%),
  radial-gradient(900px 500px at 4% 106%, #eef4f9 0%, transparent 60%),
  linear-gradient(180deg,{SURFACE} 0%, #f4f4f1 100%)}}
[data-testid="stMainBlockContainer"]{{padding-top:1.1rem;max-width:1500px}}
[data-testid="stHeader"]{{background:transparent}}

.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:6px 0 4px}}
@media(max-width:1250px){{.kpi-row{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:900px){{.kpi-row{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{position:relative;overflow:hidden;background:var(--raised);
border:1px solid var(--border);border-radius:16px;padding:13px 16px 12px;
box-shadow:0 1px 2px rgba(13,54,107,.05);
transition:transform .32s cubic-bezier(.2,.8,.2,1),box-shadow .32s,border-color .32s}}
.kpi::after{{content:"";position:absolute;inset:0;pointer-events:none;
background:linear-gradient(115deg,transparent 38%,rgba(255,255,255,.72) 50%,transparent 62%);
transform:translateX(-130%);transition:transform .78s ease}}
.kpi:hover{{transform:translateY(-5px);box-shadow:0 14px 34px rgba(13,54,107,.14);
border-color:#cfcfc6}}
.kpi:hover::after{{transform:translateX(130%)}}
.kpi .lab{{font-size:12px;color:var(--t2)}}
.kpi .val{{font-size:27px;font-weight:700;color:var(--text);line-height:1.2;
margin-top:5px;font-variant-numeric:tabular-nums}}
.kpi .sub{{font-size:11px;color:var(--t3);margin-top:5px}}
.kpi .bar{{height:3px;border-radius:2px;margin-top:11px;transition:height .32s}}
.kpi:hover .bar{{height:5px}}

.band{{display:inline-flex;align-items:center;gap:6px;border-radius:999px;
padding:3px 11px;font-size:12px;font-weight:600;line-height:1.7;
border:1px solid transparent;transition:transform .2s,box-shadow .2s}}
.band:hover{{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.10)}}
.band .g{{width:9px;height:9px;border-radius:50%;flex:none}}

.stButton>button,.stDownloadButton>button{{border-radius:11px;font-family:inherit;
font-weight:600;border:1px solid #cfcfc6;
transition:transform .2s,box-shadow .2s,background .2s}}
.stButton>button:hover,.stDownloadButton>button:hover{{transform:translateY(-2px);
box-shadow:0 8px 20px rgba(13,54,107,.14);border-color:var(--brand)}}
.stTabs [data-baseweb="tab"]{{font-family:inherit;font-weight:600}}
[data-testid="stSidebar"]{{background:linear-gradient(180deg,#fff,#f4f4f1)}}
[data-testid="stSidebar"] *{{font-family:{FONT_STACK}!important}}
div[data-testid="stDataFrame"]{{border-radius:12px;overflow:hidden;
border:1px solid var(--border)}}

/* ── فونت: باید به **همه** عناصر برسد ──────────────────────────────────
   CSS قبلی فقط html/body/.stApp را هدف می‌گرفت و ویجت‌های داخلی
   Streamlit (اسلایدر، تب، جدول، دکمه) روی فونت پیش‌فرض «Source Sans»
   می‌ماندند — اندازه‌گیری: ۱۶۵ عنصر با فونت اشتباه. انتخابگر عام لازم
   است چون کلاس‌های Streamlit هش‌شده و ناپایدارند. */
html, body, .stApp, .stApp *, [data-testid] , [data-testid] * ,
[class*="st-"], [class*="st-"] * {{
  font-family: {FONT_STACK} !important;
}}
/* استثنا: کد و عدد تک‌فاصله */
code, pre, kbd, samp, [data-testid="stCode"] * {{
  font-family: 'Cascadia Mono','Consolas','Courier New',monospace !important;
}}

/* ── کنتراست: هیچ متنی نباید هم‌رنگ پس‌زمینه‌اش باشد ──────────────────
   مقدارِ روی اسلایدر با رنگ primary روی نوارِ هم‌رنگ نوشته می‌شد
   (نسبت کنتراست ۱٫۰ — عملاً نامرئی). */
[data-testid="stSliderTickBarMin"],
[data-testid="stSliderTickBarMax"] {{
  color: var(--text) !important;
  font-weight: 700;
}}
/* مقدارِ اسلایدر روی نوارِ رنگی می‌نشیند، پس باید سفید باشد نه تیره
   (تیره روی برند ۲٫۹۷ می‌داد؛ سفید ۶٫۶۳). */
[data-testid="stSliderThumbValue"],
[data-testid="stSliderThumbValue"] * {{
  /* عدد داخل یک فرزند است، نه روی خود عنصر؛ بدون `*` رنگ متن عمومی
     روی آن می‌نشیند و تیره روی نوار برند ۲٫۷:۱ می‌دهد. */
  color: #ffffff !important;
  text-shadow: 0 1px 2px rgba(0,0,0,.45);
}}

[data-baseweb="slider"] div[role="slider"] + div {{ color: var(--text) !important; }}

/* برچسب ویجت‌ها و متن کمکی */
label, [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * ,
.stCheckbox label, .stRadio label, .stSelectbox label, .stMultiSelect label {{
  color: var(--text) !important;
}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * ,
small, .stCaption {{ color: var(--t2) !important; }}

/* چیپ‌های multiselect: متن روشن روی پس‌زمینه برند */
[data-baseweb="tag"] {{ background: var(--brand) !important; }}
[data-baseweb="tag"], [data-baseweb="tag"] * ,
[data-baseweb="tag"] span {{ color: #ffffff !important; }}

/* تب‌ها */
.stTabs [data-baseweb="tab"] {{ color: var(--t2) !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
  color: var(--brand) !important; font-weight: 700; }}

/* جدول و متریک */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ color: var(--t2) !important; }}
[data-testid="stMetricValue"] {{ color: var(--text) !important; }}
[data-testid="stDataFrame"] {{ color: var(--text); }}

/* دکمه‌ها: متن باید روی پس‌زمینه‌اش خوانا بماند */
.stButton>button, .stDownloadButton>button {{
  background: #ffffff; color: var(--text) !important; }}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {{
  background: var(--brand); color: #ffffff !important; border-color: var(--brand); }}
.stButton>button:hover, .stDownloadButton>button:hover {{ color: var(--brand) !important; }}
.stButton>button[kind="primary"]:hover {{ color: #ffffff !important; }}

/* expander و alert */
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{
  color: var(--text) !important; }}
.stAlert, .stAlert * {{ color: var(--text) !important; }}

/* ══════════════════════════════════════════════════════════════════════
   نظام طراحی البرز — زمینه، عمق و کارت
   ══════════════════════════════════════════════════════════════════════
   همان نظامی که پوستر و گزارش‌ها از آن می‌خوانند. مقدارها در
   `hrperf/report/alborz.py` است؛ اینجا فقط مصرف می‌شود. */
.stApp {{ background:{_AL.page_gradient_css()} !important; }}
.panel {{
  background:{_AL.CARD} !important;
  border:1px solid {_AL.CARD_EDGE} !important;
  border-radius:{_AL.RADIUS['panel']}px !important;
  box-shadow:{_AL.shadow_css()} !important;
}}
.kpi {{
  background:{_AL.CARD} !important;
  border:1px solid {_AL.CARD_EDGE} !important;
  border-radius:{_AL.RADIUS['sm']+4}px !important;
  box-shadow:{_AL.shadow_css()} !important;
}}

/* ══════════════════════════════════════════════════════════════════════
   کف خوانایی — رابط نباید به تم Streamlit وابسته باشد
   ══════════════════════════════════════════════════════════════════════
   اگر `.streamlit/config.toml` همراه بسته نباشد، Streamlit تم پیش‌فرضش
   را می‌گذارد و آن تم از `prefers-color-scheme` مرورگر پیروی می‌کند: روی
   ویندوزِ تاریک متن `#FAFAFA` می‌شود روی پس‌زمینهٔ روشن ما — نسبت
   کنتراست ۱٫۱۵:۱، عملاً نامرئی. این در AIBL نسخهٔ ۲۶٫۱۵٫۰ رخ داد و کل
   رابط را از کار انداخت. اینجا سه لایه هست و هرکدام به‌تنهایی کافی است:
   پیکربندی بسته‌بندی‌شده، متغیر محیطیِ راه‌انداز، و همین CSS. */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background-color: var(--surface); color: var(--text); }}
.stApp, .stApp p, .stApp span, .stApp li, .stApp td, .stApp th,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp summary, .stApp strong, .stApp em {{ color: var(--text); }}

[data-testid="stSidebar"], [data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  background: linear-gradient(180deg, var(--raised), var(--surface)) !important; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] summary {{
  color: var(--text); }}

/* پوستهٔ ورودی‌ها — عنصری که واقعاً رنگ می‌گیرد هیچ شناسه‌ای ندارد و
   فقط از روی جایگاهش زیر `data-testid` والد پیدا می‌شود. */
[data-testid="stMultiSelect"] > div > div,
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stTextArea"] > div > div {{
  background-color: var(--raised) !important;
  border-color: var(--border) !important; }}
[data-testid="stMultiSelectTagsContainer"] > span > span {{
  background-color: var(--brand) !important; }}
[data-testid="stMultiSelectTagsContainer"] > span > span,
[data-testid="stMultiSelectTagsContainer"] > span > span * {{
  color: #ffffff !important; }}

[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"],
[role="option"], input, textarea, select {{
  background-color: var(--raised) !important; color: var(--text) !important; }}
[role="option"]:hover, [role="option"][aria-selected="true"] {{
  background-color: var(--surface) !important; }}
::placeholder {{ color: var(--t3) !important; opacity:1; }}

[data-testid="stToolbar"], [data-testid="stToolbar"] * {{
  color: var(--t2) !important; }}
[data-testid="stDataFrame"] {{ background: var(--raised); }}
[data-testid="stDataFrame"], [data-testid="stDataFrame"] * {{ color: var(--text); }}

@media (prefers-reduced-motion: reduce){{
 .kpi,.kpi::after,.band,.stButton>button{{transition:none!important}}
 .kpi:hover{{transform:none}}}}
</style>"""


def kpi_card(label: str, value: str, sub: str, color: str, icon: str = "") -> str:
    ic = f'<span style="margin-left:5px">{icon}</span>' if icon else ""
    return (f'<div class="kpi"><div class="lab">{ic}{label}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div>'
            f'<div class="bar" style="background:{color}"></div></div>')


def band_chip(color: str, icon: str, label: str, text: str = "") -> str:
    """تراشهٔ رده — نقطه رنگ خام، متن رنگ تیره‌شدهٔ خوانا.

    پس‌زمینهٔ تراشه همان رنگ رده با ۱۰٪ شفافیت است؛ متن با رنگ خام روی
    آن ته‌رنگ، برای اندازهٔ ۱۲ پیکسل زیر حد خوانایی می‌افتاد.
    """
    ink = text or color
    return (f'<span class="band" style="background:{color}1a;color:{ink};'
            f'border-color:{color}44"><span class="g" style="background:{color}">'
            f'</span>{icon} {label}</span>')
