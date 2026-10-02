# -*- coding: utf-8 -*-
"""گزارش جداگانه «حمل و ترخیص» — یک مدل برای Studio، HTML ارسالی و Excel.

این ماژول محاسبه تازه‌ای برای شاهدها نمی‌سازد:

* پرونده هر بارنامه (تاریخ‌های ورود، تخلیه، ترخیصیه، کوتاژ، ترخیص کامل، مغایرت
  شاهدها، دادهٔ لازم و اقدام پیشنهادی) از :func:`gsi.report.shipping_insights.build_shipping_insights`
  می‌آید؛
* وضعیت ترخیص با همان پرچم‌های مارت (``IS_FULL_CLEARED`` / ``IS_PARTIAL_CLEARED``)
  خوانده می‌شود که بخش «ترخیص» چرخه ارز (:func:`gsi.report.fx_html.clearance_frame`)
  می‌خواند، به‌علاوه شاهد تاریخ ترخیص؛
* شمار بارنامه همیشه شمار **یکتای** بارنامه است (``gsi.studio_core.grain.unique_count``)،
  نه شمار ردیف؛ جدول اصلی یک ردیف برای هر سفارش × متریال دارد و ردیف بارنامه تکرار می‌شود.

قواعد:

* نامعلوم هرگز صفر نیست: مدتی که یکی از دو تاریخش نیست حساب نمی‌شود و شمار
  بارنامه‌های بی‌تاریخ کنارش گفته می‌شود؛ قاب خالی پیام صریح «داده نیست» دارد.
* هیچ منبعی نمی‌گوید کدام بارنامه کدام متریال را حمل کرده است؛ بارنامه به سفارش
  وصل است. پس ستون متریال همیشه «متریال‌های سفارش‌های این بارنامه» است.
* بارنامه بحرانی است اگر دست‌کم یکی از سفارش‌هایش بحرانی باشد (سطوح
  ``critical_board.DEFAULT_LEVELS``)؛ بی‌ستون بحرانی ← «نامعلوم»، نه «خیر».
* تاریخ‌ها در نمایش شمسی‌اند (``1405/06/10``)؛ مدت‌ها به روز.
"""
from __future__ import annotations

import html
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

from ..core.jalali import CalendarEngine, format_jalali
from ..design import icons as I
from ..design import brand as _BRAND
from ..design import tokens as T
from ..i18n import columns as C
from ..studio_core.grain import unique_count
from . import critical_board as CB
from . import fx_html as H
from . import fx_insight as X
from . import shipping_journey as J
from .shipping_insights import build_shipping_insights

FA, EN = C.FA, C.EN
XLSX_MIME = H.XLSX_MIME

# ═══════════════════════════════ برچسب‌ها ═══════════════════════════════
ST_TRANSIT = "در راه (بدون شاهد ورود)"
ST_ARRIVED = "رسیده، ترخیص‌نشده"
ST_PARTIAL = "ترخیص جزئی"
ST_FULL = "ترخیص کامل"
STATUSES = (ST_TRANSIT, ST_ARRIVED, ST_PARTIAL, ST_FULL)
STATUS_TONE = {ST_TRANSIT: "neutral", ST_ARRIVED: "critical", ST_PARTIAL: "warning", ST_FULL: "good"}

YES, NO, UNKNOWN = "بله", "خیر", "نامعلوم"

#: دسته‌های «روز پس از تخلیه» برای بارنامه‌های بدون ترخیص کامل
AGE_BUCKETS: List[tuple] = [("۰ تا ۷ روز", 0, 7), ("۸ تا ۱۴ روز", 8, 14), ("۱۵ تا ۳۰ روز", 15, 30),
                            ("۳۱ تا ۶۰ روز", 31, 60), ("بیش از ۶۰ روز", 61, None)]
AGE_NO_DATE = "تاریخ تخلیه قطعی نیست"
AGE_FUTURE = "تخلیه پس از تاریخ مرجع"

#: مدت‌های مرحله‌ای: (برچسب، ستون شروع، ستون پایان) روی پرونده بارنامه
DURATIONS: List[tuple] = [
    ("ورود تا دریافت ترخیصیه", "ورود", "دریافت ترخیصیه"),
    ("تخلیه تا کوتاژ", "تخلیه", "کوتاژ"),
    ("تخلیه تا ترخیص کامل", "تخلیه", "ترخیص کامل"),
]
#: پله‌های قیف شاهد به ترتیب جریان
FUNNEL = ["ورود", "تخلیه", "دریافت ترخیصیه", "کوتاژ", "ترخیص جزئی", "ترخیص کامل"]
DATE_COLS = FUNNEL

MATS_OF_BL_ORDERS = "متریال‌های سفارش‌های این بارنامه"
CRIT_MATS_OF_BL_ORDERS = "متریال‌های بحرانی سفارش‌های این بارنامه"
FILTER_DATE = "_FILTER_DATE"   # تاریخ مبنای فیلتر بازه (تخلیه، وگرنه ورود)؛ شمسی
WAIT = "روز پس از تخلیه (بدون ترخیص کامل)"

DOSSIER_COLS = [
    "بارنامه", "وضعیت ترخیص", "بحرانی", "بدترین سطح بحرانی سفارش‌ها", "سفارش‌ها", "ثبت سفارش‌ها",
    "روش حمل", "کشتی", "شماره سفر", "ورود", "تخلیه", "دریافت ترخیصیه", "کوتاژ", "ترخیص جزئی",
    "ترخیص کامل", WAIT, "شماره کوتاژ", "گمرک مقصد", "کارشناس ترخیص", CRIT_MATS_OF_BL_ORDERS,
    "شمار متریال سفارش‌ها", "کمبود داده", "مغایرت شواهد", "اقدام پیشنهادی",
]
FOLLOW_COLS = [
    "بارنامه", WAIT, "وضعیت ترخیص", "بحرانی", "بدترین سطح بحرانی سفارش‌ها", "سفارش‌ها",
    "کارشناس سفارش‌ها", "مدیریت/اداره سفارش‌ها", "کارشناس ترخیص", "تخلیه", "دریافت ترخیصیه",
    "کوتاژ", "کمبود داده", "اقدام پیشنهادی",
]
DURATION_COLS = ["مرحله", "روش حمل", "بارنامه", "دارای هر دو تاریخ", "میانه (روز)", "بیشینه (روز)",
                 "بدون تاریخ شروع", "بدون تاریخ پایان", "فاصله منفی (کنار گذاشته)"]
GAP_COLS = ["بارنامه", "وضعیت ترخیص", "مغایرت شواهد", "کمبود داده", "شمار ردیف منبع"]
COVERAGE_COLS = ["شاهد", "بارنامه", "دارای شاهد", "متعارض", "بدون شاهد", "پوشش (٪)"]

# ── R10 (مالک، ۱۴۰۵/۰۷/۰۸): پارت‌های فایل کارشناسان، حتی بی‌بارنامه ──
#: UNRECOGNIZED: Order Status پر ولی ناشناخته؛ بیرون گذاشتنش ردیف به‌روز را بی‌صدا پنهان می‌کرد
EXP_STATES = ("IN_CUSTOMS", "IN_TRANSIT", "READY", "AT_SUPPLIER", "UNRECOGNIZED")
EXP_STATE_FA = {"IN_CUSTOMS": "در گمرک", "IN_TRANSIT": "در راه", "READY": "آماده حمل", "AT_SUPPLIER": "نزد سازنده",
                "UNRECOGNIZED": "وضعیت ناشناخته"}
EXP_BL_TRACKED = "در پیگیری حمل"
EXP_BL_EXPERT_ONLY = "فقط در فایل کارشناسان"
EXP_BL_NONE = "بدون بارنامه"
EXP_BL_SUSPECT = "بارنامه ناقص یا مشکوک"
EXP_COLS = ["وضعیت پارت (کارشناس)", "Order Status", "سفارش", "متریال", "شرح", "شماره پارت", "مقدار پارت", "ترخیص‌شده (کارشناس)",
            "واحد", "بارنامه", "بارنامه در گزارش حمل", "روش حمل", "شماره حمل", "حمل‌کننده", "تاریخ برنامه حمل",
            "تاریخ ابلاغ PO", "مرحله (کارشناس)", "یادداشت لجستیک", "سطح بحرانی", "کارشناس", "نقص داده (کدام فایل)"]
NOTE_EXPERT = ("هر ردیف یک ردیف پارت فایل کارشناسان (Commercial Expert Data) با وضعیت نزد سازنده، آماده حمل، در راه "
               "یا در گمرک است؛ ردیف بی‌بارنامه هم هست. Order Status ناشناخته هم با «وضعیت ناشناخته» می‌آید (واژه را به "
               "status_lexicon.yaml اضافه کنید). «بارنامه در گزارش حمل» می‌گوید آیا همان بارنامه در فایل‌های "
               "حمل و ترخیص هم آمده است. مقدارها جمع زده نمی‌شوند چون واحد متریال‌ها یکی نیست. فیلتر تاریخ این جدول "
               "روی تاریخ برنامه حمل است (وگرنه تاریخ ابلاغ PO).")
NOTE_EXPERT_MISSING = ("Snapshot پارت‌های فایل کارشناسان را ندارد؛ یک بار Refresh کنید تا این جدول از فایل "
                       "کارشناسان پر شود.")

#: مبنای فیلتر تاریخ (برچسب ← ستون جدول‌های دانه بارنامه)؛ جدول پارت‌ها همیشه تاریخ خودش را دارد
DATE_BASES = {"تخلیه، وگرنه ورود": "_FILTER_DATE", "ورود": "ورود", "تخلیه": "تخلیه",
              "دریافت ترخیصیه": "دریافت ترخیصیه", "کوتاژ": "کوتاژ", "ترخیص جزئی": "ترخیص جزئی",
              "ترخیص کامل": "ترخیص کامل"}
BASIS_KEYS = list(DATE_BASES)
NOTE_JOURNEY = ("هر خانه یک ایستگاه مسیر بارنامه است با حالت شاهد و نام فایل و تاریخ. عبور ضمنی فقط وقتی است که "
                "منطقاً قطعی باشد (مثل ترخیص بدون ورود ممکن نیست) و تاریخ ندارد؛ تاریخ‌های متفاوت «متعارض» است و "
                "هیچ‌کدام برگزیده نمی‌شود. ترخیص فقط با پرچم ترخیص. رسید انبار SAP فقط وقتی به بارنامه نسبت داده "
                "می‌شود که سفارش‌هایش تنها همین بارنامه را داشته باشند.")
NOTE_SHAPLEY = ("سهم هر فایل با ارزش شپلی بازی پوشش: هر خانه بارنامه × ایستگاه میان فایل‌هایی که شاهدش هستند برابر "
                "تقسیم می‌شود. «خانه با تنها یک منبع» جایی است که اگر آن فایل نباشد وضعیت دوباره مبهم می‌شود. "
                "سهم داده است، نه ارزیابی افراد.")
NOTE_FLOW = ("گذار مستقیم از ترتیب تاریخ ایستگاه‌های تاریخ‌دار هر بارنامه؛ شمار بارنامه و میانه/بیشینه روز. "
             "توصیفی است؛ مهلت و علت از آن استنتاج نمی‌شود.")
NOTE_FILTER_SCOPE = ("بازه تاریخ روی کل گزارش است: کارت‌ها و جدول‌ها فقط بارنامه‌ها و پارت‌های داخل بازه را "
                     "می‌شمارند. ردیف بی‌تاریخ بیرون می‌ماند مگر تیک «ردیف‌های بی‌تاریخ هم باشند» زده شود.")
NOTE_FILTER_HTML = ("در این فایل HTML کارت‌های شمار و جدول‌ها با فیلتر به‌روز می‌شوند؛ قیف مراحل و مدت‌ها برای کل "
                    "دامنه است (در Studio با فیلتر دوباره ساخته می‌شوند).")

