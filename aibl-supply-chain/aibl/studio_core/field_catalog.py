# -*- coding: utf-8 -*-
"""کاتالوگ فیلدها — **مشتق از سورس‌ها، نه دستی‌نویس**.

نسخه قبلی یک دیکشنری ثابت با ۲۷ برچسب بود و ``available_fields`` فقط
همان‌ها را برمی‌گرداند. خط لوله ۳۶۷ ستون تولید می‌کند، پس **۹۴٪ داده در
رابط کاربری اصلاً دیده نمی‌شد و قابل گزارش نبود** — درست همان چیزی که
قرارداد ماژولاریتی README وعده می‌دهد ولی نقض می‌شد: adapter جدید اضافه
می‌کردید، ستون‌هایش هرگز در UI ظاهر نمی‌شد.

حالا کاتالوگ از خود سیستم استخراج می‌شود:

* هر adapter یک ``prefix`` و یک ``COLUMN_MAP`` دارد که مقادیرش **هدرهای
  واقعی فارسی فایل منبع**اند. پس ستون ``BL_GOODS_DESC`` خودبه‌خود برچسب
  «شرح کالا» و گروه «ردیابی بارنامه‌ها» می‌گیرد.
* ستون‌های محاسباتیِ stageها برچسب صریح دارند.
* هر ستون ناشناخته هم **حذف نمی‌شود** — در گروه «سایر» می‌آید و کاملاً
  قابل انتخاب و قابل گزارش است.

قرارداد: ``build_catalog(df)`` هرگز ستونی از df را جا نمی‌اندازد.
"""
from __future__ import annotations

__contract__ = 2

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

# ── برچسب ستون‌های محاسباتی (خروجی stageها، نه سورس) ──────────────────────
COMPUTED_LABELS: Dict[str, str] = {
    # کلیدهای کانونی
    "KEY_BL": "کلید بارنامه", "KEY_ORDER": "کلید سفارش", "KEY_REG": "کلید ثبت سفارش",
    "KEY_EMP": "کد پرسنلی", "KEY_MATERIAL": "کد متریال", "KEY_PR": "شماره درخواست خرید",
    "CANONICAL_BL": "شماره بارنامه", "CANONICAL_ORDER": "شماره سفارش",
    "CANONICAL_PART_NO": "شماره فنی", "CANONICAL_GOODS_DESC": "شرح کالا",
    "CANONICAL_EXPERT": "کارشناس مالک مرحله فعلی", "CANONICAL_REG": "ثبت سفارش",
    # نقش‌های کارشناسی — هر نقش مستقل، بدون سرریز به نقش دیگر
    "EXPERT_ROLE": "نقش کارشناس مالک",
    "EXPERT_BUYER": "کارشناس خرید خارجی",
    "EXPERT_ORDER_REG": "کارشناس ثبت سفارش",
    "EXPERT_CREDIT": "کارشناس اعتبارات",
    "EXPERT_SETTLEMENT": "کارشناس رفع تعهد ارزی",
    "EXPERT_CLEARANCE": "کارشناس ترخیص",
    "EXPERT_DOC": "کارشناس کنترل اسناد",
    "EXPERT_COMMERCIAL": "کارشناس بازرگانی",
    # سازمان
    "ORG_DEPT": "مدیریت", "ORG_MANAGER": "مدیر", "ORG_HEAD": "رئیس",
    "ORG_VICE": "معاونت", "ORG_CHAIN": "زنجیره سازمانی", "ORG_MATCHED": "تطبیق سازمانی",
    # بحرانی بودن و مقاومت
    "بحرانی (کوتاه)": "طبقه بحرانی", "کد طبقه بحرانی": "کد طبقه بحرانی",
    "مقاومت (روز)": "مقاومت (روز)", "نیاز روزانه": "نیاز روزانه",
    "موجودی کل قابل احتساب": "موجودی قابل احتساب",
    "BL_CRITICAL": "بارنامه بحرانی", "BL_CRITICAL_LEVEL": "سطح بحرانی بارنامه",
    "BL_CRITICAL_MATERIALS": "متریال‌های بحرانی بارنامه",
    "BL_CRITICAL_REASON": "علت بحرانی شدن بارنامه",
    "ORDER_CRITICAL": "سفارش بحرانی", "ORDER_CRITICAL_LEVEL": "سطح بحرانی سفارش",
    "ORDER_CRITICAL_MATERIALS": "متریال‌های بحرانی سفارش",
    "ORDER_CRITICAL_REASON": "علت بحرانی شدن سفارش",
    "CRITICALITY_SORT": "رتبه بحرانی",
    # ریسک و تعهد
    "امتیاز ریسک": "امتیاز ریسک", "طبقه ریسک": "طبقه ریسک",
    "مانده تعهد": "مانده تعهد", "روزهای تأخیر": "روزهای تأخیر",
    "جریمه برآوردی": "جریمه برآوردی", "روزهای رسوب": "روزهای رسوب",
    # روایت و فرآیند
    "STAGE_FA": "مرحله فعلی", "PROGRESS": "پیشرفت", "ALERTS": "هشدارها",
    "روایت": "روایت", "اقدام پیشنهادی": "اقدام پیشنهادی",
    "روش حمل": "روش حمل", "PARTITION": "افراز", "MATERIAL_PARTITION": "افراز متریال",
}

