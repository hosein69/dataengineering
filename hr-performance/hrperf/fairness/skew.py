# -*- coding: utf-8 -*-
"""چولگی فشار کار — چه کسی بارِ چه کسی را می‌کشد.

## چرا این ماژول، مهم‌ترین بخش عدالت است

سیستم‌های ارزیابی عملکرد معمولاً یک اشتباه ساختاری دارند: **نتیجه** را
می‌سنجند و **شرایط** را نمی‌بینند. کسی که سه برابر دیگران پرونده دارد،
اگر کیفیتش کمی پایین‌تر باشد امتیاز کمتری می‌گیرد — و این دقیقاً اجحاف
است، چون همان حجمِ بیشتر، خودش علتِ افت است.

بدتر از آن: وقتی توزیع بار چوله باشد و کسی متوجه نشود، سیستم ارزیابی
عملاً **به بی‌عدالتی پاداش می‌دهد**؛ کسی که بار کمتری برداشته امتیاز
بالاتر می‌گیرد و کسی که بار سازمان را کشیده جریمه می‌شود.

پس پیش از هر امتیازی، باید پرسید: **آیا بار عادلانه پخش شده؟**

## سنجه‌ها، و چرا این‌ها

* **ضریب جینی** (Gini, 1912) — استاندارد جهانی سنجش نابرابری توزیع. صفر
  یعنی کاملاً برابر، یک یعنی همه بار روی یک نفر. برای بار کاری همان
  معنایی را دارد که برای درآمد.
* **منحنی لورنتس** — همان اطلاعات، ولی دیدنی: «۲۰٪ افراد چند درصد بار را
  می‌کشند؟»
* **نسبت ۹۰/۱۰** — بار نفر صدک ۹۰ تقسیم بر نفر صدک ۱۰. عددی که در جلسه
  بلافاصله فهمیده می‌شود، برخلاف جینی.
* **انحراف از میانه گروه همتا** — چه کسی مشخصاً بیش‌بار یا کم‌بار است.
  آستانه بر مبنای MAD است نه انحراف معیار، چون خودِ فرد پرت، انحراف معیار
  را بزرگ می‌کند و آنگاه «پرت» به نظر نمی‌رسد.

## قاعده‌ای که شکسته نمی‌شود

هیچ‌کدام از این‌ها **امتیاز فرد** را عوض نمی‌کنند. اینجا فقط اندازه‌گیری
و اعلام است. تعدیل امتیاز بابت بار، کار ماژول ``adjust`` است و آنجا هم
صریح و قابل خاموش‌کردن است — چون تصمیم درباره «چقدر بار باید جبران شود»
تصمیم سازمانی است، نه آماری.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

#: زیر این تعداد نفر، هیچ سنجه نابرابری گزارش نمی‌شود. جینیِ سه‌نفره
#: عدد است ولی معنا ندارد.
MIN_GROUP = 5

#: ضریب آستانه بر حسب MAD برای «بیش‌بار» و «کم‌بار».
#: ۱٫۴۸۲۶ ضریب تبدیل MAD به معادل انحراف معیار در توزیع نرمال است.
MAD_TO_SIGMA = 1.4826
OUTLIER_K = 2.0

#: مرزهای تفسیر جینی. اعداد قراردادی‌اند و در گزارش هم به‌عنوان «قرارداد»
#: معرفی می‌شوند، نه به‌عنوان قانون طبیعت.
GINI_BANDS: List[Tuple[float, str, str]] = [
    (0.20, "متوازن", "توزیع بار قابل قبول است."),
    (0.35, "کمی چوله", "تفاوت محسوس ولی هنوز قابل توجیه."),
    (0.50, "چوله", "بخش بزرگی از بار روی اقلیتی از افراد است."),
    (1.01, "به‌شدت چوله", "توزیع بار ناعادلانه است و ارزیابی عملکرد را نیز مخدوش می‌کند."),
]


def gini(values: pd.Series) -> float:
    """ضریب جینی توزیع بار.

    صفر = همه دقیقاً برابر · یک = همه بار روی یک نفر.
    مقادیر منفی معنا ندارند و کنار گذاشته می‌شوند (بار منفی وجود ندارد).
    """
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v >= 0].sort_values().to_numpy(dtype=float)
    n = len(v)
    if n < 2 or v.sum() <= 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return float((2 * (idx * v).sum()) / (n * v.sum()) - (n + 1) / n)


def lorenz(values: pd.Series, points: int = 21) -> List[Tuple[float, float]]:
    """نقاط منحنی لورنتس: (سهم تجمعی افراد، سهم تجمعی بار)."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v >= 0].sort_values().to_numpy(dtype=float)
    if len(v) < 2 or v.sum() <= 0:
        return []
    cum = np.concatenate([[0.0], np.cumsum(v) / v.sum()])
    xs = np.linspace(0, 1, len(cum))
    grid = np.linspace(0, 1, points)
    return [(float(g), float(np.interp(g, xs, cum))) for g in grid]


def ratio_90_10(values: pd.Series) -> float:
    """بار صدک ۹۰ تقسیم بر صدک ۱۰ — عددی که بی‌واسطه فهمیده می‌شود."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v >= 0]
    if len(v) < MIN_GROUP:
        return float("nan")
    lo = float(v.quantile(0.10))
    hi = float(v.quantile(0.90))
    if lo <= 0:
        return float("inf") if hi > 0 else float("nan")
    return hi / lo


def top_share(values: pd.Series, frac: float = 0.20) -> float:
    """سهم پرکارترین ``frac`` از کل بار."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v >= 0].sort_values(ascending=False)
    if v.empty or v.sum() <= 0:
        return float("nan")
    k = max(1, int(round(len(v) * frac)))
    return float(v.iloc[:k].sum() / v.sum())


