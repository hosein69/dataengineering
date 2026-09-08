# -*- coding: utf-8 -*-
"""نرمال‌سازی امتیاز — پایدار در برابر نمونه کوچک و پرت.

## دو ایراد اساسی پکیج قبلی که اینجا رفع می‌شود

**۱) انقباض خاموش بود.** در کد قبلی نوشته شده بود
``ADJUSTMENT_K = None`` با توضیح «تا وقتی k رسماً کالیبره شود».
یعنی هیچ انقباضی اعمال نمی‌شد و کسی با ۲ پرونده و شانسِ ۱۰۰٪ بالاتر از
کسی با ۳۰۰ پرونده و ۹۷٪ می‌ایستاد. جبرانِ آن، ضربِ **کل امتیاز نهایی**
در یک ضریب اعتماد بود — که جای اشتباهی است: فرد را به‌خاطر نبودِ داده در
شاخص‌های *دیگر* جریمه می‌کند، ولی خودِ شاخصِ کم‌نمونه همچنان رتبه کامل
می‌گیرد. اینجا k از خود داده برآورد می‌شود (روش گشتاورها) و انقباض
**در سطح همان شاخص** اعمال می‌گردد.

**۲) امتیاز صرفاً رتبه‌ای بود.** ``5 + 90*percentile`` یعنی بازی
حاصل‌جمع صفر: اگر کل تیم بهتر شود، هیچ امتیازی بالا نمی‌رود، و افزودن یک
نفر امتیاز همه را جابه‌جا می‌کند. اینجا امتیاز نسبت به یک **توزیع مرجع
منجمد** و با آمارهای مقاوم (میانه و MAD) ساخته می‌شود، پس بهبود واقعی
دیده می‌شود. رتبه همچنان گزارش می‌شود، ولی به‌عنوان زمینه، نه امتیاز.
"""
from __future__ import annotations

__contract__ = 1

import math
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

#: کف و سقف امتیاز — هیچ‌کس صفر یا صد مطلق نمی‌گیرد
SCORE_MIN, SCORE_MAX = 5.0, 95.0
#: ثابت تبدیل MAD به انحراف معیار برای توزیع نرمال
MAD_TO_SD = 1.4826


@dataclass(frozen=True)
class Reference:
    """توزیع مرجع منجمد یک شاخص."""
    metric: str
    center: float
    scale: float
    n: int

    @property
    def usable(self) -> bool:
        return self.n > 0 and math.isfinite(self.center) and self.scale > 0


