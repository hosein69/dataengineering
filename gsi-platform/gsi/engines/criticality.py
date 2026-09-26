# -*- coding: utf-8 -*-
"""موتور مقاومت قطعه و بحرانی بودن.

مقاومت (روز) = موجودی قابل مصرف ÷ مصرف روزانه

تمام آستانه‌ها و طبقه‌بندی‌ها از ``rules/criticality.yaml`` می‌آید؛
تغییر «زیر ۱۰ روز = بحرانی» به هر عدد دیگر فقط ویرایش یک سطر YAML است.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — gsi/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 3


from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.text import is_empty_val, num_safe
from ..rulebook import RuleBook, get_rulebook

BAND_STOCKOUT = "STOCKOUT"
BAND_CRITICAL = "CRITICAL"
BAND_BECOMING = "BECOMING_CRITICAL"
BAND_WATCH = "WATCH"
BAND_SAFE = "SAFE"
BAND_NO_CONSUMPTION = "NO_CONSUMPTION"
BAND_UNKNOWN = "UNKNOWN"


@dataclass
class CriticalityResult:
    resistance_days: Optional[float]          # مقاومت اصلی: IKCO + SAPCO ÷ نیاز روزانه
    resistance_warehouse: Optional[float]     # همان مقاومت اصلی انبار
    resistance_total_supply: Optional[float]  # کل زنجیره، فقط وقتی همه اجزا معلوم باشند
    band: str
    band_fa: str
    band_short: str
    sort_rank: int
    action: str
    risk_score: float
    stock_ikco: Optional[float]
    stock_sapco: Optional[float]
    supplier_qty: Optional[float]
    in_transit_qty: Optional[float]
    in_customs_qty: Optional[float]
    daily_need: Optional[float]
    components: Dict[str, float]
    missing_components: List[str]
    coverage_pct: float
    total_confirmed: Optional[float]
    total_lower_bound: Optional[float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "مقاومت (روز)": self.resistance_days,
            "مقاومت انبار (روز)": self.resistance_warehouse,
            "مقاومت کل تامین (روز)": self.resistance_total_supply,
            "طبقه بحرانی": self.band_fa,
            "بحرانی (کوتاه)": self.band_short,
            "کد طبقه بحرانی": self.band,
            "CRITICALITY_SORT": self.sort_rank,
            "اقدام پیشنهادی مقاومت": self.action,
            "موجودی ایران خودرو": self.stock_ikco,
            "موجودی ساپکو": self.stock_sapco,
            "موجودی نزد سازنده": self.supplier_qty,
            "موجودی در راه": self.in_transit_qty,
            "موجودی در گمرک": self.in_customs_qty,
            "موجودی کل قابل احتساب": self.total_confirmed,
            "حداقل موجودی قابل اثبات": self.total_lower_bound,
            "پوشش اجزای موجودی (٪)": self.coverage_pct,
            "شکاف اجزای موجودی": "، ".join(self.missing_components),
            "نیاز روزانه": self.daily_need,
        }


class CriticalityEngine:
    """محاسبه مقاومت و طبقه بحرانی برای هر قطعه."""

    def __init__(self, rb: Optional[RuleBook] = None) -> None:
        self.rb = rb or get_rulebook()
        self.bands: List[Dict[str, Any]] = self.rb.get("criticality.bands", []) or []
        self.scores: Dict[str, float] = {
            k: float(v) for k, v in
            (self.rb.get("criticality.risk_contribution.scores", {}) or {}).items()}
        self.include_transit = bool(
            self.rb.get("criticality.formula.include_in_transit", False))
        self.max_days = float(self.rb.get("criticality.formula.max_reported_days", 999))

    # ── انتخاب طبقه بر اساس روز مقاومت ──
    def band_for_days(self, days: Optional[float]) -> Dict[str, Any]:
        if days is None:
            return self._band(BAND_UNKNOWN)
        if days <= 0:
            return self._band(BAND_STOCKOUT)
        for b in sorted(self.bands, key=lambda x: x.get("sort", 99)):
            if b["code"] in (BAND_STOCKOUT, BAND_NO_CONSUMPTION, BAND_UNKNOWN):
                continue
            cap = b.get("max_days")
            if cap is None:
                return b
            if days < float(cap):
                return b
        return self._band(BAND_SAFE)

    def _band(self, code: str) -> Dict[str, Any]:
        for b in self.bands:
            if b["code"] == code:
                return b
        return {"code": code, "fa": code, "short_fa": code, "sort": 9, "action": ""}

    # ── محاسبه اصلی ──
    def components_spec(self) -> List[Dict[str, Any]]:
        return [c for c in (self.rb.get(
            "criticality.formula.numerator_components", []) or [])
            if c.get("enabled", True)]

    def evaluate(self, row: Dict[str, Any]) -> CriticalityResult:
        """مقاومت قطعی فقط وقتی محاسبه می‌شود که تمام اجزای فعال موجود باشند.

        فرمول V26.20:
            Oracle(IKCO + SAPCO) + Expert(Supplier + Transit + Customs)

        اگر یک جزء blank باشد، ``UNKNOWN`` است نه صفر. برای اینکه داده ناقص هم
        بی‌استفاده نشود، «حداقل موجودی قابل اثبات» جداگانه گزارش می‌شود ولی
        از آن برای اعلام STOCKOUT/SAFE استفاده نمی‌کنیم.
        """
        spec = self.components_spec()
        comps: Dict[str, float] = {}
        missing: List[str] = []
        for c in spec:
            field = c["field"]
            raw = row.get(field)
            if is_empty_val(raw, treat_zero_as_empty=False):
                missing.append(c.get("fa") or field)
            else:
                comps[field] = num_safe(raw)

        def n(field: str) -> Optional[float]:
            raw = row.get(field)
            if is_empty_val(raw, treat_zero_as_empty=False):
                return None
            return float(num_safe(raw))

        ikco = n("STOCK_IKCO")
        sapco = n("STOCK_SAPCO")
        supplier = n("SUPPLIER_QTY")
        transit = n("IN_TRANSIT_QTY")
        customs = n("IN_CUSTOMS_QTY")
        need = n("DAILY_NEED")

        has_need = not is_empty_val(row.get("DAILY_NEED"), treat_zero_as_empty=False)
        wh_complete = all(not is_empty_val(row.get(f), treat_zero_as_empty=False)
                          for f in ("STOCK_IKCO", "STOCK_SAPCO"))
        complete = (not missing)
        lower_bound = sum(comps.values()) if comps else None
        total_confirmed = lower_bound if complete else None
        coverage = round(100 * (len(spec) - len(missing)) / max(len(spec), 1), 1)

        warehouse = (float(ikco or 0.0) + float(sapco or 0.0)) if wh_complete else None
        wh_days = None
        if has_need and need is not None and need > 0 and wh_complete and warehouse is not None:
            wh_days = round(min(warehouse / need, self.max_days), 1)

        # تعریف کسب‌وکار: «مقاومت قطعه» فقط موجودی انبار IKCO + SAPCO است.
        # سه bucket نزد سازنده/درراه/گمرک مقاومت‌های مستقل و دید کل تامین‌اند؛
        # نبود آن‌ها نباید طبقه بحرانی قطعه را UNKNOWN کند.
        total_supply_days = None
        if has_need and need is not None and need > 0 and complete and total_confirmed is not None:
            total_supply_days = round(min(float(total_confirmed) / need, self.max_days), 1)

        if not has_need or not wh_complete:
            days = None
            band = self._band(BAND_UNKNOWN)
        elif need is None or need <= 0:
            days = None
            band = self._band(BAND_NO_CONSUMPTION)
        else:
            days = wh_days
            band = (self._band(BAND_STOCKOUT) if float(warehouse or 0.0) <= 0
                    else self.band_for_days(days))

        return CriticalityResult(
            resistance_days=days,
            resistance_warehouse=wh_days,
            resistance_total_supply=total_supply_days,
            band=band["code"],
            band_fa=band.get("fa", band["code"]),
            band_short=band.get("short_fa", band["code"]),
            sort_rank=int(band.get("sort", 9)),
            action=band.get("action", ""),
            risk_score=self.scores.get(band["code"], 0.0),
            stock_ikco=ikco, stock_sapco=sapco, supplier_qty=supplier,
            in_transit_qty=transit, in_customs_qty=customs,
            daily_need=need, components=comps, missing_components=missing,
            coverage_pct=coverage, total_confirmed=total_confirmed,
            total_lower_bound=lower_bound,
        )

    # ── هشدارهای ترکیبی بحرانی + لجستیک ──
    def combined_alerts(self, row: Dict[str, Any]) -> List[Dict[str, str]]:
        band = str(row.get("کد طبقه بحرانی", ""))
        out: List[Dict[str, str]] = []
        for rule in self.rb.get("criticality.combined_alerts", []) or []:
            w = rule.get("when", {})
            if band not in (w.get("criticality_in") or []):
                continue
            if w.get("is_blocked") and not bool(row.get("IS_BLOCKED", False)):
                continue
            if "stuck_days_gt" in w and num_safe(row.get("روزهای رسوب")) <= float(w["stuck_days_gt"]):
                continue
            if w.get("has_no_open_order") and bool(row.get("IS_IN_MOGHAVEMAT", False)):
                continue
            out.append({"severity": rule.get("severity", "HIGH"),
                        "fa": rule.get("fa", ""),
                        "action": rule.get("action", "")})
        return out
