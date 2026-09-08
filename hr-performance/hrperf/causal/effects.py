# -*- coding: utf-8 -*-
"""برآورد اثر تعدیل‌شده — تفاوت «همبستگی» با «اثر».

سه خروجی اصلی:

1. ``effect_table`` — برای هر یال DAG، همبستگی خام کنار اثر تعدیل‌شده.
   جایی که این دو علامت یا اندازه متفاوت دارند، دقیقاً همان‌جاست که
   تصمیم‌گیری بر پایه همبستگی خام غلط می‌شد.
2. ``fair_score`` — امتیاز منصفانه: عملکرد مشاهده‌شده منهای آنچه از
   **شرایط کار** انتظار می‌رفت. تعمیمِ چندمتغیره ایده A/E.
3. ``e_value`` — سنجه حساسیت: یک مخدوش‌کننده اندازه‌گیری‌نشده چقدر باید
   قوی باشد تا این اثر را خنثی کند.

روش تعدیل: باقی‌مانده‌گیری (Frisch–Waugh–Lovell). هر دو متغیر روی
مجموعه تعدیل رگرس می‌شوند و همبستگی **باقی‌مانده‌ها** گرفته می‌شود؛
معادل ضریب جزئی در رگرسیون کامل، ولی پایدارتر و قابل بازرسی.
"""
from __future__ import annotations

__contract__ = 1

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .dag import DAG, NODE_FA

#: ریج کوچک برای پایداری وقتی تعدیل‌گرها هم‌خط‌اند
RIDGE = 1e-6
#: حداقل نمونه برای برآورد قابل گزارش
MIN_N = 8


