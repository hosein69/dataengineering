# -*- coding: utf-8 -*-
"""رجیستری معنایی سنجه‌ها.

نوع و روش تجمیع سنجه‌های مدیریتی نباید از شکل اعداد حدس زده شود. این ماژول
مرجع صریح ``kind / aggregation / grain / unit`` است و در همه خروجی‌ها قابل
استفاده است. رجیستری عمداً کوچک و قابل توسعه است؛ الگوها فقط برای خانواده‌های
شناخته‌شده‌اند و تشخیص بر اساس یکتایی/بزرگی عدد انجام نمی‌شود.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
import re
from typing import Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class MetricSpec:
    kind: str                 # additive | ratio | identifier
    aggregation: str          # sum | mean | nunique | min | max
    grain: Optional[str] = None
    unit: str = ""
    description: str = ""


# سنجه‌های حساس/مدیریتی با تعریف صریح. نام‌های انگلیسی رایج سورس نیز پوشش داده شده‌اند.
METRICS: Dict[str, MetricSpec] = {
    "مانده تعهد": MetricSpec("additive", "sum", "REG", "amount", "مانده تعهد ارزی/ریالی"),
    "تعهد اولیه": MetricSpec("additive", "sum", "REG", "amount"),
    "جریمه برآوردی": MetricSpec("additive", "sum", "REG", "amount"),
    "مقاومت (روز)": MetricSpec("ratio", "mean", "MATERIAL", "day"),
    "مقاومت انبار (روز)": MetricSpec("ratio", "mean", "MATERIAL", "day"),
    "نیاز روزانه": MetricSpec("additive", "sum", "MATERIAL", "quantity/day"),
    # R8: کل = Oracle (دانه متریال) + کارشناس (دانه سفارش×متریال)؛ جمع ردیفی‌اش موجودی
    # Oracle را به ازای هر سفارش تکرار می‌کند، پس «نسبتی» (غیرقابل جمع) ثبت شده است.
    "موجودی کل قابل احتساب": MetricSpec("ratio", "mean", "ORDER_MATERIAL", "quantity",
                                        "Oracle + کارشناس؛ جمع‌پذیر نیست"),
    "حداقل موجودی قابل اثبات": MetricSpec("ratio", "mean", "ORDER_MATERIAL", "quantity",
                                          "Oracle + کارشناس؛ جمع‌پذیر نیست"),
    "SUPPLY_TOTAL_CONFIRMED": MetricSpec("ratio", "mean", "ORDER_MATERIAL", "quantity",
                                         "Oracle + کارشناس؛ جمع‌پذیر نیست"),
    "SUPPLY_TOTAL_LOWER_BOUND": MetricSpec("ratio", "mean", "ORDER_MATERIAL", "quantity",
                                           "Oracle + کارشناس؛ جمع‌پذیر نیست"),
    "موجودی ایران خودرو": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    "موجودی ساپکو": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    # R8: مقدار پارت کارشناسی در دانه سفارش×متریال است.
    "موجودی در راه": MetricSpec("additive", "sum", "ORDER_MATERIAL", "quantity"),
    "موجودی در گمرک": MetricSpec("additive", "sum", "ORDER_MATERIAL", "quantity"),
    "روزهای رسوب": MetricSpec("ratio", "mean", "BL", "day"),
    "روزهای تأخیر": MetricSpec("ratio", "mean", "REG", "day"),
}

# نام ستون‌های مالی/مقداری رایج که باید قطعاً additive باشند، حتی اگر همه مقادیر
# صحیح، بزرگ و یکتا باشند.
_ADDITIVE_NAME = re.compile(
    r"(^|_)(AMOUNT|VALUE|BALANCE|COST|PRICE|DUTY|FEE|QTY|QUANTITY|WEIGHT|STOCK|INVENTORY|COMMITMENT)(_|$)"
    r"|مبلغ|ارزش|مانده|تعهد|جریمه|هزینه|قیمت|حقوق|عوارض|تعداد|مقدار|وزن|موجودی|نیاز",
    re.IGNORECASE,
)
_RATIO_NAME = re.compile(
    r"درصد|نرخ|٪|%|مقاومت|امتیاز|ratio|pct|rate|score|share|سهم|میانگین|throughput|روز(?:\)|$)|days?$",
    re.IGNORECASE,
)
_IDENTIFIER_NAME = re.compile(
    r"^(KEY_|CANONICAL_)|(_NO|_CODE|_ID|_KEY)$|شماره|کد |^کد$|کلید|کوتاژ|تعرفه|بارنامه|پرونده|رهگیری|No\.$|Number$",
    re.IGNORECASE,
)


#: ستون ارز هر مبلغ پولی، به ترتیب اولویت. چنین مبلغی فقط در یک ارز جمع می‌شود و مبلغی که ارزش
#: کد شناخته‌شده ندارد در هیچ جمعی نمی‌نشیند (گزارش مالک، ۱۴۰۵/۰۷/۰۶: مبلغ دو ارز هرگز جمع یا
#: یکی نمی‌شود). مبلغ ریالی و معادل یورو خودشان یک واحدند و اینجا نیستند.
_COMMITMENT_CCY = ("NTSW_CURRENCY", "CURRENCY", "ارز")
AMOUNT_CURRENCY: Dict[str, Tuple[str, ...]] = {
    "مانده تعهد": _COMMITMENT_CCY,
    "تعهد اولیه": _COMMITMENT_CCY,
    "جریمه برآوردی": _COMMITMENT_CCY,
    "BALANCE": ("NTSW_CURRENCY",),
    "NTSW_BALANCE": ("NTSW_CURRENCY",),
    "NTSW_INITIAL_COMMIT": ("NTSW_CURRENCY",),
    "CB_VALUE": ("CB_CURRENCY",),
    "INVOICE_VALUE": ("INVOICE_CURRENCY",),
    "SATA_INVOICE_VALUE": ("SATA_CURRENCY",),
    "ALLOCATED_AMOUNT": ("ALLOCATED_CURRENCY",),
    "NTSW_ALLOCATED_AMOUNT": ("NTSW_ALLOCATED_CURRENCY",),
    "OPEN_QUEUE_AMOUNT": ("OPEN_QUEUE_CURRENCY",),
    "NTSW_OPEN_QUEUE_AMOUNT": ("NTSW_OPEN_CURRENCY",),
    "REJECTED_ALLOC_AMOUNT": ("REJECTED_ALLOC_CURRENCIES",),
    "NTSW_REJECTED_AMOUNT": ("NTSW_REJECTED_CURRENCIES",),
    "NTSW_REQ_AMOUNT": ("NTSW_REQ_CURRENCY",),
    "FX_PURCHASE_AMOUNT": ("FX_CURRENCY",),
    "FX_AMOUNT": ("FX_CURRENCY",),
    "CREDIT_PROFORMA": ("CRD_CURRENCY",),
    "CRD_PROFORMA_VALUE": ("CRD_CURRENCY",),
    "MOGH_PI_VALUE_SUM": ("MOGH_CURRENCY",),
}


def currency_column(columns: Iterable[str], amount: str) -> Optional[str]:
    """ستون ارز مبلغ ``amount`` اگر در همین داده باشد؛ ``None`` یعنی مبلغ ستون ارز ندارد."""
    cols = set(map(str, columns))
    return next((c for c in AMOUNT_CURRENCY.get(str(amount), ()) if c in cols), None)


def get_metric(column: str) -> Optional[MetricSpec]:
    return METRICS.get(str(column))


def infer_kind_from_name(column: str) -> str:
    """Fallback امن و فقط نام‌محور؛ هرگز از distribution عدد استفاده نمی‌کند."""
    col = str(column)
    # additive قبل از identifier بررسی می‌شود تا INVOICE_VALUE / DUTY_AMOUNT و مشابه آن
    # هرگز به‌خاطر کلمه/پسوند فرعی به شناسه تبدیل نشوند.
    if _ADDITIVE_NAME.search(col):
        return "additive"
    if _IDENTIFIER_NAME.search(col):
        return "identifier"
    if _RATIO_NAME.search(col):
        return "ratio"
    return "additive"


def registered_grain(column: str) -> Optional[str]:
    spec = get_metric(column)
    return spec.grain if spec else None


def registered_agg(column: str) -> Optional[str]:
    spec = get_metric(column)
    return spec.aggregation if spec else None
