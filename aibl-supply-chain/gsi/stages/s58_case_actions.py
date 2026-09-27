# -*- coding: utf-8 -*-
"""مرحله ۵۸ — صف اقدام پرونده و پیشنهاد قابل ایمیل.

هدف این مرحله «تصمیم خودکار» نیست؛ هر پیشنهاد یک Draft قابل بازبینی است.
Rule Basis، شکاف شواهد، مالک پیشنهادی و تاریخ سررسید داخلی همراه آن ثبت می‌شود.
هیچ موردی صرفاً با Signal به عنوان Fraud اعلام نمی‌شود.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha1
from typing import Any, Dict, List, Optional

import pandas as pd

from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from .base import ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, PipelineContext, Stage, register


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> float:
    try:
        return float(num_safe(v) or 0.0)
    except Exception:
        return 0.0


def _d(v: Any):
    return CalendarEngine.parse(v)


def _priority(age: Optional[int], rule: Dict[str, Any], *, default: str = "MEDIUM") -> str:
    if age is None:
        return default
    if rule.get("critical_days") is not None and age >= int(rule["critical_days"]):
        return "CRITICAL"
    if rule.get("high_days") is not None and age >= int(rule["high_days"]):
        return "HIGH"
    if rule.get("watch_days") is not None and age >= int(rule["watch_days"]):
        return "MEDIUM"
    return "LOW"


def _rank(p: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(p, 0)


@register
class CaseActionStage(Stage):
    name = "case_actions"
    title = "صف اقدام پرونده، پیشنهاد سیستم و Draft Email"
    order = 58
    tolerant = True
    requires = ["FX_CASE_KEY", "FX_CURRENT_STAGE"]
    provides = [
        "NEXT_ACTION_ID", "NEXT_ACTION_PRIORITY", "NEXT_ACTION_TITLE",
        "NEXT_ACTION_OWNER", "NEXT_ACTION_DUE_DATE", "NEXT_ACTION_DAYS",
        "NEXT_ACTION_EVIDENCE_GAPS", "NEXT_ACTION_RULE_BASIS",
        "NEXT_ACTION_EMAIL_READY", "CASE_ACTION_COUNT",
    ]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        ledger = ctx.extras.get("fx_ledger")
        timeline = ctx.extras.get("fx_stage_timeline")
        realloc = ctx.extras.get("fx_reallocations")
        bridge = ctx.extras.get("fx_rate_bridge")
        if ledger is None or ledger.empty:
            self._empty(df)
            ctx.extras["case_actions"] = pd.DataFrame()
            return df

        actions = self._build_actions(df, ctx, ledger, timeline, realloc, bridge)
        ctx.extras["case_actions"] = actions
        if actions.empty:
            self._empty(df)
            return df

        # یک اقدام اصلی برای هر REG؛ بقیه در Action Queue قابل Drill-down می‌مانند.
        az = actions.copy()
        az["_RANK"] = az["PRIORITY"].map(_rank)
        az["_DUE"] = pd.to_datetime(az["DUE_DATE"], errors="coerce")
        top = (az.sort_values(["KEY_REG", "_RANK", "_DUE", "ACTION_ID"],
                              ascending=[True, False, True, True], na_position="last")
                 .drop_duplicates("KEY_REG", keep="first"))
        counts = actions.groupby("KEY_REG").size().to_dict()
        m = top.set_index("KEY_REG")
        regs = df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s)
        mapping = {
            "NEXT_ACTION_ID": "ACTION_ID",
            "NEXT_ACTION_PRIORITY": "PRIORITY",
            "NEXT_ACTION_TITLE": "TITLE",
            "NEXT_ACTION_OWNER": "OWNER_ROLE",
            "NEXT_ACTION_DUE_DATE": "DUE_DATE",
            "NEXT_ACTION_DAYS": "DAYS_REMAINING",
            "NEXT_ACTION_EVIDENCE_GAPS": "EVIDENCE_GAPS",
            "NEXT_ACTION_RULE_BASIS": "RULE_BASIS",
            "NEXT_ACTION_EMAIL_READY": "EMAIL_READY",
        }
        for target, src in mapping.items():
            df[target] = regs.map(m[src].to_dict()) if src in m.columns else ""
        df["CASE_ACTION_COUNT"] = regs.map(counts).fillna(0).astype(int)
        df["NEXT_ACTION_DAYS"] = pd.to_numeric(df["NEXT_ACTION_DAYS"], errors="coerce")
        for c in set(self.provides) - {"CASE_ACTION_COUNT", "NEXT_ACTION_DAYS"}:
            df[c] = df[c].fillna("")

        # ledger پرونده هم پیشنهاد اصلی را می‌گیرد تا HTML/Excel قدیمی آن را ببینند.
        led = ledger.copy()
        for target, src in mapping.items():
            if src in m.columns:
                led[target] = led["KEY_REG"].map(m[src].to_dict())
        led["CASE_ACTION_COUNT"] = led["KEY_REG"].map(counts).fillna(0).astype(int)
        ctx.extras["fx_ledger"] = led

        log.info(f"🎯 [case-actions] {len(actions)} پیشنهاد برای "
                 f"{actions['KEY_REG'].nunique()} پرونده | Draft Email، نیازمند تأیید کاربر")
        return df

    def _build_actions(self, df: pd.DataFrame, ctx: PipelineContext,
                       ledger: pd.DataFrame, timeline: Optional[pd.DataFrame],
                       realloc: Optional[pd.DataFrame], bridge: Optional[pd.DataFrame]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        tl = timeline if timeline is not None else pd.DataFrame()
        by_tl = {str(k): g for k, g in tl.groupby("KEY_REG", sort=False)} if not tl.empty else {}
        by_df = ({str(k): g for k, g in df[df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s) != ""]
                  .groupby(df.get("CANONICAL_REG").map(_s), sort=False)}
                 if "CANONICAL_REG" in df.columns else {})

        def add(reg: str, code: str, title: str, owner: str, priority: str,
                rationale: str, *, due=None, gaps: str = "", basis: str = "internal",
                source_class: str = "INTERNAL_ADVISORY") -> None:
            due_s = due.isoformat() if due else ""
            days = (due - ctx.today).days if due else None
            raw = f"{reg}|{code}|{title}|{due_s}"
            aid = "ACT-" + sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
            subject = f"GSI | اقدام پیشنهادی پرونده {reg} | {title}"
            body = (f"پرونده: {reg}\nاولویت: {priority}\nاقدام پیشنهادی: {title}\n"
                    f"مالک پیشنهادی: {owner}\nعلت: {rationale}\n"
                    f"شکاف شواهد: {gaps or '—'}\nمبنای پیشنهاد: {basis}\n"
                    "این متن پیشنهاد GSI است و قبل از ارسال نیازمند بازبینی انسانی است.")
            rows.append({
                "ACTION_ID": aid, "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}",
                "ACTION_CODE": code, "PRIORITY": priority, "TITLE": title,
                "OWNER_ROLE": owner, "RATIONALE": rationale,
                "DUE_DATE": due_s, "DAYS_REMAINING": days,
                "EVIDENCE_GAPS": gaps, "RULE_BASIS": basis,
                "SOURCE_CLASS": source_class, "STATUS": "PENDING_REVIEW",
                "EMAIL_READY": True, "EMAIL_SUBJECT": subject, "EMAIL_BODY": body,
                "HUMAN_REVIEW_REQUIRED": True,
            })

        for lr in ledger.to_dict("records"):
            reg = _s(lr.get("KEY_REG"))
            if not reg:
                continue
            t = by_tl.get(reg, pd.DataFrame())
            dcase = by_df.get(reg, pd.DataFrame())

            def stage(code: str):
                z = t[t.get("STAGE_CODE", pd.Series(dtype=str)) == code] if not t.empty else pd.DataFrame()
                return None if z.empty else z.iloc[0]

            # صف تخصیص
            q = stage("ALLOCATION_QUEUE")
            if q is not None and _s(q.get("STATUS")) in {"CURRENT", "PARTIAL", "WARNING", "OVERDUE"}:
                rule = ctx.rb.get("case_actions.allocation_queue", {}) or {}
                qd = _d(q.get("EVENT_DATE"))
                age = (ctx.today - qd).days if qd else None
                pr = _priority(age, rule)
                due = qd + timedelta(days=int(rule.get("watch_days", 7))) if qd else None
                add(reg, "FOLLOW_ALLOCATION_QUEUE", _s(rule.get("action_fa")) or "پیگیری صف تخصیص",
                    _s(rule.get("owner_role")) or "اعتبارات", pr,
                    _s(q.get("EVIDENCE")) or "درخواست تخصیص باز است", due=due,
                    gaps="رتبه صف" if "رتبه در export موجود نیست" in _s(q.get("EVIDENCE")) else "",
                    basis="case_actions.allocation_queue [internal SLA]")

            # تخصیص شده ولی خرید ارز ثبت نشده
            a = stage("ALLOCATION"); p = stage("FX_PURCHASE")
            if a is not None and _s(a.get("STATUS")) in {"DONE", "PARTIAL"} and p is not None and _s(p.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.allocation_to_purchase", {}) or {}
                ad = _d(a.get("EVENT_DATE")); age = (ctx.today - ad).days if ad else None
                add(reg, "ALLOCATED_NO_FX_PURCHASE", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), "تخصیص ثبت شده ولی شاهد خرید/تأمین ارز کامل نیست",
                    due=(ad + timedelta(days=int(rule.get("watch_days", 5))) if ad else None),
                    gaps="اعلامیه خرید/تأمین ارز و نرخ", basis="case_actions.allocation_to_purchase [internal SLA]")

            # خرید ارز بدون funding/swift
            fp = stage("FX_PURCHASE"); fund = stage("FUNDING"); swift = stage("SWIFT_CONVERSION")
            if fp is not None and _s(fp.get("STATUS")) == "DONE" and fund is not None and _s(fund.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.purchase_to_funding", {}) or {}; dt = _d(fp.get("EVENT_DATE")); age=(ctx.today-dt).days if dt else None
                add(reg, "FX_PURCHASE_NO_FUNDING", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), "خرید ارز ثبت شده ولی شاهد تأمین وجه بانکی نیست",
                    due=(dt + timedelta(days=int(rule.get("watch_days", 3))) if dt else None),
                    gaps="رسید تأمین وجه/دستور پرداخت", basis="case_actions.purchase_to_funding [internal SLA]")
            if fund is not None and _s(fund.get("STATUS")) == "DONE" and swift is not None and _s(swift.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.funding_to_swift", {}) or {}; dt = _d(fund.get("EVENT_DATE")); age=(ctx.today-dt).days if dt else None
                add(reg, "FUNDING_NO_SWIFT", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), "تأمین وجه ثبت شده ولی شاهد SWIFT/تأیید ذی‌نفع یا تبدیل کامل نیست",
                    due=(dt + timedelta(days=int(rule.get("watch_days", 3))) if dt else None),
                    gaps="SWIFT/تأیید ذی‌نفع/شاهد تبدیل", basis="case_actions.funding_to_swift [internal SLA]")

            # گمرک → ترخیص
            cust = stage("CUSTOMS"); clear = stage("CLEARANCE")
            if cust is not None and _s(cust.get("STATUS")) == "DONE" and clear is not None and _s(clear.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.customs_to_clearance", {}) or {}; dt = _d(cust.get("EVENT_DATE")); age=(ctx.today-dt).days if dt else None
                add(reg, "CUSTOMS_NOT_CLEARED", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), "شاهد ورود/اظهار گمرکی وجود دارد ولی ترخیص کامل نشده",
                    due=(dt + timedelta(days=int(rule.get("watch_days", 7))) if dt else None),
                    gaps="مجوزها/پروانه/علت رسوب", basis="case_actions.customs_to_clearance [internal SLA]")

            # ترخیص فیزیکی با «ارائه/تطبیق سند ترخیص مطابق نزد بانک» یکی نیست.
            bank_docs = stage("BANK_DOCS"); sett = stage("SETTLEMENT")
            if clear is not None and _s(clear.get("STATUS")) == "DONE" and bank_docs is not None and _s(bank_docs.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.clearance_to_bank_docs", {}) or {}; dt = _d(clear.get("EVENT_DATE")); age=(ctx.today-dt).days if dt else None
                add(reg, "CLEARED_BANK_DOCS_MISSING", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), "ترخیص کامل ثبت شده ولی شاهد ارائه/تطبیق سند ترخیص با بانک موجود نیست",
                    due=(dt + timedelta(days=int(rule.get("watch_days", 3))) if dt else None),
                    gaps="تاریخ/رسید ارائه سند ترخیص مطابق و نتیجه تطبیق بانک",
                    basis="CBI obligation separation 1405/03/04 + case_actions.clearance_to_bank_docs [internal SLA]")
            if bank_docs is not None and _s(bank_docs.get("STATUS")) == "DONE" and sett is not None and _s(sett.get("STATUS")) != "DONE":
                rule = ctx.rb.get("case_actions.bank_docs_to_settlement", {}) or {}; dt = _d(bank_docs.get("EVENT_DATE")); age=(ctx.today-dt).days if dt else None
                add(reg, "BANK_DOCS_COMMITMENT_OPEN", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                    _priority(age, rule), f"سند ترخیص ارائه شده ولی مانده تعهد={_num(lr.get('FX_NTSW_BALANCE')):,.2f}",
                    due=(dt + timedelta(days=int(rule.get("watch_days", 7))) if dt else None),
                    gaps="نتیجه تطبیق/مابه‌التفاوت نرخ/وثیقه/ثبت رفع تعهد",
                    basis="NTSW source record + CBI 1405/03/04 + case_actions.bank_docs_to_settlement [internal SLA]")

            # جابه‌جایی بدون شاهد مجوز — Investigation, نه Fraud.
            if realloc is not None and not realloc.empty:
                rz = realloc[((realloc.get("FROM_REG", pd.Series("", index=realloc.index)).map(_s) == reg) |
                              (realloc.get("TO_REG", pd.Series("", index=realloc.index)).map(_s) == reg)) &
                             (realloc.get("STATUS", pd.Series("", index=realloc.index)).map(_s) == "UNEXPLAINED")]
                if not rz.empty:
                    rule = ctx.rb.get("case_actions.unexplained_reallocation", {}) or {}
                    add(reg, "UNEXPLAINED_REALLOCATION", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                        "CRITICAL", f"{len(rz)} ارتباط بین‌پرونده‌ای بدون شاهد مجوز",
                        gaps="مرجع مجوز، علت، مبلغ/ارز، مبدأ و مقصد", basis="Investigation Signal — not fraud finding")

            # تبدیل ارز بدون شواهد کافی
            if bridge is not None and not bridge.empty:
                bz = bridge[(bridge.get("KEY_REG", pd.Series("", index=bridge.index)).map(_s) == reg) &
                            (bridge.get("STATUS", pd.Series("", index=bridge.index)).map(_s) == "CROSS_CURRENCY_EVIDENCE_GAP")]
                if not bz.empty:
                    rule = ctx.rb.get("case_actions.cross_currency_evidence_gap", {}) or {}
                    add(reg, "FX_CONVERSION_EVIDENCE_GAP", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                        "HIGH", "ارز خرید و ارز پرداخت متفاوت است ولی P&L قابل اثبات نیست",
                        gaps="مبلغ مقصد، نرخ ریالی مقصد، Cross Rate، کارمزد", basis="Money Flow evidence rule")

            # Supply position ناقص — به سطح پرونده نگاشت می‌شود ولی Grain منبع Order×Material می‌ماند.
            if dcase is not None and not dcase.empty and "SUPPLY_POSITION_STATUS" in dcase.columns:
                z = dcase[dcase["SUPPLY_POSITION_STATUS"].isin(["PARTIAL", "MISSING", "CONFLICT"])]
                if not z.empty:
                    gaps = " ؛ ".join(sorted({_s(x) for x in z.get("SUPPLY_POSITION_GAPS", pd.Series(dtype=str)) if _s(x)}))
                    rule = ctx.rb.get("case_actions.supply_position_missing", {}) or {}
                    add(reg, "SUPPLY_POSITION_GAP", _s(rule.get("action_fa")), _s(rule.get("owner_role")),
                        "HIGH" if (z["SUPPLY_POSITION_STATUS"] == "CONFLICT").any() else "MEDIUM",
                        f"{len(z)} ردیف Order×Material دارای پوشش ناقص/تعارض موجودی است",
                        gaps=gaps, basis="Expert inventory + Oracle reconciliation")

        if not rows:
            return pd.DataFrame(columns=["ACTION_ID", "KEY_REG", "PRIORITY", "TITLE"])
        out = pd.DataFrame(rows).drop_duplicates(subset=["ACTION_ID"], keep="last")
        # مرتب‌سازی بر رتبه، نه بر رشته: الفبایی «LOW» پیش از «MEDIUM»
        # می‌نشست و صف اقدامی که اپراتور از بالا می‌خواند وارونه می‌شد.
        out = out.assign(_RANK=out["PRIORITY"].map(_rank))
        return (out.sort_values(["KEY_REG", "_RANK", "ACTION_ID"],
                                ascending=[True, False, True])
                   .drop(columns=["_RANK"]).reset_index(drop=True))

    def _empty(self, df: pd.DataFrame) -> None:
        for c in self.provides:
            if c == "CASE_ACTION_COUNT":
                df[c] = 0
            elif c == "NEXT_ACTION_DAYS":
                df[c] = pd.NA
            else:
                df[c] = ""

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("NEXT_ACTION_PRIORITY", "اولویت اقدام بعدی", 15, GROUP_ANALYTIC, order=124),
            ColumnSpec("NEXT_ACTION_TITLE", "پیشنهاد GSI", 54, GROUP_ANALYTIC, wrap=True, order=125),
            ColumnSpec("NEXT_ACTION_OWNER", "مالک پیشنهادی", 24, GROUP_ANALYTIC, order=126),
            ColumnSpec("NEXT_ACTION_DUE_DATE", "موعد داخلی اقدام", 16, GROUP_ANALYTIC, order=127),
            ColumnSpec("NEXT_ACTION_DAYS", "روز تا اقدام", 12, GROUP_ANALYTIC, fmt=FMT_DECIMAL, order=128),
            ColumnSpec("NEXT_ACTION_EVIDENCE_GAPS", "شواهد ناقص اقدام", 48, GROUP_ANALYTIC, wrap=True, order=129),
            ColumnSpec("NEXT_ACTION_RULE_BASIS", "مبنای پیشنهاد", 44, GROUP_ANALYTIC, wrap=True, order=130),
            ColumnSpec("CASE_ACTION_COUNT", "تعداد اقدام باز", 12, GROUP_ANALYTIC, fmt=FMT_DECIMAL, order=131),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        a = ctx.extras.get("case_actions")
        if a is None or a.empty:
            return {"اقدام پیشنهادی باز": (0, "Draft؛ نیازمند بازبینی")}
        return {
            "اقدام پیشنهادی باز": (int(len(a)), "Draft؛ نیازمند بازبینی"),
            "اقدام Critical": (int((a["PRIORITY"] == "CRITICAL").sum()), "Investigation/Deadline"),
            "پرونده دارای پیشنهاد": (int(a["KEY_REG"].nunique()), "قابل Drill-down و ایمیل"),
        }