# ── ستون‌های دامنه‌ای که stage «derive» می‌سازد (بدون پیشوند سورس) ────────
DERIVED_LABELS: Dict[str, str] = {
    # موجودی و مصرف
    "STOCK_IKCO": "موجودی انبار ایران‌خودرو", "STOCK_SAPCO": "موجودی انبار ساپکو",
    "IN_TRANSIT_QTY": "تعداد در راه", "IN_CUSTOMS_QTY": "تعداد در گمرک",
    "DAILY_NEED": "نیاز روزانه", "CARS_ON_FLOOR": "تعداد خودرو کف",
    "موجودی ایران خودرو": "موجودی ایران‌خودرو", "موجودی ساپکو": "موجودی ساپکو",
    "موجودی در راه": "موجودی در راه", "موجودی در گمرک": "موجودی در گمرک",
    # متریال
    "MATERIAL_DESC": "شرح متریال", "MATERIAL_STATUS": "وضعیت متریال",
    "PART_GROUP": "گروه قطعه", "PART_CLASS": "رده‌بندی قطعه",
    "SUPPLY_GROUP": "گروه تأمین", "FOREIGN_SHARE": "درصد سهم خرید خارجی",
    "VENDOR_CODE": "کد تأمین‌کننده", "BUYER": "کارشناس خرید",
    # حمل و ترخیص
    "TRANSPORT_MODE": "روش حمل", "BL_DATE": "تاریخ بارنامه",
    "DISCHARGE_DATE": "تاریخ تخلیه", "ARRIVAL_DATE": "تاریخ ورود",
    "COTAGE_NO": "شماره کوتاژ", "CUSTOMS_FILE_NO": "شماره پرونده گمرکی",
    "ENTRY_BORDER": "مرز ورودی", "DEST_CUSTOMS": "گمرک مقصد",
    "FULL_CLEAR_DATE": "تاریخ ترخیص کامل", "PARTIAL_CLEAR_DATE": "تاریخ ترخیص درصدی",
    "CLEAR_AMOUNT": "مبلغ ترخیص", "CLEAR_EXPERT": "کارشناس ترخیص",
    "CLEARED_PCT": "درصد ترخیص‌شده", "CLEARANCE_HINT": "راهنمای ترخیص",
    "HS_CODE": "کد تعرفه", "HS_SUGGESTED": "تعرفه پیشنهادی",
    "DUTY_AMOUNT": "حقوق و عوارض گمرکی", "INVOICE_VALUE": "ارزش فاکتور",
    "EUR_VALUE": "ارزش یورویی", "نوع ترخیص": "نوع ترخیص",
    # مالی و ارز
    "CURRENCY": "نوع ارز", "BANK": "بانک", "BALANCE": "مانده",
    "FX_SOURCE": "محل تأمین ارز", "PAYMENT_METHOD": "روش پرداخت",
    "BARAT_DUE": "سررسید برات", "BUY_DATE": "تاریخ خرید ارز",
    "FIN_RECEIPT_DATE": "تاریخ دریافت وجه", "CB_DATE": "تاریخ بانک مرکزی",
    "CB_VALUE": "ارزش بانک مرکزی", "LC_NO": "شماره اعتبار", "LC_STATUS": "وضعیت اعتبار",
    "CREDIT_STATUS": "وضعیت اعتبارات", "CREDIT_EXPERT": "کارشناس اعتبارات",
    "OPEN_COMMIT_ROWS": "ردیف‌های تعهد باز", "COMMIT_ROWS": "ردیف‌های تعهد",
    "LEGAL_DEADLINE_DAYS": "مهلت قانونی (روز)",
    "ALLOCATED": "تخصیص‌یافته", "ALLOC_STATUS": "وضعیت تخصیص",
    "ALLOC_PROCESS": "مرحله تخصیص", "ALLOC_DATE": "تاریخ تخصیص",
    "ALLOC_REQUESTS": "تعداد درخواست تخصیص", "ALLOC_REJECTED_F": "تخصیص رد شده",
    # خرید
    "PR_STATUS": "وضعیت درخواست خرید", "PR_WORKFLOW": "گردش کار درخواست خرید",
    "PO_SENT_DATE": "تاریخ ارسال سفارش", "COMMERCIAL_NOTE": "یادداشت بازرگانی",
    "LOGISTICS_NOTE": "یادداشت لجستیک",
    # پرچم‌های وضعیت
    "IS_FULL_CLEARED": "ترخیص کامل شده", "IS_PARTIAL_CLEARED": "ترخیص درصدی شده",
    "IS_ABANDONED": "متروکه", "IS_IN_MOGHAVEMAT": "موجود در مقاومت",
    "IS_BLOCKED": "بلوکه", "IS_CANCELLED": "ابطال‌شده",
    "IS_IN_TRANSIT": "در راه", "IS_IN_CUSTOMS": "در گمرک",
    "SEGMENT": "سگمنت", "کد سگمنت": "کد سگمنت", "نوع پرونده": "نوع پرونده",
    # فرآیند
    "CASE_KEY": "کلید پرونده", "EVENT_COUNT": "تعداد رویداد",
    "THROUGHPUT_DAYS": "طول چرخه (روز)", "PROCESS_COMPLETENESS": "کامل بودن فرآیند",
    "ORDER_MISSING_COMMERCIAL_EXPERT": "سفارش درج‌نشده در Commercial Expert Data",
    "COMMERCIAL_EXPERT_SOURCE_PRESENT": "وجود سفارش در Commercial Expert Data",
    "ORDER_MISSING_COMMERCIAL_REASON": "علت نبود سفارش در Commercial Expert Data",
    "COMMERCIAL_COVERAGE_STATE": "وضعیت سنجش پوشش سورس خرید",
    # حوزه مسئولیت و مالکیت قطعه
    "EXPERT_PURCHASING": "کارشناس خرید",
    "EXPERT_COMMERCIAL": "کارشناس بازرگانی",
    "EXPERT_LOGISTICS": "کارشناس حمل و لجستیک",
    "PART_OWNER": "مالک قطعه (کارشناس خرید)",
    "PART_OWNER_SOURCE": "منبع شناسایی مالک",
    "PART_OWNER_DATA_GAP": "شکاف داده مالک",
    "PART_OWNER_SOURCE_GAP": "فیلدهای غایب سورس مالک",
    # وضعیت: کجا / کِی / چه کسی
    "STATUS_WHERE": "موقعیت فعلی",
    "STATUS_STAGE": "کد مرحله وضعیت",
    "STATUS_ACTIVITY": "آخرین فعالیت",
    "STATUS_WHEN": "تاریخ آخرین رویداد",
    "STATUS_AGE_DAYS": "سن وضعیت (روز)",
    "STATUS_WHO": "کارشناس مسئول وضعیت",
    "STATUS_WHO_SCOPE": "حوزه مسئول وضعیت",
    "STATUS_BASIS": "مبنای تعیین وضعیت",
    "NEXT_ACTIVITY": "فعالیت بعدی مورد انتظار",
    "WAITING_ON_SCOPE": "معطل حوزه",
    "WAITING_ON_WHO": "معطل کارشناس",
    "STATUS_MISSING": "تاریخ‌های ثبت‌نشده",
}

