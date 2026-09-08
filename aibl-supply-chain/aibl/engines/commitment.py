# -*- coding: utf-8 -*-
"""موتور رفع تعهد ارزی — کاملاً داده‌محور از روی RuleBook.

هیچ مهلت، نرخ جریمه یا آستانه‌ای در این فایل هاردکد نیست؛ همه از
``aibl/rules/fx_governance.yaml`` و ``alarms.yaml`` خوانده می‌شود.
تغییر یک مهلت قانونی = ویرایش یک عدد در YAML، بدون تغییر کد.
"""
from __future__ import annotations

__contract__ = 2   # ← aibl/contracts.py

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val, normalize_persian_text, num_safe
from ..rulebook import RuleBook, get_rulebook

CLEARANCE_FULL = "ترخیص کامل"
CLEARANCE_PARTIAL = "ترخیص درصدی"
CLEARANCE_NONE = "عدم ترخیص"


# ═══════════ توابع کمکی مستقل (قابل تست جداگانه) ═══════════
def is_barat(value: Any, rb: Optional[RuleBook] = None) -> bool:
    rb = rb or get_rulebook()
    return rb.detect_payment_method(value) == "BARAT"


def detect_payment_method(value: Any, rb: Optional[RuleBook] = None) -> str:
    """کد روش پرداخت (BARAT / LC / CASH / SIGHT_DRAFT / OTHER)."""
    rb = rb or get_rulebook()
    return rb.detect_payment_method(value)


def payment_method_fa(code: str, rb: Optional[RuleBook] = None) -> str:
    rb = rb or get_rulebook()
    for m in rb.get("fx_governance.payment_methods", []) or []:
        if m["code"] == code:
            return m["fa"]
    return code


def detect_clearance_type(full_date: Any, partial_date: Any, amount: Any = "",
                          hint: str = "", rb: Optional[RuleBook] = None) -> str:
    """§۶-د — نوع ترخیص. ``hint`` از واژگان وضعیت فایل مقاومت می‌آید."""
    rb = rb or get_rulebook()
    if not is_empty_val(full_date) or hint == "FULL":
        return CLEARANCE_FULL
    if not is_empty_val(partial_date) or hint == "PARTIAL":
        return CLEARANCE_PARTIAL
    types = rb.get("customs.clearance_types", []) or []
    markers = []
    for t in types:
        if t.get("code") == "PARTIAL":
            markers = t.get("detect", {}).get("when_value_matches", []) or []
    s = normalize_persian_text(amount)
    if s and (any(str(m) in s for m in markers) or num_safe(s) > 0):
        return CLEARANCE_PARTIAL
    return CLEARANCE_NONE


def legal_deadline(cb_date: Optional[date], segment: str,
                   barat_due: Optional[date] = None,
                   rb: Optional[RuleBook] = None) -> Optional[date]:
    """زودترین مهلت میان «CB + مهلت سگمنت» و «سررسید برات + مهلت پس از سررسید»."""
    rb = rb or get_rulebook()
    candidates = []
    if cb_date:
        candidates.append(cb_date + timedelta(days=rb.release_deadline_days(segment)))
    if barat_due:
        candidates.append(barat_due + timedelta(
            days=int(rb.deadline_days("release_after_barat_due") or 90)))
    return min(candidates) if candidates else None


def default_barat_due(bl_date: Optional[date], rb: Optional[RuleBook] = None) -> Optional[date]:
    rb = rb or get_rulebook()
    days = int(rb.deadline_days("default_barat_tenor") or 180)
    return bl_date + timedelta(days=days) if bl_date else None


def delay_penalty(outstanding: float, overdue_days: int,
                  rb: Optional[RuleBook] = None) -> float:
    """جریمه پلکانی طبق ``fx_governance.penalties.delay_tiers``."""
    rb = rb or get_rulebook()
    if outstanding <= 0 or overdue_days <= 0:
        return 0.0
    months = overdue_days / 30.0
    total, consumed = 0.0, 0.0
    for up_to, rate in rb.penalty_tiers():
        cap = float(up_to) if up_to is not None else float("inf")
        span = max(0.0, min(months, cap) - consumed)
        total += outstanding * span * rate
        consumed = min(months, cap)
        if consumed >= months:
            break
    return round(total, 2)


