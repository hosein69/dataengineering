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


def _amount_text(v: Any) -> str:
    """نمایش مبلغ شاهد؛ نامعلوم «نامعلوم» است نه 0.00."""
    x = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    return "نامعلوم" if pd.isna(x) else f"{float(x):,.2f}"


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
        "FX_CONVERSION_IMPACT_RIAL", "FX_PURCHASE_WAVG_RATE", "FX_PURCHASE_RATE_DISPLAY",
        "FX_SUPPLIER_CURRENCIES", "FX_MONEY_RECON_STATUS",
        "FX_MONEY_EVIDENCE_GAPS", "FX_OBLIGATION_RECON_STATUS",
    ]

    STAGES: Tuple[Tuple[str, str], ...] = (
        ("ORDER_REG", "ثبت سفارش"),
        ("ALLOCATION_QUEUE", "صف تخصیص"),
        ("ALLOCATION", "تخصیص ارز"),
        ("FX_PURCHASE", "خرید ارز"),
        ("FUNDING", "تأمین وجه"),
        ("SWIFT_CONVERSION", "سوئیفت / تبدیل / وصول ذی‌نفع"),
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
        money_ledger = self._build_money_ledger(df, ctx)
        reconciliation = self._build_money_reconciliation(money_ledger)
        control = self._build_control(ledger, timeline, rate_bridge, realloc, ctx)
        control = self._attach_money_reconciliation(control, reconciliation)

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
        ctx.extras["fx_money_ledger"] = money_ledger
        ctx.extras["fx_money_reconciliation"] = reconciliation
        ctx.extras["fx_control_summary"] = control

        m = control.set_index("KEY_REG")
        regs = df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s)
        for c in self.provides:
            if c in m.columns:
                df[c] = regs.map(m[c].to_dict())
        numeric = {"FX_CONTROL_RISK_SCORE", "FX_STAGE_PROGRESS_PCT",
                   "FX_REALLOCATION_COUNT", "FX_UNAUTHORIZED_REALLOCATION_COUNT",
                   "FX_CONVERSION_IMPACT_RIAL"}
        for c in numeric:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        nullable = {"FX_PURCHASE_WAVG_RATE", "FX_DAYS_REMAINING"}
        for c in nullable:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        for c in set(self.provides) - numeric - nullable:
            if c in df.columns:
                df[c] = df[c].fillna("")

        log.info(f"💸 [money-control] {len(control)} پرونده | {len(timeline)} مرحله | "
                 f"{len(money_ledger)} رویداد مبلغی | {len(reconciliation)} تطبیق ارزی | "
                 f"{len(rate_bridge)} پل نرخ/تبدیل | {len(realloc)} سیگنال جابه‌جایی")
        return df

    def _empty_outputs(self, df: pd.DataFrame) -> None:
        numeric = {"FX_CONTROL_RISK_SCORE", "FX_STAGE_PROGRESS_PCT",
                   "FX_REALLOCATION_COUNT", "FX_UNAUTHORIZED_REALLOCATION_COUNT",
                   "FX_CONVERSION_IMPACT_RIAL"}
        for c in self.provides:
            if c in ("FX_PURCHASE_WAVG_RATE", "FX_DAYS_REMAINING"):
                df[c] = float("nan")
            else:
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
            receipt_date = _earliest(f, "FX_RECEIPT_DATE")
            # BL_DATE هیچ تولیدکننده‌ای ندارد؛ زودترین شاهد حرکت محموله
            # همان چیزی است که این کنترل واقعاً به آن نیاز دارد.
            ship_date = _earliest(d, "SHIPPED_EVIDENCE_DATE")
            customs_date = _earliest(d, "COT_DATE") or _earliest(d, "ARRIVAL_DATE")
            clear_date = _latest(d, "FULL_CLEAR_DATE")
            bank_docs_date = _latest(d, "DOC_SUBMIT_DATE")
            balance = _num(lr.get("FX_NTSW_BALANCE"))
            initial = _num(lr.get("FX_NTSW_INITIAL"))
            # V29.9: مانده نامعلوم (NaN) هرگز «تسویه‌شده» نیست؛ قبلاً _num آن را
            # صفر می‌کرد و پرونده‌ی بدون شاهد مانده رفع‌تعهدشده نمایش داده می‌شد.
            balance_known = pd.notna(pd.to_numeric(pd.Series([lr.get("FX_NTSW_BALANCE")]),
                                                   errors="coerce").iloc[0])
            settled = bool(initial > EPS and balance_known and balance <= EPS) or (
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
                "SWIFT_CONVERSION": receipt_date or swift_date or (buy_date if conversion_measured else None),
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
                    qamt = _amount_text(a.iloc[0].get("NTSW_OPEN_QUEUE_AMOUNT")) if not a.empty else "0.00"
                    evidence = f"درخواست باز={open_requests}; مبلغ باز={qamt}" + (f"؛ رتبه={qrank}" if qrank else "؛ رتبه در export موجود نیست")
                elif code == "ALLOCATION":
                    aamt = _amount_text(a.iloc[0].get("NTSW_ALLOCATED_AMOUNT")) if not a.empty else "0.00"
                    evidence = f"{_s(lr.get('FX_ALLOC_STATUS'))}; درخواست تخصیص‌یافته={allocated_requests}; مبلغ={aamt}"
                elif code == "FX_PURCHASE": evidence = _s(lr.get("FX_CURRENCIES"))
                elif code == "FUNDING": evidence = _s(lr.get("FX_FUND_DATE"))
                elif code == "SWIFT_CONVERSION":
                    evidence = ((f"تایید وصول={receipt_date.isoformat()}" if receipt_date else "") or
                                _s(lr.get("FX_SWIFT_DATE")) or
                                ("شاهد تبدیل اندازه‌گیری‌شده" if conversion_measured else ("تبدیل ارز بدون شاهد کافی" if cross_currency else "")))
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

    # ───────────── دفتر کل مبلغی و تطبیق صفر تا صد پرونده ─────────────
    def _build_money_ledger(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        """Evidence ledger at REG × event grain.

        Missing amounts stay ``None`` and are never coerced to zero.  Cross-currency
        amounts are not added together here; reconciliation is performed per currency.
        """
        rows: List[Dict[str, Any]] = []

        def maybe_num(v: Any) -> Optional[float]:
            if is_empty_val(v):
                return None
            try:
                x = num_safe(v)
                return None if x is None or pd.isna(x) else float(x)
            except Exception:
                return None

        def emit(reg, code, fa, amount=None, currency="", event_date="", source="", ref="", status="", note=""):
            reg = _s(reg)
            if not reg:
                return
            rows.append({
                "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}", "EVENT_CODE": code,
                "EVENT_FA": fa, "EVENT_DATE": _s(event_date), "AMOUNT": maybe_num(amount),
                "CURRENCY": _s(currency), "SOURCE": source, "REFERENCE": _s(ref),
                "STATUS": _s(status), "NOTE": _s(note),
            })

        cr = ctx.sheet("credit", "main")
        if cr is not None and not cr.empty:
            for i, r in cr.reset_index(drop=True).iterrows():
                emit(r.get(KEY_REG), "REGISTRATION_VALUE", "ارزش ثبت سفارش/پروفرم",
                     r.get("CRD_PROFORMA_VALUE"), r.get("CRD_CURRENCY"), r.get("CRD_REG_DATE"),
                     "credit", f"credit#{i+1}", r.get("CRD_LAST_STATUS"))
                emit(r.get(KEY_REG), "BANK_FUNDING_IRR", "تأمین وجه بانکی ریالی",
                     None, "IRR", r.get("CRD_FUND_DATE"),
                     "credit", f"credit#{i+1}", r.get("CRD_LAST_STATUS"))
                # SWIFT amount is evidence of transfer instruction/receipt, not supplier receipt.
                emit(r.get(KEY_REG), "SWIFT", "سوئیفت بانکی",
                     r.get("CRD_SWIFT_AMOUNT"), r.get("CRD_SWIFT_CURRENCY"), r.get("CRD_SWIFT_DATE"),
                     "credit", f"credit#{i+1}", r.get("CRD_LC_NO"))

        ar = ctx.sheet("ntsw", "allocation_rows")
        if ar is None or ar.empty:
            ar = ctx.sheet("ntsw", "allocation")
        if ar is not None and not ar.empty:
            for i, r in ar.reset_index(drop=True).iterrows():
                state = _s(r.get("NTSW_REQUEST_STATE")) or ("ALLOCATED" if bool(r.get("NTSW_ALLOCATED")) else "")
                ref = r.get("NTSW_REQUEST_KEY") or r.get("NTSW_REQ_ROW") or f"allocation#{i+1}"
                emit(r.get(KEY_REG), "ALLOCATION_REQUEST", "درخواست تخصیص ارز",
                     r.get("NTSW_REQ_AMOUNT"), r.get("NTSW_REQ_CURRENCY"), r.get("NTSW_REQ_DATE"),
                     "ntsw/allocation", ref, state, r.get("NTSW_ALLOC_STATUS"))
                if state == "ALLOCATED" or bool(r.get("NTSW_ALLOCATED")):
                    emit(r.get(KEY_REG), "ALLOCATION", "تخصیص ارز",
                         r.get("NTSW_REQ_AMOUNT") if not is_empty_val(r.get("NTSW_REQ_AMOUNT")) else r.get("NTSW_ALLOCATED_AMOUNT"),
                         r.get("NTSW_REQ_CURRENCY"), r.get("NTSW_ALLOC_DATE"),
                         "ntsw/allocation", ref, state, r.get("NTSW_ALLOC_STATUS"))

        fx = ctx.sheet("fx_transaction", "main")
        if fx is not None and not fx.empty:
            for i, r in fx.reset_index(drop=True).iterrows():
                ref = f"fx#{i+1}"
                if _s(r.get("FX_PURCHASE_STATE")) != "PLANNED":
                    emit(r.get(KEY_REG), "FX_PURCHASE", "خرید ارز",
                         r.get("FX_AMOUNT"), r.get("FX_CURRENCY"), r.get("FX_BUY_DATE"),
                         "fx_transaction", ref, r.get("FX_STATUS"), r.get("FX_NOTE"))
                if not is_empty_val(r.get("FX_PAID_AMOUNT")) or _s(r.get("FX_PAID_CURRENCY")):
                    emit(r.get(KEY_REG), "SUPPLIER_PAYMENT", "پرداخت به ذی‌نفع",
                         r.get("FX_PAID_AMOUNT"), r.get("FX_PAID_CURRENCY"),
                         r.get("FX_RECEIPT_DATE") or r.get("FX_SWIFT_DATE") or r.get("FX_BUY_DATE"),
                         "fx_transaction", ref, "RECEIVED" if _s(r.get("FX_RECEIPT_DATE")) else "PAYMENT_EVIDENCE",
                         "تایید وصول مستقل از سوئیفت است" if not _s(r.get("FX_RECEIPT_DATE")) else "")

        cm = ctx.sheet("ntsw", "commitment")
        if cm is not None and not cm.empty:
            for i, r in cm.reset_index(drop=True).iterrows():
                initial = maybe_num(r.get("NTSW_INITIAL_COMMIT"))
                balance = maybe_num(r.get("NTSW_BALANCE"))
                released = (initial - balance) if initial is not None and balance is not None else None
                cur = r.get("NTSW_CURRENCY")
                ref = r.get("NTSW_COMMIT_ROWS") or f"commitment#{i+1}"
                emit(r.get(KEY_REG), "COMMITMENT_INITIAL", "تعهد اولیه ارزی",
                     initial, cur, r.get("NTSW_COMMIT_DATE"), "ntsw/commitment", ref, r.get("NTSW_RELEASE_STATUS"))
                emit(r.get(KEY_REG), "COMMITMENT_RELEASED", "رفع تعهد انجام‌شده",
                     released, cur, "", "ntsw/commitment", ref, r.get("NTSW_RELEASE_STATUS"))
                emit(r.get(KEY_REG), "COMMITMENT_BALANCE", "مانده تعهد",
                     balance, cur, r.get("NTSW_DEADLINE"), "ntsw/commitment", ref, r.get("NTSW_RELEASE_STATUS"),
                     "EVENT_DATE برای این ردیف مهلت رفع تعهد است، نه تاریخ تراکنش")

        cols = ["KEY_REG","FX_CASE_KEY","EVENT_CODE","EVENT_FA","EVENT_DATE","AMOUNT","CURRENCY","SOURCE","REFERENCE","STATUS","NOTE"]
        return pd.DataFrame(rows, columns=cols)

    def _build_money_reconciliation(self, money: pd.DataFrame) -> pd.DataFrame:
        """Reconcile only like-for-like currencies; unknown is never treated as zero."""
        if money is None or money.empty:
            return pd.DataFrame(columns=["KEY_REG","CURRENCY","RECON_STATUS"])
        amount_events = {
            "REGISTRATION_VALUE": "REGISTRATION_AMOUNT",
            "ALLOCATION_REQUEST": "REQUESTED_AMOUNT",
            "ALLOCATION": "ALLOCATED_AMOUNT",
            "FX_PURCHASE": "PURCHASED_AMOUNT",
            "SUPPLIER_PAYMENT": "SUPPLIER_PAID_AMOUNT",
            "COMMITMENT_INITIAL": "COMMITMENT_INITIAL",
            "COMMITMENT_RELEASED": "COMMITMENT_RELEASED",
            "COMMITMENT_BALANCE": "COMMITMENT_BALANCE",
        }
        x = money[money["EVENT_CODE"].isin(amount_events)].copy()
        x = x[x["CURRENCY"].astype(str).str.strip().ne("")]
        rows = []
        for (reg, cur), g in x.groupby(["KEY_REG","CURRENCY"], sort=False):
            vals: Dict[str, Optional[float]] = {}
            for ev, col in amount_events.items():
                z = pd.to_numeric(g.loc[g["EVENT_CODE"].eq(ev), "AMOUNT"], errors="coerce").dropna()
                vals[col] = float(z.sum()) if not z.empty else None
            initial, released, balance = vals["COMMITMENT_INITIAL"], vals["COMMITMENT_RELEASED"], vals["COMMITMENT_BALANCE"]
            obligation_variance = None
            obligation_status = "NO_COMMITMENT_EVIDENCE"
            if initial is not None and released is not None and balance is not None:
                obligation_variance = initial - released - balance
                tol = max(EPS, abs(initial) * 1e-6)
                obligation_status = "OK" if abs(obligation_variance) <= tol else "MISMATCH"

            required = ["REQUESTED_AMOUNT","ALLOCATED_AMOUNT","PURCHASED_AMOUNT","SUPPLIER_PAID_AMOUNT","COMMITMENT_INITIAL","COMMITMENT_BALANCE"]
            gaps = [c for c in required if vals[c] is None]
            # Differences are operational open gaps, not automatically errors.
            def delta(a, b):
                return None if vals[a] is None or vals[b] is None else vals[a] - vals[b]
            req_alloc = delta("REQUESTED_AMOUNT","ALLOCATED_AMOUNT")
            alloc_buy = delta("ALLOCATED_AMOUNT","PURCHASED_AMOUNT")
            buy_paid = delta("PURCHASED_AMOUNT","SUPPLIER_PAID_AMOUNT")
            if obligation_status == "MISMATCH":
                status = "ACCOUNTING_MISMATCH"
            elif gaps:
                status = "EVIDENCE_GAP"
            elif any(abs(v) > max(EPS, abs(vals["REQUESTED_AMOUNT"] or 0)*1e-6) for v in (req_alloc, alloc_buy, buy_paid) if v is not None):
                status = "OPEN_AMOUNT_GAP"
            else:
                status = "RECONCILED"
            rows.append({"KEY_REG":reg,"FX_CASE_KEY":f"REG:{reg}","CURRENCY":cur,
                         **vals,
                         "REQUEST_MINUS_ALLOCATED":req_alloc,
                         "ALLOCATED_MINUS_PURCHASED":alloc_buy,
                         "PURCHASED_MINUS_SUPPLIER_PAID":buy_paid,
                         "OBLIGATION_INVARIANT_VARIANCE":obligation_variance,
                         "OBLIGATION_RECON_STATUS":obligation_status,
                         "EVIDENCE_GAPS":" | ".join(gaps),"RECON_STATUS":status})
        return pd.DataFrame(rows)

    def _attach_money_reconciliation(self, control: pd.DataFrame, reconciliation: pd.DataFrame) -> pd.DataFrame:
        out = control.copy()
        if reconciliation is None or reconciliation.empty:
            out["FX_MONEY_RECON_STATUS"] = "NO_AMOUNT_EVIDENCE"
            out["FX_MONEY_EVIDENCE_GAPS"] = ""
            out["FX_OBLIGATION_RECON_STATUS"] = "NO_COMMITMENT_EVIDENCE"
            return out
        rank = {"ACCOUNTING_MISMATCH":4,"EVIDENCE_GAP":3,"OPEN_AMOUNT_GAP":2,"RECONCILED":1}
        # Aggregate once per REG.  The former implementation rebuilt a boolean
        # mask over the entire control table for every reconciliation group
        # (REGs × control rows).  Real NTSW snapshots contain thousands of REGs,
        # so that quadratic update dominated the stage while adding no semantics.
        recon_map: Dict[str, Dict[str, Any]] = {}
        for reg, g in reconciliation.groupby("KEY_REG", sort=False):
            statuses = [_s(x) for x in g["RECON_STATUS"]]
            worst = max(statuses, key=lambda x: rank.get(x,0)) if statuses else ""
            recon_map[_s(reg)] = {
                "status": worst,
                "gaps": _set_join(g["EVIDENCE_GAPS"]),
                "obligation": _set_join(g["OBLIGATION_RECON_STATUS"]),
            }
        regs = out["KEY_REG"].map(_s)
        out["FX_MONEY_RECON_STATUS"] = regs.map(
            lambda r: recon_map.get(r, {}).get("status", "NO_AMOUNT_EVIDENCE"))
        out["FX_MONEY_EVIDENCE_GAPS"] = regs.map(
            lambda r: recon_map.get(r, {}).get("gaps", ""))
        out["FX_OBLIGATION_RECON_STATUS"] = regs.map(
            lambda r: recon_map.get(r, {}).get("obligation", "NO_COMMITMENT_EVIDENCE"))
        mismatch = out["FX_MONEY_RECON_STATUS"].eq("ACCOUNTING_MISMATCH")
        if mismatch.any():
            out.loc[mismatch,"FX_CONTROL_RISK_SCORE"] = (
                pd.to_numeric(out.loc[mismatch,"FX_CONTROL_RISK_SCORE"], errors="coerce")
                .fillna(0).add(20).clip(upper=100)
            )
        score = pd.to_numeric(out["FX_CONTROL_RISK_SCORE"], errors="coerce").fillna(0)
        out["FX_CONTROL_RISK_BAND"] = score.map(lambda v: "CRITICAL" if v>=80 else "HIGH" if v>=60 else "MEDIUM" if v>=35 else "LOW")
        return out

    # ───────────────────── خلاصه آمپرها و ریسک ──────────────────────────
    def _build_control(self, ledger: pd.DataFrame, timeline: pd.DataFrame,
                       rate_bridge: pd.DataFrame, realloc: pd.DataFrame,
                       ctx: PipelineContext) -> pd.DataFrame:
        # Pre-aggregate the small per-case frames once.  Repeated pandas
        # filtering/sorting of 11-row timeline frames for every REG was far
        # slower than the business calculations themselves on production data.
        timeline_summary: Dict[str, Dict[str, Any]] = {}
        if timeline is not None and not timeline.empty and KEY_REG in timeline.columns:
            for reg, g in timeline.groupby(timeline[KEY_REG].map(_s), sort=False):
                reg = _s(reg)
                if not reg:
                    continue
                recs = g.to_dict("records")
                open_rows = [r for r in recs if _s(r.get("STATUS")) != "DONE"]
                if open_rows:
                    top_rank = max(_status_rank(_s(r.get("STATUS"))) for r in open_rows)
                    top = [r for r in open_rows if _status_rank(_s(r.get("STATUS"))) == top_rank]
                    chosen = min(top, key=lambda r: _num(r.get("STAGE_ORDER")))
                    current_stage = _s(chosen.get("STAGE_FA"))
                else:
                    current_stage = "چرخه تکمیل"
                progress = round(100 * sum(_s(r.get("STATUS")) == "DONE" for r in recs) / len(recs), 1) if recs else 0.0

                due_rows = [r for r in open_rows if _s(r.get("DUE_DATE"))]
                deadline_date = ""
                deadline_days = None
                deadline_status = "NO_DEADLINE"
                deadline_basis = ""
                if due_rows:
                    def _due_sort(r):
                        v = pd.to_numeric(pd.Series([r.get("DAYS_REMAINING")]), errors="coerce").iloc[0]
                        return float(v) if pd.notna(v) else float("inf")
                    x = min(due_rows, key=_due_sort)
                    deadline_date = _s(x.get("DUE_DATE"))
                    dv = pd.to_numeric(pd.Series([x.get("DAYS_REMAINING")]), errors="coerce").iloc[0]
                    deadline_days = int(dv) if pd.notna(dv) else None
                    deadline_basis = f"{_s(x.get('DEADLINE_BASIS'))} [{_s(x.get('RULE_STATUS'))}]"
                    if deadline_days is not None:
                        deadline_status = ("OVERDUE" if deadline_days < 0 else
                                           "CRITICAL" if deadline_days <= 15 else
                                           "WARNING" if deadline_days <= 45 else "OK")
                timeline_summary[reg] = {
                    "current_stage": current_stage,
                    "progress": progress,
                    "deadline_date": deadline_date,
                    "deadline_days": deadline_days,
                    "deadline_status": deadline_status,
                    "deadline_basis": deadline_basis,
                }

        rate_summary: Dict[str, Dict[str, Any]] = {}
        if rate_bridge is not None and not rate_bridge.empty and KEY_REG in rate_bridge.columns:
            for reg, g in rate_bridge.groupby(rate_bridge[KEY_REG].map(_s), sort=False):
                reg = _s(reg)
                if not reg:
                    continue
                recs = g.to_dict("records")
                supplier_curs = _set_join(r.get("PAID_CURRENCY") for r in recs)
                measured = [r for r in recs if _s(r.get("STATUS")) == "CROSS_CURRENCY_MEASURED"]
                gaps = [r for r in recs if _s(r.get("STATUS")) == "CROSS_CURRENCY_EVIDENCE_GAP"]
                impact = sum(_num(r.get("IMPACT_RIAL")) for r in measured)
                if gaps: conv_status = "EVIDENCE_GAP"
                elif measured: conv_status = "MEASURED"
                elif supplier_curs: conv_status = "SAME_CURRENCY_OR_NO_CROSS"
                else: conv_status = "NO_SUPPLIER_PAYMENT_DATA"

                by_cur: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                for r in recs:
                    cur = _s(r.get("PURCHASE_CURRENCY"))
                    if cur:
                        by_cur[cur].append(r)
                rate_parts = []
                for cur in sorted(by_cur):
                    rows_cur = by_cur[cur]
                    amount = sum(_num(r.get("PURCHASE_AMOUNT")) for r in rows_cur)
                    if amount <= EPS:
                        continue
                    rial = sum(_num(r.get("PURCHASE_RIAL")) for r in rows_cur)
                    if rial > EPS:
                        cr = rial / amount
                    else:
                        cr = sum(_num(r.get("PURCHASE_RATE_RIAL")) * _num(r.get("PURCHASE_AMOUNT")) for r in rows_cur) / amount
                    if cr > EPS:
                        rate_parts.append((cur, float(cr)))
                rate_summary[reg] = {
                    "supplier_curs": supplier_curs,
                    "conv_status": conv_status,
                    "impact": float(impact),
                    "wavg": rate_parts[0][1] if len(rate_parts) == 1 else None,
                    "rate_display": " | ".join(f"{cur}: {rate:,.4f}" for cur, rate in rate_parts),
                }
        # reallocation می‌تواند یک REG را در مبدا یا مقصد درگیر کند.
        rr: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if realloc is not None and not realloc.empty:
            for r in realloc.to_dict("records"):
                rr[_s(r.get("FROM_REG"))].append(r)
                rr[_s(r.get("TO_REG"))].append(r)

        # شدت anomalyهای V26.16
        an = ctx.extras.get("fx_anomalies")
        anomaly_counts: Dict[str, Dict[str, int]] = {}
        if an is not None and not an.empty and KEY_REG in an.columns:
            for reg, g in an.groupby(an[KEY_REG].map(_s), sort=False):
                sev = g.get("شدت", pd.Series(dtype=str)).astype(str)
                anomaly_counts[_s(reg)] = {
                    "CRITICAL": int((sev == "CRITICAL").sum()),
                    "HIGH": int((sev == "HIGH").sum()),
                    "MEDIUM": int((sev == "MEDIUM").sum()),
                }

        rows = []
        for lr in ledger.to_dict("records"):
            reg = _s(lr.get("KEY_REG"))
            rel = rr.get(reg, [])
            auth = sum(1 for x in rel if x.get("STATUS") == "AUTHORIZED")
            unauth = sum(1 for x in rel if x.get("STATUS") == "UNEXPLAINED")
            if unauth and auth: rel_status = "MIXED"
            elif unauth: rel_status = "UNEXPLAINED"
            elif auth: rel_status = "AUTHORIZED"
            else: rel_status = "NONE"

            rs = rate_summary.get(reg, {})
            supplier_curs = rs.get("supplier_curs", "")
            conv_status = rs.get("conv_status", "NO_SUPPLIER_PAYMENT_DATA")
            impact = float(rs.get("impact", 0.0) or 0.0)
            wavg = rs.get("wavg")
            rate_display = rs.get("rate_display", "")

            current_stage = ""
            progress = 0.0
            deadline_date = ""
            deadline_days = None
            deadline_status = "NO_DEADLINE"
            deadline_basis = ""
            ts = timeline_summary.get(reg)
            if ts:
                current_stage = ts["current_stage"]
                progress = ts["progress"]
                deadline_date = ts["deadline_date"]
                deadline_days = ts["deadline_days"]
                deadline_status = ts["deadline_status"]
                deadline_basis = ts["deadline_basis"]

            score = 0.0
            score += min(60.0, unauth * 35.0)
            if conv_status == "EVIDENCE_GAP": score += 20.0
            rial_out = _num(lr.get("FX_RIAL_OUTFLOW_REPORTED"))
            if impact > EPS:
                score += 10.0 + (10.0 if rial_out > EPS and impact / rial_out > 0.01 else 0.0)
            if deadline_status == "OVERDUE": score += 30.0
            elif deadline_status == "CRITICAL": score += 20.0
            elif deadline_status == "WARNING": score += 10.0
            sev = anomaly_counts.get(reg, {})
            if sev:
                score += min(35.0, sev.get("CRITICAL", 0) * 20 +
                             sev.get("HIGH", 0) * 12 + sev.get("MEDIUM", 0) * 5)
            trace = _num(lr.get("FX_TRACE_SCORE"))
            score += max(0.0, 100.0 - trace) * 0.20
            score = round(min(100.0, score), 1)
            band = "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM" if score >= 35 else "LOW"

            rows.append({
                "KEY_REG": reg,
                "FX_CONTROL_RISK_SCORE": score, "FX_CONTROL_RISK_BAND": band,
                "FX_DEADLINE_DATE": deadline_date,
                # بدون مهلت، «۰ روز باقی‌مانده» (سررسید امروز) گمراه‌کننده است.
                "FX_DAYS_REMAINING": deadline_days if deadline_days is not None else float("nan"),
                "FX_DEADLINE_STATUS": deadline_status, "FX_DEADLINE_BASIS": deadline_basis,
                "FX_CURRENT_STAGE": current_stage, "FX_STAGE_PROGRESS_PCT": progress,
                "FX_REALLOCATION_STATUS": rel_status, "FX_REALLOCATION_COUNT": len(rel),
                "FX_UNAUTHORIZED_REALLOCATION_COUNT": unauth,
                "FX_CONVERSION_STATUS": conv_status,
                "FX_CONVERSION_IMPACT_RIAL": round(impact, 2),
                "FX_PURCHASE_WAVG_RATE": (round(wavg, 4) if wavg is not None else None),
                "FX_PURCHASE_RATE_DISPLAY": rate_display,
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
            ColumnSpec("FX_PURCHASE_WAVG_RATE", "نرخ موزون خرید ارز (تک‌ارز)", 18, GROUP_ANALYTIC,
                       fmt=FMT_DECIMAL, order=103),
            ColumnSpec("FX_PURCHASE_RATE_DISPLAY", "نرخ خرید به تفکیک ارز", 28, GROUP_ANALYTIC, order=103),
            ColumnSpec("FX_SUPPLIER_CURRENCIES", "ارز پرداختی به تأمین‌کننده", 20, GROUP_ANALYTIC, order=104),
            ColumnSpec("FX_MONEY_RECON_STATUS", "وضعیت تطبیق صفر تا صد مبالغ", 24, GROUP_ANALYTIC, order=104),
            ColumnSpec("FX_OBLIGATION_RECON_STATUS", "تطبیق معادله تعهد", 22, GROUP_ANALYTIC, order=104),
            ColumnSpec("FX_MONEY_EVIDENCE_GAPS", "شکاف شاهد مبلغی", 36, GROUP_ANALYTIC, wrap=True, order=104),
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
