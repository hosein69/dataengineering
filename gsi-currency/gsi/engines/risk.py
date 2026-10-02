# -*- coding: utf-8 -*-
"""موتور امتیاز ریسک ۰–۱۰۰ (§۶-ح) — کاملاً غایب در نسخه ۲۰.۱."""
from __future__ import annotations

__contract__ = 2   # ← gsi/contracts.py

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..core.text import flag_true, is_empty_val, num_safe
from ..rulebook import RuleBook, get_rulebook


#: سقف ارزش هم‌ارز که مرحله ۷۰ برای هر ردیف می‌گذارد (0 = ارز نامعلوم)
SAME_CURRENCY_CAP = "_CB_SAME_CURRENCY_MAX"
#: مبنای «مواجهه با جریمه» به ارز خود جریمه که مرحله ۷۰ می‌گذارد (None = مبنای هم‌ارز نیست)
PENALTY_BASE = "_PENALTY_BASE_SAME_CURRENCY"


def _clip(x: float) -> float:
    return max(0.0, min(100.0, x))


@dataclass
class RiskResult:
    score: float
    band: str
    factors: Dict[str, float]

    def as_dict(self) -> Dict[str, Any]:
        out = {"امتیاز ریسک": round(self.score, 1), "طبقه ریسک": self.band}
        out.update({f"ریسک/{k}": round(v, 1) for k, v in self.factors.items()})
        return out


class RiskScoreEngine:
    """هفت مؤلفه وزن‌دار → امتیاز ۰ تا ۱۰۰."""

    def __init__(self, max_cb_value: float = 0.0, rb: Optional[RuleBook] = None) -> None:
        self.max_cb_value = max(max_cb_value, 1.0)
        self.rb = rb or get_rulebook()
        self.weights = self.rb.risk_weights()
        self.budget_scores = {k: float(v) for k, v in
                              (self.rb.get("alarms.risk_engine.budget_flags", {}) or {}).items()}
        self.horizon = int(self.rb.get("alarms.risk_engine.customs_risk_horizon_days", 180))
        self.penalty_base_ratio = float(
            self.rb.get("alarms.risk_engine.penalty_exposure_base_ratio", 0.10))

    def score(self, row: Dict[str, Any]) -> RiskResult:
        f: Dict[str, float] = {}

        # ۱) کهنگی نسبت به مهلت قانونی
        elapsed = num_safe(row.get("ELAPSED_DAYS", 0))
        legal = num_safe(row.get("LEGAL_DEADLINE_DAYS", 0))
        f["aging_pct"] = _clip((elapsed / legal) * 100) if legal > 0 else 0.0

        # ۲) ارزش در معرض خطر — نسبت به بزرگ‌ترین ارزشِ **همان ارز**. مرحله ۷۰ این سقف را
        # روی ردیف می‌گذارد؛ یک میلیون یوان با یک میلیون یورو هم‌وزن نیست. ارزش با ارز
        # نامعلوم با هیچ ارزی مقایسه‌پذیر نیست و سهم ارزشی نمی‌گیرد. ردیفی که سقف ندارد
        # (فراخوانی مستقیم موتور) همان سقف کلی قبلی را می‌گیرد.
        cb = num_safe(row.get("CB_VALUE", 0))
        if SAME_CURRENCY_CAP in row:
            cap = num_safe(row.get(SAME_CURRENCY_CAP) or 0)
            f["value_at_risk"] = _clip(cb / max(cap, 1.0) * 100) if cap > 0 else 0.0
        else:
            f["value_at_risk"] = _clip(cb / self.max_cb_value * 100)

        # ۳) وضعیت تخصیص ارز
        allocated = flag_true(row.get("ALLOCATED"))   # NaN/«خیر» تخصیص نیست
        f["allocation_status"] = 0.0 if allocated else 100.0

        # ۴) تکمیل اسناد (معکوس): ساتا، مالی، ترخیص
        docs = [not is_empty_val(row.get("SATA_NO")),
                not is_empty_val(row.get("FIN_RECEIPT_DATE")),
                not is_empty_val(row.get("FULL_CLEAR_DATE"))]
        f["doc_completion"] = _clip((1 - sum(docs) / 3.0) * 100)

        # ۵) مواجهه با جریمه — جریمه از مانده تعهد و به ارز تعهد است؛ نسبتش فقط با ارزشی
        # به همان ارز معنا دارد. مرحله ۷۰ آن مبنا را می‌گذارد؛ مبنای هم‌ارز نبود یعنی مبنا نیست.
        penalty = num_safe(row.get("PENALTY", 0))
        base_value = row.get(PENALTY_BASE) if PENALTY_BASE in row else cb
        base = (num_safe(base_value) if base_value is not None else 0.0) * self.penalty_base_ratio
        f["penalty_exposure"] = _clip(penalty / base * 100) if base > 0 else (100.0 if penalty > 0 else 0.0)

        # ۶) ریسک گمرکی
        stuck = num_safe(row.get("STUCK_DAYS", 0))
        f["customs_risk"] = _clip(stuck / self.horizon * 100)

        # ۷) ریسک بودجه
        f["budget_risk"] = self.budget_scores.get(str(row.get("BUDGET_FLAG", "")).upper(), 0.0)

        # ۸) بحرانی بودن قطعه — از موتور مقاومت (rules/criticality.yaml)
        f["part_criticality"] = _clip(num_safe(row.get("PART_CRITICALITY_SCORE", 0)))

        total = sum(self.weights.get(k, 0.0) * v for k, v in f.items())
        return RiskResult(_clip(total), self.band(total), f)

    def band(self, score: float) -> str:
        return self.rb.risk_band(score)
