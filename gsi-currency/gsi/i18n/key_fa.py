# -*- coding: utf-8 -*-
"""عنوان فارسی برای کلیدهای فنی که در کاتالوگ برچسب فارسی ندارند.

ترکیب اسمی انگلیسی (``BL_DISCHARGE_DATE``) هسته‌اش در آخر است و در فارسی
هسته اول می‌آید؛ پس توکن‌ها برعکس چیده می‌شوند: «تاریخ تخلیه بارنامه».
عبارت‌های چندتوکنی (``IN_TRANSIT``، ``AT_SUPPLIER``) پیش از برعکس کردن
یک واحد می‌شوند تا حرف اضافه جابه‌جا نشود.
"""
from __future__ import annotations

from typing import Dict, List

#: عبارت‌های چندتوکنی (به ترتیب انگلیسی)
PHRASES_FA: Dict[tuple, str] = {
    ("IN", "TRANSIT"): "در راه", ("IN", "CUSTOMS"): "در گمرک",
    ("AT", "SUPPLIER"): "نزد سازنده", ("READY",): "آماده حمل",
    ("NO", "DATE"): "بدون تاریخ", ("NOT", "FOR"): "نه برای",
    ("WAITING", "ON", "WHO"): "منتظر چه کسی", ("WHO", "SCOPE"): "حوزه مسئول",
    ("IN", "MOGHAVEMAT"): "در فایل مقاومت", ("IN", "EXPERT"): "در فایل کارشناسان",
    ("IN", "NTSW"): "در NTSW", ("EXCLUDED", "FROM", "KPI"): "خارج از KPI",
    ("LOWER", "BOUND"): "کران پایین", ("DUE", "DATE"): "تاریخ سررسید",
    ("EMAIL", "READY"): "ایمیل آماده", ("RIAL", "EQ"): "معادل ریالی",
    ("EUR", "EQ"): "معادل یورویی", ("KEY", "EMP"): "کد پرسنلی",
    ("CLEAR", "DONE"): "ترخیص انجام‌شده", ("PART", "NO"): "شماره فنی",
    ("MFR", "PART", "NO"): "شماره فنی سازنده", ("PR", "NO"): "شماره درخواست خرید",
    ("BL", "NO"): "شماره بارنامه", ("LC", "NO"): "شماره اعتبار اسنادی",
    ("COTAGE", "NO"): "شماره کوتاژ", ("PI", "NO"): "شماره پیش‌فاکتور",
    ("HS", "CODE"): "کد تعرفه", ("ROOT", "CAUSE"): "علت ریشه‌ای",
    ("NEXT", "ACTION"): "اقدام بعدی", ("DAILY", "NEED"): "نیاز روزانه",
    ("FLOOR", "STOCK"): "موجودی کف", ("CONTAINER", "20"): "کانتینر ۲۰ فوت",
    ("CONTAINER", "40"): "کانتینر ۴۰ فوت", ("SOURCE", "ROW"): "ردیف سورس",
    ("SOURCE", "FILE", "ID"): "شناسه فایل سورس", ("SOURCE", "SHEET"): "شیت سورس",
}

