# -*- coding: utf-8 -*-
"""تولید داده آزمون با تله‌های واقعی.

هر تله یک باگ واقعیِ سنجش عملکرد را پوشش می‌دهد:

  T1  فردی با نمونه بسیار کوچک و مقدار عالی   → نباید رتبه اول شود
  T2  فردی با نمونه بزرگ و مقدار خوب          → باید بالا بایستد
  T3  گروه همتای کوچک‌تر از حد نصاب            → باید صعود کند و ثبت شود
  T4  مخدوش‌کننده واقعی (سختی کار)             → همبستگی خام باید گمراه کند
  T5  فرد با داده ناقص                          → پوشش پایین، نه امتیاز پایین
  T6  دو مدیریت و چند اداره و چند نوع کار      → مقایسه نباید بین‌گروهی شود
  T7  شاخص کاملاً خالی                          → نباید خط لوله را بشکند
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

MANAGEMENTS = ["مدیریت خرید خارجی مواد اولیه", "مدیریت خرید خارجی قطعات تولیدی"]
DEPARTMENTS = ["اداره ترخیص", "اداره اعتبارات", "اداره ثبت سفارش"]
JOB_FAMILIES = ["ترخیص", "اعتبارات", "ثبت سفارش"]
ROLES = ["کارشناس", "مسئول", "رئیس"]


def build(n_people: int = 60, seed: int = 11) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(people, long) — جدول افراد و جدول بلند شاخص‌ها."""
    rng = np.random.default_rng(seed)

    rows = []
    for i in range(n_people):
        mg = MANAGEMENTS[i % 2]
        # T6: توزیع واقعی روی اداره و نوع کار
        d = DEPARTMENTS[i % 3]
        jf = JOB_FAMILIES[i % 3]
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
        "job_family": "بازرسی", "role": "کارشناس",
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

    # ── شاخص‌ها ──
    base_fpy = 0.88 - 0.05 * difficulty + 0.03 * tz + rng.normal(0, .03, n)
    fpy = np.clip(base_fpy, 0.4, 0.999)
    fpy[2] = 1.0        # T1: عالی ولی با n=2
    fpy[3] = 1.0
    fpy[4] = 0.97       # T2: خوب با n=240

    speed_h = np.clip(30 - 6 * tz + 5 * difficulty + rng.normal(0, 4, n), 2, 200)
    under24 = np.clip(0.7 - 0.08 * difficulty + 0.05 * tz + rng.normal(0, .06, n), .05, .99)
    first_corr = np.clip(0.75 + 0.04 * tz - 0.05 * difficulty + rng.normal(0, .05, n), .1, .99)
    major_err = np.clip(0.06 + 0.03 * difficulty - 0.01 * tz + rng.normal(0, .02, n), .001, .5)
    completion = np.clip(0.85 + 0.03 * tz - 0.03 * difficulty + rng.normal(0, .05, n), .2, .99)
    open_reject = np.clip(0.2 + 0.05 * difficulty + rng.normal(0, .05, n), .0, .9)
    open_bill = np.clip(0.15 + 0.04 * difficulty + rng.normal(0, .04, n), .0, .9)
    rework_eur = np.clip(4000 + 2500 * difficulty + rng.normal(0, 900, n), 0, None)
    rework_rate = np.clip(0.12 + 0.04 * difficulty + rng.normal(0, .03, n), .0, .9)
    orders = rng.integers(10, 140, n).astype(float)
    fin_eur = np.clip(120000 + 60000 * assignment + rng.normal(0, 25000, n), 0, None)

    def rec(metric, values, sample=None):
        return pd.DataFrame({
            "person_key": people["person_key"],
            "metric_key": metric,
            "value": values,
            "sample_n": sample if sample is not None else np.nan,
            "source": "synthetic",
        })

    frames = [
        rec("fpy", fpy, cases),
        rec("first_correction_success", first_corr, cases * .4),
        rec("major_error_rate", major_err, orders),
        rec("median_correction_hours", speed_h, cases * .5),
        rec("under24_rate", under24, cases * .5),
        rec("completion_rate", completion, cases),
        rec("open_reject_ratio", open_reject, cases * .3),
        rec("open_bill_rate", open_bill, cases),
        rec("rework_loss", rework_eur, orders),
        rec("rework_rate", rework_rate, cases),
        rec("unique_cases", cases, cases),
        rec("unique_orders", orders, orders),
        rec("financial_responsibility", fin_eur, orders),
        rec("repeat_reject_rate", np.clip(1 - first_corr, 0, 1), cases * .4),
        rec("p75_correction_hours", speed_h * 1.7, cases * .5),
    ]
    long = pd.concat(frames, ignore_index=True)

    # T5: یک نفر با داده ناقص
    long = long[~((long["person_key"] == people["person_key"].iloc[6])
                  & (long["metric_key"].isin(
                      ["fpy", "first_correction_success", "under24_rate"])))]
    # T7: یک شاخص کاملاً خالی
    long.loc[long["metric_key"] == "open_bill_rate", "value"] = np.nan

    return people, long.reset_index(drop=True)
