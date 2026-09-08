# -*- coding: utf-8 -*-
"""سورس مقاومت — ساختار جدید (۳۵ ستون استاندارد انگلیسی).

این سورس دیگر یک لیست ساده بارنامه نیست؛ یک **جدول سطح-قلم** (line level) از
کل چرخه خرید است: PR → PO → PI → حمل → ترخیص. بنابراین:

  • کلید اتصال «Order No. (Our Reference)» است، نه بارنامه.
  • هر سفارش می‌تواند چند ردیف داشته باشد (حمل پارشیالی / چند قلم PR).
    ⇒ adapter دو خروجی می‌دهد:
        lines : جدول کامل سطح-قلم (برای drill-down و شیت جزئیات)
        main  : تجمیع‌شده در سطح سفارش (برای ادغام بدون تکثیر سطر)
  • ستون «BL No.» در نمونه‌های واقعی حاوی شماره فنی سازنده یا شماره پروفرما
    بود (541339، 2036866948، 603111/1، KBL5001350). هر مقدار با
    ``RuleBook.validate_bl`` سنجیده و مقادیر مشکوک به ستون قرنطینه منتقل
    می‌شوند تا کلید بارنامه آلوده نشود.
  • ستون «Additional Data» قالب «وضعیت بازرگانی // وضعیت لجستیک» دارد و با
    واژگان status_lexicon.yaml به مرحله چرخه عمر و درصد پیشرفت تبدیل می‌شود.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from ..core.text import (clean_employee_code, clean_order_ref, clean_part_no,
                         is_empty_val, num_safe, order_ref_base)
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_ORDER, SourceAdapter, register


@register
class MoghavematAdapter(SourceAdapter):
    key, prefix = "moghavemat", "MOGH"

    #: نگاشت ۳۵ ستون رسمی. برای تغییر نام هدر فقط همین دیکشنری را ویرایش کنید.
    COLUMN_MAP: Dict[str, List[str]] = {
        "ROW_NO":            ["Row No."],
        "ORDER_REF":         ["Order No. (Our Reference)", "Order No.", "Our Reference"],
        "PR_NO":             ["PR No."],
        "PR_ITEM":           ["PR Item"],
        "MATERIAL":          ["Material"],
        "MATERIAL_DESC":     ["Material Description"],
        "MATERIAL_SHORT":    ["Material Short Text"],
        "MFR_PART_NO":       ["Manufacturer Part Number"],
        "PR_ITEM":           ["PR Item"],
        "PGR":               ["PGR"],
        "PR_TOTAL_QTY":      ["PR Total Quantity"],
        "UOM":               ["Unit Of Measure"],
        "REF_LETTER_NO":     ["Reference Letter No.", "شماره نامه اتوماسیونی"],
        "DATA_TYPE":         ["Data type"],
        "QTY_IN_ORDER":      ["Quantity In Order"],
        "MFR_VENDOR_CODE":   ["Manufacturer Vendor Code"],
        "MFR_PI_NO":         ["Manufacturer PI Number"],
        "VENDOR_CODE":       ["Vendor Code"],
        "VENDOR_PI_NO":      ["Vendor PI Number"],
        "PI_QTY":            ["PI Quantity"],
        "PI_UNIT_PRICE":     ["PI Unit Price"],
        "CURRENCY":          ["Currency"],
        "PI_LINE_VALUE":     ["PI Line Value"],
        "PI_ADDITIONAL":     ["PI Additional Costs"],
        "PO_SENT_DATE":      ["PO Sent Date", "تاریخ ابلاغ فرم"],
        "PART_NO_PARTIAL":   ["Part No.", "شماره پارت در حمل پارشیالی"],
        "QTY_IN_PART":       ["Quantity In Part"],
        "CLEARED_QTY":       ["Customs Cleared Quantity"],
        "ORDER_STATUS":      ["Order Status"],
        "TRANSPORT_MODE":    ["Mode of Transport"],
        "TRANSPORT_NO":      ["Transport No."],
        "BL_RAW":            ["BL No."],
        "CARRIER":           ["Carrier Name"],
        "SCHEDULED_SHIP":    ["Scheduled Shipment Date"],
        "ADDITIONAL_DATA":   ["Additional Data", "Note , Brand"],
        "EMP_CODE":          ["Employee Code"],
    }

    NUMERIC_FIELDS = ["PR_TOTAL_QTY", "QTY_IN_ORDER", "PI_QTY", "PI_UNIT_PRICE",
                      "PI_LINE_VALUE", "PI_ADDITIONAL", "QTY_IN_PART", "CLEARED_QTY"]

    # ═══════════ تبدیل ═══════════
    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        rb = get_rulebook()

        lines = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        p = self.p

        # ── کلیدها ──
        lines[KEY_ORDER] = lines[p("ORDER_REF")].map(clean_order_ref)
        lines[p("ORDER_BASE")] = lines[p("ORDER_REF")].map(order_ref_base)
        lines[p("KEY_EMP")] = lines[p("EMP_CODE")].map(clean_employee_code)
        lines[p("MFR_PART_NO")] = lines[p("MFR_PART_NO")].map(clean_part_no)

        # ── عددی‌سازی ──
        for f in self.NUMERIC_FIELDS:
            lines[p(f)] = lines[p(f)].map(num_safe)

        # ── ارز ──
        lines[p("CURRENCY")] = lines[p("CURRENCY")].map(rb.normalize_currency)

        # ── اعتبارسنجی بارنامه و قرنطینه مقادیر مشکوک ──
        checks = lines[p("BL_RAW")].map(rb.validate_bl)
        lines[p("BL_VALID")] = [v for v, _ in checks]
        lines[p("BL_REJECT_REASON")] = [r for _, r in checks]
        lines[p("BL_NO")] = [
            str(v).strip().upper() if ok else ""
            for v, ok in zip(lines[p("BL_RAW")], lines[p("BL_VALID")])]
        # مقدار تهی «مشکوک» نیست؛ فقط مقادیر پرشده‌ای که بارنامه نیستند قرنطینه می‌شوند
        lines[p("BL_SUSPECT")] = [
            "" if (ok or is_empty_val(v)) else str(v).strip()
            for v, ok in zip(lines[p("BL_RAW")], lines[p("BL_VALID")])]
        lines[p("BL_REJECT_REASON")] = [
            "" if (ok or is_empty_val(v)) else reason
            for v, ok, reason in zip(lines[p("BL_RAW")], lines[p("BL_VALID")],
                                     lines[p("BL_REJECT_REASON")])]
        n_susp = int((lines[p("BL_SUSPECT")].astype(str).str.strip() != "").sum())
        if n_susp:
            log.warning(
                f"   🚧 [moghavemat] {n_susp} مقدار ستون «BL No.» شماره بارنامه معتبر نبود "
                f"(احتمالاً شماره فنی/پروفرما) و به ستون قرنطینه MOGH_BL_SUSPECT منتقل شد.")

        # ── روش حمل ──
        lines[p("TRANSPORT_MODE_CODE")] = lines[p("TRANSPORT_MODE")].map(rb.transport_mode)

        # ── وضعیت متنی → مرحله چرخه عمر ──
        parsed = [rb.parse_status_note(v) for v in lines[p("ADDITIONAL_DATA")]]
        for field in ("COMMERCIAL_NOTE", "LOGISTICS_NOTE", "STAGE", "STAGE_FA",
                      "PROGRESS", "BLOCKING", "TERMINAL", "EXCLUDED_FROM_KPI",
                      "CLEARANCE_HINT", "ALERTS"):
            lines[p(field)] = [x[field] for x in parsed]

        # ── پیشنهاد کد تعرفه ──
        hs = [rb.infer_hs(d) for d in lines[p("MATERIAL_DESC")]]
        lines[p("HS_SUGGESTED")] = [c for c, _ in hs]
        lines[p("HS_KEYWORD")] = [k for _, k in hs]

        # ── تشخیص قالب فایل (تک‌نوع یا چندنوع Data type) ──
        dtypes = sorted({str(v).strip() for v in lines[p("DATA_TYPE")] if not is_empty_val(v)})
        if len(dtypes) > 1:
            log.info(f"   🧩 [moghavemat] فایل چندنوعی است — Data type: {dtypes}")
        elif dtypes:
            log.info(f"   🧩 [moghavemat] تک‌نوع — Data type: {dtypes[0]}")

        # کلید PR برای اتصال به گردش کار SAP
        from .base import KEY_PR
        from ..core.text import clean_key as _ck
        lines[KEY_PR] = lines[p("PR_NO")].map(_ck)
        lines[p("KEY_PR")] = lines[KEY_PR]   # نسخه پیشوندی، تا در ادغام حذف نشود
        lines[p("PRESENT")] = True
        agg = self._aggregate(lines)
        log.info(f"   📊 [moghavemat] {len(lines)} قلم در {len(agg)} سفارش تجمیع شد.")
        return {"main": agg, "lines": lines}

    # ═══════════ تجمیع سطح سفارش ═══════════
    def _aggregate(self, lines: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        src = lines[lines[KEY_ORDER].astype(str).str.strip() != ""]
        if src.empty:
            return pd.DataFrame(columns=[KEY_ORDER])

        def first_valid(s: pd.Series) -> Any:
            for v in s:
                if not is_empty_val(v):
                    return v
            return ""

        rows: List[Dict[str, Any]] = []
        for order, g in src.groupby(KEY_ORDER, sort=False):
            top = g.loc[g[p("PROGRESS")].astype(float).idxmax()] if len(g) else g.iloc[0]
            rows.append({
                KEY_ORDER: order,
                p("PRESENT"): True,
                p("ORDER_BASE"): first_valid(g[p("ORDER_BASE")]),
                p("LINE_COUNT"): int(len(g)),
                p("PR_NO"): first_valid(g[p("PR_NO")]),
                p("KEY_PR"): first_valid(g[p("KEY_PR")]),
                p("MATERIAL"): first_valid(g[p("MATERIAL")]),
                p("MATERIAL_DESC"): first_valid(g[p("MATERIAL_DESC")]),
                p("MFR_PART_NO"): first_valid(g[p("MFR_PART_NO")]),
                p("VENDOR_CODE"): first_valid(g[p("VENDOR_CODE")]),
                p("VENDOR_PI_NO"): first_valid(g[p("VENDOR_PI_NO")]),
                p("CURRENCY"): first_valid(g[p("CURRENCY")]),
                p("PI_VALUE_SUM"): float(g[p("PI_LINE_VALUE")].sum()),
                p("PI_ADDITIONAL_SUM"): float(g[p("PI_ADDITIONAL")].sum()),
                p("ORDER_QTY_SUM"): float(g[p("QTY_IN_ORDER")].sum()),
                p("PART_QTY_SUM"): float(g[p("QTY_IN_PART")].sum()),
                p("CLEARED_QTY_SUM"): float(g[p("CLEARED_QTY")].sum()),
                p("PO_SENT_DATE"): first_valid(g[p("PO_SENT_DATE")]),
                p("SCHEDULED_SHIP"): first_valid(g[p("SCHEDULED_SHIP")]),
                p("ORDER_STATUS"): first_valid(g[p("ORDER_STATUS")]),
                p("TRANSPORT_MODE_CODE"): first_valid(g[p("TRANSPORT_MODE_CODE")]),
                p("CARRIER"): first_valid(g[p("CARRIER")]),
                p("BL_NO"): first_valid(g[p("BL_NO")]),
                p("BL_SUSPECT"): first_valid(g[p("BL_SUSPECT")]),
                p("KEY_EMP"): first_valid(g[p("KEY_EMP")]),
                p("HS_SUGGESTED"): first_valid(g[p("HS_SUGGESTED")]),
                p("PROGRESS"): float(g[p("PROGRESS")].max()),
                p("STAGE"): top[p("STAGE")],
                p("STAGE_FA"): top[p("STAGE_FA")],
                p("COMMERCIAL_NOTE"): first_valid(g[p("COMMERCIAL_NOTE")]),
                p("LOGISTICS_NOTE"): first_valid(g[p("LOGISTICS_NOTE")]),
                p("BLOCKING"): bool(g[p("BLOCKING")].any()),
                p("TERMINAL"): bool(g[p("TERMINAL")].all()),
                p("EXCLUDED_FROM_KPI"): bool(g[p("EXCLUDED_FROM_KPI")].any()),
                p("CLEARANCE_HINT"): first_valid(g[p("CLEARANCE_HINT")]),
                p("ALERTS"): " ؛ ".join(sorted({a for a in g[p("ALERTS")] if a})),
            })
        out = pd.DataFrame(rows)
        # درصد تکمیل ترخیص در سطح سفارش (بدون تقسیم بر صفر)
        ordered = out[p("ORDER_QTY_SUM")].astype(float)
        cleared = out[p("CLEARED_QTY_SUM")].astype(float)
        out[p("CLEARED_PCT")] = [
            round(c / o * 100, 1) if o > 0 else 0.0 for c, o in zip(cleared, ordered)]
        return out