#: گروه‌بندی ستون‌های محاسباتی بر اساس الگوی نام
COMPUTED_GROUPS: List[tuple] = [
    ("کلیدهای کانونی", re.compile(r"^(KEY_|CANONICAL_)")),
    ("سازمان و مالکیت", re.compile(r"^ORG_|^EXPERT_")),
    ("بحرانی بودن و مقاومت", re.compile(
        r"(بحرانی|مقاومت|CRITICAL|نیاز روزانه|موجودی کل)")),
    ("ریسک و تعهد ارزی", re.compile(r"(ریسک|تعهد|جریمه|تأخیر|رسوب)")),
    ("روایت و فرآیند", re.compile(
        r"(روایت|اقدام|STAGE|PROGRESS|ALERT|PARTITION|روش حمل|CASE_KEY|EVENT_COUNT"
        r"|THROUGHPUT|PROCESS_COMPLETENESS)")),
    ("موجودی و مصرف", re.compile(r"^(STOCK_|IN_TRANSIT|IN_CUSTOMS|DAILY_NEED|CARS_ON_FLOOR)|موجودی")),
    ("ترخیص و گمرک", re.compile(
        r"^(CLEAR|COTAGE|CUSTOMS|ENTRY_BORDER|DEST_CUSTOMS|FULL_CLEAR|PARTIAL_CLEAR"
        r"|HS_|DUTY_)|نوع ترخیص")),
    ("مالی، ارز و اعتبار", re.compile(
        r"^(CURRENCY|BANK|BALANCE|FX_|PAYMENT_METHOD|BARAT|BUY_DATE|FIN_|CB_|LC_"
        r"|CREDIT_|ALLOC|ALLOCATED|COMMIT_ROWS|OPEN_COMMIT|LEGAL_DEADLINE"
        r"|INVOICE_VALUE|EUR_VALUE)")),
    ("پرچم‌های وضعیت", re.compile(r"^IS_|^SEGMENT$|^نوع پرونده$|^کد سگمنت$")),
    ("تحلیل هوشمند و انطباق", re.compile(
        r"(هشدار|پیشنهاد|احتمال|انطباق|انحراف|قطعیت|هوشمند|VARIANT|جاافتاده"
        r"|نقض ترتیب|علت ریشه)")),
    ("مالی، ارز و اعتبار", re.compile(r"^(روش پرداخت|برات/یوزانس)$")),
    ("خرید و تأمین‌کننده", re.compile(
        r"^(PR_|PO_|VENDOR_|BUYER|SUPPLY_GROUP|FOREIGN_SHARE|PART_GROUP|PART_CLASS"
        r"|MATERIAL_DESC|MATERIAL_STATUS|COMMERCIAL_NOTE|LOGISTICS_NOTE)")),
    ("حمل و بارنامه", re.compile(r"^(TRANSPORT_MODE|BL_DATE|DISCHARGE_DATE|ARRIVAL_DATE|BL_SUSPECT)$")),
]


