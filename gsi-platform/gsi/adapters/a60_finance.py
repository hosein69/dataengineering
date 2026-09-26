# -*- coding: utf-8 -*-
"""سورس‌های مالی و اداری: خرید ارز، اعتبارات، الحاقیه، SAP، اسناد، HR."""
from __future__ import annotations

__contract__ = 1

from typing import Dict
from datetime import datetime, timedelta

import pandas as pd

from ..core.columns import find_col
from ..core.text import clean_employee_code, clean_key, clean_part_no, num_safe
from ..core.jalali import CalendarEngine
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_BL, KEY_ORDER, KEY_PR, KEY_PO, KEY_MATERIAL, KEY_REG, KEY_REG_FILE, SourceAdapter, register


def _reg_key(df: pd.DataFrame, candidates, exclude) -> pd.Series:
    col = find_col(df, candidates, exclude=exclude)
    return df[col].map(clean_key) if col is not None else ""


@register
class FxTransactionAdapter(SourceAdapter):
    """خرید ارز — هدرهای واقعی Sheet1 (۱۸ ستون)."""
    key, prefix = "fx_transaction", "FX"

    COLUMN_MAP = {
        "BUY_DATE":       ["تاریخ خرید", "تاریخ خرید ارز"],
        "BENEFICIARY":    ["نام ذینفع"],
        "GOODS_DESC":     ["شرح کالا"],
        "EXCHANGE":       ["نام صرافي", "نام صرافی"],
        "BANK":           ["نام بانک"],
        "AMOUNT":         ["ارز خریداری شده", "مبلغ خرید ارز"],
        "CURRENCY":       ["نوع ارز خریداری شده", "نوع ارز"],
        "RATE":           ["نرخ ارز خریداری شده", "نرخ ارز"],
        "EUR_VALUE":      ["معادل یورویی خرید ارز", "معادل یورویی"],
        "RIAL_VALUE":     ["مبلغ ریالی"],
        "STATUS":         ["وضعیت"],
        "ALLOC_VALIDITY": ["اعتبارتخصیص", "اعتبار تخصیص"],
        "BENEF_CONFIRM":  ["تاييد ذينفع", "تایید ذینفع"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        from ..warehouse.numeric import number
        num_safe = number
        if len(sheets) > 1:
            parts = [self.transform({name: frame}) for name, frame in sheets.items()]
            return {key: pd.concat([part[key] for part in parts if key in part], ignore_index=True, sort=False)
                    for key in {key for part in parts for key in part}}
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        from ..warehouse.excel import header_normal
        lookup={header_normal(col):col for col in df.columns}
        out=pd.DataFrame(index=df.index)
        selected_cols = {}
        for target,candidates in self.COLUMN_MAP.items():
            col=next((lookup[header_normal(alias)] for alias in candidates if header_normal(alias) in lookup),None)
            selected_cols[target] = col
            out[p(target)]=df[col] if col is not None else None
        out[p("CURRENCY")] = out[p("CURRENCY")].map(get_rulebook().normalize_currency)
        # Profiles 30/31 explicitly distinguish a purchase plan from a purchase.
        out[p("PURCHASE_STATE")] = out[p("STATUS")].map(
            lambda value: "PLANNED" if header_normal(value).replace(" ", "") == "دربرنامهخرید" else "SOURCE_OBSERVED")
        for f in ("AMOUNT", "RATE", "EUR_VALUE", "RIAL_VALUE"):
            out[p(f)] = out[p(f)].map(num_safe)
        out[KEY_REG] = _reg_key(df, ["ثبت سفارش", "کد ثبت سفارش"],
                                ["پرونده", "تاریخ", "ارزش"])
        self.add_order_key(out, df, ["سفارش", "شماره سفارش"])
        # V26.18 — لینک اختیاری بارنامه و شواهد تبدیل/باز تخصیص. این فیلدها
        # اختیاری‌اند و نبودشان خطا نیست؛ وقتی فایل مالی آن‌ها را داشته باشد
        # Money Flow Control Tower می‌تواند تبدیل ارز و جابه‌جایی بین پرونده‌ها
        # را با شاهد مستقیم تحلیل کند.
        self.add_bl_key(out, df, ["شماره بارنامه", "بارنامه", "BL", "B/L", "AWB"])

        def opt(target, candidates, numeric=False):
            col = find_col(df, candidates, exclude=["توضیح کلی"])
            if col is None:
                out[p(target)] = float("nan") if numeric else ""
            else:
                out[p(target)] = df[col].map(num_safe) if numeric else df[col]

        opt("PAID_AMOUNT", ["مبلغ پرداختی به ذینفع", "مبلغ پرداخت به ذینفع", "Supplier Paid Amount", "Paid Amount"], True)
        opt("PAID_CURRENCY", ["ارز پرداختی به ذینفع", "ارز پرداخت به ذینفع", "Supplier Currency", "Paid Currency"])
        opt("PAID_RATE_RIAL", ["نرخ ریالی ارز پرداختی", "نرخ پرداخت به ذینفع", "Paid FX Rate", "Supplier FX Rate"], True)
        opt("CONVERSION_RATE", ["نرخ تبدیل ارز", "Conversion Rate", "Cross Rate"], True)
        opt("CONVERSION_FEE_RIAL", ["کارمزد تبدیل ارز", "Conversion Fee", "FX Conversion Fee"], True)
        opt("ORIGINAL_REG", ["ثبت سفارش مبدا", "ثبت سفارش اولیه", "Original Registration", "Source REG"])
        opt("TARGET_REG", ["ثبت سفارش مقصد", "Target Registration", "Destination REG"])
        opt("ORIGINAL_ORDER", ["سفارش مبدا", "Original Order", "Source Order"])
        opt("TARGET_ORDER", ["سفارش مقصد", "Target Order", "Destination Order"])
        opt("ORIGINAL_BL", ["بارنامه مبدا", "Original BL", "Source BL"])
        opt("TARGET_BL", ["بارنامه مقصد", "Target BL", "Destination BL"])
        opt("REALLOC_REASON", ["علت جابجایی", "علت جابه جایی", "Reallocation Reason", "Transfer Reason"])
        opt("AUTH_REF", ["شماره مجوز", "مجوز انتقال", "مرجع تایید", "Authorization Ref", "Approval Ref"])
        opt("NOTE", ["ملاحظات", "توضیحات", "شرح", "Note", "Remark"])
        out[p("PAID_CURRENCY")] = out[p("PAID_CURRENCY")].map(get_rulebook().normalize_currency)
        for fld in ("ORIGINAL_REG", "TARGET_REG"):
            out[p(fld)] = out[p(fld)].map(clean_key)
        for fld in ("ORIGINAL_ORDER", "TARGET_ORDER"):
            out[p(fld)] = out[p(fld)].map(clean_key)

        # Profiles 30/31: repeated currency header has different meanings.
        # In the current-year layout it is SWIFT currency; in Sheet1 it is
        # payment method (e.g. حواله), so never bind it globally.
        def exact(aliases):
            col = next((lookup[header_normal(a)] for a in aliases if header_normal(a) in lookup), None)
            return df[col] if col is not None else None
        out[p("PROFORMA_AMOUNT")] = exact(["مبلغ ارز پروفرم"])
        out[p("PROFORMA_CURRENCY")] = exact(["نوع ارز"]) if header_normal("مبلغ ارز پروفرم") in lookup else None
        out[p("SWIFT_AMOUNT")] = exact(["ارز سوئیفت", "ارز سوئيفت"])
        swift_layout = any(header_normal(a) in lookup for a in ["ارز سوئیفت", "ارز سوئيفت"])
        out[p("SWIFT_CURRENCY")] = exact(["نوع ارز__2", "نوع ارز.1"]) if swift_layout else None
        out[p("SWIFT_DATE")] = exact(["تاریخ سوئیفت", "تاريخ سوئيفت"])
        out[p("RECEIPT_DATE")] = exact(["تاریخ تایید وصول", "تاريخ تائيد وصول"])
        for field in ("PROFORMA_AMOUNT", "SWIFT_AMOUNT"):
            out[p(field)] = out[p(field)].map(num_safe)
        for field in ("PROFORMA_CURRENCY", "SWIFT_CURRENCY"):
            out[p(field)] = out[p(field)].map(get_rulebook().normalize_currency)
        for col in ('_SOURCE_ROW','_SOURCE_SHEET','_SOURCE_FILE_ID'):
            if col in df: out[col] = df[col]
        from ..warehouse.store import Warehouse
        # Rows without a business key or with an unusable purchase amount are
        # quarantined, not allowed to poison the whole publication.  This is
        # deliberately conservative: quarantined rows stay recoverable in the
        # warehouse but do not count as FX purchase evidence or enter sums.
        orphan=out[KEY_REG].fillna('').eq('') & out[KEY_ORDER].fillna('').eq('')
        quarantine_parts = []
        if orphan.any():
            q = df.loc[orphan].copy()
            q['_QUARANTINE_REASON'] = 'NO_ORDER_OR_REG'
            quarantine_parts.append(q)
            Warehouse().issue('FX_ORPHAN_ROWS',{
                'rows':q.get('_SOURCE_ROW',q.index.to_series()).tolist(),
                'count':int(orphan.sum()),
                'reason':'no order or registration identifier; excluded from financial sums'})
            out=out.loc[~orphan].copy()

        amount_col = selected_cols.get('AMOUNT')
        bad = out[p('AMOUNT')].isna()
        if bad.any():
            bad_idx = out.index[bad]
            q = df.loc[bad_idx].copy()
            q['_QUARANTINE_REASON'] = 'INVALID_PURCHASE_AMOUNT'
            if amount_col is not None and amount_col in q.columns:
                q['_RAW_FX_AMOUNT'] = q[amount_col]
                samples = [str(x) for x in q[amount_col].dropna().astype(str).head(10).tolist()]
            else:
                q['_RAW_FX_AMOUNT'] = None
                samples = []
            quarantine_parts.append(q)
            rows = q.get('_SOURCE_ROW',q.index.to_series()).tolist()
            Warehouse().issue('FX_INVALID_PURCHASE_AMOUNT', {
                'rows':rows,
                'count':int(bad.sum()),
                'raw_samples':samples,
                'reason':'invalid/missing purchase amount; row quarantined and excluded from financial sums'})
            log.warning(
                f"   ⚠️ [fx] {int(bad.sum())} ردیف با مبلغ خرید ارز نامعتبر/خالی "
                "قرنطینه شد؛ داده خام محفوظ است و این ردیف‌ها وارد جمع‌های مالی نمی‌شوند.")
            out=out.loc[~bad].copy()

        quarantine = (pd.concat(quarantine_parts, ignore_index=False, sort=False)
                      if quarantine_parts else df.iloc[0:0].copy())

        rates = out[[p("CURRENCY"), p("RATE")]].rename(
            columns={p("CURRENCY"): "CURRENCY", p("RATE"): "RATE"})
        rates = rates[(rates["CURRENCY"] != "") & (rates["RATE"] > 0)]
        rates = rates.groupby("CURRENCY", as_index=False)["RATE"].median()
        log.info(f"   💱 [fx] {len(rates)} ارز، "
                 f"{int(out[KEY_REG].astype(str).ne('').sum())} ردیف با کد ثبت سفارش")
        return {"main": out, "rates": rates, "quarantine": quarantine}


@register
class CreditAdapter(SourceAdapter):
    """اعتبارات اسنادی — شیت PURCREDIT (۳۷ ستون)."""
    key, prefix = "credit", "CRD"

    COLUMN_MAP = {
        "CUSTOMER":     ["مشتری"],
        "OPEN_YEAR":    ["سال گشايش", "سال گشایش"],
        "CARGO_DESC":   ["شرح محموله"],
        "DEPARTMENT":   ["اداره"],
        "EXPERT":       ["کارشناس اعتبارات"],
        # ⚠️ ستون جداگانه کارشناس خرید. تا نسخه ۲۶٫۵ خوانده نمی‌شد و
        # resolver ناچار نام کارشناس ترخیص را جای خرید می‌نشاند.
        "BUYER":        ["کارشناس خرید خارجی", "کارشناس خريد خارجي"],
        "SUPPLIER":     ["نام تامین کننده"],
        "PAYMENT_TYPE": ["نوع پرداخت"],
        "BANK_BRANCH":  ["بانك عامل شعبه", "بانک عامل شعبه"],
        "PROFORMA_VALUE": ["ارزش پروفرم"],
        "CURRENCY":     ["نوع ارز"],
        "EUR_AMOUNT":   ["مبلغ به یورو"],
        "RIAL_AMOUNT":  ["مبلغ به ریال"],
        "OPEN_PCT":     ["درصد گشايش", "درصد گشایش"],
        "PREPAYMENT":   ["پیش پرداخت اعتبار"],
        "REMAINING":    ["اعتبار باقیمانده"],
        "REG_DATE":     ["تاریخ ثبت سفارش"],
        "LC_NO":        ["شماره اعتبار/حواله", "شماره اعتبار"],
        "LAST_STATUS":  ["آخرین وضعیت"],
        "FUND_DATE":    ["تاریخ تامین وجه"],
        "SWIFT_DATE":   ["تاریخ دریافت سوئیفت"],
        "SWIFT_AMOUNT": ["مبلغ دریافت سوئیفت"],
        "SWIFT_CURRENCY": ["نوع ارز6"],
        "ALLOC_AMOUNT": ["مبلغ تخصیص ارز"],
        "ALLOC_CURRENCY": ["نوع ارز5"],
        "NOTE":         ["ملاحظات"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        # Currency fields are semantically distinct. Fuzzy header matching must
        # never promote event-specific نوع ارز5/6 into the LC/native currency.
        from ..warehouse.excel import header_normal
        exact = {header_normal(c): c for c in df.columns}
        native_col = exact.get(header_normal("نوع ارز"))
        out[p("CURRENCY")] = (df[native_col] if native_col is not None else pd.Series("", index=df.index)).map(get_rulebook().normalize_currency)
        for raw_name, target in (("نوع ارز5", "ALLOC_CURRENCY"), ("نوع ارز6", "SWIFT_CURRENCY")):
            raw_col = exact.get(header_normal(raw_name))
            if raw_col is not None:
                out[p(target)] = df[raw_col]
        # Preserve physical source lineage unchanged for replay/audit.
        for lineage in ("_SOURCE_ROW", "_SOURCE_FILE_ID", "_SOURCE_SHEET"):
            if lineage in df.columns:
                out[lineage] = df[lineage].copy()
        from ..warehouse.numeric import number
        for f in ("PROFORMA_VALUE", "EUR_AMOUNT", "RIAL_AMOUNT", "PREPAYMENT", "REMAINING", "SWIFT_AMOUNT", "ALLOC_AMOUNT"):
            out[p(f)] = out[p(f)].map(number)
        for f in ("SWIFT_CURRENCY", "ALLOC_CURRENCY"):
            out[p(f)] = out[p(f)].map(get_rulebook().normalize_currency)
        out[KEY_REG] = _reg_key(df, ["شماره ثبت سفارش", "کد ثبت سفارش"],
                                ["تاریخ", "پرونده"])
        self.add_order_key(out, df, ["شماره سفارش"])
        return {"main": out}


@register
class IlAppendAdapter(SourceAdapter):
    """الحاقیه ثبت سفارش — شیت Append (۸۷ ستون، بیشترشان خالی).

    ⚠️ تفکیک حیاتی: «شماره ثبت سفارش» (۸ رقمی، کلید NTSW) با
    «شماره پرونده ثبت سفارش» (۹ رقمی) یکی نیست. نسخه قبل دومی را کلید گرفته
    بود و کل زنجیره تعهد ارزی قطع شده بود.
    """
    key, prefix = "ilappend", "IL"

    COLUMN_MAP = {
        "STATUS":       ["وضعیت"],
        "AMENDMENT_NO": ["شماره اصلاحیه"],
        "AMENDMENT_DATE": ["تاریخ درخواست اصلاحیه"],
        "APPROVAL_DATE": ["تاریخ تایید دستگاه مجوز دهنده"],
        "REQUEST_TYPE": ["نوع درخواست"],
        "COMPANY":      ["نام شرکت"],
        "FILE_NO":      ["شماره پرونده ثبت سفارش"],
        "REG_DATE":     ["تاریخ صدور ثبت سفارش"],
        # کارشناس ثبت سفارش — نقش مستقل، نه «کارشناس» عمومی.
        "EXPERT":       ["نام کارشناس", "کارشناس ثبت سفارش"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        out[KEY_REG_FILE] = out[self.p("FILE_NO")].map(clean_key)
        col = find_col(df, ["شماره ثبت سفارش"],
                       exclude=["پرونده", "تاریخ", "ارزش", "حالت", "کارمزد", "تغییر"])
        out[KEY_REG] = df[col].map(clean_key) if col is not None else ""
        self.add_order_key(out, df, ["شماره سفارش"])
        log.info(f"   🔑 [il] کلید ثبت سفارش از ستون «{col}» "
                 f"({int(out[KEY_REG].astype(str).ne('').sum())} ردیف)")
        return {"main": out}


@register
class SapAdapter(SourceAdapter):
    """SAP Procurement — evidence-preserving multi-grain adapter.

    V29.7.6 accepts the completed SAP export where one physical row can carry
    PR-item, package/workflow and PO-item attributes at the same time.  Those
    are *different business grains* and must never be treated as one fact.

    Frames:
      raw_rows      one standardized row per source row (lineage / replay)
      pr_items      current PR-item snapshot (PR × PR item)
      workflow_rows workflow/package evidence, history-preserving
      po_items      current purchasing-document item (PO × PO item)
      main          compatibility projection: one latest row per PR
    """
    key, prefix = "sap", "SAP"

    COLUMN_MAP = {
        # PR item
        "DOC_TYPE": ["Document Type"],
        # Legacy workflow export columns remain accepted for backward compatibility.
        "STATUS_ID": ["Status ID"],
        "NOTIFICATION": ["Notification"],
        "WORKFLOW_STATUS": ["WorkFlow Status"],
        "PR_STATUS_TEXT": ["PR Status Text"],
        "TASK_STATUS": ["Tasks Status"],
        "ACTION": ["Action"],
        "CHANGED_BY": ["Changed By"],
        "PR_ITEM": ["Item of requisition"],
        "MATERIAL": ["Material"],
        "MATERIAL_DESC": ["Material Description"],
        "SHORT_TEXT": ["Short Text"],
        "REQ_QTY": ["Quantity requested"],
        "UOM": ["Unit of Measure"],
        "MATERIAL_GROUP": ["Material Group"],
        "PURCH_GROUP": ["Purchasing Group"],
        "PURCH_GROUP_DESC": ["Purgroup Description"],
        "REQUISITIONER": ["Requisitioner"],
        "REQUISITION_DATE": ["Requisition date"],
        "CREATED_BY": ["Created By"],
        "CHANGED_ON": ["Changed On"],
        "RELEASE_DATE": ["Release Date"],
        "DELIVERY_FROM_TO": ["Deliv. date(From/to)"],
        "HEADER_PURCHASE_ORDER": ["Purchase order"],
        "QTY_ORDERED": ["Quantity ordered"],
        "SUPPLIER_NAME": ["Name of Supplier"],
        "DELETION_IND": ["Deletion Indicator"],
        "PROCESSING_STATUS": ["Processing status"],
        "ITEM_CATEGORY": ["Item Category"],
        "ACCT_ASSIGNMENT_CAT": ["Acct Assignment Cat."],
        "PURCH_ORG": ["Purch. Organization"],
        "SUPPLIER_MATERIAL": ["Supplier Mat. No."],
        "PLANT": ["Plant"],
        "GOODS_RECEIPT": ["Goods Receipt"],
        "DELIVERY_DATE_CATEGORY": ["Deliv. date category"],
        "DELIVERY_DATE": ["Delivery Date"],
        "PR_TYPE": ["PR Type"],
        "REQ_TRACKING_NO": ["Req. Tracking Number"],
        "GR_NON_VALUATED": ["GR Non-Valuated"],
        "TOTAL_VALUE": ["Total Value"],
        "CURRENCY": ["Currency"],
        "OVERALL_RELEASE": ["Overall release of requisitions"],
        "MFR_PART_PROFILE": ["Mfr Part Profile"],
        "LANGUAGE": ["Language Key"],
        "GR_PROCESSING_TIME": ["GR processing time"],
        "VALUATION_PRICE": ["Valuation Price"],
        "PURCHASE_ORDER_ITEM": ["Purchase Order Item"],
        "PURCHASE_ORDER_DATE": ["Purchase Order Date"],
        "PRICE_UNIT": ["Price Unit"],
        "MANUFACTURER": ["Manufacturer"],
        "FRAMEWORK_ORDER_ITEM": ["Framework order item"],
        "DESIRED_VENDOR": ["Desired Vendor"],
        "RELEASE_STRATEGY": ["Release strategy"],

        # Package / workflow
        "PACK_NO": ["pack.Pack Number"],
        "PACK_PR": ["pack.Purchase Requisition"],
        "PACK_PR_ITEM": ["pack.Item of requisition"],
        "PACK_QTY": ["pack.Quantity"],
        "PACK_ORDER_UNIT": ["pack.Order Unit"],
        "PACK_ORDER_NO": ["pack.order Num"],
        "PACK_RESPONSIBLE": ["pack.Responsible"],
        "PACK_PACKED": ["pack.Packed"],
        "WORKFLOW_ID": ["pack.WorkFlow ID", "WorkFlow ID"],
        "COMPARISON_ID": ["pack.Comparision ID", "Comparision ID", "Comparison ID"],
        "COMMISSION_NO": ["pack.Commision No", "Commision No", "Commission No"],
        "COMMISSION_DATE": ["pack.Commision Date", "Commision Date", "Commission Date"],
        "PACK_MATERIAL": ["pack.Material"],
        "PACK_MPN_MATERIAL": ["pack.MPN: Material"],

        # PO item
        "PO_ITEM": ["po.Item"],
        "PO_DOCUMENT_ITEM": ["po.Document Item"],
        "PO_DELETION_IND": ["po.Deletion Indicator"],
        "PO_LAST_CHANGED": ["po.Last Changed on"],
        "PO_SHORT_TEXT": ["po.Short Text"],
        "PO_MATERIAL": ["po.Material"],
        "PO_COMPANY_CODE": ["po.Company Code"],
        "PO_PLANT": ["po.Plant"],
        "PO_STORAGE_LOCATION": ["po.Storage Location"],
        "PO_REQ_TRACKING_NO": ["po.Req. Tracking Number"],
        "PO_MATERIAL_GROUP": ["po.Material Group"],
        "PO_INFO_REC": ["po.Purchasing Info Rec."],
        "PO_SUPPLIER_MATERIAL": ["po.Supplier Mat. No."],
        "PO_TARGET_QTY": ["po.Target Quantity"],
        "PO_ORDER_UNIT": ["po.Order Unit"],
        "PO_ORDER_QTY": ["po.Order Quantity"],
        "PO_ORDER_PRICE_UNIT": ["po.Order Price Unit"],
        "PO_QTY_CONVERSION": ["po.Quantity Conversion"],
        "PO_DENOMINATOR": ["po.Denominator"],
        "PO_NET_PRICE": ["po.Net Order Price"],
        "PO_CURRENCY": ["po.Currency"],
        "PO_PRICE_UNIT": ["po.Price Unit"],
        "PO_NET_VALUE": ["po.Net Order Value"],
        "PO_GROSS_VALUE": ["po.Gross order value"],
        "PO_DELIVERY_COMPLETED": ["po.Delivery Completed"],
        "PO_RFQ": ["po.RFQ"],
        "PO_PR": ["po.Purchase Requisition"],
        "PO_PR_ITEM": ["po.Item of requisition"],
        "PO_MFR_PART_NO": ["po.Manufacturer Part No."],
        "PO_DOC_TYPE": ["po.Purchasing Doc. Type"],
        "PO_SUPPLIER": ["po.Supplier"],
        "PO_DOCUMENT_DATE": ["po.Document Date"],
        "PO_CREATED_BY": ["po.Created By"],
        "PO_REG_FILE": ["po.شماره پرونده"],
        "PO_YOUR_REFERENCE": ["po.Your Reference"],
        "PO_PURCH_ORG": ["po.Purch. Organization"],
        "PO_PURCH_GROUP": ["po.Purchasing Group"],
        "PO_OUR_REFERENCE": ["po.Our Reference"],
    }

    # ── Native multi-sheet export ────────────────────────────────────────
    # The real SAP export separates its grains into sheets instead of prefixing
    # the PO side with "po.". Each sheet maps onto the same standardized names
    # the single-sheet layout produces, so every downstream consumer is unchanged.
    PR_SHEET = "pr"; PO_SHEET = "po"; PACK_SHEET = "pack"
    INBOUND_SHEET = "inbound"; GR_SHEET = "gr"

    PO_SHEET_MAP = {
        "PO_ITEM": ["Item"],
        "PO_DOCUMENT_ITEM": ["Document Item"],
        "PO_DELETION_IND": ["Deletion Indicator"],
        "PO_LAST_CHANGED": ["Last Changed on"],
        "PO_SHORT_TEXT": ["Short Text"],
        "PO_MATERIAL": ["Material"],
        "PO_COMPANY_CODE": ["Company Code"],
        "PO_PLANT": ["Plant"],
        "PO_STORAGE_LOCATION": ["Storage Location"],
        "PO_REQ_TRACKING_NO": ["Req. Tracking Number"],
        "PO_MATERIAL_GROUP": ["Material Group"],
        "PO_INFO_REC": ["Purchasing Info Rec."],
        "PO_SUPPLIER_MATERIAL": ["Supplier Mat. No."],
        "PO_TARGET_QTY": ["Target Quantity"],
        "PO_ORDER_UNIT": ["Order Unit"],
        "PO_ORDER_QTY": ["Order Quantity"],
        "PO_ORDER_PRICE_UNIT": ["Order Price Unit"],
        "PO_QTY_CONVERSION": ["Quantity Conversion"],
        "PO_DENOMINATOR": ["Denominator"],
        "PO_NET_PRICE": ["Net Order Price"],
        "PO_CURRENCY": ["Currency"],
        "PO_PRICE_UNIT": ["Price Unit"],
        "PO_NET_VALUE": ["Net Order Value"],
        "PO_GROSS_VALUE": ["Gross order value"],
        "PO_DELIVERY_COMPLETED": ["Delivery Completed"],
        "PO_RFQ": ["RFQ"],
        "PO_PR": ["Purchase Requisition"],
        "PO_PR_ITEM": ["Item of requisition"],
        "PO_MFR_PART_NO": ["Manufacturer Part No."],
        "PO_DOC_TYPE": ["Purchasing Doc. Type"],
        "PO_SUPPLIER": ["Supplier"],
        "PO_DOCUMENT_DATE": ["Document Date"],
        "PO_CREATED_BY": ["Created By"],
        "PO_REG_FILE": ["شماره پرونده"],
        "PO_YOUR_REFERENCE": ["Your Reference"],
        "PO_PURCH_ORG": ["Purch. Organization"],
        "PO_PURCH_GROUP": ["Purchasing Group"],
        "PO_OUR_REFERENCE": ["Our Reference"],
    }
    PACK_SHEET_MAP = {
        "PACK_NO": ["Pack Number"], "PACK_PR": ["Purchase Requisition"],
        "PACK_PR_ITEM": ["Item of requisition"], "PACK_QTY": ["Quantity"],
        "PACK_ORDER_UNIT": ["Order Unit"], "PACK_ORDER_NO": ["order Num"],
        "PACK_RESPONSIBLE": ["Responsible"], "PACK_PACKED": ["Packed"],
        "WORKFLOW_ID": ["WorkFlow ID"], "COMPARISON_ID": ["Comparision ID", "Comparison ID"],
        "COMMISSION_NO": ["Commision No", "Commission No"],
        "COMMISSION_DATE": ["Commision Date", "Commission Date"],
        "PACK_MATERIAL": ["Material"], "PACK_MPN_MATERIAL": ["MPN: Material"],
    }
    INBOUND_MAP = {
        "IB_DELIVERY": ["Delivery"], "IB_DELIVERY_TYPE": ["Delivery Type"],
        "IB_CREATED_BY": ["Created By"], "IB_CREATED_ON": ["Created On"],
        "IB_ITEM": ["Item"], "IB_MATERIAL": ["Material"], "IB_PLANT": ["Plant"],
        "IB_QTY": ["Delivery Quantity"], "IB_UNIT": ["Sales Unit"],
        "IB_REFERENCE_DOC": ["Reference Document"], "IB_REFERENCE_ITEM": ["Reference Item"],
        "IB_SHIPMENT_NO": ["Shipment Number"], "IB_SUPPLIER": ["Supplier"],
        "IB_SHIPMENT_TYPE": ["Shipment Type"], "IB_SERVICE_AGENT": ["Service Agent"],
    }
    GR_MAP = {
        "GR_POSTING_DATE": ["Posting Date"], "GR_ENTRY_TIME": ["Time of Entry"],
        "GR_USER": ["User Name"], "GR_DOCUMENT_DATE": ["Document Date"],
        "GR_ITEM": ["Item"], "GR_MATERIAL_DOC": ["Material Document"],
        "GR_MATERIAL_DOC_ITEM": ["Material Doc.Item"], "GR_MATERIAL": ["Material"],
        "GR_MATERIAL_DESC": ["Material Description"], "GR_QTY": ["Quantity"],
        "GR_BASE_UNIT": ["Base Unit of Measure"], "GR_PRICE_UNIT": ["Order Price Unit"],
        "GR_MOVEMENT_TYPE": ["Movement Type"], "GR_SUPPLIER": ["Supplier"],
        "GR_BATCH": ["Batch"], "GR_STORAGE_LOCATION": ["Storage Location"],
        "GR_REFERENCE": ["Reference"], "GR_PLANT": ["Plant"],
        "GR_MOVEMENT_REASON": ["Reason for Movement"], "GR_COST_CENTER": ["Cost Center"],
    }
    #: SAP goods movements against a purchase order. A reversal carries the same
    #: quantity with the opposite meaning, so summing quantity without splitting
    #: on movement type counts a reversed receipt twice.
    GR_RECEIPT_TYPES = {"101", "103", "105", "123"}
    GR_REVERSAL_TYPES = {"102", "104", "106", "122"}

    DATE_FIELDS = (
        "REQUISITION_DATE", "CHANGED_ON", "RELEASE_DATE", "DELIVERY_DATE",
        "PURCHASE_ORDER_DATE", "COMMISSION_DATE", "PO_LAST_CHANGED", "PO_DOCUMENT_DATE",
    )
    NUMERIC_FIELDS = (
        "REQ_QTY", "QTY_ORDERED", "TOTAL_VALUE", "VALUATION_PRICE", "PRICE_UNIT",
        "PACK_QTY", "PO_TARGET_QTY", "PO_ORDER_QTY", "PO_NET_PRICE", "PO_PRICE_UNIT",
        "PO_NET_VALUE", "PO_GROSS_VALUE", "GR_PROCESSING_TIME",
    )

    @staticmethod
    def _iso_date(value) -> str:
        """Normalize SAP mixed dates while retaining raw columns separately."""
        if value is None or value is pd.NA:
            return ""
        # Excel serial date: SAP extracts frequently expose these as numbers.
        try:
            if isinstance(value, (int, float)) and not pd.isna(value):
                x = float(value)
                if 20000 <= x <= 80000:
                    return (datetime(1899, 12, 30) + timedelta(days=x)).date().isoformat()
        except Exception:
            pass
        s = str(value).strip()
        if not s or s.lower() in {"nan", "none", "<na>"}:
            return ""
        # Numeric strings may also be Excel serials.
        try:
            x = float(s)
            if s.replace(".", "", 1).isdigit() and 20000 <= x <= 80000:
                return (datetime(1899, 12, 30) + timedelta(days=x)).date().isoformat()
        except Exception:
            pass
        d = CalendarEngine.parse(s)
        return d.isoformat() if d else ""

    @staticmethod
    def _clean_item(value) -> str:
        v = clean_key(value)
        return v.lstrip("0") or ("0" if v else "")

    @staticmethod
    def _sheet(sheets: Dict[str, pd.DataFrame], name: str):
        """Case-insensitive sheet lookup; the export spells GR and gr both ways."""
        for key, df in (sheets or {}).items():
            if str(key).strip().lower() == name and isinstance(df, pd.DataFrame) and not df.empty:
                return df
        return None

    def _native_sheets(self, sheets):
        return {n: self._sheet(sheets, n) for n in
                (self.PR_SHEET, self.PO_SHEET, self.PACK_SHEET,
                 self.INBOUND_SHEET, self.GR_SHEET)}

    def _gr_direction(self, value) -> str:
        code = clean_key(value).lstrip("0") or clean_key(value)
        if code in self.GR_RECEIPT_TYPES:
            return "RECEIPT"
        if code in self.GR_REVERSAL_TYPES:
            return "REVERSAL"
        return "UNCLASSIFIED"

    def _transform_native(self, found: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Build the frames from an export that separates grains into sheets.

        Every frame keeps the standardized names the single-sheet layout produces,
        so business_dwh, the chatbot and the report consume them unchanged. What
        changes is that PR and PO identity can no longer be conflated: they arrive
        from different sheets.
        """
        p = self.p
        out: Dict[str, pd.DataFrame] = {}
        raw_parts = []

        pr_sheet = found.get(self.PR_SHEET)
        if pr_sheet is not None:
            pr = self.std(pr_sheet, self.COLUMN_MAP)
            # A native PR sheet has no authority to manufacture PO/package fields
            # from similarly named unqualified headers such as Material/Currency.
            for target in self.COLUMN_MAP:
                if target.startswith(("PO_", "PACK_")):
                    pr[p(target)] = ""
            pr["SAP_SOURCE_ROW"] = range(1, len(pr) + 1)
            pr["SAP_SOURCE_SHEET"] = self.PR_SHEET
            self.add_pr_key(pr, pr_sheet, ["Purchase Requisition"])
            pr[KEY_PO] = ""
            mcol = find_col(pr_sheet, ["Material"], exclude=["description", "group", "short text"])
            pr[KEY_MATERIAL] = pr_sheet[mcol].map(clean_part_no) if mcol is not None else ""
            pr[KEY_REG_FILE] = ""
            pr["SAP_PR_ITEM"] = pr[p("PR_ITEM")].map(self._clean_item)
            pr["SAP_PO_ITEM"] = ""
            self._normalise(pr)
            pr = pr[pr[KEY_PR].astype(str).str.strip().ne("")].reset_index(drop=True)
            pr["__SORT"] = pr[p("CHANGED_ON_ISO")].where(pr[p("CHANGED_ON_ISO")].ne(""),
                                                         pr[p("RELEASE_DATE_ISO")])
            pr = pr.sort_values([KEY_PR, "SAP_PR_ITEM", "__SORT", "SAP_SOURCE_ROW"], kind="stable")
            out["pr_items"] = (pr.groupby([KEY_PR, "SAP_PR_ITEM"], dropna=False, as_index=False)
                                 .tail(1).drop(columns=["__SORT"], errors="ignore")
                                 .reset_index(drop=True))
            raw_parts.append(pr.drop(columns=["__SORT"], errors="ignore"))

        po_sheet = found.get(self.PO_SHEET)
        if po_sheet is not None:
            po = self.std(po_sheet, self.PO_SHEET_MAP)
            po["SAP_SOURCE_ROW"] = range(1, len(po) + 1)
            po["SAP_SOURCE_SHEET"] = self.PO_SHEET
            self.add_po_key(po, po_sheet, ["Purchasing Document"])
            # PO-side identity only. The PR on this sheet is the PO's own
            # requisition reference, never a header PR borrowed from elsewhere.
            po[KEY_PR] = po[p("PO_PR")].map(clean_key)
            po[KEY_MATERIAL] = po[p("PO_MATERIAL")].map(clean_part_no)
            po[KEY_REG_FILE] = po[p("PO_REG_FILE")].map(clean_key)
            # Evidence profile 2 contains mixed reference semantics, including
            # a 10-digit requisition-like value. Preserve it as a candidate only.
            po["SAP_ORDER_REFERENCE_CANDIDATE"] = po[p("PO_OUR_REFERENCE")].map(clean_key)
            po[KEY_ORDER] = ""
            po["SAP_PO_ITEM"] = po[p("PO_ITEM")].map(self._clean_item)
            po["SAP_PR_ITEM"] = po[p("PO_PR_ITEM")].map(self._clean_item)
            self._normalise(po)
            po = po[po[KEY_PO].astype(str).str.strip().ne("")].reset_index(drop=True)
            po["__SORT"] = po[p("PO_LAST_CHANGED_ISO")].where(
                po[p("PO_LAST_CHANGED_ISO")].ne(""), po[p("PO_DOCUMENT_DATE_ISO")])
            po = po.sort_values([KEY_PO, "SAP_PO_ITEM", "__SORT", "SAP_SOURCE_ROW"], kind="stable")
            out["po_items"] = (po.groupby([KEY_PO, "SAP_PO_ITEM"], dropna=False, as_index=False)
                                 .tail(1).drop(columns=["__SORT"], errors="ignore")
                                 .reset_index(drop=True))
            raw_parts.append(po.drop(columns=["__SORT"], errors="ignore"))

        pack_sheet = found.get(self.PACK_SHEET)
        if pack_sheet is not None:
            pack = self.std(pack_sheet, self.PACK_SHEET_MAP)
            pack["SAP_SOURCE_ROW"] = range(1, len(pack) + 1)
            pack["SAP_SOURCE_SHEET"] = self.PACK_SHEET
            pack[KEY_PR] = pack[p("PACK_PR")].map(clean_key)
            pack["SAP_PR_ITEM"] = pack[p("PACK_PR_ITEM")].map(self._clean_item)
            pack[KEY_PO] = ""
            pack[KEY_MATERIAL] = pack[p("PACK_MATERIAL")].map(clean_part_no)
            pack[KEY_REG_FILE] = ""
            self._normalise(pack)
            pack = pack[pack[KEY_PR].astype(str).str.strip().ne("")].reset_index(drop=True)
            pack["SAP_WORKFLOW_SEQ"] = pack.groupby(KEY_PR).cumcount() + 1
            out["workflow_rows"] = pack
            raw_parts.append(pack)

        inbound_sheet = found.get(self.INBOUND_SHEET)
        if inbound_sheet is not None:
            ib = self.std(inbound_sheet, self.INBOUND_MAP)
            ib["SAP_SOURCE_ROW"] = range(1, len(ib) + 1)
            ib["SAP_SOURCE_SHEET"] = self.INBOUND_SHEET
            ib[KEY_MATERIAL] = ib[p("IB_MATERIAL")].map(clean_part_no)
            # Direct SAP↔bill-of-lading evidence, co-observed on one native row.
            self.add_bl_key(ib, inbound_sheet, ["شماره بارنامه", "Bill of Lading", "BL"])
            ib[KEY_PO] = ib[p("IB_REFERENCE_DOC")].map(clean_key)
            ib["SAP_PO_ITEM"] = ib[p("IB_REFERENCE_ITEM")].map(self._clean_item)
            self._normalise(ib)
            out["inbound_deliveries"] = ib.reset_index(drop=True)
            raw_parts.append(ib)

        gr_sheet = found.get(self.GR_SHEET)
        if gr_sheet is not None:
            gr = self.std(gr_sheet, self.GR_MAP)
            gr["SAP_SOURCE_ROW"] = range(1, len(gr) + 1)
            gr["SAP_SOURCE_SHEET"] = self.GR_SHEET
            self.add_po_key(gr, gr_sheet, ["Purchase order"])
            gr[KEY_MATERIAL] = gr[p("GR_MATERIAL")].map(clean_part_no)
            gr["SAP_PO_ITEM"] = gr[p("GR_ITEM")].map(self._clean_item)
            gr["SAP_GR_DOC_ITEM"] = gr[p("GR_MATERIAL_DOC_ITEM")].map(self._clean_item)
            # A reversal carries the same quantity with the opposite meaning.
            # An unknown movement type yields NaN rather than a guessed sign, so a
            # consumer cannot silently add a movement nobody has classified.
            gr[p("GR_DIRECTION")] = gr[p("GR_MOVEMENT_TYPE")].map(self._gr_direction)
            qty = pd.to_numeric(gr[p("GR_QTY")], errors="coerce")
            sign = gr[p("GR_DIRECTION")].map({"RECEIPT": 1.0, "REVERSAL": -1.0})
            gr[p("GR_SIGNED_QTY")] = qty.abs() * sign
            gr["SAP_GR_PHASE"] = gr[p("GR_MOVEMENT_TYPE")].map(clean_key).map({
                "101": "DIRECT_RECEIPT", "102": "DIRECT_RECEIPT",
                "103": "BLOCKED_RECEIPT", "104": "BLOCKED_RECEIPT",
                "105": "BLOCKED_RELEASE", "106": "BLOCKED_RELEASE",
                "122": "VENDOR_RETURN", "123": "VENDOR_RETURN"}).fillna("UNCLASSIFIED")
            gr[p("GR_QTY")] = qty
            self._normalise(gr)
            out["goods_receipts"] = gr.reset_index(drop=True)
            raw_parts.append(gr)
            unknown = int(gr[p("GR_DIRECTION")].eq("UNCLASSIFIED").sum())
            if unknown:
                log.warning(f"   ⚠️ [sap] {unknown} حرکت کالا با نوع نامشخص؛ مقدار علامت‌دار "
                            "برای آن‌ها NaN ماند و در هیچ جمعی وارد نمی‌شود.")

        if raw_parts:
            out["raw_rows"] = pd.concat(raw_parts, ignore_index=True, sort=False)
        if "pr_items" in out and not out["pr_items"].empty:
            latest = out["pr_items"].copy()
            latest["__SORT"] = latest[p("CHANGED_ON_ISO")].where(
                latest[p("CHANGED_ON_ISO")].ne(""), latest[p("RELEASE_DATE_ISO")])
            latest = latest.sort_values([KEY_PR, "__SORT", "SAP_SOURCE_ROW"], kind="stable")
            out["main"] = (latest.groupby(KEY_PR, as_index=False).tail(1)
                                 .drop(columns=["__SORT"], errors="ignore").reset_index(drop=True))
        elif "po_items" in out:
            out["main"] = out["po_items"].head(0).copy()
        log.info("   ⚙️ [sap] native multi-sheet export — " +
                 " | ".join(f"{k}={len(v)}" for k, v in out.items()))
        return out

    def _normalise(self, frame: pd.DataFrame) -> None:
        """Shared date/number normalisation for every SAP frame."""
        p = self.p
        for f in self.DATE_FIELDS:
            if p(f) in frame:
                frame[p(f + "_ISO")] = frame[p(f)].map(self._iso_date)
        for f in self.NUMERIC_FIELDS:
            if p(f) in frame:
                frame[p(f)] = pd.to_numeric(frame[p(f)], errors="coerce")

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        native = self._native_sheets(sheets)
        if any(v is not None for v in native.values()):
            return self._transform_native(native)
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP)
        out["SAP_SOURCE_ROW"] = range(1, len(out) + 1)

        self.add_pr_key(out, df, ["Purchase Requisition"])
        self.add_po_key(out, df, ["po.Purchasing Document"])
        # Material is the PR material first; PO material is a fallback only.
        mcol = find_col(df, ["Material"], exclude=["description", "group", "pack.", "po."])
        pocol = find_col(df, ["po.Material"])
        if mcol is not None:
            out[KEY_MATERIAL] = df[mcol].map(clean_part_no)
        elif pocol is not None:
            out[KEY_MATERIAL] = df[pocol].map(clean_part_no)
        else:
            out[KEY_MATERIAL] = ""

        # Direct registration-file evidence from PO is valuable but is NOT REG.
        rfcol = find_col(df, ["po.شماره پرونده"])
        out[KEY_REG_FILE] = df[rfcol].map(clean_key) if rfcol is not None else ""

        # Explicit item keys and normalized analytical dates.
        out["SAP_PR_ITEM"] = out[p("PR_ITEM")].map(self._clean_item)
        out["SAP_PO_ITEM"] = out[p("PO_ITEM")].map(self._clean_item)
        for f in self.DATE_FIELDS:
            out[p(f + "_ISO")] = out[p(f)].map(self._iso_date)
        for f in self.NUMERIC_FIELDS:
            out[p(f)] = pd.to_numeric(out[p(f)], errors="coerce")

        # Preserve the standardized source row exactly once for lineage/replay.
        raw_rows = out.reset_index(drop=True).copy()

        # PR-item snapshot. Many PO/package rows may repeat the same PR item; the
        # current fact is one row per PR item, while raw_rows retains all evidence.
        pr = raw_rows[raw_rows[KEY_PR].astype(str).str.strip().ne("")].copy()
        pr["__SORT"] = pr[p("CHANGED_ON_ISO")].where(pr[p("CHANGED_ON_ISO")].ne(""), pr[p("RELEASE_DATE_ISO")])
        pr = pr.sort_values([KEY_PR, "SAP_PR_ITEM", "__SORT", "SAP_SOURCE_ROW"], kind="stable")
        pr_items = pr.groupby([KEY_PR, "SAP_PR_ITEM"], dropna=False, as_index=False).tail(1).drop(columns=["__SORT"], errors="ignore")
        pr_items = pr_items.reset_index(drop=True)
        # PR grain cannot carry one arbitrary PO from a split procurement.
        counts = po_counts = raw_rows.groupby([KEY_PR, "SAP_PR_ITEM"], dropna=False)[KEY_PO].nunique()
        pr_items["SAP_PO_COUNT"] = [int(counts.get((row[KEY_PR], row["SAP_PR_ITEM"]), 0)) for _, row in pr_items.iterrows()]
        for column in [c for c in pr_items if c.startswith("SAP_PO_") and c != "SAP_PO_COUNT"] + [KEY_PO, "SAP_QTY_ORDERED", "SAP_HEADER_PURCHASE_ORDER"]:
            if column in pr_items:
                pr_items.loc[pr_items["SAP_PO_COUNT"].gt(1), column] = pd.NA

        # PO-item current fact. A PR may legitimately feed several purchasing docs.
        po = raw_rows[raw_rows[KEY_PO].astype(str).str.strip().ne("")].copy()
        po["__SORT"] = po[p("PO_LAST_CHANGED_ISO")].where(po[p("PO_LAST_CHANGED_ISO")].ne(""), po[p("PO_DOCUMENT_DATE_ISO")])
        po = po.sort_values([KEY_PO, "SAP_PO_ITEM", "__SORT", "SAP_SOURCE_ROW"], kind="stable")
        po_items = po.groupby([KEY_PO, "SAP_PO_ITEM"], dropna=False, as_index=False).tail(1).drop(columns=["__SORT"], errors="ignore")
        po_items = po_items.reset_index(drop=True)

        # Workflow/package history. Do not collapse status history to the final PR.
        wf = raw_rows.copy()
        wf_key_cols = [p("WORKFLOW_ID"), p("PACK_NO"), p("COMPARISON_ID"), p("COMMISSION_NO"),
                       p("WORKFLOW_STATUS"), p("PR_STATUS_TEXT"), p("TASK_STATUS"), p("ACTION")]
        wf_mask = pd.Series(False, index=wf.index)
        for c in wf_key_cols:
            wf_mask |= wf[c].fillna("").astype(str).str.strip().ne("")
        workflow_rows = wf[wf_mask].copy()
        if workflow_rows.empty:
            # Still retain one PR-item workflow observation when the export has no
            # package columns. This is a coverage fact, not a fabricated workflow.
            workflow_rows = pr_items.copy()
        workflow_rows["SAP_WORKFLOW_SEQ"] = workflow_rows.groupby(KEY_PR).cumcount() + 1
        workflow_rows = workflow_rows.reset_index(drop=True)

        # Compatibility projection: latest evidence per PR; used only by legacy UI.
        latest = pr_items.copy()
        latest["__SORT"] = latest[p("CHANGED_ON_ISO")].where(latest[p("CHANGED_ON_ISO")].ne(""), latest[p("RELEASE_DATE_ISO")])
        latest = latest.sort_values([KEY_PR, "__SORT", "SAP_SOURCE_ROW"], kind="stable")
        latest = latest.groupby(KEY_PR, as_index=False).tail(1).drop(columns=["__SORT"], errors="ignore").reset_index(drop=True)

        log.info(
            f"   ⚙️ [sap] raw={len(raw_rows)} | PR-item={len(pr_items)} | "
            f"workflow={len(workflow_rows)} | PO-item={len(po_items)} | PR={len(latest)}"
        )
        return {
            "main": latest,
            "raw_rows": raw_rows,
            "pr_items": pr_items,
            "workflow_rows": workflow_rows,
            "po_items": po_items,
        }


@register
class DocCheckAdapter(SourceAdapter):
    """بررسی و مغایرت اسناد — شیت Checking.

    ⚠️ دو یافته از HEADERS_MAP که کل این سورس را از خط لوله بیرون انداخته بود:
      ۱ ستون بارنامه پرشدگی **صفر** دارد؛ «Order Number» صد درصد پر است.
        جوین روی بارنامه یعنی حذف کامل ۳۲۱۳ ردیف.
      ۲ نام ستون‌ها انگلیسی است (Status / Date Received / Expert)، نه فارسی.

    کاردینالیتی این فایل «سند» است نه «قلم سفارش»، پس پیش از تحویل به خط
    لوله روی شماره سفارش به آخرین وضعیت تقلیل داده می‌شود؛ وگرنه جوین
    many-to-many ردیف‌های خط لوله را تکثیر می‌کند.
    """
    key, prefix = "doccheck", "DOC"

    COLUMN_MAP = {
        "STATUS":      ["Status", "وضعیت"],
        "SUBMIT_DATE": ["Date Received", "تاریخ دریافت اسناد", "تاریخ ارائه اسناد"],
        "EXPERT":      ["Expert", "کارشناس"],
        "DISCREPANCY": ["Discrepancy", "مغایرت"],
        "DOC_TYPE":    ["Document Type", "نوع سند"],
        "REMARK":      ["Remark", "ملاحظات", "توضیحات"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None or df.empty:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        self.add_order_key(out, df, ["Order Number", "شماره سفارش", "سفارش"])
        self.add_bl_key(out, df, ["BL Number", "بارنامه", "شماره بارنامه"])

        n_bl = int(out[KEY_BL].astype(str).str.strip().ne("").sum())
        n_ord = int(out[KEY_ORDER].astype(str).str.strip().ne("").sum())
        log.info(f"   📑 [doccheck] {len(out)} سند — بارنامه {n_bl} ردیف، "
                 f"سفارش {n_ord} ردیف (کلید ادغام: سفارش)")

        # تقلیل سطح سند → سطح سفارش با نگه‌داشتن آخرین وضعیت
        from ..dataio.merge import dedupe_on_key
        doc_rows = out.copy()
        out = dedupe_on_key(out, KEY_ORDER, keep_by=p("SUBMIT_DATE"),
                            label="doccheck→سفارش")
        return {"main": out, "doc_rows": doc_rows}


@register
class HrAdapter(SourceAdapter):
    """پرسنل — هدرهای واقعی Sheet1 (۲۹ ستون)."""
    key, prefix = "hr", "HR"

    COLUMN_MAP = {
        "FIRST_NAME": ["نام شخص"],
        "LAST_NAME":  ["نام خانوادگی"],
        "FULL_NAME":  ["نام کامل"],
        "EMAIL":      ["Email"],
        "UNIT":       ["نام واحد سازمانی کد ساخت"],
        "VICE":       ["نام معاونت"],
        "DEPT":       ["نام مدیریت", "مدیریت"],
        "POST":       ["شرح پست"],
        "SECTION":    ["بخش"],
        "OFFICE":     ["اداره"],
        "SUPERVISOR": ["مسئول"],
        "HEAD":       ["رئیس"],
        "MANAGER":    ["مدیر"],
        "STATUS":     ["وضعیت"],
        "INACTIVE_DATE": ["تاریخ غیرفعال شدن"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["تاریخ تولد", "سال تولد"])
        self.add_emp_key(out, df, ["شماره پرسنلی", "کد پرسنلی"])
        active = out[p("STATUS")].astype(str).str.contains("فعال", na=False) & \
            ~out[p("STATUS")].astype(str).str.contains("غیرفعال", na=False)
        log.info(f"   👥 [hr] {len(out)} پرسنل — {int(active.sum())} فعال")
        return {"main": out}
