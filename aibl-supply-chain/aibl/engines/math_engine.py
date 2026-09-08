# -*- coding: utf-8 -*-
"""موتور ریاضی: بقای ویبول + احتمال بیزین حضور در گمرک."""
from __future__ import annotations

import math
from typing import Iterable, List

from ..rulebook import get_rulebook

CLEARANCE_PARTIAL = "ترخیص درصدی"


def _p() -> dict:
    """پارامترهای مدل از RuleBook (customs.yaml)."""
    rb = get_rulebook()
    types = rb.get("customs.clearance_types", []) or []
    factor = next((t.get("weibull_time_factor", 0.15)
                   for t in types if t.get("code") == "PARTIAL"), 0.15)
    return {
        "beta": float(rb.get("customs.survival_model.beta", 1.4)),
        "eta": float(rb.get("customs.survival_model.eta_days", 45.0)),
        "partial_factor": float(factor),
        "prior": float(rb.get("customs.customs_presence_model.prior", 0.60)),
        "fp": float(rb.get("customs.customs_presence_model.false_positive_rate", 0.10)),
        "weights": dict(rb.get("customs.customs_presence_model.evidence_weights", {}) or {}),
    }


class DoctoralMathEngine:

    @staticmethod
    def weibull_survival(stuck_days: float, beta: float = None,
                         eta: float = None,
                         clearance_type: str = "عدم ترخیص") -> float:
        """S(t) = exp(-(t/η)^β) × ۱۰۰

        برای ترخیص درصدی، زمان مؤثر با ضریب ۰٫۱۵ کاهش می‌یابد چون بخشی از
        محموله از چرخه رسوب خارج شده است.
        """
        if stuck_days is None or stuck_days <= 0:
            return 100.0
        prm = _p()
        beta = prm["beta"] if beta is None else beta
        eta = prm["eta"] if eta is None else eta
        t = stuck_days * prm["partial_factor"] if clearance_type == CLEARANCE_PARTIAL else stuck_days
        try:
            return round(math.exp(-((t / eta) ** beta)) * 100, 1)
        except (OverflowError, ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def bayesian_customs_prob(present_evidence: Iterable[str]) -> float:
        """احتمال پسین حضور محموله در گمرک بر پایه شواهد موجود.

        P(H|E) = P(E|H)·P(H) / [ P(E|H)·P(H) + P(E|¬H)·P(¬H) ]
        که در آن P(E|H) = مجموع وزن شواهد و P(E|¬H) = ۰٫۱۰ (نرخ شاهد کاذب).

        نسبت به نسخه ۲۰.۱ فرمول مخرج اصلاح شد: آنجا به‌جای P(E|¬H) از
        (1-weight) استفاده شده بود که قاعده بیز را نقض می‌کرد.
        """
        prm = _p()
        ev = set(present_evidence or [])
        likelihood = min(1.0, sum(w for k, w in prm["weights"].items() if k in ev))
        if likelihood <= 0:
            return 10.0          # فقط نرخ شاهد کاذب

        false_positive = prm["fp"]
        prior = prm["prior"]
        num = likelihood * prior
        den = num + false_positive * (1 - prior)
        if den == 0:
            return 50.0
        return round(min(99.0, num / den * 100), 1)

    @staticmethod
    def evidence_list(has_discharge: bool, has_cotage: bool, has_sata: bool) -> List[str]:
        ev = []
        if has_discharge:
            ev.append("تاریخ تخلیه")
        if has_cotage:
            ev.append("کوتاژ گمرکی")
        if has_sata:
            ev.append("کد ساتا")
        return ev