#: نام کوتاه فارسی هر سورس — برای رفع ابهام برچسب‌های تکراری
SOURCE_SHORT: Dict[str, str] = {
    "abbasi": "بارنامه", "sata": "ساتا", "clearance": "ترخیص", "cotage": "کوتاژ",
    "oracle": "اوراکل", "ntsw": "NTSW", "fx_transaction": "خرید ارز",
    "credit": "اعتبارات", "ilappend": "الحاقیه", "sap": "SAP",
    "doccheck": "کنترل اسناد", "hr": "منابع انسانی", "moghavemat": "مقاومت",
}


@dataclass(frozen=True)
class FieldSpec:
    """یک ستون قابل گزارش."""
    column: str
    label: str
    group: str
    source: str = ""        # کلید adapter، اگر از سورس آمده باشد
    dtype: str = ""
    fill_pct: float = 0.0   # چند درصد ردیف‌ها مقدار دارند

    @property
    def display(self) -> str:
        return f"{self.label} · {self.column}" if self.label != self.column else self.column


def _clean_header(raw: str) -> str:
    """هدر واقعی فایل را به یک برچسب تمیز تبدیل می‌کند.

    هدرهای تولید ناهنجاری دارند: ``_شرح کالا_`` با زیرخط، فاصله دوتایی،
    «ي» عربی. اینجا فقط برای *نمایش* تمیز می‌شوند؛ نام ستون دست‌نخورده
    می‌ماند تا گزارش‌ها نشکنند.
    """
    s = str(raw).strip().strip("_").strip()
    s = re.sub(r"\s+", " ", s)
    return s.replace("ي", "ی").replace("ك", "ک")


