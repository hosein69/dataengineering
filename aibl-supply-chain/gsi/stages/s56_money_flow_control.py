# -*- coding: utf-8 -*-
"""مرحله ۵۶ — Money Flow Control Tower.

V26.18 لایه کنترلی روی FX Traceability است. هدف، پاسخ شفاف به چهار سؤال است:
  1) پول الان در کدام مرحله است؟
  2) با چه ارز/نرخی خریداری و با چه ارز/نرخی به ذی‌نفع پرداخت شده؟
  3) آیا پول/ارز بین REG / Order / BL جابه‌جا شده و برای آن مجوز داریم؟
  4) نزدیک‌ترین مهلت چیست و چند روز تا آن باقی مانده؟

اصل حاکمیتی: هیچ Signal به‌تنهایی «تقلب» نامیده نمی‌شود. خروجی این مرحله
Investigation Signal است و بین مجوزدار، بدون شاهد مجوز و شکاف داده تفکیک می‌کند.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from ..adapters.base import KEY_BL, KEY_ORDER, KEY_REG
from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_CURRENCY, FMT_DECIMAL, GROUP_ANALYTIC,
                   GROUP_DETAIL, PipelineContext, Stage, register)

EPS = 0.01


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> float:
    try:
        return float(num_safe(v) or 0.0)
    except Exception:
        return 0.0


def _date(v: Any):
    return CalendarEngine.parse(v)


def _first(values: Iterable[Any]) -> str:
    return next((_s(v) for v in values if _s(v)), "")


def _dates(values: Iterable[Any]) -> List:
    return [d for d in (_date(v) for v in values) if d]


def _earliest(frame: pd.DataFrame, col: str):
    if frame is None or frame.empty or col not in frame.columns:
        return None
    ds = _dates(frame[col])
    return min(ds) if ds else None


def _latest(frame: pd.DataFrame, col: str):
    if frame is None or frame.empty or col not in frame.columns:
        return None
    ds = _dates(frame[col])
    return max(ds) if ds else None


def _groups(frame: Optional[pd.DataFrame], key: str = KEY_REG) -> Dict[str, pd.DataFrame]:
    if frame is None or frame.empty or key not in frame.columns:
        return {}
    z = frame[frame[key].map(_s) != ""].copy()
    return {str(k): g for k, g in z.groupby(z[key].map(_s), sort=False)}


def _set_join(values: Iterable[Any]) -> str:
    return " | ".join(sorted({_s(v) for v in values if _s(v)}))


def _status_rank(s: str) -> int:
    return {"CRITICAL": 4, "OVERDUE": 4, "HIGH": 3, "EVIDENCE_GAP": 3,
            "WARNING": 2, "CURRENT": 2, "PARTIAL": 2, "PENDING": 1, "DONE": 0}.get(s, 0)


@register
class MoneyFlowControlStage(Stage):
    name = "money_flow_control"
    title = "برج کنترل جریان پول، نرخ، جابه‌جایی و مهلت‌ها"
    order = 56
    tolerant = True
    requires = ["FX_CASE_KEY", "FX_TRACE_SCORE", "FX_ANOMALY_COUNT"]
    provides = [
        "FX_CONTROL_RISK_SCORE", "FX_CONTROL_RISK_BAND",
        "FX_DEADLINE_DATE", "FX_DAYS_REMAINING", "FX_DEADLINE_STATUS",
        "FX_DEADLINE_BASIS", "FX_CURRENT_STAGE", "FX_STAGE_PROGRESS_PCT",
        "FX_REALLOCATION_STATUS", "FX_REALLOCATION_COUNT",
        "FX_UNAUTHORIZED_REALLOCATION_COUNT", "FX_CONVERSION_STATUS",
        "FX_CONVERSION_IMPACT_RIAL", "FX_PURCHASE_WAVG_RATE",
        "FX_SUPPLIER_CURRENCIES",
    ]

    STAGES: Tuple[Tuple[str, str], ...] = (
        ("ORDER_REG", "ثبت سفارش"),
        ("ALLOCATION_QUEUE", "صف تخصیص"),
        ("ALLOCATION", "تخصیص ارز"),
        ("FX_PURCHASE", "خرید ارز"),
        ("FUNDING", "تأمین وجه"),
        ("SWIFT_CONVERSION", "سوئیفت / تبدیل ارز"),
        ("SHIPMENT", "حمل"),
        ("CUSTOMS", "ورود / EPL"),
        ("CLEARANCE", "ترخیص"),
        ("BANK_DOCS", "ارائه/تطبیق سند ترخیص با بانک"),
        ("SETTLEMENT", "رفع تعهد"),
    )

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        ledger = ctx.extras.get("fx_ledger")
        if ledger is None or ledger.empty:
            self._empty_outputs(df)
            return df

        rate_bridge = self._build_rate_bridge(ctx)
        realloc = self._build_reallocations(df, ctx)
        timeline = self._build_timeline(df, ctx, ledger, rate_bridge)
        control = self._build_control(ledger, timeline, rate_bridge, realloc, ctx)

        # ledger اصلی را غنی می‌کنیم تا همه exportهای قدیمی نیز داده جدید را ببینند.
        ledger = ledger.copy()
        for c in control.columns:
            if c == "KEY_REG":
                continue
            ledger[c] = ledger["KEY_REG"].map(control.set_index("KEY_REG")[c].to_dict())
        ctx.extras["fx_ledger"] = ledger
        ctx.extras["fx_rate_bridge"] = rate_bridge
        ctx.extras["fx_reallocations"] = realloc
        ctx.extras["fx_stage_timeline"] = timeline
        ctx.extras["fx_control_summary"] = control

        m = control.set_index("KEY_REG")
        regs = df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s)
        for c in self.provides:
            if c in m.columns:
                df[c] = regs.map(m[c].to_dict())
        numeric = {"FX_CONTROL_RISK_SCORE", "FX_DAYS_REMAINING", "FX_STAGE_PROGRESS_PCT",
                   "FX_REALLOCATION_COUNT", "FX_UNAUTHORIZED_REALLOCATION_COUNT",
                   "FX_CONVERSION_IMPACT_RIAL", "FX_PURCHASE_WAVG_RATE"}
        for c in numeric:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        for c in set(self.provides) - numeric:
            if c in df.columns:
                df[c] = df[c].fillna("")

        log.info(f"💸 [money-control] {len(control)} پرونده | {len(timeline)} مرحله | "
                 f"{len(rate_bridge)} پل نرخ/تبدیل | {len(realloc)} سیگنال جابه‌جایی")
        return df

    def _empty_outputs(self, df: pd.DataFrame) -> None:
        numeric = {"FX_CONTROL_RISK_SCORE", "FX_DAYS_REMAINING", "FX_STAGE_PROGRESS_PCT",
                   "FX_REALLOCATION_COUNT", "FX_UNAUTHORIZED_REALLOCATION_COUNT",
                   "FX_CONVERSION_IMPACT_RIAL", "FX_PURCHASE_WAVG_RATE"}
        for c in self.provides:
            df[c] = 0.0 if c in numeric else ""

    # ───────────────────────── پل نرخ و تبدیل ارز ─────────────────────────
    def _build_rate_bridge(self, ctx: PipelineContext) -> pd.DataFrame:
        fx = ctx.sheet("fx_transaction", "main")
        if fx is None or fx.empty:
            return pd.DataFrame(columns=["KEY_REG", "STATUS", "PURCHASE_CURRENCY",
                                         "PAID_CURRENCY", "IMPACT_RIAL"])
        rows: List[Dict[str, Any]] = []
        for idx, r in fx.reset_index(drop=True).iterrows():
            reg = _s(r.get(KEY_REG))
            if not reg:
                continue
            src_cur = _s(r.get("FX_CURRENCY"))
            src_amt = _num(r.get("FX_AMOUNT"))
            src_rate = _num(r.get("FX_RATE"))
            src_rial = _num(r.get("FX_RIAL_VALUE"))
            eff_buy_rate = (src_rial / src_amt) if src_amt > EPS and src_rial > EPS else src_rate
            paid_cur = _s(r.get("FX_PAID_CURRENCY"))
            paid_amt = _num(r.get("FX_PAID_AMOUNT"))
            paid_rate = _num(r.get("FX_PAID_RATE_RIAL"))
            cross = _num(r.get("FX_CONVERSION_RATE"))
            fee = _num(r.get("FX_CONVERSION_FEE_RIAL"))

            # مغایرت حسابی مبلغ ریالی با مبلغ×نرخ؛ این «زیان اقتصادی» نیست.
            rate_data_gap = 0.0
            if src_amt > EPS and src_rate > EPS and src_rial > EPS:
                rate_data_gap = src_rial - (src_amt * src_rate)

            status = "NO_SUPPLIER_PAYMENT_DATA"
            impact: Optional[float] = None
            basis_rial: Optional[float] = None
            paid_rial: Optional[float] = None
            note = ""
            if paid_cur:
                if paid_cur == src_cur:
                    status = "SAME_CURRENCY"
                    impact = fee
                    note = "ارز خرید و پرداخت یکسان است؛ فقط کارمزد صریح تبدیل/پرداخت لحاظ شده."
                else:
                    required = [paid_amt > EPS, paid_rate > EPS, cross > EPS, eff_buy_rate > EPS]
                    if all(required):
                        # قرارداد داده V26.18: cross rate = واحد ارز مقصد به ازای ۱ واحد ارز مبدأ.
                        src_used = paid_amt / cross
                        basis_rial = src_used * eff_buy_rate
                        paid_rial = paid_amt * paid_rate
                        impact = paid_rial + fee - basis_rial
                        status = "CROSS_CURRENCY_MEASURED"
                        note = "Impact = ریال معادل پرداخت مقصد + کارمزد − بهای ریالی ارز مبدأ مصرف‌شده."
                    else:
                        status = "CROSS_CURRENCY_EVIDENCE_GAP"
                        missing = []
                        if paid_amt <= EPS: missing.append("مبلغ پرداختی")
                        if paid_rate <= EPS: missing.append("نرخ ریالی ارز مقصد")
                        if cross <= EPS: missing.append("Cross Rate")
                        if eff_buy_rate <= EPS: missing.append("نرخ خرید ارز مبدأ")
                        note = "برای محاسبه زیان/صرفه قطعی، شاهد لازم ناقص است: " + "، ".join(missing)
            rows.append({
                "ROW_ID": idx + 1, "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}",
                "PURCHASE_DATE": _s(r.get("FX_BUY_DATE")),
                "PURCHASE_AMOUNT": src_amt, "PURCHASE_CURRENCY": src_cur,
                "PURCHASE_RATE_RIAL": eff_buy_rate, "PURCHASE_RIAL": src_rial,
                "PAID_AMOUNT": paid_amt, "PAID_CURRENCY": paid_cur,
                "PAID_RATE_RIAL": paid_rate, "CONVERSION_RATE_TARGET_PER_SOURCE": cross,
                "CONVERSION_FEE_RIAL": fee, "SOURCE_BASIS_RIAL": basis_rial,
                "PAID_EQUIVALENT_RIAL": paid_rial, "IMPACT_RIAL": impact,
                "RATE_DATA_VARIANCE_RIAL": rate_data_gap, "STATUS": status,
                "NOTE": note,
            })
        return pd.DataFrame(rows)

    # ───────────────────── جابه‌جایی بین پرونده‌ها ──────────────────────
    def _build_reallocations(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        # مرجع مالکیت واقعی Order/BL → REG از جدول canonical.
        order_regs: Dict[str, Set[str]] = defaultdict(set)
        bl_regs: Dict[str, Set[str]] = defaultdict(set)
        for r in df.to_dict("records"):
            reg = _s(r.get("CANONICAL_REG"))
            if not reg:
                continue
            order = _s(r.get("CANONICAL_ORDER"))
            bl = _s(r.get("CANONICAL_BL"))
            if order: order_regs[order].add(reg)
            if bl: bl_regs[bl].add(reg)

        fx = ctx.sheet("fx_transaction", "main")
        if fx is None or fx.empty:
            return pd.DataFrame(columns=["FROM_REG", "TO_REG", "STATUS", "SIGNAL_TYPE"])

        rows: List[Dict[str, Any]] = []
        seen = set()

        def emit(from_reg: str, to_reg: str, r: Dict[str, Any], signal: str, ref: str):
            from_reg, to_reg = _s(from_reg), _s(to_reg)
            if not from_reg or not to_reg or from_reg == to_reg:
                return
            auth = _s(r.get("FX_AUTH_REF"))
            reason = _s(r.get("FX_REALLOC_REASON"))
            status = "AUTHORIZED" if auth else "UNEXPLAINED"
            key = (from_reg, to_reg, signal, ref, _s(r.get("FX_BUY_DATE")), _num(r.get("FX_AMOUNT")))
            if key in seen:
                return
            seen.add(key)
            rows.append({
                "FROM_REG": from_reg, "TO_REG": to_reg,
                "SOURCE_ORDER": _s(r.get(KEY_ORDER)), "SOURCE_BL": _s(r.get(KEY_BL)),
                "AMOUNT": _num(r.get("FX_AMOUNT")), "CURRENCY": _s(r.get("FX_CURRENCY")),
                "EVENT_DATE": _s(r.get("FX_BUY_DATE")), "SIGNAL_TYPE": signal,
                "REFERENCE": ref, "AUTH_REF": auth, "REASON": reason,
                "STATUS": status,
                "REVIEW_LABEL": ("جابجایی دارای شاهد مجوز" if auth else
                                 "جابجایی/ارجاع بین‌پرونده‌ای بدون شاهد مجوز — نیازمند بررسی"),
            })

        for r in fx.to_dict("records"):
            declared = _s(r.get(KEY_REG))
            oreg, treg = _s(r.get("FX_ORIGINAL_REG")), _s(r.get("FX_TARGET_REG"))
            if oreg and treg and oreg != treg:
                emit(oreg, treg, r, "EXPLICIT_REALLOCATION", f"{oreg}→{treg}")

            order = _s(r.get(KEY_ORDER))
            if declared and order and len(order_regs.get(order, set())) == 1:
                expected = next(iter(order_regs[order]))
                if expected != declared:
                    emit(declared, expected, r, "ORDER_REG_MISMATCH", f"ORDER:{order}")
            bl = _s(r.get(KEY_BL))
            if declared and bl and len(bl_regs.get(bl, set())) == 1:
                expected = next(iter(bl_regs[bl]))
                if expected != declared:
                    emit(declared, expected, r, "BL_REG_MISMATCH", f"BL:{bl}")

            # فیلدهای مقصد صریح حتی اگر Target REG خالی باشد، از mapping canonical حل می‌شوند.
            tord = _s(r.get("FX_TARGET_ORDER"))
            if declared and tord and len(order_regs.get(tord, set())) == 1:
                emit(declared, next(iter(order_regs[tord])), r, "TARGET_ORDER_REALLOCATION", f"ORDER:{tord}")
            tbl = _s(r.get("FX_TARGET_BL"))
            if declared and tbl and len(bl_regs.get(tbl, set())) == 1:
                emit(declared, next(iter(bl_regs[tbl])), r, "TARGET_BL_REALLOCATION", f"BL:{tbl}")
        return pd.DataFrame(rows)

    # ─────────────────────── مرحله و مهلت هر پرونده ─────────────────────
    def _build_timeline(self, df: pd.DataFrame, ctx: PipelineContext,
                        ledger: pd.DataFrame, rate_bridge: pd.DataFrame) -> pd.DataFrame:
        gmain = _groups(df, "CANONICAL_REG")
        gfx = _groups(ctx.sheet("fx_transaction", "main"))
        gcr = _groups(ctx.sheet("credit", "main"))
        gal = _groups(ctx.sheet("ntsw", "allocation"))
        gar = _groups(ctx.sheet("ntsw", "allocation_rows"))
        gcm = _groups(ctx.sheet("ntsw", "commitment"))
        gil = _groups(ctx.sheet("ilappend", "main"))
        grb = _groups(rate_bridge)

        out: List[Dict[str, Any]] = []
        for lr in ledger.to_dict("records"):
            reg = _s(lr.get("KEY_REG"))
            d = gmain.get(reg, pd.DataFrame())
            f = gfx.get(reg, pd.DataFrame())
            c = gcr.get(reg, pd.DataFrame())
            a = gal.get(reg, pd.DataFrame())
            ar = gar.get(reg, pd.DataFrame())
            n = gcm.get(reg, pd.DataFrame())
            il = gil.get(reg, pd.DataFrame())
            rb = grb.get(reg, pd.DataFrame())

            reg_date = _earliest(il, "IL_REG_DATE") or _earliest(c, "CRD_REG_DATE")
            queue_date = _earliest(ar, "NTSW_REQ_DATE") or _earliest(a, "NTSW_QUEUE_ENTER_DATE") or _earliest(a, "NTSW_REQ_DATE")
            alloc_date = _earliest(ar[ar.get("NTSW_REQUEST_STATE", pd.Series(index=ar.index, dtype=str)).eq("ALLOCATED")], "NTSW_ALLOC_DATE") if not ar.empty else _earliest(a, "NTSW_ALLOC_DATE")
            open_requests = int(_num(a.iloc[0].get("NTSW_OPEN_REQUESTS"))) if not a.empty else int((ar.get("NTSW_REQUEST_STATE", pd.Series(dtype=str)) == "OPEN").sum())
            allocated_requests = int(_num(a.iloc[0].get("NTSW_ALLOCATED_REQUESTS"))) if not a.empty else int((ar.get("NTSW_REQUEST_STATE", pd.Series(dtype=str)) == "ALLOCATED").sum())
            request_count = int(_num(a.iloc[0].get("NTSW_ALLOC_REQUESTS"))) if not a.empty else len(ar)
            buy_date = _earliest(f, "FX_BUY_DATE")
            fund_date = _earliest(c, "CRD_FUND_DATE")
            swift_date = _earliest(c, "CRD_SWIFT_DATE")
            ship_date = _earliest(d, "BL_DATE")
            customs_date = _earliest(d, "COT_DATE") or _earliest(d, "ARRIVAL_DATE")
            clear_date = _latest(d, "FULL_CLEAR_DATE")
            bank_docs_date = _latest(d, "DOC_SUBMIT_DATE")
            balance = _num(lr.get("FX_NTSW_BALANCE"))
            initial = _num(lr.get("FX_NTSW_INITIAL"))
            settled = bool(initial > EPS and balance <= EPS) or (
                "رفع" in _s(lr.get("FX_NTSW_RELEASE_STATUS")) and
                "نشده" not in _s(lr.get("FX_NTSW_RELEASE_STATUS")))

            cross_currency = False
            conversion_measured = False
            if rb is not None and not rb.empty:
                cross_currency = bool((rb["STATUS"] == "CROSS_CURRENCY_EVIDENCE_GAP").any() or
                                      (rb["STATUS"] == "CROSS_CURRENCY_MEASURED").any())
                conversion_measured = bool((rb["STATUS"] == "CROSS_CURRENCY_MEASURED").any())

            dates = {
                "ORDER_REG": reg_date,
                "ALLOCATION_QUEUE": queue_date,
                "ALLOCATION": alloc_date,
                "FX_PURCHASE": buy_date,
                "FUNDING": fund_date,
                "SWIFT_CONVERSION": swift_date or (buy_date if conversion_measured else None),
                "SHIPMENT": ship_date,
                "CUSTOMS": customs_date,
                "CLEARANCE": clear_date,
                "BANK_DOCS": bank_docs_date,
                "SETTLEMENT": None,
            }
            done = {k: bool(v) for k, v in dates.items()}
            # وجود REG خودش شاهد ثبت سفارش است حتی اگر تاریخ در سورس مالی نیامده باشد.
            done["ORDER_REG"] = bool(reg)
            # صف زمانی DONE است که درخواست‌ها از صف باز خارج شده باشند. وجود یک
            # درخواست باز هرگز با وجود یک tranche تخصیص‌یافته پنهان نمی‌شود.
            done["ALLOCATION_QUEUE"] = bool(request_count and open_requests == 0)
            done["ALLOCATION"] = bool(allocated_requests and open_requests == 0)
            done["SETTLEMENT"] = settled
            if cross_currency and not conversion_measured and not swift_date:
                done["SWIFT_CONVERSION"] = False

            # Deadlineهای مرحله‌ای. فقط وقتی مبنا واقعاً موجود است.
            due: Dict[str, Tuple[Any, str, str]] = {}
            queue_rule = ctx.rb.get("case_actions.allocation_queue", {}) or {}
            if queue_date and open_requests > 0 and queue_rule.get("watch_days"):
                due["ALLOCATION_QUEUE"] = (
                    queue_date + timedelta(days=int(queue_rule["watch_days"])),
                    "SLA داخلی پایش صف تخصیص؛ الزام قانونی نیست", "internal")
            alloc_rule = ctx.rb.get("fx_governance.deadlines.allocation_validity", {}) or {}
            if alloc_date and alloc_rule.get("days"):
                due["FX_PURCHASE"] = (
                    alloc_date + timedelta(days=int(alloc_rule["days"])),
                    "اعتبار تخصیص تا خرید/تأمین ارز", _s(alloc_rule.get("status")) or "needs_verification")

            # هشدار عملیاتی رسوب: 45 روز از تخلیه، صریحاً internal و نه مهلت قانونی ماده 24.
            discharge = _earliest(d, "DISCHARGE_DATE")
            dem = ctx.rb.get("customs.demurrage", {}) or {}
            if discharge and dem.get("critical_days"):
                due["CLEARANCE"] = (discharge + timedelta(days=int(dem["critical_days"])),
                                    "SLA داخلی رسوب پس از تخلیه", "internal")

            ntsw_deadline = _earliest(n, "NTSW_DEADLINE")
            if ntsw_deadline:
                due["SETTLEMENT"] = (ntsw_deadline, "مهلت ثبت‌شده در NTSW", "source_record")
            elif buy_date:
                seg_text = _first(d.get("کد سگمنت", pd.Series(dtype=str))) or _first(d.get("SEGMENT", pd.Series(dtype=str)))
                seg = seg_text if seg_text in {"production", "commercial"} else ctx.rb.detect_segment(seg_text)
                days = ctx.rb.release_deadline_days(seg)
                key = "release_commercial" if seg == "commercial" else "release_production"
                rule = ctx.rb.get(f"fx_governance.deadlines.{key}", {}) or {}
                due["SETTLEMENT"] = (buy_date + timedelta(days=int(days)),
                                     _s(rule.get("fa")) or f"SLA داخلی {days} روز", _s(rule.get("status")) or "internal")

            stage_codes = [x[0] for x in self.STAGES]
            for pos, (code, fa) in enumerate(self.STAGES):
                later_done = any(done.get(x, False) for x in stage_codes[pos + 1:])
                if code == "ALLOCATION_QUEUE" and open_requests > 0:
                    status = "PARTIAL" if allocated_requests > 0 else "CURRENT"
                elif code == "ALLOCATION" and allocated_requests > 0 and open_requests > 0:
                    status = "PARTIAL"
                elif done.get(code):
                    status = "DONE"
                elif later_done:
                    status = "EVIDENCE_GAP"
                else:
                    previous_done = all(done.get(x, False) for x in stage_codes[:pos])
                    status = "CURRENT" if previous_done else "PENDING"
                due_date, due_basis, rule_status = due.get(code, (None, "", ""))
                days_remaining = None
                if due_date:
                    days_remaining = (due_date - ctx.today).days
                    if not done.get(code):
                        if days_remaining < 0:
                            status = "OVERDUE"
                        elif days_remaining <= 30 and status in {"CURRENT", "PENDING"}:
                            status = "WARNING"
                evidence = ""
                if code == "ORDER_REG": evidence = "REG موجود" + (f"؛ {reg_date.isoformat()}" if reg_date else "؛ تاریخ ثبت سفارش ناقص")
                elif code == "ALLOCATION_QUEUE":
                    qrank = _s(a.iloc[0].get("NTSW_QUEUE_RANK")) if not a.empty else ""
                    qamt = _num(a.iloc[0].get("NTSW_OPEN_QUEUE_AMOUNT")) if not a.empty else 0.0
                    evidence = f"درخواست باز={open_requests}; مبلغ باز={qamt:,.2f}" + (f"؛ رتبه={qrank}" if qrank else "؛ رتبه در export موجود نیست")
                elif code == "ALLOCATION":
                    aamt = _num(a.iloc[0].get("NTSW_ALLOCATED_AMOUNT")) if not a.empty else 0.0
                    evidence = f"{_s(lr.get('FX_ALLOC_STATUS'))}; درخواست تخصیص‌یافته={allocated_requests}; مبلغ={aamt:,.2f}"
                elif code == "FX_PURCHASE": evidence = _s(lr.get("FX_CURRENCIES"))
                elif code == "FUNDING": evidence = _s(lr.get("FX_FUND_DATE"))
                elif code == "SWIFT_CONVERSION":
                    evidence = _s(lr.get("FX_SWIFT_DATE")) or ("شاهد تبدیل اندازه‌گیری‌شده" if conversion_measured else ("تبدیل ارز بدون شاهد کافی" if cross_currency else ""))
                elif code == "SHIPMENT": evidence = _s(lr.get("BL_LIST"))
                elif code == "CUSTOMS": evidence = _s(lr.get("FX_COTAGE"))
                elif code == "CLEARANCE": evidence = "ترخیص کامل" if bool(lr.get("FX_FULL_CLEAR")) else ""
                elif code == "BANK_DOCS":
                    evidence = (f"تاریخ ارائه/تطبیق سند={bank_docs_date.isoformat()}" if bank_docs_date else
                                "تاریخ ارائه/تطبیق سند ترخیص با بانک در export موجود نیست")
                elif code == "SETTLEMENT": evidence = _s(lr.get("FX_NTSW_RELEASE_STATUS")) or f"مانده={balance:,.2f}"
                out.append({
                    "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}", "STAGE_CODE": code,
                    "STAGE_ORDER": pos + 1, "STAGE_FA": fa, "STATUS": status,
                    "EVENT_DATE": dates.get(code).isoformat() if dates.get(code) else "",
                    "DUE_DATE": due_date.isoformat() if due_date else "",
                    "DAYS_REMAINING": days_remaining, "DEADLINE_BASIS": due_basis,
                    "RULE_STATUS": rule_status, "EVIDENCE": evidence,
                })
        return pd.DataFrame(out)

    # ───────────────────── خلاصه آمپرها و ریسک ──────────────────────────
    def _build_control(self, ledger: pd.DataFrame, timeline: pd.DataFrame,
                       rate_bridge: pd.DataFrame, realloc: pd.DataFrame,
                       ctx: PipelineContext) -> pd.DataFrame:
        gt = _groups(timeline)
        gr = _groups(rate_bridge)
        # reallocation می‌تواند یک REG را در مبدا یا مقصد درگیر کند.
        rr: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if realloc is not None and not realloc.empty:
            for r in realloc.to_dict("records"):
                rr[_s(r.get("FROM_REG"))].append(r)
                rr[_s(r.get("TO_REG"))].append(r)

        # شدت anomalyهای V26.16
        an = ctx.extras.get("fx_anomalies")
        ga = _groups(an) if an is not None and not an.empty else {}

        rows = []
        for lr in ledger.to_dict("records"):
            reg = _s(lr.get("KEY_REG"))
            t = gt.get(reg, pd.DataFrame())
            rbridge = gr.get(reg, pd.DataFrame())
            rel = rr.get(reg, [])
            auth = sum(1 for x in rel if x.get("STATUS") == "AUTHORIZED")
            unauth = sum(1 for x in rel if x.get("STATUS") == "UNEXPLAINED")
            if unauth and auth: rel_status = "MIXED"
            elif unauth: rel_status = "UNEXPLAINED"
            elif auth: rel_status = "AUTHORIZED"
            else: rel_status = "NONE"

            supplier_curs = _set_join(rbridge.get("PAID_CURRENCY", pd.Series(dtype=str))) if not rbridge.empty else ""
            measured = rbridge[rbridge.get("STATUS", pd.Series(dtype=str)) == "CROSS_CURRENCY_MEASURED"] if not rbridge.empty else pd.DataFrame()
            gaps = rbridge[rbridge.get("STATUS", pd.Series(dtype=str)) == "CROSS_CURRENCY_EVIDENCE_GAP"] if not rbridge.empty else pd.DataFrame()
            impacts = pd.to_numeric(measured.get("IMPACT_RIAL"), errors="coerce").dropna() if not measured.empty else pd.Series(dtype=float)
            impact = float(impacts.sum()) if not impacts.empty else 0.0
            if not gaps.empty: conv_status = "EVIDENCE_GAP"
            elif not measured.empty: conv_status = "MEASURED"
            elif supplier_curs: conv_status = "SAME_CURRENCY_OR_NO_CROSS"
            else: conv_status = "NO_SUPPLIER_PAYMENT_DATA"

            # نرخ متوسط خرید فقط وقتی یک ارز خرید وجود دارد؛ مخلوط ارزها قابل میانگین‌گیری نیست.
            purchase_curs = sorted({_s(x) for x in rbridge.get("PURCHASE_CURRENCY", pd.Series(dtype=str)) if _s(x)}) if not rbridge.empty else []
            wavg = 0.0
            if len(purchase_curs) == 1 and not rbridge.empty:
                am = pd.to_numeric(rbridge["PURCHASE_AMOUNT"], errors="coerce").fillna(0)
                ri = pd.to_numeric(rbridge["PURCHASE_RIAL"], errors="coerce").fillna(0)
                if am.sum() > EPS:
                    wavg = float(ri.sum() / am.sum()) if ri.sum() > EPS else float(
                        (pd.to_numeric(rbridge["PURCHASE_RATE_RIAL"], errors="coerce").fillna(0) * am).sum() / am.sum())

            current_stage = ""
            progress = 0.0
            deadline_date = ""
            deadline_days = None
            deadline_status = "NO_DEADLINE"
            deadline_basis = ""
            if not t.empty:
                # مرحله جاری: شدیدترین وضعیت باز، با اولویت ترتیب زمانی.
                open_t = t[t["STATUS"] != "DONE"].copy()
                if not open_t.empty:
                    open_t["_rank"] = open_t["STATUS"].map(_status_rank)
                    top_rank = open_t["_rank"].max()
                    current_stage = _s(open_t[open_t["_rank"] == top_rank].sort_values("STAGE_ORDER").iloc[0]["STAGE_FA"])
                else:
                    current_stage = "چرخه تکمیل"
                progress = round(100 * int((t["STATUS"] == "DONE").sum()) / len(t), 1)
                td = t[t["DUE_DATE"].astype(str).str.strip() != ""].copy()
                if not td.empty:
                    td["DAYS_REMAINING"] = pd.to_numeric(td["DAYS_REMAINING"], errors="coerce")
                    # نزدیک‌ترین deadline باز؛ deadline مرحله انجام‌شده دیگر مهم نیست.
                    td = td[td["STATUS"] != "DONE"]
                    if not td.empty:
                        x = td.sort_values("DAYS_REMAINING").iloc[0]
                        deadline_date = _s(x["DUE_DATE"])
                        deadline_days = int(x["DAYS_REMAINING"]) if pd.notna(x["DAYS_REMAINING"]) else None
                        deadline_basis = f"{_s(x['DEADLINE_BASIS'])} [{_s(x['RULE_STATUS'])}]"
                        if deadline_days is not None:
                            deadline_status = ("OVERDUE" if deadline_days < 0 else
                                               "CRITICAL" if deadline_days <= 15 else
                                               "WARNING" if deadline_days <= 45 else "OK")

            score = 0.0
            score += min(60.0, unauth * 35.0)
            if conv_status == "EVIDENCE_GAP": score += 20.0
            rial_out = _num(lr.get("FX_RIAL_OUTFLOW_REPORTED"))
            if impact > EPS:
                score += 10.0 + (10.0 if rial_out > EPS and impact / rial_out > 0.01 else 0.0)
            if deadline_status == "OVERDUE": score += 30.0
            elif deadline_status == "CRITICAL": score += 20.0
            elif deadline_status == "WARNING": score += 10.0
            anomalies = ga.get(reg, pd.DataFrame())
            if not anomalies.empty:
                sev = anomalies.get("شدت", pd.Series(dtype=str)).astype(str)
                score += min(35.0, int((sev == "CRITICAL").sum()) * 20 +
                             int((sev == "HIGH").sum()) * 12 + int((sev == "MEDIUM").sum()) * 5)
            trace = _num(lr.get("FX_TRACE_SCORE"))
            score += max(0.0, 100.0 - trace) * 0.20
            score = round(min(100.0, score), 1)
            band = "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM" if score >= 35 else "LOW"

            rows.append({
                "KEY_REG": reg,
                "FX_CONTROL_RISK_SCORE": score, "FX_CONTROL_RISK_BAND": band,
                "FX_DEADLINE_DATE": deadline_date,
                "FX_DAYS_REMAINING": deadline_days if deadline_days is not None else 0,
                "FX_DEADLINE_STATUS": deadline_status, "FX_DEADLINE_BASIS": deadline_basis,
                "FX_CURRENT_STAGE": current_stage, "FX_STAGE_PROGRESS_PCT": progress,
                "FX_REALLOCATION_STATUS": rel_status, "FX_REALLOCATION_COUNT": len(rel),
                "FX_UNAUTHORIZED_REALLOCATION_COUNT": unauth,
                "FX_CONVERSION_STATUS": conv_status,
                "FX_CONVERSION_IMPACT_RIAL": round(impact, 2),
                "FX_PURCHASE_WAVG_RATE": round(wavg, 4),
                "FX_SUPPLIER_CURRENCIES": supplier_curs,
            })
        return pd.DataFrame(rows)

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("FX_CURRENT_STAGE", "مرحله جاری جریان پول", 24, GROUP_DETAIL, order=71),
            ColumnSpec("FX_STAGE_PROGRESS_PCT", "پیشرفت مراحل پول (٪)", 16, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_low_bad", order=98),
            ColumnSpec("FX_CONTROL_RISK_SCORE", "امتیاز ریسک کنترل پول", 16, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_high_bad", order=99),
            ColumnSpec("FX_CONTROL_RISK_BAND", "سطح ریسک کنترل پول", 16, GROUP_ANALYTIC, order=100),
            ColumnSpec("FX_DAYS_REMAINING", "روز باقی‌مانده نزدیک‌ترین مهلت", 18, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_low_bad", order=101),
            ColumnSpec("FX_DEADLINE_BASIS", "مبنای نزدیک‌ترین مهلت", 42, GROUP_ANALYTIC,
                       wrap=True, order=102),
            ColumnSpec("FX_PURCHASE_WAVG_RATE", "نرخ موزون خرید ارز", 18, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, order=103),
            ColumnSpec("FX_SUPPLIER_CURRENCIES", "ارز پرداختی به تأمین‌کننده", 20, GROUP_ANALYTIC, order=104),
            ColumnSpec("FX_CONVERSION_IMPACT_RIAL", "اثر ریالی تبدیل ارز", 20, GROUP_ANALYTIC,
                       fmt=FMT_CURRENCY, color_rule="scale_high_bad", order=105),
            ColumnSpec("FX_CONVERSION_STATUS", "وضعیت شاهد تبدیل ارز", 24, GROUP_ANALYTIC, order=106),
            ColumnSpec("FX_REALLOCATION_STATUS", "وضعیت جابه‌جایی بین پرونده‌ها", 22, GROUP_ANALYTIC, order=107),
            ColumnSpec("FX_UNAUTHORIZED_REALLOCATION_COUNT", "جابجایی بدون شاهد مجوز", 16, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, color_rule="scale_high_bad", order=108),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        c = ctx.extras.get("fx_control_summary")
        if c is None or c.empty:
            return {}
        return {
            "ریسک بالای جریان پول": (int(c["FX_CONTROL_RISK_BAND"].isin(["HIGH", "CRITICAL"]).sum()),
                                      "Signal کنترلی؛ نه حکم تقلب"),
            "جابجایی بدون شاهد مجوز": (int(pd.to_numeric(c["FX_UNAUTHORIZED_REALLOCATION_COUNT"], errors="coerce").fillna(0).sum()),
                                        "نیازمند بررسی مالی/حقوقی"),
            "شکاف شاهد تبدیل ارز": (int((c["FX_CONVERSION_STATUS"] == "EVIDENCE_GAP").sum()),
                                    "ارز خرید و پرداخت متفاوت، ولی داده نرخ/تبدیل ناقص"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"Money Flow Control Tower": {
            "اثر ریالی تبدیل": "PaidAmount×PaidRate + Fee − (PaidAmount/CrossRate)×PurchaseRate",
            "قرارداد CrossRate": "واحد ارز مقصد به ازای ۱ واحد ارز مبدأ",
            "کنترل جابه‌جایی": "REG مالی در برابر مالک canonical سفارش/بارنامه + مجوز صریح",
            "امتیاز ریسک": "ترکیب جابه‌جایی بدون مجوز، شکاف تبدیل، Deadline، مغایرت و پوشش Evidence؛ سقف ۱۰۰",
            "اصل حقوقی": "Risk Signal ≠ Fraud finding؛ نتیجه قطعی نیازمند بررسی و شاهد انسانی/حقوقی است",
        }}
