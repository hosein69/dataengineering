# -*- coding: utf-8 -*-
"""صفحه «اعتماد داده» — وضعیت واقعی داده، بدون تعارف و بدون سرزنش.

سه قاعده طراحی که در کل این صفحه رعایت می‌شود (`docs/DATA_STRATEGY_FA.md`):

۱. **هیچ عدد لختی نمایش داده نمی‌شود.** هر عدد تصمیم‌ساز چیپ درجه دارد و
   می‌گوید مجاز به چه کاری هست و چه کاری نیست.
۲. **نامعلوم «—» است، هرگز صفر.** بخش معلوم و تعداد نامعلوم کنار هم می‌آیند.
۳. **صفحه به «حالا چه کار کنم؟» جواب می‌دهد.** کارنامه مالک بر اساس
   «چقدر می‌تواند آزاد کند» مرتب است، نه «چقدر خراب‌کاری کرده».
"""
from __future__ import annotations

import html
import io
import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from gsi.design import tokens as T
from gsi.trust import inquiry as inq
from gsi.trust import trend as trend_mod
from gsi.trust.anomaly import STRENGTH_FA, Anomaly
from gsi.trust.fitness import GRADE_FA, GRADE_LICENCE_FA, GRADE_TONE, NOT_USABLE
from gsi.trust.impact import NO_ORG_UNIT

# رنگ‌ها از همان پالت وضعیت سیستم طراحی می‌آیند (`gsi/design/tokens.py`)، که
# کنتراستش با WCAG سنجیده شده. هیچ hex دستی در این فایل نیست.


#: Column widths for the trust tables. Streamlit gives every column the same
#: default width and then scrolls horizontally, which in an RTL layout pushes
#: the *most useful* columns — the action sentence and the evidence locator —
#: off the left edge where nobody scrolls to find them.
_WIDE = ("مهم‌ترین اقدام", "اقدام پیشنهادی", "اقدام لازم", "شایع‌ترین مقدار نامعتبر",
         "توضیح")
_MEDIUM = ("تصمیم‌های متأثر", "نمونه کلید", "شاهد", "مالک", "نقش", "اداره",
           "مدیر", "معاونت", "فیلد")
_NARROW = ("ایراد", "پرونده درگیر", "قابل آزادسازی", "سلول تکمیل",
           "مورد بررسی", "پرونده قابل آزادسازی", "تعداد سلول",
           "پرونده آزادشده", "پرونده متأثر",
           "پوشش (٪)", "پرونده", "سالم", "خالی", "مشکوک", "متعارض", "نوع",
           "وضعیت", "کلید", "ستون")


def _cfg(frame: pd.DataFrame) -> Dict[str, Any]:
    """Width hints so the column that says what to do stays readable."""
    out: Dict[str, Any] = {}
    for column in frame.columns:
        if column in _WIDE:
            out[column] = st.column_config.TextColumn(column, width="large")
        elif column in _MEDIUM:
            out[column] = st.column_config.TextColumn(column, width="medium")
        elif column in _NARROW:
            out[column] = st.column_config.Column(column, width="small")
    return out


