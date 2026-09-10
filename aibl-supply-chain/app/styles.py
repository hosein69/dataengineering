# -*- coding: utf-8 -*-
"""CSS رابط — راست‌به‌چپ، واکنش‌گر به موس، بدون وابستگی به JS.

⚠️ اینجا هرگز ``position`` را روی ``.stApp`` بازنویسی نکنید. Streamlit خودش
آن را ``position:absolute; inset:0`` می‌گذارد و ``#stAppViewContainer`` که
``absolute`` است ارتفاعش را از همان می‌گیرد؛ با ``relative`` ارتفاع صفر
می‌شود و چون ``overflow`` آن ``hidden`` است **کل صفحه سفیدِ خالی رندر
می‌شود** — عناصر در DOM هستند ولی هیچ پیکسلی نقاشی نمی‌شود.
"""
from __future__ import annotations

from aibl.report import alborz as _AL
from .theme import (ACCENT, BORDER, BORDER_STRONG, BRAND, BRAND_DEEP, BRAND_SOFT,
                    FONT_STACK, SURFACE, SURFACE_RAISED, SURFACE_SUNKEN, TEXT,
                    TEXT_MUTED, TEXT_SECONDARY)


def css() -> str:
    return f"""<style>
/* ── فونت: نام‌های نصبِ ایران‌سنس روی ویندوز یکسان نیست ──────────────
   بسته به اینکه فونت از کجا نصب شده، نامش می‌تواند «IRANSans»،
   «IRANSansWeb»، «IRAN Sans» یا «IRANSansX» باشد. این چند نام به یک
   خانواده گره می‌خورند تا هر کدام نصب بود، همان استفاده شود؛ اگر هیچ‌کدام
   نبود، مرورگر بی‌صدا به گزینهٔ بعدی زنجیره می‌رود. */
@font-face {{ font-family:'IRANSans'; font-style:normal; font-weight:400;
  src: local('IRANSans'), local('IRANSansWeb'), local('IRAN Sans'),
       local('IRANSansX'), local('IRANSans Regular'), local('IRANSansWeb(FaNum)'); }}
@font-face {{ font-family:'IRANSans'; font-style:normal; font-weight:700;
  src: local('IRANSans Bold'), local('IRANSansWeb Bold'), local('IRANSansX Bold'),
       local('IRAN Sans Bold'); }}
@font-face {{ font-family:'IRANSans Light'; font-style:normal; font-weight:300;
  src: local('IRANSans Light'), local('IRANSansWeb Light'),
       local('IRANSansX Light'), local('IRAN Sans Light'); }}

:root {{
  /* رابط همیشه روشن است. بدون این، کنترل‌های خود مرورگر (نوار پیمایش،
     فلش عدد، تقویم) در ویندوزِ تاریک، تیره رندر می‌شوند. */
  color-scheme: light;
  --brand:{BRAND}; --brand-deep:{BRAND_DEEP}; --accent:{ACCENT};
  --surface:{SURFACE}; --raised:{SURFACE_RAISED}; --sunken:{SURFACE_SUNKEN};
  --border:{BORDER}; --border-strong:{BORDER_STRONG};
  --text:{TEXT}; --text-2:{TEXT_SECONDARY}; --text-3:{TEXT_MUTED};
}}
html, body, [class*="css"], .stApp {{
  font-family:{FONT_STACK} !important; direction:rtl;
}}
.stApp {{ background:
    radial-gradient(1200px 620px at 88% -12%, {BRAND_SOFT} 0%, transparent 58%),
    radial-gradient(900px 520px at 4% 108%, #eef4f9 0%, transparent 60%),
    linear-gradient(180deg, {SURFACE} 0%, {SURFACE_SUNKEN} 100%);
}}
[data-testid="stMainBlockContainer"] {{ padding-top:1.1rem; max-width:1500px; }}
[data-testid="stHeader"] {{ background:transparent; }}

/* ── کارت KPI: بلند شدن و عبور نور با هاور (CSS خالص) ── */
.kpi-row {{ display:grid; grid-template-columns:repeat(4,1fr);
  gap:12px; margin:6px 0 4px; }}
@media (max-width:1250px) {{ .kpi-row {{ grid-template-columns:repeat(3,1fr); }} }}
@media (max-width:900px)  {{ .kpi-row {{ grid-template-columns:repeat(2,1fr); }} }}
.kpi {{
  position:relative; overflow:hidden; background:var(--raised);
  border:1px solid var(--border); border-radius:16px; padding:13px 16px 12px;
  box-shadow:0 1px 2px rgba(16,45,77,.05);
  transition:transform .32s cubic-bezier(.2,.8,.2,1),
             box-shadow .32s, border-color .32s;
}}
.kpi::after {{ /* نوار نوری که با هاور عبور می‌کند */
  content:""; position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(115deg,transparent 38%,rgba(255,255,255,.72) 50%,transparent 62%);
  transform:translateX(-130%); transition:transform .78s ease;
}}
.kpi:hover {{ transform:translateY(-5px);
  box-shadow:0 14px 34px rgba(16,45,77,.13); border-color:var(--border-strong); }}
.kpi:hover::after {{ transform:translateX(130%); }}
.kpi .lab {{ font-size:12px; color:var(--text-2); letter-spacing:.1px; }}
.kpi .val {{ font-size:27px; font-weight:700; color:var(--text); line-height:1.2;
  margin-top:5px; font-variant-numeric:tabular-nums; }}
.kpi .sub {{ font-size:11px; color:var(--text-3); margin-top:5px; }}
.kpi .bar {{ height:3px; border-radius:2px; margin-top:11px; opacity:.92;
  transition:height .32s; }}
.kpi:hover .bar {{ height:5px; }}
.kpi .ico {{ font-size:12px; margin-left:5px; }}

/* ── نشان طبقه بحرانی: رنگ + آیکن + برچسب، هرگز فقط رنگ ── */
.band {{ display:inline-flex; align-items:center; gap:6px; border-radius:999px;
  padding:3px 11px 3px 9px; font-size:12px; font-weight:600; line-height:1.7;
  border:1px solid transparent; transition:transform .2s, box-shadow .2s; }}
.band:hover {{ transform:translateY(-1px); box-shadow:0 4px 12px rgba(0,0,0,.10); }}
.band .g {{ width:9px; height:9px; border-radius:50%; flex:none; }}

/* ── پنل‌ها ── */
.panel {{ background:var(--raised); border:1px solid var(--border);
  border-radius:18px; padding:14px 18px; margin:8px 0 4px;
  transition:border-color .3s, box-shadow .3s; }}
.panel:hover {{ border-color:var(--border-strong);
  box-shadow:0 10px 30px rgba(16,45,77,.08); }}
.panel h3 {{ margin:0 0 3px; font-size:16px; font-weight:700; color:var(--text); }}
.panel .hint {{ font-size:12px; color:var(--text-3); margin:0 0 12px; }}

/* ── نوار پرشدگی فیلد ── */
.fill {{ height:6px; border-radius:3px; background:var(--sunken);
  overflow:hidden; margin-top:5px; }}
.fill > i {{ display:block; height:100%; border-radius:3px;
  background:linear-gradient(90deg,var(--brand),#2fb0a6); transition:width .5s; }}

/* ── ویجت‌های Streamlit ── */
.stButton>button, .stDownloadButton>button {{
  border-radius:11px; font-family:inherit; font-weight:600; border:1px solid var(--border-strong);
  transition:transform .2s, box-shadow .2s, background .2s; }}
.stButton>button:hover, .stDownloadButton>button:hover {{
  transform:translateY(-2px); box-shadow:0 8px 20px rgba(16,45,77,.14);
  border-color:var(--brand); }}
.stTabs [data-baseweb="tab"] {{ font-family:inherit; font-weight:600; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
[data-testid="stSidebar"] {{ background:linear-gradient(180deg,#fff,{SURFACE_SUNKEN}); }}
[data-testid="stSidebar"] * {{ font-family:{FONT_STACK} !important; }}
[data-testid="stMetricValue"] {{ font-variant-numeric:tabular-nums; }}
.stAlert {{ border-radius:14px; }}
div[data-testid="stDataFrame"] {{ border-radius:12px; overflow:hidden;
  border:1px solid var(--border); }}


/* ── فونت: باید به **همه** عناصر برسد ──────────────────────────────────
   CSS قبلی فقط html/body/.stApp را هدف می‌گرفت و ویجت‌های داخلی
   Streamlit (اسلایدر، تب، جدول، دکمه) روی فونت پیش‌فرض «Source Sans»
   می‌ماندند — اندازه‌گیری: ۱۶۵ عنصر با فونت اشتباه. انتخابگر عام لازم
   است چون کلاس‌های Streamlit هش‌شده و ناپایدارند. */
/* منوها و پاپ‌آورهای baseweb بیرون از `.stApp` و مستقیم زیر `body`
   رندر می‌شوند؛ انتخابگرهای قبلی به آن‌ها نمی‌رسید و روی «Source Sans»
   می‌ماندند. `body *` تنها انتخابگری است که پرتال‌ها را هم می‌گیرد. */
html, body, body * {{
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
small, .stCaption {{ color: var(--text-2) !important; }}

/* چیپ‌های multiselect: متن روشن روی پس‌زمینه برند */
[data-baseweb="tag"] {{ background: var(--brand) !important; }}
[data-baseweb="tag"], [data-baseweb="tag"] * ,
[data-baseweb="tag"] span {{ color: #ffffff !important; }}

/* تب‌ها */
.stTabs [data-baseweb="tab"] {{ color: var(--text-2) !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
  color: var(--brand) !important; font-weight: 700; }}

/* جدول و متریک */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ color: var(--text-2) !important; }}
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
   رابط و پوستر و گزارش باید یک چیز به‌نظر برسند. مقدارها از
   `aibl/report/alborz.py` می‌آیند؛ اینجا فقط مصرف می‌شوند. */
.stApp {{
  background: {_AL.page_gradient_css()} !important;
}}
[data-testid="stMainBlockContainer"] {{ max-width:1500px; }}

/* کارت: بدون حاشیهٔ خاکستری. عمق از دو لایه سایه و لبهٔ سفید داخلی. */
.panel, [data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {{
  border-radius:{_AL.RADIUS['panel']}px;
}}
.panel {{
  background:{_AL.CARD} !important;
  border:1px solid {_AL.CARD_EDGE} !important;
  box-shadow:{_AL.shadow_css()} !important;
}}
.panel:hover {{ box-shadow:{_AL.shadow_css()} !important; }}
.kpi {{
  background:{_AL.CARD} !important;
  border:1px solid {_AL.CARD_EDGE} !important;
  border-radius:{_AL.RADIUS['sm']+4}px !important;
  box-shadow:{_AL.shadow_css()} !important;
}}
div[data-testid="stDataFrame"] {{
  border-radius:{_AL.RADIUS['sm']}px; border:1px solid {_AL.HAIRLINE};
}}

/* ══════════════════════════════════════════════════════════════════════
   کف خوانایی — رابط نباید به تم Streamlit وابسته باشد
   ══════════════════════════════════════════════════════════════════════
   این بخش عمداً **آخر** فایل است تا در برابری خاص‌بودن (specificity)
   برنده شود.

   چه اتفاقی افتاد: `.streamlit/config.toml` در بسته‌بندی جا افتاد. بدون
   آن، Streamlit تم پیش‌فرضش را می‌گذارد و آن تم از `prefers-color-scheme`
   مرورگر پیروی می‌کند. روی ویندوزِ حالت‌تاریک، Streamlit متن را
   `#FAFAFA` کرد در حالی که CSS ما پس‌زمینه را سبز روشن آکوا کرده بود:
   نوار کناری، برچسب فیلترها و تراشه‌ها **نامرئی** شدند — نه حذف، فقط
   دیده‌نشدنی؛ و کاربر فکر کرد امکانات از بین رفته‌اند.

   حالا سه لایه هست و هر کدام به‌تنهایی کافی است: پیکربندی بسته‌بندی‌شده،
   متغیر محیطیِ راه‌انداز، و همین CSS. */

/* سطح و متن پایه */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
  background-color: var(--surface);
  color: var(--text);
}}
/* هر چیزی که رنگ متن صریح نگرفته، رنگ متن آکوا می‌گیرد. بدون
   !important تا رنگ‌های درون‌خطی (تراشهٔ طبقه، KPI) دست‌نخورده بمانند. */
.stApp, .stApp p, .stApp span, .stApp li, .stApp td, .stApp th,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp summary, .stApp strong, .stApp em {{ color: var(--text); }}

/* نوار کناری — جایی که فاجعه بیشترین اثر را داشت */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  background: linear-gradient(180deg, var(--raised), var(--sunken)) !important;
}}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] summary {{
  color: var(--text);
}}

/* ورودی‌ها، انتخابگرها و منوهای شناور (پرتال، بیرون از .stApp) */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, [data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"], [data-baseweb="calendar"], [role="option"],
input, textarea, select {{
  background-color: var(--raised) !important;
  color: var(--text) !important;
}}
[data-baseweb="menu"] li, [role="option"], [role="option"] * {{
  color: var(--text) !important;
}}
[role="option"]:hover, [role="option"][aria-selected="true"] {{
  background-color: var(--sunken) !important;
}}
::placeholder {{ color: var(--text-3) !important; opacity:1; }}

/* پوستهٔ ورودی‌ها. در این نسخهٔ Streamlit، ویجت‌های baseweb دیگر
   `data-baseweb` روی خودشان ندارند و عنصری که واقعاً رنگ می‌گیرد هیچ
   شناسه‌ای ندارد — فقط از روی جایگاهش زیر `data-testid` والد پیدا
   می‌شود. اندازه‌گیری‌شده روی DOM زنده، نه حدس. */
[data-testid="stMultiSelect"] > div > div,
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stTextArea"] > div > div {{
  background-color: var(--raised) !important;
  border-color: var(--border) !important;
}}
/* تراشهٔ انتخاب‌شده: پیش‌فرض Streamlit قرمز `#FF4B4B` است — نه رنگ
   برند، و با متن تیره کنتراست ضعیفی می‌دهد. */
[data-testid="stMultiSelectTagsContainer"] > span > span {{
  background-color: var(--brand) !important;
}}
[data-testid="stMultiSelectTagsContainer"] > span > span,
[data-testid="stMultiSelectTagsContainer"] > span > span * {{
  color: #ffffff !important;
}}

/* نوار ابزار بالای صفحه (منوی سه‌نقطه و Deploy) */
[data-testid="stToolbar"], [data-testid="stToolbar"] * ,
[data-testid="stMainMenu"], [data-testid="stMainMenu"] * {{
  color: var(--text-2) !important;
}}

/* جدول داده — شبکه، سرستون و سلول را خودش نقاشی می‌کند */
[data-testid="stDataFrame"], [data-testid="stDataFrame"] * {{
  color: var(--text);
}}
[data-testid="stDataFrame"] {{ background: var(--raised); }}

/* expander و کانتینرهای حاشیه‌دار */
[data-testid="stExpander"], [data-testid="stExpanderDetails"],
[data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {{
  background-color: transparent;
}}
[data-testid="stExpander"] details {{
  background: var(--raised); border-color: var(--border); }}

/* ── احترام به کاهش حرکت ── */
@media (prefers-reduced-motion: reduce) {{
  .kpi, .kpi::after, .panel, .band, .stButton>button, .fill > i {{
    transition:none !important; }}
  .kpi:hover {{ transform:none; }}
}}
</style>"""


def kpi_card(label: str, value: str, sub: str, color: str, icon: str = "") -> str:
    ic = f'<span class="ico">{icon}</span>' if icon else ""
    return (f'<div class="kpi"><div class="lab">{ic}{label}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div>'
            f'<div class="bar" style="background:{color}"></div></div>')


def band_chip(color: str, icon: str, label: str, text: str = "") -> str:
    """تراشهٔ طبقه — نقطه رنگ خام، متن رنگ تیره‌شدهٔ خوانا.

    پس‌زمینهٔ تراشه، همان رنگ وضعیت با ۱۰٪ شفافیت است. متن با رنگ خام
    روی آن ته‌رنگ ۲٫۰۶ تا ۴٫۴۱ کنتراست می‌داد — زیر حد. ``text`` رنگ
    تیره‌شدهٔ محاسبه‌شده است؛ اگر داده نشود، رفتار قبلی حفظ می‌شود.
    """
    ink = text or color
    return (f'<span class="band" style="background:{color}1a;color:{ink};'
            f'border-color:{color}44"><span class="g" style="background:{color}">'
            f'</span>{icon} {label}</span>')
