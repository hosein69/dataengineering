# -*- coding: utf-8 -*-
"""پایه‌های آماری گزارش تحلیلی — سبک، بسته، و قابل استناد.

## چرا این‌طور و نه یادگیری ماشین

می‌شد یک مدل درختی یا شبکه روی همین داده آموزش داد و «احتمال بحرانی شدن»
بیرون داد. عمداً این کار نشده، به سه دلیل:

**۱) قابل استناد بودن.** عددی که در جلسه مدیریتی روی میز می‌رود باید
بتواند به یک جمله ساده تجزیه شود: «از ۱۲۰ سفارش مشابه، ۳۸ تا دیر شدند.»
خروجی یک مدل جعبه‌سیاه چنین جمله‌ای ندارد؛ «مدل گفت» پاسخ قابل دفاعی در
برابر کسی که با نتیجه مخالف است نیست.

**۲) اندازه داده.** تعداد پرونده‌ها در این دامنه در حد چند هزار است، نه
چند میلیون. در این اندازه، نرخ تجربی با بازه اطمینان هم دقیق‌تر است و هم
صادق‌تر از یک مدل که واریانسش را پنهان می‌کند.

**۳) پایداری.** مدل آموزش‌دیده با هر اجرا کمی فرق می‌کند و کسی نمی‌فهمد
چرا. فرمول بسته، هر بار همان عدد را می‌دهد و بازتولیدپذیر است.

پس روش این است: **نرخ تجربی + بازه اطمینان + کنترل مخدوش‌کننده**، و هرجا
داده کم است، صریحاً «کافی نیست» گفته می‌شود.

## مراجع

* بازه اطمینان نسبت: Wilson (1927) — بر خلاف روش نرمال ساده، روی نسبت‌های
  نزدیک صفر و یک هم فرو نمی‌پاشد و برای n کوچک معتبر می‌ماند.
* حساسیت به مخدوش‌کننده مشاهده‌نشده: E-value، VanderWeele & Ding (2017),
  *Annals of Internal Medicine* 167(4):268-274.
* تجمیع لایه‌ای: Mantel & Haenszel (1959).
"""
from __future__ import annotations

__contract__ = 1

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

#: زیر این تعداد، هیچ نرخی گزارش نمی‌شود. عددی که از ۵ مورد درمی‌آید
#: «یافته» نیست، نویز است — و در گزارش مدیریتی، نویزِ با اعتمادبه‌نفس
#: بدتر از نبودِ عدد است.
MIN_N = 20

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Rate:
    """یک نرخ با شواهدش. هر عدد این کلاس در گزارش، n و بازه‌اش را همراه دارد."""
    k: int                      # تعداد رخداد
    n: int                      # تعداد کل
    lo: float                   # کران پایین بازه ۹۵٪
    hi: float                   # کران بالای بازه ۹۵٪

    @property
    def p(self) -> float:
        return self.k / self.n if self.n else float("nan")

    @property
    def enough(self) -> bool:
        return self.n >= MIN_N

    @property
    def width(self) -> float:
        return self.hi - self.lo

    def fa(self, nd: int = 1) -> str:
        if not self.n:
            return "—"
        return (f"{self.p * 100:.{nd}f}٪ "
                f"({self.lo * 100:.{nd}f} تا {self.hi * 100:.{nd}f}) از {self.n:,}")


