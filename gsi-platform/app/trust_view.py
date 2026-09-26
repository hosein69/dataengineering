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

import io
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from gsi.design import tokens as T
from gsi.trust import trend as trend_mod
from gsi.trust.fitness import GRADE_FA, GRADE_LICENCE_FA, GRADE_TONE, NOT_USABLE

# رنگ‌ها از همان پالت وضعیت سیستم طراحی می‌آیند (`gsi/design/tokens.py`)، که
# کنتراستش با WCAG سنجیده شده. هیچ hex دستی در این فایل نیست.


#: Column widths for the trust tables. Streamlit gives every column the same
#: default width and then scrolls horizontally, which in an RTL layout pushes
#: the *most useful* columns — the action sentence and the evidence locator —
#: off the left edge where nobody scrolls to find them.
_WIDE = ("مهم‌ترین اقدام", "اقدام پیشنهادی", "اقدام لازم", "شایع‌ترین مقدار نامعتبر",
         "توضیح")
_MEDIUM = ("تصمیم‌های متأثر", "نمونه کلید", "شاهد", "مالک", "نقش", "اداره", "فیلد")
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

    st.markdown(
        f'<div class="tr-hero"><h2>اعتماد داده — این اعداد چقدر قابل استنادند؟</h2>'
        f'<p>{headline}<br>{trend_mod.headline_fa(history)}</p></div>',
        unsafe_allow_html=True)

    tabs = st.tabs(["تصمیم‌ها", "حالا چه کار کنم؟", "کارنامه مالکان",
                    "آینه فیلدها", "روند بهبود"])

    with tabs[0]:
        _decisions(decisions)
    with tabs[1]:
        _next_fixes(extras.get("trust_next_fixes"))
    with tabs[2]:
        _owners(extras.get("trust_owners"), extras.get("trust_defects"))
    with tabs[3]:
        _fields(extras.get("trust_fields"), summary)
    with tabs[4]:
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


# ── تب ۳: کارنامه مالکان ───────────────────────────────────────────────────
def _owners(owners: Optional[pd.DataFrame], defects: Optional[pd.DataFrame]) -> None:
    if not isinstance(owners, pd.DataFrame) or owners.empty:
        st.info("مالکی برای ایرادها تشخیص داده نشد.")
        return
    st.caption("ترتیب این جدول بر اساس «چقدر می‌تواند آزاد کند» است، نه «چقدر ایراد دارد». "
               "معیار ارزیابی، نرخ بهبود است؛ مقدار مطلق در نقطه صفر تقصیر کسی نیست.")
    # The action sentence is a paragraph. Left in this grid it squeezes every
    # other column to nothing; the same sentence is one click away in the
    # per-person worklist below, and it is kept in full in the Excel export.
    grid = owners.drop(columns=["مهم‌ترین اقدام"], errors="ignore")
    st.dataframe(grid, hide_index=True, width="stretch", column_config=_cfg(grid))

    if isinstance(defects, pd.DataFrame) and not defects.empty:
        names = [n for n in owners["مالک"].tolist() if n]
        if names:
            chosen = st.selectbox("فهرست کار یک نفر", names, key="trust_owner_pick")
            worklist = defects[defects["مالک"] == chosen]
            show = [c for c in ("فیلد", "کلید", "مقدار فعلی", "شاهد",
                                "اقدام لازم") if c in worklist.columns]
            st.dataframe(worklist[show], hide_index=True, width="stretch",
                         column_config=_cfg(worklist[show]))
            st.download_button(
                f"⬇ فهرست کار «{chosen}» (Excel)",
                data=_excel({"فهرست کار": worklist}),
                file_name=f"GSI_Worklist_{chosen}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="trust_worklist_dl")


# ── تب ۴: آینه فیلدها ──────────────────────────────────────────────────────
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


# ── تب ۵: روند ─────────────────────────────────────────────────────────────
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
