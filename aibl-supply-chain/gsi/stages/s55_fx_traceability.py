# -*- coding: utf-8 -*-
"""مرحله ۵۵ — دفترکل رهگیری مالی/ارزی واردات (FX Traceability Ledger).

این مرحله عمداً «پول پرداخت‌شده» را از روی خرید ارز حدس نمی‌زند. سه شاهد را
جدا نگه می‌دارد: خرید ارز، تأمین وجه بانکی و سوئیفت. همین تفکیک جلوی یکی از
خطرناک‌ترین خطاهای مدیریتی را می‌گیرد: یکی گرفتن «ارز خریداری شد» با
«وجه به ذی‌نفع منتقل شد».

خروجی‌های شیءمحور:
  * ctx.extras['fx_ledger']      یک ردیف برای هر ثبت سفارش (REG)
  * ctx.extras['fx_eventlog']    رویدادهای مالی/ارزی قابل ممیزی
  * ctx.extras['fx_anomalies']   مغایرت‌ها و شکاف‌های داده با شدت و شاهد

از source frameهای اصلی استفاده می‌شود تا مبالغی که روی چند BL تکرار شده‌اند
دوباره جمع نشوند (fan-out safe).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from ..adapters.base import KEY_BL, KEY_REG
from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_CURRENCY, FMT_DECIMAL, GROUP_ANALYTIC,
                   GROUP_DETAIL, PipelineContext, Stage, register)

EPS = 0.01


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> float:
    return float(num_safe(v) or 0.0)


def _date(v: Any):
    return CalendarEngine.parse(v)


def _date_iso(v: Any) -> str:
    d = _date(v)
    return d.isoformat() if d else ""


def _set_text(values: Iterable[Any]) -> str:
    vals = sorted({_s(v) for v in values if _s(v)})
    return " | ".join(vals)


def _first_nonempty(g: pd.DataFrame, col: str) -> str:
    if col not in g.columns:
        return ""
    return next((_s(x) for x in g[col] if _s(x)), "")


def _latest_date(g: pd.DataFrame, col: str) -> str:
    if col not in g.columns:
        return ""
    ds = [d for d in (_date(x) for x in g[col]) if d]
    return max(ds).isoformat() if ds else ""


def _earliest_date(g: pd.DataFrame, col: str) -> str:
    if col not in g.columns:
        return ""
    ds = [d for d in (_date(x) for x in g[col]) if d]
    return min(ds).isoformat() if ds else ""


@register
class FxTraceabilityStage(Stage):
    name = "fx_traceability"
    title = "رهگیری ورود/خروج پول، تخصیص، خرید ارز و رفع تعهد"
    order = 55
    tolerant = True
    requires = ["CANONICAL_REG"]
    provides = [
        "FX_CASE_KEY", "FX_PURCHASED_AMOUNT", "FX_RIAL_OUTFLOW_REPORTED",
        "FX_NTSW_INITIAL", "FX_NTSW_RELEASED", "FX_NTSW_BALANCE",
        "FX_MONEY_STAGE", "FX_CUSTOMS_DOC_OBLIGATION", "FX_DIFFERENTIAL_OBLIGATION",
        "FX_COLLATERAL_STATUS", "FX_ALLOCATION_ROUTE", "FX_TRACE_SCORE",
        "FX_ANOMALY_COUNT", "FX_ANOMALIES", "FX_EVIDENCE_STATUS",
    ]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        ledger = self._build_ledger(df, ctx)
        events = self._build_events(df, ctx, ledger)
        anomalies = self._build_anomalies(df, ledger, ctx)

        ctx.extras["fx_ledger"] = ledger
        ctx.extras["fx_eventlog"] = events
        ctx.extras["fx_anomalies"] = anomalies

        if ledger.empty:
            for c in self.provides:
                df[c] = 0 if c in {"FX_PURCHASED_AMOUNT", "FX_RIAL_OUTFLOW_REPORTED",
                                   "FX_NTSW_INITIAL", "FX_NTSW_RELEASED", "FX_NTSW_BALANCE",
                                   "FX_TRACE_SCORE", "FX_ANOMALY_COUNT"} else ""
            return df

        # نگاشت یک‌به‌چند امن: ledger یک ردیف برای هر REG است.
        map_cols = [c for c in self.provides if c != "FX_CASE_KEY"]
        m = ledger.set_index("KEY_REG")
        regs = df["CANONICAL_REG"].map(_s)
        df["FX_CASE_KEY"] = regs.map(lambda x: f"REG:{x}" if x else "")
        for c in map_cols:
            if c in m.columns:
                df[c] = regs.map(m[c].to_dict())

        num_cols = {"FX_PURCHASED_AMOUNT", "FX_RIAL_OUTFLOW_REPORTED", "FX_NTSW_INITIAL",
                    "FX_NTSW_RELEASED", "FX_NTSW_BALANCE", "FX_TRACE_SCORE", "FX_ANOMALY_COUNT"}
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        for c in set(self.provides) - num_cols:
            if c in df.columns:
                df[c] = df[c].fillna("")

        log.info(f"💱 [fx-trace] {len(ledger)} پرونده ثبت سفارش | "
                 f"{len(events)} رویداد | {len(anomalies)} مغایرت/شکاف")
        return df

    # ═══════════ ledger پرونده ═══════════
    def _build_ledger(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        regs = set(df.get("CANONICAL_REG", pd.Series(dtype=str)).map(_s))
        for source, frame in (("fx_transaction", "main"), ("credit", "main"),
                              ("ntsw", "commitment"), ("ntsw", "allocation")):
            t = ctx.sheet(source, frame)
            if t is not None and KEY_REG in t.columns:
                regs.update(t[KEY_REG].map(_s))
        regs.discard("")
        if not regs:
            return pd.DataFrame()

        fx = ctx.sheet("fx_transaction", "main")
        cr = ctx.sheet("credit", "main")
        cm = ctx.sheet("ntsw", "commitment")
        al = ctx.sheet("ntsw", "allocation")

        def groups(t: Optional[pd.DataFrame]) -> Dict[str, pd.DataFrame]:
            if t is None or t.empty or KEY_REG not in t.columns:
                return {}
            z = t[t[KEY_REG].map(_s) != ""].copy()
            return {str(k): g for k, g in z.groupby(z[KEY_REG].map(_s), sort=False)}

        gfx, gcr, gcm, gal = map(groups, (fx, cr, cm, al))
        gmain = {str(k): g for k, g in df[df["CANONICAL_REG"].map(_s) != ""].groupby(
            df["CANONICAL_REG"].map(_s), sort=False)}

        rows: List[Dict[str, Any]] = []
        for reg in sorted(regs):
            f = gfx.get(reg, pd.DataFrame())
            c = gcr.get(reg, pd.DataFrame())
            n = gcm.get(reg, pd.DataFrame())
            a = gal.get(reg, pd.DataFrame())
            d = gmain.get(reg, pd.DataFrame())

            fx_amount = float(pd.to_numeric(f.get("FX_AMOUNT"), errors="coerce").fillna(0).sum()) if not f.empty else 0.0
            fx_rial = float(pd.to_numeric(f.get("FX_RIAL_VALUE"), errors="coerce").fillna(0).sum()) if not f.empty else 0.0
            fx_eur = float(pd.to_numeric(f.get("FX_EUR_VALUE"), errors="coerce").fillna(0).sum()) if not f.empty else 0.0

            initial = _num(n.iloc[0].get("NTSW_INITIAL_COMMIT")) if not n.empty else 0.0
            balance = _num(n.iloc[0].get("NTSW_BALANCE")) if not n.empty else 0.0
            released = max(0.0, initial - balance)
            alloc_amount = _num(a.iloc[0].get("NTSW_ALLOCATED_AMOUNT")) if not a.empty else 0.0
            open_queue_amount = _num(a.iloc[0].get("NTSW_OPEN_QUEUE_AMOUNT")) if not a.empty else 0.0
            requested_gross = _num(a.iloc[0].get("NTSW_REQUESTED_GROSS")) if not a.empty else 0.0
            allocated = bool(a.iloc[0].get("NTSW_ALLOCATED")) if not a.empty else False
            queue_state = _first_nonempty(a, "NTSW_QUEUE_STATE")
            queue_enter = _first_nonempty(a, "NTSW_QUEUE_ENTER_DATE")
            queue_rank = _first_nonempty(a, "NTSW_QUEUE_RANK")

            full_clear = bool(d.get("IS_FULL_CLEARED", pd.Series(False, index=d.index)).fillna(False).astype(bool).any()) if not d.empty else False
            cotage = _set_text(d.get("COTAGE_NO", pd.Series(dtype=str))) if not d.empty else ""
            sata = _set_text(d.get("SATA_NO", pd.Series(dtype=str))) if not d.empty else ""
            bls = sorted({_s(x) for x in d.get("CANONICAL_BL", pd.Series(dtype=str)) if _s(x)}) if not d.empty else []

            # پس از بخشنامه ۱۴۰۵/۰۳/۰۴ این سه تعهد عمداً مستقل‌اند.
            if full_clear and cotage:
                customs_ob = "سند گمرکی موجود؛ تطبیق بانکی باید تأیید شود"
            elif full_clear:
                customs_ob = "ترخیص ثبت شده؛ کوتاژ/پروانه برای تطبیق ناقص"
            else:
                customs_ob = "تعهد ارائه سند ترخیص باز/نامشخص"
            diff_ob = "داده مستقیم مابه‌التفاوت در سورس‌ها موجود نیست"
            collateral = "داده مستقیم وثیقه/آزادسازی در سورس‌ها موجود نیست"

            fund_date = _latest_date(c, "CRD_FUND_DATE") if not c.empty else ""
            swift_date = _latest_date(c, "CRD_SWIFT_DATE") if not c.empty else ""
            buy_date = _latest_date(f, "FX_BUY_DATE") if not f.empty else ""
            alloc_date = _latest_date(a, "NTSW_ALLOC_DATE") if not a.empty else ""
            if swift_date:
                money_stage = "شاهد سوئیفت موجود"
            elif fund_date:
                money_stage = "تأمین وجه بانکی ثبت شده"
            elif fx_amount > EPS or buy_date:
                money_stage = "خرید ارز ثبت شده"
            elif allocated or alloc_date:
                money_stage = "تخصیص ارز ثبت شده"
            else:
                money_stage = "فاقد شاهد مالی پس از ثبت سفارش"

            route = _first_nonempty(a, "NTSW_REQ_TYPE") or _first_nonempty(a, "NTSW_ALLOC_PROCESS")
            if not route:
                route = "نامشخص/نیازمند فیلد مسیر مستقیم-غیرمستقیم"

            # پوشش شواهد؛ نه امتیاز حقوقی.
            evidence = {
                "ntsw_commitment": bool(not n.empty), "allocation": bool(not a.empty),
                "fx_purchase": bool(not f.empty), "bank_credit": bool(not c.empty),
                "shipment": bool(bls), "customs": bool(cotage or full_clear), "sata": bool(sata),
            }
            score = round(100 * sum(evidence.values()) / len(evidence), 1)
            ev_status = "کامل" if score >= 85 else ("متوسط" if score >= 55 else "ناقص")

            row = {
                "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}",
                "BL_COUNT": len(bls), "BL_LIST": " | ".join(bls),
                "FX_PURCHASED_AMOUNT": round(fx_amount, 2),
                "FX_RIAL_OUTFLOW_REPORTED": round(fx_rial, 2),
                "FX_EUR_EQUIVALENT": round(fx_eur, 2),
                "FX_CURRENCIES": _set_text(f.get("FX_CURRENCY", pd.Series(dtype=str))) if not f.empty else "",
                "FX_FIRST_BUY_DATE": _earliest_date(f, "FX_BUY_DATE") if not f.empty else "",
                "FX_LAST_BUY_DATE": buy_date,
                "FX_BENEFICIARIES": _set_text(f.get("FX_BENEFICIARY", pd.Series(dtype=str))) if not f.empty else "",
                "FX_BANKS": _set_text(f.get("FX_BANK", pd.Series(dtype=str))) if not f.empty else "",
                "FX_EXCHANGES": _set_text(f.get("FX_EXCHANGE", pd.Series(dtype=str))) if not f.empty else "",
                "FX_NTSW_INITIAL": round(initial, 2), "FX_NTSW_RELEASED": round(released, 2),
                "FX_NTSW_BALANCE": round(balance, 2),
                "FX_RELEASE_PCT": round(100 * released / initial, 1) if initial > EPS else 0.0,
                "FX_NTSW_RELEASE_STATUS": _first_nonempty(n, "NTSW_RELEASE_STATUS"),
                "FX_ALLOC_REQUEST_AMOUNT": round(alloc_amount + open_queue_amount, 2),
                "FX_ALLOCATED_AMOUNT": round(alloc_amount, 2),
                "FX_OPEN_QUEUE_AMOUNT": round(open_queue_amount, 2),
                "FX_REQUESTED_GROSS_HISTORY": round(requested_gross, 2),
                "FX_ALLOCATED": allocated, "FX_ALLOC_DATE": alloc_date,
                "FX_ALLOC_QUEUE_STATE": queue_state,
                "FX_ALLOC_QUEUE_ENTER_DATE": queue_enter,
                "FX_ALLOC_QUEUE_RANK": queue_rank,
                "FX_OPEN_ALLOC_REQUESTS": int(_num(a.iloc[0].get("NTSW_OPEN_REQUESTS"))) if not a.empty else 0,
                "FX_ALLOCATED_REQUESTS": int(_num(a.iloc[0].get("NTSW_ALLOCATED_REQUESTS"))) if not a.empty else 0,
                "FX_ALLOC_STATUS": _first_nonempty(a, "NTSW_ALLOC_STATUS"),
                "FX_ALLOCATION_ROUTE": route,
                "FX_SOURCE": _first_nonempty(a, "NTSW_FX_SOURCE"),
                "FX_MONEY_STAGE": money_stage,
                "FX_FUND_DATE": fund_date, "FX_SWIFT_DATE": swift_date,
                "FX_CREDIT_PROFORMA": float(pd.to_numeric(c.get("CRD_PROFORMA_VALUE"), errors="coerce").fillna(0).max()) if not c.empty else 0.0,
                "FX_CREDIT_PREPAYMENT": float(pd.to_numeric(c.get("CRD_PREPAYMENT"), errors="coerce").fillna(0).sum()) if not c.empty else 0.0,
                "FX_CREDIT_REMAINING": float(pd.to_numeric(c.get("CRD_REMAINING"), errors="coerce").fillna(0).max()) if not c.empty else 0.0,
                "FX_FULL_CLEAR": full_clear, "FX_COTAGE": cotage, "FX_SATA": sata,
                "FX_CUSTOMS_DOC_OBLIGATION": customs_ob,
                "FX_DIFFERENTIAL_OBLIGATION": diff_ob,
                "FX_COLLATERAL_STATUS": collateral,
                "FX_TRACE_SCORE": score, "FX_EVIDENCE_STATUS": ev_status,
                "FX_ANOMALY_COUNT": 0, "FX_ANOMALIES": "",
            }
            rows.append(row)
        return pd.DataFrame(rows)

    # ═══════════ رویدادهای مالی/ارزی ═══════════
    def _build_events(self, df: pd.DataFrame, ctx: PipelineContext,
                      ledger: pd.DataFrame) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []

        def add(reg, typ, fa, dt, amount=0.0, currency="", source="", evidence=""):
            d = _date(dt)
            reg = _s(reg)
            if not reg or d is None:
                return
            rows.append({"_CASE_KEY": f"REG:{reg}", "KEY_REG": reg,
                         "EVENT_TYPE": typ, "ACTIVITY_FA": fa,
                         "EVENTTIME": pd.Timestamp(d), "AMOUNT": _num(amount),
                         "CURRENCY": _s(currency), "SOURCE_SYSTEM": source,
                         "EVIDENCE": _s(evidence)})

        cm = ctx.sheet("ntsw", "commitment")
        if cm is not None:
            for r in cm.to_dict("records"):
                add(r.get(KEY_REG), "FX_COMMITMENT_CREATED", "ایجاد تعهد ارزی",
                    r.get("NTSW_COMMIT_DATE"), r.get("NTSW_INITIAL_COMMIT"),
                    r.get("NTSW_CURRENCY"), "NTSW", r.get("NTSW_RELEASE_STATUS"))
        al_rows = ctx.sheet("ntsw", "allocation_rows")
        if al_rows is not None:
            for r in al_rows.to_dict("records"):
                add(r.get(KEY_REG), "ALLOCATION_QUEUE", "ورود درخواست به صف تخصیص",
                    r.get("NTSW_REQ_DATE"), r.get("NTSW_REQ_AMOUNT"),
                    r.get("NTSW_REQ_CURRENCY"), "NTSW",
                    f"request={_s(r.get('NTSW_REQUEST_KEY'))}; state={_s(r.get('NTSW_REQUEST_STATE'))}; rank={_s(r.get('NTSW_QUEUE_RANK'))}")
                if _s(r.get("NTSW_REQUEST_STATE")) == "ALLOCATED":
                    add(r.get(KEY_REG), "ALLOCATION", "تخصیص ارز", r.get("NTSW_ALLOC_DATE"),
                        r.get("NTSW_REQ_AMOUNT"), r.get("NTSW_REQ_CURRENCY"), "NTSW",
                        r.get("NTSW_ALLOC_STATUS"))
        else:
            al = ctx.sheet("ntsw", "allocation")
            if al is not None:
                for r in al.to_dict("records"):
                    add(r.get(KEY_REG), "ALLOCATION", "تخصیص ارز", r.get("NTSW_ALLOC_DATE"),
                        r.get("NTSW_ALLOCATED_AMOUNT", r.get("NTSW_REQ_AMOUNT")),
                        r.get("NTSW_REQ_CURRENCY"), "NTSW", r.get("NTSW_ALLOC_STATUS"))
        fx = ctx.sheet("fx_transaction", "main")
        if fx is not None:
            for r in fx.to_dict("records"):
                add(r.get(KEY_REG), "FX_PURCHASE", "خرید ارز", r.get("FX_BUY_DATE"),
                    r.get("FX_AMOUNT"), r.get("FX_CURRENCY"), "FX_TRANSACTION",
                    r.get("FX_STATUS"))
        cr = ctx.sheet("credit", "main")
        if cr is not None:
            for r in cr.to_dict("records"):
                add(r.get(KEY_REG), "FUNDING", "تأمین وجه بانکی", r.get("CRD_FUND_DATE"),
                    r.get("CRD_RIAL_AMOUNT"), "IRR", "CREDIT", r.get("CRD_LAST_STATUS"))
                add(r.get(KEY_REG), "SWIFT", "دریافت/ثبت سوئیفت", r.get("CRD_SWIFT_DATE"),
                    r.get("CRD_EUR_AMOUNT"), "EUR", "CREDIT", r.get("CRD_LC_NO"))

        # رویدادهای فیزیکی از dataframe نهایی؛ روی REG+BL+نوع رویداد dedupe می‌شوند.
        for r in df.to_dict("records"):
            reg = r.get("CANONICAL_REG")
            bl = r.get("CANONICAL_BL")
            add(reg, "SHIPMENT", "صدور بارنامه", r.get("BL_DATE"),
                r.get("INVOICE_VALUE"), r.get("CURRENCY"), "BL", bl)
            add(reg, "CUSTOMS_DECLARATION", "ثبت کوتاژ", r.get("COT_DATE"),
                r.get("INVOICE_VALUE"), r.get("CURRENCY"), "EPL/CUSTOMS", r.get("COTAGE_NO"))
            add(reg, "SATA", "صدور کد ساتا", r.get("SATA_DATE"),
                r.get("INVOICE_VALUE"), r.get("CURRENCY"), "SATA", r.get("SATA_NO"))
            add(reg, "FULL_CLEAR", "ترخیص کامل", r.get("FULL_CLEAR_DATE"),
                r.get("INVOICE_VALUE"), r.get("CURRENCY"), "EPL/CUSTOMS", r.get("COTAGE_NO"))

        if not rows:
            return pd.DataFrame(columns=["_CASE_KEY", "EVENT_TYPE", "EVENTTIME"])
        ev = pd.DataFrame(rows)
        ev = ev.drop_duplicates(subset=["_CASE_KEY", "EVENT_TYPE", "EVENTTIME", "AMOUNT", "EVIDENCE"])
        return ev.sort_values(["_CASE_KEY", "EVENTTIME", "EVENT_TYPE"], kind="mergesort").reset_index(drop=True)

    # ═══════════ مغایرت‌ها ═══════════
    def _build_anomalies(self, df: pd.DataFrame, ledger: pd.DataFrame,
                         ctx: PipelineContext) -> pd.DataFrame:
        issues: Dict[str, List[Dict[str, str]]] = defaultdict(list)

        def flag(reg: str, code: str, severity: str, desc: str, evidence: str = ""):
            if reg:
                issues[reg].append({"code": code, "severity": severity,
                                    "desc": desc, "evidence": evidence})

        # ردیف‌های فیزیکی: تاریخ آینده و توالی ناممکن گمرکی.
        for r in df.to_dict("records"):
            reg = _s(r.get("CANONICAL_REG"))
            if not reg:
                continue
            for col, label in (("BL_DATE", "بارنامه"), ("ARRIVAL_DATE", "ورود"),
                               ("DISCHARGE_DATE", "تخلیه"), ("COT_DATE", "کوتاژ"),
                               ("FULL_CLEAR_DATE", "ترخیص کامل")):
                d = _date(r.get(col))
                if d and d > ctx.today:
                    flag(reg, "FUTURE_DATE", "HIGH", f"تاریخ {label} بعد از تاریخ مرجع است",
                         f"{col}={d.isoformat()}")
            bl, clear = _date(r.get("BL_DATE")), _date(r.get("FULL_CLEAR_DATE"))
            if bl and clear and clear < bl:
                flag(reg, "CLEAR_BEFORE_SHIPMENT", "CRITICAL",
                     "ترخیص کامل قبل از تاریخ حمل ثبت شده است",
                     f"BL={bl.isoformat()} / CLEAR={clear.isoformat()}")

        # سطح پرونده: نسبت‌های مالی فقط وقتی ارز/مبنای مبلغ قابل مقایسه باشد.
        for i, r in ledger.iterrows():
            reg = _s(r["KEY_REG"])
            initial, bal, purchased = map(_num, (r["FX_NTSW_INITIAL"], r["FX_NTSW_BALANCE"],
                                                 r["FX_PURCHASED_AMOUNT"]))
            if initial > EPS and bal - initial > EPS:
                flag(reg, "BALANCE_GT_INITIAL", "CRITICAL",
                     "مانده تعهد از تعهد اولیه بزرگ‌تر است",
                     f"initial={initial:,.2f}; balance={bal:,.2f}")
            if r.get("FX_NTSW_RELEASE_STATUS") and "رفع" in _s(r.get("FX_NTSW_RELEASE_STATUS")) \
                    and "نشده" not in _s(r.get("FX_NTSW_RELEASE_STATUS")) and bal > EPS:
                flag(reg, "RELEASED_WITH_BALANCE", "HIGH",
                     "وضعیت NTSW رفع‌شده است ولی مانده تعهد مثبت است",
                     f"balance={bal:,.2f}")
            if bool(r.get("FX_FULL_CLEAR")) and bal > EPS:
                flag(reg, "CLEARED_BUT_COMMITMENT_OPEN", "MEDIUM",
                     "کالا ترخیص کامل شده اما مانده تعهد هنوز باز است؛ پس از تفکیک ۱۴۰۵ می‌تواند ناشی از مابه‌التفاوت/تطبیق باشد",
                     f"balance={bal:,.2f}")
            if purchased > EPS and initial > EPS and r.get("FX_CURRENCIES") and purchased > initial * 1.02:
                flag(reg, "FX_PURCHASE_GT_COMMITMENT", "HIGH",
                     "مبلغ خرید ارز بیش از ۱۰۲٪ تعهد اولیه ثبت شده؛ نیازمند تطبیق ارز/اصلاحیه",
                     f"purchase={purchased:,.2f}; initial={initial:,.2f}")
            if _s(r.get("FX_MONEY_STAGE")) == "شاهد سوئیفت موجود" and purchased <= EPS:
                flag(reg, "SWIFT_WITHOUT_FX_PURCHASE", "MEDIUM",
                     "سوئیفت ثبت شده ولی خرید ارز در سورس تراکنش ارزی پیدا نشد",
                     _s(r.get("FX_SWIFT_DATE")))
            if _num(r.get("FX_TRACE_SCORE")) < 55:
                flag(reg, "LOW_EVIDENCE_COVERAGE", "MEDIUM",
                     "پوشش شواهد زنجیره مالی/ارزی کمتر از ۵۵٪ است",
                     f"score={_num(r.get('FX_TRACE_SCORE')):.1f}%")

            lst = issues.get(reg, [])
            ledger.at[i, "FX_ANOMALY_COUNT"] = len(lst)
            ledger.at[i, "FX_ANOMALIES"] = " ؛ ".join(x["desc"] for x in lst)

        rows = []
        for reg, lst in issues.items():
            for x in lst:
                rows.append({"KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}",
                             "کد مغایرت": x["code"], "شدت": x["severity"],
                             "شرح": x["desc"], "شاهد": x["evidence"]})
        return pd.DataFrame(rows)

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("FX_MONEY_STAGE", "مرحله پول/ارز", 24, GROUP_DETAIL, order=70),
            ColumnSpec("FX_PURCHASED_AMOUNT", "خرید ارز ثبت‌شده", 20, GROUP_ANALYTIC,
                       fmt=FMT_CURRENCY, order=89),
            ColumnSpec("FX_RIAL_OUTFLOW_REPORTED", "ارزش ریالی خرید ارز", 20, GROUP_ANALYTIC,
                       fmt=FMT_CURRENCY, order=90),
            ColumnSpec("FX_NTSW_RELEASED", "رفع‌شده در NTSW", 20, GROUP_ANALYTIC,
                       fmt=FMT_CURRENCY, order=91),
            ColumnSpec("FX_NTSW_BALANCE", "مانده NTSW", 20, GROUP_ANALYTIC,
                       fmt=FMT_CURRENCY, order=92),
            ColumnSpec("FX_CUSTOMS_DOC_OBLIGATION", "تعهد سند ترخیص", 36,
                       GROUP_ANALYTIC, wrap=True, order=93),
            ColumnSpec("FX_DIFFERENTIAL_OBLIGATION", "تعهد مابه‌التفاوت", 36,
                       GROUP_ANALYTIC, wrap=True, order=94),
            ColumnSpec("FX_COLLATERAL_STATUS", "وضعیت وثیقه", 34,
                       GROUP_ANALYTIC, wrap=True, order=95),
            ColumnSpec("FX_TRACE_SCORE", "پوشش رهگیری (٪)", 15, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_low_bad", order=96),
            ColumnSpec("FX_ANOMALY_COUNT", "تعداد مغایرت FX", 15, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_high_bad", order=97),
            ColumnSpec("FX_ANOMALIES", "مغایرت‌های مالی/ارزی", 60, GROUP_ANALYTIC,
                       wrap=True, color_rule="flag_nonempty", order=98),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        ledger = ctx.extras.get("fx_ledger")
        anomalies = ctx.extras.get("fx_anomalies")
        if ledger is None or ledger.empty:
            return {}
        return {
            "پرونده‌های ارزی قابل رهگیری": (int(len(ledger)), "سطح دانه‌بندی: کد ثبت سفارش"),
            "مغایرت‌های رهگیری FX": (int(0 if anomalies is None else len(anomalies)),
                                       "توالی تاریخ، مانده، پوشش شواهد و تطبیق بین سامانه‌ای"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"دفترکل رهگیری مالی-ارزی": {
            "دانه‌بندی": "یک پرونده = یک کد ثبت سفارش (REG)",
            "رفع‌شده NTSW": "max(0, تعهد اولیه − مانده تعهد)",
            "پوشش رهگیری": "تعداد لایه‌های دارای شاهد ÷ ۷ × ۱۰۰",
            "اصل کنترل": "خرید ارز ≠ تأمین وجه ≠ سوئیفت؛ هیچ‌کدام از دیگری استنتاج نمی‌شود",
            "تعهد ۱۴۰۵": "سند ترخیص، مابه‌التفاوت و آزادسازی وثیقه سه وضعیت مستقل",
        }}