def wilson(k: int, n: int, z: float = Z95) -> Rate:
    """بازه اطمینان Wilson برای یک نسبت.

    روش نرمالِ ساده (p ± z·√(p(1-p)/n)) برای نسبت‌های نزدیک صفر یا یک
    بازه‌ای بیرون از [0,1] می‌دهد و برای n کوچک بی‌معنا می‌شود. Wilson این
    مشکل را ندارد و همان فرمول بسته است — بدون نیاز به scipy.
    """
    k, n = int(k), int(n)
    if n <= 0:
        return Rate(0, 0, float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return Rate(k, n, max(0.0, centre - half), min(1.0, centre + half))


def rate_of(mask: pd.Series, outcome: pd.Series) -> Rate:
    """نرخ رخداد پیامد در زیرمجموعه‌ای که ``mask`` مشخص می‌کند."""
    sel = mask.fillna(False).astype(bool)
    sub = outcome[sel].fillna(False).astype(bool)
    return wilson(int(sub.sum()), int(sel.sum()))


@dataclass(frozen=True)
class Contrast:
    """مقایسه دو گروه — تفاضل نرخ، نسبت خطر، و حساسیت به مخدوش‌کننده."""
    label: str
    exposed: Rate               # گروه دارای ویژگی
    control: Rate               # بقیه

    @property
    def diff(self) -> float:
        return self.exposed.p - self.control.p

    @property
    def rr(self) -> float:
        """نسبت خطر. مقدار ۱ یعنی بی‌تفاوت."""
        if not self.control.p:
            return float("inf") if self.exposed.p else 1.0
        return self.exposed.p / self.control.p

    @property
    def enough(self) -> bool:
        return self.exposed.enough and self.control.enough

    @property
    def significant(self) -> bool:
        """بازه‌های دو گروه هم‌پوشانی ندارند.

        آزمون محافظه‌کارانه‌ای است (از آزمون رسمی سخت‌گیرتر)، و همین برای
        گزارشی که قرار است مبنای تصمیم شود مناسب‌تر است: چیزی را «یافته»
        اعلام نمی‌کند مگر شواهد روشن باشد.
        """
        if not self.enough:
            return False
        return self.exposed.lo > self.control.hi or self.control.lo > self.exposed.hi

    @property
    def e_value(self) -> float:
        """E-value: مخدوش‌کننده مشاهده‌نشده چقدر باید قوی باشد تا این رابطه را توضیح دهد.

        عدد ۱ یعنی «هیچ»؛ هرچه بزرگ‌تر، رابطه در برابر توضیح‌های جایگزین
        مقاوم‌تر. این عدد جای آزمایش تصادفی را نمی‌گیرد، ولی صریح می‌گوید
        نتیجه چقدر شکننده است — و همین آن را قابل استناد می‌کند.
        """
        rr = self.rr
        if not math.isfinite(rr) or rr <= 0:
            return float("inf")
        if rr < 1:
            rr = 1 / rr
        return rr + math.sqrt(rr * (rr - 1))


def contrast(label: str, mask: pd.Series, outcome: pd.Series) -> Contrast:
    sel = mask.fillna(False).astype(bool)
    return Contrast(label, rate_of(sel, outcome), rate_of(~sel, outcome))


def stratified_diff(mask: pd.Series, outcome: pd.Series,
                    strata: pd.Series) -> Tuple[Optional[float], int, List[str]]:
    """تفاضل نرخ **درون لایه‌ها**، وزن‌دار بر اساس اندازه لایه.

    این ساده‌ترین شکل کنترل مخدوش‌کننده است: اگر «روش حمل هوایی» بیشتر
    بحرانی می‌شود، شاید علتش هوایی بودن نباشد بلکه این باشد که قطعات
    فوری را هوایی می‌فرستند. با مقایسه **درون هر مدیریت**، آن توضیح
    جایگزین تا حد زیادی کنار می‌رود.

    خروجی: (تفاضل تجمیع‌شده، تعداد لایه معتبر، نام لایه‌های کنارگذاشته).
    اگر هیچ لایه‌ای داده کافی نداشته باشد، ``None`` — نه یک عدد بی‌پشتوانه.
    """
    sel = mask.fillna(False).astype(bool)
    out = outcome.fillna(False).astype(bool)
    st = strata.fillna("—").astype(str)

    num = den = 0.0
    used = 0
    dropped: List[str] = []
    for value, idx in st.groupby(st).groups.items():
        s, o = sel.loc[idx], out.loc[idx]
        a, b = wilson(int(o[s].sum()), int(s.sum())), wilson(int(o[~s].sum()), int((~s).sum()))
        if a.n < MIN_N // 2 or b.n < MIN_N // 2:
            dropped.append(str(value))
            continue
        w = a.n + b.n
        num += (a.p - b.p) * w
        den += w
        used += 1
    if not den:
        return None, 0, dropped
    return num / den, used, dropped


def median_iqr(values: pd.Series) -> Tuple[float, float, float, int]:
    """میانه و بازه میان‌چارکی — در برابر مقادیر پرت مقاوم‌اند، برخلاف میانگین."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return (float("nan"),) * 3 + (0,)
    return float(v.median()), float(v.quantile(0.25)), float(v.quantile(0.75)), int(len(v))
