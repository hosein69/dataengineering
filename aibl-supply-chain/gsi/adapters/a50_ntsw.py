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

__contract__ = 2

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
        "FX_RATE_NUMERIC":["نرخ ارز"],
        "REQ_TYPE":       ["نوع درخواست"],
        "ALLOC_BRANCH":   ["شعبه"],
        "APPROVE_DATE":   ["تاریخ تایید"],
        "QUEUE_RANK":     ["رتبه در صف", "اولویت صف", "ردیف صف", "Queue Rank", "Queue Position"],
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
            a[p("FX_RATE_NUMERIC")] = a[p("FX_RATE_NUMERIC")].map(num_safe)
            a[p("REQ_CURRENCY")] = a[p("REQ_CURRENCY")].map(rb.normalize_currency)
            # V26.20: درخواست تخصیص موجودیت مستقل است. تاریخچه خام به ledger
            # request-level تبدیل می‌شود تا retry/تغییر وضعیت یک درخواست، مبلغ
            # نیاز را چندبار نشمارد. aggregation فقط خلاصه پرونده است.
            request_ledger = self._allocation_request_ledger(a)
            out["allocation_rows"] = request_ledger.copy()
            out["allocation"] = self._agg_allocation(request_ledger)
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

    # ═══ تخصیص V26.20: ledger درخواست‌ها، نه جمع تاریخچه ═══
    def _allocation_request_ledger(self, a: pd.DataFrame) -> pd.DataFrame:
        """هر «درخواست تخصیص» را یک بار نگه می‌دارد و آخرین وضعیتش را ثبت می‌کند.

        فایل NTSW ممکن است یک درخواست را در چند snapshot/status تکرار کند. جمع
        ساده همه ردیف‌ها، مبلغ درخواست را متورم می‌کند. کلید اصلی ``REQ_ROW``
        است؛ اگر export آن را نداشته باشد، کلید ترکیبی محافظه‌کارانه می‌سازیم.
        """
        p = self.p
        a = a[a[KEY_REG].astype(str).str.strip() != ""].copy()
        if a.empty:
            return a

        a["_ord"] = [f"{_sort_key(r)}|{_sort_key(v)}|{_sort_key(d)}"
                     for r, v, d in zip(a[p("REQ_DATE")], a[p("APPROVE_DATE")],
                                        a[p("ALLOC_DATE")])]

        def request_key(row: pd.Series) -> str:
            rr = clean_key(row.get(p("REQ_ROW"), ""))
            if rr:
                return f"{clean_key(row.get(KEY_REG,''))}|ROW:{rr}"
            # fallback: شناسه مصنوعی فقط برای dedupe یک export، نه شناسه حقوقی
            return "|".join([
                clean_key(row.get(KEY_REG, "")),
                _sort_key(row.get(p("REQ_DATE"), "")),
                str(row.get(p("REQ_AMOUNT"), "") or ""),
                clean_key(row.get(p("REQ_CURRENCY"), "")),
                normalize_persian_text(row.get(p("REQ_TYPE"), "")),
            ])

        a[p("REQUEST_KEY")] = a.apply(request_key, axis=1)
        # آخرین snapshot هر request برنده است؛ مبلغ فقط همان یک بار وارد ledger می‌شود.
        a = (a.sort_values("_ord")
              .drop_duplicates(subset=[p("REQUEST_KEY")], keep="last")
              .copy())

        def state(row: pd.Series) -> str:
            status = normalize_persian_text(row.get(p("ALLOC_STATUS"), ""))
            proc = normalize_persian_text(row.get(p("ALLOC_PROCESS"), ""))
            alloc_date = CalendarEngine.parse(row.get(p("ALLOC_DATE"), ""))
            text = f"{status} {proc}"
            if alloc_date or any(k in text for k in _ALLOCATED_STATES):
                return "ALLOCATED"
            if any(k in text for k in _REJECTED_STATES):
                return "REJECTED"
            return "OPEN"

        a[p("REQUEST_STATE")] = a.apply(state, axis=1)
        a[p("QUEUE_ENTER_DATE")] = a[p("REQ_DATE")].where(
            a[p("REQUEST_STATE")].eq("OPEN"), "")
        # ``QUEUE_RANK`` ممکن است در export رسمی موجود نباشد. خالی باید خالی بماند.
        a[p("QUEUE_RANK")] = a[p("QUEUE_RANK")].where(
            a[p("REQUEST_STATE")].eq("OPEN"), "")
        return a.drop(columns=["_ord"], errors="ignore")

    def _agg_allocation(self, a: pd.DataFrame) -> pd.DataFrame:
        """خلاصه پرونده از request ledger، با تفکیک open/allocated/rejected."""
        p = self.p
        a = a[a[KEY_REG].astype(str).str.strip() != ""].copy()
        if a.empty:
            return a

        # برای تعیین «آخرین وضعیت نمایشی» دوباره ترتیب زمانی می‌سازیم.
        a["_ord"] = [f"{_sort_key(r)}|{_sort_key(v)}|{_sort_key(d)}"
                     for r, v, d in zip(a[p("REQ_DATE")], a[p("APPROVE_DATE")],
                                        a[p("ALLOC_DATE")])]
        rows: List[Dict[str, Any]] = []
        for reg, g in a.groupby(KEY_REG, sort=False):
            g = g.sort_values("_ord")
            last = g.iloc[-1]
            allocated = g[g[p("REQUEST_STATE")].eq("ALLOCATED")]
            open_q = g[g[p("REQUEST_STATE")].eq("OPEN")]
            rejected = g[g[p("REQUEST_STATE")].eq("REJECTED")]
            alloc_dates = [d for d in (CalendarEngine.parse(x) for x in allocated[p("ALLOC_DATE")]) if d]
            open_dates = [d for d in (CalendarEngine.parse(x) for x in open_q[p("REQ_DATE")]) if d]

            def amount(frame: pd.DataFrame) -> float:
                if frame.empty:
                    return 0.0
                return float(pd.to_numeric(frame[p("REQ_AMOUNT")], errors="coerce").fillna(0).sum())

            alloc_amt = amount(allocated)
            open_amt = amount(open_q)
            rejected_amt = amount(rejected)
            gross_amt = amount(g)

            if len(open_q) and len(allocated):
                qstate = "PARTIAL_ALLOCATED"
            elif len(open_q):
                qstate = "IN_QUEUE"
            elif len(allocated):
                qstate = "ALLOCATED"
            elif len(rejected):
                qstate = "REJECTED"
            else:
                qstate = "NO_REQUEST"

            # آخرین رتبه معتبر میان درخواست‌های باز؛ هرگز 0 جعل نمی‌شود.
            ranks = [x for x in open_q[p("QUEUE_RANK")].tolist()
                     if not is_empty_val(x, treat_zero_as_empty=False)]
            queue_rank = ranks[-1] if ranks else ""

            rows.append({
                KEY_REG: reg,
                p("ALLOC_REQUESTS"): int(len(g)),
                p("ALLOCATED_REQUESTS"): int(len(allocated)),
                p("OPEN_REQUESTS"): int(len(open_q)),
                p("REJECTED_REQUESTS"): int(len(rejected)),
                p("QUEUE_STATE"): qstate,
                p("ALLOC_STATUS"): last[p("ALLOC_STATUS")],
                p("ALLOC_PROCESS"): last[p("ALLOC_PROCESS")],
                p("ALLOC_DATE"): max(alloc_dates).isoformat() if alloc_dates else "",
                p("QUEUE_ENTER_DATE"): min(open_dates).isoformat() if open_dates else "",
                p("QUEUE_RANK"): queue_rank,
                p("REQ_DATE"): last[p("REQ_DATE")],
                p("APPROVE_DATE"): last[p("APPROVE_DATE")],
                # gross صرفاً تاریخچه درخواست است؛ برای نیاز/تخصیص واقعی استفاده نشود.
                p("REQUESTED_GROSS"): gross_amt,
                p("ALLOCATED_AMOUNT"): alloc_amt,
                p("OPEN_QUEUE_AMOUNT"): open_amt,
                p("REJECTED_AMOUNT"): rejected_amt,
                # سازگاری عقب‌رو: REQ_AMOUNT = مبلغ باز + تخصیص‌یافته، نه retry history
                p("REQ_AMOUNT"): alloc_amt + open_amt,
                p("REQ_CURRENCY"): last[p("REQ_CURRENCY")],
                p("FX_SOURCE"): last[p("FX_SOURCE")],
                p("FX_RATE_TYPE"): last[p("FX_RATE_TYPE")],
                p("FX_RATE_NUMERIC"): (float(last[p("FX_RATE_NUMERIC")])
                                        if not is_empty_val(last[p("FX_RATE_NUMERIC")],
                                                            treat_zero_as_empty=False) else None),
                p("REQ_TYPE"): last[p("REQ_TYPE")],
                p("ALLOC_BRANCH"): last[p("ALLOC_BRANCH")],
                p("ALLOCATED"): bool(len(allocated)),
                p("ALLOC_REJECTED"): bool(len(rejected) and not len(allocated) and not len(open_q)),
            })
        return pd.DataFrame(rows)