def _design(df: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    if not cols:
        return np.ones((len(df), 1))
    X = df[list(cols)].astype(float).to_numpy()
    return np.column_stack([np.ones(len(df)), X])


def residualize(df: pd.DataFrame, target: str,
                controls: Sequence[str]) -> pd.Series:
    """باقی‌مانده ``target`` پس از حذف اثر خطی ``controls``."""
    sub = df[[target, *controls]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        return pd.Series(np.nan, index=df.index, dtype=float)
    y = sub[target].to_numpy(dtype=float)
    X = _design(sub, list(controls))
    XtX = X.T @ X + RIDGE * np.eye(X.shape[1])
    beta = np.linalg.solve(XtX, X.T @ y)
    resid = y - X @ beta
    return pd.Series(resid, index=sub.index).reindex(df.index)


def _spearman(a: pd.Series, b: pd.Series) -> float:
    s = pd.concat([a, b], axis=1).dropna()
    if len(s) < 3:
        return math.nan
    r = s.iloc[:, 0].rank().corr(s.iloc[:, 1].rank())
    return float(r) if pd.notna(r) else math.nan


@dataclass(frozen=True)
class Effect:
    treatment: str
    outcome: str
    raw: float
    adjusted: float
    adjust_set: List[str]
    n: int

    @property
    def gap(self) -> float:
        if math.isnan(self.raw) or math.isnan(self.adjusted):
            return math.nan
        return self.raw - self.adjusted

    @property
    def misleading(self) -> bool:
        """آیا همبستگی خام گمراه‌کننده بوده است؟"""
        if math.isnan(self.gap):
            return False
        sign_flip = (self.raw * self.adjusted) < 0
        big_shrink = abs(self.adjusted) < 0.5 * abs(self.raw) and abs(self.raw) >= 0.2
        return bool(sign_flip or big_shrink)


def e_value(effect: float) -> float:
    """E-value برای یک اثر همبستگی‌مانند (VanderWeele & Ding, 2017).

    عدد بزرگ‌تر یعنی نتیجه در برابر مخدوش‌کننده پنهان مقاوم‌تر است.
    """
    r = abs(float(effect))
    if not math.isfinite(r) or r <= 0:
        return 1.0
    r = min(r, 0.999)
    # تبدیل تقریبی همبستگی به نسبت خطر، سپس فرمول E-value
    rr = math.exp(0.91 * 1.81 * r / math.sqrt(max(1e-9, 1 - r * r)))
    rr = max(rr, 1.0)
    return float(rr + math.sqrt(rr * (rr - 1.0)))


def estimate(df: pd.DataFrame, dag: DAG, treatment: str, outcome: str) -> Effect:
    """اثر یک یال، خام و تعدیل‌شده."""
    if treatment not in df.columns or outcome not in df.columns:
        return Effect(treatment, outcome, math.nan, math.nan, [], 0)
    adj = sorted(c for c in dag.backdoor_set(treatment, outcome)
                 if c in df.columns)
    raw = _spearman(df[treatment], df[outcome])
    if adj:
        rt = residualize(df, treatment, adj)
        ro = residualize(df, outcome, adj)
        adjusted = _spearman(rt, ro)
    else:
        adjusted = raw
    n = int(df[[treatment, outcome]].dropna().shape[0])
    return Effect(treatment, outcome, raw, adjusted, adj, n)


def effect_table(df: pd.DataFrame, dag: DAG) -> pd.DataFrame:
    """جدول همه یال‌های DAG با همبستگی خام و اثر تعدیل‌شده."""
    rows = []
    for t, o in dag.edges:
        if t not in df.columns or o not in df.columns:
            continue
        e = estimate(df, dag, t, o)
        if e.n < MIN_N:
            continue
        rows.append({
            "از": NODE_FA.get(t, t), "به": NODE_FA.get(o, o),
            "کلید از": t, "کلید به": o,
            "همبستگی خام": round(e.raw, 3) if pd.notna(e.raw) else None,
            "اثر تعدیل‌شده": round(e.adjusted, 3) if pd.notna(e.adjusted) else None,
            "تفاوت": round(e.gap, 3) if pd.notna(e.gap) else None,
            "تعدیل برای": "، ".join(NODE_FA.get(c, c) for c in e.adjust_set) or "—",
            "E-value": round(e_value(e.adjusted), 2),
            "n": e.n,
            "هشدار": "⚠ همبستگی خام گمراه‌کننده" if e.misleading else "",
        })
    return pd.DataFrame(rows)


def fair_score(df: pd.DataFrame, outcome: str,
               drivers: Sequence[str],
               scale: float = 12.0) -> pd.DataFrame:
    """امتیاز منصفانه = عملکرد واقعی منهای انتظار، با توجه به شرایط کار.

    این تعمیمِ چندمتغیرهٔ A/E است: به‌جای یک baseline تک‌بعدی، انتظار از
    ترکیب همه «شرایط» (حجم، سختی، تخصیص، تجربه) مدل می‌شود.

    خروجی: ``expected`` (انتظار)، ``residual`` (تفاوت) و ``fair`` (امتیاز
    ۰..۱۰۰ حول ۵۰). ``fair = 50`` یعنی دقیقاً مطابق انتظارِ شرایطش.
    """
    have = [c for c in drivers if c in df.columns]
    out = pd.DataFrame(index=df.index)
    y = pd.to_numeric(df.get(outcome), errors="coerce")
    if y is None or y.notna().sum() < 3 or not have:
        out["expected"] = np.nan
        out["residual"] = np.nan
        out["fair"] = y
        return out

    sub = df[[outcome, *have]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        out["expected"] = np.nan
        out["residual"] = np.nan
        out["fair"] = y
        return out

    X = _design(sub, have)
    yy = sub[outcome].to_numpy(dtype=float)
    beta = np.linalg.solve(X.T @ X + RIDGE * np.eye(X.shape[1]), X.T @ yy)
    exp = pd.Series(X @ beta, index=sub.index).reindex(df.index)
    resid = y - exp
    sd = float(resid.std(ddof=0)) or 1.0
    out["expected"] = exp
    out["residual"] = resid
    out["fair"] = (50.0 + scale * (resid / sd)).clip(5, 95)
    return out
