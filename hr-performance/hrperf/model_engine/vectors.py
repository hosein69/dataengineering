# -*- coding: utf-8 -*-
"""کلاسترها در فضای برداری — «آیا این شاخص واقعاً در این کلاستر است؟»

## چرا فضای برداری

تا امروز، عضویت هر شاخص در کلاستر یک **تصمیم** بود: کسی نوشته بود
«نرخ رسوب گمرکی» در کلاستر «صیانت» است. تصمیم بدی نبود، ولی هیچ‌وقت با
داده سنجیده نمی‌شد. اگر دو شاخص در یک کلاستر باشند ولی رفتارشان هیچ
شباهتی نداشته باشد، امتیازِ آن کلاستر معنای واحدی ندارد و جمله‌ای که
درباره‌اش می‌گوییم («فلانی در انطباق ضعیف است») بی‌پایه است.

راه‌حل: **هر شاخص یک بردار است** — ستون امتیازهایش روی همه افراد،
استانداردشده. آنگاه:

* شباهت دو شاخص = **همبستگی** بردارهایشان (کسینوس بردارهای استاندارد)
* مرکز هر کلاستر = میانگین بردارهای اعضایش (**centroid**)
* «چقدر این شاخص به کلاستر خودش تعلق دارد» = شباهتش به مرکز خودش در
  برابر نزدیک‌ترین مرکز دیگر

این همان منطق **سیلوئت** (Rousseeuw, 1987) است، با یک تفاوت مهم: ما
کلاسترها را دوباره کشف نمی‌کنیم. کلاستر یک **قرارداد سازمانی** است، نه
یافتهٔ آماری. موتور فقط می‌گوید «داده با این قرارداد نمی‌خواند» و
**دلیلش را می‌گوید**؛ تصمیم با آدم است.

## چرا k-means نداریم

وسوسه‌انگیز است که شاخص‌ها را خودکار خوشه‌بندی کنیم. نکردیم: خوشهٔ
کشف‌شده اسم ندارد، مرجع ندارد، و در جلسهٔ ارزیابی قابل دفاع نیست.
«کلاستر ۳» به کسی نمی‌شود گفت. کلاسترِ نام‌دار و دلیل‌دار، حتی اگر
آماری بهینه نباشد، قابل استفاده است.

## جهت‌دهی

شاخصی که `direction: lower` است (مثل «روزهای رسوب») پیش از برداری شدن
**قرینه** می‌شود، وگرنه همبستگی منفیِ ساختگی با هم‌کلاستری‌هایش
می‌سازد. امتیازهای مدل از قبل جهت‌دار شده‌اند؛ این تابع روی مقدار خام
هم درست کار می‌کند.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config.model import PerformanceModel

#: کمینه تعداد فرد برای اینکه یک بردار قابل اتکا باشد
MIN_N = 8

#: اختلاف شباهتی که «جابه‌جایی» را پیشنهادکردنی می‌کند
MOVE_MARGIN = 0.15

#: بالای این همبستگی، دو شاخص عملاً یک چیز را می‌سنجند
REDUNDANT = 0.90


def vectors(scores: pd.DataFrame, model: Optional[PerformanceModel] = None,
            ) -> pd.DataFrame:
    """ماتریس شاخص × فرد، استاندارد و جهت‌دار — پایهٔ همه محاسبات این ماژول."""
    df = scores.copy()
    if model is not None:
        for k, m in model.metrics.items():
            if k in df.columns and m.direction == "lower":
                df[k] = -pd.to_numeric(df[k], errors="coerce")
    z = df.apply(lambda s: pd.to_numeric(s, errors="coerce"), axis=0)
    keep = [c for c in z.columns if z[c].notna().sum() >= MIN_N
            and float(z[c].std(ddof=0) or 0) > 1e-9]
    z = z[keep]
    return (z - z.mean()) / z.std(ddof=0).replace(0, np.nan)


def similarity(vec: pd.DataFrame) -> pd.DataFrame:
    """همبستگی جفتی شاخص‌ها — با حداقل هم‌پوشانی، نه هر جفتی."""
    cols = list(vec.columns)
    out = pd.DataFrame(np.nan, index=cols, columns=cols, dtype=float)
    for i, a in enumerate(cols):
        out.loc[a, a] = 1.0
        for b in cols[i + 1:]:
            pair = vec[[a, b]].dropna()
            if len(pair) < MIN_N:
                continue
            sa, sb = pair[a], pair[b]
            if float(sa.std(ddof=0) or 0) < 1e-9 or float(sb.std(ddof=0) or 0) < 1e-9:
                continue
            r = float(np.corrcoef(sa, sb)[0, 1])
            out.loc[a, b] = out.loc[b, a] = r
    return out


def centroids(vec: pd.DataFrame, member_of: Dict[str, str]) -> pd.DataFrame:
    """مرکز هر کلاستر = میانگین بردار اعضایش (فرد × کلاستر)."""
    out: Dict[str, pd.Series] = {}
    for ck in sorted(set(member_of.values())):
        cols = [m for m, c in member_of.items() if c == ck and m in vec.columns]
        if cols:
            out[ck] = vec[cols].mean(axis=1)
    return pd.DataFrame(out)


def _corr(a: pd.Series, b: pd.Series) -> float:
    pair = pd.concat([a, b], axis=1).dropna()
    if len(pair) < MIN_N:
        return float("nan")
    x, y = pair.iloc[:, 0], pair.iloc[:, 1]
    if float(x.std(ddof=0) or 0) < 1e-9 or float(y.std(ddof=0) or 0) < 1e-9:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


@dataclass
class Fit:
    """جای یک شاخص در فضای برداری."""
    metric: str
    cluster: str
    own: float                    # شباهت به مرکز کلاستر خودش
    best_other: str = ""
    best_other_sim: float = float("nan")

    @property
    def margin(self) -> float:
        """چقدر به کلاستر خودش نزدیک‌تر است تا به بهترین رقیب."""
        if not np.isfinite(self.own) or not np.isfinite(self.best_other_sim):
            return float("nan")
        return self.own - self.best_other_sim

    @property
    def verdict(self) -> str:
        m = self.margin
        if not np.isfinite(m):
            return "قابل سنجش نیست"
        if m >= MOVE_MARGIN:
            return "در جای خودش"
        if m <= -MOVE_MARGIN:
            return "به کلاستر دیگری نزدیک‌تر است"
        return "مرزی"


def fit_table(vec: pd.DataFrame, member_of: Dict[str, str]) -> List[Fit]:
    """برای هر شاخص: به مرکز کدام کلاستر نزدیک‌تر است؟

    مرکز کلاستر خودی **بدون خود شاخص** حساب می‌شود؛ وگرنه هر شاخص با
    مرکزی مقایسه می‌شود که خودش جزئی از آن است و همیشه برنده می‌شود.
    """
    out: List[Fit] = []
    cents = centroids(vec, member_of)
    for m in vec.columns:
        ck = member_of.get(m, "")
        peers = [x for x, c in member_of.items()
                 if c == ck and x != m and x in vec.columns]
        own = _corr(vec[m], vec[peers].mean(axis=1)) if peers else float("nan")
        others = [(c, _corr(vec[m], cents[c])) for c in cents.columns if c != ck]
        others = [(c, r) for c, r in others if np.isfinite(r)]
        best = max(others, key=lambda t: t[1]) if others else ("", float("nan"))
        out.append(Fit(m, ck, own, best[0], best[1]))
    out.sort(key=lambda f: (np.inf if not np.isfinite(f.margin) else f.margin))
    return out


@dataclass
class Cohesion:
    """آیا اعضای این کلاستر واقعاً با هم حرکت می‌کنند؟"""
    cluster: str
    n: int
    mean_within: float            # میانگین همبستگی درون‌کلاستری
    mean_between: float           # میانگین همبستگی با شاخص‌های بیرون

    @property
    def separation(self) -> float:
        return self.mean_within - self.mean_between

    @property
    def verdict(self) -> str:
        if self.n < 2:
            return "تک‌عضوی — انسجام معنا ندارد"
        if not np.isfinite(self.mean_within):
            return "قابل سنجش نیست"
        if self.mean_within < 0.15:
            return "اعضا با هم حرکت نمی‌کنند"
        if self.separation < 0.05:
            return "از کلاسترهای دیگر جدا نیست"
        return "منسجم"


def cohesion(sim: pd.DataFrame, member_of: Dict[str, str]) -> List[Cohesion]:
    out: List[Cohesion] = []
    for ck in sorted(set(member_of.values())):
        inside = [m for m, c in member_of.items() if c == ck and m in sim.columns]
        outside = [m for m in sim.columns if member_of.get(m) != ck]
        if not inside:
            continue
        w = [sim.loc[a, b] for i, a in enumerate(inside) for b in inside[i + 1:]]
        b_ = [sim.loc[a, x] for a in inside for x in outside]
        out.append(Cohesion(
            ck, len(inside),
            float(np.nanmean(w)) if w else float("nan"),
            float(np.nanmean(b_)) if b_ else float("nan")))
    return out


@dataclass
class Suggestion:
    """یک پیشنهاد، همراه با دلیلی که بتوان بلند خواند."""
    kind: str                     # move | split | redundant | reweight
    metric: str
    detail: str
    reason: str
    to_cluster: str = ""
    new_weight: Optional[float] = None
    strength: float = 0.0         # هرچه بزرگ‌تر، شواهد قوی‌تر

    @property
    def title(self) -> str:
        return {"move": "جابه‌جایی", "split": "تفکیک",
                "redundant": "هم‌پوشانی", "reweight": "تغییر وزن"}.get(
                    self.kind, self.kind)


def suggest(scores: pd.DataFrame, model: PerformanceModel,
            max_items: int = 12) -> List[Suggestion]:
    """پیشنهادهای موتور — هرکدام با دلیل، و هیچ‌کدام خودکار اعمال نمی‌شود.

    چهار نوع پیشنهاد:

    * **جابه‌جایی** — شاخص به مرکز کلاستر دیگری نزدیک‌تر است.
    * **هم‌پوشانی** — دو شاخص عملاً یک چیز را می‌سنجند و وزنشان دو بار
      شمرده می‌شود.
    * **تفکیک** — اعضای یک کلاستر با هم حرکت نمی‌کنند؛ احتمالاً دو
      مفهوم در یک نام جمع شده‌اند.
    * **تغییر وزن** — شاخصی که تقریباً برای همه یکسان است، تفکیک ایجاد
      نمی‌کند و وزنش عملاً هدر می‌رود.
    """
    member = {k: m.cluster for k, m in model.metrics.items() if m.scored}
    vec = vectors(scores[[c for c in scores.columns if c in member]], model)
    if vec.empty or vec.shape[1] < 2:
        return []
    sim = similarity(vec)
    out: List[Suggestion] = []

    for f in fit_table(vec, member):
        if f.verdict == "به کلاستر دیگری نزدیک‌تر است" and f.best_other:
            out.append(Suggestion(
                "move", f.metric,
                f"از «{_label(model, f.cluster)}» به «{_label(model, f.best_other)}»",
                f"همبستگی این شاخص با بقیهٔ اعضای کلاستر فعلی "
                f"{f.own:+.2f} است ولی با مرکز «{_label(model, f.best_other)}» "
                f"{f.best_other_sim:+.2f}. یعنی داده می‌گوید این شاخص همان "
                f"چیزی را می‌سنجد که آن کلاستر می‌سنجد.",
                to_cluster=f.best_other, strength=abs(f.margin)))

    seen: set = set()
    for a in sim.columns:
        for b in sim.columns:
            if a >= b or (a, b) in seen:
                continue
            r = sim.loc[a, b]
            if np.isfinite(r) and r >= REDUNDANT:
                seen.add((a, b))
                same = member.get(a) == member.get(b)
                out.append(Suggestion(
                    "redundant", a,
                    f"با «{_mlabel(model, b)}» هم‌پوشانی دارد (r={r:.2f})",
                    ("هر دو در یک کلاسترند و وزنشان روی هم جمع می‌شود؛ "
                     "عملاً یک چیز دو بار شمرده می‌شود."
                     if same else
                     "در دو کلاستر متفاوت‌اند ولی یک چیز را می‌سنجند؛ "
                     "امتیاز دو کلاستر مستقل نیست."),
                    strength=float(r)))

    for c in cohesion(sim, member):
        if c.verdict == "اعضا با هم حرکت نمی‌کنند":
            out.append(Suggestion(
                "split", "", f"کلاستر «{_label(model, c.cluster)}»",
                f"میانگین همبستگی درونی {c.mean_within:+.2f} است — اعضا با هم "
                f"حرکت نمی‌کنند. امتیاز این کلاستر یک عدد است ولی یک معنا "
                f"ندارد؛ احتمالاً دو مفهوم در یک نام جمع شده‌اند.",
                strength=abs(c.mean_within - 0.15)))

    spread = vec.std(ddof=0)
    raw_spread = scores[[c for c in vec.columns]].std(ddof=0)
    for m in vec.columns:
        s = float(raw_spread.get(m, np.nan))
        if np.isfinite(s) and s < 3.0:       # امتیاز ۰..۱۰۰، پراکندگی زیر ۳
            w = model.effective_weight(m)
            out.append(Suggestion(
                "reweight", m, f"وزن مؤثر {w:.1%} → پیشنهاد کاهش",
                f"انحراف معیار این شاخص روی کل افراد فقط {s:.1f} واحد است؛ "
                f"تقریباً همه یک عدد می‌گیرند. وزنی که تفکیک ایجاد نمی‌کند، "
                f"سهم بقیهٔ شاخص‌ها را بی‌دلیل کم می‌کند.",
                new_weight=0.0, strength=float(3.0 - s)))

    out.sort(key=lambda s: -s.strength)
    return out[:max_items]


def _label(model: PerformanceModel, key: str) -> str:
    c = model.clusters.get(key)
    return c.label if c else key


def _mlabel(model: PerformanceModel, key: str) -> str:
    m = model.metrics.get(key)
    return m.label if m else key


def layout(sim: pd.DataFrame, member_of: Dict[str, str],
           iterations: int = 220, seed: int = 7) -> pd.DataFrame:
    """مختصات دوبعدی شاخص‌ها برای نقشهٔ کلاستر — MDS ساده با گرادیان.

    فاصلهٔ هدف = ۱ − همبستگی. یعنی دو شاخصی که با هم حرکت می‌کنند، روی
    نقشه کنار هم می‌نشینند. بدون scikit-learn: همان چیزی که برای دیدن
    ساختار لازم است، نه بیشتر.
    """
    cols = list(sim.columns)
    n = len(cols)
    if n < 2:
        return pd.DataFrame(columns=["x", "y", "cluster"])
    rng = np.random.default_rng(seed)
    pos = rng.normal(0, 1, (n, 2))
    d = np.nan_to_num(1.0 - sim.to_numpy(dtype=float), nan=1.0)
    np.fill_diagonal(d, 0.0)
    for step in range(iterations):
        lr = 0.12 * (1 - step / iterations) + 0.01
        diff = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((diff ** 2).sum(-1)) + 1e-9
        grad = ((dist - d) / dist)[:, :, None] * diff
        np.fill_diagonal(dist, 1.0)
        pos -= lr * grad.sum(axis=1) / max(n - 1, 1)
    pos -= pos.mean(axis=0)
    scale = np.abs(pos).max() or 1.0
    pos /= scale
    return pd.DataFrame({"x": pos[:, 0], "y": pos[:, 1],
                         "cluster": [member_of.get(c, "") for c in cols]},
                        index=cols)
