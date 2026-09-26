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
from .. import health
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_MATERIAL, KEY_ORDER, SourceAdapter, register


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
        # ── موجودی‌های کارشناسی؛ منبع اصلی Supply Position ──
        # این سه عدد باید توسط کارشناس/فایل کارشناسی ثبت شوند. وضعیت حمل یا
        # تاریخ گمرکی جایگزین مقدار کمی نیست و از روی آن عدد ساخته نمی‌شود.
        "SUPPLIER_STOCK_QTY": [
            "Supplier Stock Qty", "Supplier Inventory", "Qty at Supplier",
            "Quantity at Supplier", "Stock at Supplier", "Vendor Stock",
            "موجودی نزد سازنده", "موجودی سازنده", "موجودی نزد تامین کننده",
            "موجودی نزد تأمین کننده", "موجودی تامین کننده", "نزد سازنده"
        ],
        "IN_TRANSIT_QTY": [
            "In Transit Qty", "Quantity in Transit", "In Transit Inventory",
            "Transit Stock", "موجودی در راه", "تعداد در راه", "در راه"
        ],
        "IN_CUSTOMS_QTY": [
            "In Customs Qty", "Quantity in Customs", "Customs Inventory",
            "Customs Stock", "موجودی گمرک", "موجودی در گمرک", "تعداد در گمرک",
            "نزد گمرک"
        ],
        "INVENTORY_ASOF_DATE": [
            "Inventory As Of Date", "Inventory Update Date", "As Of Date",
            "تاریخ بروزرسانی موجودی", "تاریخ به روز رسانی موجودی", "تاریخ موجودی"
        ],
        "INVENTORY_NOTE": [
            "Inventory Note", "Supply Position Note", "Inventory Comment",
            "توضیحات موجودی", "شرح موجودی", "یادداشت موجودی"
        ],
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
    INVENTORY_NUMERIC_FIELDS = ["SUPPLIER_STOCK_QTY", "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY"]

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
        # دانه موجودی کارشناسی Order × Material است. اگر Material خالی بود،
        # شماره فنی سازنده fallback می‌شود؛ خالی هرگز به «0» تبدیل نمی‌شود.
        material = lines[p("MATERIAL")].map(clean_part_no)
        mfr = lines[p("MFR_PART_NO")].map(clean_part_no)
        lines[KEY_MATERIAL] = material.where(material.astype(str).str.strip().ne(""), mfr)
        lines[p("ORDER_BASE")] = lines[p("ORDER_REF")].map(order_ref_base)
        lines[p("KEY_EMP")] = lines[p("EMP_CODE")].map(clean_employee_code)
        lines[p("MFR_PART_NO")] = lines[p("MFR_PART_NO")].map(clean_part_no)

        # ── عددی‌سازی ──
        for f in self.NUMERIC_FIELDS:
            lines[p(f)] = lines[p(f)].map(num_safe)
        # در موجودی، blank و zero دو معنای کاملاً متفاوت دارند.
        for f in self.INVENTORY_NUMERIC_FIELDS:
            lines[p(f)] = lines[p(f)].map(
                lambda v: "" if is_empty_val(v, treat_zero_as_empty=False) else num_safe(v))

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
        inv = self._aggregate_inventory(lines)
        ompi = self._aggregate_order_material_pr_item(lines)
        log.info(f"   📊 [moghavemat] {len(lines)} قلم در {len(agg)} سفارش تجمیع شد؛ "
                 f"{len(inv)} موقعیت موجودی Order×Material و {len(ompi)} رابطه Order×Material×PR×PR Item ساخته شد.")
        return {"main": agg, "inventory": inv, "order_material_pr_item": ompi, "lines": lines}

    # ═══════════ تجمیع سطح سفارش ═══════════
    @staticmethod
    def _uniq_values(s: pd.Series) -> List[str]:
        """مقادیر یکتا و مرتب، بدون خالی — برای حفظ نسب."""
        seen: List[str] = []
        for v in s:
            if is_empty_val(v):
                continue
            t = str(v).strip()
            if t and t not in seen:
                seen.append(t)
        return sorted(seen)

    def _aggregate_inventory(self, lines: pd.DataFrame) -> pd.DataFrame:
        """جدول موجودی کارشناسی در دانه Order × Material.

        سه bucket کارشناسی منبع اصلی‌اند: نزد سازنده، در راه و گمرک.
        اگر یک bucket در فایل نیامده باشد مقدار آن blank باقی می‌ماند؛ صفر فقط
        وقتی پذیرفته می‌شود که کارشناس صریحاً صفر ثبت کرده باشد. تکرار یک
        snapshot روی چند ردیف با sum دوباره‌شماری نمی‌شود؛ برای هر bucket
        آخرین/اولین مقدار معتبر همان کلید نگه داشته می‌شود و تعارض ثبت می‌گردد.
        """
        p = self.p
        cols = [p(x) for x in self.INVENTORY_NUMERIC_FIELDS]
        # Only these columns are read per Order×Material group. Grouping the full
        # standardized line frame split every mapped column for each key.
        used = [KEY_ORDER, KEY_MATERIAL, *cols, p("INVENTORY_ASOF_DATE"), p("INVENTORY_NOTE"),
                p("QTY_IN_ORDER"), p("QTY_IN_PART"), p("CLEARED_QTY"), p("PART_NO_PARTIAL")]
        lines = lines[[c for c in dict.fromkeys(used) if c in lines.columns]]
        src = lines[(lines[KEY_ORDER].astype(str).str.strip() != "") &
                    (lines[KEY_MATERIAL].astype(str).str.strip() != "")].copy()
        if src.empty:
            return pd.DataFrame(columns=[KEY_ORDER, KEY_MATERIAL] + cols)

        def vals(series):
            out=[]
            for v in series.tolist():
                if is_empty_val(v, treat_zero_as_empty=False):
                    continue
                try: x=float(v)
                except Exception: continue
                if x not in out: out.append(x)
            return out

        rows=[]
        conflict_count=0

        def _max_valid(series):
            vals=[]
            for v in series.tolist():
                if is_empty_val(v, treat_zero_as_empty=False):
                    continue
                try: vals.append(float(v))
                except Exception: continue
            return max(vals) if vals else None

        def _partial_total(group, qty_col):
            """جمع حمل/ترخیص بدون دوباره‌شماری ردیف‌های یک Part No.

            Commercial Expert Data ممکن است یک Part No. را در چند مرحله تکرار کند.
            برای هر Part No. بیشترین مقدار ثبت‌شده گرفته می‌شود و سپس Partها جمع
            می‌شوند. ردیف‌های فاقد Part No. فقط با بیشترین مقدار نمایندگی می‌شوند.
            """
            part_col=p("PART_NO_PARTIAL")
            if qty_col not in group.columns:
                return None
            # Same arithmetic as the former per-group DataFrame pipeline
            # (max per Part No., summed in sorted-key order with pandas; max of
            # unnamed rows) without allocating five intermediate frames per key.
            qty=pd.to_numeric(group[qty_col], errors="coerce").tolist()
            parts=group[part_col].tolist() if part_col in group.columns else [""]*len(qty)
            named={}; unnamed=None
            for part, q in zip(parts, qty):
                if pd.isna(q):
                    continue
                part="" if pd.isna(part) else str(part).strip()
                if part:
                    named[part]=q if part not in named else max(named[part], q)
                else:
                    unnamed=q if unnamed is None else max(unnamed, q)
            if not named and unnamed is None:
                return None
            total=0.0
            if named:
                total += float(pd.Series([named[k] for k in sorted(named)], dtype="float64").sum())
            if unnamed is not None:
                total += float(unnamed)
            return total

        for (order, material), g in src.groupby([KEY_ORDER, KEY_MATERIAL], sort=False):
            row={KEY_ORDER: order, KEY_MATERIAL: material}
            missing=[]; conflicts=[]
            for field in self.INVENTORY_NUMERIC_FIELDS:
                c=p(field); vv=vals(g[c]) if c in g.columns else []
                if not vv:
                    row[c]=""; missing.append(field)
                else:
                    # snapshot quantity: تکرار مقدار یکسان sum نمی‌شود. اگر چند
                    # مقدار متفاوت وجود داشت، آخرین مقدار معتبرِ فایل استفاده و
                    # تعارض برای ممیزی نگه داشته می‌شود.
                    row[c]=vv[-1]
                    if len(vv)>1:
                        conflicts.append(f"{field}:"+"|".join(str(x) for x in vv))
            asof=[v for v in g.get(p("INVENTORY_ASOF_DATE"), pd.Series(dtype=object)).tolist()
                  if not is_empty_val(v, treat_zero_as_empty=False)]
            notes=[str(v).strip() for v in g.get(p("INVENTORY_NOTE"), pd.Series(dtype=object)).tolist()
                   if not is_empty_val(v, treat_zero_as_empty=False)]
            row[p("INVENTORY_ASOF_DATE")]=str(asof[-1]) if asof else ""
            row[p("INVENTORY_NOTE")]=notes[-1] if notes else ""
            row[p("INVENTORY_MISSING")]=", ".join(missing)
            row[p("INVENTORY_CONFLICT")]= " ; ".join(conflicts)
            # ── مشتق عملیاتی از هدر واقعی Commercial Expert Data ──
            # Quantity In Order = مقدار سفارش، Quantity In Part = مقدار ارسال‌شده،
            # Customs Cleared Quantity = مقدار ترخیص‌شده. این مقادیر منبع جایگزین
            # سه bucket صریح‌اند و فقط وقتی ستون مستقیم خالی است استفاده می‌شوند.
            ordered=_max_valid(g[p("QTY_IN_ORDER")]) if p("QTY_IN_ORDER") in g.columns else None
            shipped=_partial_total(g, p("QTY_IN_PART"))
            cleared=_partial_total(g, p("CLEARED_QTY"))
            supplier_derived=(max(ordered-(shipped or 0.0),0.0) if ordered is not None and shipped is not None else None)
            open_shipped=(max((shipped or 0.0)-(cleared or 0.0),0.0) if shipped is not None and cleared is not None else None)
            row[p("SUPPLIER_STOCK_QTY_DERIVED")]=supplier_derived if supplier_derived is not None else ""
            row[p("OPEN_SHIPPED_QTY")]=open_shipped if open_shipped is not None else ""
            row[p("QTY_IN_ORDER_BASIS")]=ordered if ordered is not None else ""
            row[p("QTY_IN_PART_BASIS")]=shipped if shipped is not None else ""
            row[p("CLEARED_QTY_BASIS")]=cleared if cleared is not None else ""
            row[p("INVENTORY_DERIVATION")]=(
                "Supplier=max(Quantity In Order-Quantity In Part,0); "
                "OpenShipped=max(Quantity In Part-Customs Cleared Quantity,0)"
                if ordered is not None or shipped is not None or cleared is not None else "")

            row[p("INVENTORY_COVERAGE_PCT")]=round(100*(3-len(missing))/3,1)
            if conflicts:
                conflict_count += 1
            rows.append(row)
        if conflict_count:
            log.warning(f"⚠️ [moghavemat] {conflict_count} کلید Order×Material چند snapshot موجودی متفاوت دارد؛ آخرین مقدار فایل استفاده و تعارض ثبت شد.")
        return pd.DataFrame(rows)

    def _aggregate_order_material_pr_item(self, lines: pd.DataFrame) -> pd.DataFrame:
        """Bridge evidence at the business relation grain Order×Material×PR×PR Item.

        Supply Position remains Order×Material, but procurement lineage must preserve
        multiple PRs/items for the same order/material. Repeated raw rows are collapsed
        only at this relation grain and retained as evidence_count/source_rows.
        """
        p = self.p
        from .base import KEY_PR
        cols=[KEY_ORDER, KEY_MATERIAL, KEY_PR, p("PR_ITEM"), p("ROW_NO"),
              p("MATERIAL_DESC"), p("MATERIAL_SHORT")]
        have=[c for c in cols if c in lines.columns]
        src=lines[have].copy()
        if src.empty:
            return pd.DataFrame(columns=[KEY_ORDER, KEY_MATERIAL, KEY_PR, p("PR_ITEM"), p("OMPI_KEY"), p("EVIDENCE_COUNT"), p("SOURCE_ROWS")])
        for c in (KEY_ORDER, KEY_MATERIAL, KEY_PR):
            if c not in src.columns: src[c]=""
            src[c]=src[c].fillna("").astype(str).str.strip()
        item=p("PR_ITEM")
        if item not in src.columns: src[item]=""
        def _clean_item(v):
            if is_empty_val(v): return ""
            t=str(v).strip()
            # Excel often turns integer PR Item 20 into 20.0; preserve business identity.
            try:
                f=float(t)
                if f.is_integer(): return str(int(f))
            except Exception:
                pass
            return t
        src[item]=src[item].map(_clean_item)
        src=src[(src[KEY_ORDER]!="") & (src[KEY_MATERIAL]!="") & (src[KEY_PR]!="")].copy()
        if src.empty:
            return pd.DataFrame(columns=[KEY_ORDER, KEY_MATERIAL, KEY_PR, item, p("OMPI_KEY"), p("EVIDENCE_COUNT"), p("SOURCE_ROWS")])
        rows=[]
        for (order, material, pr, pr_item), g in src.groupby([KEY_ORDER, KEY_MATERIAL, KEY_PR, item], sort=False, dropna=False):
            source_rows=[]
            if p("ROW_NO") in g.columns:
                for v in g[p("ROW_NO")].tolist():
                    if is_empty_val(v): continue
                    t=_clean_item(v)
                    if t and t not in source_rows: source_rows.append(t)
            desc=self._uniq_values(g[p("MATERIAL_DESC")]) if p("MATERIAL_DESC") in g.columns else []
            short=self._uniq_values(g[p("MATERIAL_SHORT")]) if p("MATERIAL_SHORT") in g.columns else []
            key=f"{order}|{material}|{pr}|{pr_item or '<BLANK>'}"
            rows.append({
                KEY_ORDER:order, KEY_MATERIAL:material, KEY_PR:pr, item:pr_item,
                p("OMPI_KEY"):key, p("EVIDENCE_COUNT"):int(len(g)),
                p("SOURCE_ROWS"):",".join(source_rows),
                p("MATERIAL_DESC"):"، ".join(desc),
                p("MATERIAL_SHORT"):"، ".join(short),
            })
        return pd.DataFrame(rows)

    def _aggregate(self, lines: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        src = lines[lines[KEY_ORDER].astype(str).str.strip() != ""]
        if src.empty:
            return pd.DataFrame(columns=[KEY_ORDER])

        _uniq = self._uniq_values

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
                p("PR_COUNT"): int(len(_uniq(g[p("KEY_PR")]))),
                p("PRS_ALL"): "، ".join(_uniq(g[p("KEY_PR")])),
                p("PR_ITEMS_ALL"): "، ".join(_uniq(g[p("PR_ITEM")])),
                p("MULTI_PR"): bool(len(_uniq(g[p("KEY_PR")])) > 1),
                p("MATERIAL"): first_valid(g[p("MATERIAL")]),
                p("MATERIAL_DESC"): first_valid(g[p("MATERIAL_DESC")]),
                p("MFR_PART_NO"): first_valid(g[p("MFR_PART_NO")]),
                p("VENDOR_CODE"): first_valid(g[p("VENDOR_CODE")]),
                p("VENDOR_PI_NO"): first_valid(g[p("VENDOR_PI_NO")]),
                p("CURRENCY"): first_valid(g[p("CURRENCY")]),
                p("PI_VALUE_SUM"): (float(g[p("PI_LINE_VALUE")].sum(min_count=len(g))) if g[p("CURRENCY")].fillna("").nunique(dropna=False) == 1 and str(first_valid(g[p("CURRENCY")])).strip() else float("nan")),
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
                # ── نسب متریال ──────────────────────────────────────────
                # سورس در دانه «قلم درخواست» است و اینجا به دانه «سفارش»
                # تجمیع می‌شود. برای متریال از first_valid استفاده می‌شود،
                # یعنی اگر سفارشی پنج قلم داشته باشد جدول اصلی فقط یکی را
                # نمایندگی می‌کند و چهارتای دیگر **بی‌صدا ناپدید می‌شوند**.
                #
                # این نقطه کور واقعیِ داده است، نه یک شرط اشتباه؛ با عوض
                # کردن یک خط حل نمی‌شود چون دانه جدول اصلی سفارش است.
                # کاری که می‌شود و باید کرد این است که نسب حفظ شود و
                # سفارش چندمتریاله صریحاً علامت بخورد، تا هیچ تحلیلی
                # ناخواسته آن را «تک‌متریال» فرض نکند.
                p("MATERIAL_COUNT"): int(_uniq(g[p("MATERIAL")]).__len__()),
                p("MATERIALS_ALL"): "، ".join(_uniq(g[p("MATERIAL")])),
                p("PARTS_ALL"): "، ".join(_uniq(g[p("MFR_PART_NO")])),
                p("MULTI_MATERIAL"): bool(len(_uniq(g[p("MATERIAL")])) > 1),
            })
        out = pd.DataFrame(rows)
        multi = int(out[p("MULTI_MATERIAL")].sum()) if not out.empty else 0
        if multi:
            log.warning(
                f"⚠️ [{self.key}] {multi} سفارش چندمتریاله است. جدول اصلی در دانه "
                f"«سفارش» خلاصه شده و ستون متریال فقط یکی از اقلام را نشان "
                f"می‌دهد؛ فهرست کامل در «{p('MATERIALS_ALL')}» است. تحلیل "
                f"مقاومت مستقلِ هر قلم نیازمند تحلیل در دانه «قلم سفارش» است.")
            health.current().find(
                "دانه‌بندی", health.WARN,
                f"{multi} سفارش چندمتریاله در سورس خرید",
                "جدول اصلی در دانه سفارش است؛ ستون متریال یکی از اقلام را "
                "نمایندگی می‌کند. فهرست کامل اقلام در ستون نسب متریال است.")
        multi_pr = int(out[p("MULTI_PR")].sum()) if not out.empty and p("MULTI_PR") in out.columns else 0
        if multi_pr:
            log.warning(
                f"⚠️ [{self.key}] {multi_pr} سفارش بیش از یک PR دارد. PR اول فقط برای سازگاری legacy نگه داشته شده؛ "
                f"رابطه کامل در {p('PRS_ALL')} و frame مستقل order_material_pr_item حفظ شده است.")
            health.current().find(
                "دانه‌بندی", health.WARN,
                f"{multi_pr} سفارش چند-PR در سورس خرید",
                "هیچ PR حذف نشده است؛ برای تحلیل رابطه از frame Order×Material×PR×PR Item استفاده شود.")

        # درصد تکمیل ترخیص در سطح سفارش (بدون تقسیم بر صفر)
        ordered = out[p("ORDER_QTY_SUM")].astype(float)
        cleared = out[p("CLEARED_QTY_SUM")].astype(float)
        out[p("CLEARED_PCT")] = [
            round(c / o * 100, 1) if o > 0 else 0.0 for c, o in zip(cleared, ordered)]
        return out