def _css() -> str:
    return f"""
<style>
.tr-hero{{background:linear-gradient(135deg,{T.NAVY_WASH} 0%,{T.SURFACE_RAISED} 60%);
 border:1px solid {T.BORDER};border-radius:16px;padding:18px 20px;margin-bottom:14px}}
.tr-hero h2{{margin:0 0 6px;font-size:20px;color:{T.TEXT}}}
.tr-hero p{{margin:0;font-size:13px;color:{T.TEXT_SECONDARY};line-height:1.9}}
.tr-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.tr-card{{background:{T.SURFACE_RAISED};border:1px solid {T.BORDER};border-radius:14px;
 padding:14px 16px;display:flex;flex-direction:column;gap:8px}}
.tr-card .q{{font-size:12px;color:{T.TEXT_MUTED}}}
.tr-card h4{{margin:0;font-size:15px;color:{T.TEXT}}}
.tr-chip{{display:inline-flex;align-items:center;gap:6px;border-radius:999px;
 padding:3px 11px;font-size:12px;font-weight:700;border:1px solid}}
.tr-value{{font-size:15px;font-weight:800;color:{T.TEXT};direction:ltr;text-align:right;
 font-variant-numeric:tabular-nums;overflow-wrap:anywhere}}
.tr-licence{{font-size:11.5px;color:{T.TEXT_SECONDARY};line-height:1.8;
 border-top:1px dashed {T.BORDER};padding-top:7px}}
.tr-reason{{font-size:11.5px;color:{T.TEXT_MUTED};line-height:1.9}}
.tr-action{{background:{T.TEAL_WASH};border:1px solid {T.BORDER};border-right:3px solid {T.BRAND_TEAL};
 border-radius:10px;padding:10px 12px;font-size:12.5px;color:{T.TEXT};line-height:1.9;margin-bottom:8px}}
.tr-note{{font-size:11.5px;color:{T.TEXT_MUTED};line-height:1.9;margin-top:4px}}
.tr-ask{{background:{T.SURFACE_PAPER_SOFT};border:1px solid {T.PAPER_RULE};border-radius:14px;
 padding:14px 16px;margin-bottom:12px;line-height:2;font-size:13px;color:{T.TEXT}}}
.tr-ask b{{color:{T.TEAL_INK}}}
.tr-odd{{font-size:14px;font-weight:700;color:{T.TEXT};line-height:1.9;margin-bottom:6px}}
.tr-vs{{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px}}
.tr-vs span{{background:{T.SURFACE_SUNKEN};border-radius:8px;padding:3px 10px;font-size:12px;
 color:{T.TEXT_SECONDARY}}}
.tr-hyp{{border-right:3px solid {T.BORDER_STRONG};padding:6px 10px;margin:6px 0;
 background:{T.SURFACE_RAISED};border-radius:6px}}
.tr-hyp h5{{margin:0 0 2px;font-size:13px;color:{T.TEXT}}}
.tr-hyp p{{margin:0;font-size:12px;color:{T.TEXT_SECONDARY};line-height:1.9}}
.tr-str{{font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px;margin-inline-start:6px}}
.tr-str.strong{{color:{T.TEAL_INK};background:{T.TEAL_WASH}}}
.tr-str.medium{{color:{T.GOLD_INK};background:{T.GOLD_WASH}}}
.tr-str.weak{{color:{T.TEXT_MUTED};background:{T.SURFACE_SUNKEN}}}
.tr-fix{{background:{T.TEAL_WASH};border:1px dashed {T.BRAND_TEAL};border-radius:10px;
 padding:8px 12px;font-size:12.5px;color:{T.TEXT};line-height:1.9;margin:8px 0}}
</style>"""


def _status(grade: str):
    return T.STATUS.get(GRADE_TONE.get(grade, "unknown"), T.STATUS["unknown"])


def _chip(grade: str) -> str:
    s = _status(grade)
    return (f'<span class="tr-chip" style="color:{s.ink};background:{s.wash};'
            f'border-color:{s.ink}44">{s.icon} {GRADE_FA.get(grade, grade)}</span>')