def alarm_status(alarm_key: str, days: Optional[float], segment: str,
                 rb: Optional[RuleBook] = None) -> Tuple[str, str]:
    rb = rb or get_rulebook()
    green, yellow, red = (rb.status_label("green"), rb.status_label("yellow"),
                          rb.status_label("red"))
    if days is None:
        return green, "داده ناقص"
    t = (rb.thresholds(segment) or {}).get(alarm_key)
    if not t:
        return green, "تعریف نشده"
    label = t.get("fa", alarm_key)
    y_min, y_max = t.get("yellow", [0, 0])
    if days >= float(t["red"]):
        return red, f"{label}: {days:.0f} روز — عبور از سقف قانونی {t['legal']} روز"
    if float(y_min) <= days < float(y_max):
        return yellow, f"{label}: {days:.0f} روز — بازه هشدار ({y_min}–{y_max})"
    return green, f"{label}: {days:.0f} روز — مجاز"


# ═══════════ نتیجه ═══════════
@dataclass
class CommitmentResult:
    segment: str = "production"
    segment_fa: str = "تولیدی"
    payment_method: str = "OTHER"
    payment_method_fa: str = "سایر"
    clearance_type: str = CLEARANCE_NONE
    is_barat: bool = False
    deadline: Optional[date] = None
    overdue_days: int = 0
    outstanding: float = 0.0
    penalty: float = 0.0
    alarms: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    worst_status: str = "سبز"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "نوع پرونده": self.segment_fa,
            "کد سگمنت": self.segment,
            "روش پرداخت": self.payment_method_fa,
            "نوع ترخیص": self.clearance_type,
            "برات/یوزانس": "بله" if self.is_barat else "خیر",
            "مهلت قانونی رفع تعهد": self.deadline.isoformat() if self.deadline else "",
            "روزهای تأخیر": self.overdue_days,
            "مانده تعهد": self.outstanding,
            "جریمه برآوردی": self.penalty,
            "وضعیت کلی هشدار": self.worst_status,
            "شرح هشدارها": " ؛ ".join(d for _, d in self.alarms.values()),
        }


class CommitmentEngine:

    def __init__(self, rb: Optional[RuleBook] = None) -> None:
        self.rb = rb or get_rulebook()

    def evaluate(self, row: Dict[str, Any], today: date) -> CommitmentResult:
        rb = self.rb
        segment = rb.detect_segment(row.get("SEGMENT", ""))
        seg_fa = next((s["fa"] for s in rb.get("fx_governance.segments", []) or []
                       if s["code"] == segment), segment)

        pm = detect_payment_method(row.get("PAYMENT_METHOD", ""), rb)
        res = CommitmentResult(
            segment=segment, segment_fa=seg_fa,
            payment_method=pm, payment_method_fa=payment_method_fa(pm, rb),
            is_barat=(pm == "BARAT"),
        )
        res.clearance_type = detect_clearance_type(
            row.get("FULL_CLEAR_DATE"), row.get("PARTIAL_CLEAR_DATE"),
            row.get("CLEAR_AMOUNT"), str(row.get("CLEARANCE_HINT", "")), rb)

        P = CalendarEngine.parse
        cb_date = P(row.get("CB_DATE")) or P(row.get("BUY_DATE"))
        bl_date = P(row.get("BL_DATE"))
        barat_due = P(row.get("BARAT_DUE")) or (default_barat_due(bl_date, rb)
                                                if res.is_barat else None)

        res.deadline = legal_deadline(cb_date, segment, barat_due, rb)
        if res.deadline:
            res.overdue_days = max(0, (today - res.deadline).days)

        res.outstanding = num_safe(row.get("BALANCE", row.get("CB_VALUE", 0)))
        res.penalty = delay_penalty(res.outstanding, res.overdue_days, rb)

        d = CalendarEngine.days_between
        spans = {
            "alarm1_buy_to_docs": d(row.get("BUY_DATE"), row.get("DOC_SUBMIT_DATE")),
            "alarm2_buy_to_fin": d(row.get("BUY_DATE"), row.get("FIN_RECEIPT_DATE")),
            "alarm3_clear_to_sata": d(row.get("FULL_CLEAR_DATE"), row.get("SATA_DATE")),
            "days_since_buy": d(row.get("BUY_DATE"), today),
            "days_since_sata": d(row.get("SATA_DATE"), today),
            "days_since_doc": d(row.get("DOC_SUBMIT_DATE"), today),
            "bl_age": d(row.get("BL_DATE"), today),
            "payment_age": d(row.get("CB_DATE"), today),
        }
        ranks = {rb.status_label(c): rb.status_rank(c) for c in ("green", "yellow", "red")}
        res.worst_status = rb.status_label("green")
        for k, days in spans.items():
            st, desc = alarm_status(k, days, segment, rb)
            res.alarms[k] = (st, desc)
            if ranks.get(st, 0) > ranks.get(res.worst_status, 0):
                res.worst_status = st
        return res
