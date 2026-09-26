# -*- coding: utf-8 -*-
"""مرحله ۵۷ — انتقال دانش نسل قدیم به مدل سیستمی.

این مرحله دانش منابع قدیمی را به «راهنمای قابل ممیزی» تبدیل می‌کند، نه قانون
جاری. هیچ deadline، جریمه یا حکم حقوقی از Legacy Pack به‌صورت خودکار enforce
نمی‌شود. خروجی‌ها فقط Root-cause candidate، Evidence requirement، lineage hint
و technical guardrail هستند.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

import pandas as pd

from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from ..knowledge.legacy import LegacyKnowledgeItem, load_legacy_catalog
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, GROUP_DETAIL,
                   PipelineContext, Stage, register)


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> float:
    try:
        return float(num_safe(v) or 0.0)
    except Exception:
        return 0.0


def _join(values: Iterable[str]) -> str:
    out: List[str] = []
    for v in values:
        s = _s(v)
        if s and s not in out:
            out.append(s)
    return " ؛ ".join(out)


@register
class LegacyKnowledgeTransferStage(Stage):
    name = "legacy_knowledge_transfer"
    title = "انتقال دانش تاریخی به Root Cause / Evidence / Provenance"
    order = 57
    tolerant = True
    requires = ["FX_CASE_KEY"]
    provides = [
        "FX_KNOWLEDGE_SIGNAL_COUNT", "FX_ROOT_CAUSE_HINTS",
        "FX_EVIDENCE_REQUIREMENTS", "FX_KNOWLEDGE_PROVENANCE",
        "FX_RATE_SEMANTIC_GAPS", "FX_PAYMENT_WITHOUT_BL_SIGNAL",
        "FX_LEGACY_RULE_GUARD",
    ]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        catalog = load_legacy_catalog(ctx.rb)
        ledger = ctx.extras.get("fx_ledger")
        bridge = ctx.extras.get("fx_rate_bridge")
        realloc = ctx.extras.get("fx_reallocations")
        anomalies = ctx.extras.get("fx_anomalies")

        catalog_df = pd.DataFrame(catalog.rows())
        ctx.extras["legacy_knowledge_catalog"] = catalog_df
        ctx.extras["legacy_rate_semantics"] = pd.DataFrame(catalog.rate_semantics)
        ctx.extras["legacy_antipatterns"] = catalog_df[catalog_df.get("KIND", pd.Series(dtype=str)) == "technical_antipattern"].copy() if not catalog_df.empty else pd.DataFrame()

        if ledger is None or ledger.empty:
            self._empty(df)
            ctx.extras["legacy_case_signals"] = pd.DataFrame()
            return df

        rows: List[Dict[str, Any]] = []
        case_summary: List[Dict[str, Any]] = []
        by_reg = {str(k): g for k, g in df[df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s) != ""].groupby(df.get("CANONICAL_REG").map(_s), sort=False)} if "CANONICAL_REG" in df.columns else {}

        for _, lr in ledger.iterrows():
            reg = _s(lr.get("KEY_REG"))
            if not reg:
                continue
            matched: Dict[str, LegacyKnowledgeItem] = {}
            evidence: List[str] = []
            basis: List[str] = []
            rate_gaps: List[str] = []
            payment_without_bl = False

            # 1) match only from text actually present in this case.
            text_parts: List[str] = [
                _s(lr.get("FX_ANOMALIES")), _s(lr.get("FX_NTSW_RELEASE_STATUS")),
                _s(lr.get("FX_CUSTOMS_DOC_OBLIGATION")), _s(lr.get("FX_DIFFERENTIAL_OBLIGATION")),
            ]
            g = by_reg.get(reg)
            if g is not None and not g.empty:
                note_cols = [c for c in g.columns if any(k in str(c).upper() for k in ("NOTE", "STATUS", "DESC", "شرح", "وضعیت", "یادداشت"))]
                for c in note_cols:
                    text_parts.extend(_s(x) for x in g[c].head(50))
            text = " | ".join(x for x in text_parts if x)
            for item in catalog.match_text(text, kinds=["root_cause"]):
                matched[item.id] = item
                basis.append(f"متن پرونده با الگوی «{item.title}» منطبق شد")

            # 2) structural knowledge from the old OF workbook: Payment without BL.
            has_purchase = (
                _num(lr.get("FX_PURCHASED_AMOUNT")) > 0.01
                or _s(lr.get("FX_PURCHASED_NATIVE_DISPLAY")) not in {"", "—"}
                or _num(lr.get("FX_EUR_EQUIVALENT")) > 0.01
                or _num(lr.get("FX_RIAL_OUTFLOW_REPORTED")) > 0.01
            )
            if has_purchase and _num(lr.get("BL_COUNT")) <= 0:
                item = catalog.get("LEGACY_PAYMENT_WITHOUT_BL")
                if item:
                    matched[item.id] = item
                payment_without_bl = True
                basis.append("خرید ارز/Payment ثبت شده ولی BL قابل اتصال در پرونده دیده نشد")

            # 3) Cross-currency semantics: do not invent P&L when evidence is missing.
            if bridge is not None and not bridge.empty and "KEY_REG" in bridge.columns:
                bz = bridge[bridge["KEY_REG"].map(_s) == reg]
                if not bz.empty and "STATUS" in bz.columns:
                    statuses = set(bz["STATUS"].map(_s))
                    if "CROSS_CURRENCY_EVIDENCE_GAP" in statuses:
                        rate_gaps.append("تبدیل بین دو ارز ثبت شده ولی مبلغ/نرخ مقصد، Cross Rate یا نرخ خرید مبدأ کامل نیست")
                    if "NO_SUPPLIER_PAYMENT_DATA" in statuses:
                        rate_gaps.append("شاهد مبلغ/ارز پرداختی به تأمین‌کننده موجود نیست؛ خرید ارز مساوی پرداخت تلقی نمی‌شود")
                    if "CROSS_CURRENCY_MEASURED" in statuses:
                        basis.append("پل نرخ خرید→تبدیل→پرداخت مقصد دارای شاهد قابل محاسبه است")

            # 4) Reallocation: old FIFO is not authority; evidence of authorization wins.
            if realloc is not None and not realloc.empty:
                rz = realloc[(realloc.get("FROM_REG", pd.Series("", index=realloc.index)).map(_s) == reg) |
                             (realloc.get("TO_REG", pd.Series("", index=realloc.index)).map(_s) == reg)]
                if not rz.empty:
                    unexpl = rz[rz.get("STATUS", pd.Series("", index=rz.index)).map(_s) == "UNEXPLAINED"]
                    if not unexpl.empty:
                        evidence.extend(["شماره/مرجع مجوز جابه‌جایی", "علت جابه‌جایی", "REG/Order/BL مبدأ و مقصد", "مبلغ/ارز منتقل‌شده", "تاریخ تأیید"])
                        basis.append(f"{len(unexpl)} جابه‌جایی بین‌پرونده‌ای بدون شاهد مجوز")

            # 5) Existing anomalies can request the old evidence package, without declaring a cause.
            if anomalies is not None and not anomalies.empty and "KEY_REG" in anomalies.columns:
                az = anomalies[anomalies["KEY_REG"].map(_s) == reg]
                if not az.empty:
                    codes = set(az.get("کد مغایرت", pd.Series(dtype=str)).map(_s))
                    if codes & {"CLEARED_BUT_COMMITMENT_OPEN", "RELEASED_WITH_BALANCE"}:
                        evpack = catalog.get("EVIDENCE_BANK_DOCUMENT_PACKAGE")
                        if evpack:
                            evidence.extend(evpack.evidence_requirements)
                        basis.append("تعهد/مانده بعد از ترخیص یا وضعیت رفع‌شده نیازمند reconciliation سندی است")

            for item in matched.values():
                evidence.extend(item.evidence_requirements)
                rows.append({
                    "KEY_REG": reg, "FX_CASE_KEY": f"REG:{reg}",
                    "SIGNAL_CODE": item.id, "SIGNAL_TYPE": item.kind,
                    "TITLE": item.title, "BASIS": _join(basis),
                    "CONFIDENCE": item.confidence, "BINDING": False,
                    "AUTO_ENFORCE": False, "SOURCE_ID": item.source_id,
                    "SOURCE_LOCATION": item.source_location,
                    "EVIDENCE_REQUIREMENTS": _join(item.evidence_requirements),
                })

            root_titles = [x.title for x in matched.values() if x.kind == "root_cause"]
            signal_count = len(matched) + (1 if rate_gaps else 0)
            case_summary.append({
                "KEY_REG": reg,
                "FX_KNOWLEDGE_SIGNAL_COUNT": signal_count,
                "FX_ROOT_CAUSE_HINTS": _join(root_titles),
                "FX_EVIDENCE_REQUIREMENTS": _join(evidence),
                "FX_KNOWLEDGE_PROVENANCE": "Legacy Knowledge Pack V26.19 — non-binding / fail-closed",
                "FX_RATE_SEMANTIC_GAPS": _join(rate_gaps),
                "FX_PAYMENT_WITHOUT_BL_SIGNAL": "UNALLOCATED_PAYMENT_CANDIDATE" if payment_without_bl else "",
                "FX_LEGACY_RULE_GUARD": "NO_AUTO_ENFORCEMENT",
            })

        sig = pd.DataFrame(rows)
        summary = pd.DataFrame(case_summary)
        ctx.extras["legacy_case_signals"] = sig
        ctx.extras["legacy_case_summary"] = summary

        # enrich case ledger, keeping its one-row-per-REG grain.
        if not summary.empty:
            m = summary.set_index("KEY_REG")
            ledger = ledger.copy()
            for c in self.provides:
                ledger[c] = ledger["KEY_REG"].map(m[c].to_dict())
            ctx.extras["fx_ledger"] = ledger

            regs = df.get("CANONICAL_REG", pd.Series("", index=df.index)).map(_s)
            for c in self.provides:
                df[c] = regs.map(m[c].to_dict())
        else:
            self._empty(df)

        df["FX_KNOWLEDGE_SIGNAL_COUNT"] = pd.to_numeric(df.get("FX_KNOWLEDGE_SIGNAL_COUNT"), errors="coerce").fillna(0)
        for c in set(self.provides) - {"FX_KNOWLEDGE_SIGNAL_COUNT"}:
            df[c] = df.get(c, "").fillna("")

        log.info(f"🧠 [legacy-knowledge] {len(catalog.items)} دانش versioned | "
                 f"{len(summary)} پرونده | {len(sig)} signal | enforce خودکار=0")
        return df

    def _empty(self, df: pd.DataFrame) -> None:
        for c in self.provides:
            df[c] = 0.0 if c == "FX_KNOWLEDGE_SIGNAL_COUNT" else ""

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("FX_KNOWLEDGE_SIGNAL_COUNT", "سیگنال دانش تاریخی", 16,
                       GROUP_ANALYTIC, fmt=FMT_DECIMAL, color_rule="scale_high_bad", order=118),
            ColumnSpec("FX_ROOT_CAUSE_HINTS", "کاندید علت ریشه‌ای", 44,
                       GROUP_ANALYTIC, wrap=True, order=119),
            ColumnSpec("FX_EVIDENCE_REQUIREMENTS", "شواهد پیشنهادی برای بررسی", 58,
                       GROUP_ANALYTIC, wrap=True, order=120),
            ColumnSpec("FX_RATE_SEMANTIC_GAPS", "شکاف معنایی نرخ/تبدیل", 48,
                       GROUP_ANALYTIC, wrap=True, color_rule="flag_nonempty", order=121),
            ColumnSpec("FX_PAYMENT_WITHOUT_BL_SIGNAL", "Payment بدون BL", 24,
                       GROUP_DETAIL, color_rule="flag_nonempty", order=122),
            ColumnSpec("FX_LEGACY_RULE_GUARD", "گارد دانش تاریخی", 24,
                       GROUP_ANALYTIC, order=123),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        sig = ctx.extras.get("legacy_case_signals")
        summary = ctx.extras.get("legacy_case_summary")
        return {
            "پرونده با Signal انتقال دانش": (int(0 if summary is None or summary.empty else (summary["FX_KNOWLEDGE_SIGNAL_COUNT"] > 0).sum()),
                                                "راهنمای بررسی؛ نه حکم حقوقی/تقلب"),
            "Root-cause candidate تاریخی": (int(0 if sig is None or sig.empty else (sig["SIGNAL_TYPE"] == "root_cause").sum()),
                                               "از تجربه قدیمی، با provenance"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"انتقال دانش V26.19": {
            "اصل": "Legacy knowledge is advisory and fail-closed; binding=false by default",
            "ممنوع": "مهلت/جریمه/P&L/تقلب از فایل تاریخی بدون سند جاری enforce نمی‌شود",
            "Root Cause": "فقط candidate بر پایه متن/ساختار پرونده + Evidence Requirements",
            "Payment without BL": "به‌عنوان Unallocated Payment Candidate، نه BL مصنوعی",
            "نرخ": "Static legacy rate فقط برای بازسازی تاریخی؛ P&L نیازمند نرخ/تاریخ واقعی تراکنش است",
        }}