def _excel(frames: Dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in frames.items():
            (frame if not frame.empty else pd.DataFrame({"—": ["داده‌ای نیست"]})).to_excel(
                writer, sheet_name=name[:31], index=False)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════════════
def render(extras: Optional[Dict[str, Any]] = None, ref_date: str = "") -> None:
    """صفحه را از روی فریم‌های `trust_*` همان اجرای منتشرشده می‌سازد."""
    extras = extras or {}
    st.markdown(_css(), unsafe_allow_html=True)

    decisions = extras.get("trust_decisions")
    if not isinstance(decisions, pd.DataFrame) or decisions.empty:
        st.info("سنجش اعتماد داده برای این اجرا موجود نیست. "
                "یک بار «اجرای مجدد خط لوله» یا `REFRESH_GSI_DATA.cmd` را اجرا کنید.")
        return

    headline = extras.get("trust_headline", "")
    summary = extras.get("trust_summary") or {}
    history = trend_mod.load_snapshots()

    anomaly_line = extras.get("anomaly_headline", "")
    st.markdown(
        f'<div class="tr-hero"><h2>اعتماد داده — این اعداد چقدر قابل استنادند؟</h2>'
        f'<p>{headline}<br>{trend_mod.headline_fa(history)}'
        + (f'<br>🕵️ {html.escape(anomaly_line)}' if anomaly_line else "")
        + '</p></div>',
        unsafe_allow_html=True)

    tabs = st.tabs(["تصمیم‌ها", "حالا چه کار کنم؟", "ناهنجاری‌ها — اول بپرس",
                    "کارنامه مالکان", "آینه فیلدها", "روند بهبود"])

    with tabs[0]:
        _decisions(decisions)
    with tabs[1]:
        _next_fixes(extras.get("trust_next_fixes"))
    with tabs[2]:
        _inquiries(extras)
    with tabs[3]:
        _owners(extras, extras.get("trust_defects"))
    with tabs[4]:
        _fields(extras.get("trust_fields"), summary)
    with tabs[5]:
        _trend(history)

    defects = extras.get("trust_defects")
    if isinstance(defects, pd.DataFrame) and not defects.empty:
        st.download_button(
            "⬇ دریافت کل گزارش اعتماد داده (Excel)",
            data=_excel({
                "تصمیم‌ها": decisions,
                "اقدام بعدی": extras.get("trust_next_fixes", pd.DataFrame()),
                "مالکان": extras.get("trust_owners", pd.DataFrame()),
                "دفتر ایرادها": defects,
                "آینه فیلدها": extras.get("trust_fields", pd.DataFrame()),
                "ناهنجاری‌ها": _public(extras.get("anomaly_inquiries")),
                "ترمیم‌های اعمال‌شده": extras.get("heal_applied", pd.DataFrame()),
            }),
            file_name=f"GSI_Data_Trust_{ref_date or 'run'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch")


# ── تب ۱: درجه هر تصمیم ────────────────────────────────────────────────────
def _decisions(decisions: pd.DataFrame) -> None:
    st.caption("درجه به جفت «تصمیم و پرونده» تعلق دارد، نه به خود پرونده: "
               "یک پرونده می‌تواند برای «کجاست؟» قابل استناد باشد و برای "
               "«چقدر بدهکاریم؟» نباشد.")
    cards: List[str] = []
    for row in decisions.to_dict("records"):
        grade = row.get("_grade", NOT_USABLE)
        reason = row.get("علت", "—")
        cards.append(
            '<div class="tr-card">'
            f'<div class="q">{row.get("پرسش", "")}</div>'
            f'<h4>{row.get("تصمیم", "")}</h4>'
            f'<div>{_chip(grade)}</div>'
            f'<div class="tr-value">{row.get("عدد قابل استناد", "—")}</div>'
            f'<div class="tr-reason">پوشش شواهد: {row.get("پوشش (٪)", 0)}٪ '
            f'({row.get("پرونده آماده", 0)} از {row.get("کل پرونده", 0)} پرونده)</div>'
            + (f'<div class="tr-reason">علت: {reason}</div>' if reason and reason != "—" else "")
            + f'<div class="tr-licence">{GRADE_LICENCE_FA.get(grade, "")}</div>'
            '</div>')
    st.markdown('<div class="tr-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    with st.expander("جدول کامل تصمیم‌ها"):
        st.dataframe(decisions.drop(columns=[c for c in ("_grade", "_tone") if c in decisions],
                                    errors="ignore"),
                     hide_index=True, width="stretch")


# ── تب ۲: کوچک‌ترین اقدام بعدی ─────────────────────────────────────────────
def _next_fixes(fixes: Optional[pd.DataFrame]) -> None:
    if not isinstance(fixes, pd.DataFrame) or fixes.empty:
        st.success("هیچ ایراد مسدودکننده‌ای برای تصمیم‌های تعریف‌شده باقی نمانده است.")
        return
    st.caption("به ترتیب «کم‌ترین کار، بیشترین اثر». هر سطر یک کار مشخص است، "
               "نه یک گزارش. «پرونده آزادشده» یعنی پرونده‌هایی که تنها مانعشان همین است.")
    unlocking = fixes[fixes["پرونده آزادشده"] > 0]
    for row in unlocking.head(12).to_dict("records"):
        st.markdown(
            f'<div class="tr-action"><b>{row["مالک"]}</b>'
            f'{" · " + row["نقش"] if row.get("نقش") else ""}'
            f'<br>{row["اقدام پیشنهادی"]}'
            f'<div class="tr-note">نمونه پرونده: {row.get("نمونه کلید", "—")} · '
            f'تصمیم متأثر: {row.get("تصمیم‌های متأثر", "—")}</div></div>',
            unsafe_allow_html=True)
    blocked = fixes[fixes["پرونده آزادشده"] == 0]
    if not blocked.empty:
        with st.expander(f"ایرادهایی که به‌تنهایی پرونده‌ای آزاد نمی‌کنند ({len(blocked)})"):
            st.caption("این‌ها هم باید رفع شوند، ولی پرونده‌هایشان مانع دیگری هم دارند؛ "
                       "وعده «آزادسازی» برایشان داده نمی‌شود.")
            st.dataframe(blocked, hide_index=True, width="stretch",
                         column_config=_cfg(blocked))


# ── تب ۳: ناهنجاری‌ها — اول بپرس، بعد ترمیم کن ───────────────────────────────
#: Colour of each answer state, from the audited status palette.
_STATUS_TONE = {
    inq.OVERDUE: "critical", inq.OPEN: "warning", inq.UNKNOWN: "neutral",
    inq.REPAIR_APPROVED: "good", inq.EXPLAINED: "good", inq.REPAIR_REJECTED: "neutral",
}
#: What the one sentence should say, per kind of anomaly.
_NOTE_HINT = {
    "VALUE_OUTLIER": "مثلاً: «سفارش یک‌باره خط جدید است، واقعی است» یا «در سورس به ریال وارد شده»",
    "CATEGORY_VARIANT": "مثلاً: «همان گمرک است، دو نفر دو جور نوشته‌اند»",
    "NEW_CATEGORY": "مثلاً: «از این ماه با تأمین‌کننده جدید از این مرز کار می‌کنیم»",
    "VOLUME_DROP": "مثلاً: «فایل BLs این هفته نیمه‌کاره کپی شد» یا «تعطیلات بود»",
    "TOO_GOOD": "مثلاً: «کارزار تکمیل داده با آقای/خانم … انجام شد»",
}
#: Pending anomalies shown as full cards; the rest stay in the table.
_MAX_CARDS = 25


def _public(frame: Optional[pd.DataFrame]) -> pd.DataFrame:
    """The inquiry table without its machine columns."""
    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    return frame.drop(columns=[c for c in frame.columns if str(c).startswith("_")])


def _default_actor() -> str:
    return (st.session_state.get("inq_actor")
            or os.environ.get("USERNAME") or os.environ.get("USER") or "")


def _inquiries(extras: Dict[str, Any]) -> None:
    st.markdown(
        '<div class="tr-ask">داده پرت <b>خبرچین مجانی</b> است: یعنی داده جایی رفتاری کرده که '
        'تصویر ما از کسب‌وکار پیش‌بینی نمی‌کرد. اینجا هیچ چیزی حذف یا بی‌صدا صاف نمی‌شود. '
        'سامانه برای هر مورد می‌گوید <b>چه چیزی عجیب است</b>، توضیح‌های محتمل را <b>با شاهد از خود '
        'داده</b> می‌سنجد و اگر اصلاحی پیشنهاد دارد، <b>فقط با تأیید شما</b> و از اجرای بعد اعمالش '
        'می‌کند. «نمی‌دانیم» جواب قابل قبولی است، ولی فقط تا یک تاریخ مشخص.</div>',
        unsafe_allow_html=True)

    frame = extras.get("anomaly_inquiries")
    register = inq.InquiryRegister.load()
    today = date.today()
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        # Answers given since the run are live: the page reads the register,
        # not the state frozen at run time.
        frame = frame.copy()
        frame["_status"] = frame["شناسه"].map(lambda i: register.status(str(i), today))
        frame["وضعیت"] = frame["_status"].map(lambda s: inq.STATUS_FA.get(s, s))
        counts = frame["_status"].value_counts()
        cols = st.columns(4)
        cols[0].metric("منتظر پاسخ شما", int(counts.get(inq.OPEN, 0) + counts.get(inq.OVERDUE, 0)))
        cols[1].metric("مهلت «نمی‌دانیم» گذشته", int(counts.get(inq.OVERDUE, 0)))
        cols[2].metric("توضیح داده‌شده", int(counts.get(inq.EXPLAINED, 0)
                                              + counts.get(inq.REPAIR_REJECTED, 0)))
        cols[3].metric("ترمیم تأییدشده", int(counts.get(inq.REPAIR_APPROVED, 0)))

        pending = frame[frame["_status"].isin(inq.NEEDS_ANSWER)]
        if pending.empty:
            st.success("همه ناهنجاری‌های این اجرا پاسخ گرفته‌اند. ممنون — این جمله‌ها دانش سازمان‌اند.")
        for row in pending.head(_MAX_CARDS).to_dict("records"):
            _inquiry_card(row, register)
        if len(pending) > _MAX_CARDS:
            st.caption(f"{len(pending) - _MAX_CARDS} مورد دیگر در جدول زیر است؛ "
                       "پس از پاسخ به این‌ها بالا می‌آیند.")
        with st.expander(f"همه ناهنجاری‌های این اجرا ({len(frame)})"):
            table = _public(frame)
            st.dataframe(table, hide_index=True, width="stretch", column_config=_cfg(table))
    else:
        st.info("در این اجرا ناهنجاری‌ای دیده نشد — یا این اجرا پیش از نسخه 29.15 ساخته شده است. "
                "با هر اجرای تازه، مقایسه با اجراهای قبل دقیق‌تر می‌شود.")

    _active_repairs(extras, register)
    history = register.history_frame()
    if not history.empty:
        with st.expander(f"تاریخچه پاسخ‌ها ({len(history)}) — هیچ پاسخی پاک نمی‌شود"):
            st.dataframe(history, hide_index=True, width="stretch", column_config=_cfg(history))


def _inquiry_card(row: Dict[str, Any], register) -> None:
    try:
        anomaly = Anomaly.from_dict(json.loads(row.get("_payload") or "{}"))
    except (TypeError, ValueError):
        return
    status = row.get("_status", inq.OPEN)
    tone = T.STATUS[_STATUS_TONE.get(status, "unknown")]
    esc = html.escape
    title = f"{inq.STATUS_FA.get(status, status)} · {anomaly.kind_fa} — {anomaly.headline_fa}"
    with st.expander(title, expanded=status == inq.OVERDUE):
        parts = [f'<div class="tr-odd" style="border-right:4px solid {tone.ink};'
                 f'padding-right:10px">{esc(anomaly.headline_fa)}</div><div class="tr-vs">']
        if anomaly.observed_fa:
            parts.append(f"<span>مقدار: {esc(anomaly.observed_fa)}</span>")
        if anomaly.expected_fa:
            parts.append(f"<span>معمول: {esc(anomaly.expected_fa)}</span>")
        who = " · ".join(x for x in (anomaly.owner_name, inq.role_fa(anomaly.owner_role),
                                     anomaly.owner_dept) if x)
        if who:
            parts.append(f"<span>چه کسی می‌تواند جواب دهد: {esc(who)}</span>")
        if anomaly.locator_fa:
            parts.append(f"<span>محل: {esc(anomaly.locator_fa)}</span>")
        parts.append("</div><div class='tr-note'>توضیح‌های محتمل، به ترتیب قوت شاهد:</div>")
        for h in anomaly.hypotheses:
            parts.append(
                f'<div class="tr-hyp"><h5>{esc(h.title_fa)}<span class="tr-str {esc(h.strength)}">'
                f'{STRENGTH_FA.get(h.strength, h.strength)}</span></h5><p>{esc(h.evidence_fa)}</p></div>')
        repair = anomaly.repair
        if repair:
            parts.append(f'<div class="tr-fix">🔧 اگر تأیید کنید: <b>{esc(inq.repair_fa(repair))}</b><br>'
                         'از اجرای بعد اعمال می‌شود، قبل از همه محاسبات. مقدار اصلی روی همان ردیف '
                         '(ستون «ترمیم تأییدشده») می‌ماند و هر وقت بخواهید قابل پس‌گرفتن است.</div>')
        last = register.latest(anomaly.id)
        if last is not None and status == inq.OVERDUE:
            parts.append(f'<div class="tr-note">پاسخ قبلی: «{esc(last.note)}» — {esc(last.actor)}، '
                         f'تا {esc(last.until)}. مهلت گذشته؛ حالا چه می‌دانیم؟</div>')
        st.markdown("".join(parts), unsafe_allow_html=True)
        _answer_form(anomaly, repair)


def _answer_form(anomaly: Anomaly, repair: Optional[Dict[str, Any]]) -> None:
    actions = [inq.EXPLAIN, inq.DONT_KNOW]
    if repair:
        actions = [inq.APPROVE, inq.REJECT] + actions
    with st.form(f"inq_form_{anomaly.id}", clear_on_submit=False):
        action = st.radio("پاسخ شما", actions, format_func=lambda a: inq.ACTION_FA[a],
                          key=f"inq_act_{anomaly.id}")
        note = st.text_area("در یک جمله: چرا؟ (الزامی)", key=f"inq_note_{anomaly.id}",
                            placeholder=_NOTE_HINT.get(anomaly.kind, ""), height=80)
        c1, c2 = st.columns(2)
        days = c1.number_input("اگر «نمی‌دانم»: تا چند روز دیگر؟", min_value=1,
                               max_value=inq.UNKNOWN_MAX_DAYS, value=inq.UNKNOWN_DEFAULT_DAYS,
                               key=f"inq_days_{anomaly.id}")
        actor = c2.text_input("نام شما", value=_default_actor(), key=f"inq_actor_{anomaly.id}")
        standing = False
        if repair and repair.get("kind") == "ALIAS":
            standing = st.checkbox("از این به بعد هر جا همین املا آمد، خودکار یکسان شود",
                                   key=f"inq_standing_{anomaly.id}")
        if st.form_submit_button("ثبت پاسخ", type="primary"):
            try:
                decision = inq.make_decision(anomaly, action, note, actor, days=int(days),
                                             standing=standing and action == inq.APPROVE)
            except inq.InquiryError as ex:
                st.error(str(ex))
                return
            inq.InquiryRegister().record(decision)
            st.session_state["inq_actor"] = actor
            done = ("ثبت شد. ترمیم در اجرای بعدی خط لوله اعمال می‌شود."
                    if action == inq.APPROVE else "ثبت شد. ممنون — این جمله دانش سازمان است.")
            st.toast(done, icon="✅")
            st.rerun()


def _active_repairs(extras: Dict[str, Any], register) -> None:
    applied = extras.get("heal_applied")
    stale = extras.get("heal_stale")
    approved = register.approved()
    if isinstance(applied, pd.DataFrame) and not applied.empty:
        with st.expander(f"🔧 ترمیم‌های اعمال‌شده در این اجرا ({len(applied)})", expanded=False):
            st.caption("هر ترمیم فقط تا وقتی اعمال می‌شود که سورس همان مقدار تأییدشده را دارد.")
            st.dataframe(applied, hide_index=True, width="stretch", column_config=_cfg(applied))
    if isinstance(stale, pd.DataFrame) and not stale.empty:
        st.warning(f"{len(stale)} ترمیم تأییدشده دیگر با داده جور نیست و اعمال نشد "
                   "(معمولاً یعنی سورس اصلاح شده است — خبر خوب).")
        st.dataframe(stale, hide_index=True, width="stretch", column_config=_cfg(stale))
    if not approved:
        return
    with st.expander(f"پس‌گرفتن یک ترمیم ({len(approved)} ترمیم فعال)"):
        labels = {d.anomaly_id: f"{inq.repair_fa(d.repair)} — {d.actor}" for d in approved}
        with st.form("inq_revoke"):
            pick = st.selectbox("کدام ترمیم؟", list(labels), format_func=lambda i: labels[i])
            note = st.text_area("در یک جمله: چرا پس گرفته می‌شود؟")
            actor = st.text_input("نام شما", value=_default_actor(), key="inq_revoke_actor")
            if st.form_submit_button("پس‌گرفتن"):
                target = next(d for d in approved if d.anomaly_id == pick)
                try:
                    decision = inq.make_decision(target.anomaly, inq.REVOKE, note, actor)
                except inq.InquiryError as ex:
                    st.error(str(ex))
                    return
                inq.InquiryRegister().record(decision)
                st.toast("پس گرفته شد؛ از اجرای بعد مقدار اصلی سورس استفاده می‌شود.", icon="↩️")
                st.rerun()


# ── تب ۴: کارنامه مالکان ───────────────────────────────────────────────────
#: Slice label -> (frame key in ``extras``, its own first column). A defect is
#: closed by a person, but the queue is planned by a manager and reported by a
#: department, so the same backlog has to be readable at all three levels.
_ORG_VIEWS = {
    "فرد": ("trust_owners", "مالک"),
    "اداره": ("trust_owners_by_dept", "اداره"),
    "مدیر": ("trust_owners_by_manager", "مدیر"),
}


def _owners(extras: Dict[str, Any], defects: Optional[pd.DataFrame]) -> None:
    owners = extras.get("trust_owners")
    if not isinstance(owners, pd.DataFrame) or owners.empty:
        st.info("مالکی برای ایرادها تشخیص داده نشد.")
        return
    st.caption("ترتیب این جدول بر اساس «چقدر می‌تواند آزاد کند» است، نه «چقدر ایراد دارد». "
               "معیار ارزیابی، نرخ بهبود است؛ مقدار مطلق در نقطه صفر تقصیر کسی نیست.")

    available = [name for name, (key, _) in _ORG_VIEWS.items()
                 if isinstance(extras.get(key), pd.DataFrame)]
    level = (st.radio("سطح نمایش", available, horizontal=True, key="trust_org_level")
             if len(available) > 1 else "فرد")
    frame = extras.get(_ORG_VIEWS[level][0], owners)

    # The action sentence is a paragraph. Left in this grid it squeezes every
    # other column to nothing; the same sentence is one click away in the
    # per-person worklist below, and it is kept in full in the Excel export.
    grid = frame.drop(columns=["مهم‌ترین اقدام"], errors="ignore")
    st.dataframe(grid, hide_index=True, width="stretch", column_config=_cfg(grid))

    if isinstance(defects, pd.DataFrame) and not defects.empty:
        _worklist(frame, defects, _ORG_VIEWS[level][1])


def _worklist(frame: pd.DataFrame, defects: pd.DataFrame, column: str) -> None:
    """The backlog of one person, unit or manager — whatever level is showing.

    Filtered on the same column the grid is grouped by, so what the user clicked
    and what they download are the same set of cells.
    """
    if column not in frame.columns or column not in defects.columns:
        return
    picks = [v for v in frame[column].tolist() if v]
    if not picks:
        return
    chosen = st.selectbox(f"فهرست کار «{column}»", picks, key="trust_owner_pick")
    values = defects[column].astype(str).str.strip()
    # The rollup labels the blank group; the ledger still stores it blank. A
    # source-contract defect has no manager by definition, and that bucket is
    # usually the highest-value row on the page — sending it to an empty state
    # would hide exactly the item the page most wants read.
    worklist = defects[values == ("" if chosen == NO_ORG_UNIT else str(chosen).strip())]
    if worklist.empty:
        st.info("برای این انتخاب، ایراد قابل ارجاعی در دفتر ثبت نشده است.")
        return
    show = [c for c in ("فیلد", "کلید", "مقدار فعلی", "شاهد", "مالک", "نقش",
                        "اداره", "مدیر", "اقدام لازم") if c in worklist.columns]
    st.dataframe(worklist[show], hide_index=True, width="stretch",
                 column_config=_cfg(worklist[show]))
    st.download_button(
        f"⬇ فهرست کار «{chosen}» (Excel)",
        data=_excel({"فهرست کار": worklist}),
        file_name=f"GSI_Worklist_{chosen}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="trust_worklist_dl")


# ── تب ۵: آینه فیلدها ──────────────────────────────────────────────────────
def _fields(fields: Optional[pd.DataFrame], summary: Dict[str, Any]) -> None:
    if not isinstance(fields, pd.DataFrame) or fields.empty:
        st.info("کارنامه فیلدی موجود نیست.")
        return
    st.caption("ستون «شایع‌ترین مقدار نامعتبر» معمولاً کل ماجرا را لو می‌دهد: "
               "اکثر ایرادهای یک ستون، دو سه الگوی تکراری‌اند.")
    st.dataframe(fields.sort_values("پوشش (٪)"), hide_index=True,
                 width="stretch", column_config=_cfg(fields))
    routable = summary.get("routable_pct")
    if routable is not None and routable < 100:
        st.warning(f"{100 - routable:.0f}٪ ایرادها مالک مشخصی ندارند و قابل ارجاع نیستند. "
                   "این یک مشکل «قرارداد سورس» است، نه بی‌دقتی کارشناسان.")


# ── تب ۶: روند ─────────────────────────────────────────────────────────────
#: Below this many runs a line has no shape to read, and a flat two-point chart
#: implies a precision the programme does not have yet.
_MIN_POINTS_FOR_A_LINE = 4


def _trend(history: pd.DataFrame) -> None:
    if history is None or history.empty:
        st.info("هنوز سابقه‌ای ثبت نشده است؛ همین اجرا نقطه صفر می‌شود.")
        return
    st.caption("معیار ما تغییر است، نه مقدار مطلق. هر اجرای خط لوله یک نقطه اضافه می‌کند.")
    deltas = trend_mod.compare(history)
    if deltas:
        _trend_metrics(deltas)
    else:
        st.markdown(f'<div class="tr-note">{trend_mod.headline_fa(history)}</div>',
                    unsafe_allow_html=True)
    frame = trend_mod.trend_frame(history)
    st.dataframe(frame, hide_index=True, width="stretch", column_config=_cfg(frame))
    if len(history) >= _MIN_POINTS_FOR_A_LINE:
        _defects_chart(history)


def _trend_metrics(deltas) -> None:
    """One card per tracked metric: where it stands and which way it moved.

    Cards rather than three small line charts: at this stage most series are
    flat, and a flat line drawn on an auto-scaled axis sits exactly on a
    gridline and disappears — a chart that shows nothing reads as a chart that
    is broken. The arrow on a card cannot vanish.
    """
    for box, delta in zip(st.columns(len(deltas)), deltas):
        with box:
            st.metric(
                delta.label,
                f"{delta.current:,.0f}",
                delta=None if delta.change == 0 else f"{delta.change:+,.0f}",
                # Direction is per metric: fewer open defects is the win, more
                # decision-grade answers is the win. Streamlit's default paints
                # every rise green, which would congratulate the wrong move.
                delta_color="normal" if delta.better_direction > 0 else "inverse")


def _defects_chart(history: pd.DataFrame) -> None:
    """The one series worth a line: open defects over time.

    Deliberately a single chart. The other tracked metrics are bounded small
    integers whose movement the cards above already state exactly; drawing them
    as lines adds axes without adding information.
    """
    if "defects" not in history.columns:
        return
    label = "ایراد باز"
    series = history[["at", "defects"]].copy()
    # Full timestamps as tick labels are longer than the chart is wide and get
    # rotated on top of the plot. Runs are ordered, so the time alone is enough.
    series["at"] = _short_run_labels(series["at"])
    series = series.set_index("at")
    series.columns = [label]
    moved = float(series[label].iloc[-1]) - float(series[label].iloc[0])
    tone = "neutral" if moved == 0 else ("good" if moved < 0 else "critical")
    st.markdown(f'<div class="tr-note" style="color:{T.STATUS[tone].ink};'
                f'font-weight:700">{label} در طول زمان</div>', unsafe_allow_html=True)
    st.line_chart(series, color=T.STATUS[tone].fill, height=260,
                  x_label="", use_container_width=True)


def _short_run_labels(stamps: pd.Series) -> pd.Series:
    """``HH:MM`` while every run is from one day, otherwise ``MM-DD HH:MM``."""
    text = stamps.astype(str)
    days = text.str.slice(0, 10)
    if days.nunique() <= 1:
        return text.str.slice(11, 16)
    return days.str.slice(5) + " " + text.str.slice(11, 16)


def run(extras: Optional[Dict[str, Any]] = None, ref_date: str = "") -> None:
    st.title("اعتماد داده و کیفیت")
    render(extras, ref_date)
