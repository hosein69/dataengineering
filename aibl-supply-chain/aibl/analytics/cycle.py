# -*- coding: utf-8 -*-
"""زمان کجا می‌رود — و اگر یک مرحله بهبود یابد، چقدر برمی‌گردد.

خط لوله از قبل ۱۳ فعالیت تاریخ‌دار دارد. با همان‌ها می‌شود به دو سؤال
مدیریتی جواب داد، بدون هیچ داده تازه‌ای:

**۱) بین کدام دو رویداد بیشترین زمان می‌سوزد؟**
میانه و بازه میان‌چارکی، نه میانگین: چند پرونده رهاشده میانگین را چند
برابر می‌کنند و تصویر را غلط می‌سازند.

**۲) اگر آن مرحله به میانه‌ی خودش برسد، چند روز از کل چرخه کم می‌شود؟**
این یک **پادواقعیت ساده و صریح** است، نه پیش‌بینی: «اگر پرونده‌های کندتر
از میانه، به میانه می‌رسیدند، این‌قدر صرفه‌جویی می‌شد.» فرضش را هم کنار
عدد می‌نویسیم تا خواننده بتواند قبول یا ردش کند.

عمداً از مدل صف یا شبیه‌سازی استفاده نشده: آن‌ها فرض‌هایی درباره توزیع
ورود و ظرفیت لازم دارند که این داده تأییدشان نمی‌کند.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from ..resolve.part_status import TIMELINE, _to_date
from .evidence import MIN_N, median_iqr


@dataclass(frozen=True)
class Leg:
    """یک گام از چرخه: از فعالیت الف تا فعالیت ب."""
    frm: str
    to: str
    median: float
    q1: float
    q3: float
    n: int
    scope: str = ""

    @property
    def enough(self) -> bool:
        return self.n >= MIN_N

    @property
    def spread(self) -> float:
        return self.q3 - self.q1


def legs(df: pd.DataFrame, scope_of: Optional[dict] = None) -> List[Leg]:
    """مدت هر گام متوالی چرخه، بر حسب روز."""
    present = [a for a in TIMELINE if a[0] in df.columns]
    if len(present) < 2:
        return []
    present = sorted(present, key=lambda a: a[2])
    dates = {a[0]: _to_date(df[a[0]]) for a in present}
    out: List[Leg] = []
    for (c1, fa1, _o1, st1), (c2, fa2, _o2, _st2) in zip(present, present[1:]):
        delta = (dates[c2] - dates[c1]).dt.days
        # مدت منفی یعنی ترتیب رویدادها خراب است؛ آن ردیف‌ها در تحلیل
        # زمان کنار می‌روند و جداگانه به‌عنوان ناسازگاری گزارش می‌شوند.
        delta = delta[delta.notna() & (delta >= 0)]
        med, q1, q3, n = median_iqr(delta)
        if n:
            out.append(Leg(fa1, fa2, med, q1, q3, n,
                           (scope_of or {}).get(st1, "")))
    return out


def bottleneck(items: List[Leg]) -> Optional[Leg]:
    """کندترین گامِ دارای شواهد کافی."""
    ok = [x for x in items if x.enough]
    return max(ok, key=lambda x: x.median) if ok else None


@dataclass(frozen=True)
class WhatIf:
    leg: Leg
    slower_n: int          # چند پرونده کندتر از میانه بودند
    days_saved: float      # مجموع روزهای برگشتی
    per_case: float        # به‌ازای هر پرونده کند

    @property
    def assumption(self) -> str:
        return (f"فرض: پرونده‌هایی که در گام «{self.leg.frm} ← {self.leg.to}» "
                f"کندتر از میانه ({self.leg.median:,.0f} روز) بوده‌اند، به همان "
                f"میانه می‌رسیدند. هیچ فرض دیگری درباره ظرفیت یا اولویت نشده.")


def what_if(df: pd.DataFrame, leg: Leg) -> Optional[WhatIf]:
    """اگر گام کند به میانه‌اش برسد، چند روز آزاد می‌شود؟"""
    pair = {a[1]: a[0] for a in TIMELINE}
    c1, c2 = pair.get(leg.frm), pair.get(leg.to)
    if not c1 or not c2 or c1 not in df.columns or c2 not in df.columns:
        return None
    d = (_to_date(df[c2]) - _to_date(df[c1])).dt.days
    d = d[d.notna() & (d >= 0)]
    if len(d) < MIN_N:
        return None
    slower = d[d > leg.median]
    if slower.empty:
        return None
    saved = float((slower - leg.median).sum())
    return WhatIf(leg, int(len(slower)), saved, saved / len(slower))