def build_reference(values: pd.Series, metric: str = "") -> Reference:
    """میانه و MAD — مقاوم در برابر پرت، برخلاف میانگین و انحراف معیار."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return Reference(metric, math.nan, math.nan, 0)
    center = float(v.median())
    mad = float((v - center).abs().median())
    scale = mad * MAD_TO_SD
    if scale <= 0:                      # همه مقادیر یکسان‌اند
        sd = float(v.std(ddof=0))
        scale = sd if sd > 0 else 1.0
    return Reference(metric, center, scale, int(len(v)))


def calibrate_k(values: pd.Series, sample_n: pd.Series) -> float:
    """برآورد k انقباض از خود داده — نه یک عدد دستی، نه ``None``.

    مدل مؤلفه‌های واریانس: واریانسِ مقدارِ مشاهده‌شده هر فرد دو بخش دارد،
    نویز نمونه‌گیری که با n کوچک می‌شود، و تفاوت واقعی بین افراد:

        Var(xᵢ)  ≈  σ²/nᵢ  +  τ²

    پس اگر انحرافِ مجذور هر فرد را روی ``1/nᵢ`` رگرس کنیم، **عرض از مبدأ
    همان τ²** (تفاوت واقعی) و **شیب همان σ²** (نویز واحد) است. آنگاه:

        k = σ² / τ²

    شهودش: k بزرگ یعنی بیشترِ پراکندگیِ دیده‌شده نویز است نه مهارت، پس
    انقباض باید شدید باشد. پکیج قبلی این را هرگز کالیبره نکرد و انقباض را
    خاموش گذاشت.
    """
    v = pd.to_numeric(values, errors="coerce")
    n = pd.to_numeric(sample_n, errors="coerce")
    ok = v.notna() & n.notna() & (n > 0)
    if ok.sum() < 3:
        return 10.0                     # شواهد برای کالیبراسیون کافی نیست
    v = v[ok].astype(float).to_numpy()
    n = n[ok].astype(float).to_numpy()

    mu = float(np.average(v, weights=n))
    y = (v - mu) ** 2                   # انحراف مجذور
    x = 1.0 / n                         # وارون اندازه نمونه

    if np.allclose(x, x[0]):            # همه n یکسان — تفکیک ممکن نیست
        return float(np.median(n))

    # رگرسیون ساده y = τ² + σ²·x
    x_bar, y_bar = x.mean(), y.mean()
    denom = float(((x - x_bar) ** 2).sum())
    if denom <= 0:
        return float(np.median(n))
    sigma2 = float(((x - x_bar) * (y - y_bar)).sum() / denom)   # شیب
    tau2 = float(y_bar - sigma2 * x_bar)                        # عرض از مبدأ

    if sigma2 <= 0:
        return 0.5                      # نویزی دیده نمی‌شود ⇒ انقباض کمینه
    if tau2 <= 0:
        return 500.0                    # تفاوت واقعی قابل تشخیص نیست ⇒ انقباض بیشینه
    return float(min(max(sigma2 / tau2, 0.5), 500.0))


def shrink(values: pd.Series, sample_n: pd.Series, prior: float,
           k: float) -> pd.Series:
    """انقباض تجربی-بیزی به سمت میانگین گروه همتا.

    ``x̂ = (n·x + k·μ) / (n + k)`` — نمونه بزرگ تقریباً دست‌نخورده می‌ماند،
    نمونه کوچک به سمت میانگین گروه کشیده می‌شود.
    """
    v = pd.to_numeric(values, errors="coerce")
    n = pd.to_numeric(sample_n, errors="coerce")
    n = n.where(n.notna() & (n > 0), other=np.nan)
    if not math.isfinite(prior):
        prior = float(v.mean(skipna=True)) if v.notna().any() else 0.0
    out = (n * v + k * prior) / (n + k)
    # اگر n نامعلوم باشد، محافظه‌کارانه کاملاً به prior متمایل می‌شود
    return out.where(n.notna(), other=prior).where(v.notna(), other=np.nan)


def robust_score(values: pd.Series, direction: str,
                 reference: Optional[Reference] = None) -> pd.Series:
    """امتیاز ۵ تا ۹۵ نسبت به توزیع مرجع، با نگاشت لجستیک کراندار.

    برخلاف رتبه‌بندی، این امتیاز **مطلق** است: اگر کل گروه بهتر شود،
    امتیاز همه بالا می‌رود.
    """
    v = pd.to_numeric(values, errors="coerce")
    ref = reference or build_reference(v)
    out = pd.Series(np.nan, index=v.index, dtype=float)
    if not ref.usable:
        return out
    z = (v - ref.center) / ref.scale
    if direction == "lower":
        z = -z
    # لجستیک: z=0 → ۵۰ ، z=±۲ → حدود ۸۸/۱۲
    s = 50.0 + 45.0 * np.tanh(z / 2.0)
    return s.clip(SCORE_MIN, SCORE_MAX).where(v.notna(), other=np.nan)


def percentile_context(values: pd.Series, direction: str) -> pd.Series:
    """رتبه درصدی — فقط به‌عنوان زمینه گزارش می‌شود، نه امتیاز."""
    v = pd.to_numeric(values, errors="coerce")
    valid = v.dropna()
    out = pd.Series(np.nan, index=v.index, dtype=float)
    if len(valid) < 2:
        if len(valid) == 1:
            out.loc[valid.index] = 50.0
        return out
    r = valid.rank(method="average", ascending=(direction == "higher"))
    out.loc[valid.index] = 100.0 * (r - 1) / (len(valid) - 1)
    return out


def evidence(sample_n: pd.Series, q_target: Optional[float]) -> pd.Series:
    """کیفیت شواهد ۰..۱ بر پایه اندازه نمونه در برابر هدف.

    مقدار نامعلوم با عدد ساختگی پر نمی‌شود؛ NaN می‌ماند.
    """
    n = pd.to_numeric(sample_n, errors="coerce")
    if not q_target or q_target <= 0:
        return pd.Series(np.nan, index=n.index, dtype=float)
    return (n / float(q_target)).clip(0.0, 1.0)
