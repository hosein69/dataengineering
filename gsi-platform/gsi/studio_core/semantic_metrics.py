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
from typing import Dict, Optional


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
    "موجودی کل قابل احتساب": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    "موجودی ایران خودرو": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    "موجودی ساپکو": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    "موجودی در راه": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
    "موجودی در گمرک": MetricSpec("additive", "sum", "MATERIAL", "quantity"),
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
