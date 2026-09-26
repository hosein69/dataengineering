# -*- coding: utf-8 -*-
"""سنجه‌های فرآیندی Kanban/Scrum از روی Event Log و جدول پرونده‌ها.

## چرا این ماژول جدا است

نماهای فرآیندی موجود (نقشه جریان، Aging، گلوگاه، Heatmap، Variant، Conformance،
Funnel، Timeline) وضعیت *لحظه‌ای* را خوب نشان می‌دهند ولی سه پرسش تصمیم‌سازِ
کانبان/اسکرام را جواب نمی‌دادند:

  * روند WIP در زمان چطور بوده؟            → Cumulative Flow
  * چند پرونده در هفته واقعاً بسته می‌شود؟  → Throughput
  * پروندهٔ بازِ امروز چقدر پیر است و کجای  → Aging WIP
    توزیع تاریخی قرار دارد؟

هر تابع اینجا **خالص** است: DataFrame می‌گیرد و DataFrame می‌دهد، به Streamlit
یا HTML وابسته نیست و هیچ مقداری را حدس نمی‌زند.

## قاعدهٔ صداقت

هیچ‌کدام از این توابع «هدف» یا SLA نمی‌سازند. صدک‌ها از رفتار **مشاهده‌شدهٔ**
گذشته می‌آیند؛ یک صدک ۸۵ درصدیِ ۴۰ روزه یعنی «تاکنون ۸۵٪ پرونده‌ها ظرف ۴۰ روز
بسته شده‌اند»، نه «هدف ۴۰ روز است». جایی که داده کافی نیست، ستون خالی برمی‌گردد
و صفر جای «نامعلوم» نمی‌نشیند.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pandas as pd

#: کمینهٔ تعداد مشاهده برای گزارش صدک. زیر این عدد، صدک گمراه‌کننده است.
MIN_SAMPLE_FOR_PERCENTILE = 3


def _col(frame: pd.DataFrame, names: Sequence[str]) -> Optional[str]:
    for n in names:
        if n in frame.columns:
            return n
    return None


def _empty(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _usable(frame) -> bool:
    return isinstance(frame, pd.DataFrame) and not frame.empty


# ══════════════════════════════════════════════════════════════════════════
#  ۱) Cumulative Flow — انباشت پرونده در هر مرحله، در طول زمان
# ══════════════════════════════════════════════════════════════════════════
CFD_COLUMNS = ("دوره", "مرحله", "ترتیب", "پرونده رسیده (انباشتی)")


def cumulative_flow(eventlog, freq: str = "W", max_periods: int = 16) -> pd.DataFrame:
    """چند پرونده تا پایان هر دوره به هر مرحله رسیده بود.

    این «انباشتی» است، نه «حاضر در مرحله»: یک پرونده که از مرحله عبور کرده هم
    شمرده می‌شود. فاصلهٔ عمودی بین دو منحنی، معنی WIP آن مرحله را می‌دهد.
    """
    if not _usable(eventlog):
        return _empty(CFD_COLUMNS)
    act = _col(eventlog, ["ACTIVITY_FA", "ACTIVITY_EN", "STAGE_FA"])
    case = _col(eventlog, ["_CASE_KEY", "CASE_KEY"])
    when = _col(eventlog, ["EVENTTIME", "EVENT_DATE"])
    if not (act and case and when):
        return _empty(CFD_COLUMNS)
    x = eventlog[[c for c in {act, case, when, "_SORTING"} if c in eventlog.columns]].copy()
    x[when] = pd.to_datetime(x[when], errors="coerce")
    x = x.dropna(subset=[when, act, case])
    if x.empty:
        return _empty(CFD_COLUMNS)
    order = {}
    if "_SORTING" in x.columns:
        z = x[[act, "_SORTING"]].dropna().sort_values("_SORTING").drop_duplicates(act)
        order = {str(a): i for i, a in enumerate(z[act].astype(str))}
    # اولین رسیدن هر پرونده به هر مرحله؛ رسیدن دوباره دوبار شمرده نمی‌شود.
    first = (x.groupby([x[act].astype(str), x[case].astype(str)])[when].min()
             .reset_index().rename(columns={act: "مرحله", case: "_case", when: "_at"}))
    first["دوره"] = first["_at"].dt.to_period(freq).dt.start_time
    periods = sorted(first["دوره"].unique())[-max_periods:]
    stages = sorted(first["مرحله"].unique(), key=lambda a: (order.get(a, 999), a))
    rows = []
    for stage in stages:
        seen = 0
        sub = first[first["مرحله"] == stage]
        per = sub.groupby("دوره")["_case"].nunique().to_dict()
        for p in periods:
            seen += int(per.get(p, 0))
            rows.append({"دوره": pd.Timestamp(p).date().isoformat(), "مرحله": stage,
                         "ترتیب": order.get(stage, 999),
                         "پرونده رسیده (انباشتی)": seen})
    return pd.DataFrame(rows, columns=list(CFD_COLUMNS))


# ══════════════════════════════════════════════════════════════════════════
#  ۲) Throughput — چند پرونده در هر دوره بسته شد
# ══════════════════════════════════════════════════════════════════════════
THROUGHPUT_COLUMNS = ("دوره", "پرونده بسته‌شده", "میانه متحرک ۴ دوره")


def throughput(case_table, freq: str = "W", max_periods: int = 16) -> pd.DataFrame:
    if not _usable(case_table):
        return _empty(THROUGHPUT_COLUMNS)
    state = _col(case_table, ["CASE_STATE"])
    last = _col(case_table, ["LAST_EVENT"])
    key = _col(case_table, ["CASE_KEY", "_CASE_KEY"])
    if not (state and last and key):
        return _empty(THROUGHPUT_COLUMNS)
    x = case_table[[state, last, key]].copy()
    x[last] = pd.to_datetime(x[last], errors="coerce")
    closed = x[x[state].astype(str).ne("OPEN")].dropna(subset=[last])
    if closed.empty:
        return _empty(THROUGHPUT_COLUMNS)
    g = (closed.assign(دوره=closed[last].dt.to_period(freq).dt.start_time)
         .groupby("دوره")[key].nunique().rename("پرونده بسته‌شده").reset_index()
         .sort_values("دوره"))
    g = g.tail(max_periods).reset_index(drop=True)
    g["میانه متحرک ۴ دوره"] = (g["پرونده بسته‌شده"].rolling(4, min_periods=2)
                                .median().round(1))
    g["دوره"] = g["دوره"].map(lambda d: pd.Timestamp(d).date().isoformat())
    return g[list(THROUGHPUT_COLUMNS)]


# ══════════════════════════════════════════════════════════════════════════
#  ۳) Aging WIP — پروندهٔ باز، سن آن، و جای آن در توزیع تاریخی
# ══════════════════════════════════════════════════════════════════════════
AGING_COLUMNS = ("پرونده", "مرحله جاری", "سن (روز)", "انتظار جاری (روز)",
                 "صدک ۵۰ تاریخی", "صدک ۸۵ تاریخی", "هشدار")


def aging_wip(case_table, limit: int = 60) -> pd.DataFrame:
    """پرونده‌های باز کنار صدک تاریخیِ همان مرحله.

    «هشدار» یک قاعدهٔ اختراعی نیست: فقط می‌گوید سن این پروندهٔ باز از صدکی که
    خودِ همین سازمان تاکنون داشته گذشته است یا نه.
    """
    if not _usable(case_table):
        return _empty(AGING_COLUMNS)
    state = _col(case_table, ["CASE_STATE"])
    stage = _col(case_table, ["LAST_ACTIVITY", "CURRENT_FOCUS_STAGE_FA"])
    key = _col(case_table, ["CASE_KEY", "_CASE_KEY"])
    age = _col(case_table, ["CASE_AGE_DAYS"])
    wait = _col(case_table, ["CURRENT_WAIT_DAYS"])
    thr = _col(case_table, ["THROUGHPUT_DAYS"])
    if not (state and stage and key and age):
        return _empty(AGING_COLUMNS)
    x = case_table.copy()
    x[age] = pd.to_numeric(x[age], errors="coerce")
    bench = {}
    if thr:
        done = x[x[state].astype(str).ne("OPEN")].copy()
        done[thr] = pd.to_numeric(done[thr], errors="coerce")
        done = done.dropna(subset=[thr])
        for name, grp in done.groupby(done[stage].astype(str)):
            if len(grp) >= MIN_SAMPLE_FOR_PERCENTILE:
                bench[name] = (round(float(grp[thr].quantile(.50)), 1),
                               round(float(grp[thr].quantile(.85)), 1))
    openc = x[x[state].astype(str).eq("OPEN")].dropna(subset=[age])
    rows = []
    for r in openc.sort_values(age, ascending=False).head(limit).to_dict("records"):
        st = str(r.get(stage) or "نامشخص")
        p50, p85 = bench.get(st, (None, None))
        a = float(r.get(age) or 0)
        alert = ("بیش از صدک ۸۵ تاریخی همین مرحله" if p85 is not None and a > p85
                 else "بیش از میانه تاریخی همین مرحله" if p50 is not None and a > p50
                 else "" if p50 is not None else "مبنای تاریخی کافی نیست")
        rows.append({"پرونده": str(r.get(key) or ""), "مرحله جاری": st,
                     "سن (روز)": round(a, 1),
                     "انتظار جاری (روز)": (round(float(r.get(wait)), 1)
                                            if wait and pd.notna(r.get(wait)) else None),
                     "صدک ۵۰ تاریخی": p50, "صدک ۸۵ تاریخی": p85, "هشدار": alert})
    return pd.DataFrame(rows, columns=list(AGING_COLUMNS))


# ══════════════════════════════════════════════════════════════════════════
#  ۴) توزیع زمان چرخه — صدک‌های مشاهده‌شده، نه هدف
# ══════════════════════════════════════════════════════════════════════════
CYCLE_COLUMNS = ("گروه", "پرونده بسته", "صدک ۵۰ (روز)", "صدک ۸۵ (روز)",
                 "صدک ۹۵ (روز)", "بیشینه (روز)")


def cycle_time_percentiles(case_table, by: str = "VARIANT") -> pd.DataFrame:
    if not _usable(case_table):
        return _empty(CYCLE_COLUMNS)
    thr = _col(case_table, ["THROUGHPUT_DAYS"])
    grp = _col(case_table, [by, "VARIANT", "LAST_ACTIVITY"])
    key = _col(case_table, ["CASE_KEY", "_CASE_KEY"])
    if not (thr and grp and key):
        return _empty(CYCLE_COLUMNS)
    x = case_table[[thr, grp, key]].copy()
    x[thr] = pd.to_numeric(x[thr], errors="coerce")
    x = x.dropna(subset=[thr])
    if x.empty:
        return _empty(CYCLE_COLUMNS)
    rows = []
    for name, g in x.groupby(x[grp].astype(str)):
        if len(g) < MIN_SAMPLE_FOR_PERCENTILE:
            rows.append({"گروه": name, "پرونده بسته": len(g), "صدک ۵۰ (روز)": None,
                         "صدک ۸۵ (روز)": None, "صدک ۹۵ (روز)": None,
                         "بیشینه (روز)": round(float(g[thr].max()), 1)})
            continue
        rows.append({"گروه": name, "پرونده بسته": len(g),
                     "صدک ۵۰ (روز)": round(float(g[thr].quantile(.50)), 1),
                     "صدک ۸۵ (روز)": round(float(g[thr].quantile(.85)), 1),
                     "صدک ۹۵ (روز)": round(float(g[thr].quantile(.95)), 1),
                     "بیشینه (روز)": round(float(g[thr].max()), 1)})
    out = pd.DataFrame(rows, columns=list(CYCLE_COLUMNS))
    return out.sort_values("پرونده بسته", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════
#  ۵) دوباره‌کاری — پرونده‌ای که به مرحله‌ای برمی‌گردد
# ══════════════════════════════════════════════════════════════════════════
REWORK_COLUMNS = ("فعالیت", "پرونده با تکرار", "کل تکرار اضافه", "بیشترین تکرار در یک پرونده")


def rework_loops(eventlog) -> pd.DataFrame:
    if not _usable(eventlog):
        return _empty(REWORK_COLUMNS)
    act = _col(eventlog, ["ACTIVITY_FA", "ACTIVITY_EN", "STAGE_FA"])
    case = _col(eventlog, ["_CASE_KEY", "CASE_KEY"])
    if not (act and case):
        return _empty(REWORK_COLUMNS)
    x = eventlog[[act, case]].dropna().astype(str)
    if x.empty:
        return _empty(REWORK_COLUMNS)
    counts = x.groupby([act, case]).size().rename("n").reset_index()
    repeats = counts[counts["n"] > 1]
    if repeats.empty:
        return _empty(REWORK_COLUMNS)
    out = (repeats.groupby(act)
           .agg(**{"پرونده با تکرار": (case, "nunique"),
                   "کل تکرار اضافه": ("n", lambda s: int((s - 1).sum())),
                   "بیشترین تکرار در یک پرونده": ("n", "max")})
           .reset_index().rename(columns={act: "فعالیت"}))
    return (out[list(REWORK_COLUMNS)]
            .sort_values("کل تکرار اضافه", ascending=False).reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════════
#  ۶) تحویل بین واحدها — کار کجا دست‌به‌دست می‌شود
# ══════════════════════════════════════════════════════════════════════════
HANDOFF_COLUMNS = ("از", "به", "تعداد تحویل", "پرونده", "میانه فاصله (روز)")


def handoff_matrix(eventlog, top: int = 20) -> pd.DataFrame:
    if not _usable(eventlog):
        return _empty(HANDOFF_COLUMNS)
    who = _col(eventlog, ["ORG_UNIT", "RESOURCE"])
    case = _col(eventlog, ["_CASE_KEY", "CASE_KEY"])
    when = _col(eventlog, ["EVENTTIME", "EVENT_DATE"])
    if not (who and case and when):
        return _empty(HANDOFF_COLUMNS)
    x = eventlog[[who, case, when]].copy()
    x[when] = pd.to_datetime(x[when], errors="coerce")
    x = x.dropna(subset=[when])
    x[who] = x[who].fillna("").astype(str).str.strip()
    x = x[x[who].ne("")]
    if x.empty:
        return _empty(HANDOFF_COLUMNS)
    x = x.sort_values([case, when])
    x["_next_who"] = x.groupby(case)[who].shift(-1)
    x["_next_at"] = x.groupby(case)[when].shift(-1)
    moves = x.dropna(subset=["_next_who", "_next_at"])
    moves = moves[moves["_next_who"].astype(str).ne(moves[who])]
    if moves.empty:
        return _empty(HANDOFF_COLUMNS)
    moves = moves.assign(_gap=(moves["_next_at"] - moves[when]).dt.total_seconds() / 86400.0)
    out = (moves.groupby([who, "_next_who"])
           .agg(**{"تعداد تحویل": (case, "size"), "پرونده": (case, "nunique"),
                   "میانه فاصله (روز)": ("_gap", "median")})
           .reset_index().rename(columns={who: "از", "_next_who": "به"}))
    out["میانه فاصله (روز)"] = out["میانه فاصله (روز)"].round(1)
    return (out[list(HANDOFF_COLUMNS)]
            .sort_values("تعداد تحویل", ascending=False).head(top).reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════════
#  ۷) پوشش مرحله‌ای — کدام مرحله اصلاً شاهد ندارد
# ══════════════════════════════════════════════════════════════════════════
COVERAGE_COLUMNS = ("مرحله", "ترتیب", "پرونده دارای شاهد", "پرونده بدون شاهد", "پوشش (٪)")


def stage_evidence_coverage(stage_matrix) -> pd.DataFrame:
    """چند درصد پرونده‌ها برای هر مرحله شاهد دارند.

    «بدون شاهد» یعنی اندازه‌گیری نشده، نه «انجام نشده». تفکیک این دو، همان چیزی
    است که یک تصمیم اشتباه را جلوگیری می‌کند.
    """
    if not _usable(stage_matrix):
        return _empty(COVERAGE_COLUMNS)
    stage = _col(stage_matrix, ["STAGE_FA", "STAGE_CODE"])
    order = _col(stage_matrix, ["STAGE_ORDER"])
    case = _col(stage_matrix, ["PROCESS_CASE_ID", "CASE_KEY", "_CASE_KEY"])
    obs = _col(stage_matrix, ["OBSERVATION_COUNT"])
    if not (stage and case):
        return _empty(COVERAGE_COLUMNS)
    x = stage_matrix.copy()
    x["_has"] = (pd.to_numeric(x[obs], errors="coerce").fillna(0) > 0) if obs else False
    rows = []
    for name, g in x.groupby(x[stage].astype(str)):
        total = int(g[case].nunique())
        with_ev = int(g[g["_has"]][case].nunique())
        rows.append({"مرحله": name,
                     "ترتیب": int(pd.to_numeric(g[order], errors="coerce").min()) if order else 999,
                     "پرونده دارای شاهد": with_ev,
                     "پرونده بدون شاهد": total - with_ev,
                     "پوشش (٪)": round(with_ev / total * 100, 1) if total else None})
    return (pd.DataFrame(rows, columns=list(COVERAGE_COLUMNS))
            .sort_values("ترتیب").reset_index(drop=True))


def build_all(extras) -> dict:
    """همهٔ سنجه‌های این ماژول از روی extras موجود.

    کلیدی که داده‌اش نیست، DataFrame خالی می‌گیرد؛ حذف نمی‌شود تا نبودِ آن هم
    در خروجی دیده شود.
    """
    get = (extras.get if hasattr(extras, "get") else (lambda k, d=None: d))
    ev, ct = get("eventlog"), get("case_table")
    return {
        "cfd": cumulative_flow(ev),
        "throughput": throughput(ct),
        "aging_wip": aging_wip(ct),
        "cycle_percentiles": cycle_time_percentiles(ct),
        "rework": rework_loops(ev),
        "handoff": handoff_matrix(ev),
        "stage_coverage": stage_evidence_coverage(get("process_stage_matrix")),
    }