TOKEN_FA: Dict[str, str] = {
    "1": "۱", "2": "۲", "20": "۲۰", "40": "۴۰",
    "ABANDONED": "متروکه", "ACTION": "اقدام", "ACTIVITY": "فعالیت",
    "ADDITIONAL": "اضافی", "ADDITIVITY": "جمع‌پذیری", "AGE": "سن", "ALERTS": "هشدارها",
    "ALL": "همه", "ALLOC": "تخصیص", "ALLOCATED": "تخصیص‌یافته", "ALLOCATION": "تخصیص",
    "ALTERNATIVE": "جایگزین", "AMENDMENT": "اصلاحیه", "AMENDMENTS": "اصلاحیه‌ها",
    "AMOUNT": "مبلغ", "ANOMALIES": "ناهنجاری‌ها", "ANOMALY": "ناهنجاری",
    "APPROVAL": "تأیید", "APPROVE": "تأیید", "APPROXIMATE": "تقریبی",
    "ARRIVAL": "ورود", "AT": "در", "AUTHORITY": "مرجع", "AUTO": "خودکار",
    "BALANCE": "مانده", "BAND": "بازه", "BANK": "بانک", "BANKS": "بانک‌ها",
    "BARAT": "برات", "BASE": "پایه", "BASIS": "مبنا", "BENEF": "ذی‌نفع",
    "BENEFICIARIES": "ذی‌نفعان", "BENEFICIARY": "ذی‌نفع", "BINDING": "الزام‌آور",
    "BL": "بارنامه", "BLOCKED": "مسدود", "BLOCKERS": "موانع", "BLOCKING": "مانع",
    "BLREG": "پیوند بارنامه/ثبت", "BODY": "متن", "BORDER": "مرز", "BOUND": "کران",
    "BRANCH": "شعبه", "BUILD": "ساخت", "BUY": "خرید", "BUYER": "کارشناس خرید",
    "CANCELLED": "ابطال‌شده", "CANONICAL": "مرجع", "CARGO": "محموله",
    "CARRIER": "حمل‌کننده", "CARS": "خودرو", "CASE": "پرونده", "CAUSE": "علت",
    "CB": "بانک مرکزی", "CERTAIN": "قطعی", "CHAIN": "زنجیره", "CHECKS": "کنترل‌ها",
    "CL": "ترخیص", "CLASS": "طبقه", "CLEAR": "ترخیص", "CLEARANCE": "ترخیص",
    "CLEARED": "ترخیص‌شده", "CLOSED": "بسته", "CODE": "کد", "COLLATERAL": "وثیقه",
    "COMMERCIAL": "بازرگانی", "COMMIT": "تعهد", "COMMITMENT": "تعهد",
    "COMPANY": "شرکت", "COMPLETENESS": "کامل بودن", "COMPLETION": "تکمیل",
    "CONFIDENCE": "اطمینان", "CONFIRM": "تأیید", "CONFIRMED": "تأییدشده",
    "CONFLICT": "تعارض", "CONTAINER": "کانتینر", "CONTROL": "کنترل",
    "CONVERSION": "تبدیل", "COT": "کوتاژ", "COTAGE": "کوتاژ", "COUNT": "تعداد",
    "COVERAGE": "پوشش", "CRD": "اعتبارات", "CREDIT": "اعتبار",
    "CRITICAL": "بحرانی", "CRITICALITY": "بحرانی بودن", "CURRENCIES": "ارزها",
    "CURRENCY": "ارز", "CURRENT": "جاری", "CUSTOMER": "مشتری", "CUSTOMS": "گمرک",
    "DAILY": "روزانه", "DAMAGE": "خسارت", "DATA": "داده", "DATE": "تاریخ",
    "DATES": "تاریخ‌ها", "DAYS": "روز", "DEADLINE": "مهلت", "DECISION": "تصمیم",
    "DECLARED": "اظهارشده", "DELIVERY": "تحویل", "DEPARTMENT": "مدیریت",
    "DEPT": "مدیریت", "DESC": "شرح", "DESCRIPTION": "شرح", "DESCS": "شرح‌ها",
    "DEST": "مقصد", "DETAIL": "جزئیات", "DEVIATION": "انحراف",
    "DIFFERENTIAL": "تفاضلی", "DIMENSION": "بُعد", "DISCHARGE": "تخلیه",
    "DISCREPANCY": "مغایرت", "DISPLAY": "نمایشی", "DO": "ترخیصیه", "DOC": "کنترل اسناد",
    "DOCS": "اسناد", "DOMAIN": "دامنه", "DONE": "انجام‌شده", "DUE": "سررسید",
    "DUTY": "حقوق ورودی", "EFFECTIVE": "مؤثر", "EMAIL": "ایمیل", "EMP": "پرسنل",
    "EN": "انگلیسی", "ENFORCE": "اعمال", "ENTER": "ورود", "ENTRY": "ورود",
    "EQ": "معادل", "EQUIVALENT": "معادل", "EUR": "یورو", "EVENT": "رویداد",
    "EVENTTIME": "زمان رویداد", "EVIDENCE": "شاهد", "EXCHANGE": "صرافی",
    "EXCHANGES": "صرافی‌ها", "EXCLUDED": "مستثنا", "EXECUTION": "اجرا",
    "EXPERT": "کارشناس", "F": "F", "FA": "(فارسی)", "FIELDS": "فیلدها",
    "FILE": "فایل", "FIN": "مالی", "FINAL": "نهایی", "FIRST": "اولین", "FIX": "اصلاح",
    "FLAG": "علامت", "FLAGS": "علامت‌ها", "FLOOR": "کف", "FOCUS": "تمرکز",
    "FOR": "برای", "FORBIDDEN": "ممنوع", "FOREIGN": "خارجی", "FRAME": "فریم",
    "FROM": "از", "FULL": "کامل", "FUND": "وجه", "FUNDING": "تأمین وجه", "FX": "ارزی",
    "GAP": "شکاف", "GAPS": "شکاف‌ها", "GOODS": "کالا", "GRADE": "درجه",
    "GROSS": "ناخالص", "GROUP": "گروه", "GUARD": "محافظ", "HEAD": "رئیس",
    "HEALED": "ترمیم‌شده", "HINT": "راهنما", "HINTS": "راهنماها", "HISTORY": "سابقه",
    "HS": "تعرفه", "HUMAN": "انسانی", "ID": "شناسه", "IKCO": "ایران خودرو",
    "IL": "مجوز ورود", "IMPACT": "اثر", "IN": "در", "INITIAL": "اولیه",
    "INSTRUMENT": "ابزار", "INV": "فاکتور", "INVARIANT": "ثابت", "INVENTORY": "موجودی",
    "INVOICE": "فاکتور", "ITEM": "قلم", "ITEMS": "اقلام", "KEY": "کلید",
    "KEYS": "کلیدها", "KIND": "نوع", "KNOWLEDGE": "دانش", "KPI": "KPI",
    "LAG": "تأخیر", "LAST": "آخرین", "LC": "اعتبار اسنادی", "LEGACY": "قدیمی",
    "LEGAL": "قانونی", "LEVEL": "سطح", "LICENSE": "مجوز", "LIFECYCLE": "چرخه ارز",
    "LINE": "ردیف", "LINEAGE": "تبار", "LIST": "فهرست", "LOAD": "بارگیری",
    "LOCATION": "مکان", "LOGISTICS": "لجستیک", "LOWER": "پایین", "MANAGER": "مدیر",
    "MATCH": "تطبیق", "MATERIAL": "متریال", "MATERIALS": "متریال‌ها",
    "MEANING": "معنی", "METHOD": "روش", "MFR": "سازنده", "MINUS": "منهای",
    "MISSING": "مفقود", "MODE": "روش", "MOGH": "کارشناسان", "MOGHAVEMAT": "مقاومت",
    "MONEY": "پول", "MULTI": "چندگانه", "NATIVE": "به ارز اصلی", "NEED": "نیاز",
    "NEGATIVE": "منفی", "NEXT": "بعدی", "NO": "شماره", "NOT": "نه", "NOTE": "یادداشت",
    "NTSW": "NTSW", "NUMERIC": "عددی", "OBLIGATION": "تعهد",
    "OBSERVATION": "مشاهده", "OBSERVED": "مشاهده‌شده", "OF": "از", "ON": "روی",
    "OPEN": "باز", "ORACLE": "اوراکل", "ORC": "اوراکل", "ORDER": "سفارش",
    "ORDERS": "سفارش‌ها", "ORG": "سازمان", "OUT": "خروج", "OUTFLOW": "خروجی",
    "OWNER": "مالک", "PACK": "بسته‌بندی", "PAID": "پرداخت‌شده", "PART": "قطعه",
    "PARTIAL": "جزئی", "PARTITION": "بخش", "PARTS": "قطعات", "PATH": "مسیر",
    "PAY": "پرداخت", "PAYLOAD": "محتوا", "PAYMENT": "پرداخت", "PCT": "(٪)",
    "PER": "به ازای", "PERMITTED": "مجاز", "PI": "پیش‌فاکتور", "PLANNED": "برنامه‌ای",
    "PLANNING": "برنامه‌ریزی", "PO": "سفارش خرید", "POPULATION": "جامعه",
    "POSITION": "موقعیت", "POSSIBLE": "ممکن", "PR": "درخواست خرید",
    "PREPAYMENT": "پیش‌پرداخت", "PRESENT": "موجود", "PRIMARY": "اصلی",
    "PRIORITY": "اولویت", "PROCESS": "فرایند", "PROFORMA": "پروفرم",
    "PROGRESS": "پیشرفت", "PROVENANCE": "منشأ", "PRS": "درخواست‌های خرید",
    "PURCHASE": "خرید", "PURCHASED": "خریداری‌شده", "PURCHASING": "خرید",
    "QTY": "مقدار", "QUEUE": "صف", "RANK": "رتبه", "RATE": "نرخ",
    "RATIONALE": "استدلال", "RAW": "خام", "READY": "آماده", "REALLOCATION": "جابه‌جایی",
    "REASON": "دلیل", "RECEIPT": "رسید", "RECEIVED": "دریافت‌شده", "RECON": "تطبیق",
    "RECORD": "رکورد", "REF": "مرجع", "REFERENCE": "مرجع", "REG": "ثبت سفارش",
    "REGISTRATION": "ثبت سفارش", "REJECTED": "ردشده", "RELATION": "رابطه",
    "RELEASE": "آزادسازی", "RELEASED": "آزادشده", "REMAINING": "باقی‌مانده",
    "REMARK": "توضیح", "REPORTED": "گزارش‌شده", "REQ": "درخواست",
    "REQUEST": "درخواست", "REQUESTED": "درخواستی", "REQUESTS": "درخواست‌ها",
    "REQUIRED": "لازم", "REQUIREMENTS": "الزامات", "RESOURCE": "منبع",
    "RETURNED": "برگشتی", "REVIEW": "بازبینی", "REWORK": "دوباره‌کاری", "RIAL": "ریال",
    "RISK": "ریسک", "ROLE": "نقش", "ROOT": "ریشه", "ROUTE": "مسیر", "ROW": "ردیف",
    "ROWS": "ردیف‌ها", "RULE": "قاعده", "SAPCO": "ساپکو", "SATA": "ساتا",
    "SCHEDULED": "برنامه‌ریزی‌شده", "SCOPE": "حوزه", "SCORE": "امتیاز",
    "SEGMENT": "سگمنت", "SEMANTIC": "معنایی", "SENT": "ارسال‌شده",
    "SETTLEMENT": "رفع تعهد", "SEVERITY": "شدت", "SHARE": "سهم", "SHEET": "شیت",
    "SHIP": "حمل", "SHIPMENT": "حمل", "SHIPPED": "حمل‌شده", "SIGNAL": "سیگنال",
    "SKIPPED": "جاافتاده", "SORT": "ترتیب", "SORTING": "مرتب‌سازی", "SOURCE": "منبع",
    "STAGE": "مرحله", "STAGES": "مراحل", "STATE": "وضعیت", "STATUS": "وضعیت",
    "STOCK": "موجودی", "SUBJECT": "موضوع", "SUBMIT": "ارسال", "SUGGESTED": "پیشنهادی",
    "SUM": "جمع", "SUPPLIER": "سازنده", "SUPPLY": "تأمین", "SUSPECT": "مشکوک",
    "SWIFT": "سوئیفت", "SYSTEM": "سیستم", "TAGS": "برچسب‌ها", "TERMINAL": "پایانی",
    "THROUGHPUT": "زمان عبور", "TIME": "زمان", "TITLE": "عنوان", "TO": "تا",
    "TONE": "لحن", "TOTAL": "کل", "TRACE": "ردپا", "TRACKING": "رهگیری",
    "TRANSIT": "راه", "TRANSPORT": "حمل", "TRIP": "سفر", "TRUST": "اعتماد",
    "TYPE": "نوع", "UNAUTHORIZED": "غیرمجاز", "UNIT": "واحد", "UNKNOWN": "نامعلوم",
    "UNMEASURED": "اندازه‌گیری‌نشده", "UNSHIPPED": "حمل‌نشده", "USE": "کاربرد",
    "VALIDITY": "اعتبار", "VALUE": "ارزش", "VARIANCE": "واریانس", "VARIANT": "واریانت",
    "VENDOR": "فروشنده", "VESSEL": "کشتی", "VICE": "معاونت", "VOYAGE": "سفر دریایی",
    "WAIT": "انتظار", "WAITING": "منتظر", "WAREHOUSE": "انبار", "WAVG": "میانگین وزنی",
    "WH": "انبار", "WHEN": "زمان", "WHERE": "مکان", "WHO": "چه کسی",
    "WITHOUT": "بدون", "WORKFLOW": "گردش کار", "YEAR": "سال",
    # SAP / HR و سایر سورس‌ها
    "ACCT": "حساب", "ASSIGNMENT": "تخصیص", "BY": "توسط", "CAT": "دسته", "CATEGORY": "دسته",
    "CHANGED": "تغییر", "COMMISSION": "کمیسیون", "COMPARISON": "مقایسه", "COMPLETED": "تکمیل‌شده",
    "CREATED": "ایجاد", "DELETION": "حذف", "DENOMINATOR": "مخرج", "DESIRED": "مطلوب", "DOCUMENT": "سند",
    "FRAMEWORK": "چارچوب", "GR": "رسید کالا", "HEADER": "سربرگ", "HR": "منابع انسانی", "INACTIVE": "غیرفعال",
    "IND": "نشانگر", "INFO": "اطلاعات", "LANGUAGE": "زبان", "LETTER": "نامه", "MANUFACTURER": "سازنده",
    "MATCHED": "منطبق", "MPN": "شماره فنی سازنده", "NAME": "نام", "NET": "خالص", "NON": "غیر",
    "NOTIFICATION": "اعلان", "OFFICE": "اداره", "ORDERED": "سفارش‌شده", "OUR": "ما", "OVERALL": "کلی",
    "PACKED": "بسته‌بندی‌شده", "PGR": "گروه خرید", "PLANT": "کارخانه", "POST": "پست سازمانی", "PRICE": "قیمت",
    "PROCESSING": "پردازش", "PROFILE": "پروفایل", "PURCH": "خرید", "REC": "دریافت", "REQUISITION": "درخواست خرید",
    "REQUISITIONER": "درخواست‌کننده", "RESPONSIBLE": "مسئول", "RFQ": "استعلام", "SAP": "SAP", "SECTION": "بخش",
    "SHORT": "کوتاه", "STORAGE": "انبارش", "STRATEGY": "راهبرد", "SUPERVISOR": "سرپرست", "TARGET": "هدف",
    "TASK": "وظیفه", "TEXT": "متن", "UOM": "واحد سنجش", "VALUATED": "ارزش‌گذاری‌شده", "VALUATION": "ارزش‌گذاری",
    "YOUR": "شما",
}

