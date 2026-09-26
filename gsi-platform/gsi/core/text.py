# -*- coding: utf-8 -*-
"""لایه نرمال‌سازی متن و کلیدها — پایه‌ای‌ترین ماژول سیستم.

این ماژول هیچ وابستگی به pandas ندارد جز برای تشخیص NaN، تا بتوان آن را
به‌صورت مستقل تست کرد و در آینده در سرویس‌های دیگر (Streamlit / API) استفاده نمود.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — gsi/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 4


import math
import re
from typing import Any

# ── نگاشت ارقام فارسی و عربی به لاتین ──
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# ── نگاشت حروف چندشکلی عربی/فارسی ──
_CHAR_MAP = {
    "ي": "ی", "ك": "ک", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "آ", "ؤ": "و",
    "ى": "ی",        # الف مقصوره عربی (U+0649) — در صفحه‌کلید عربی جای «ی»
    "ڪ": "ک",        # کاف سواحلی/سندی (U+06AA) — در برخی فونت‌ها/کپی وب
    "\u200c": " ",  # نیم‌فاصله
    "\xa0": " ",    # فاصله نشکن
    "\u202f": " ",  # فاصله نشکن باریک
}
_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670]")
#: نویسه‌های نامرئی جهت‌دهی/عرض صفر/کشیده که از کپی وب و Excel در سلول
#: می‌مانند؛ در متن فارسی هیچ معنایی ندارند و اگر حذف نشوند «12345» و
#: «\u200f12345» دو کلید متفاوت می‌شوند و ادغام بی‌صدا شکست می‌خورد.
_INVISIBLE = re.compile("[\u200b\u200d\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\u0640]")
_WS = re.compile(r"\s+")

_EMPTY_TOKENS_BASE = {
    "nan", "none", "nat", "-", "--", "null", "namashakhas",
    "نامشخص", "ندارد", "خالی", "فاقد", "na", "n/a", "empty", "#n/a",
}


def _is_nan(v: Any) -> bool:
    """تشخیص NaN بدون وابستگی به pandas."""
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    # pandas.NaT و numpy.nan و pd.NA
    try:
        r = v != v  # noqa: PLR0124 — NaN != NaN
    except Exception:
        return False
    if isinstance(r, bool):
        return r
    # pd.NA != pd.NA is itself pd.NA; ``bool(pd.NA)`` raises TypeError, so
    # is_empty_val(pd.NA) used to crash (nullable columns hold pd.NA).
    if type(r).__name__ == "NAType":
        return True
    try:
        return bool(r)
    except Exception:
        return False


def to_latin_digits(s: Any) -> str:
    """تبدیل ارقام فارسی/عربی به لاتین."""
    if _is_nan(s):
        return ""
    return str(s).translate(_DIGIT_MAP)


def normalize_persian_text(text: Any) -> str:
    """یکسان‌سازی کامل متن فارسی: ارقام، حروف، اعراب، فاصله‌ها."""
    if _is_nan(text):
        return ""
    s = _INVISIBLE.sub("", str(text).translate(_DIGIT_MAP))
    for src, dst in _CHAR_MAP.items():
        s = s.replace(src, dst)
    s = _DIACRITICS.sub("", s)
    return _WS.sub(" ", s).strip()


def normalize_col_name(col: Any) -> str:
    """نرمال‌سازی نام ستون‌های اکسل (حفظ حروف، حذف فاصله اضافی)."""
    if _is_nan(col):
        return ""
    return normalize_persian_text(col)


def clean_key(val: Any) -> str:
    """کلید سفارش / ثبت سفارش.

    FIX-1: نسخه قبلی از ``.replace('.0', '')`` استفاده می‌کرد که هر '.0' را در
    هرجای رشته حذف می‌کرد و مقادیری مثل '1.05' را به '15' تبدیل می‌نمود.
    اینجا فقط پسوند انتهایی '.0' (ناشی از خواندن float توسط اکسل) حذف می‌شود.
    """
    if _is_nan(val):
        return ""
    s = _INVISIBLE.sub("", to_latin_digits(str(val))).strip().upper()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def clean_bl(bl: Any) -> str:
    """کلید بارنامه: فقط A-Z و 0-9؛ طول کمتر از ۴ نامعتبر است."""
    if _is_nan(bl):
        return ""
    raw = re.sub(r"[^A-Z0-9]", "", to_latin_digits(str(bl)).strip().upper())
    return raw if len(raw) >= 4 else ""


def clean_part_no(pn: Any) -> str:
    """کلید متریال/شماره فنی به‌صورت TEXT، با پشتیبانی حروف و ارقام Unicode.

    Material یک identifier است، نه عدد. بنابراین:
      * حروف لاتین (a/A) و فارسی/عربی حفظ می‌شوند؛
      * ارقام فارسی/عربی به لاتین تبدیل می‌شوند؛
      * فاصله و جداکننده‌های نمایشی حذف می‌شوند؛
      * فقط پسوند ``.0`` یک مقدار کاملاً عددیِ Excel حذف می‌شود.

    مثال‌ها: ``ab-12`` → ``AB12``، ``قطعه-۱۲A`` → ``قطعه12A``،
    ``9654003280.0`` → ``9654003280``.
    """
    if _is_nan(pn):
        return ""
    s = normalize_persian_text(pn).strip().upper()
    if re.fullmatch(r"[0-9]+\.0", s):
        s = s[:-2]
    # str.isalnum() Unicode-aware است؛ برخلاف [A-Z0-9] حروف فارسی را حذف نمی‌کند.
    return "".join(ch for ch in s if ch.isalnum())


def clean_employee_code(code: Any) -> str:
    """کد پرسنلی.

    FIX-12: فقط بخش عددی ابتدای رشته استخراج و به ۸ رقم zero-pad می‌شود.
    مثال: '10201069_GS' → '10201069'  |  '  201069-A' → '00201069'
    """
    if _is_nan(code):
        return ""
    s = to_latin_digits(str(code)).strip()
    m = re.match(r"^\D*(\d+)", s)
    if not m:
        return ""
    digits = m.group(1)
    return digits.zfill(8) if len(digits) <= 8 else digits


_EMPTY_TOKENS = frozenset(_EMPTY_TOKENS_BASE)
_EMPTY_TOKENS_ZERO = frozenset(_EMPTY_TOKENS_BASE | {"0", "0.0", "۰"})


def is_empty_val(v: Any, treat_zero_as_empty: bool = True) -> bool:
    """تشخیص جامع مقدار تهی (None, NaN, '', '0', 'nan', 'نامشخص', ...).

    V29.9 (کارایی): این تابع در هر اجرا میلیون‌ها بار صدا زده می‌شود و قبلاً
    در هر فراخوانی یک set تازه می‌ساخت. مجموعه‌ها یک‌بار ساخته می‌شوند و رشته
    ساده مسیر سریع دارد (رشته هیچ‌وقت NaN نیست)؛ نتیجه بدون تغییر است.
    """
    if type(v) is str:
        s = v.strip()
    else:
        if _is_nan(v):
            return True
        s = str(v).strip()
    if s == "":
        return True
    return s.lower() in (_EMPTY_TOKENS_ZERO if treat_zero_as_empty else _EMPTY_TOKENS)


def num_safe(v: Any) -> float:
    """تبدیل امن به float با قرارداد قدیمی «ناشناخته = 0.0».

    FIX-2: نسخه قبلی روی مقادیری مثل '1.234.567' (جداکننده هزارگان نقطه‌ای)
    بی‌صدا 0.0 برمی‌گرداند. اینجا جداکننده هزارگان تشخیص داده و حذف می‌شود.

    V29.9: پیاده‌سازی به ``gsi.core.numeric_parse.parse_decimal`` منتقل شد. نسخه
    قبلی نماد علمی را «نویز» می‌دانست و حذف می‌کرد (``1e-05 → 105`` و
    ``1.5e16 → 1.516``)، ممیز فارسی «٫» را پاک می‌کرد (``1٫5 → 15``) و منفی
    انتهایی SAP (``1,234.56-``) را مثبت می‌خواند. این تابع هنوز برای مقدار
    ناشناخته 0.0 برمی‌گرداند؛ مسیرهای مالی تصمیم‌ساز باید از
    ``parse_decimal``/``warehouse.numeric.number`` استفاده کنند تا Unknown
    با صفر یکی نشود.
    """
    if is_empty_val(v, treat_zero_as_empty=False):
        return 0.0
    from .numeric_parse import parse_decimal
    value = parse_decimal(v, strict=False)
    return float(value) if value is not None else 0.0


_ITEM_SUFFIX = re.compile(r"[\s\-–—]*items?\s*[\d&\s,and]*$", re.IGNORECASE)
_TRAILING_ALPHA = re.compile(r"^(\d{3,})([A-Z]*)$")


def clean_order_ref(val: Any) -> str:
    """مرجع سفارش IKCO — «Order No. (Our Reference)».

    نمونه‌های واقعی سورس مقاومت:
        '602164B'                → '602164B'
        '603128A-\nItem 1'       → '603128A'
        '603130B-Items 2 & 3 '   → '603130B'
        '10200001.0'             → '10200001'
    """
    if _is_nan(val):
        return ""
    s = normalize_persian_text(val).upper()
    s = s.replace("\n", " ").replace("\r", " ")
    s = _ITEM_SUFFIX.sub("", s).strip(" -–—\t")
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\s+", "", s)


def order_ref_base(val: Any) -> str:
    """ریشه عددی مرجع سفارش: '603128A' → '603128' (برای تجمیع اقلام یک سفارش)."""
    s = clean_order_ref(val)
    m = _TRAILING_ALPHA.match(s)
    return m.group(1) if m else s
