# -*- coding: utf-8 -*-
"""مرحله ۲۰ — ساخت ستون‌های مشتق از سورس‌های ادغام‌شده.

این مرحله «مترجم» است: نام‌های اختصاصی هر سورس (با پیشوند) را به نام‌های
دامنه‌ای تبدیل می‌کند تا مرحله‌های بعدی هرگز به نام ستون یک سورس خاص وابسته
نباشند. افزودن سورس جدید = یک سطر در DERIVED، بدون لمس هیچ موتوری.
"""
from __future__ import annotations

from typing import Any, List

import pandas as pd

from ..adapters.base import KEY_EMP
from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from .base import (ColumnSpec, GROUP_DETAIL, GROUP_MAIN, PipelineContext,
                   Stage, register)

#: {ستون دامنه‌ای: (فهرست کاندیدها به ترتیب اولویت، پیش‌فرض، عددی؟)}
DERIVED = {
    # ── گمرک ──
    "COTAGE_NO":          (["COT_NO"], "", False),
    "SATA_NO":            (["SATA_NO"], "", False),
    "SATA_DATE":          (["SATA_DATE"], "", False),
    "DISCHARGE_DATE":     (["CL_DISCHARGE_DATE"], "", False),
    "ARRIVAL_DATE":       (["CL_ARRIVAL_DATE"], "", False),
    "FULL_CLEAR_DATE":    (["CL_FULL_CLEAR_DATE"], "", False),
    # سامانه جامع انبارها: قبض انبار تا V26.20 در فریم مبدأ می‌ماند و هرگز
    # به فریم اصلی نمی‌رسید، پس آخرین حلقه زنجیره شاهد دیده نمی‌شد.
    "WAREHOUSE_RECEIPT":  (["BL_WAREHOUSE_RECEIPT"], "", False),
    "PARTIAL_CLEAR_DATE": (["CL_PARTIAL_CLEAR_DATE"], "", False),
    "CLEAR_AMOUNT":       (["CL_CLEAR_AMOUNT"], "", False),
    # ── حمل و پرونده ──
    "NTSW_FILE_NO":       (["IL_FILE_NO"], "", False),
    "BL_DATE":            (["BL_BL_DATE"], "", False),
    "SEGMENT":            (["BL_SEGMENT"], "تولیدی", False),
    "PAYMENT_METHOD":     (["SATA_PAYMENT_METHOD"], "", False),
    "BARAT_DUE":          (["SATA_BARAT_DUE"], "", False),
    # ── ارز و تعهد ──
    "BUY_DATE":           (["FX_BUY_DATE"], "", False),
    "CB_DATE":            (["NTSW_COMMIT_DATE", "FX_BUY_DATE"], "", False),
    "CB_VALUE":           (["FX_CB_VALUE", "NTSW_INITIAL_COMMIT", "MOGH_PI_VALUE_SUM"], 0, True),
    "BALANCE":            (["NTSW_BALANCE"], 0, True),
    "DOC_SUBMIT_DATE":    (["DOC_SUBMIT_DATE"], "", False),
    "FIN_RECEIPT_DATE":   (["SATA_DOC_RECEIVED"], "", False),
    "FX_STATUS":          (["FX_STATUS"], "", False),
    "ALLOC_STATUS":       (["NTSW_ALLOC_STATUS"], "", False),
    "ALLOC_REJECTED_F":   (["NTSW_ALLOC_REJECTED"], "", False),
    "CURRENCY":           (["NTSW_CURRENCY", "FX_CURRENCY", "MOGH_CURRENCY"], "", False),
    # ── چرخه خرید (سورس مقاومت) ──
    "ORDER_STAGE":        (["MOGH_STAGE"], "", False),
    "ORDER_STAGE_FA":     (["MOGH_STAGE_FA"], "", False),
    "ORDER_PROGRESS":     (["MOGH_PROGRESS"], 0, True),
    "COMMERCIAL_NOTE":    (["MOGH_COMMERCIAL_NOTE"], "", False),
    "LOGISTICS_NOTE":     (["MOGH_LOGISTICS_NOTE"], "", False),
    "CLEARANCE_HINT":     (["MOGH_CLEARANCE_HINT"], "", False),
    "STAGE_ALERTS":       (["MOGH_ALERTS"], "", False),
    "HS_SUGGESTED":       (["MOGH_HS_SUGGESTED"], "", False),
    "TRANSPORT_MODE":     (["MOGH_TRANSPORT_MODE_CODE", "BL_TRIP_MODE_CODE", "CL_TRANSPORT_MODE_CODE"], "", False),
    "VENDOR_CODE":        (["MOGH_VENDOR_CODE"], "", False),
    "CLEARED_PCT":        (["MOGH_CLEARED_PCT"], 0, True),
    "BL_SUSPECT":         (["MOGH_BL_SUSPECT"], "", False),
    "PO_SENT_DATE":       (["MOGH_PO_SENT_DATE"], "", False),
    # ── موقعیت موجودی کارشناسی — منبع اصلی سه bucket ──
    # عددها عمداً numeric=False هستند تا blank به 0 تبدیل نشود. مرحله
    # supply_position عددی‌سازی، پوشش و reconciliation را انجام می‌دهد.
    "SUPPLIER_QTY":       (["MOGH_SUPPLIER_STOCK_QTY"], "", False),
    "IN_TRANSIT_QTY":     (["MOGH_IN_TRANSIT_QTY"], "", False),
    "IN_CUSTOMS_QTY":     (["MOGH_IN_CUSTOMS_QTY"], "", False),
    "EXPERT_INV_ASOF":    (["MOGH_INVENTORY_ASOF_DATE"], "", False),
    "EXPERT_INV_NOTE":    (["MOGH_INVENTORY_NOTE"], "", False),
    "EXPERT_INV_MISSING": (["MOGH_INVENTORY_MISSING"], "", False),
    "EXPERT_INV_CONFLICT":(["MOGH_INVENTORY_CONFLICT"], "", False),
    "EXPERT_INV_COVERAGE":(["MOGH_INVENTORY_COVERAGE_PCT"], "", False),
    # ── موجودی و نیاز (سورس Oracle) — عمداً بدون پیش‌فرض ۰ ──
    # «۰» یعنی موجودی صفر (توقف خط)، «خالی» یعنی متریال در Oracle نبود.
    "STOCK_IKCO":         (["ORC_STOCK_IKCO"], "", False),
    "STOCK_SAPCO":        (["ORC_STOCK_SAPCO"], "", False),
    "DAILY_NEED":         (["ORC_DAILY_NEED"], "", False),
    "CARS_ON_FLOOR":      (["ORC_CARS_ON_FLOOR"], 0, True),
    "PART_GROUP":         (["ORC_PART_GROUP"], "", False),
    "PART_CLASS":         (["ORC_PART_CLASS"], "", False),
    "SUPPLY_GROUP":       (["ORC_SUPPLY_GROUP"], "", False),
    "FOREIGN_SHARE":      (["ORC_FOREIGN_SHARE"], 0, True),
    "MATERIAL_STATUS":    (["ORC_STATUS"], "", False),
    "MATERIAL_DESC":      (["ORC_MATERIAL_DESC", "MOGH_MATERIAL_DESC"], "", False),
    "BUYER":              (["ORC_BUYER"], "", False),
    # ── منابع انسانی ──
    KEY_EMP:              (["MOGH_KEY_EMP", "ORC_EMP_CODE"], "", False),
    # ── گمرکی ──
    "HS_CODE":            (["CL_HS_CODE"], "", False),
    "CUSTOMS_FILE_NO":    (["CL_FILE_NO"], "", False),
    "CLEAR_EXPERT":       (["CL_EXPERT"], "", False),
    "ENTRY_BORDER":       (["COT_ENTRY_BORDER"], "", False),
    "DEST_CUSTOMS":       (["COT_DEST_CUSTOMS"], "", False),
    "INVOICE_VALUE":      (["CL_INVOICE_VALUE", "SATA_INVOICE_VALUE",
                            "COT_INVOICE_VALUE"], 0, True),
    "EUR_VALUE":          (["CL_EUR_VALUE", "COT_EUR_VALUE", "FX_EUR_VALUE"], 0, True),
    "DUTY_AMOUNT":        (["CL_DUTY_AMOUNT"], 0, True),
    # ── اعتبارات و تخصیص ──
    "CREDIT_STATUS":      (["SATA_CREDIT_STATUS"], "", False),
    "CREDIT_EXPERT":      (["SATA_CREDIT_EXPERT"], "", False),
    "BANK":               (["SATA_BANK", "FX_BANK", "CRD_BANK_BRANCH"], "", False),
    "FX_SOURCE":          (["SATA_FX_SOURCE", "NTSW_FX_SOURCE"], "", False),
    "ALLOC_PROCESS":      (["NTSW_ALLOC_PROCESS"], "", False),
    "ALLOC_DATE":         (["NTSW_ALLOC_DATE"], "", False),
    "ALLOC_REQUESTS":     (["NTSW_ALLOC_REQUESTS"], 0, True),
    "ALLOCATED_REQUESTS": (["NTSW_ALLOCATED_REQUESTS"], 0, True),
    "OPEN_ALLOC_REQUESTS":(["NTSW_OPEN_REQUESTS"], 0, True),
    "REJECTED_ALLOC_REQUESTS":(["NTSW_REJECTED_REQUESTS"], 0, True),
    "ALLOC_QUEUE_STATE":  (["NTSW_QUEUE_STATE"], "", False),
    "ALLOC_QUEUE_ENTER_DATE":(["NTSW_QUEUE_ENTER_DATE"], "", False),
    "ALLOC_QUEUE_RANK":   (["NTSW_QUEUE_RANK"], "", False),
    "ALLOCATED_AMOUNT":   (["NTSW_ALLOCATED_AMOUNT"], 0, True),
    "OPEN_QUEUE_AMOUNT":  (["NTSW_OPEN_QUEUE_AMOUNT"], 0, True),
    "REJECTED_ALLOC_AMOUNT":(["NTSW_REJECTED_AMOUNT"], 0, True),
    "ALLOC_REQUESTED_GROSS":(["NTSW_REQUESTED_GROSS"], 0, True),
    "COMMIT_ROWS":        (["NTSW_COMMIT_ROWS"], 0, True),
    "OPEN_COMMIT_ROWS":   (["NTSW_OPEN_ROWS"], 0, True),
    "LC_STATUS":          (["CRD_LAST_STATUS"], "", False),
    "LC_NO":              (["CRD_LC_NO"], "", False),
    # ── رهگیری مالی-ارزی (V26.16) ──
    "FX_PURCHASE_AMOUNT": (["FX_AMOUNT"], 0, True),
    "FX_RIAL_VALUE":      (["FX_RIAL_VALUE"], 0, True),
    "FX_EUR_VALUE":       (["FX_EUR_VALUE"], 0, True),
    "FX_RATE":            (["FX_RATE"], 0, True),
    "FX_BENEFICIARY":     (["FX_BENEFICIARY"], "", False),
    "FX_EXCHANGE":        (["FX_EXCHANGE"], "", False),
    "FX_ALLOC_VALIDITY":  (["FX_ALLOC_VALIDITY"], "", False),
    "FX_BENEF_CONFIRM":   (["FX_BENEF_CONFIRM"], "", False),
    "CREDIT_PAYMENT_TYPE":(["CRD_PAYMENT_TYPE"], "", False),
    "CREDIT_PROFORMA":    (["CRD_PROFORMA_VALUE"], 0, True),
    "CREDIT_RIAL_AMOUNT": (["CRD_RIAL_AMOUNT"], 0, True),
    "CREDIT_EUR_AMOUNT":  (["CRD_EUR_AMOUNT"], 0, True),
    "CREDIT_PREPAYMENT":  (["CRD_PREPAYMENT"], 0, True),
    "CREDIT_REMAINING":   (["CRD_REMAINING"], 0, True),
    "FUND_DATE":          (["CRD_FUND_DATE"], "", False),
    "SWIFT_DATE":         (["CRD_SWIFT_DATE"], "", False),
    # ── گردش کار SAP ──
    "PR_STATUS":          (["SAP_PR_STATUS_TEXT"], "", False),
    "PR_WORKFLOW":        (["SAP_WORKFLOW_STATUS"], "", False),
}

