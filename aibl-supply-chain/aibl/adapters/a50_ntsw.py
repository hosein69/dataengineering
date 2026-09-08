# -*- coding: utf-8 -*-
"""NTSW — تعهدات ارزی و تخصیص ارز.

هدرهای واقعی
────────────
Release Commitment (۱۱ ستون):
    ردیف | کد ثبت سفارش | شماره ردیف تعهد | شعبه | ارز | تعهد اولیه |
    مانده تعهد | تاریخ ایجاد تعهد | مهلت رفع تعهد | وضعیت رفع تعهد | شرکت

Allocation (۱۵ ستون):
    ردیف | کد ثبت سفارش | ردیف درخواست | وضعیت | فرآیند فعلی | مبلغ درخواست |
    ارز درخواست | تاریخ ایجاد درخواست | تاریخ تخصیص | محل تامین ارز |
    نرخ ارز | نوع درخواست | شعبه | تاریخ تایید | شرکت

⚠️ دو اصلاح بیزینسی حیاتی
─────────────────────────
۱ **تعهدها باید جمع شوند.** یک «کد ثبت سفارش» چند «شماره ردیف تعهد» دارد.
  نسخه قبل با drop_duplicates فقط یک ردیف را نگه می‌داشت و بقیه مانده تعهد
  را دور می‌ریخت. حالا: جمع تعهد اولیه و مانده، زودترین مهلت، و «رفع نشده»
  اگر حتی یک ردیف باز باشد.

۲ **از تخصیص باید آخرین وضعیت گرفته شود.** یک کد ثبت سفارش چند درخواست
  تخصیص دارد (نمونه واقعی: 97687754 دو بار). ملاک، آخرین درخواست بر اساس
  «تاریخ ایجاد درخواست» و سپس «تاریخ تایید» است، نه ردیف اول فایل.
"""
from __future__ import annotations

__contract__ = 1

from typing import Any, Dict, List

import pandas as pd

from ..core.jalali import CalendarEngine
from ..core.text import clean_key, is_empty_val, normalize_persian_text, num_safe
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_REG, SourceAdapter, register

#: وضعیت‌هایی که یعنی تخصیص واقعاً انجام شده
_ALLOCATED_STATES = ("تخصیص یافته", "پذیرفته شده", "تایید", "تأیید", "اتمام")
_REJECTED_STATES = ("پذیرفته نشده", "رد شده", "ابطال")
_UNRESOLVED = ("رفع تعهد نشده", "رفع نشده", "باز")


def _sort_key(v) -> str:
    """تاریخ شمسی به‌صورت رشته‌ای مرتب‌شدنی (1405/06/10 → 14050610)."""
    d = CalendarEngine.parse(v)
    return d.isoformat() if d else ""


