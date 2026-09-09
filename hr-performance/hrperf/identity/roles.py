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

from . import scopes as scopemod


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
              ["ترخیص", "گمرک", "clearance", "customs", "EXPERT_CLEARANCE",
               "حمل و لجستیک", "حمل", "لجستیک", "EXPERT_LOGISTICS"],
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


def applicable(long: pd.DataFrame, people: pd.DataFrame,
               model=None) -> pd.DataFrame:
    """رکوردهایی که برای حوزهٔ آن فرد بی‌معنا هستند را کنار می‌گذارد.

    دو صافی، به این ترتیب:

    **۱) حوزه مسئولیت** (اگر مدل، حوزهٔ سنجه‌ها را اعلام کرده باشد).
    کارشناس حمل بابت «تعهد ارزی معوق» سنجیده نمی‌شود و کارشناس بازرگانی
    بابت «رسوب گمرکی». سنجهٔ مشترک (``ANY``) برای همه می‌ماند.

    **۲) نقش کاری** — صافی قدیمی، برای سنجه‌هایی که در مدلِ حوزه‌دار
    نیستند (سورس‌های قدیمی HR). سنجه‌ای که هیچ‌کدام از دو صافی درباره‌اش
    حرفی ندارند، **حذف نمی‌شود**: نبودِ قاعده، دلیل حذف نیست.
    """
    if long.empty or people.empty or "job_family" not in people.columns:
        return long

    scope_of: Dict[str, Optional[str]] = {}
    idx = people.set_index("person_key")
    known = idx["scope"] if "scope" in idx.columns else None
    for pk in idx.index:
        sc = str(known.get(pk, "")).strip() if known is not None else ""
        if not sc or sc not in scopemod.BY_KEY:
            fam = classify(idx["job_family"].get(pk))
            s_ = scopemod.of_family(fam) if fam else None
            sc = s_.key if s_ else ""
        scope_of[str(pk)] = sc or None

    metric_scope: Dict[str, str] = {}
    if model is not None:
        metric_scope = {k: m.scope for k, m in model.metrics.items()}

    fam_of = (idx["job_family"].map(lambda v: classify(v) or None)).to_dict()
    keep = []
    for pk, grp in long.groupby("person_key", sort=False):
        allowed = metrics_for(fam_of.get(pk))
        mk = grp["metric_key"].astype(str)
        # صافی حوزه — فقط روی سنجه‌هایی که حوزه‌شان اعلام شده
        in_scope = mk.map(
            lambda k: scopemod.applies(metric_scope[k], scope_of.get(pk))
            if k in metric_scope else True)
        # صافی نقش — فقط روی سنجه‌هایی که مدل حوزه‌دار درباره‌شان ساکت است
        by_role = mk.map(
            lambda k: True if (k in metric_scope or allowed is None)
            else k in allowed)
        keep.append(grp[in_scope & by_role])
    return pd.concat(keep, ignore_index=True) if keep else long


def coverage(people: pd.DataFrame) -> pd.DataFrame:
    """توزیع نفرات روی نقش‌های کاری."""
    if people.empty or "job_family" not in people.columns:
        return pd.DataFrame()
    fam = people["job_family"].map(lambda v: classify(v) or "نامشخص")
    g = (fam.value_counts().rename_axis("نقش").reset_index(name="نفر"))
    g["نقش"] = g["نقش"].map(lambda k: LABELS.get(k, k))
    return g