#: ترجمه انگلیسی متن‌های همین گزارش؛ متنی که اینجا نیست به ``columns.phrase`` می‌رود
EN_TEXT: Dict[str, str] = {
    ST_TRANSIT: "In transit (no arrival evidence)", ST_ARRIVED: "Arrived, not cleared",
    ST_PARTIAL: "Partially cleared", ST_FULL: "Fully cleared",
    YES: "Yes", NO: "No", UNKNOWN: "Unknown",
    "۰ تا ۷ روز": "0-7 days", "۸ تا ۱۴ روز": "8-14 days", "۱۵ تا ۳۰ روز": "15-30 days",
    "۳۱ تا ۶۰ روز": "31-60 days", "بیش از ۶۰ روز": "Over 60 days",
    AGE_NO_DATE: "No definite discharge date", AGE_FUTURE: "Discharge after reference date",
    "ورود تا دریافت ترخیصیه": "Arrival to delivery order", "تخلیه تا کوتاژ": "Discharge to cotage",
    "تخلیه تا ترخیص کامل": "Discharge to full clearance",
    "ورود": "Arrival", "تخلیه": "Discharge", "دریافت ترخیصیه": "Delivery order (DO)", "کوتاژ": "Cotage",
    "ترخیص جزئی": "Partial clearance", "ترخیص کامل": "Full clearance",
    MATS_OF_BL_ORDERS: "Materials of this B/L's orders",
    CRIT_MATS_OF_BL_ORDERS: "Critical materials of this B/L's orders",
    WAIT: "Days since discharge (not fully cleared)",
    "بارنامه": "B/L", "وضعیت ترخیص": "Clearance status", "بحرانی": "Critical",
    "بدترین سطح بحرانی سفارش‌ها": "Worst criticality of orders", "سفارش‌ها": "Orders",
    "ثبت سفارش‌ها": "Registrations", "روش حمل": "Transport mode", "کشتی": "Vessel", "شماره سفر": "Voyage no.",
    "شماره کوتاژ": "Cotage no.", "گمرک مقصد": "Destination customs", "کارشناس ترخیص": "Clearance expert",
    "شمار متریال سفارش‌ها": "Materials of the orders", "کمبود داده": "Missing data",
    "مغایرت شواهد": "Conflicting evidence", "اقدام پیشنهادی": "Suggested action",
    "کارشناس سفارش‌ها": "Order experts", "مدیریت/اداره سفارش‌ها": "Order departments",
    "مرحله": "Stage", "دارای هر دو تاریخ": "With both dates", "میانه (روز)": "Median (days)",
    "بیشینه (روز)": "Max (days)", "بدون تاریخ شروع": "Missing start date", "بدون تاریخ پایان": "Missing end date",
    "فاصله منفی (کنار گذاشته)": "Negative gap (excluded)", "شمار ردیف منبع": "Source rows",
    "شاهد": "Evidence", "دارای شاهد": "With evidence", "متعارض": "Conflicting", "بدون شاهد": "Without evidence",
    "پوشش (٪)": "Coverage (%)", "همه روش‌ها": "All modes", "نامشخص": "Unknown",
    "حمل و ترخیص": "Shipping and customs clearance",
    "گزارش حمل و ترخیص": "Shipping and customs clearance report",
    "بارنامه · حمل · گمرک · ترخیص": "B/L · shipping · customs · clearance",
    "نمای کلی": "Overview", "مراحل و مدت‌ها": "Stages and durations", "پرونده بارنامه‌ها": "B/L dossiers",
    "پیگیری ترخیص": "Clearance follow-up", "پوشش و کمبود داده": "Coverage and data gaps",
    "بارنامه یکتا": "Unique B/Ls", "بارنامه در راه": "B/Ls in transit",
    "رسیده، ترخیص‌نشده ": "Arrived, not cleared",
    "بارنامه بحرانی ترخیص‌نشده": "Critical B/Ls not fully cleared",
    "بارنامه با مغایرت شاهد": "B/Ls with conflicting evidence",
    "روز پس از تخلیه در بارنامه‌های بدون ترخیص کامل": "Days since discharge, B/Ls not fully cleared",
    "قیف شاهد مراحل (بارنامه یکتا)": "Stage evidence funnel (unique B/Ls)",
    "مدت هر مرحله به تفکیک روش حمل": "Stage durations by transport mode",
    "پرونده هر بارنامه": "One dossier per B/L", "فهرست پیگیری ترخیص": "Clearance follow-up list",
    "پوشش شواهد": "Evidence coverage", "بارنامه‌های دارای کمبود یا مغایرت": "B/Ls with gaps or conflicts",
    "تاریخ مرجع": "Reference date", "سفارش": "Orders", "ثبت سفارش": "Registrations",
    "داده‌ای نیست": "No data",
    "خلاصه": "Summary", "پرونده بارنامه": "BL dossiers", "پیگیری": "Follow-up", "مدت‌ها": "Durations",
    "کمبود داده ": "Data gaps", "فیلد": "Field", "مقدار": "Value",
    "جستجو در جدول‌ها": "Search tables", "از تاریخ": "From date", "تا تاریخ": "To date",
    "ردیف‌های بی‌تاریخ هم باشند": "Include rows without a date", "ردیف نمایش داده شده": "rows shown",
    "پاک کردن": "Clear",
    "دانلود Excel حمل و ترخیص": "Download shipping & clearance Excel",
    "نکته": "Note",
    "وضعیت پارت (کارشناس)": "Part status (expert)", "متریال": "Material", "شرح": "Description",
    "شماره پارت": "Part no.", "مقدار پارت": "Part quantity", "ترخیص‌شده (کارشناس)": "Cleared (expert)",
    "واحد": "Unit", "بارنامه در گزارش حمل": "B/L in shipping sources", "شماره حمل": "Transport no.",
    "حمل‌کننده": "Carrier", "تاریخ برنامه حمل": "Scheduled shipment", "تاریخ ابلاغ PO": "PO sent date",
    "مرحله (کارشناس)": "Stage (expert)", "یادداشت لجستیک": "Logistics note", "سطح بحرانی": "Criticality",
    "کارشناس": "Expert", "نقص داده (کدام فایل)": "Data gap (which file)",
    "در گمرک": "In customs", "در راه": "In transit", "آماده حمل": "Ready to ship", "نزد سازنده": "At supplier",
    EXP_BL_TRACKED: "In shipping sources", EXP_BL_EXPERT_ONLY: "Only in the experts' file",
    EXP_BL_NONE: "No B/L", "پارت‌های کارشناسان": "Expert shipments", EXP_BL_SUSPECT: "Incomplete or suspect B/L",
    "وضعیت ناشناخته": "Unrecognised status", "پارت با وضعیت ناشناخته": "Shipments with unrecognised status",
    "پارت‌های کارشناسان (نزد سازنده تا گمرک)": "Expert shipments (at supplier to customs)",
}

#: یادداشت‌های ثابت گزارش (فارسی ← انگلیسی)
NOTE_GRAIN = ("همه شمارها شمار بارنامه یکتاست، نه ردیف. بارنامه به سفارش وصل است؛ هیچ منبعی نمی‌گوید "
              "کدام بارنامه کدام متریال را حمل کرده، پس ستون متریال «متریال‌های سفارش‌های این بارنامه» است.")
NOTE_DURATION = ("مدت فقط وقتی حساب می‌شود که هر دو تاریخ باشد و تاریخ متعارض کنار گذاشته می‌شود. فاصله منفی "
                 "(پایان پیش از شروع) در میانه و بیشینه نمی‌آید و جدا شمرده می‌شود. زمان خام علت، تقصیر یا "
                 "هزینه دموراژ را ثابت نمی‌کند.")
NOTE_CRITICAL = ("بارنامه بحرانی است اگر دست‌کم یکی از سفارش‌هایش متریال بحرانی داشته باشد "
                 "(توقف خط، بحرانی، در حال بحرانی شدن).")
NOTE_FILTER = ("مبنای پیش‌فرض بازه تاریخ، تاریخ تخلیه (و اگر نیست، تاریخ ورود) هر بارنامه است و از «مبنای تاریخ» "
               "عوض می‌شود؛ پارت‌های کارشناسان با تاریخ برنامه حمل (وگرنه تاریخ ابلاغ PO) فیلتر می‌شوند. تاریخ "
               "شمسی مثل 1405/01/01.")
NOTE_FOLLOW = ("بارنامه‌های بدون ترخیص کامل، به ترتیب بیشترین روز پس از تخلیه؛ کارشناس و مدیریت از سفارش‌های همان "
               "بارنامه می‌آید. بارنامه بی‌تاریخ تخلیه آخر فهرست است.")
NOTE_COVERAGE = ("مخرج هر ردیف شمار بارنامه یکتای همین دامنه است؛ تاریخ متعارض «دارای شاهد» شمرده نمی‌شود و هیچ "
                 "مقداری از میان شاهدهای متعارض انتخاب نمی‌شود.")
NOTE_GAPS = "کمبود داده و مغایرت شاهد هر بارنامه؛ هیچ مقداری از میان شاهدهای متعارض انتخاب نمی‌شود."
NOTE_NO_BL = "سفارش در این دامنه هنوز هیچ بارنامه‌ای ندارد و در جدول‌های این گزارش نیست."
NOTE_EMPTY = "در این دامنه بارنامه‌ای با شاهد حمل یا ترخیص نیست؛ هیچ عددی ساخته نشد."
NOTE_LEGAL = ("این گزارش از همان Snapshot منتشرشده ساخته شده و به هیچ منبع بیرونی وصل نمی‌شود. «—» یعنی شاهد "
              "نیست، نه صفر. فری‌تایم قراردادی و هزینه دموراژ از این داده استنتاج نمی‌شود.")
