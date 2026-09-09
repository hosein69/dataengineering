# -*- coding: utf-8 -*-
"""پیامدها و محرک‌هایشان — «چه چیزی با چه چیزی همراه است، و آیا می‌ماند».

هر تحلیل اینجا سه لایه دارد و هر سه در گزارش دیده می‌شوند:

1. **نرخ پایه** — پیامد اصلاً چقدر رخ می‌دهد؟ بدون این، هر عددی بی‌مقیاس است.
2. **مقایسه خام** — نرخ در گروه دارای ویژگی، در برابر بقیه.
3. **مقایسه کنترل‌شده** — همان تفاضل، ولی **درون لایه‌های** یک متغیر
   مخدوش‌کننده. اگر رابطه اینجا آب برود، رابطه خام توضیح ساده‌تری داشته.

هیچ‌جا کلمه «علت» به‌کار نمی‌رود مگر جایی که سه شرط برقرار باشد: داده
کافی، بازه‌های جدا، و پایداری پس از کنترل. در بقیه موارد گزارش می‌گوید
«همراهی»، که همان چیزی است که داده مشاهده‌ای می‌تواند بگوید.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..core.text import num_parse
from .evidence import (MIN_N, Contrast, Rate, contrast, rate_of,
                       stratified_diff, wilson)


@dataclass(frozen=True)
class Outcome:
    """یک پیامد قابل سنجش، با تعریف صریح و قابل بازبینی."""
    key: str
    fa: str
    definition: str                     # تعریف دقیق، همان‌که در گزارش چاپ می‌شود
    build: Callable[[pd.DataFrame], Optional[pd.Series]]


def _band_in(df: pd.DataFrame, codes) -> Optional[pd.Series]:
    col = "کد طبقه بحرانی"
    if col not in df.columns:
        return None
    return df[col].astype(str).isin(codes)


def _num_gt(df: pd.DataFrame, col: str, thr: float) -> Optional[pd.Series]:
    if col not in df.columns:
        return None
    v = df[col].map(num_parse)
    return v.notna() & (v.astype(float) > thr)


#: پیامدهایی که از داده موجود بدون هیچ فرض تازه‌ای ساخته می‌شوند.
OUTCOMES: List[Outcome] = [
    Outcome("critical", "بحرانی شدن قطعه",
            "طبقه بحرانی در «توقف خط» یا «بحرانی» باشد "
            "(مقاومت کمتر از ۱۰ روز یا موجودی صفر).",
            lambda d: _band_in(d, ["STOCKOUT", "CRITICAL"])),
    Outcome("stockout", "توقف خط",
            "طبقه بحرانی «توقف خط» باشد — موجودی قابل احتساب صفر.",
            lambda d: _band_in(d, ["STOCKOUT"])),
    Outcome("overdue", "تعهد ارزی معوق",
            "«روزهای تأخیر» بزرگ‌تر از صفر باشد.",
            lambda d: _num_gt(d, "روزهای تأخیر", 0)),
    Outcome("stuck", "رسوب بیش از ۳۰ روز",
            "«روزهای رسوب» بیش از ۳۰ روز از تاریخ تخلیه.",
            lambda d: _num_gt(d, "روزهای رسوب", 30)),
]

#: ستون‌هایی که به‌عنوان محرک بررسی می‌شوند. فقط ستون‌های **موجود** و
#: کم‌کاردینالیتی؛ چیزی حدس زده یا ساخته نمی‌شود.
CANDIDATE_FACTORS: List[str] = [
    "روش حمل", "ORG_DEPT", "نوع پرونده", "STATUS_WHERE", "WAITING_ON_SCOPE",
    "EXPERT_LOGISTICS", "EXPERT_COMMERCIAL", "PART_OWNER",
    "ORDER_MISSING_COMMERCIAL_EXPERT", "IS_BLOCKED", "TRANSPORT_MODE",
]

#: متغیری که برای کنترل مخدوش‌کنندگی لایه‌بندی می‌شود.
DEFAULT_CONTROL = "ORG_DEPT"

MAX_LEVELS = 12


@dataclass
class Finding:
    factor: str
    factor_fa: str
    level: str
    crude: Contrast
    adjusted: Optional[float] = None
    strata_used: int = 0
    control: str = ""

    @property
    def robust(self) -> bool:
        """رابطه پس از کنترل هم می‌ماند و جهتش عوض نمی‌شود."""
        if self.adjusted is None or not self.crude.significant:
            return False
        if self.crude.diff == 0:
            return False
        same_sign = (self.adjusted > 0) == (self.crude.diff > 0)
        return same_sign and abs(self.adjusted) >= abs(self.crude.diff) * 0.5

    @property
    def verdict(self) -> str:
        if not self.crude.enough:
            return "داده کافی نیست"
        if not self.crude.significant:
            return "تفاوت معنادار نیست"
        if self.adjusted is None:
            return "همراهی — کنترل‌نشده"
        return "همراهی پایدار پس از کنترل" if self.robust else "پس از کنترل کم‌رنگ می‌شود"


@dataclass
class OutcomeReport:
    outcome: Outcome
    base: Rate
    findings: List[Finding] = field(default_factory=list)
    control: str = ""
    skipped: List[str] = field(default_factory=list)


def _levels(s: pd.Series) -> List[str]:
    v = s.fillna("").astype(str).str.strip()
    v = v[v.ne("") & ~v.str.lower().isin(("nan", "none", "false"))]
    counts = v.value_counts()
    return [str(k) for k in counts.index[:MAX_LEVELS] if counts[k] >= MIN_N]


def analyse(df: pd.DataFrame, outcome: Outcome,
            factors: Optional[List[str]] = None,
            control: str = DEFAULT_CONTROL,
            labels: Optional[Dict[str, str]] = None) -> Optional[OutcomeReport]:
    """یک پیامد را در برابر همه محرک‌های نامزد می‌سنجد."""
    y = outcome.build(df)
    if y is None or not len(y):
        return None
    y = y.fillna(False).astype(bool)
    base = wilson(int(y.sum()), int(len(y)))
    if not base.enough:
        return None

    labels = labels or {}
    rep = OutcomeReport(outcome, base, control=control if control in df.columns else "")
    use_control = rep.control and df[rep.control].nunique() > 1

    for col in (factors or CANDIDATE_FACTORS):
        if col not in df.columns or col == rep.control:
            if col in (factors or CANDIDATE_FACTORS) and col not in df.columns:
                rep.skipped.append(col)
            continue
        series = df[col]
        if series.dtype == bool:
            levels = ["بله"]
            masks = {"بله": series.fillna(False).astype(bool)}
        else:
            levels = _levels(series)
            txt = series.fillna("").astype(str).str.strip()
            masks = {lv: txt.eq(lv) for lv in levels}
        for lv in levels:
            m = masks[lv]
            c = contrast(f"{labels.get(col, col)} = {lv}", m, y)
            if not c.enough:
                continue
            adj, used = (None, 0)
            if use_control:
                adj, used, _ = stratified_diff(m, y, df[rep.control])
            rep.findings.append(Finding(col, labels.get(col, col), lv, c,
                                        adj, used, rep.control))
    rep.findings.sort(key=lambda f: (not f.robust, not f.crude.significant,
                                     -abs(f.crude.diff)))
    return rep


def analyse_all(df: pd.DataFrame, labels: Optional[Dict[str, str]] = None,
                control: str = DEFAULT_CONTROL) -> List[OutcomeReport]:
    out = []
    for oc in OUTCOMES:
        rep = analyse(df, oc, control=control, labels=labels)
        if rep is not None:
            out.append(rep)
    return out
