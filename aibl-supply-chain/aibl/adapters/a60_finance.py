# -*- coding: utf-8 -*-
"""سورس‌های مالی و اداری: خرید ارز، اعتبارات، الحاقیه، SAP، اسناد، HR."""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.columns import find_col
from ..core.text import clean_employee_code, clean_key, num_safe
from ..dataio.logging_setup import log
from ..rulebook import get_rulebook
from .base import KEY_BL, KEY_ORDER, KEY_PR, KEY_REG, SourceAdapter, register


def _reg_key(df: pd.DataFrame, candidates, exclude) -> pd.Series:
    col = find_col(df, candidates, exclude=exclude)
    return df[col].map(clean_key) if col is not None else ""


@register
class FxTransactionAdapter(SourceAdapter):
    """خرید ارز — هدرهای واقعی Sheet1 (۱۸ ستون)."""
    key, prefix = "fx_transaction", "FX"

    COLUMN_MAP = {
        "BUY_DATE":       ["تاریخ خرید ارز"],
        "BENEFICIARY":    ["نام ذینفع"],
        "GOODS_DESC":     ["شرح کالا"],
        "EXCHANGE":       ["نام صرافي", "نام صرافی"],
        "BANK":           ["نام بانک"],
        "AMOUNT":         ["مبلغ خرید ارز"],
        "CURRENCY":       ["نوع ارز"],
        "RATE":           ["نرخ ارز"],
        "EUR_VALUE":      ["معادل یورویی"],
        "RIAL_VALUE":     ["مبلغ ریالی"],
        "STATUS":         ["وضعیت"],
        "ALLOC_VALIDITY": ["اعتبارتخصیص", "اعتبار تخصیص"],
        "BENEF_CONFIRM":  ["تاييد ذينفع", "تایید ذینفع"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        out[p("CURRENCY")] = out[p("CURRENCY")].map(get_rulebook().normalize_currency)
        for f in ("AMOUNT", "RATE", "EUR_VALUE", "RIAL_VALUE"):
            out[p(f)] = out[p(f)].map(num_safe)
        out[KEY_REG] = _reg_key(df, ["ثبت سفارش", "کد ثبت سفارش"],
                                ["پرونده", "تاریخ", "ارزش"])
        self.add_order_key(out, df, ["سفارش", "شماره سفارش"])
        rates = out[[p("CURRENCY"), p("RATE")]].rename(
            columns={p("CURRENCY"): "CURRENCY", p("RATE"): "RATE"})
        rates = rates[(rates["CURRENCY"] != "") & (rates["RATE"] > 0)]
        rates = rates.groupby("CURRENCY", as_index=False)["RATE"].median()
        log.info(f"   💱 [fx] {len(rates)} ارز، "
                 f"{int(out[KEY_REG].astype(str).ne('').sum())} ردیف با کد ثبت سفارش")
        return {"main": out, "rates": rates}


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
        "NOTE":         ["ملاحظات"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        out[p("CURRENCY")] = out[p("CURRENCY")].map(get_rulebook().normalize_currency)
        for f in ("PROFORMA_VALUE", "EUR_AMOUNT", "RIAL_AMOUNT", "PREPAYMENT", "REMAINING"):
            out[p(f)] = out[p(f)].map(num_safe)
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
        "REQUEST_TYPE": ["نوع درخواست"],
        "COMPANY":      ["نام شرکت"],
        "FILE_NO":      ["شماره پرونده ثبت سفارش"],
        "REG_DATE":     ["تاریخ صدور ثبت سفارش"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        out = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
        col = find_col(df, ["شماره ثبت سفارش"],
                       exclude=["پرونده", "تاریخ", "ارزش", "حالت", "کارمزد", "تغییر"])
        out[KEY_REG] = df[col].map(clean_key) if col is not None else ""
        self.add_order_key(out, df, ["شماره سفارش"])
        log.info(f"   🔑 [il] کلید ثبت سفارش از ستون «{col}» "
                 f"({int(out[KEY_REG].astype(str).ne('').sum())} ردیف)")
        return {"main": out}


@register
class SapAdapter(SourceAdapter):
    """گردش کار درخواست خرید در SAP — شیت Data.

    این فایل بارنامه ندارد. کلیدش Purchase Requisition است که با «PR No.»
    فایل مقاومت جور می‌شود. نسخه قبل آن را روی بارنامه join می‌کرد که
    هرگز نمی‌توانست منطبق شود.
    """
    key, prefix = "sap", "SAP"

    COLUMN_MAP = {
        "DOC_TYPE":       ["Document Type"],
        "PURCH_ORG":      ["Purch. Organization"],
        "STATUS_ID":      ["Status ID"],
        "NOTIFICATION":   ["Notification"],
        "WORKFLOW_ID":    ["WorkFlow ID"],
        "WORKFLOW_STATUS": ["WorkFlow Status"],
        "PR_STATUS_TEXT": ["PR Status Text"],
        "COMPARISON_ID":  ["Comparision ID", "Comparison ID"],
        "COMMISSION_NO":  ["Commision No", "Commission No"],
        "COMMISSION_DATE": ["Commision Date", "Commission Date"],
        "CHANGED_ON":     ["Changed On"],
        "CHANGED_BY":     ["Changed By"],
        "TASK_STATUS":    ["Tasks Status"],
        "ACTION":         ["Action"],
        "PURCH_GROUP":    ["Purchasing Group"],
    }

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = self._first(sheets)
        if df is None:
            return {}
        p = self.p
        out = self.std(df, self.COLUMN_MAP)
        self.add_pr_key(out, df, ["Purchase Requisition"])
        out = out[out[KEY_PR].astype(str).str.strip() != ""]
        if out.empty:
            return {}
        # آخرین وضعیت گردش کار هر PR
        out = out.sort_values(p("CHANGED_ON")).groupby(KEY_PR, as_index=False).last()
        log.info(f"   ⚙️ [sap] {len(out)} درخواست خرید یکتا (آخرین وضعیت گردش کار)")
        return {"main": out}


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
        out = dedupe_on_key(out, KEY_ORDER, keep_by=p("SUBMIT_DATE"),
                            label="doccheck→سفارش")
        return {"main": out}


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