EN_TEXT.update({
    NOTE_FOLLOW: ("B/Ls not fully cleared, longest time since discharge first; expert and department come from "
                  "the orders on that B/L. B/Ls without a discharge date are listed last."),
    NOTE_COVERAGE: ("The denominator is the number of unique B/Ls in this scope; a conflicting date is not counted "
                    "as evidence and no value is picked among conflicting evidence."),
    NOTE_GAPS: "Missing data and conflicting evidence per B/L; no value is picked among conflicting evidence.",
    NOTE_NO_BL: "orders in this scope have no B/L yet and are not in this report's tables.",
    "ردیف دیگر در فایل Excel": "more rows in the Excel file",
    "بارنامه‌های بدون ترخیص کامل، به ترتیب بیشترین روز پس از تخلیه.":
        "B/Ls not fully cleared, longest time since discharge first.",
    "مخرج: شمار بارنامه یکتای همین دامنه.": "Denominator: unique B/Ls in this scope.",
    "سفارش بارنامه": "Orders of the B/L", "سطح بحرانی سفارش‌ها": "Criticality of the orders",
    "پرچم ترخیص کامل بدون تاریخ": "Full-clearance flag without a date",
    "تاریخ ترخیص کامل بدون پرچم ترخیص کامل": "Full-clearance date without a full-clearance flag",
    "تاریخ ترخیص جزئی بدون پرچم ترخیص جزئی": "Partial-clearance date without a partial-clearance flag",
    "بدون اقدام ترخیص؛ بایگانی پرونده": "No clearance action; archive the dossier",
    "بدون اقدام ترخیص؛ تطبیق شاهدهای متعارض با اصل سند": "No clearance action; reconcile conflicting evidence with the source document",
    "دسته": "Bucket",
    # روش حمل (برچسب فارسی قواعد) و متن اقدام/کمبود build_shipping_insights
    "دریایی": "Sea", "هوایی": "Air", "زمینی (جاده‌ای)": "Road", "زمینی": "Road", "ریلی": "Rail",
    "چندوجهی": "Multimodal", "پست سریع / کوریر": "Courier",
    "تطبیق شاهدهای متعارض با اصل سند": "Reconcile conflicting evidence with the source document",
    "دریافت شاهد ورود/تخلیه از منبع حمل": "Obtain arrival/discharge evidence from the shipping source",
    "استعلام وضعیت دریافت ترخیصیه و تاریخ درخواست/پرداخت": "Ask for delivery-order status and request/payment date",
    "استعلام وضعیت ترخیص و فری‌تایم قراردادی": "Ask for clearance status and contractual free time",
    "هزینه قابل استنتاج نیست": "cost cannot be inferred",
    "بررسی خط زمانی": "Review the timeline",
    "علت و مسئولیت از زمان خام استنتاج نمی‌شود": "cause and responsibility are not inferred from elapsed time",
    "شاهد ترخیص کامل بدون تاریخ": "Full clearance evidenced without a date",
    "مبنای شاهد حرکت": "Movement evidence basis",
    NOTE_GRAIN: ("All counts are unique B/Ls, never rows. A B/L attaches to orders; no source says which B/L "
                 "carried which material, so the material column lists the materials of this B/L's orders."),
    NOTE_DURATION: ("A duration is computed only when both dates exist; conflicting dates are left out. Negative "
                    "gaps (end before start) are excluded from median and max and counted separately. Elapsed "
                    "time alone does not prove cause, fault or demurrage cost."),
    NOTE_CRITICAL: ("A B/L is critical when at least one of its orders has a critical material "
                    "(line stop, critical, becoming critical)."),
    NOTE_FILTER: ("By default the date range uses each B/L's discharge date (arrival date when discharge is "
                  "missing); change it with 'Date basis'. Expert shipments use the scheduled shipment date (else "
                  "the PO sent date). Jalali dates such as 1405/01/01."),
    NOTE_EMPTY: "No B/L with shipping or clearance evidence in this scope; no figures were produced.",
    NOTE_EXPERT: ("One row per shipment (part) row of the experts' file (Commercial Expert Data) at supplier, ready "
                  "to ship, in transit or in customs, including rows without a B/L. An unrecognised Order Status shows as "
                  "'Unrecognised status' (add the word to status_lexicon.yaml). 'B/L in shipping sources' says "
                  "whether that B/L also appears in the shipping and clearance files. Quantities are not summed "
                  "because units differ. This table's date filter uses the scheduled shipment date (else PO sent date)."),
    NOTE_EXPERT_MISSING: "The snapshot has no expert shipment rows; refresh once to fill this table.",
    NOTE_FILTER_SCOPE: ("The date range applies to the whole report: tiles and tables count only B/Ls and shipments "
                        "inside the range. Rows without a date are left out unless \"Include rows without a date\" "
                        "is ticked."),
    NOTE_FILTER_HTML: ("In this HTML file the count tiles and tables follow the filter; the stage funnel and "
                       "durations cover the whole scope (Studio rebuilds them with the filter)."),
    "مبنای تاریخ": "Date basis", "تخلیه، وگرنه ورود": "Discharge, else arrival",
    "پارت در گمرک": "Shipments in customs", "پارت در راه": "Shipments in transit",
    "پارت آماده حمل": "Shipments ready to ship", "پارت نزد سازنده": "Shipments at supplier",
    "پارت بی‌بارنامه": "Shipments without a B/L", "بارنامه فقط در فایل کارشناسان": "B/L only in the experts' file",
    "پارت": "shipments",
    **J.EN,
    NOTE_JOURNEY: ("Each cell is one station of the B/L's route with its evidence state, file name and date. 'Passed by "
                   "logic' is used only when it is certain (clearance is impossible without arrival) and has no date; "
                   "different dates are 'conflicting' and none is chosen. Clearance only from the clearance flag. An SAP "
                   "warehouse receipt is tied to a B/L only when its orders have that single B/L."),
    NOTE_SHAPLEY: ("Each file's share is its Shapley value in the coverage game: every B/L × station cell is split equally "
                   "among the files that evidence it. 'Cells with a single source' would become unclear without that "
                   "file. This is a share of data, not an assessment of people."),
    NOTE_FLOW: ("Directly-follows transitions from the date order of each B/L's dated stations, with B/L count and "
                "median/max days. Descriptive only; deadlines and causes are not inferred."),
    NOTE_LEGAL: ("Built from the same published snapshot, with no external resources. '—' means no evidence, "
                 "never zero. Contractual free time and demurrage cost are not inferred from this data."),
})


def t(text: Any, lang: str = FA) -> str:
    """متن رابط در زبان خواسته‌شده؛ فارسی دست نمی‌خورد."""
    s = X.s(text)
    if lang != EN or not s:
        return s
    if s in EN_TEXT:
        return EN_TEXT[s]
    return C.phrase(s, lang)


def L(text: Any, lang: str = FA) -> str:
    """برچسب escape‌شده؛ انگلیسی داخل ``<bdi>``."""
    out = html.escape(t(text, lang))
    return f"<bdi>{out}</bdi>" if lang == EN else out


# ═══════════════════════════════ کمکی ═══════════════════════════════
def _present(v: Any) -> bool:
    return X.s(v) not in ("", "—")


def _parse(v: Any) -> Optional[date]:
    try:
        return CalendarEngine.parse(v) if _present(v) else None
    except (TypeError, ValueError):
        return None


def _jal(iso: Any) -> str:
    """تاریخ ISO/شمسی ← شمسی؛ نبود ← رشته خالی."""
    d = _parse(iso)
    return format_jalali(d) if d else ""


def _uniq(values) -> List[str]:
    return X._uniq(values)


def _join(values, sep: str = "، ", limit: int = 0) -> str:
    vals = _uniq(values)
    if limit and len(vals) > limit:
        return sep.join(vals[:limit]) + f"{sep}… (+{len(vals) - limit})"
    return sep.join(vals)


def _col(df: pd.DataFrame, *names: str) -> pd.Series:
    return X._col(df, *names)


def _coalesce(df: pd.DataFrame, *names: str) -> pd.Series:
    """نخستین مقدار غیرخالی هر ردیف از میان ستون‌ها (به ترتیب)."""
    out = pd.Series([""] * len(df), index=df.index, dtype=object)
    for c in names:
        if c in df.columns:
            v = df[c].map(X.s)
            out = out.where(out.ne(""), v)
    return out


def _mode_label(code: Any) -> str:
    c = X.s(code)
    if not c or c == "نامشخص":
        return "نامشخص"
    try:
        from ..rulebook.loader import get_rulebook
        return get_rulebook().transport_mode_fa(c) or c
    except Exception:
        return c


def _one_date(part: pd.DataFrame, *cols: str) -> tuple:
    """(تاریخ یکتا، متعارض؟) از نخستین ستون موجود و دارای مقدار."""
    for c in cols:
        if c not in part.columns:
            continue
        vals = sorted({d for d in (_parse(v) for v in part[c]) if d is not None})
        if vals:
            return (vals[0], False) if len(vals) == 1 else (None, True)
    return None, False


# ═══════════════════════════════ مدل ═══════════════════════════════
@dataclass
class ShippingModel:
    """همه جدول‌های گزارش حمل و ترخیص؛ هر جدول در دانه بارنامه (به‌جز مدت‌ها و پوشش)."""
    ref_date: str
    as_of: Optional[date]
    dossiers: pd.DataFrame
    follow_up: pd.DataFrame
    durations: pd.DataFrame
    coverage: pd.DataFrame
    gaps: pd.DataFrame
    ages: pd.DataFrame
    counts: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    expert: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=EXP_COLS + ["_FILTER_DATE"]))
    journey: J.Journey = field(default_factory=J.empty_journey)

    @property
    def empty(self) -> bool:
        return self.dossiers.empty and self.expert.empty

    @property
    def total(self) -> int:
        return int(self.counts.get("total", 0))


def _empty_model(ref_date: str, as_of: Optional[date], notes: List[str]) -> ShippingModel:
    return ShippingModel(ref_date=ref_date, as_of=as_of, dossiers=pd.DataFrame(columns=DOSSIER_COLS + [FILTER_DATE]),
                         follow_up=pd.DataFrame(columns=FOLLOW_COLS + [FILTER_DATE]),
                         durations=pd.DataFrame(columns=DURATION_COLS), coverage=pd.DataFrame(columns=COVERAGE_COLS),
                         gaps=pd.DataFrame(columns=GAP_COLS + [FILTER_DATE]), ages=pd.DataFrame(columns=["دسته", "بارنامه"]),
                         counts={"total": 0}, notes=notes)


