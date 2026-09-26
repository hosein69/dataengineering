# -*- coding: utf-8 -*-
"""Defect taxonomy — the stable vocabulary of the data-trust layer.

Every defect the system reports is one of these codes. The code is a stable
identifier (never renamed, never reused) because worklists, trend history and
owner scorecards are keyed by it.

Three properties of a code carry real operational weight:

``state``
    ``MISSING`` and ``SUSPECT`` are deliberately different. *Missing* means
    nobody filled the cell — it is fixed by data entry. *Suspect* means somebody
    filled it with something that cannot be right — it needs a human to decide
    what the truth is. Routing them to the same worklist wastes the expert's
    time on cells a clerk could fill.

``fix_type``
    Who can actually close it. A defect nobody can act on is noise; a defect
    routed to the wrong role is worse than no defect at all.

``dimension``
    The DAMA/ISO-8000 quality dimension, so the scorecard can roll up by cause
    ("we have a completeness problem", not "we have 4,000 defects").
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, Tuple

# ── value states ────────────────────────────────────────────────────────────
OK = "OK"                # present and passes its checks
MISSING = "MISSING"      # absent: blank, NaN, or a placeholder such as "-"
SUSPECT = "SUSPECT"      # present but cannot be right
CONFLICT = "CONFLICT"    # two sources/rows disagree for the same key

#: Worse-first. Used when one field collects several verdicts.
STATE_RANK: Dict[str, int] = {OK: 0, MISSING: 1, SUSPECT: 2, CONFLICT: 3}

STATE_FA: Dict[str, str] = {
    OK: "سالم",
    MISSING: "خالی",
    SUSPECT: "مشکوک",
    CONFLICT: "متعارض",
}

# ── quality dimensions (DAMA / ISO 8000) ────────────────────────────────────
COMPLETENESS = "COMPLETENESS"
VALIDITY = "VALIDITY"
CONSISTENCY = "CONSISTENCY"
UNIQUENESS = "UNIQUENESS"
TIMELINESS = "TIMELINESS"

DIMENSION_FA: Dict[str, str] = {
    COMPLETENESS: "کامل‌بودن",
    VALIDITY: "اعتبار",
    CONSISTENCY: "سازگاری",
    UNIQUENESS: "یکتایی",
    TIMELINESS: "به‌هنگام‌بودن",
}

# ── who can close the defect ────────────────────────────────────────────────
#: A clerk/expert types the missing value into the source file.
DATA_ENTRY = "DATA_ENTRY"
#: Someone must decide which of two contradictory facts is true.
INVESTIGATION = "INVESTIGATION"
#: The producing system/export must change; no amount of typing fixes it.
SOURCE_CONTRACT = "SOURCE_CONTRACT"

FIX_TYPE_FA: Dict[str, str] = {
    DATA_ENTRY: "تکمیل داده",
    INVESTIGATION: "بررسی و رفع تعارض",
    SOURCE_CONTRACT: "اصلاح قرارداد سورس",
}


@dataclass(frozen=True)
class DefectCode:
    """One kind of defect, with everything needed to route and explain it."""
    code: str
    state: str
    dimension: str
    fix_type: str
    title_fa: str
    #: Imperative, addressed to the owner. This is what lands in the worklist.
    action_fa: str

    @property
    def state_fa(self) -> str:
        return STATE_FA.get(self.state, self.state)

    @property
    def dimension_fa(self) -> str:
        return DIMENSION_FA.get(self.dimension, self.dimension)

    @property
    def fix_type_fa(self) -> str:
        return FIX_TYPE_FA.get(self.fix_type, self.fix_type)


def _c(code, state, dimension, fix_type, title_fa, action_fa) -> DefectCode:
    return DefectCode(code, state, dimension, fix_type, title_fa, action_fa)


#: The catalogue. Grounded in defects actually observed in GSI sources.
CODES: Tuple[DefectCode, ...] = (
    # ── completeness ────────────────────────────────────────────────────────
    _c("VALUE_MISSING", MISSING, COMPLETENESS, DATA_ENTRY,
       "مقدار خالی است",
       "مقدار این سلول را در فایل منبع وارد کنید."),
    _c("VALUE_PLACEHOLDER", MISSING, COMPLETENESS, DATA_ENTRY,
       "مقدار جای‌نگهدار است",
       "به‌جای «نامشخص/-/0» مقدار واقعی را وارد کنید، یا اگر واقعاً وجود ندارد سلول را خالی بگذارید."),
    _c("KEY_MISSING", MISSING, COMPLETENESS, DATA_ENTRY,
       "کلید کسب‌وکار ندارد",
       "کد ثبت سفارش/سفارش/بارنامه این ردیف را وارد کنید؛ بدون کلید، ردیف به هیچ پرونده‌ای وصل نمی‌شود."),
    _c("OWNER_UNKNOWN", MISSING, COMPLETENESS, SOURCE_CONTRACT,
       "مالک مشخص نیست",
       "نام کارشناس/اداره مسئول این ردیف در سورس موجود نیست؛ بدون آن، ایراد قابل ارجاع نیست."),

    # ── validity ────────────────────────────────────────────────────────────
    _c("VALUE_UNPARSEABLE", SUSPECT, VALIDITY, INVESTIGATION,
       "مقدار قابل خواندن نیست",
       "متن این سلول عدد/تاریخ معتبر نیست؛ مقدار درست را جایگزین کنید."),
    _c("VALUE_NEGATIVE", SUSPECT, VALIDITY, INVESTIGATION,
       "مقدار منفی است",
       "مبلغ/مقدار منفی در این فیلد معنا ندارد؛ علت را بررسی کنید."),
    _c("DATE_INVALID", SUSPECT, VALIDITY, INVESTIGATION,
       "تاریخ نامعتبر است",
       "تاریخ در تقویم وجود ندارد (مثل ۳۰ اسفند سال غیرکبیسه)؛ تاریخ درست را ثبت کنید."),
    _c("DATE_FUTURE", SUSPECT, VALIDITY, INVESTIGATION,
       "تاریخ بعد از تاریخ مرجع است",
       "رویدادی که هنوز رخ نداده تاریخ نمی‌گیرد؛ تاریخ را اصلاح یا خالی کنید."),
    _c("CURRENCY_UNKNOWN", SUSPECT, VALIDITY, SOURCE_CONTRACT,
       "ارز شناسایی نشد",
       "نام ارز با هیچ کد ISO تطبیق نخورد؛ املای استاندارد را به کتابخانه ارزها اضافه کنید."),
    _c("CURRENCY_AMBIGUOUS", SUSPECT, VALIDITY, INVESTIGATION,
       "ارز مبهم است",
       "در یک سلول بیش از یک ارز آمده؛ ارز واقعی این رکورد را مشخص کنید."),
    _c("KEY_PLACEHOLDER", SUSPECT, VALIDITY, SOURCE_CONTRACT,
       "کلید جای‌نگهدار است",
       "کلیدهایی مثل «0» یا «000» کلید واقعی نیستند و باعث اتصال غلط پرونده‌ها می‌شوند."),

    # ── consistency ─────────────────────────────────────────────────────────
    _c("VALUE_CONFLICT", CONFLICT, CONSISTENCY, INVESTIGATION,
       "دو مقدار متفاوت برای یک کلید",
       "دو منبع/ردیف برای همین کلید دو مقدار می‌گویند؛ مقدار درست را تعیین کنید."),
    _c("DATE_SEQUENCE", SUSPECT, CONSISTENCY, INVESTIGATION,
       "ترتیب تاریخ‌ها ناممکن است",
       "رویداد بعدی قبل از رویداد قبلی ثبت شده؛ کدام تاریخ اشتباه است؟"),
    _c("CURRENCY_MIXED", CONFLICT, CONSISTENCY, INVESTIGATION,
       "چند ارز در یک پرونده",
       "جمع این پرونده بدون تبدیل ارز ممکن نیست؛ تفکیک یا مبنای تبدیل مستند لازم است."),
    _c("ORPHAN_REFERENCE", SUSPECT, CONSISTENCY, INVESTIGATION,
       "ارجاع بی‌مقصد",
       "این ردیف به کلیدی ارجاع می‌دهد که در سورس مرجع وجود ندارد."),

    # ── uniqueness ──────────────────────────────────────────────────────────
    _c("DUPLICATE_SNAPSHOT", SUSPECT, UNIQUENESS, SOURCE_CONTRACT,
       "ردیف تکراری",
       "یک رکورد چند بار در export آمده؛ جمع را متورم می‌کند. خروجی سورس باید یکتا شود."),

    # ── timeliness ──────────────────────────────────────────────────────────
    _c("STALE_OBSERVATION", SUSPECT, TIMELINESS, DATA_ENTRY,
       "مشاهده قدیمی است",
       "آخرین به‌روزرسانی این رکورد از بودجه تازگی گذشته؛ وضعیت فعلی را تأیید کنید."),
)

BY_CODE: Dict[str, DefectCode] = {c.code: c for c in CODES}


def get(code: str) -> DefectCode:
    """Look up a code, failing loudly on a typo.

    A silently-unknown defect code would quietly vanish from every scorecard,
    so this raises instead of returning a default.
    """
    try:
        return BY_CODE[code]
    except KeyError:
        raise KeyError(f"کد ایراد ناشناخته: {code!r} — باید در gsi/trust/codes.py تعریف شود") from None


def state_of(code: str) -> str:
    return get(code).state


def worst_state(states) -> str:
    """Worst state in an iterable; ``OK`` for an empty one."""
    worst, rank = OK, 0
    for s in states:
        r = STATE_RANK.get(s, 0)
        if r > rank:
            worst, rank = s, r
    return worst


__all__ = [
    "OK", "MISSING", "SUSPECT", "CONFLICT", "STATE_RANK", "STATE_FA",
    "COMPLETENESS", "VALIDITY", "CONSISTENCY", "UNIQUENESS", "TIMELINESS", "DIMENSION_FA",
    "DATA_ENTRY", "INVESTIGATION", "SOURCE_CONTRACT", "FIX_TYPE_FA",
    "DefectCode", "CODES", "BY_CODE", "get", "state_of", "worst_state",
]
