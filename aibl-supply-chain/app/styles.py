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


def css() -> str:
    return f"""<style>
:root {{
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


def band_chip(color: str, icon: str, label: str) -> str:
    return (f'<span class="band" style="background:{color}1a;color:{color};'
            f'border-color:{color}44"><span class="g" style="background:{color}">'
            f'</span>{icon} {label}</span>')
