# -*- coding: utf-8 -*-
"""AIBL Studio warehouse explorer.

This is intentionally query-first: the UI reads the persisted SQLite facts rather
than reconstructing process history from the current DataFrame.
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd


def render(warehouse, current_df: Optional[pd.DataFrame] = None, current_run_id: Optional[str] = None) -> None:
    import streamlit as st

    try:
        stats = warehouse.stats()
    except Exception as ex:
        st.error(f"انبار داده در دسترس نیست: {ex}")
        return

    st.markdown("### 🗄 انبار داده و لاگ فرآیند")
    st.caption("SQLite منبع ماندگار تحلیل است؛ Excel/PDF از این نسخه به بعد artifact خروجی هستند، نه محل نگه‌داری داده.")
    a,b,c,d,e = st.columns(5)
    a.metric("اجرای موفق", f"{stats.get('runs',0):,}")
    b.metric("رویداد یکتا", f"{stats.get('events',0):,}")
    c.metric("Transition", f"{stats.get('transitions',0):,}")
    d.metric("تغییر وضعیت", f"{stats.get('state_changes',0):,}")
    e.metric("حجم DB", f"{stats.get('size_mb',0):,.1f} MB")
    st.code(stats.get("path", ""), language=None)

    t1,t2,t3,t4,t5 = st.tabs(["اجراها", "روند KPI", "Drill-down پرونده", "گلوگاه SQL", "Audit Log"])

    with t1:
        runs = warehouse.list_runs(100)
        if runs.empty:
            st.info("هنوز snapshot موفقی ثبت نشده است.")
        else:
            st.dataframe(runs, use_container_width=True, hide_index=True)
            with st.expander("Lineage سورس‌های آخرین Snapshot", expanded=False):
                lin=warehouse.source_lineage(current_run_id)
                if lin.empty: st.info("Lineage سورس ثبت نشده است.")
                else: st.dataframe(lin.drop(columns=["columns_json"],errors="ignore"),use_container_width=True,hide_index=True)

    with t2:
        trend = warehouse.kpi_trend(limit=366)
        if trend.empty:
            st.info("برای روند حداقل یک اجرای ثبت‌شده لازم است.")
        else:
            labels = (trend[["metric_key","metric_label"]].drop_duplicates()
                      .set_index("metric_key")["metric_label"].to_dict())
            keys = list(labels)
            pick = st.selectbox("شاخص", keys, format_func=lambda k: labels.get(k,k), key="wh_kpi_metric")
            x = trend[trend["metric_key"] == pick].copy()
            x["ref_date"] = pd.to_datetime(x["ref_date"], errors="coerce")
            x = x.sort_values("ref_date")
            if x["numeric_value"].notna().any():
                st.line_chart(x.set_index("ref_date")[["numeric_value"]], use_container_width=True)
            st.dataframe(x[["ref_date","metric_label","numeric_value","unit","run_id"]], use_container_width=True, hide_index=True)

    with t3:
        candidates = []
        if isinstance(current_df, pd.DataFrame) and "CASE_KEY" in current_df.columns:
            candidates = current_df["CASE_KEY"].dropna().astype(str).replace("", pd.NA).dropna().drop_duplicates().head(5000).tolist()
        case_key = st.selectbox("CASE_KEY", [""] + candidates, key="wh_case_pick") if candidates else st.text_input("CASE_KEY", key="wh_case_text")
        if case_key:
            timeline = warehouse.case_timeline(case_key, current_run_id)
            transitions = warehouse.case_transitions(case_key, current_run_id)
            changes = warehouse.case_changes(case_key)
            c1,c2 = st.columns([1.25,1])
            with c1:
                st.markdown("**Timeline واقعی رویدادها**")
                st.dataframe(timeline, use_container_width=True, hide_index=True)
                st.markdown("**Transitionهای دقیق و زمان انتظار**")
                if transitions.empty:
                    st.info("برای این پرونده Transition ثبت نشده است.")
                else:
                    st.dataframe(transitions, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("**تغییرات بین Snapshotها**")
                if changes.empty:
                    st.info("تغییر ثبت‌شده‌ای وجود ندارد.")
                else:
                    show = changes.copy()
                    if "changed_fields_json" in show.columns:
                        show["changed_fields"] = show["changed_fields_json"].map(
                            lambda v: "، ".join(json.loads(v)) if v else "")
                    st.dataframe(show[[c for c in ["ref_date","changed_fields","run_id","previous_run_id"] if c in show.columns]],
                                 use_container_width=True, hide_index=True)
                    with st.expander("JSON تغییرات آخرین Snapshot"):
                        r = changes.iloc[0]
                        st.json({"previous": json.loads(r["previous_json"]) if r.get("previous_json") else {},
                                 "current": json.loads(r["current_json"]) if r.get("current_json") else {}})

    with t4:
        orgs=[]; experts=[]
        if isinstance(current_df,pd.DataFrame):
            if "ORG_DEPT" in current_df.columns:
                orgs=sorted(current_df["ORG_DEPT"].dropna().astype(str).replace("",pd.NA).dropna().unique().tolist())
            if "CANONICAL_EXPERT" in current_df.columns:
                experts=sorted(current_df["CANONICAL_EXPERT"].dropna().astype(str).replace("",pd.NA).dropna().unique().tolist())
        c1,c2=st.columns(2)
        org=c1.selectbox("مدیریت", [""]+orgs, key="wh_org")
        expert=c2.selectbox("کارشناس", [""]+experts, key="wh_expert")
        bn=warehouse.process_bottlenecks(run_id=current_run_id, org_unit=org or None, resource=expert or None, limit=100)
        st.dataframe(bn, use_container_width=True, hide_index=True)
        st.caption("این جدول مستقیم از fact_transition_snapshot محاسبه می‌شود؛ هر سطر فاصله واقعی دو Event متوالی در یک CASE است.")

    with t5:
        logs=warehouse.audit_entries(300)
        if logs.empty:
            st.info("لاگی ثبت نشده است.")
        else:
            st.dataframe(logs[[c for c in ["created_at","level","actor","action","run_id","message"] if c in logs.columns]],
                         use_container_width=True, hide_index=True)
