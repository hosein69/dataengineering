# -*- coding: utf-8 -*-
"""منطق خالص داشبورد — بدون وابستگی به Streamlit.

## چرا جدا شده

Streamlit در زمان import کد سطح-ماژول را اجرا می‌کند، پس فایل داشبورد
به‌تنهایی قابل تست خودکار نیست. هر چیزی که *منطق* است (پالت، ساخت کارت،
تولید HTML، محاسبه KPI) اینجاست تا با تست عادی سنجیده شود و
``dashboard.py`` فقط لایه نمایش بماند.
"""
from __future__ import annotations

__contract__ = 1

import html as _html
from typing import Any, Dict, List, Optional

import pandas as pd

# ── پالت: آکوا، طیف سبز، سفید، خاکستری ──
AQUA_DEEP, AQUA, AQUA_SOFT = "#0F6E6E", "#1E9E9E", "#7FC9C2"
GREEN_SOFT, GREY, GREY_BG, WHITE = "#D9EDE7", "#5A6B6B", "#F2F5F5", "#FFFFFF"
RED, AMBER, GREEN = "#C0392B", "#F39C12", "#27AE60"

BAND_COLORS: Dict[str, str] = {
    "توقف خط": RED, "بحرانی": "#C0392B", "در حال بحرانی شدن": AMBER,
    "تحت نظر": "#F1C40F", "ایمن": GREEN, "بدون مصرف": "#95A5A6",
    "نامشخص": "#95A5A6",
}

#: ستون‌هایی که در جدول جزئیات نشان داده می‌شوند (به همین ترتیب)
DETAIL_COLUMNS: List[str] = [
    "KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL", "KEY_REG",
    "طبقه بحرانی", "مقاومت (روز)", "موجودی کل قابل احتساب", "نیاز روزانه",
    "BL_CRITICAL", "BL_CRITICAL_MATERIALS", "BL_CRITICAL_REASON",
    "ORDER_CRITICAL", "ORDER_CRITICAL_MATERIALS", "ORDER_CRITICAL_REASON",
    "روزهای رسوب", "مانده تعهد", "طبقه ریسک", "CANONICAL_EXPERT",
]


def num(df: pd.DataFrame, col: str) -> pd.Series:
    """ستون را عددی می‌کند؛ اگر نبود، سری تهی هم‌طول برمی‌گرداند."""
    if col not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def band_count(df: pd.DataFrame, code: str) -> int:
    """تعداد **متریال یکتا** در یک طبقه بحرانی — نه تعداد ردیف."""
    if "کد طبقه بحرانی" not in df.columns:
        return 0
    sub = df[df["کد طبقه بحرانی"] == code]
    if "KEY_MATERIAL" not in sub.columns:
        return int(len(sub))
    return int(sub["KEY_MATERIAL"].replace("", pd.NA).nunique())


def kpis(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """کارت‌های بالای داشبورد. هر کارت یک سؤال تصمیم‌ساز را جواب می‌دهد."""
    stockout = band_count(df, "STOCKOUT")
    critical = band_count(df, "CRITICAL")
    becoming = band_count(df, "BECOMING_CRITICAL")
    low = num(df, "مقاومت (روز)").min()
    bal = float(num(df, "مانده تعهد").fillna(0).sum())
    overdue = int((num(df, "روزهای تأخیر").fillna(0) > 0).sum())
    crit_bl = int(df.loc[df["BL_CRITICAL"].astype(bool), "CANONICAL_BL"].replace("", pd.NA).nunique()) if "BL_CRITICAL" in df and "CANONICAL_BL" in df else 0
    crit_ord = int(df.loc[df["ORDER_CRITICAL"].astype(bool), "CANONICAL_ORDER"].replace("", pd.NA).nunique()) if "ORDER_CRITICAL" in df and "CANONICAL_ORDER" in df else 0
    # «سنجیده نشد» ≠ «صفر». وقتی سورس خرید بارگذاری نشده، نباید کارت سبز
    # نشان دهد که انگار همه سفارش‌ها مالک دارند.
    cov_measured = ("COMMERCIAL_COVERAGE_STATE" in df
                    and (df["COMMERCIAL_COVERAGE_STATE"] == "measured").any())
    missing_commercial = int(df.loc[df["ORDER_MISSING_COMMERCIAL_EXPERT"].astype(bool), "CANONICAL_ORDER"].replace("", pd.NA).nunique()) if "ORDER_MISSING_COMMERCIAL_EXPERT" in df and "CANONICAL_ORDER" in df else 0
    stuck = num(df, "روزهای رسوب")
    risk = num(df, "امتیاز ریسک")
    return [
        {"label": "توقف خط", "value": stockout, "sub": "موجودی صفر",
         "critical": stockout > 0},
        {"label": "قطعات بحرانی", "value": critical, "sub": "مقاومت زیر ۱۰ روز",
         "critical": critical > 0},
        {"label": "در حال بحرانی شدن", "value": becoming,
         "sub": "بین ۱۰ تا ۲۰ روز", "critical": False},
        {"label": "کمترین مقاومت",
         "value": "—" if pd.isna(low) else f"{low:,.1f} روز",
         "sub": "بحرانی‌ترین قطعه",
         "critical": bool(not pd.isna(low) and low < 10)},
        {"label": "جمع مانده تعهد", "value": bal, "sub": "سورس NTSW",
         "critical": False},
        {"label": "تعهدات معوق", "value": overdue, "sub": "عبور از مهلت قانونی",
         "critical": overdue > 0},
        {"label": "میانگین رسوب",
         "value": "—" if not stuck.notna().any() else f"{stuck.mean():,.1f} روز",
         "sub": "از تاریخ تخلیه", "critical": False},
        {"label": "بارنامه‌های بحرانی", "value": crit_bl, "sub": "حداقل یک متریال بحرانی", "critical": crit_bl > 0},
        {"label": "سفارش‌های بحرانی", "value": crit_ord, "sub": "حداقل یک متریال بحرانی", "critical": crit_ord > 0},
        {"label": "سفارش خارج از Commercial Expert Data",
         "value": missing_commercial if cov_measured else "سنجیده نشد",
         "sub": "بدون انتساب کارشناس خرید" if cov_measured
                else "سورس خرید در این اجرا بارگذاری نشد",
         "critical": bool(cov_measured and missing_commercial > 0)},
        {"label": "میانگین ریسک",
         "value": "—" if not risk.notna().any() else f"{risk.mean():,.1f}",
         "sub": "موتور ۸ مؤلفه‌ای", "critical": False},
    ]


def card_html(label: str, value: Any, sub: str = "",
              critical: bool = False) -> str:
    cls = "kpi crit" if critical else "kpi"
    v = f"{value:,.0f}" if isinstance(value, (int, float)) else str(value)
    return (f'<div class="{cls}"><div class="lbl">{_html.escape(label)}</div>'
            f'<div class="val">{_html.escape(v)}</div>'
            f'<div class="sub">{_html.escape(sub)}</div>'
            f'<div class="bar"></div></div>')


def detail_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in DETAIL_COLUMNS if c in df.columns]