def source_field_map() -> Dict[str, tuple]:
    """{نام ستون: (برچسب، گروه، کلید سورس)} برای همه adapterهای کشف‌شده.

    این تابع همان رجیستری‌ای را می‌خواند که pipeline استفاده می‌کند، پس
    adapter جدید بدون هیچ تغییری در این فایل به UI اضافه می‌شود.
    """
    out: Dict[str, tuple] = {}
    try:
        from ..adapters import REGISTRY, discover
        discover()
    except Exception:
        return out
    for key, cls in REGISTRY.items():
        prefix = getattr(cls, "prefix", "") or ""
        column_map = getattr(cls, "COLUMN_MAP", {}) or {}
        try:
            role = cls().spec.role or key
        except Exception:
            role = key
        group = f"{role}"
        for std_name, candidates in column_map.items():
            col = f"{prefix}_{std_name}" if prefix else std_name
            head = candidates[0] if isinstance(candidates, (list, tuple)) and candidates else std_name
            out[col] = (_clean_header(head), group, key)
    return out


def source_prefix_groups() -> Dict[str, tuple]:
    """{پیشوند سورس: (گروه، کلید سورس)} — برای ستون‌هایی که adapter
    برنامه‌نویسی می‌سازد و در ``COLUMN_MAP`` نیستند (مثل NTSW)."""
    out: Dict[str, tuple] = {}
    try:
        from ..adapters import REGISTRY, discover
        discover()
    except Exception:
        return out
    for key, cls in REGISTRY.items():
        prefix = getattr(cls, "prefix", "") or ""
        if not prefix:
            continue
        try:
            role = cls().spec.role or key
        except Exception:
            role = key
        out[prefix] = (role, key)
    return out


def _computed_group(col: str) -> Optional[str]:
    for name, pattern in COMPUTED_GROUPS:
        if pattern.search(col):
            return name
    return None


def build_catalog(df: pd.DataFrame) -> List[FieldSpec]:
    """کاتالوگ کامل ستون‌های df — **هیچ ستونی حذف نمی‌شود**."""
    if df is None or len(df.columns) == 0:
        return []
    src_map = source_field_map()
    prefix_groups = source_prefix_groups()
    n = max(len(df), 1)
    specs: List[FieldSpec] = []
    for col in df.columns:
        col = str(col)
        if col in COMPUTED_LABELS:
            label, group, source = COMPUTED_LABELS[col], (_computed_group(col) or "محاسباتی"), ""
        elif col in src_map:
            label, group, source = src_map[col]
        elif col in DERIVED_LABELS:
            label = DERIVED_LABELS[col]
            group, source = (_computed_group(col) or "ستون‌های دامنه‌ای"), ""
        else:
            grp = _computed_group(col)
            if grp:
                label, group, source = _clean_header(col), grp, ""
            else:
                # پیشوند سورس را می‌شناسیم حتی اگر خود ستون در COLUMN_MAP نباشد
                # (مثلاً NTSW ستون‌هایش را برنامه‌نویسی می‌سازد، نه با نگاشت).
                pref = col.split("_", 1)[0]
                if pref in prefix_groups:
                    grp_name, src_key = prefix_groups[pref]
                    label, group, source = _clean_header(col), grp_name, src_key
                else:
                    # ناشناخته — ولی همچنان قابل انتخاب و قابل گزارش
                    label, group, source = _clean_header(col), "سایر ستون‌ها", ""
        try:
            s = df[col]
            filled = float(s.notna().sum() - (s.astype(str).str.strip() == "").sum()) if s.dtype == object else float(s.notna().sum())
            fill = max(0.0, min(100.0, 100.0 * filled / n))
            dtype = str(s.dtype)
        except Exception:
            fill, dtype = 0.0, ""
        specs.append(FieldSpec(col, label, group, source, dtype, round(fill, 1)))
    return specs


