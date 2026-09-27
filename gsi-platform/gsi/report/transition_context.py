# -*- coding: utf-8 -*-
"""Context for observed process gaps; duration alone is not a bottleneck verdict."""
from __future__ import annotations

import pandas as pd


ACTIVITY_DOMAIN = {
    "ابلاغ سفارش به تأمین‌کننده": "خرید",
    "ایجاد تعهد ارزی": "ارز و تعهد",
    "تخصیص ارز": "ارز و تعهد",
    "خرید ارز": "ارز و تعهد",
    "ثبت تأمین وجه بانکی": "ارز و تعهد",
    "ثبت/دریافت سوئیفت": "ارز و تعهد",
    "شاهد حرکت محموله": "حمل",
    "ورود محموله": "حمل",
    "تخلیه محموله": "گمرک و ترخیص",
    "ارائه اسناد به بانک": "اسناد بانکی",
    "ثبت کوتاژ گمرکی": "گمرک و ترخیص",
    "صدور کد ساتا": "گمرک و ترخیص",
    "ترخیص درصدی": "گمرک و ترخیص",
    "ترخیص کامل": "گمرک و ترخیص",
    "ثبت رسید مالی": "دریافت مالی",
    "رفع تعهد": "رفع تعهد",
    "رفع تعهد انجام‌شده": "رفع تعهد",
}
ACTIVITY_DOMAIN.update({
    "PO Sent to Vendor": "خرید", "FX Commitment Created": "ارز و تعهد",
    "FX Allocated": "ارز و تعهد", "FX Purchased": "ارز و تعهد",
    "Bank Funding Recorded": "ارز و تعهد", "SWIFT Recorded": "ارز و تعهد",
    "Goods Movement Evidenced": "حمل", "Vessel Arrived": "حمل",
    "Cargo Discharged": "گمرک و ترخیص", "Documents Submitted": "اسناد بانکی",
    "Customs Declaration Filed": "گمرک و ترخیص", "SATA Code Issued": "گمرک و ترخیص",
    "Partially Cleared": "گمرک و ترخیص", "Fully Cleared": "گمرک و ترخیص",
    "Financial Receipt Booked": "دریافت مالی",
})


def annotate_transitions(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep measurements, explicitly withhold bottleneck status absent a matching rule.

    A transition may straddle two domains; its elapsed days cannot be assigned
    to either team. Even an in-domain median is descriptive without a case-level
    deadline, start condition and verified outcome. FX settlement deadlines live
    in the financial stage matrix, not this event-log transition table.
    """
    out = frame.copy()
    if not {"از فعالیت", "به فعالیت"}.issubset(out.columns):
        return out
    source = out["از فعالیت"].map(ACTIVITY_DOMAIN)
    target = out["به فعالیت"].map(ACTIVITY_DOMAIN)
    same = source.notna() & source.eq(target)
    known = source.notna() & target.notna()
    out["حوزه فرایندی"] = source.where(same, "گذار میان‌حوزه‌ای").where(known, "حوزه نامشخص")
    out["نوع مقایسه"] = "صرفاً توصیفی"
    out["وضعیت گلوگاه"] = "سنجش‌نشده"
    out["مبنای قضاوت"] = (
        "زمان مشاهده‌شده؛ برای تشخیص گلوگاه، مهلت معتبر و شاهدِ هر پرونده در همان حوزه لازم است"
    )
    return out
