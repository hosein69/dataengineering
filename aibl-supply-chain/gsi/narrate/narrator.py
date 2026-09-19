# -*- coding: utf-8 -*-
"""راوی شناختی فارسی — ۵ شاخه روایت (§۹).

B1 (FIX) — مهم‌ترین اصلاح منطقی: در نسخه ۲۰.۱ راوی داخل حلقه‌ای اجرا می‌شد که
ستون‌های COTAGE_NO / SATA_NO / تاریخ تخلیه هنوز ساخته نشده بودند (آن‌ها بعد از
حلقه به df اضافه می‌شدند). نتیجه: برای *تمام* ردیف‌ها شواهد گمرکی «مفقود»
تلقی می‌شد و «درصد قطعیت» همیشه روی ۲۵٪ قفل بود. اینجا راوی یک گام مستقل و
**پس از** تکمیل تمام ستون‌های مشتق اجرا می‌شود و ورودی‌اش صریحاً اعتبارسنجی می‌گردد.

FIX-9 — بررسی وجود کوتاژ/ساتا با ``is_empty_val`` انجام می‌شود نه truthiness
(رشته "0" یا "نامشخص" دیگر «موجود» شمرده نمی‌شود).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val
from ..engines.commitment import (CLEARANCE_FULL, CLEARANCE_NONE,
                                  CLEARANCE_PARTIAL)
from ..engines.math_engine import DoctoralMathEngine
from ..rulebook import get_rulebook

REQUIRED_FIELDS = ("CANONICAL_BL", "COTAGE_NO", "SATA_NO", "DISCHARGE_DATE")


@dataclass
class Narration:
    narrative: str
    recommendation: str
    confidence: int
    stuck_days: float
    is_critical: bool
    survival_pct: float
    customs_prob: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "روایت اختصاصی بارنامه": self.narrative,
            "پیشنهاد عملیاتی هوش مصنوعی": self.recommendation,
            "درصد قطعیت": self.confidence,
            "روزهای رسوب": self.stuck_days,
            "وضعیت هوشمند": "بحرانی (رسوب شدید)" if self.is_critical else "در جریان ترخیص",
            "احتمال بقای ویبول (٪)": self.survival_pct,
            "احتمال حضور در گمرک (٪)": self.customs_prob,
        }


class DynamicGranularNarrator:

    @staticmethod
    def validate_input(row: Dict[str, Any]) -> None:
        """گارد ضد باگ B1: اگر ستون‌های شاهد وجود نداشته باشند، خطای صریح."""
        missing = [f for f in REQUIRED_FIELDS if f not in row]
        if missing:
            raise KeyError(
                f"راوی زودتر از ساخت ستون‌های مشتق فراخوانی شده است. ستون‌های غایب: {missing}")

    @classmethod
    def generate(cls, row: Dict[str, Any], today: date,
                 conflict: Optional[str] = None, validate: bool = True) -> Narration:
        if validate:
            cls.validate_input(row)

        bl = row.get("CANONICAL_BL") or "نامشخص"
        order = row.get("CANONICAL_ORDER") or "نامشخص"
        pn = row.get("CANONICAL_PART_NO") or "نامشخص"
        goods = row.get("CANONICAL_GOODS_DESC") or "قطعات خودرو"
        expert = row.get("CANONICAL_EXPERT") or "نامشخص"

        discharge = CalendarEngine.parse(row.get("DISCHARGE_DATE"))
        full_clear = CalendarEngine.parse(row.get("FULL_CLEAR_DATE"))
        partial_clear = CalendarEngine.parse(row.get("PARTIAL_CLEAR_DATE"))
        hint = str(row.get("CLEARANCE_HINT", ""))
        clearance_type = (CLEARANCE_FULL if (full_clear or hint == "FULL")
                          else CLEARANCE_PARTIAL if (partial_clear or hint == "PARTIAL")
                          else CLEARANCE_NONE)

        has_cotage = not is_empty_val(row.get("COTAGE_NO"))
        has_sata = not is_empty_val(row.get("SATA_NO"))
        has_discharge = discharge is not None

        evidence = DoctoralMathEngine.evidence_list(has_discharge, has_cotage, has_sata)
        missing: List[str] = []
        if not has_discharge:
            missing.append("تاریخ تخلیه کشتی")
        if not has_cotage:
            missing.append("شماره کوتاژ گمرکی")
        if not has_sata:
            missing.append("کد رهگیری ساتا")
        if is_empty_val(row.get("CANONICAL_ORDER")):
            missing.append("شماره سفارش")

        stuck = float((today - discharge).days) if discharge else 0.0
        critical_days = get_rulebook().demurrage_critical_days()
        is_critical = stuck > critical_days and clearance_type == CLEARANCE_NONE
        prob = DoctoralMathEngine.bayesian_customs_prob(evidence)
        survival = DoctoralMathEngine.weibull_survival(stuck, clearance_type=clearance_type)
        confidence = int(((4 - len(missing)) / 4.0) * 100)

        conflict_text = f" هشدار: تعارض داده ({conflict})." if conflict else ""
        fin = ""
        alloc = row.get("ALLOC_STATUS")
        if alloc and not is_empty_val(alloc):
            fin += f" تخصیص ارز: {alloc}."
        fx = row.get("FX_STATUS")
        if fx and not is_empty_val(fx):
            fin += f" خرید ارز: {fx}."
        commit = row.get("وضعیت کلی هشدار")
        if commit and commit != "سبز":
            fin += f" وضعیت تعهد ارزی: {commit}."
        stage_fa = row.get("ORDER_STAGE_FA")
        if stage_fa and not is_empty_val(stage_fa):
            prog = row.get("ORDER_PROGRESS", 0)
            fin += f" مرحله سفارش: {stage_fa} ({prog:.0f}٪)."
        alerts = row.get("STAGE_ALERTS")
        if alerts and not is_empty_val(alerts):
            fin += f" ⚠️ {alerts}"

        if clearance_type == CLEARANCE_FULL:
            nar = f"بارنامه {bl} مربوط به سفارش {order} (قطعه {goods} — {pn}) ترخیص قطعی گردیده.{fin}{conflict_text}"
            rec = "خاتمه پرونده و ثبت سبز گمرکی."
        elif clearance_type == CLEARANCE_PARTIAL:
            nar = (f"بارنامه {bl} (قطعه {goods}) در وضعیت ترخیص درصدی است؛ "
                   f"خطر توقف خط مرتفع گردیده. احتمال بقا {survival:.0f}٪.{fin}{conflict_text}")
            rec = f"پیگیری روتین توسط {expert} جهت ترخیص مابقی، بدون فوریت."
        elif is_critical:
            miss = " و ".join(missing) if missing else "هیچ‌کدام"
            nar = (f"بارنامه {bl} ({goods}) زیر نظر {expert}، پس از {stuck:.0f} روز در رسوب شدید است. "
                   f"احتمال حضور در گمرک {prob:.0f}٪ و احتمال بقا {survival:.0f}٪.{fin}{conflict_text}")
            rec = f"اقدام فوری جهت استعلام توقف (ماده ۲۴) و تکمیل {miss}."
        elif has_discharge:
            nar = f"محموله بارنامه {bl} (سفارش {order}) مدت {stuck:.0f} روز است تخلیه شده.{fin}{conflict_text}"
            rec = f"پیگیری کارشناس ({expert}) جهت ثبت کوتاژ."
        else:
            nar = f"تخلیه کشتی بارنامه {bl} در سیستم درج نشده؛ احتمالاً در حمل بین‌المللی است.{fin}{conflict_text}"
            rec = "ارسال درخواست استعلام مانفیست از شرکت حمل."

        return Narration(nar, rec, confidence, stuck, is_critical, survival, prob)
