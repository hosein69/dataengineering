# -*- coding: utf-8 -*-
"""تب تحلیل — جدول متقاطع و توزیع، روی هر ۳۶۷ فیلد.

تحلیل قبلی به چند نمودار ثابت محدود بود. اینجا کاربر خودش بُعد سطر،
بُعد ستون و سنجه را انتخاب می‌کند؛ همان چیزی که یک تحلیلگر در Excel
Pivot می‌سازد، ولی روی خروجی کامل خط لوله و با نام فارسی ستون‌ها.

نکته طراحی: نقشه حرارتی با **یک هیو** (آبی، روشن→تیره) رنگ می‌گیرد،
چون بزرگی پیوسته است نه هویت. رنگین‌کمان استفاده نمی‌شود.
"""
from __future__ import annotations

from typing import Callable, Dict, List

import pandas as pd
import streamlit as st

from .theme import SEQUENTIAL, SERIES, STATUS

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

AGGS: Dict[str, str] = {
    "تعداد ردیف": "count",
    "تعداد یکتا": "nunique",
    "جمع": "sum",
    "میانگین": "mean",
    "میانه": "median",
    "کمینه": "min",
    "بیشینه": "max",
}


def _short(t, n: int = 26) -> str:
    t = str(t)
    return t if len(t) <= n else t[:n - 1] + "…"


def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) or \
        pd.to_numeric(s, errors="coerce").notna().mean() > 0.6