def _order_facts(frame: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """{سفارش: بحرانی؟، بدترین سطح، متریال‌ها، متریال‌های بحرانی، کارشناس‌ها، اداره‌ها} از **همه**
    ردیف‌های سفارش (نه فقط ردیف دارای بارنامه)؛ ردیف متریال افزوده بارنامه ندارد ولی مال همان سفارش است."""
    okey = _coalesce(frame, "CANONICAL_ORDER", "KEY_ORDER")
    has_crit_cols = any(c in frame.columns for c in ("ORDER_CRITICAL", "ORDER_CRITICAL_LEVEL", "کد طبقه بحرانی"))
    work = frame.assign(_O=okey)
    work = work[work["_O"].ne("")]
    out: Dict[str, Dict[str, Any]] = {}
    for o, g in work.groupby("_O", sort=False):
        mat_codes = _col(g, "کد طبقه بحرانی").map(X.s)
        mats = _col(g, "KEY_MATERIAL", "CANONICAL_PART_NO").map(X.s)
        crit_mats = [m for m, c in zip(mats, mat_codes) if m and c in CB.DEFAULT_LEVELS]
        level = X.worst_level(list(_col(g, "ORDER_CRITICAL_LEVEL")) + list(mat_codes))
        flag = any(X.truthy(v) for v in _col(g, "ORDER_CRITICAL"))
        known = has_crit_cols and (bool(level) or flag or
                                   any(X.s(v) for v in list(_col(g, "ORDER_CRITICAL")) + list(mat_codes)))
        out[o] = {"critical": (flag or level in CB.DEFAULT_LEVELS) if known else None,
                  "level": level, "materials": _uniq(mats), "critical_materials": _uniq(crit_mats),
                  "experts": _uniq(_col(g, "CANONICAL_EXPERT")), "depts": _uniq(_col(g, "ORG_DEPT"))}
    return out


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """قاب کاری برای ``build_shipping_insights``: کلید بارنامه، کلید سفارش و تاریخ کوتاژ یکدست.

    مارت منتشرشده ستون ``COT_DATE`` ندارد (s20 آن را نمی‌سازد) و تاریخ دریافت شماره کوتاژ در
    ``CL_COTAGE_DATE`` / ``COT_COTAGE_DATE`` است؛ فقط وقتی ``COT_DATE`` خالی است از آن‌ها پر می‌شود."""
    work = frame.copy()
    work["CANONICAL_BL"] = _coalesce(work, "CANONICAL_BL", "KEY_BL")
    work["CANONICAL_ORDER"] = _coalesce(work, "CANONICAL_ORDER", "KEY_ORDER")
    work["COT_DATE"] = _coalesce(work, "COT_DATE", "CL_COTAGE_DATE", "COT_COTAGE_DATE")
    return work


def _bucket(age: Optional[int], has_discharge: bool) -> str:
    if age is None:
        return AGE_FUTURE if has_discharge else AGE_NO_DATE
    for lab, lo, hi in AGE_BUCKETS:
        if age >= lo and (hi is None or age <= hi):
            return lab
    return AGE_NO_DATE


def build_model(df: Optional[pd.DataFrame], extras: Any = None, ref_date: Any = "") -> ShippingModel:
    """مدل گزارش حمل و ترخیص از مارت منتشرشده (دامنه‌خورده).

    ``extras`` فعلاً فقط برای هم‌امضایی با دیگر گزارش‌ها پذیرفته می‌شود؛ همه شاهدهای حمل و
    ترخیص در خود مارت‌اند. ``ref_date`` تاریخ مرجع Snapshot است (شمسی یا ISO)."""
    ref_text = X.s(ref_date)
    as_of = _parse(ref_text)
    notes: List[str] = []
    if as_of is None:
        as_of = date.today()
        notes.append(f"تاریخ مرجع معتبر نبود؛ روزهای انتظار تا امروز ({format_jalali(as_of)}) شمرده شد.")
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return _empty_model(ref_text, as_of, [NOTE_EMPTY] + notes)
    tracked = set(_coalesce(df, "CANONICAL_BL", "KEY_BL")) - {""}
    expert, exp_note = expert_frame(df, extras, tracked)
    if exp_note:
        notes.append(exp_note)
    if not ("CANONICAL_BL" in df.columns or "KEY_BL" in df.columns):
        return _with_expert(_empty_model(ref_text, as_of, [NOTE_EMPTY] + notes), expert)

    work = _prepare(df)
    bl_rows = work[work["CANONICAL_BL"].ne("")]
    total = unique_count(bl_rows, "CANONICAL_BL", blank_counts=False)
    if not total:
        return _with_expert(_empty_model(ref_text, as_of, [NOTE_EMPTY] + notes), expert)
    base, coverage = build_shipping_insights(bl_rows, as_of)
    orders = _order_facts(work)
    parts = {b: g for b, g in bl_rows.groupby("CANONICAL_BL", sort=False)}

    recs = []
    for _, r in base.iterrows():
        bl = X.s(r["بارنامه"])
        g = parts.get(bl, bl_rows.iloc[0:0])
        ords = [o for o in X.s(r["سفارش‌ها"]).split(" | ") if o]
        facts = [orders[o] for o in ords if o in orders]
        # ── بحرانی: هر سفارش بحرانی ← بارنامه بحرانی؛ بی‌سفارش ← پرچم خود ردیف بارنامه
        if facts:
            known = [f["critical"] for f in facts if f["critical"] is not None]
            crit = (any(known) if known else None)
            level = X.worst_level(f["level"] for f in facts)
        else:
            lv = X.worst_level(_col(g, "BL_CRITICAL_LEVEL"))
            flags = [X.truthy(v) for v in _col(g, "BL_CRITICAL") if X.s(v)]
            crit = (any(flags) or lv in CB.DEFAULT_LEVELS) if (flags or lv) else None
            level = lv
        crit_mats = _uniq(m for f in facts for m in f["critical_materials"])
        all_mats = _uniq(m for f in facts for m in f["materials"])
        # ── وضعیت ترخیص: پرچم مارت (همان fx_html.clearance_frame) یا شاهد تاریخ
        full_flag = any(X.truthy(v) for v in _col(g, "IS_FULL_CLEARED"))
        done_no_date = any(X.truthy(v) for v in _col(g, "CL_CLEAR_DONE_NO_DATE"))
        full_date = _parse(r["ترخیص کامل"])
        full_conflict = "ترخیص کامل" in X.s(r["مغایرت شواهد"])
        partial_date, partial_conflict = _one_date(g, "PARTIAL_CLEAR_DATE", "CL_PARTIAL_CLEAR_DATE", "COT_PARTIAL_DATE_1")
        partial_flag = any(X.truthy(v) for v in _col(g, "IS_PARTIAL_CLEARED"))
        arrived = any(_parse(v) for c in ("ARRIVAL_DATE", "DISCHARGE_DATE", "BL_DISCHARGE_DATE", "CL_ARRIVAL_DATE")
                      for v in _col(g, c))
        # R9: وضعیت فقط با پرچم ترخیص (همان بخش ترخیص چرخه ارز و تابلوی بحرانی)، تا سه گزارش یک
        # عدد بدهند. تاریخ «ترخیص کامل» مارت از آخرین تاریخ بارگیری فایل ترخیص هم پر می‌شود و بارگیری
        # در ترخیص جزئی هم رخ می‌دهد؛ تاریخ بدون پرچم «مغایرت شواهد» است، نه ترخیص کامل.
        if full_flag or done_no_date:
            status = ST_FULL
        elif partial_flag:
            status = ST_PARTIAL
        elif arrived:
            status = ST_ARRIVED
        else:
            status = ST_TRANSIT
        discharge = _parse(r["تخلیه"])
        age = (as_of - discharge).days if (discharge and status != ST_FULL and as_of >= discharge) else None
        # ── کمبود و مغایرت: همان شاهد build_shipping_insights، به‌علاوه پرچم/تاریخ ترخیص
        conflicts = [c for c in X.s(r["مغایرت شواهد"]).split("، ") if c]
        missing = [m for m in X.s(r["دادهٔ لازم"]).split("، ") if m]
        if partial_conflict:
            conflicts.append("ترخیص جزئی")
        if (full_date or full_conflict) and not (full_flag or done_no_date):
            conflicts.append("تاریخ ترخیص کامل بدون پرچم ترخیص کامل")
        if partial_date and not (partial_flag or full_flag or done_no_date):
            conflicts.append("تاریخ ترخیص جزئی بدون پرچم ترخیص جزئی")
        if status != ST_FULL:
            # بارنامه‌ای که هنوز ترخیص کامل نشده تاریخ ترخیص کامل ندارد؛ این کمبود داده نیست
            missing = [x for x in missing if x != "ترخیص کامل"]
        if full_flag and not full_date and not full_conflict and "شاهد ترخیص کامل بدون تاریخ" not in missing:
            missing.append("پرچم ترخیص کامل بدون تاریخ")
        if not ords:
            missing.append("سفارش بارنامه")
        if crit is None:
            missing.append("سطح بحرانی سفارش‌ها")
        if status == ST_FULL:
            # بارنامه ترخیص‌شده منتظر ترخیصیه/کوتاژ نیست؛ نبود آن تاریخ فقط کمبود داده است
            action = "بدون اقدام ترخیص؛ " + ("تطبیق شاهدهای متعارض با اصل سند" if conflicts else "بایگانی پرونده")
        else:
            action = X.s(r["اقدام پیشنهادی"])
        filter_date = _jal(r["تخلیه"]) or _jal(r["ورود"])
        recs.append({
            "بارنامه": bl, "وضعیت ترخیص": status,
            "بحرانی": UNKNOWN if crit is None else (YES if crit else NO),
            "بدترین سطح بحرانی سفارش‌ها": CB.level_label(level) if level else "",
            "سفارش‌ها": "، ".join(ords), "ثبت سفارش‌ها": _join(_coalesce(g, "KEY_REG", "CANONICAL_REG")),
            "روش حمل": _mode_label(r["روش حمل"]), "کشتی": X.s(r["کشتی"]), "شماره سفر": X.s(r["شماره سفر"]),
            "ورود": _jal(r["ورود"]), "تخلیه": _jal(r["تخلیه"]), "دریافت ترخیصیه": _jal(r["دریافت ترخیصیه"]),
            "کوتاژ": _jal(r["کوتاژ"]), "ترخیص جزئی": format_jalali(partial_date) if partial_date else "",
            "ترخیص کامل": _jal(r["ترخیص کامل"]), WAIT: age,
            "شماره کوتاژ": _join(_coalesce(g, "COTAGE_NO", "CL_COTAGE_NO", "COT_NO")),
            "گمرک مقصد": _join(_coalesce(g, "DEST_CUSTOMS", "COT_DEST_CUSTOMS")),
            "کارشناس ترخیص": _join(_coalesce(g, "CL_EXPERT", "COT_EXPERT")),
            CRIT_MATS_OF_BL_ORDERS: _join(crit_mats, limit=12),
            "شمار متریال سفارش‌ها": len(all_mats) if facts else None,
            "کمبود داده": "، ".join(dict.fromkeys(missing)), "مغایرت شواهد": "، ".join(dict.fromkeys(conflicts)),
            "اقدام پیشنهادی": action,
            "کارشناس سفارش‌ها": _join(e for f in facts for e in f["experts"]),
            "مدیریت/اداره سفارش‌ها": _join(d for f in facts for d in f["depts"]),
            "شمار ردیف منبع": int(r["شمار ردیف منبع"]),
            "_DISCHARGE": discharge, "_CRIT_RANK": CB.level_rank(level) if level else 9,
            FILTER_DATE: filter_date,
        })
    full = pd.DataFrame(recs)
    full["_S"] = full["وضعیت ترخیص"].map({s: i for i, s in enumerate(STATUSES)})
    full = full.sort_values(["_S", WAIT, "_CRIT_RANK", "بارنامه"], ascending=[True, False, True, True],
                            na_position="last").reset_index(drop=True)

    full[WAIT] = pd.array([None if pd.isna(v) else int(v) for v in full[WAIT]], dtype="Int64")
    full["شمار متریال سفارش‌ها"] = pd.array([None if pd.isna(v) else int(v) for v in full["شمار متریال سفارش‌ها"]],
                                             dtype="Int64")
    dossiers = full[DOSSIER_COLS + [FILTER_DATE]].copy()
    fu = full[full["وضعیت ترخیص"].ne(ST_FULL)].copy()
    fu["_C"] = fu["بحرانی"].eq(YES)
    fu = fu.sort_values([WAIT, "_C", "_CRIT_RANK", "بارنامه"], ascending=[False, False, True, True],
                        na_position="last")
    follow_up = fu[FOLLOW_COLS + [FILTER_DATE]].reset_index(drop=True)

    gaps = full[full["کمبود داده"].ne("") | full["مغایرت شواهد"].ne("")][GAP_COLS + [FILTER_DATE]].reset_index(drop=True)

    # ── دسته‌های روز پس از تخلیه، فقط بارنامه‌های بدون ترخیص کامل
    open_ = full[full["وضعیت ترخیص"].ne(ST_FULL)]
    labels = [_bucket(a if pd.notna(a) else None, d is not None)
              for a, d in zip(open_[WAIT], open_["_DISCHARGE"])]
    order = [b[0] for b in AGE_BUCKETS] + [AGE_FUTURE, AGE_NO_DATE]
    ages = pd.DataFrame({"دسته": order, "بارنامه": [labels.count(b) for b in order]})
    ages = ages[(ages["بارنامه"] > 0) | ages["دسته"].isin([b[0] for b in AGE_BUCKETS])].reset_index(drop=True)

    counts = {"total": total, **{s: int(full["وضعیت ترخیص"].eq(s).sum()) for s in STATUSES},
              "critical_open": int((full["بحرانی"].eq(YES) & full["وضعیت ترخیص"].ne(ST_FULL)).sum()),
              "critical_unknown": int(full["بحرانی"].eq(UNKNOWN).sum()),
              "conflicts": int(full["مغایرت شواهد"].ne("").sum()),
              "open": int(len(open_)),
              "orders": int(len({o for s in full["سفارش‌ها"] for o in s.split("، ") if o})),
              "orders_without_bl": 0}
    # سفارش‌هایی که هیچ ردیف بارنامه ندارند؛ فقط شمرده می‌شوند، در جدول‌ها نیستند
    with_bl = set(bl_rows["CANONICAL_ORDER"])
    all_orders = set(work["CANONICAL_ORDER"]) - {""}
    counts["orders_without_bl"] = len(all_orders - with_bl)

    out = ShippingModel(ref_text, as_of, dossiers, follow_up, _durations(full), _coverage(full, coverage), gaps, ages,
                        counts, [NOTE_GRAIN] + notes)
    out.journey = J.build(bl_rows, full, extras, as_of, ST_FULL)
    return _with_expert(out, expert)


def _with_expert(m: ShippingModel, expert: pd.DataFrame) -> ShippingModel:
    m.expert = expert
    for code in EXP_STATES:
        m.counts["exp_" + code] = int(expert["وضعیت پارت (کارشناس)"].eq(EXP_STATE_FA[code]).sum()) \
            if not expert.empty else 0
    m.counts["exp_no_bl"] = int(expert["بارنامه در گزارش حمل"].isin([EXP_BL_NONE, EXP_BL_SUSPECT]).sum()) \
        if not expert.empty else 0
    m.counts["exp_expert_only"] = int(expert["بارنامه در گزارش حمل"].eq(EXP_BL_EXPERT_ONLY).sum()) \
        if not expert.empty else 0
    return m


def _expert_source(df: pd.DataFrame, extras: Any) -> tuple:
    """(پارت‌های کارشناسان، منبع). اول دفتر ``expert_shipments`` مرحله ۴۱ (دانه ردیف فایل)؛ اگر
    Snapshot قدیمی است، از ستون‌های مقدار پارت مارت در دانه سفارش × متریال (بدون بارنامه/تاریخ پارت)."""
    ship = None
    try:
        ship = extras.get("expert_shipments") if extras is not None else None
    except Exception:
        ship = None
    if isinstance(ship, pd.DataFrame) and not ship.empty:
        return ship.copy(), "lines"
    qty_cols = {"AT_SUPPLIER": "MOGH_QTY_AT_SUPPLIER", "READY": "MOGH_QTY_READY",
                "IN_TRANSIT": "MOGH_QTY_IN_TRANSIT", "IN_CUSTOMS": "MOGH_QTY_IN_CUSTOMS"}
    if not any(c in df.columns for c in qty_cols.values()):
        return pd.DataFrame(), ""
    base = df.drop_duplicates(subset=[c for c in ("KEY_ORDER", "KEY_MATERIAL") if c in df.columns])
    rows = []
    for code, col in qty_cols.items():
        if col not in base.columns:
            continue
        q = pd.to_numeric(base[col], errors="coerce")
        sub = base[q.gt(0)]
        for (_, r), qty in zip(sub.iterrows(), q[q.gt(0)]):
            rows.append({"KEY_ORDER": X.s(r.get("KEY_ORDER")), "KEY_MATERIAL": X.s(r.get("KEY_MATERIAL")),
                         "MATERIAL_DESC": X.s(r.get("MATERIAL_DESC")), "PART_STATE": code, "QTY_IN_PART": qty,
                         "CRIT_CODE": X.s(r.get("کد طبقه بحرانی")), "EXPERT": X.s(r.get("CANONICAL_EXPERT")),
                         "DATA_GAP_FILES": X.s(r.get("DATA_GAP_FILES"))})
    return pd.DataFrame(rows), "flat"


def expert_frame(df: pd.DataFrame, extras: Any, tracked: set) -> tuple:
    """جدول پارت‌های کارشناسان در چهار وضعیت (نزد سازنده، آماده حمل، در راه، در گمرک) و یادداشت منبع."""
    src, kind = _expert_source(df, extras)
    empty = pd.DataFrame(columns=EXP_COLS + [FILTER_DATE])
    if src.empty:
        return empty, (NOTE_EXPERT_MISSING if kind == "" else "")
    src = src[src.get("PART_STATE", pd.Series("", index=src.index)).map(X.s).isin(EXP_STATES)]
    # دامنه Studio (فیلتر دامنه تاریخی) روی مارت اعمال شده است؛ همان سفارش × متریال‌ها می‌مانند
    if "KEY_MATERIAL" in df.columns and ({"KEY_ORDER", "CANONICAL_ORDER"} & set(df.columns)):
        pairs = set(zip(_coalesce(df, "KEY_ORDER", "CANONICAL_ORDER"), _col(df, "KEY_MATERIAL").map(X.s)))
        src = src[[(X.s(o), X.s(m)) in pairs for o, m in zip(src["KEY_ORDER"], src["KEY_MATERIAL"])]]
    if src.empty:
        return empty, ""
    rows = []
    for _, r in src.iterrows():
        g = lambda k: X.s(r.get(k))  # noqa: E731
        bl = g("BL")
        code = g("CRIT_CODE")
        sched, po = _jal(g("SCHEDULED_SHIP")), _jal(g("PO_SENT_DATE"))
        qty, clr = r.get("QTY_IN_PART"), r.get("CLEARED_QTY")
        rows.append({
            "وضعیت پارت (کارشناس)": EXP_STATE_FA[g("PART_STATE")], "Order Status": g("ORDER_STATUS_RAW"),
            "سفارش": g("KEY_ORDER"), "متریال": g("KEY_MATERIAL"),
            "شرح": g("MATERIAL_DESC"), "شماره پارت": g("PART_NO"),
            "مقدار پارت": None if qty is None or pd.isna(qty) else float(qty),
            "ترخیص‌شده (کارشناس)": None if clr is None or pd.isna(clr) else float(clr), "واحد": g("UOM"),
            "بارنامه": bl or g("BL_SUSPECT"),
            "بارنامه در گزارش حمل": ((EXP_BL_SUSPECT if g("BL_SUSPECT") else EXP_BL_NONE) if not bl
                                      else EXP_BL_TRACKED if bl in tracked else EXP_BL_EXPERT_ONLY),
            "روش حمل": g("MODE"), "شماره حمل": g("TRANSPORT_NO"), "حمل‌کننده": g("CARRIER"),
            "تاریخ برنامه حمل": sched, "تاریخ ابلاغ PO": po, "مرحله (کارشناس)": g("STAGE_FA"),
            "یادداشت لجستیک": g("LOGISTICS_NOTE"),
            "سطح بحرانی": CB.level_label(code) if code in CB.LEVELS else CB.level_label("UNKNOWN"),
            "کارشناس": g("EXPERT"), "نقص داده (کدام فایل)": g("DATA_GAP_FILES"),
            "_S": EXP_STATES.index(g("PART_STATE")), "_R": CB.level_rank(code) if code in CB.LEVELS else 6,
            FILTER_DATE: sched or po,
        })
    out = pd.DataFrame(rows).sort_values(["_S", "_R", "سفارش", "متریال"]).drop(columns=["_S", "_R"])
    return out.reset_index(drop=True)[EXP_COLS + [FILTER_DATE]], ""


def _durations(full: pd.DataFrame) -> pd.DataFrame:
    rows = []
    modes = ["همه روش‌ها"] + sorted(full["روش حمل"].unique().tolist(), key=lambda m: (m == "نامشخص", m))
    for lab, a, b in DURATIONS:
        start = full[a].map(_parse)
        end = full[b].map(_parse)
        for mode in modes:
            mask = pd.Series(True, index=full.index) if mode == "همه روش‌ها" else full["روش حمل"].eq(mode)
            s, e = start[mask], end[mask]
            both = s.notna() & e.notna()
            gaps = [(y - x).days for x, y in zip(s[both], e[both])]
            ok = [g for g in gaps if g >= 0]
            rows.append({"مرحله": lab, "روش حمل": mode, "بارنامه": int(mask.sum()), "دارای هر دو تاریخ": len(ok),
                         "میانه (روز)": float(pd.Series(ok).median()) if ok else None,
                         "بیشینه (روز)": int(max(ok)) if ok else None,
                         "بدون تاریخ شروع": int(s.isna().sum()), "بدون تاریخ پایان": int(e.isna().sum()),
                         "فاصله منفی (کنار گذاشته)": len(gaps) - len(ok)})
    return pd.DataFrame(rows, columns=DURATION_COLS)


def _coverage(full: pd.DataFrame, base_cov: pd.DataFrame) -> pd.DataFrame:
    n = len(full)
    rows = []
    for lab in FUNNEL + ["روش حمل", "سفارش بارنامه", "سطح بحرانی سفارش‌ها"]:
        if lab == "روش حمل":
            have = int(full[lab].ne("نامشخص").sum())
        elif lab == "سفارش بارنامه":
            have = int(full["سفارش‌ها"].ne("").sum())
        elif lab == "سطح بحرانی سفارش‌ها":
            have = int(full["بحرانی"].ne(UNKNOWN).sum())
        else:
            have = int(full[lab].ne("").sum())
        conflict = int(full["مغایرت شواهد"].map(lambda v, k=lab: k in X.s(v).split("، ")).sum())
        # «ترخیص کامل» بدون تاریخ ولی با پرچم مارت: شاهد وضعیت هست، شاهد تاریخ نیست
        rows.append({"شاهد": lab, "بارنامه": n, "دارای شاهد": have, "متعارض": conflict,
                     "بدون شاهد": n - have - conflict, "پوشش (٪)": round(100 * have / n, 1) if n else None})
    return pd.DataFrame(rows, columns=COVERAGE_COLS)


# ═══════════════════════════════ فیلتر ═══════════════════════════════
def _norm_date(text: Any) -> str:
    """ورودی کاربر (شمسی/ISO، رقم فارسی) ← «1405/01/01»؛ نامعتبر ← رشته خالی."""
    d = _parse(text)
    return format_jalali(d) if d else ""


def filter_frame(frame: pd.DataFrame, text: str = "", start: Any = "", end: Any = "",
                 include_undated: bool = False, basis: str = "") -> pd.DataFrame:
    """همان فیلتر سمت کاربر HTML برای Studio: جستجوی متن در همه ستون‌ها و بازه تاریخ مبنا.

    ``basis`` یکی از کلیدهای :data:`DATE_BASES` است؛ جدولی که آن ستون را ندارد (پارت‌های کارشناسان)
    با تاریخ مبنای خودش فیلتر می‌شود. R10: ردیف بی‌تاریخ به‌طور پیش‌فرض بیرون می‌ماند؛ پیش‌تر
    می‌ماند و بازه تاریخ روی بیشتر ردیف‌ها بی‌اثر به نظر می‌رسید."""
    if frame is None or frame.empty:
        return frame
    out = frame
    q = X.s(text).lower()
    if q:
        hay = out.astype(str).agg(" ".join, axis=1).str.lower()
        out = out[hay.str.contains(q, regex=False)]
    a, b = _norm_date(start), _norm_date(end)
    col = DATE_BASES.get(basis or "", FILTER_DATE)
    if col not in out.columns:
        col = FILTER_DATE
    if (a or b) and col in out.columns:
        d = out[col].map(_jal)
        keep = d.ne("")
        if a:
            keep &= d >= a
        if b:
            keep &= d <= b
        if include_undated:
            keep |= d.eq("")
        out = out[keep]
    return out


def filtered_model(m: ShippingModel, df: pd.DataFrame, extras: Any = None, ref_date: Any = "", start: Any = "",
                   end: Any = "", include_undated: bool = False, basis: str = "") -> ShippingModel:
    """R10: بازه تاریخ روی **همه** گزارش (کارت‌ها، قیف، مدت‌ها و جدول‌ها)، نه فقط جدول‌ها.

    بارنامه‌های داخل بازه از پرونده‌ها انتخاب می‌شوند و مدل از ردیف‌های همان بارنامه‌ها (و ردیف‌های
    بی‌بارنامه سفارش‌هایشان) دوباره ساخته می‌شود؛ پارت‌های کارشناسان با تاریخ خودشان فیلتر می‌شوند."""
    if not (_norm_date(start) or _norm_date(end)) or df is None or df.empty:
        return m
    keep = set(filter_frame(m.dossiers, start=start, end=end, include_undated=include_undated,
                            basis=basis)["بارنامه"].map(X.s))
    work = _prepare(df)
    orders = set(work.loc[work["CANONICAL_BL"].isin(keep), "CANONICAL_ORDER"]) - {""}
    sub = df[(work["CANONICAL_BL"].isin(keep) | (work["CANONICAL_BL"].eq("") & work["CANONICAL_ORDER"].isin(orders)))
             .to_numpy()]
    out = build_model(sub, extras, ref_date) if not sub.empty else _empty_model(m.ref_date, m.as_of, [NOTE_EMPTY])
    return _with_expert(out, filter_frame(m.expert, start=start, end=end, include_undated=include_undated))


# ═══════════════════════════════ نمایش ═══════════════════════════════
def display_frame(frame: pd.DataFrame, lang: str = FA) -> pd.DataFrame:
    """جدول برای نمایش/Excel: بدون ستون‌های داخلی، سرستون و برچسب‌ها در زبان خواسته‌شده."""
    if frame is None:
        return pd.DataFrame()
    out = frame[[c for c in frame.columns if not str(c).startswith("_")]].copy()
    if lang == EN:
        for c in ("وضعیت ترخیص", "بحرانی", "بدترین سطح بحرانی سفارش‌ها", "روش حمل", "مرحله", "شاهد", "دسته",
                  "کمبود داده", "مغایرت شواهد", "اقدام پیشنهادی", "وضعیت پارت (کارشناس)", "بارنامه در گزارش حمل",
                  "سطح بحرانی"):
            if c in out.columns:
                out[c] = out[c].map(lambda v: _en_list(v))
        out.columns = [t(c, EN) for c in out.columns]
    return out


def _en_list(v: Any) -> Any:
    s = X.s(v)
    if not s:
        return v
    if s in EN_TEXT:
        return EN_TEXT[s]
    for sep, j in (("؛ ", "; "), ("، ", ", ")):
        if sep in s:
            return j.join(_en_list(p) for p in s.split(sep))
    return C.phrase(s, EN)


CSS = f"""
.sc-funnel{{display:grid;gap:8px;margin:6px 0 14px}}
.sc-frow{{display:grid;grid-template-columns:minmax(120px,170px) 1fr minmax(92px,auto);gap:10px;align-items:center;font-size:12px}}
.sc-frow>span:first-child{{color:{T.TEXT_SECONDARY};font-weight:700}}
.sc-fbar{{height:14px;border-radius:{T.RADIUS['pill']}px;background:{T.SURFACE_SUNKEN};box-shadow:{T.ELEVATION['inset']};overflow:hidden}}
.sc-fbar i{{display:block;height:100%;border-radius:{T.RADIUS['pill']}px;background:linear-gradient(270deg,{T.TEAL_PALETTE[3]},{T.TEAL_PALETTE[7]})}}
.sc-frow b{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.sc-frow small{{margin-inline-start:6px}}
.sc-ages{{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 14px}}
.sc-age{{background:{T.SURFACE_RAISED};border-radius:{T.RADIUS['md']}px;box-shadow:{T.ELEVATION['raised']};padding:8px 12px;min-width:110px}}
.sc-age b{{display:block;font-size:18px;color:{T.TEAL_INK}}} .sc-age span{{font-size:11px;color:{T.TEXT_MUTED}}}
.sc-age.is-hot b{{color:{T.STATUS['critical'].ink}}}
.sc-age.is-na b{{color:{T.TEXT_MUTED}}}
.sc-filter{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:{T.SURFACE_RAISED};border-radius:{T.RADIUS['lg']}px;
  box-shadow:{T.ELEVATION['raised']};padding:10px 14px;margin:10px 0 4px;font-size:12px}}
.sc-filter input[type=text]{{border:1px solid {T.BORDER};border-radius:{T.RADIUS['sm']}px;padding:6px 10px;font:inherit;
  background:{T.SURFACE_PAGE};color:{T.TEXT};min-width:120px}}
.sc-filter input.sc-q{{flex:1 1 220px}}
.sc-filter label{{display:inline-flex;gap:6px;align-items:center;color:{T.TEXT_SECONDARY};font-weight:700;white-space:nowrap}}
.sc-filter input[type=checkbox]{{width:16px;height:16px;margin:0;accent-color:{T.BRAND_TEAL}}}
.sc-filter input::placeholder{{color:{T.TEXT_MUTED};font-weight:400}}
.sc-filter button{{border:1px solid {T.BORDER};background:{T.SURFACE_PAGE};border-radius:{T.RADIUS['sm']}px;padding:6px 12px;
  font:inherit;cursor:pointer;color:{T.TEAL_INK};font-weight:800}}
.sc-filter .sc-count{{margin-inline-start:auto;color:{T.TEXT_MUTED}}}
.gx-tbl td.sc-crit{{box-shadow:inset -3px 0 0 {T.STATUS['critical'].fill}}}
[dir="ltr"] .gx-tbl td.sc-crit{{box-shadow:inset 3px 0 0 {T.STATUS['critical'].fill}}}
.sc-k{{display:contents}}
{J.css()}
.sc-filter select{{border:1px solid {T.BORDER};border-radius:{T.RADIUS['sm']}px;padding:5px 8px;font:inherit;
  background:{T.SURFACE_PAGE};color:{T.TEXT}}}
@media print{{.sc-filter{{display:none!important}}}}
"""


def style_tag() -> str:
    """شیوه‌نامه مشترک چرخه ارز به‌علاوه چند قاعده این گزارش؛ Studio و HTML یکی."""
    return f"<style>{H.css()}{CSS}</style>"


def _empty(lang: str, msg: str = NOTE_EMPTY) -> str:
    return f'<div class="gx-empty">{L(msg, lang)}</div>'


def _sec(icon: str, title: str, lang: str, small: str = "", tone: str = "brand") -> str:
    sm = f"<small>{L(small, lang)}</small>" if small else ""
    return f'<div class="gx-sec">{I.icon_tile(icon, tone, 16)}<h3>{L(title, lang)}</h3>{sm}</div>'


def _num(v: Any, nd: int = 0) -> str:
    x = X.n(v)
    return '<span class="gx-na">—</span>' if x is None else f'<span class="gx-num">{x:,.{nd}f}</span>'


def _table(frame: pd.DataFrame, lang: str, cells: Optional[Dict[str, Callable]] = None,
           max_rows: int = 600, key: str = "t", filterable: bool = True,
           attrs: Optional[Callable[[Any], str]] = None) -> str:
    """جدول سبک با ``data-d`` (تاریخ مبنای فیلتر) روی هر ردیف برای فیلتر سمت کاربر."""
    if frame is None or frame.empty:
        return f'<div class="gx-empty">{L("داده‌ای نیست", lang)}</div>'
    cells = cells or {}
    cols = [c for c in frame.columns if not str(c).startswith("_")]
    head = "".join(f"<th>{L(c, lang)}</th>" for c in cols)
    body = []
    for _, r in frame.head(max_rows).iterrows():
        tds = []
        for c in cols:
            v = r[c]
            if c in cells:
                tds.append(f"<td>{cells[c](v, r)}</td>")
                continue
            txt = X.s(v)
            if lang == EN and c in ("کمبود داده", "مغایرت شواهد", "اقدام پیشنهادی", "روش حمل", "مرحله", "شاهد"):
                txt = X.s(_en_list(txt))
            cls = ' class="w"' if len(txt) > 36 else ""
            tds.append(f"<td{cls}>{html.escape(txt) if txt else '—'}</td>")
        d = html.escape(X.s(r.get(FILTER_DATE, "")), quote=True)
        extra = attrs(r) if attrs else ""
        body.append(f'<tr data-d="{d}"{extra}>' + "".join(tds) + "</tr>")
    more = (f'<div class="gx-note">{len(frame) - max_rows:,} '
            f'{L("ردیف دیگر در فایل Excel", lang)}</div>' if len(frame) > max_rows else "")
    fcls = " sc-filterable" if filterable else ""
    whole = ' data-whole="1"' if len(frame) <= max_rows else ""
    return (f'<div class="gx-tbl{fcls}" data-key="{html.escape(key, quote=True)}"{whole}><table><thead><tr>{head}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table></div>{more}')


def _cells(lang: str) -> Dict[str, Callable]:
    def status(v, r):
        return H.pill(t(v, lang), STATUS_TONE.get(X.s(v), "unknown"), FA)

    def crit(v, r):
        s = X.s(v)
        if s == YES:
            return H.pill(t(YES, lang), "critical", FA)
        if s == UNKNOWN:
            return H.pill(t(UNKNOWN, lang), "unknown", FA)
        return html.escape(t(NO, lang))

    def level(v, r):
        s = X.s(v)
        code = next((k for k, val in CB.LEVELS.items() if val[1] == s), "")
        return H.level_badge(code, lang) if code else "—"

    return {"بارنامه": lambda v, r: f'<b class="gx-key">{H.esc(v)}</b>', "وضعیت ترخیص": status, "بحرانی": crit,
            "بدترین سطح بحرانی سفارش‌ها": level, WAIT: lambda v, r: _num(v),
            "شمار متریال سفارش‌ها": lambda v, r: _num(v), "شمار ردیف منبع": lambda v, r: _num(v),
            "میانه (روز)": lambda v, r: _num(v, 1), "بیشینه (روز)": lambda v, r: _num(v),
            "پوشش (٪)": lambda v, r: _num(v, 1)}


def _bl_attrs(m: ShippingModel) -> Callable[[Any], str]:
    """تاریخ هر مبنای فیلتر (``data-b1``…) از پرونده همان بارنامه، تا جدول‌های پیگیری و کمبود داده هم
    با مبنای انتخابی فیلتر شوند؛ ``data-s``/``data-co``/``data-cf`` برای بازشماری کارت‌ها در HTML."""
    idx = m.dossiers.set_index("بارنامه") if not m.dossiers.empty else pd.DataFrame()
    status = {s: i for i, s in enumerate(STATUSES)}

    def attrs(r) -> str:
        bl = X.s(r.get("بارنامه"))
        if bl not in idx.index:
            return ""
        d = idx.loc[bl]
        if isinstance(d, pd.DataFrame):
            d = d.iloc[0]
        out = "".join(f' data-b{i}="{html.escape(_jal(d.get(DATE_BASES[k])), quote=True)}"'
                      for i, k in enumerate(BASIS_KEYS) if i)
        st = X.s(d.get("وضعیت ترخیص"))
        out += f' data-s="{status.get(st, "")}"'
        if X.s(d.get("بحرانی")) == YES and st != ST_FULL:
            out += ' data-co="1"'
        if X.s(d.get("مغایرت شواهد")):
            out += ' data-cf="1"'
        return out
    return attrs


def _k(key: str, tile: str) -> str:
    """کارت KPI با کلید بازشماری سمت کاربر (``display:contents``؛ چیدمان کارت‌ها عوض نمی‌شود)."""
    return f'<div class="sc-k" data-k="{key}">{tile}</div>'


# ── (الف) KPI ──
@H._css_icons
def kpi_section(m: ShippingModel, lang: str = FA) -> str:
    """کارت‌های شمار یکتای بارنامه در هر وضعیت و دسته‌های روز پس از تخلیه."""
    if m.dossiers.empty:
        return _empty(lang) + (_expert_tiles(m, lang) if not m.expert.empty else "")
    c = m.counts
    tiles = [("total", "ship", "بارنامه یکتا", c["total"], "brand"),
             ("s0", "truck", "بارنامه در راه", c[ST_TRANSIT], "brand"),
             ("s1", "warehouse", ST_ARRIVED, c[ST_ARRIVED], "critical" if c[ST_ARRIVED] else "brand"),
             ("s2", "customs", ST_PARTIAL, c[ST_PARTIAL], "brand"),
             ("s3", "check", ST_FULL, c[ST_FULL], "brand"),
             ("co", "alert", "بارنامه بحرانی ترخیص‌نشده", c["critical_open"], "critical" if c["critical_open"] else "brand"),
             ("cf", "search", "بارنامه با مغایرت شاهد", c["conflicts"], "brand")]
    k = "".join(_k(key, I.kpi_tile(ic, t(lab, lang), f"{v:,}", tone=tone)) for key, ic, lab, v, tone in tiles)
    hot = {"۳۱ تا ۶۰ روز", "بیش از ۶۰ روز"}
    ages = "".join(
        f'<div class="sc-age{" is-hot" if r["دسته"] in hot and r["بارنامه"] else ""}'
        f'{" is-na" if r["دسته"] in (AGE_NO_DATE, AGE_FUTURE) else ""}"><b>{int(r["بارنامه"]):,}</b>'
        f'<span>{L(r["دسته"], lang)}</span></div>' for _, r in m.ages.iterrows())
    notes = "".join(f'<div class="gx-note">{L(n, lang)}</div>' for n in m.notes)
    extra = ""
    if c.get("orders_without_bl"):
        extra = (f'<div class="gx-note">{c["orders_without_bl"]:,} '
                 f'{L(NOTE_NO_BL, lang)}</div>')
    return (f'<div class="mi-kpis">{k}</div>' + _expert_tiles(m, lang)
            + _sec("clock", "روز پس از تخلیه در بارنامه‌های بدون ترخیص کامل", lang,
                   small=f'{c["open"]:,} {t("بارنامه", lang)}')
            + f'<div class="sc-ages">{ages}</div>{notes}{extra}'
            + f'<div class="gx-note">{L(NOTE_CRITICAL, lang)}</div>')


# ── (ب) قیف و مدت‌ها ──
@H._css_icons
def stages_section(m: ShippingModel, lang: str = FA) -> str:
    """قیف شاهد هر مرحله (بارنامه یکتا) و میانه/بیشینه مدت هر مرحله به تفکیک روش حمل."""
    if m.dossiers.empty:
        return _empty(lang)
    cov = m.coverage.set_index("شاهد")
    n = m.total
    rows = []
    for lab in FUNNEL:
        have = int(cov.loc[lab, "دارای شاهد"]) if lab in cov.index else 0
        conf = int(cov.loc[lab, "متعارض"]) if lab in cov.index else 0
        w = 100 * have / n if n else 0
        cf = f'<small>{conf:,} {L("متعارض", lang)}</small>' if conf else ""
        rows.append(f'<div class="sc-frow"><span>{L(lab, lang)}</span><span class="sc-fbar"><i style="width:{w:.1f}%"></i>'
                    f'</span><b>{have:,} / {n:,}{cf}</b></div>')
    funnel = f'<div class="sc-funnel">{"".join(rows)}</div>'
    dur = _table(m.durations, lang, _cells(lang), key="durations", filterable=False)
    return (_sec("flow", "قیف شاهد مراحل (بارنامه یکتا)", lang) + funnel
            + _sec("clock", "مدت هر مرحله به تفکیک روش حمل", lang) + f'<div class="gx-note">{L(NOTE_DURATION, lang)}</div>'
            + dur)


# ── (ج) پرونده بارنامه‌ها ──
@H._css_icons
def dossier_section(m: ShippingModel, lang: str = FA, frame: Optional[pd.DataFrame] = None,
                    max_rows: int = 600) -> str:
    if m.dossiers.empty:
        return _empty(lang)
    f = m.dossiers if frame is None else frame
    return (_sec("file", "پرونده هر بارنامه", lang, small=f"{len(f):,} {t('بارنامه', lang)}")
            + f'<div class="gx-note">{L(NOTE_GRAIN, lang)}</div>'
            + _table(f, lang, _cells(lang), max_rows=max_rows, key="dossiers", attrs=_bl_attrs(m)))


# ── (د) پیگیری ترخیص ──
@H._css_icons
def followup_section(m: ShippingModel, lang: str = FA, frame: Optional[pd.DataFrame] = None,
                     max_rows: int = 600) -> str:
    if m.dossiers.empty:
        return _empty(lang)
    f = m.follow_up if frame is None else frame
    note = L(NOTE_FOLLOW, lang)
    return (_sec("queue", "فهرست پیگیری ترخیص", lang, small=f"{len(f):,} {t('بارنامه', lang)}")
            + f'<div class="gx-note">{note}</div>' + _table(f, lang, _cells(lang), max_rows=max_rows, key="followup",
                                                                           attrs=_bl_attrs(m)))


# ── (هـ) پوشش و کمبود داده ──
@H._css_icons
def gaps_section(m: ShippingModel, lang: str = FA, frame: Optional[pd.DataFrame] = None,
                 max_rows: int = 600) -> str:
    if m.dossiers.empty:
        return _empty(lang)
    f = m.gaps if frame is None else frame
    note = L(NOTE_COVERAGE, lang)
    return (_sec("database", "پوشش شواهد", lang) + f'<div class="gx-note">{note}</div>'
            + _table(m.coverage, lang, _cells(lang), key="coverage", filterable=False)
            + _sec("alert", "بارنامه‌های دارای کمبود یا مغایرت", lang, small=f"{len(f):,} {t('بارنامه', lang)}", tone="critical")
            + _table(f, lang, _cells(lang), max_rows=max_rows, key="gaps", attrs=_bl_attrs(m)))


# ── (و) پارت‌های فایل کارشناسان (R10، مالک ۱۴۰۵/۰۷/۰۸): نزد سازنده تا گمرک، حتی بی‌بارنامه ──
EXP_TILES = [("IN_CUSTOMS", "customs", "پارت در گمرک"), ("IN_TRANSIT", "truck", "پارت در راه"),
             ("READY", "box", "پارت آماده حمل"), ("AT_SUPPLIER", "warehouse", "پارت نزد سازنده"),
             ("UNRECOGNIZED", "alert", "پارت با وضعیت ناشناخته")]


def _expert_tiles(m: ShippingModel, lang: str) -> str:
    """شمار ردیف پارت هر وضعیت (جمع مقدار نه، چون واحدها یکی نیست) و پارت‌های بی‌بارنامه."""
    c = m.counts
    tiles = [_k("e" + code, I.kpi_tile(ic, t(lab, lang), f'{c.get("exp_" + code, 0):,}'))
             for code, ic, lab in EXP_TILES]
    tiles.append(_k("enb", I.kpi_tile("alert", t("پارت بی‌بارنامه", lang), f'{c.get("exp_no_bl", 0):,}',
                                      tone="critical" if c.get("exp_no_bl") else "brand")))
    tiles.append(_k("eeo", I.kpi_tile("search", t("بارنامه فقط در فایل کارشناسان", lang),
                                      f'{c.get("exp_expert_only", 0):,}')))
    return f'<div class="mi-kpis">{"".join(tiles)}</div>'


def _exp_attrs(r) -> str:
    code = next((k for k, v in EXP_STATE_FA.items() if v == X.s(r.get("وضعیت پارت (کارشناس)"))), "")
    bl = X.s(r.get("بارنامه در گزارش حمل"))
    return (f' data-e="{code}"' + (' data-enb="1"' if bl in (EXP_BL_NONE, EXP_BL_SUSPECT) else "")
            + (' data-eeo="1"' if bl == EXP_BL_EXPERT_ONLY else ""))


def _exp_cells(lang: str) -> Dict[str, Callable]:
    def state(v, r):
        tone = {"در گمرک": "warning", "در راه": "neutral"}.get(X.s(v), "unknown")
        return H.pill(t(v, lang), tone, FA)

    def level(v, r):
        s = X.s(v)
        code = next((k for k, val in CB.LEVELS.items() if val[1] == s), "")
        return H.level_badge(code, lang) if code else "—"

    def gap(v, r):
        s = X.s(v)
        return html.escape(CB.gap_text(s, lang)) if s else "—"

    def bl(v, r):
        s = X.s(v)
        if not s:
            return f'<span class="gx-na">{html.escape(t(EXP_BL_NONE, lang))}</span>'
        return f'<b class="gx-key">{H.esc(s)}</b>'

    return {"وضعیت پارت (کارشناس)": state, "سطح بحرانی": level, "نقص داده (کدام فایل)": gap, "بارنامه": bl,
            "بارنامه در گزارش حمل": lambda v, r: html.escape(t(v, lang)) if X.s(v) else "—",
            "مقدار پارت": lambda v, r: _num(v, 2 if X.n(v) is not None and X.n(v) % 1 else 0),
            "ترخیص‌شده (کارشناس)": lambda v, r: _num(v, 2 if X.n(v) is not None and X.n(v) % 1 else 0)}


@H._css_icons
def expert_section(m: ShippingModel, lang: str = FA, frame: Optional[pd.DataFrame] = None,
                   max_rows: int = 600) -> str:
    """پارت‌های فایل کارشناسان در وضعیت نزد سازنده، آماده حمل، در راه و در گمرک، با یا بی بارنامه."""
    f = m.expert if frame is None else frame
    note = next((n for n in m.notes if n == NOTE_EXPERT_MISSING), "")
    if m.expert.empty:
        return _empty(lang, note or "پارتی در این چهار وضعیت در فایل کارشناسان نیست.")
    return (_sec("box", "پارت‌های کارشناسان (نزد سازنده تا گمرک)", lang, small=f"{len(f):,} {t('پارت', lang)}")
            + _expert_tiles(m, lang) + f'<div class="gx-note">{L(NOTE_EXPERT, lang)}</div>'
            + _table(f, lang, _exp_cells(lang), max_rows=max_rows, key="expert", attrs=_exp_attrs))


# ── (ز) مسیر شواهد: داستان تصویری وضعیت، بی‌متن و بی‌نام ──
@H._css_icons
def journey_section(m: ShippingModel, lang: str = FA, frame: Optional[pd.DataFrame] = None,
                    max_rows: int = 600) -> str:
    """خط مترو، ماتریس بارنامه × ایستگاه، گذارهای مستقیم، سهم هر فایل و اثر انگشت شواهد (الگوریتم در
    :mod:`gsi.report.shipping_journey`)."""
    j = m.journey
    if j.empty:
        return _empty(lang)
    k = j.kpis
    tiles = [("jbl", "ship", "بارنامه", f'{k["bl"]:,}', "brand"),
             ("jcl", "eye", "روشنی مسیر", "—" if k["clarity"] is None else f'{k["clarity"]}٪', "brand"),
             ("jcf", "search", "ایستگاه متعارض", f'{k["conflict"]:,}', "warning" if k["conflict"] else "brand"),
             ("jrv", "exchange", "وارونگی ترتیب", f'{k["reversal"]:,}', "critical" if k["reversal"] else "brand"),
             ("jeb", "users", "کارشناس عقب‌تر از شواهد", f'{k["expert_behind"]:,}', "brand"),
             ("jea", "users", "کارشناس جلوتر از شواهد", f'{k["expert_ahead"]:,}', "brand")]
    hero = "".join(I.kpi_tile(ic, J._t(lab, lang), v, tone=tone) for _, ic, lab, v, tone in tiles)
    return (f'<div class="mi-kpis">{hero}</div>'
            + J.metro(j, lang, _k)
            + _sec("layers", "مسیر شواهد", lang) + J.legend(lang)
            + J.matrix(j, lang, frame, _bl_attrs(m), YES, max_rows=max_rows)
            + _sec("flow", "گذار مستقیم", lang) + J.flow_view(j, lang)
            + _sec("database", "سهم هر فایل در روشن کردن وضعیت", lang) + J.sources_view(j, lang)
            + _sec("bars", "اثر انگشت شواهد", lang) + J.fingerprint_view(j, lang)
            + f'<details class="j-notes"><summary>{I.icon("book", 14)}</summary>'
            + "".join(f'<div class="gx-note">{L(n, lang)}</div>' for n in (NOTE_JOURNEY, NOTE_FLOW, NOTE_SHAPLEY))
            + "</details>")


SECTIONS = [("layers", "مسیر شواهد", journey_section), ("gauge", "نمای کلی", kpi_section), ("flow", "مراحل و مدت‌ها", stages_section),
            ("file", "پرونده بارنامه‌ها", dossier_section), ("queue", "پیگیری ترخیص", followup_section),
            ("box", "پارت‌های کارشناسان", expert_section),
            ("database", "پوشش و کمبود داده", gaps_section)]


# ═══════════════════════════════ HTML مستقل ═══════════════════════════════
_JS = """
(function(){
  var fa='۰۱۲۳۴۵۶۷۸۹', ar='٠١٢٣٤٥٦٧٨٩';
  function lat(s){return (s||'').replace(/[۰-۹]/g,function(c){return fa.indexOf(c)}).replace(/[٠-٩]/g,function(c){return ar.indexOf(c)}).trim();}
  function nd(s){s=lat(s).replace(/-/g,'/');var p=s.split('/');if(p.length!==3)return '';
    return p[0]+'/'+('0'+p[1]).slice(-2)+'/'+('0'+p[2]).slice(-2);}
  var q=document.getElementById('sc-q'), a=document.getElementById('sc-a'), b=document.getElementById('sc-b'),
      u=document.getElementById('sc-u'), n=document.getElementById('sc-n'), x=document.getElementById('sc-x'),
      bs=document.getElementById('sc-bs');
  document.querySelectorAll('.sc-k').forEach(function(k){var v=k.querySelector('.mi-kpi-val');if(v)k.setAttribute('data-o',v.textContent);});
  function setk(key,val){document.querySelectorAll('.sc-k[data-k="'+key+'"] .mi-kpi-val').forEach(function(v){v.textContent=val.toLocaleString();});}
  function tally(sel,fn){var t=document.querySelector(sel);if(!t||!t.hasAttribute('data-whole'))return false;
    t.querySelectorAll('tbody tr').forEach(function(tr){if(tr.style.display!=='none')fn(tr);});return true;}
  function run(){
    var qs=lat(q.value).toLowerCase(), av=nd(a.value), bv=nd(b.value), bi=bs?bs.value:'0', shown=0, all=0;
    document.querySelectorAll('.sc-filterable tbody tr').forEach(function(tr){
      var ok=true, d=tr.getAttribute('data-d')||'';
      if(bi!=='0' && tr.hasAttribute('data-b'+bi)) d=tr.getAttribute('data-b'+bi)||'';
      if(qs && tr.textContent.toLowerCase().indexOf(qs)<0) ok=false;
      if(ok && (av||bv)){ if(!d){ok=u.checked;} else { if(av && d<av) ok=false; if(bv && d>bv) ok=false; } }
      tr.style.display=ok?'':'none'; all++; if(ok) shown++;
    });
    n.textContent=shown.toLocaleString()+' / '+all.toLocaleString();
    var on=!!(qs||av||bv);
    if(!on){document.querySelectorAll('.sc-k').forEach(function(k){var v=k.querySelector('.mi-kpi-val');if(v&&k.hasAttribute('data-o'))v.textContent=k.getAttribute('data-o');});return;}
    var c={total:0,s0:0,s1:0,s2:0,s3:0,co:0,cf:0};
    if(tally('.gx-tbl[data-key="dossiers"]',function(tr){c.total++;var s=tr.getAttribute('data-s');if(s!==null&&s!=='')c['s'+s]++;
        if(tr.hasAttribute('data-co'))c.co++;if(tr.hasAttribute('data-cf'))c.cf++;})){for(var k in c)setk(k,c[k]);}
    var jm={};document.querySelectorAll('.sc-k[data-k^="j"]').forEach(function(k){jm[k.getAttribute('data-k')]=0;});
    if(tally('.gx-tbl[data-key="journey"]',function(tr){var c='j'+(tr.getAttribute('data-cur')||'START');if(c in jm)jm[c]++;})){for(var k3 in jm)setk(k3,jm[k3]);}
    var e={eIN_CUSTOMS:0,eIN_TRANSIT:0,eREADY:0,eAT_SUPPLIER:0,eUNRECOGNIZED:0,enb:0,eeo:0};
    if(tally('.gx-tbl[data-key="expert"]',function(tr){var s=tr.getAttribute('data-e');if(s)e['e'+s]++;
        if(tr.hasAttribute('data-enb'))e.enb++;if(tr.hasAttribute('data-eeo'))e.eeo++;})){for(var k2 in e)setk(k2,e[k2]);}
  }
  [q,a,b].forEach(function(e){e.addEventListener('input',run);}); u.addEventListener('change',run);
  if(bs) bs.addEventListener('change',run);
  x.addEventListener('click',function(){q.value='';a.value='';b.value='';u.checked=false;if(bs)bs.value='0';run();});
  run();
})();
"""


def filter_bar(lang: str = FA) -> str:
    """نوار فیلتر سمت کاربر (فقط HTML مستقل؛ Studio با ویجت‌های خودش همین فیلتر را دارد)."""
    return (f'<div class="sc-filter" role="search"><input id="sc-q" class="sc-q" type="text" '
            f'placeholder="{html.escape(t("جستجو در جدول‌ها", lang), quote=True)}">'
            f'<label>{L("از تاریخ", lang)} <input id="sc-a" type="text" dir="ltr" size="10" placeholder="1405/01/01"></label>'
            f'<label>{L("تا تاریخ", lang)} <input id="sc-b" type="text" dir="ltr" size="10" placeholder="1405/12/29"></label>'
            f'<label>{L("مبنای تاریخ", lang)} <select id="sc-bs">'
            + "".join(f'<option value="{i}">{html.escape(t(k, lang))}</option>' for i, k in enumerate(BASIS_KEYS))
            + '</select></label>'
            f'<label><input id="sc-u" type="checkbox"> {L("ردیف‌های بی‌تاریخ هم باشند", lang)}</label>'
            f'<button id="sc-x" type="button">{L("پاک کردن", lang)}</button>'
            f'<span class="sc-count"><span id="sc-n"></span> {L("ردیف نمایش داده شده", lang)}</span></div>'
            f'<div class="gx-note">{L(NOTE_FILTER, lang)} {L(NOTE_FILTER_SCOPE, lang)} {L(NOTE_FILTER_HTML, lang)}</div>')


@H._css_icons
def _tabs(panes: List[str], lang: str, key: str = "sc") -> str:
    gid = H.uid("tabs", key)
    radios = "".join(f'<input type="radio" class="gx-t gx-t{i}" name="{gid}" id="{gid}-{i}"{" checked" if i == 0 else ""}>'
                     for i in range(len(panes)))
    labels = "".join(f'<label class="gx-tb gx-tb{i}" for="{gid}-{i}">{I.icon(ic, 16)}{L(title, lang)}</label>'
                     for i, (ic, title, _) in enumerate(SECTIONS[:len(panes)]))
    body = "".join(f'<section class="gx-tpane gx-tp{i}">{p}</section>' for i, p in enumerate(panes))
    return f'{radios}<nav class="gx-tabs">{labels}</nav><div class="gx-tpanes">{body}</div>'


@H._css_icons
def build_html(model_or_df: Any, extras: Any = None, ref_date: Any = "", lang: str = FA, title: str = "",
               embed_excel: bool = True, embed_fonts: Optional[bool] = None) -> str:
    """صفحه HTML مستقل و آفلاین «حمل و ترخیص» — همان تکه‌های Studio، فونت سازمانی جاسازی‌شده،
    فیلتر متن و بازه تاریخ سمت کاربر و (اختیاری) Excel همین گزارش داخل خود فایل."""
    from ..design import fonts as F
    from ..design.css import stylesheet

    m = model_or_df if isinstance(model_or_df, ShippingModel) else build_model(model_or_df, extras, ref_date)
    title = title or t("گزارش حمل و ترخیص", lang)
    if m.empty:
        body = _empty(lang)
    else:
        panes = [fn(m, lang) for _, _, fn in SECTIONS]
        body = filter_bar(lang) + _tabs(panes, lang)
    dl = ""
    if embed_excel and not m.empty:
        name = f"GSI_SHIPPING_CLEARANCE_{(m.ref_date or 'report').replace('/', '-')}{'_EN' if lang == EN else ''}.xlsx"
        dl = (f'<div class="gx-dls">{H.data_link(build_excel(m, lang), name, t("دانلود Excel حمل و ترخیص", lang), "file")}'
              '</div>').replace("gx-dl", "gx-dl is-primary", 1)
    chips = ""
    if not m.empty:
        co = m.counts.get("critical_open", 0)
        chips = (f'<div class="gx-chips"><span class="gx-chip"><b>{m.total:,}</b>{L("بارنامه", lang)}</span>'
                 f'<span class="gx-chip"><b>{m.counts.get("orders", 0):,}</b>{L("سفارش", lang)}</span>'
                 f'<span class="gx-chip"><b>{len(m.expert):,}</b>{L("پارت‌های کارشناسان", lang)}</span>'
                 f'<span class="gx-chip{" is-alert" if co else ""}"><b>{co:,}</b>'
                 f'{L("بارنامه بحرانی ترخیص‌نشده", lang)}</span></div>')
    ref = _jal(m.ref_date) or m.ref_date
    sub = (f'{L("تاریخ مرجع", lang)} <span class="ltr">{html.escape(ref)}</span>' if ref else "")
    font_css = F.html_font_css() if (embed_fonts is None or embed_fonts) else ""
    page_dir = 'lang="en" dir="ltr"' if lang == EN else 'lang="fa" dir="rtl"'
    script = f"<script>{_JS}</script>" if not m.empty else ""
    return (f'<!DOCTYPE html><html {page_dir}><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{font_css}{stylesheet()}{H.css()}{CSS}</style></head><body class="gx gx-page"><main class="gx-wrap">'
            f'{_BRAND.band_raw(html.escape(title), sub_html=sub, eyebrow_html=L("بارنامه · حمل · گمرک · ترخیص", lang), side_html=chips, tag=L(_BRAND.TAGLINE_FA, lang))}{dl}{body}'
            f'<p class="gx-legal">{L(NOTE_LEGAL, lang)}</p></main>{script}</body></html>')


# ═══════════════════════════════ Excel ═══════════════════════════════
SHEETS = [("خلاصه", "Summary"), ("پرونده بارنامه", "BL dossiers"), ("پیگیری ترخیص", "Clearance follow-up"),
          ("مدت‌ها", "Durations"), ("کمبود داده", "Data gaps"), ("پوشش شواهد", "Evidence coverage"),
          ("پارت‌های کارشناسان", "Expert shipments"), ("مسیر شواهد", "Evidence route"),
          ("سهم منابع", "Source shares"), ("گذار مستقیم", "Directly-follows")]


def summary_pairs(m: ShippingModel, lang: str = FA) -> List[tuple]:
    if m.empty:
        return [(t("تاریخ مرجع", lang), m.ref_date or "—"), (t("نکته", lang), t(NOTE_EMPTY, lang))]
    c = m.counts
    pairs = [("تاریخ مرجع", _jal(m.ref_date) or m.ref_date or "—"), ("بارنامه یکتا", c.get("total", 0)),
             ("بارنامه در راه", c.get(ST_TRANSIT, 0)), (ST_ARRIVED, c.get(ST_ARRIVED, 0)),
             (ST_PARTIAL, c.get(ST_PARTIAL, 0)), (ST_FULL, c.get(ST_FULL, 0)),
             ("بارنامه بحرانی ترخیص‌نشده", c.get("critical_open", 0)), ("بارنامه با مغایرت شاهد", c.get("conflicts", 0))]
    pairs += [(f'{t("روز پس از تخلیه در بارنامه‌های بدون ترخیص کامل", lang)} · {t(r["دسته"], lang)}', int(r["بارنامه"]))
              for _, r in m.ages.iterrows()]
    pairs += [(lab, c.get("exp_" + code, 0)) for code, _, lab in EXP_TILES]
    pairs += [("پارت بی‌بارنامه", c.get("exp_no_bl", 0)),
              ("بارنامه فقط در فایل کارشناسان", c.get("exp_expert_only", 0))]
    pairs += [("نکته", n) for n in m.notes + [NOTE_CRITICAL, NOTE_DURATION]]
    return [(t(k, lang), t(v, lang) if isinstance(v, str) else v) for k, v in pairs]


def build_excel(m: ShippingModel, lang: str = FA) -> bytes:
    """Excel گزارش: خلاصه، پرونده بارنامه، پیگیری، مدت‌ها، کمبود داده و پوشش شواهد؛
    همان سبک Excelهای چرخه ارز (راست‌چین، سرستون فیروزه‌ای، فیلتر و سطر ثابت)."""
    from openpyxl import Workbook

    from . import fx_excel as XL

    wb = Workbook()
    wb.remove(wb.active)

    def name(i: int) -> str:
        return SHEETS[i][1] if lang == EN else SHEETS[i][0]

    title = t("گزارش حمل و ترخیص", lang)
    XL.add_key_values(wb, name(0), summary_pairs(m, lang), lang=lang, title=title,
                      note=t(NOTE_GRAIN, lang))
    frames = [m.dossiers, m.follow_up, m.durations, m.gaps, m.coverage, m.expert, J.export_frame(m.journey, lang),
              m.journey.sources, m.journey.flow]
    notes = [NOTE_GRAIN, "بارنامه‌های بدون ترخیص کامل، به ترتیب بیشترین روز پس از تخلیه.", NOTE_DURATION,
             NOTE_GAPS,
             "مخرج: شمار بارنامه یکتای همین دامنه.", NOTE_EXPERT, NOTE_JOURNEY, NOTE_SHAPLEY, NOTE_FLOW]
    for i, (f, note) in enumerate(zip(frames, notes), 1):
        XL.add_frame(wb, name(i), display_frame(f, lang), lang=lang, title=f"{title} · {name(i)}", note=t(note, lang))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def write_report(df: pd.DataFrame, extras: Any, ref_date: str, out_dir: Any, lang: str = FA) -> Dict[str, Any]:
    """HTML و Excel را در ``out_dir`` می‌نویسد و مسیرها را برمی‌گرداند."""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    m = build_model(df, extras, ref_date)
    stem = f"GSI_SHIPPING_CLEARANCE_{(X.s(ref_date) or 'report').replace('/', '-')}{'_EN' if lang == EN else ''}"
    h = out / f"{stem}.html"
    h.write_text(build_html(m, lang=lang), encoding="utf-8")
    x = out / f"{stem}.xlsx"
    x.write_bytes(build_excel(m, lang))
    return {"html": h, "excel": x}