def band_of(g: float) -> Tuple[str, str]:
    """برچسب و توضیح یک مقدار جینی."""
    if not np.isfinite(g):
        return "نامشخص", "داده کافی برای سنجش توزیع نیست."
    for cut, label, note in GINI_BANDS:
        if g < cut:
            return label, note
    return GINI_BANDS[-1][1], GINI_BANDS[-1][2]


@dataclass
class SkewReport:
    """گزارش چولگی یک گروه."""
    group: str
    n: int
    total: float
    gini: float
    p90_p10: float
    top20: float
    median: float
    mad: float
    lorenz: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def enough(self) -> bool:
        return self.n >= MIN_GROUP

    @property
    def band(self) -> str:
        return band_of(self.gini)[0]

    @property
    def note(self) -> str:
        return band_of(self.gini)[1]


def _mad(v: pd.Series) -> float:
    x = pd.to_numeric(v, errors="coerce").dropna()
    if x.empty:
        return float("nan")
    return float((x - x.median()).abs().median())


def analyse_group(values: pd.Series, group: str = "") -> SkewReport:
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v >= 0]
    return SkewReport(
        group=group, n=int(len(v)), total=float(v.sum()),
        gini=gini(v), p90_p10=ratio_90_10(v), top20=top_share(v),
        median=float(v.median()) if len(v) else float("nan"),
        mad=_mad(v), lorenz=lorenz(v))


def by_group(df: pd.DataFrame, load_col: str,
             group_col: Optional[str] = None) -> List[SkewReport]:
    """چولگی کل، و به تفکیک گروه اگر ستون گروه داده شود."""
    if load_col not in df.columns:
        return []
    out = [analyse_group(df[load_col], "کل سازمان")]
    if group_col and group_col in df.columns:
        for key, sub in df.groupby(df[group_col].fillna("—").astype(str)):
            rep = analyse_group(sub[load_col], str(key))
            if rep.enough:
                out.append(rep)
    return out


#: برچسب وضعیت بار فرد
BALANCED, OVER, UNDER = "متوازن", "بیش‌بار", "کم‌بار"


def flag_individuals(df: pd.DataFrame, load_col: str,
                     peer_col: Optional[str] = None,
                     k: float = OUTLIER_K) -> pd.DataFrame:
    """چه کسی نسبت به **گروه همتای خودش** بیش‌بار یا کم‌بار است.

    آستانه از MAD می‌آید نه انحراف معیار: خودِ فرد بیش‌بار، انحراف معیار
    را بالا می‌برد و در نتیجه دیگر «پرت» به نظر نمی‌رسد — همان مکانیزمی
    که باعث می‌شود بی‌عدالتی آشکار، آماری نامرئی شود.
    """
    if load_col not in df.columns:
        return pd.DataFrame()
    work = df.copy()
    grp = (work[peer_col].fillna("—").astype(str)
           if peer_col and peer_col in work.columns
           else pd.Series("کل", index=work.index))
    load = pd.to_numeric(work[load_col], errors="coerce")

    med = load.groupby(grp).transform("median")
    mad = load.groupby(grp).transform(lambda s: (s - s.median()).abs().median())
    size = load.groupby(grp).transform("size")

    scale = mad * MAD_TO_SIGMA
    # MAD صفر یعنی بیش از نیمی از گروه دقیقاً روی میانه‌اند؛ آنگاه
    # انحراف نسبی مبنا می‌شود تا تقسیم بر صفر رخ ندهد.
    fallback = med.abs().where(med.abs() > 0, 1.0) * 0.25
    scale = scale.where(scale > 0, fallback)

    z = (load - med) / scale
    status = pd.Series(BALANCED, index=work.index, dtype=object)
    status = status.mask(z > k, OVER)
    status = status.mask(z < -k, UNDER)
    status = status.mask(load.isna() | (size < MIN_GROUP), "نامشخص")

    return pd.DataFrame({
        "گروه همتا": grp,
        "بار": load,
        "میانه گروه": med,
        "انحراف نسبی": z.round(2),
        "وضعیت بار": status,
        "نسبت به میانه": (load / med.where(med > 0)).round(2),
    }, index=work.index)


def rebalance_hint(flags: pd.DataFrame) -> Dict[str, float]:
    """چقدر بار باید جابه‌جا شود تا گروه به میانه برسد.

    عدد اجرایی است نه تئوریک: «برای رسیدن به میانه، این‌قدر پرونده باید
    از بیش‌بارها به کم‌بارها منتقل شود».
    """
    if flags.empty or "وضعیت بار" not in flags.columns:
        return {}
    over = flags[flags["وضعیت بار"] == OVER]
    under = flags[flags["وضعیت بار"] == UNDER]
    excess = float((over["بار"] - over["میانه گروه"]).clip(lower=0).sum())
    room = float((under["میانه گروه"] - under["بار"]).clip(lower=0).sum())
    return {
        "نفرات بیش‌بار": int(len(over)),
        "نفرات کم‌بار": int(len(under)),
        "بار مازاد بیش‌بارها": round(excess, 1),
        "ظرفیت خالی کم‌بارها": round(room, 1),
        "قابل جابه‌جایی": round(min(excess, room), 1),
    }