def render(fdf: pd.DataFrame, catalog, lab: Callable[[str], str]) -> None:
    if fdf.empty:
        st.info("فیلتر فعلی هیچ ردیفی برنمی‌گرداند.")
        return

    cols = list(fdf.columns)
    # ابعاد خوب: کاردینالیتی پایین. سنجه‌های خوب: عددی.
    dims, measures = [], []
    for c in cols:
        s = fdf[c]
        try:
            nu = s.nunique(dropna=True)
        except Exception:
            continue
        if 0 < nu <= max(60, len(fdf) // 2):
            dims.append(c)
        if _is_numeric(s):
            measures.append(c)

    if not dims:
        st.info("بُعد مناسبی (ستون با کاردینالیتی پایین) در فیلتر فعلی نیست.")
        return

    def fmt(c: str) -> str:
        return lab(c)

    with st.container(border=True):
        st.markdown("##### ⊞ جدول متقاطع")
        st.caption("بُعد سطر و ستون را انتخاب کنید و یک سنجه بگذارید. "
                   "روی همان فیلتر فعلی محاسبه می‌شود.")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        row_dim = c1.selectbox("بُعد سطر", dims, format_func=fmt,
                               index=_pref(dims, ["ORG_DEPT", "بحرانی (کوتاه)"]))
        col_dim = c2.selectbox("بُعد ستون", ["— بدون —"] + dims,
                               format_func=lambda c: "— بدون —" if c == "— بدون —" else fmt(c),
                               index=_pref_offset(dims, ["بحرانی (کوتاه)", "روش حمل"]))
        agg_name = c3.selectbox("سنجه", list(AGGS.keys()), index=0)
        measure = None
        if AGGS[agg_name] not in ("count",):
            opts = measures if AGGS[agg_name] != "nunique" else cols
            if not opts:
                st.warning("ستون عددی برای این سنجه موجود نیست.")
                return
            measure = c4.selectbox("ستون سنجه", opts, format_func=fmt,
                                   index=_pref(opts, ["مانده تعهد", "مقاومت (روز)"]))

        try:
            piv = _pivot(fdf, row_dim, None if col_dim == "— بدون —" else col_dim,
                         AGGS[agg_name], measure)
        except Exception as ex:
            st.error(f"محاسبه ممکن نشد: {ex}")
            return
        if piv.empty:
            st.info("نتیجه‌ای برای این ترکیب نیست.")
            return

        if HAS_PLOTLY and piv.shape[1] > 1:
            z = piv.values.astype(float)
            fig = go.Figure(go.Heatmap(
                z=z,
                x=[_short(c, 20) for c in piv.columns.astype(str)],
                y=[_short(r, 30) for r in piv.index.astype(str)],
                customdata=[[f"{r} × {c}" for c in piv.columns.astype(str)]
                            for r in piv.index.astype(str)],
                colorscale=[[i / (len(SEQUENTIAL) - 1), h]
                            for i, h in enumerate(SEQUENTIAL)],
                hovertemplate="%{customdata}<br>%{z:,.1f}<extra></extra>",
                colorbar=dict(title=agg_name, thickness=12, outlinewidth=0)))
            fig.update_layout(height=max(300, 34 * len(piv) + 140),
                              xaxis_title=fmt(col_dim), yaxis_title=None,
                              yaxis=dict(autorange="reversed", automargin=False,
                                         tickfont=dict(size=11)),
                              margin=dict(t=16, r=24, b=54, l=300))
            st.plotly_chart(fig, use_container_width=True)
        elif HAS_PLOTLY:
            ser = piv.iloc[:, 0]
            fig = go.Figure(go.Bar(
                x=ser.values, y=[_short(i, 34) for i in ser.index.astype(str)],
                orientation="h", customdata=list(ser.index.astype(str)),
                marker=dict(color=SERIES[0], line=dict(color="#fcfcfb", width=2)),
                text=[f"{v:,.1f}" if isinstance(v, float) else f"{v:,}" for v in ser.values],
                textposition="outside",
                hovertemplate="%{customdata}<br>" + agg_name + " %{x:,.1f}<extra></extra>"))
            fig.update_layout(height=max(280, 34 * len(ser) + 90), showlegend=False,
                              xaxis_title=agg_name, yaxis_title=None,
                              yaxis=dict(autorange="reversed", automargin=False,
                                         tickfont=dict(size=11)),
                              margin=dict(t=16, r=24, b=44, l=330))
            st.plotly_chart(fig, use_container_width=True)

        show = piv.reset_index().rename(columns={row_dim: fmt(row_dim),
                                                 "_r": fmt(row_dim)})
        st.dataframe(show, use_container_width=True, hide_index=True, height=320)
        st.download_button("⬇ دانلود جدول متقاطع (CSV)",
                           show.to_csv(index=False).encode("utf-8-sig"),
                           file_name="AIBL_pivot.csv", mime="text/csv")

    # ── توزیع یک ستون عددی ──
    with st.container(border=True):
        st.markdown("##### ◔ توزیع یک سنجه")
        st.caption("پراکندگی مقادیر یک ستون عددی، با میانه.")
        if not measures:
            st.info("ستون عددی‌ای در فیلتر فعلی نیست.")
            return
        mcol = st.selectbox("ستون", measures, format_func=fmt,
                            index=_pref(measures, ["مقاومت (روز)", "مانده تعهد"]),
                            key="dist_col")
        v = pd.to_numeric(fdf[mcol], errors="coerce").dropna()
        if v.empty:
            st.info("این ستون مقدار عددی ندارد.")
            return
        if HAS_PLOTLY:
            fig = go.Figure(go.Histogram(
                x=v, nbinsx=min(30, max(5, int(len(v) ** 0.5) * 3)),
                marker=dict(color=SEQUENTIAL[3], line=dict(color="#fcfcfb", width=2)),
                hovertemplate="%{x}<br>%{y} ردیف<extra></extra>"))
            med = float(v.median())
            fig.add_vline(x=med, line_width=2, line_dash="dash",
                          line_color=STATUS["critical"],
                          annotation_text=f"میانه {med:,.1f}", annotation_position="top")
            fig.update_layout(height=300, showlegend=False, bargap=0.06,
                              xaxis_title=fmt(mcol), yaxis_title="تعداد ردیف",
                              margin=dict(t=30, r=24, b=44, l=24))
            st.plotly_chart(fig, use_container_width=True)
        q = v.quantile([0, .25, .5, .75, 1.0])
        st.caption(f"کمینه {q[0]:,.1f} · چارک۱ {q[.25]:,.1f} · میانه {q[.5]:,.1f} · "
                   f"چارک۳ {q[.75]:,.1f} · بیشینه {q[1.0]:,.1f} · "
                   f"جمع {v.sum():,.1f} · {len(v):,} مقدار")


def _pivot(df: pd.DataFrame, row: str, col: str | None, how: str,
           measure: str | None) -> pd.DataFrame:
    """جدول متقاطع.

    برای شمارش از ``crosstab`` استفاده می‌شود، نه ``pivot_table`` با
    ``values=row`` — آن حالت وقتی بُعد سطر و ستون سنجه یکی می‌شدند
    پانداس را به خطای «Grouper not 1-dimensional» می‌انداخت.
    """
    work = df.copy()
    r = work[row].fillna("—").astype(str)
    c = work[col].fillna("—").astype(str) if col else None

    if how == "count":
        if c is not None:
            out = pd.crosstab(r, c)
        else:
            out = r.value_counts().to_frame("تعداد ردیف")
            out.index.name = row
    else:
        if measure is None:
            raise ValueError("ستون سنجه انتخاب نشده است.")
        m = work[measure]
        vals = m.astype(str) if how == "nunique" else pd.to_numeric(m, errors="coerce")
        tmp = pd.DataFrame({"_r": r, "_m": vals})
        if c is not None:
            tmp["_c"] = c
            out = tmp.pivot_table(index="_r", columns="_c", values="_m",
                                  aggfunc=how, fill_value=0)
            out.index.name = row
            out.columns.name = col
        else:
            out = tmp.groupby("_r")["_m"].agg(how).to_frame(measure)
            out.index.name = row

    if len(out.columns):
        try:
            out = out.sort_values(out.columns[0], ascending=False)
        except Exception:
            pass
    return out


def _pref(options: List[str], wanted: List[str]) -> int:
    for w in wanted:
        if w in options:
            return options.index(w)
    return 0


def _pref_offset(options: List[str], wanted: List[str]) -> int:
    for w in wanted:
        if w in options:
            return options.index(w) + 1
    return 0
