# -*- coding: utf-8 -*-
"""ممیزی عدالت — آیا خودِ سیستم ارزیابی به کسی اجحاف می‌کند؟

## سه اجحافی که این ماژول شکار می‌کند

**۱) جریمهٔ بار کاری.** اگر امتیاز با حجم کار همبستگی منفی داشته باشد،
سیستم عملاً پرکارها را جریمه می‌کند. این را با **همبستگی رتبه‌ای** و
سپس با **باقی‌مانده‌گیری** می‌سنجیم: امتیازی که اثر بار از آن برداشته
شده، چقدر با امتیاز خام فرق می‌کند؟ اگر رتبه‌ها زیاد جابه‌جا شوند، یعنی
رتبه‌بندی فعلی بیشتر «چه‌قدر کار برداشته‌ای» را می‌سنجد تا «چه‌قدر خوب
کار کرده‌ای».

**۲) شکاف گروهی.** اگر یک اداره به‌طور سیستماتیک پایین‌تر بیاید، دو
احتمال هست: واقعاً ضعیف‌تر است، یا سنجه به آن نوع کار نمی‌خورد. تفکیک
این دو با داده مشاهده‌ای قطعی نیست، ولی می‌شود **اندازه شکاف را با بازه
اطمینان** گزارش کرد و پرسید آیا پس از کنترل بار و پیچیدگی باقی می‌ماند.

**۳) بی‌ثباتی به‌خاطر نمونه کوچک.** کسی که ۴ پرونده داشته، اگر یکی خطا
داشته باشد ۲۵٪ خطا می‌خورد؛ کسی با ۴۰۰ پرونده هرگز چنین نوسانی ندارد.
شرینکیج این را از قبل درمان می‌کند — اینجا فقط **اعلام** می‌شود که کدام
افراد امتیازشان بر شواهد نازک ایستاده.

## مبنای روش

* شکاف گروهی با نسبت تأثیر (**adverse impact ratio**، قاعده چهارپنجم،
  EEOC 1978) — سنجه‌ای که چهار دهه در ممیزی استخدام به‌کار رفته و
  محاسبه‌اش شفاف است.
* باقی‌مانده‌گیری Frisch–Waugh–Lovell برای جدا کردن اثر بار.
* بازه اطمینان و کف نمونه، همان قواعد ماژول ``analytics.evidence``.

هیچ‌جا ادعا نمی‌شود «تبعیض اثبات شد». ادعا این است: «این شکاف هست، این
اندازه است، و پس از کنترل این متغیرها این‌قدر از آن می‌ماند».
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..analytics.evidence import MIN_N, mean_ci, rank_corr

#: قاعده چهارپنجم: نسبت زیر ۰٫۸ به‌طور سنتی «قابل بررسی» تلقی می‌شود.
FOUR_FIFTHS = 0.80

#: جابه‌جایی رتبه بیش از این نسبت، یعنی رتبه‌بندی به بار حساس است.
RANK_SHIFT_ALERT = 0.15


@dataclass
class LoadPenalty:
    """آیا سیستم، پرکارها را جریمه می‌کند؟"""
    corr: float                  # همبستگی رتبه‌ای امتیاز با بار
    n: int
    mean_rank_shift: float       # میانگین جابه‌جایی رتبه پس از حذف اثر بار
    max_rank_shift: int
    moved: int                   # چند نفر بیش از ۱۰٪ جمعیت جابه‌جا شدند

    @property
    def enough(self) -> bool:
        return self.n >= MIN_N

    @property
    def penalised(self) -> bool:
        """امتیاز با بار **منفی** همبسته است و جابه‌جایی رتبه محسوس است."""
        return (self.enough and np.isfinite(self.corr)
                and self.corr < -0.15 and self.mean_rank_shift > RANK_SHIFT_ALERT)

    @property
    def verdict(self) -> str:
        if not self.enough:
            return "داده کافی نیست"
        if not np.isfinite(self.corr):
            return "قابل سنجش نیست"
        if self.penalised:
            return "امتیاز به زیان پرکارها است"
        if self.corr > 0.15:
            return "امتیاز به سود پرکارها است"
        return "امتیاز نسبت به بار خنثی است"


def load_penalty(df: pd.DataFrame, score_col: str, load_col: str) -> LoadPenalty:
    """اثر بار بر رتبه‌بندی را می‌سنجد و رتبهٔ بدون‌اثرِ بار را مقایسه می‌کند."""
    if score_col not in df.columns or load_col not in df.columns:
        return LoadPenalty(float("nan"), 0, 0.0, 0, 0)
    s = pd.to_numeric(df[score_col], errors="coerce")
    w = pd.to_numeric(df[load_col], errors="coerce")
    ok = s.notna() & w.notna()
    s, w = s[ok], w[ok]
    n = int(len(s))
    if n < MIN_N or s.nunique() < 2 or w.nunique() < 2:
        return LoadPenalty(float("nan"), n, 0.0, 0, 0)

    corr = rank_corr(s, w)
    resid = residual_score(s, w)
    r0 = s.rank(ascending=False, method="average")
    r1 = resid.rank(ascending=False, method="average")
    shift = (r0 - r1).abs()
    return LoadPenalty(corr, n, float(shift.mean() / n), int(shift.max()),
                       int((shift > 0.10 * n).sum()))


def residual_score(score: pd.Series, load: pd.Series) -> pd.Series:
    """امتیازی که اثر خطی بار از آن برداشته شده (باقی‌مانده FWL).

    میانگین امتیاز حفظ می‌شود تا عدد در همان مقیاس قابل خواندن بماند.
    """
    s = pd.to_numeric(score, errors="coerce")
    w = pd.to_numeric(load, errors="coerce")
    ok = s.notna() & w.notna()
    if ok.sum() < 3 or w[ok].nunique() < 2:
        return s
    x = np.column_stack([np.ones(int(ok.sum())), w[ok].to_numpy(float)])
    y = s[ok].to_numpy(float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    out = s.copy()
    out.loc[ok] = y - x @ beta + y.mean()
    return out


@dataclass
class GroupGap:
    """شکاف امتیاز یک گروه نسبت به بقیه."""
    group: str
    n: int
    mean: float
    lo: float
    hi: float
    others_mean: float
    adjusted_mean: Optional[float] = None       # میانگین گروه، پس از حذف اثر بار
    adjusted_others: Optional[float] = None     # میانگین بقیه، با همان تعدیل

    @property
    def enough(self) -> bool:
        return self.n >= MIN_N

    @property
    def gap(self) -> float:
        return self.mean - self.others_mean

    @property
    def ratio(self) -> float:
        """نسبت تأثیر — مبنای قاعده چهارپنجم."""
        return self.mean / self.others_mean if self.others_mean else float("nan")

    @property
    def flagged(self) -> bool:
        """نسبت تأثیر زیر ۰٫۸ — لنز قاعده چهارپنجم."""
        return self.enough and np.isfinite(self.ratio) and self.ratio < FOUR_FIFTHS

    @property
    def distinguishable(self) -> bool:
        """میانگین بقیه بیرون از بازه اطمینان این گروه است.

        این لنز از قاعده چهارپنجم حساس‌تر است: شکاف ۹ واحدی روی پایه ۵۵
        نسبتش ۰٫۸۴ می‌شود و از صافیِ چهارپنجم رد می‌شود، در حالی که
        آماری کاملاً قابل تشخیص است. برای سنجش آدم‌ها، رد شدن از یک
        آستانه قراردادی دلیل نادیده گرفتن نیست.
        """
        if not self.enough or not np.isfinite(self.lo):
            return False
        return not (self.lo <= self.others_mean <= self.hi)

    @property
    def adjusted_gap(self) -> Optional[float]:
        """شکاف پس از تعدیل — **هر دو طرف** تعدیل‌شده.

        مقایسه میانگینِ تعدیل‌شدهٔ گروه با میانگینِ **خام** بقیه غلط است:
        دو عدد از دو مقیاس. هر دو باید از یک باقی‌مانده بیایند.
        """
        if self.adjusted_mean is None or self.adjusted_others is None:
            return None
        return self.adjusted_mean - self.adjusted_others

    @property
    def survives(self) -> Optional[bool]:
        """آیا شکاف پس از حذف اثر بار هم می‌ماند؟"""
        ag = self.adjusted_gap
        if ag is None or not self.enough:
            return None
        return abs(ag) >= abs(self.gap) * 0.5

    @property
    def verdict(self) -> str:
        if not self.enough:
            return "داده کافی نیست"
        if not (self.distinguishable or self.flagged):
            return "شکاف قابل توجهی نیست"
        if self.survives is None:
            return "شکاف هست — کنترل‌نشده"
        return ("شکاف پس از کنترل بار می‌ماند" if self.survives
                else "شکاف عمدتاً از تفاوت بار می‌آید")


def group_gaps(df: pd.DataFrame, score_col: str, group_col: str,
               load_col: Optional[str] = None) -> List[GroupGap]:
    """شکاف هر گروه، خام و پس از حذف اثر بار."""
    if score_col not in df.columns or group_col not in df.columns:
        return []
    s = pd.to_numeric(df[score_col], errors="coerce")
    g = df[group_col].fillna("—").astype(str)
    adj = residual_score(s, df[load_col]) if (load_col and load_col in df.columns) else None

    out: List[GroupGap] = []
    for key in g.dropna().unique():
        sel = g.eq(key)
        inside, outside = s[sel].dropna(), s[~sel].dropna()
        if inside.empty or outside.empty:
            continue
        m, lo, hi = mean_ci(inside)
        out.append(GroupGap(
            group=str(key), n=int(len(inside)), mean=m, lo=lo, hi=hi,
            others_mean=float(outside.mean()),
            adjusted_mean=(float(adj[sel].dropna().mean())
                           if adj is not None and adj[sel].notna().any() else None),
            adjusted_others=(float(adj[~sel].dropna().mean())
                             if adj is not None and adj[~sel].notna().any() else None)))
    out.sort(key=lambda x: x.gap)
    return out


@dataclass
class ThinEvidence:
    """کسانی که امتیازشان بر شواهد نازک ایستاده."""
    n_people: int
    thin: int
    threshold: int
    names: List[str]

    @property
    def share(self) -> float:
        return self.thin / self.n_people if self.n_people else float("nan")


def thin_evidence(df: pd.DataFrame, sample_col: str,
                  name_col: str = "", threshold: int = 10) -> ThinEvidence:
    """چند نفر امتیازشان از نمونه کوچک آمده — و اسمشان چیست.

    این‌ها را حذف نمی‌کنیم؛ اعلام می‌کنیم. حذف کردن، خودش یک اجحاف
    دیگر است: کسی که کم پرونده داشته لزوماً بد کار نکرده.
    """
    if sample_col not in df.columns:
        return ThinEvidence(len(df), 0, threshold, [])
    n = pd.to_numeric(df[sample_col], errors="coerce")
    thin = n.notna() & (n < threshold)
    names: List[str] = []
    if name_col and name_col in df.columns:
        names = [str(x) for x in df.loc[thin, name_col].head(50)]
    return ThinEvidence(int(len(df)), int(thin.sum()), threshold, names)


def audit(df: pd.DataFrame, score_col: str, load_col: str,
          group_cols: Sequence[str] = (), sample_col: str = "",
          name_col: str = "") -> Dict[str, object]:
    """ممیزی کامل عدالت — یک فراخوان، همه بخش‌ها."""
    return {
        "load_penalty": load_penalty(df, score_col, load_col),
        "gaps": {c: group_gaps(df, score_col, c, load_col)
                 for c in group_cols if c in df.columns},
        "thin": thin_evidence(df, sample_col, name_col) if sample_col else None,
    }
