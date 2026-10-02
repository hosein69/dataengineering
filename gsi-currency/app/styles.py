# -*- coding: utf-8 -*-
"""CSS رابط — راست‌به‌چپ، واکنش‌گر به موس، بدون وابستگی به JS.

⚠️ اینجا هرگز ``position`` را روی ``.stApp`` بازنویسی نکنید. Streamlit خودش
آن را ``position:absolute; inset:0`` می‌گذارد و ``#stAppViewContainer`` که
``absolute`` است ارتفاعش را از همان می‌گیرد؛ با ``relative`` ارتفاع صفر
می‌شود و چون ``overflow`` آن ``hidden`` است **کل صفحه سفیدِ خالی رندر
می‌شود** — عناصر در DOM هستند ولی هیچ پیکسلی نقاشی نمی‌شود.
"""
from __future__ import annotations

from .theme import (ACCENT, BORDER, BORDER_STRONG, BRAND, BRAND_DEEP, BRAND_SOFT,
                    FONT_STACK, SURFACE, SURFACE_RAISED, SURFACE_SUNKEN, TEXT,
                    TEXT_MUTED, TEXT_SECONDARY)
from gsi.design import icons as DI
from gsi.design import tokens as DT

_ICONS_CSS = DI.minimal_css()
_GRAD = f"linear-gradient(135deg,{DT.TEAL_PALETTE[3]} 0%,{DT.TEAL_PALETTE[7]} 100%)"