BOOLS = {
    "ALLOCATED": "NTSW_ALLOCATED",
    "IS_FULL_CLEARED": "CL_IS_FULL",
    "IS_PARTIAL_CLEARED": "CL_IS_PARTIAL",
    "IS_ABANDONED": "COT_IS_ABANDONED",
    "IS_IN_MOGHAVEMAT": "MOGH_PRESENT",
    "IS_BLOCKED": "MOGH_BLOCKING",
    "IS_CANCELLED": "MOGH_EXCLUDED_FROM_KPI",
}


@register
class DeriveStage(Stage):
    name = "derive"
    title = "ترجمه ستون‌های سورس به ستون‌های دامنه‌ای"
    order = 20
    requires = []
    provides = list(DERIVED) + list(BOOLS)

    @staticmethod
    def _inventory_pipeline(df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        """فقط وضعیت لجستیکی را از رویدادها می‌سازد؛ **مقدار موجودی را نه**.

        از V26.20 سه مقدار کمی SUPPLIER_QTY / IN_TRANSIT_QTY / IN_CUSTOMS_QTY
        فقط از سورس کارشناسان می‌آیند. تاریخ تخلیه، BL یا وضعیت حمل می‌تواند
        بگوید محموله «کجاست»، اما حق ندارد مقدار کمی بسازد. این جداسازی
        Unknown را از Zero جدا می‌کند.
        """
        from ..core.text import is_empty_val

        discharged = ~df.get("DISCHARGE_DATE", pd.Series("", index=df.index)).map(
            lambda v: is_empty_val(v, treat_zero_as_empty=False))
        full_clear = df.get("IS_FULL_CLEARED", pd.Series(False, index=df.index)).astype(bool)

        q_transit = pd.to_numeric(df.get("IN_TRANSIT_QTY", pd.Series(index=df.index, dtype=object)),
                                  errors="coerce")
        q_customs = pd.to_numeric(df.get("IN_CUSTOMS_QTY", pd.Series(index=df.index, dtype=object)),
                                  errors="coerce")
        # Presence از عدد کارشناسی اولویت دارد؛ رویداد فقط شاهد مکانی است.
        df["IS_IN_TRANSIT"] = q_transit.gt(0) | ((~discharged) & (~full_clear))
        df["IS_IN_CUSTOMS"] = q_customs.gt(0) | (discharged & (~full_clear))

        missing_any = False
        for c in ("SUPPLIER_QTY", "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY"):
            if c not in df.columns or df[c].map(
                    lambda v: is_empty_val(v, treat_zero_as_empty=False)).all():
                missing_any = True
        ctx.extras["expert_inventory_qty_missing"] = bool(missing_any)
        if missing_any:
            log.warning(
                "⚠️ یکی یا بیشتر از سه bucket کارشناسی «نزد سازنده / در راه / "
                "گمرک» مقدار کمی ندارند؛ مقدار خالی صفر نمی‌شود و مقاومت کل "
                "در مرحله Supply Position با پوشش داده گزارش می‌شود.")
        return df

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        for target, (candidates, default, numeric) in DERIVED.items():
            series = self._first_nonempty(df, candidates, default)
            df[target] = series.map(num_safe) if numeric else series
        for target, src in BOOLS.items():
            # FutureWarning: downcasting در fillna حذف شد
            df[target] = (df[src].astype("object").where(df[src].notna(), False).astype(bool)
                          if src in df.columns else pd.Series(False, index=df.index))

        df = self._inventory_pipeline(df, ctx)

        missing = [t for t, (c, _, _) in DERIVED.items()
                   if not any(x in df.columns for x in c)]
        if missing:
            ctx.extras.setdefault("derive_missing", []).extend(missing)
        return df

    @staticmethod
    def _first_nonempty(df: pd.DataFrame, names: List[str], default: Any) -> pd.Series:
        out = pd.Series([default] * len(df), index=df.index, dtype="object")
        for n in names:
            if n in df.columns:
                need = out.map(is_empty_val)
                out.loc[need] = df[n].loc[need]
        return out

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("DISCHARGE_DATE", "تاریخ تخلیه", 16, GROUP_DETAIL, order=60),
            ColumnSpec("ARRIVAL_DATE", "تاریخ رسیدن", 16, GROUP_DETAIL, order=61),
            ColumnSpec("FULL_CLEAR_DATE", "تاریخ ترخیص کامل", 16, GROUP_DETAIL, order=62),
            ColumnSpec("COTAGE_NO", "شماره کوتاژ", 16, GROUP_DETAIL, order=63),
            ColumnSpec("SATA_NO", "شماره ساتا", 16, GROUP_DETAIL, order=64),
            ColumnSpec("NTSW_FILE_NO", "شماره پرونده NTSW", 18, GROUP_DETAIL, order=65),
            ColumnSpec("ORDER_STAGE_FA", "مرحله سفارش", 22, GROUP_MAIN, order=30),
            ColumnSpec("ORDER_PROGRESS", "پیشرفت سفارش (٪)", 14, GROUP_MAIN,
                       fmt="decimal", order=31),
            ColumnSpec("STAGE_ALERTS", "هشدار مرحله", 40, GROUP_DETAIL, wrap=True, order=66),
            ColumnSpec("BL_SUSPECT", "مقدار مشکوک BL", 20, GROUP_DETAIL, order=67),
        ]