#: توکن‌هایی که در فارسی باید در انتها بمانند (پسوند توضیحی)
_TAIL = {"PCT", "FA", "DAYS", "UNKNOWN", "NUMERIC", "DISPLAY"}
_TAIL_FA = {"DAYS": "(روز)"}


def fa_from_key(key: str) -> str:
    """``BL_DISCHARGE_DATE`` ← «تاریخ تخلیه بارنامه»."""
    toks = [t.upper() for t in str(key).strip("_").split("_") if t]
    if not toks:
        return str(key)
    question = False
    if "IS" in toks:
        i = toks.index("IS")
        question = not (i + 1 < len(toks) and toks[i + 1] == "UNKNOWN")
        toks = toks[:i] + toks[i + 1:]
    tail = []
    while toks and toks[-1] in _TAIL and len(toks) > 1:
        tail.insert(0, toks.pop())
    # یکی‌کردن عبارت‌های چندتوکنی (بلندترین تطبیق اول)
    units: List[str] = []
    i = 0
    longest = max(len(k) for k in PHRASES_FA)
    while i < len(toks):
        for n in range(min(longest, len(toks) - i), 0, -1):
            ph = tuple(toks[i:i + n])
            if ph in PHRASES_FA:
                units.append(PHRASES_FA[ph])
                i += n
                break
        else:
            t = toks[i]
            units.append(TOKEN_FA.get(t, t))
            i += 1
    words = list(reversed(units))
    # کسره اضافه نوشتاری: «مبنا ارزش» ← «مبنای ارزش»، «شکاف‌ها شاهد» ← «شکاف‌های شاهد»
    for j in range(len(words) - 1):
        if words[j].endswith("ا") and not words[j].endswith(")"):
            words[j] += "ی"
    words += [_TAIL_FA.get(t, TOKEN_FA.get(t, t)) for t in tail]
    out: List[str] = []
    for w in words:                      # «ترخیص ترخیص» ← «ترخیص»
        if not out or out[-1] != w:
            out.append(w)
    text = " ".join(out)
    return text + "؟" if question else text