@register
class NtswAdapter(SourceAdapter):
    key, prefix = "ntsw", "NTSW"

    COMMITMENT_MAP = {
        "COMMIT_ROW":     ["شماره ردیف تعهد"],
        "BRANCH":         ["شعبه"],
        "CURRENCY":       ["ارز"],
        "INITIAL_COMMIT": ["تعهد اولیه"],
        "BALANCE":        ["مانده تعهد"],
        "COMMIT_DATE":    ["تاریخ ایجاد تعهد"],
        "DEADLINE":       ["مهلت رفع تعهد"],
        "RELEASE_STATUS": ["وضعیت رفع تعهد"],
        "COMPANY":        ["شرکت"],
    }

    ALLOCATION_MAP = {
        "REQ_ROW":        ["ردیف درخواست"],
        "ALLOC_STATUS":   ["وضعیت"],
        "ALLOC_PROCESS":  ["فرآیند فعلی"],
        "REQ_AMOUNT":     ["مبلغ درخواست"],
        "REQ_CURRENCY":   ["ارز درخواست"],
        "REQ_DATE":       ["تاریخ ایجاد درخواست"],
        "ALLOC_DATE":     ["تاریخ تخصیص"],
        "FX_SOURCE":      ["محل تامین ارز"],
        "FX_RATE_TYPE":   ["نرخ ارز"],
        "REQ_TYPE":       ["نوع درخواست"],
        "ALLOC_BRANCH":   ["شعبه"],
        "APPROVE_DATE":   ["تاریخ تایید"],
        "COMPANY":        ["شرکت"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        rb = get_rulebook()
        p = self.p

        df_c = sheets.get("Release Commitment")
        if df_c is not None and not df_c.empty:
            c = self.std(df_c, self.COMMITMENT_MAP, exclude=["توضیح"])
            c[KEY_REG] = self._reg(df_c)
            c[p("CURRENCY")] = c[p("CURRENCY")].map(rb.normalize_currency)
            for f in ("INITIAL_COMMIT", "BALANCE"):
                c[p(f)] = c[p(f)].map(num_safe)
            out["commitment"] = self._agg_commitment(c)
            log.info(f"   ✅ [ntsw] Release Commitment: {len(c)} ردیف تعهد → "
                     f"{len(out['commitment'])} کد ثبت سفارش")
        else:
            log.warning("   ⚠️ [ntsw] شیت «Release Commitment» یافت نشد.")

        df_a = sheets.get("Allocation")
        if df_a is not None and not df_a.empty:
            a = self.std(df_a, self.ALLOCATION_MAP, exclude=["توضیح"])
            a[KEY_REG] = self._reg(df_a)
            a[p("REQ_AMOUNT")] = a[p("REQ_AMOUNT")].map(num_safe)
            a[p("REQ_CURRENCY")] = a[p("REQ_CURRENCY")].map(rb.normalize_currency)
            out["allocation"] = self._agg_allocation(a)
            log.info(f"   ✅ [ntsw] Allocation: {len(a)} درخواست → "
                     f"{len(out['allocation'])} کد ثبت سفارش")
        else:
            log.warning("   ⚠️ [ntsw] شیت «Allocation» یافت نشد.")
        return out

    @staticmethod
    def _reg(df: pd.DataFrame) -> pd.Series:
        from ..core.columns import find_col
        col = find_col(df, ["کد ثبت سفارش", "شماره ثبت سفارش", "ثبت سفارش"],
                       exclude=["تاریخ", "پرونده"])
        return df[col].map(clean_key) if col is not None else ""

    # ═══ تجمیع تعهدها: جمع، نه انتخاب یک ردیف ═══
    def _agg_commitment(self, c: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        c = c[c[KEY_REG].astype(str).str.strip() != ""]
        if c.empty:
            return c
        rows: List[Dict[str, Any]] = []
        for reg, g in c.groupby(KEY_REG, sort=False):
            statuses = [normalize_persian_text(s) for s in g[p("RELEASE_STATUS")]]
            unresolved = [s for s in statuses if any(u in s for u in _UNRESOLVED)]
            deadlines = [d for d in (CalendarEngine.parse(x) for x in g[p("DEADLINE")]) if d]
            created = [d for d in (CalendarEngine.parse(x) for x in g[p("COMMIT_DATE")]) if d]
            rows.append({
                KEY_REG: reg,
                p("COMMIT_ROWS"): int(len(g)),
                p("INITIAL_COMMIT"): float(g[p("INITIAL_COMMIT")].sum()),
                p("BALANCE"): float(g[p("BALANCE")].sum()),
                p("OPEN_ROWS"): int(len(unresolved)),
                p("RELEASE_STATUS"): ("رفع تعهد نشده" if unresolved else
                                      (statuses[0] if statuses else "")),
                p("DEADLINE"): min(deadlines).isoformat() if deadlines else "",
                p("COMMIT_DATE"): min(created).isoformat() if created else "",
                p("LAST_COMMIT_DATE"): max(created).isoformat() if created else "",
                p("CURRENCY"): next((x for x in g[p("CURRENCY")] if not is_empty_val(x)), ""),
                p("BRANCH"): next((x for x in g[p("BRANCH")] if not is_empty_val(x)), ""),
                p("COMPANY"): next((x for x in g[p("COMPANY")] if not is_empty_val(x)), ""),
            })
        return pd.DataFrame(rows)

    # ═══ تخصیص: آخرین وضعیت، نه اولین ردیف ═══
    def _agg_allocation(self, a: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        a = a[a[KEY_REG].astype(str).str.strip() != ""]
        if a.empty:
            return a
        a = a.copy()
        a["_ord"] = [f"{_sort_key(r)}|{_sort_key(v)}"
                     for r, v in zip(a[p("REQ_DATE")], a[p("APPROVE_DATE")])]

        rows: List[Dict[str, Any]] = []
        for reg, g in a.groupby(KEY_REG, sort=False):
            g = g.sort_values("_ord")
            last = g.iloc[-1]                       # ← آخرین درخواست
            states = [normalize_persian_text(s) for s in g[p("ALLOC_STATUS")]]
            procs = [normalize_persian_text(s) for s in g[p("ALLOC_PROCESS")]]
            alloc_dates = [d for d in (CalendarEngine.parse(x) for x in g[p("ALLOC_DATE")]) if d]
            any_alloc = bool(alloc_dates) or any(
                any(k in s for k in _ALLOCATED_STATES) for s in states + procs)
            rejected = any(any(k in s for k in _REJECTED_STATES) for s in states)
            rows.append({
                KEY_REG: reg,
                p("ALLOC_REQUESTS"): int(len(g)),
                p("ALLOC_STATUS"): last[p("ALLOC_STATUS")],
                p("ALLOC_PROCESS"): last[p("ALLOC_PROCESS")],
                p("ALLOC_DATE"): max(alloc_dates).isoformat() if alloc_dates else "",
                p("REQ_DATE"): last[p("REQ_DATE")],
                p("APPROVE_DATE"): last[p("APPROVE_DATE")],
                p("REQ_AMOUNT"): float(g[p("REQ_AMOUNT")].sum()),
                p("REQ_CURRENCY"): last[p("REQ_CURRENCY")],
                p("FX_SOURCE"): last[p("FX_SOURCE")],
                p("FX_RATE_TYPE"): last[p("FX_RATE_TYPE")],
                p("REQ_TYPE"): last[p("REQ_TYPE")],
                p("ALLOC_BRANCH"): last[p("ALLOC_BRANCH")],
                p("ALLOCATED"): bool(any_alloc),
                p("ALLOC_REJECTED"): bool(rejected and not any_alloc),
            })
        return pd.DataFrame(rows)