def css() -> str:
    return f"""<style>
:root {{
  --brand:{BRAND}; --brand-deep:{BRAND_DEEP}; --accent:{ACCENT};
  --surface:{SURFACE}; --raised:{SURFACE_RAISED}; --sunken:{SURFACE_SUNKEN};
  --border:{BORDER}; --border-strong:{BORDER_STRONG};
  --text:{TEXT}; --text-2:{TEXT_SECONDARY}; --text-3:{TEXT_MUTED};
  --paper:{DT.SURFACE_PAPER}; --paper-soft:{DT.SURFACE_PAPER_SOFT};
  --paper-rule:{DT.PAPER_RULE}; --pencil:{DT.PENCIL}; --aqua-mist:{DT.AQUA_MIST};
}}
html, body, [class*="css"], .stApp {{
  font-family:{FONT_STACK} !important; direction:rtl;
}}
.stApp {{ background:
    radial-gradient(1000px 420px at 96% -10%, var(--aqua-mist) 0%, transparent 62%),
    linear-gradient(180deg,#ffffff 0%, {SURFACE} 62%, var(--paper-soft) 140%);
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
  box-shadow:0 1px 2px rgba(15,53,56,.05);
  transition:transform .32s cubic-bezier(.2,.8,.2,1),
             box-shadow .32s, border-color .32s;
}}
.kpi::after {{ /* نوار نوری که با هاور عبور می‌کند */
  content:""; position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(115deg,transparent 38%,rgba(255,255,255,.72) 50%,transparent 62%);
  transform:translateX(-130%); transition:transform .78s ease;
}}
.kpi:hover {{ transform:translateY(-2px);
  box-shadow:0 8px 22px rgba(15,53,56,.09); border-color:var(--border-strong); }}
.kpi:hover::after {{ transform:translateX(130%); }}
.kpi .lab {{ font-size:12px; color:var(--text-2); letter-spacing:.1px; }}
.kpi .val {{ font-size:27px; font-weight:700; color:var(--text); line-height:1.2;
  margin-top:5px; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }}
.kpi .val.is-long {{ font-size:17px; line-height:1.5; }}
.kpi .val bdi {{ unicode-bidi:isolate; }}
.kpi .val .amt {{ display:block; direction:ltr; text-align:right; }}
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
  box-shadow:0 5px 16px rgba(15,53,56,.055); }}
.panel h3 {{ margin:0 0 3px; font-size:16px; font-weight:700; color:var(--text); }}
.panel .hint {{ font-size:12px; color:var(--text-3); margin:0 0 12px; }}

/* ── نوار پرشدگی فیلد ── */
.fill {{ height:6px; border-radius:3px; background:var(--sunken);
  overflow:hidden; margin-top:5px; }}
.fill > i {{ display:block; height:100%; border-radius:3px;
  background:linear-gradient(90deg,var(--brand),#26b2b0); transition:width .5s; }}

/* ── ویجت‌های Streamlit ── */
.stButton>button, .stDownloadButton>button {{
  border-radius:11px; font-family:inherit; font-weight:600; border:1px solid var(--border-strong);
  transition:transform .2s, box-shadow .2s, background .2s; }}
.stButton>button:hover, .stDownloadButton>button:hover {{
  transform:translateY(-2px); box-shadow:0 8px 20px rgba(15,53,56,.14);
  border-color:var(--brand); }}
.stTabs [data-baseweb="tab"] {{ font-family:inherit; font-weight:600; }}
.stTabs [data-baseweb="tab-list"] {{ gap:4px; }}
[data-testid="stSidebar"] {{ background:linear-gradient(180deg,#fff 0%,var(--paper-soft) 145%); border-left:1px solid var(--paper-rule); }}
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
html, body, .stApp, .stApp *, [data-testid] , [data-testid] * ,
[class*="st-"], [class*="st-"] * {{
  font-family: {FONT_STACK} !important;
}}
/* استثنا: کد و عدد تک‌فاصله */
code, pre, kbd, samp, [data-testid="stCode"] * {{
  font-family: 'Cascadia Mono','Consolas','Courier New',monospace !important;
}}
/* استثنا: آیکن‌های Material خود Streamlit. قاعده عام بالا فونت ligature آیکن را
   هم IRANSans می‌کرد و به‌جای فلش، کلمهٔ «keyboard_arrow_right» روی برچسب
   فارسی expander و دکمه جمع‌کردن سایدبار نوشته می‌شد (اندازه‌گیری‌شده در DOM). */
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons {{
  font-family: 'Material Symbols Rounded','Material Icons' !important;
  font-feature-settings: 'liga' !important;
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
[data-testid="stSliderThumbValue"] {{
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

/* ── GSI Editorial Data Language · ایران مدرن، بدون تزئین افراطی ── */
.gsi-editorial-lead{{position:relative;background:linear-gradient(180deg,#fff,var(--paper-soft));
  border:1px solid var(--paper-rule);border-radius:16px;padding:18px 20px;margin:6px 0 14px;overflow:hidden}}
.gsi-editorial-lead::before{{content:"";position:absolute;right:0;top:0;width:5px;height:100%;background:var(--brand)}}
.gsi-editorial-lead::after{{content:"";position:absolute;left:22px;bottom:13px;width:74px;height:2px;
  background:var(--accent);opacity:.55;transform:rotate(-1deg)}}
.gsi-editorial-kicker{{font-size:11px;font-weight:800;color:var(--brand);letter-spacing:.35px}}
.gsi-editorial-title{{font-size:25px;font-weight:800;line-height:1.5;color:var(--text);margin-top:3px}}
.gsi-editorial-deck{{font-size:12px;color:var(--text-2);max-width:900px;line-height:1.9;margin-top:4px}}
.gsi-paper-note{{background:var(--paper-soft);border:1px solid var(--paper-rule);border-radius:12px;padding:12px 14px}}
.gsi-annotation{{border-right:2px solid var(--accent);padding:7px 12px 7px 8px;color:var(--text-2);font-size:12px}}
.gsi-annotation::before{{content:"✎";color:var(--pencil);margin-left:6px}}
.gsi-data-health{{display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border-radius:999px;
  background:#fff;border:1px solid var(--border);font-size:11px;color:var(--text-2)}}
.gsi-data-health i{{display:block;width:7px;height:7px;border-radius:50%;background:var(--brand)}}
[data-testid="stPlotlyChart"]{{background:linear-gradient(180deg,#fff,var(--paper-soft));border:1px solid var(--border);
  border-radius:14px;padding:4px 6px 2px;box-shadow:0 1px 2px rgba(15,53,56,.035)}}
[data-testid="stMetric"]{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:10px 12px}}


/* ══ لایه مینیمال · کیت طراحی مالک — سفید + طیف فیروزه‌ای، راست‌چین ═══════
   کارت‌ها بدون مرز سنگین با سایه نرم دوطرفه، دکمه/تب/ورودی کپسولی.
   فقط متغیرهای توکن؛ رنگ جدیدی تعریف نمی‌شود. */
.stApp {{ background: var(--surface) !important; }}
[data-testid="stSidebar"] {{ background: var(--raised) !important; border-left: 0 !important;
  box-shadow: {DT.ELEVATION["raised"]}; }}
.kpi, .panel, .gsi-decision-card, .gsi-board-metrics>div, [data-testid="stMetric"],
[data-testid="stPlotlyChart"], .gsi-cockpit-head, .gsi-editorial-lead {{
  background: var(--raised) !important; border-color: transparent !important;
  box-shadow: {DT.ELEVATION["raised"]} !important; border-radius: {DT.RADIUS["lg"]}px !important; }}
.kpi:hover, .panel:hover {{ box-shadow: {DT.ELEVATION["overlay"]} !important; }}
.gsi-editorial-lead::after {{ display: none; }}
.gsi-editorial-lead::before, .gsi-cockpit-head::before {{ display: none; }}
.stButton>button, .stDownloadButton>button {{ border-radius: 999px !important; border-color: transparent !important;
  box-shadow: {DT.ELEVATION["raised"]}; min-height: 42px; }}
.stButton>button:hover, .stDownloadButton>button:hover {{ box-shadow: {DT.ELEVATION["overlay"]}; }}
.stTabs [data-baseweb="tab-list"] {{ border-radius: 999px !important; box-shadow: {DT.ELEVATION["inset"]}; padding: 5px !important; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 999px !important; }}
.stTabs [aria-selected="true"] {{ background: var(--brand) !important; color: #ffffff !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {{
  border-radius: 999px !important; background: var(--sunken) !important; border-color: transparent !important;
  box-shadow: {DT.ELEVATION["inset"]}; }}
[data-baseweb="textarea"] {{ border-radius: {DT.RADIUS["lg"]}px !important; }}
div[data-testid="stDataFrame"] {{ border: 0 !important; border-radius: {DT.RADIUS["lg"]}px;
  box-shadow: {DT.ELEVATION["raised"]}; }}
.fill {{ height: 8px; border-radius: 999px; box-shadow: {DT.ELEVATION["inset"]}; }}
.fill > i {{ border-radius: 999px; background: var(--brand); }}
.band {{ border-radius: 999px; }}
.stAlert {{ border-radius: {DT.RADIUS["lg"]}px; border: 0; }}

/* ══ فرهنگ آیکن مینیمال · فایل مرجع مالک ══════════════════════════════
   کاشی آیکن خطی، دکمه گرادیانی فیروزه‌ای، ناوبری کاشی‌ای، کلید کپسولی. */
{_ICONS_CSS}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"],
.stFormSubmitButton>button {{ background: {_GRAD} !important; color: {DT.TEXT_ON_BRAND} !important;
  border: 0 !important; box-shadow: {DT.ELEVATION["overlay"]} !important; font-weight: 700; }}
.stButton>button[kind="primary"]:hover, .stDownloadButton>button[kind="primary"]:hover {{
  filter: brightness(1.05); color: {DT.TEXT_ON_BRAND} !important; }}
.st-key-gsi_surface [role="radiogroup"] {{ gap: 8px !important; flex-direction: column; }}
.st-key-gsi_surface [role="radiogroup"] > div {{ width: 100%; }}
.st-key-gsi_surface [data-testid="stRadioOption"] {{ width: 100%; margin: 0 !important; padding: 10px 12px !important;
  border-radius: {DT.RADIUS["md"]}px; background: var(--raised); box-shadow: {DT.ELEVATION["raised"]};
  display: flex; align-items: center; color: var(--brand); transition: box-shadow .2s, background .2s; cursor: pointer;
  direction: rtl; justify-content: flex-start; }}
.st-key-gsi_surface [data-testid="stRadioOption"] p {{ color: var(--text); }}
.st-key-gsi_surface [data-testid="stRadioOption"]:hover {{ box-shadow: {DT.ELEVATION["overlay"]}; }}
.st-key-gsi_surface [data-testid="stRadioOption"] > div > div:first-child,
.st-key-gsi_col_lang [data-testid="stRadioOption"] > div > div:first-child {{ display: none !important; }}
.st-key-gsi_surface [role="radiogroup"] > div[data-selected="true"] [data-testid="stRadioOption"] {{
  background: {_GRAD}; box-shadow: {DT.ELEVATION["overlay"]}; color: {DT.TEXT_ON_BRAND}; }}
.st-key-gsi_surface [role="radiogroup"] > div[data-selected="true"] [data-testid="stRadioOption"] p {{
  color: {DT.TEXT_ON_BRAND} !important; font-weight: 700; }}
.st-key-gsi_col_lang [role="radiogroup"] {{ background: var(--sunken); border-radius: 999px; padding: 4px;
  box-shadow: {DT.ELEVATION["inset"]}; gap: 0 !important; display: flex; }}
.st-key-gsi_col_lang [role="radiogroup"] > div {{ flex: 1; }}
.st-key-gsi_col_lang [data-testid="stRadioOption"] {{ justify-content: center; margin: 0 !important; width: 100%;
  padding: 6px 10px !important; border-radius: 999px; cursor: pointer; }}
.st-key-gsi_col_lang [role="radiogroup"] > div[data-selected="true"] [data-testid="stRadioOption"] {{
  background: {_GRAD}; box-shadow: {DT.ELEVATION["raised"]}; }}
.st-key-gsi_col_lang [role="radiogroup"] > div[data-selected="true"] p {{ color: {DT.TEXT_ON_BRAND} !important; font-weight: 700; }}
/* تب‌ها (Streamlit ≥1.5x: stTab / role=tab) — کپسول روی شیار فرورفته */
.stTabs [role="tablist"] {{ background: var(--sunken); border-radius: 999px !important; padding: 5px !important;
  box-shadow: {DT.ELEVATION["inset"]}; gap: 4px !important; border: 0 !important; width: fit-content; max-width: 100%;
  overflow-x: auto; }}
.stTabs [data-testid="stTab"] {{ border-radius: 999px !important; padding: 6px 14px !important; color: var(--text-2);
  display: inline-flex; align-items: center; direction: rtl; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background: {_GRAD} !important; color: {DT.TEXT_ON_BRAND} !important;
  box-shadow: {DT.ELEVATION["raised"]}; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color: {DT.TEXT_ON_BRAND} !important; font-weight: 700; }}
.stTabs .react-aria-SelectionIndicator {{ display: none !important; }}
.kpi .lab {{ display: flex; align-items: center; gap: 10px; }}
.kpi .ico {{ display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px;
  margin: 0; border-radius: {DT.RADIUS["md"]}px; background: var(--raised); box-shadow: {DT.ELEVATION["raised"]};
  font-size: 0; flex: none; }}
.kpi .bar {{ height: 4px; border-radius: 999px; opacity: .55; }}

/* ── احترام به کاهش حرکت ── */
@media (prefers-reduced-motion: reduce) {{
  .kpi, .kpi::after, .panel, .band, .stButton>button, .fill > i {{
    transition:none !important; }}
  .kpi:hover {{ transform:none; }}
}}

/* ══ Figma v1 · Process Operations Cockpit ═══════════════════════════ */
.gsi-cockpit-head{{display:flex;align-items:center;justify-content:space-between;gap:20px;background:linear-gradient(180deg,#fff,var(--paper-soft));border:1px solid var(--paper-rule);border-radius:14px;padding:18px 20px;margin:4px 0 14px;position:relative;overflow:hidden}}
.gsi-cockpit-head::before{{content:"";position:absolute;right:0;top:0;width:5px;height:100%;background:var(--brand)}}
.gsi-cockpit-head h2{{font-size:25px!important;line-height:1.4;margin:2px 0 4px!important;color:var(--text)!important;}}
.gsi-cockpit-head p{{font-size:12px;color:var(--text-2);margin:0}}.gsi-overline{{font-size:11px;font-weight:800;letter-spacing:.6px;color:var(--brand)}}
.gsi-search-ghost{{width:min(360px,34vw);min-height:48px;display:flex;align-items:center;padding:0 14px;border:1px solid var(--border);border-radius:10px;color:var(--text-3);background:var(--raised)}}
.gsi-decision-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 16px}}
.gsi-decision-card{{background:var(--raised);border:1px solid var(--border);border-radius:14px;padding:16px;box-shadow:0 1px 3px rgba(15,53,56,.04)}}
.gsi-decision-card.is-critical{{background:#fdeded;border-color:#a52020}}.gsi-decision-card.is-warning{{background:#fbf3e2;border-color:#7a5a15}}.gsi-decision-card.is-good{{background:#e8f6ec;border-color:#136b13}}
.gsi-eyebrow{{font-size:11px;color:var(--text-3)}}.gsi-metric{{font-size:26px;font-weight:800;line-height:1.2;color:var(--text);margin:5px 0}}.gsi-card-sub{{font-size:12px;color:var(--text-2);line-height:1.65}}
.gsi-process-strip{{display:flex;gap:8px;overflow-x:auto;padding:4px 1px 10px;scrollbar-width:thin}}.gsi-stage{{min-width:92px;flex:1;text-align:center;border:1px solid var(--border);background:var(--sunken);border-radius:9px;padding:10px 6px}}.gsi-stage.is-warning{{background:#fbf3e2;border-color:#7a5a15}}.gsi-stage.is-critical{{background:#fdeded;border-color:#a52020}}.gsi-stage-name{{font-size:12px;font-weight:700;color:var(--text)}}.gsi-stage.is-critical .gsi-stage-name{{color:#a52020}}.gsi-stage-meta{{font-size:11px;color:var(--text-3);margin-top:3px}}
.gsi-kanban-title{{display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:800;color:var(--text);padding:8px 0}}.gsi-kanban-title span{{font-size:11px;background:var(--sunken);border-radius:999px;padding:2px 8px;color:var(--text-2)}}
.gsi-action-card{{background:var(--raised);border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:7px 0}}.gsi-action-key{{font-size:12px;font-weight:800;color:var(--text)}}.gsi-action-title{{font-size:12px;color:var(--brand);font-weight:600;margin-top:4px}}.gsi-action-meta{{font-size:11px;color:var(--text-3);margin-top:4px}}
.gsi-board-metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:4px 0 14px}}.gsi-board-metrics>div{{background:var(--raised);border:1px solid var(--border);border-radius:12px;padding:10px 12px;display:grid;gap:2px}}.gsi-board-metrics b{{font-size:20px;color:var(--text)}}.gsi-board-metrics span{{font-size:10px;color:var(--text-3)}}.gsi-board-metrics .is-critical{{background:#fdeded;border-color:#a52020}}.gsi-board-metrics .is-critical b{{color:#a52020}}
.gsi-action-board{{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(260px,1fr);gap:12px;overflow-x:auto;padding:2px 1px 12px;align-items:start;scrollbar-width:thin}}
.gsi-board-col{{background:var(--sunken);border:1px solid var(--border);border-radius:14px;padding:10px;min-height:210px}}.gsi-board-col>header{{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 4px 10px}}.gsi-board-col>header h3{{font-size:13px!important;margin:0!important}}.gsi-board-col>header span{{background:var(--raised);border:1px solid var(--border);border-radius:999px;padding:2px 8px;font-size:10px;font-weight:800}}
.gsi-board-stack{{display:grid;gap:9px}}.gsi-board-card{{background:var(--raised);border:1px solid var(--border);border-right:3px solid var(--brand);border-radius:10px;padding:11px;display:grid;gap:6px;box-shadow:0 1px 3px rgba(15,53,56,.04)}}.gsi-board-card.is-critical{{border-right-color:#a52020}}.gsi-board-card.is-warning{{border-right-color:#7a5a15}}.gsi-board-card-top{{display:flex;align-items:center;justify-content:space-between;gap:8px}}.gsi-case-key{{font:800 11px var(--font);color:var(--brand);direction:ltr}}.gsi-priority{{font-size:9px;font-weight:800;border:1px solid var(--border);border-radius:999px;padding:2px 6px;color:var(--text-2)}}.gsi-board-card h4{{font-size:12.5px!important;line-height:1.7;margin:0!important;color:var(--text)!important}}.gsi-board-meta{{font-size:10.5px;color:var(--text-3)}}.gsi-board-card p{{font-size:10.5px!important;color:var(--text-2)!important;margin:0!important}}.gsi-evidence-gap{{font-size:10px;color:#7a5a15;background:#fbf3e2;border-radius:7px;padding:5px 7px}}.gsi-board-empty,.gsi-board-more{{font-size:10.5px;color:var(--text-3);padding:10px;text-align:center}}
.gsi-res-row{{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);padding:10px 6px;font-size:12px}}.gsi-res-row span{{font-variant-numeric:tabular-nums;font-weight:800}}.gsi-res-row.is-critical span{{color:#a52020}}.gsi-res-row.is-warning span{{color:#7a5a15}}
[data-testid="stVerticalBlockBorderWrapper"]{{border-radius:14px!important}}.stTabs [data-baseweb="tab-list"]{{gap:4px;background:var(--sunken);border-radius:12px;padding:4px}}.stTabs [data-baseweb="tab"]{{min-height:44px;border-radius:9px;padding:8px 13px}}.stTabs [aria-selected="true"]{{background:var(--raised)!important;color:var(--brand)!important;box-shadow:0 1px 3px rgba(15,53,56,.08)}}
@media(max-width:1024px){{.gsi-decision-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.gsi-search-ghost{{display:none}}}}
@media(max-width:768px){{[data-testid="stMainBlockContainer"]{{padding-left:.8rem;padding-right:.8rem}}.gsi-cockpit-head{{padding:14px}}.gsi-decision-grid{{grid-template-columns:1fr 1fr}}.gsi-metric{{font-size:19px}}.gsi-process-strip{{padding-bottom:12px}}.gsi-stage{{min-width:88px}}.stDataFrame{{overflow-x:auto}}}}
@media(max-width:480px){{.gsi-decision-grid{{grid-template-columns:1fr}}.gsi-cockpit-head h2{{font-size:20px!important}}.gsi-decision-card{{padding:14px}}.gsi-process-strip{{margin-inline:-4px}}.stTabs [data-baseweb="tab"]{{font-size:11px;padding:7px 9px}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}}}
</style>"""


