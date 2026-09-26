# -*- coding: utf-8 -*-
"""GSI Process Operations Cockpit — Figma-aligned, data-driven Streamlit view.

این ماژول لایه‌ی «از ریز تا درشت» محصول است: تصمیم → فرآیند → WIP →
Kanban/Action Queue → قطعه/مقاومت → پرونده. هیچ عدد نمایشی در آن hard-code
نمی‌شود؛ تمام مقادیر از DataFrame/Extras اجرای واقعی می‌آیند و Missing صفر
فرض نمی‌شود.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional
import html

import pandas as pd
try:
    import streamlit as st
except Exception:  # منطق خالص Cockpit بدون Streamlit هم قابل تست است
    st = None

from .theme import BANDS, STATUS, STATUS_INK, STATUS_WASH


_STAGE_LABELS = {
    "PR": "PR", "PO": "سفارش", "ORDER_REG": "ثبت سفارش",
    "ALLOCATION_QUEUE": "صف تخصیص", "ALLOCATION": "تخصیص",
    "FX_SUPPLY": "تأمین ارز", "SHIPMENT": "حمل", "DOCS": "اسناد",
    "CUSTOMS": "گمرک", "RELEASE": "ترخیص", "SETTLEMENT": "رفع تعهد",
}
_STAGE_ORDER = list(_STAGE_LABELS)


def _nunique(df: pd.DataFrame, col: str, mask: Optional[pd.Series] = None) -> int:
    if col not in df.columns:
        return 0
    s = df[col]
    if mask is not None:
        s = s.loc[mask]
    return int(s.replace("", pd.NA).dropna().astype(str).nunique())


def _band_count(df: pd.DataFrame, code: str) -> int:
    if "کد طبقه بحرانی" not in df.columns:
        return 0
    m = df["کد طبقه بحرانی"].astype(str).eq(code)
    return _nunique(df, "KEY_MATERIAL", m) if "KEY_MATERIAL" in df.columns else int(m.sum())


def _fmt(value, nd: int = 0) -> str:
    try:
        if pd.isna(value):
            return "—"
        return f"{float(value):,.{nd}f}"
    except Exception:
        return "—"


def _metric_card(label: str, value: str, sub: str, state: str = "normal") -> str:
    cls = "gsi-decision-card"
    if state in {"critical", "warning", "good"}:
        cls += f" is-{state}"
    return (
        f'<div class="{cls}"><div class="gsi-eyebrow">{html.escape(label)}</div>'
        f'<div class="gsi-metric">{html.escape(str(value))}</div>'
        f'<div class="gsi-card-sub">{html.escape(sub)}</div></div>'
    )


def _current_stage_counts(extras: Dict) -> pd.Series:
    """WIP proxy: latest lifecycle stage per case from the actual event log."""
    ev = extras.get("eventlog")
    if ev is None or not isinstance(ev, pd.DataFrame) or ev.empty:
        return pd.Series(dtype="int64")
    if not {"_CASE_KEY", "LIFECYCLE_STAGE"} <= set(ev.columns):
        return pd.Series(dtype="int64")
    x = ev.copy()
    if "EVENTTIME" in x.columns:
        x["_t"] = pd.to_datetime(x["EVENTTIME"], errors="coerce")
    else:
        x["_t"] = pd.NaT
    if "_SORTING" not in x.columns:
        x["_SORTING"] = 0
    x = x.sort_values(["_CASE_KEY", "_t", "_SORTING"], na_position="last")
    latest = x.groupby("_CASE_KEY", as_index=False).tail(1)
    return latest["LIFECYCLE_STAGE"].astype(str).value_counts()


def _bottleneck_stage(extras: Dict) -> tuple[str, str]:
    bott = extras.get("bottlenecks")
    if bott is None or not isinstance(bott, pd.DataFrame) or bott.empty:
        return "—", "داده کافی برای گلوگاه نیست"
    b = bott.copy()
    metric = None
    for c in ["میانگین مدت (روز)", "میانه مدت (روز)", "P90 مدت (روز)", "AVG_DAYS", "MEDIAN_DAYS", "P90_DAYS"]:
        if c in b.columns and pd.to_numeric(b[c], errors="coerce").notna().any():
            metric = c
            break
    if metric is None:
        nums = [c for c in b.columns if pd.api.types.is_numeric_dtype(b[c])]
        metric = nums[0] if nums else None
    if metric is None:
        return "—", "شاخص زمان گلوگاه موجود نیست"
    b[metric] = pd.to_numeric(b[metric], errors="coerce")
    b = b.dropna(subset=[metric]).sort_values(metric, ascending=False)
    if b.empty:
        return "—", "گذار قابل اندازه‌گیری نیست"
    r = b.iloc[0]
    frm = str(r.get("از فعالیت", r.get("FROM_ACTIVITY", ""))).strip()
    to = str(r.get("به فعالیت", r.get("TO_ACTIVITY", ""))).strip()
    label = " ← ".join(x for x in [frm, to] if x) or "گلوگاه فرآیند"
    return label, f"{metric}: {_fmt(r.get(metric), 1)}"


def _owner_coverage(df: pd.DataFrame) -> tuple[str, str]:
    for col in ["PART_OWNER", "CANONICAL_EXPERT"]:
        if col in df.columns and len(df):
            good = df[col].fillna("").astype(str).str.strip().ne("")
            return f"{100 * good.mean():.0f}%", f"{int(good.sum()):,} از {len(df):,} ردیف"
    return "—", "مالک در داده موجود نیست"


def _quality_coverage(df: pd.DataFrame) -> tuple[str, str]:
    if not len(df):
        return "—", "بدون داده"
    known = pd.Series(True, index=df.index)
    basis = 0
    if "KEY_MATERIAL" in df.columns:
        known &= df["KEY_MATERIAL"].fillna("").astype(str).str.strip().ne("")
        basis += 1
    if "DAILY_NEED" in df.columns:
        known &= pd.to_numeric(df["DAILY_NEED"], errors="coerce").gt(0)
        basis += 1
    if "مقاومت (روز)" in df.columns:
        known &= pd.to_numeric(df["مقاومت (روز)"], errors="coerce").notna()
        basis += 1
    if not basis:
        return "—", "سنجه پایه موجود نیست"
    return f"{100 * known.mean():.0f}%", f"{int(known.sum()):,} ردیف با ورودی قابل اتکا"


def _stage_html(counts: pd.Series, extras: Dict) -> str:
    bott = extras.get("bottlenecks")
    bott_text = ""
    if isinstance(bott, pd.DataFrame) and not bott.empty:
        cols = [c for c in ["از فعالیت", "به فعالیت"] if c in bott.columns]
        if cols:
            bott_text = " ".join(bott[cols].astype(str).head(5).stack().tolist())
    cards = []
    for stage in _STAGE_ORDER:
        cnt = int(counts.get(stage, 0))
        state = "normal"
        if stage in {"ALLOCATION", "ALLOCATION_QUEUE"} and ("تخصیص" in bott_text or "ALLOCATION" in bott_text):
            state = "critical"
        elif _STAGE_LABELS[stage] in bott_text or stage in bott_text:
            state = "warning"
        cards.append(
            f'<div class="gsi-stage is-{state}"><div class="gsi-stage-name">{_STAGE_LABELS[stage]}</div>'
            f'<div class="gsi-stage-meta">WIP {cnt:,}</div></div>'
        )
    return '<div class="gsi-process-strip">' + "".join(cards) + "</div>"


def _action_board(extras: Dict) -> pd.DataFrame:
    act = extras.get("case_actions")
    if act is None or not isinstance(act, pd.DataFrame) or act.empty:
        return pd.DataFrame()
    a = act.copy()
    for c in ["PRIORITY", "TITLE", "OWNER_ROLE", "DUE_DATE", "DAYS_REMAINING", "KEY_REG", "ACTION_ID"]:
        if c not in a.columns:
            a[c] = ""
    rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    a["_rank"] = a["PRIORITY"].astype(str).str.upper().map(rank).fillna(0)
    a["_days"] = pd.to_numeric(a["DAYS_REMAINING"], errors="coerce")
    return a.sort_values(["_rank", "_days"], ascending=[False, True], na_position="last")


def _render_kanban(extras: Dict) -> None:
    """Render a true operational board, not three dataframe-like columns.

    Columns come from factual due/priority evidence.  Cards expose action,
    owner, aging/due and evidence gaps; no velocity/burndown is invented.
    """
    a = _action_board(extras)
    if a.empty:
        st.info("Action Queue واقعی در این اجرا ساخته نشده است؛ Kanban نمایشی تولید نمی‌شود.")
        return

    def pick(row, *names, default=""):
        for n in names:
            if n in row and pd.notna(row.get(n)) and str(row.get(n)).strip():
                return str(row.get(n)).strip()
        return default

    def bucket(row) -> str:
        p = pick(row, "PRIORITY", "ACTION_PRIORITY").upper()
        d = pd.to_numeric(pd.Series([row.get("_days")]), errors="coerce").iloc[0]
        status = pick(row, "STATUS", "ACTION_STATUS").upper()
        if status in {"DONE", "CLOSED", "COMPLETED"}:
            return "تکمیل‌شده"
        if p in {"CRITICAL", "URGENT"} or (pd.notna(d) and d < 0):
            return "معوق / فوری"
        if p == "HIGH" or (pd.notna(d) and d <= 7):
            return "این هفته"
        return "Backlog"

    a["_bucket"] = a.apply(bucket, axis=1)
    order = ["معوق / فوری", "این هفته", "Backlog", "تکمیل‌شده"]
    total = len(a)
    cases_col = next((c for c in ["KEY_REG", "CASE_KEY", "_CASE_KEY", "ACTION_ID"] if c in a.columns), None)
    cases = int(a[cases_col].astype(str).nunique()) if cases_col else total
    urgent = int(a["_bucket"].eq("معوق / فوری").sum())
    owners = int(a.get("OWNER_ROLE", a.get("OWNER", pd.Series(dtype=str))).replace("", pd.NA).dropna().astype(str).nunique()) if ("OWNER_ROLE" in a.columns or "OWNER" in a.columns) else 0
    metrics = (
        '<div class="gsi-board-metrics">'
        f'<div><b>{total:,}</b><span>اقدام واقعی</span></div>'
        f'<div><b>{cases:,}</b><span>پرونده</span></div>'
        f'<div class="is-critical"><b>{urgent:,}</b><span>معوق / فوری</span></div>'
        f'<div><b>{owners:,}</b><span>مالک</span></div>'
        '</div>'
    )
    columns=[]
    for name in order:
        z=a[a["_bucket"].eq(name)].head(10)
        cards=[]
        for _, r in z.iterrows():
            key=pick(r,"KEY_REG","CASE_KEY","_CASE_KEY","ACTION_ID",default="پرونده")
            title=pick(r,"TITLE","NEXT_ACTION","NEXT_ACTION_TITLE",default="اقدام بعدی")
            owner=pick(r,"OWNER_ROLE","OWNER","NEXT_ACTION_OWNER",default="مالک نامشخص")
            priority=pick(r,"PRIORITY","ACTION_PRIORITY",default="NORMAL").upper()
            due=pick(r,"DUE_DATE","ACTION_DUE_DATE")
            days=pick(r,"DAYS_REMAINING","AGING_DAYS","STATUS_AGE_DAYS")
            evidence=pick(r,"EVIDENCE_GAP","DATA_GAP","MISSING_EVIDENCE")
            reason=pick(r,"RATIONALE","REASON","ACTION_REASON")
            tone="critical" if priority in {"CRITICAL","URGENT"} else ("warning" if priority=="HIGH" else "normal")
            meta=' · '.join(x for x in [owner, (f"موعد {due}" if due else ""), (f"{days} روز" if days else "")] if x)
            cards.append(
                f'<article class="gsi-board-card is-{tone}">'
                f'<div class="gsi-board-card-top"><span class="gsi-case-key">{html.escape(key)}</span>'
                f'<span class="gsi-priority">{html.escape(priority)}</span></div>'
                f'<h4>{html.escape(title)}</h4>'
                f'<div class="gsi-board-meta">{html.escape(meta)}</div>'
                + (f'<p>{html.escape(reason)}</p>' if reason else '')
                + (f'<div class="gsi-evidence-gap">شکاف شاهد: {html.escape(evidence)}</div>' if evidence else '')
                + '</article>')
        more=max(int(a["_bucket"].eq(name).sum())-len(z),0)
        footer=f'<div class="gsi-board-more">+ {more:,} مورد دیگر</div>' if more else ''
        columns.append(
            f'<section class="gsi-board-col" data-state="{html.escape(name)}">'
            f'<header><h3>{html.escape(name)}</h3><span>{int(a["_bucket"].eq(name).sum()):,}</span></header>'
            f'<div class="gsi-board-stack">{"".join(cards) or "<div class=\"gsi-board-empty\">موردی نیست</div>"}</div>{footer}</section>')
    st.markdown(metrics+'<div class="gsi-action-board">'+''.join(columns)+'</div>', unsafe_allow_html=True)


def _critical_materials(df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if not {"KEY_MATERIAL", "مقاومت (روز)"} <= set(df.columns):
        return pd.DataFrame()
    z = df[["KEY_MATERIAL", "مقاومت (روز)"]].copy()
    z["مقاومت (روز)"] = pd.to_numeric(z["مقاومت (روز)"], errors="coerce")
    z["KEY_MATERIAL"] = z["KEY_MATERIAL"].fillna("").astype(str).str.strip()
    z = z[(z["KEY_MATERIAL"] != "") & z["مقاومت (روز)"].notna()]
    if z.empty:
        return z
    return z.groupby("KEY_MATERIAL", as_index=False)["مقاومت (روز)"].min().nsmallest(limit, "مقاومت (روز)")


def _priority_cases(df: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    cols = [c for c in ["KEY_MATERIAL", "CANONICAL_ORDER", "KEY_REG", "مقاومت (روز)",
                           "بحرانی (کوتاه)", "CURRENT_STAGE_FA", "CURRENT_STAGE",
                           "PART_OWNER", "CANONICAL_EXPERT", "STATUS_AGE_DAYS", "WAITING_ON_SCOPE"] if c in df.columns]
    if not cols:
        return pd.DataFrame()
    z = df[cols].copy()
    if "مقاومت (روز)" in z.columns:
        z["مقاومت (روز)"] = pd.to_numeric(z["مقاومت (روز)"], errors="coerce")
        z = z.sort_values("مقاومت (روز)", ascending=True, na_position="last")
    subset = [c for c in ["KEY_MATERIAL", "CANONICAL_ORDER", "KEY_REG"] if c in z.columns]
    if subset:
        z = z.drop_duplicates(subset=subset, keep="first")
    return z.head(limit)


def render(df: pd.DataFrame, extras: Dict, ref_date: str = "") -> None:
    """Render the Figma-aligned operations cockpit from real runtime data."""
    if st is None:
        raise RuntimeError("Streamlit برای رندر Process Cockpit نصب نیست.")
    if df is None:
        df = pd.DataFrame()
    from gsi.studio_core.runtime_data import ensure_criticality_columns
    df = ensure_criticality_columns(df)
    from app.process_intelligence import render as render_process_exports
    render_process_exports(df, extras, ref_date)
    stop = _band_count(df, "STOCKOUT")
    crit = _band_count(df, "CRITICAL")
    becoming = _band_count(df, "BECOMING_CRITICAL")
    need_action = stop + crit + becoming
    bott_name, bott_sub = _bottleneck_stage(extras)
    owner, owner_sub = _owner_coverage(df)
    quality, quality_sub = _quality_coverage(df)

    st.markdown(
        '<div class="gsi-cockpit-head"><div><div class="gsi-overline">DATA • PROCESS • DECISION</div>'
        '<h2>مرکز عملیات فرآیند</h2>'
        f'<p>{html.escape(ref_date or "اجرای جاری")} · {len(df):,} ردیف پس از فیلتر</p></div>'
        '<div class="gsi-search-ghost">⌕ جست‌وجو از نوار فیلترها</div></div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="gsi-decision-grid">' +
        _metric_card("نیازمند اقدام", f"{need_action:,}", "توقف خط + بحرانی + درحال بحرانی شدن", "critical" if need_action else "good") +
        _metric_card("گلوگاه اصلی", bott_name, bott_sub, "warning" if bott_name != "—" else "normal") +
        _metric_card("پوشش مالک", owner, owner_sub) +
        _metric_card("کیفیت ورودی مقاومت", quality, quality_sub) +
        '</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### نقشه فرآیند و WIP")
        st.caption("آخرین مرحله واقعی هر پرونده از Event Log؛ رنگ هشدار/بحرانی فقط وقتی شواهد گلوگاه موجود باشد.")
        st.markdown(_stage_html(_current_stage_counts(extras), extras), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1, st.container(border=True):
        st.markdown("### Kanban عملیاتی")
        st.caption("بر اساس Action Queue واقعی؛ velocity یا sprint ساختگی ایجاد نمی‌شود.")
        _render_kanban(extras)
    with c2, st.container(border=True):
        st.markdown("### کم‌مقاومت‌ترین قطعات")
        st.caption("مقاومت انبار = (IKCO + SAPCO) ÷ نیاز روزانه؛ هر شماره فنی یک بار.")
        low = _critical_materials(df)
        if low.empty:
            st.info("مقاومت قابل رسم موجود نیست؛ Missing صفر محسوب نشده است.")
        else:
            for _, r in low.iterrows():
                val = float(r["مقاومت (روز)"])
                state = "critical" if val < 10 else "warning" if val < 20 else "normal"
                st.markdown(
                    f'<div class="gsi-res-row is-{state}"><b>{html.escape(str(r["KEY_MATERIAL"]))}</b>'
                    f'<span>{val:,.1f} روز</span></div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### پرونده‌های اولویت‌دار")
        st.caption("از مقاومت پایین به بالا؛ Drill-down کامل‌تر در تب فرآیند و دید تأمین است.")
        pc = _priority_cases(df)
        if pc.empty:
            st.info("پرونده اولویت‌دار قابل استخراج نیست.")
        else:
            st.dataframe(pc, width="stretch", hide_index=True, height=min(430, 42 * len(pc) + 50))

    with st.expander("از نمای کلان به ریز: مسیر پیشنهادی کار"):
        st.markdown(
            "**۱.** Decision Cards → **۲.** Process/WIP → **۳.** Kanban/گلوگاه → "
            "**۴.** قطعه و مقاومت → **۵.** پرونده و Timeline → **۶.** Source Lineage / شواهد.  "
            "این ترتیب برای کاهش بار ذهنی طراحی شده و هیچ مرحله‌ای داده‌ی خام را پنهان نمی‌کند.")