def catalog_groups(specs: List[FieldSpec]) -> Dict[str, List[FieldSpec]]:
    """{گروه: [فیلدها]} با حفظ ترتیب معنادار."""
    order = ["کلیدهای کانونی", "بحرانی بودن و مقاومت", "ریسک و تعهد ارزی",
             "سازمان و مالکیت", "روایت و فرآیند"]
    groups: Dict[str, List[FieldSpec]] = {}
    for sp in specs:
        groups.setdefault(sp.group, []).append(sp)
    ranked = {k: groups.pop(k) for k in order if k in groups}
    for k in sorted(groups):
        if k != "سایر ستون‌ها":
            ranked[k] = groups[k]
    if "سایر ستون‌ها" in groups:
        ranked["سایر ستون‌ها"] = groups["سایر ستون‌ها"]
    return ranked


def unique_labels(specs: List[FieldSpec]) -> Dict[str, str]:
    """{ستون: نام نمایشی یکتا}.

    چند سورس برچسب یکسان دارند — «شرح کالا» هم در بارنامه هست، هم ساتا،
    هم ترخیص، هم خرید ارز؛ «وضعیت» در پنج سورس. اگر ستون‌ها را مستقیم به
    برچسب rename کنیم، pandas ستون تکراری می‌سازد و
    ``ValueError: Duplicate column names`` می‌دهد. پس هر برچسب تکراری با
    نام سورسش مقید می‌شود و اگر باز هم یکتا نشد، با نام خود ستون.
    """
    counts: Dict[str, int] = {}
    for sp in specs:
        counts[sp.label] = counts.get(sp.label, 0) + 1
    out: Dict[str, str] = {}
    used: set = set()
    for sp in specs:
        name = sp.label if counts.get(sp.label, 0) == 1 else (
            f"{sp.label} · {SOURCE_SHORT.get(sp.source, sp.source)}"
            if sp.source else f"{sp.label} · {sp.column}")
        if name in used:
            name = f"{sp.label} · {sp.column}"
        while name in used:          # آخرین سد — نام ستون یکتاست
            name += " "
        used.add(name)
        out[sp.column] = name
    return out


# ── سازگاری با API قبلی ────────────────────────────────────────────────────
def available_fields(df) -> List[str]:
    """همه ستون‌های df — برخلاف نسخه قبل که فقط ۲۲ ستون برمی‌گرداند."""
    return [sp.column for sp in build_catalog(df)]


def label(field) -> str:
    col = str(field)
    if col in COMPUTED_LABELS:
        return COMPUTED_LABELS[col]
    src = source_field_map().get(col)
    return src[0] if src else _clean_header(col)


def _legacy_groups() -> Dict[str, List[str]]:
    g: Dict[str, List[str]] = {}
    for col, lbl in COMPUTED_LABELS.items():
        g.setdefault(_computed_group(col) or "محاسباتی", []).append(col)
    return g


FIELD_LABELS = COMPUTED_LABELS          # سازگاری عقب‌رو
FIELD_GROUPS = _legacy_groups()         # سازگاری عقب‌رو