def export_html(df: pd.DataFrame, ref_date: str,
                cards: Optional[List[Dict[str, Any]]] = None) -> str:
    """HTML مستقل با CSS و JS درون‌خط.

    بدون هیچ وابستگی بیرونی (به‌جز فونت) تا آفلاین هم باز شود، و با دکمه
    «ذخیره به PDF» که فقط پنجره چاپ مرورگر را باز می‌کند — نه کتابخانه
    اضافه، نه سرور.
    """
    cards = cards if cards is not None else kpis(df)
    cols = detail_columns(df) or list(df.columns)[:12]
    table = df[cols].head(500).to_html(index=False, classes="tbl",
                                       border=0, escape=True)
    parts = []
    for c in cards:
        v = c["value"]
        vs = f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)
        parts.append(
            f'<div class="c{" crit" if c.get("critical") else ""}">'
            f'<div class="l">{_html.escape(str(c["label"]))}</div>'
            f'<div class="v">{_html.escape(vs)}</div>'
            f'<div class="s">{_html.escape(str(c.get("sub", "")))}</div></div>')
    kpi_html = "".join(parts)

    return f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش AIBL — {_html.escape(ref_date)}</title>
<style>

*{{box-sizing:border-box}}
body{{font-family:"IRANSans Light",IRANSans,Tahoma,Arial,sans-serif;color:#20302f;margin:0;padding:28px;
     background:linear-gradient(135deg,{WHITE} 0%,{GREY_BG} 100%);min-height:100vh}}
h1{{color:{AQUA_DEEP};margin:0 0 4px;font-weight:800}}
.sub{{color:{GREY};font-size:.85rem;margin-bottom:22px}}
.k{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}}
.c{{background:#fff;border:1px solid rgba(15,110,110,.15);border-radius:16px;
    padding:16px 20px;min-width:158px;box-shadow:0 4px 18px rgba(15,110,110,.08)}}
.c.crit{{border-color:rgba(146,43,33,.32)}}
.c.crit .v{{color:{RED}}}
.c .l{{font-size:.76rem;color:{GREY}}}
.c .v{{font-size:1.8rem;font-weight:800;color:{AQUA_DEEP};font-variant-numeric:tabular-nums}}
.c .s{{font-size:.68rem;color:{GREY};opacity:.8;margin-top:4px}}
.tbl{{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;
      overflow:hidden;box-shadow:0 4px 18px rgba(15,110,110,.08);font-size:.78rem}}
.tbl th{{background:{AQUA_DEEP};color:#fff;padding:9px;text-align:center;font-weight:600}}
.tbl td{{padding:7px 9px;border-bottom:1px solid {GREEN_SOFT};text-align:center}}
.tbl tr:hover td{{background:{GREEN_SOFT}}}
.btn{{position:fixed;bottom:22px;left:22px;background:{AQUA_DEEP};color:#fff;border:0;
      border-radius:12px;padding:11px 18px;font-family:inherit;font-size:.9rem;
      cursor:pointer;box-shadow:0 6px 20px rgba(15,110,110,.28)}}
.btn:hover{{background:{AQUA}}}
@media print{{.btn{{display:none}}body{{background:#fff;padding:0}}
              .c{{break-inside:avoid;box-shadow:none}}}}
</style></head><body>
<h1>مغز شناختی لجستیک</h1>
<div class="sub">گزارش {_html.escape(ref_date)} — {len(df):,} پرونده</div>
<div class="k">{kpi_html}</div>
{table}
<button class="btn" onclick="window.print()">ذخیره به PDF</button>
<script>
document.querySelectorAll('.c').forEach(function(el,i){{
  el.style.opacity=0; el.style.transform='translateY(10px)';
  el.style.transition='all .5s cubic-bezier(.2,.8,.2,1)';
  setTimeout(function(){{el.style.opacity=1; el.style.transform='none';}}, 90*i);
}});
</script></body></html>"""
