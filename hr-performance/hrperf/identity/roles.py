# -*- coding: utf-8 -*-
"""نقش کاری (job family) — هر کارشناس با هم‌نقش خودش سنجیده می‌شود.

## چرا این ماژول

«کارشناس» یک شغل نیست، هفت شغل است: خرید خارجی، ثبت سفارش، اعتبارات،
رفع تعهد ارزی، ترخیص، کنترل اسناد، بازرگانی. سختی کار، مخرج شاخص‌ها و
چرخه زمانی هرکدام فرق دارد.

در پلتفرم AIBL تا نسخه ۲۶٫۵ همه در یک ستون «نام کارشناس» ادغام می‌شدند و
نام کارشناس ترخیص جای کارشناس خرید می‌نشست. اینجا از همان ابتدا نقش‌ها
جدا نگه داشته می‌شوند و **گروه همتا** روی همین نقش بسته می‌شود.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class JobFamily:
    key: str
    fa: str
    aliases: List[str]
    #: شاخص‌هایی که برای این نقش معنا دارند؛ بقیه برایش محاسبه نمی‌شود
    metrics: List[str]


#: هفت نقش کارشناسی. افزودن نقش = یک ورودی، بدون تغییر موتور.
FAMILIES: List[JobFamily] = [
    JobFamily("buyer", "کارشناس خرید خارجی",
              ["خرید", "خرید خارجی", "buyer", "purchasing", "EXPERT_BUYER"],
              ["fpy", "first_correction_success", "major_error_rate",
               "median_correction_hours", "completion_rate", "unique_orders",
               "rework_loss", "rework_rate"]),
    JobFamily("order_reg", "کارشناس ثبت سفارش",
              ["ثبت سفارش", "order registration", "EXPERT_ORDER_REG"],
              ["fpy", "first_correction_success", "under24_rate",
               "median_correction_hours", "completion_rate", "unique_orders",
               "open_bill_rate"]),
    JobFamily("credit", "کارشناس اعتبارات",
              ["اعتبارات", "credit", "lc", "EXPERT_CREDIT"],
              ["fpy", "first_correction_success", "median_correction_hours",
               "under24_rate", "completion_rate", "major_error_rate",
               "rework_loss"]),
    JobFamily("settlement", "کارشناس رفع تعهد ارزی",
              ["رفع تعهد", "تعهد ارزی", "settlement", "EXPERT_SETTLEMENT"],
              ["completion_rate", "median_correction_hours", "open_reject_ratio",
               "major_error_rate", "rework_loss", "unique_orders"]),
    JobFamily("clearance", "کارشناس ترخیص",
              ["ترخیص", "گمرک", "clearance", "customs", "EXPERT_CLEARANCE"],
              ["fpy", "median_correction_hours", "under24_rate",
               "completion_rate", "open_bill_rate", "unique_cases",
               "rework_rate"]),
    JobFamily("doc_control", "کارشناس کنترل اسناد",
              ["کنترل اسناد", "بررسی اسناد", "document checking", "EXPERT_DOC"],
              ["fpy", "first_correction_success", "under24_rate",
               "median_correction_hours", "open_reject_ratio", "unique_cases",
               "rework_rate", "ae_deferred_reject"]),
    JobFamily("commercial", "کارشناس بازرگانی",
              ["بازرگانی", "commercial", "EXPERT_COMMERCIAL"],
              ["fpy", "major_error_rate", "completion_rate", "unique_orders",
               "rework_loss"]),
]

BY_KEY: Dict[str, JobFamily] = {f.key: f for f in FAMILIES}
BY_FA: Dict[str, JobFamily] = {f.fa: f for f in FAMILIES}
LABELS: Dict[str, str] = {f.key: f.fa for f in FAMILIES}


def classify(value) -> Optional[str]:
    """متن آزاد (عنوان شغل، نام ستون، نقش) → کلید نقش کاری."""
    s = str(value or "").strip().lower()
    if not s:
        return None
    for f in FAMILIES:
        if s == f.key or s == f.fa.lower():
            return f.key
        for a in f.aliases:
            if a.lower() in s:
                return f.key
    return None


def metrics_for(job_family: Optional[str]) -> Optional[List[str]]:
    """شاخص‌های معنادار یک نقش؛ ``None`` یعنی محدودیتی نیست."""
    if not job_family:
        return None
    f = BY_KEY.get(job_family) or BY_FA.get(str(job_family))
    return list(f.metrics) if f else None


def applicable(long: pd.DataFrame, people: pd.DataFrame) -> pd.DataFrame:
    """رکوردهایی که برای نقشِ آن فرد بی‌معنا هستند را کنار می‌گذارد.

    بدون این فیلتر، «نرخ بارنامه باز» برای کارشناس اعتبارات هم محاسبه
    می‌شد و امتیازی می‌ساخت که هیچ ربطی به کار او ندارد.
    """
    if long.empty or people.empty or "job_family" not in people.columns:
        return long
    fam = (people.set_index("person_key")["job_family"]
           .map(lambda v: classify(v) or None))
    keep = []
    for pk, grp in long.groupby("person_key", sort=False):
        allowed = metrics_for(fam.get(pk))
        keep.append(grp if allowed is None
                    else grp[grp["metric_key"].isin(allowed)])
    return pd.concat(keep, ignore_index=True) if keep else long


def coverage(people: pd.DataFrame) -> pd.DataFrame:
    """توزیع نفرات روی نقش‌های کاری."""
    if people.empty or "job_family" not in people.columns:
        return pd.DataFrame()
    fam = people["job_family"].map(lambda v: classify(v) or "نامشخص")
    g = (fam.value_counts().rename_axis("نقش").reset_index(name="نفر"))
    g["نقش"] = g["نقش"].map(lambda k: LABELS.get(k, k))
    return g
