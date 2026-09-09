# -*- coding: utf-8 -*-
"""تولید داده آزمون با تله‌های واقعی.

هر تله یک باگ واقعیِ سنجش عملکرد را پوشش می‌دهد:

  T1  فردی با نمونه بسیار کوچک و مقدار عالی   → نباید رتبه اول شود
  T2  فردی با نمونه بزرگ و مقدار خوب          → باید بالا بایستد
  T3  گروه همتای کوچک‌تر از حد نصاب            → باید صعود کند و ثبت شود
  T4  مخدوش‌کننده واقعی (سختی کار)             → همبستگی خام باید گمراه کند
  T8  سنجهٔ حوزه‌ای برای حوزهٔ دیگر               → نباید اصلاً ساخته شود
  T5  فرد با داده ناقص                          → پوشش پایین، نه امتیاز پایین
  T6  دو مدیریت و چند اداره و چند نوع کار      → مقایسه نباید بین‌گروهی شود
  T7  شاخص کاملاً خالی                          → نباید خط لوله را بشکند
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from hrperf.identity import roles, scopes

#: حوزهٔ ناشناخته — کلید خالی، تا map هرگز None نشود.
_NO_SCOPE = scopes.Scope("", "", "", (), ())

MANAGEMENTS = ["مدیریت خرید خارجی مواد اولیه", "مدیریت خرید خارجی قطعات تولیدی"]
#: اداره و نقش کاری جفت‌اند — کارشناس ترخیص در اداره ترخیص می‌نشیند.
DEPARTMENTS = ["اداره ترخیص", "اداره اعتبارات", "اداره ثبت سفارش",
               "اداره خرید خارجی", "اداره رفع تعهد ارزی", "اداره کنترل اسناد"]
#: هفت نقش کاری متمایز — «کارشناس» یک شغل نیست، هفت شغل است.
JOB_FAMILIES = ["کارشناس ترخیص", "کارشناس اعتبارات", "کارشناس ثبت سفارش",
                "کارشناس خرید خارجی", "کارشناس رفع تعهد ارزی",
                "کارشناس کنترل اسناد"]
ROLES = ["کارشناس", "مسئول", "رئیس"]


def build(n_people: int = 60, seed: int = 11) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(people, long) — جدول افراد و جدول بلند شاخص‌ها."""
    rng = np.random.default_rng(seed)

    rows = []
    for i in range(n_people):
        mg = MANAGEMENTS[i % 2]
        # T6: توزیع واقعی روی اداره و نوع کار
        d = DEPARTMENTS[i % len(DEPARTMENTS)]
        jf = JOB_FAMILIES[i % len(JOB_FAMILIES)]
        role = ROLES[0] if i % 11 else ROLES[1]
        if i in (0, 1):
            role = ROLES[2]
        rows.append({
            "person_key": f"E{1000+i}",
            "full_name": f"کارمند {i+1}",
            "personnel_id": f"{1000+i}",
            "vice": "معاونت خرید",
            "management": mg,
            "department": d,
            "job_family": jf,
            "role": role,
            "manager": f"مدیر {i % 4 + 1}",
            "head": f"رئیس {i % 3 + 1}",
            "active": 1,
            "tenure_years": float(rng.integers(1, 25)),
        })
    # T3: یک گروه عمداً کوچک
    rows.append({
        "person_key": "E9001", "full_name": "کارمند تک‌نفره",
        "personnel_id": "9001", "vice": "معاونت خرید",
        "management": MANAGEMENTS[0], "department": "اداره ویژه",
        "job_family": "کارشناس بازرگانی", "role": "کارشناس",
        "manager": "مدیر ۱", "head": "رئیس ۱", "active": 1,
        "tenure_years": 3.0,
    })
    people = pd.DataFrame(rows)
    n = len(people)

    # ── درایورهای پنهان ──
    assignment = pd.Categorical(people["department"]).codes.astype(float)
    difficulty = 0.9 * assignment + rng.normal(0, .4, n)
    tenure = people["tenure_years"].to_numpy(dtype=float)
    tz = (tenure - tenure.mean()) / (tenure.std() or 1)

    # ── اندازه نمونه: بیشتر افراد بزرگ، دو نفر عمداً ریز ──
    cases = rng.integers(40, 260, n).astype(float)
    cases[2] = 2.0      # T1
    cases[3] = 3.0      # T1
    cases[4] = 240.0    # T2

    def rate(base, d_coef, t_coef, sd, lo=.02, hi=.99):
        return np.clip(base - d_coef * difficulty + t_coef * tz
                       + rng.normal(0, sd, n), lo, hi)

    # ── اتکاپذیری ──
    on_time = rate(.86, .05, .03, .04)
    doc_ok = rate(.82, .04, .03, .05)
    no_dev = rate(.80, .05, .02, .05)
    perfect = np.clip(on_time * doc_ok * no_dev, .01, .99)   # همه‌یا‌هیچ
    perfect[2] = 1.0    # T1: بی‌نقص ولی با n=2
    perfect[3] = 1.0
    perfect[4] = 0.93   # T2

    # ── انطباق ──
    conformance = rate(.85, .06, .03, .04)
    skipped = np.clip(1 - no_dev + rng.normal(0, .02, n), .0, .8)
    violation = np.clip(.08 + .03 * difficulty + rng.normal(0, .02, n), .0, .6)

    # ── پاسخ‌گویی ──
    ball_days = np.clip(18 - 5 * tz + 6 * difficulty + rng.normal(0, 4, n), 1, 200)
    leg_days = np.clip(ball_days * 1.4 + rng.normal(0, 3, n), 1, 300)
    aging = np.clip(.22 + .06 * difficulty - .04 * tz + rng.normal(0, .05, n), .0, .95)

    # ── کیفیت داده و همکاری ──
    traceable = rate(.88, .04, .03, .04)
    clean_handover = no_dev.copy()

    # ── بار و زمینه ──
    parts = rng.integers(5, 90, n).astype(float)
    mix = np.clip(.45 + .05 * difficulty + rng.normal(0, .06, n), .05, .8)
    value_eur = np.clip(120000 + 60000 * assignment + rng.normal(0, 25000, n), 0, None)

    # ── سنجه‌های حوزه‌ای ──
    owner_complete = rate(.75, .05, .04, .06)
    crit_mix = np.clip(.12 + .05 * assignment / 5 + rng.normal(0, .04, n), .0, .8)
    overdue = np.clip(.18 + .05 * difficulty - .03 * tz + rng.normal(0, .05, n), .0, .9)
    alloc_lag = np.clip(24 + 7 * difficulty - 4 * tz + rng.normal(0, 5, n), 1, 300)
    in_full = rate(.70, .05, .03, .06)
    dwell = np.clip(35 + 12 * difficulty - 6 * tz + rng.normal(0, 8, n), 1, 400)

    scope_key = people["job_family"].map(
        lambda v: (scopes.of_family(roles.classify(v) or "") or _NO_SCOPE).key)

    def rec(metric, values, sample=None, scope=scopes.ANY):
        """یک سنجه؛ سنجهٔ حوزه‌ای فقط برای افراد همان حوزه ساخته می‌شود."""
        m = (pd.Series(True, index=people.index) if scope == scopes.ANY
             else scope_key.eq(scope))
        smp = (pd.Series(sample, index=people.index) if sample is not None
               else pd.Series(np.nan, index=people.index))
        return pd.DataFrame({
            "person_key": people["person_key"][m],
            "metric_key": metric,
            "value": pd.Series(values, index=people.index)[m],
            "sample_n": smp[m],
            "source": "synthetic",
            "scope": scope,
        })

    P, C, L = (scopes.SCOPES[0].key, scopes.SCOPES[1].key, scopes.SCOPES[2].key)
    frames = [
        rec("perfect_flow_rate", perfect, cases),
        rec("on_time_stage_rate", on_time, cases),
        rec("doc_accuracy_rate", doc_ok, cases * .8),
        rec("conformance_score", conformance, cases),
        rec("skipped_activity_rate", skipped, cases),
        rec("order_violation_rate", violation, cases),
        rec("ball_in_court_days", ball_days, cases * .5),
        rec("own_leg_median_days", leg_days, cases * .6),
        rec("aging_backlog_rate", aging, cases * .5),
        rec("status_traceability", traceable, cases),
        rec("clean_handover_rate", clean_handover, cases * .7),
        rec("case_load", cases, cases),
        rec("distinct_parts", parts, cases),
        rec("transport_mix_difficulty", mix, cases),
        rec("value_at_risk", value_eur, cases),
        rec("owner_field_completeness", owner_complete, cases, P),
        rec("part_criticality_mix", crit_mix, cases, P),
        rec("overdue_commitment_rate", overdue, cases, C),
        rec("allocation_lag_days", alloc_lag, cases * .6, C),
        rec("in_full_rate", in_full, cases * .7, L),
        rec("customs_dwell_days", dwell, cases * .6, L),
    ]
    long = pd.concat(frames, ignore_index=True)

    # T5: یک نفر با داده ناقص
    long = long[~((long["person_key"] == people["person_key"].iloc[6])
                  & (long["metric_key"].isin(
                      ["perfect_flow_rate", "on_time_stage_rate",
                       "doc_accuracy_rate"])))]
    # T7: یک شاخص کاملاً خالی
    long.loc[long["metric_key"] == "distinct_parts", "value"] = np.nan

    return people, long.reset_index(drop=True)