def kpi_card(label: str, value: str, sub: str, color: str, icon: str = "") -> str:
    """کارت KPI. مقدار غیرعددی (پیام «جمع قابل اتکا نیست») عدد نیست:
    به‌جای نوشتن جمله با اندازه عدد، «—» نمایش داده و پیام به زیرنویس می‌رود.
    مبلغ چندارزی (``1,000.00 EUR | 20.00 USD``) با اندازه کوچک‌تر و ایزوله
    جهت (bdi) نمایش داده می‌شود تا در متن راست‌به‌چپ جابه‌جا نشود."""
    if icon and (icon in DI.GLYPH_TO_ICON or icon in DI.NAMES):
        ic = f'<span class="ico" style="color:{color}">{DI.icon(icon, 18)}</span>'
    else:
        ic = f'<span class="ico">{icon}</span>' if icon else ""
    text = str(value)
    cls = "val"
    if text not in ("", "—") and not any(ch.isdigit() for ch in text):
        sub = f"{text} · {sub}" if sub else text
        text = "—"
    elif len(text) > 14:
        cls = "val is-long"
        if " · " in text:                       # افشای پوشش ← زیرنویس، نه کنار عدد
            text, note = text.split(" · ", 1)
            sub = f"{note} · {sub}" if sub else note
        text = "".join(f'<bdi class="amt">{t.strip()}</bdi>' for t in text.split("|"))
    return (f'<div class="kpi"><div class="lab">{ic}{label}</div>'
            f'<div class="{cls}">{text}</div><div class="sub">{sub}</div>'
            f'<div class="bar" style="background:{color}"></div></div>')


def band_chip(color: str, icon: str, label: str) -> str:
    return (f'<span class="band" style="background:{color}1a;color:{color};'
            f'border-color:{color}44"><span class="g" style="background:{color}">'
            f'</span>{icon} {label}</span>')
