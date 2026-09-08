# -*- coding: utf-8 -*-
"""سازگاری رو به عقب — ثابت‌های بیزینسی که اکنون از RuleBook می‌آیند.

⚠️ هیچ عدد قانونی جدیدی اینجا ننویسید. مقصد صحیح: ``aibl/rules/*.yaml``.
این فایل فقط پلی است برای کدی که هنوز ثابت‌های ماژول‌سطح را import می‌کند.
"""
from __future__ import annotations

from typing import Dict, Tuple

from ..rulebook import get_rulebook

_RB = get_rulebook()

# ── سگمنت ──
SEGMENT_PRODUCTION = "production"
SEGMENT_COMMERCIAL = "commercial"
SEGMENT_FA = {SEGMENT_PRODUCTION: "تولیدی", SEGMENT_COMMERCIAL: "بازرگانی"}

# ── مهلت‌ها ──
RELEASE_PRODUCTION_DAYS = _RB.release_deadline_days(SEGMENT_PRODUCTION)
RELEASE_COMMERCIAL_DAYS = _RB.release_deadline_days(SEGMENT_COMMERCIAL)
AFTER_BARAT_DUE_DAYS = _RB.deadline_days("release_after_barat_due") or 90
DOCS_AFTER_OPENING_DAYS = _RB.deadline_days("docs_after_opening") or 180
CLEARANCE_AFTER_SATA_DAYS = _RB.deadline_days("clearance_after_sata") or 90
DEFAULT_BARAT_TENOR_DAYS = _RB.deadline_days("default_barat_tenor") or 180

# ── روش پرداخت / ترخیص ──
PAYMENT_BARAT, PAYMENT_CASH, PAYMENT_LC, PAYMENT_OTHER = "BARAT", "CASH", "LC", "OTHER"
PAYMENT_FA = {m["code"]: m["fa"] for m in (_RB.get("fx_governance.payment_methods", []) or [])}

CLEARANCE_FULL = "ترخیص کامل"
CLEARANCE_PARTIAL = "ترخیص درصدی"
CLEARANCE_NONE = "عدم ترخیص"
CLEARANCE_FA = {"FULL": CLEARANCE_FULL, "PARTIAL": CLEARANCE_PARTIAL, "NONE": CLEARANCE_NONE}
PARTIAL_MARKERS = tuple(_RB.get("customs.clearance_types", [{}])[1]
                        .get("detect", {}).get("when_value_matches", ["*", "٪", "%", "درصد"]))

# ── وضعیت هشدار ──
STATUS_GREEN = _RB.status_label("green")
STATUS_YELLOW = _RB.status_label("yellow")
STATUS_RED = _RB.status_label("red")

# ── آستانه‌ها (legal, y_min, y_max, red) ──
def _thresholds(segment: str) -> Dict[str, Tuple[int, int, int, int]]:
    out: Dict[str, Tuple[int, int, int, int]] = {}
    for key, t in (_RB.thresholds(segment) or {}).items():
        y = t.get("yellow", [0, 0])
        out[key] = (int(t["legal"]), int(y[0]), int(y[1]), int(t["red"]))
    return out


ALARM_THRESHOLDS = {
    SEGMENT_PRODUCTION: _thresholds(SEGMENT_PRODUCTION),
    SEGMENT_COMMERCIAL: _thresholds(SEGMENT_COMMERCIAL),
}
ALARM_LABELS_FA = {k: t.get("fa", k)
                   for k, t in (_RB.thresholds(SEGMENT_PRODUCTION) or {}).items()}

# ── ریسک ──
RISK_WEIGHTS = _RB.risk_weights()
BUDGET_RISK_SCORES = {k: float(v) for k, v in
                      (_RB.get("alarms.risk_engine.budget_flags", {}) or {}).items()}
CUSTOMS_RISK_HORIZON_DAYS = int(_RB.get("alarms.risk_engine.customs_risk_horizon_days", 180))
PENALTY_EXPOSURE_BASE = float(_RB.get("alarms.risk_engine.penalty_exposure_base_ratio", 0.10))

# ── ویبول / بیزین ──
WEIBULL_BETA = float(_RB.get("customs.survival_model.beta", 1.4))
WEIBULL_ETA = float(_RB.get("customs.survival_model.eta_days", 45.0))
WEIBULL_PARTIAL_FACTOR = float(_RB.get("customs.clearance_types", [{}])[1]
                               .get("weibull_time_factor", 0.15))
BAYES_PRIOR_CUSTOMS = float(_RB.get("customs.customs_presence_model.prior", 0.60))
BAYES_FALSE_POSITIVE = float(_RB.get("customs.customs_presence_model.false_positive_rate", 0.10))
BAYES_EVIDENCE_WEIGHTS = dict(_RB.get("customs.customs_presence_model.evidence_weights", {}) or {})
