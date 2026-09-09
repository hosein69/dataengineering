# -*- coding: utf-8 -*-
"""موتور مقاومت قطعه و بحرانی بودن.

مقاومت (روز) = موجودی قابل مصرف ÷ مصرف روزانه

تمام آستانه‌ها و طبقه‌بندی‌ها از ``rules/criticality.yaml`` می‌آید؛
تغییر «زیر ۱۰ روز = بحرانی» به هر عدد دیگر فقط ویرایش یک سطر YAML است.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 2


from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.text import is_empty_val, num_parse, num_safe
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
    resistance_days: Optional[float]          # کل: انبار + در راه + در گمرک
    resistance_warehouse: Optional[float]     # فقط موجودی فیزیکی قابل مصرف
    band: str
    band_fa: str
    band_short: str
    sort_rank: int
    action: str
    risk_score: float
    stock_ikco: float
    stock_sapco: float
    in_transit_qty: float
    in_customs_qty: float
    daily_need: float
    components: Dict[str, float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "مقاومت (روز)": self.resistance_days,
            "مقاومت انبار (روز)": self.resistance_warehouse,
            "طبقه بحرانی": self.band_fa,
            "بحرانی (کوتاه)": self.band_short,
            "کد طبقه بحرانی": self.band,
            "CRITICALITY_SORT": self.sort_rank,
            "اقدام پیشنهادی مقاومت": self.action,
            "موجودی ایران خودرو": self.stock_ikco,
            "موجودی ساپکو": self.stock_sapco,
            "موجودی در راه": self.in_transit_qty,
            "موجودی در گمرک": self.in_customs_qty,
            "موجودی کل قابل احتساب": sum(self.components.values()),
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
        """مقاومت = (موجودی ایران‌خودرو + ساپکو + در راه + در گمرک) ÷ نیاز روزانه

        اجزای صورت کسر از ``rules/criticality.yaml`` می‌آیند؛ غیرفعال کردن
        هر جزء (مثلاً «در راه») فقط یک ``enabled: false`` در YAML است.
        """
        # ── «عدد نداریم» با «عدد صفر است» یکی نیست ──────────────────────
        # سلولی که «ندارد» یا «N/A» یا یک متن دیگر در آن نوشته شده، اگر
        # صفر خوانده شود یعنی **موجودی صفر** یعنی **توقف خط** — یک هشدار
        # اضطراری که هیچ‌کس تولیدش نکرده. num_parse برای چنین سلولی None
        # می‌دهد و ردیف به طبقه «نامشخص» می‌رود، نه به STOCKOUT.
        comps: Dict[str, float] = {}
        unreadable: List[str] = []
        # شمارنده روی نمونه موتور می‌ماند تا مرحله بتواند گزارشش کند؛
        # یک سلول ناخوانا در موجودی، یعنی یک ردیف که وضعیتش قابل اتکا نیست.
        if not hasattr(self, "unreadable_cells"):
            self.unreadable_cells = {}
        for c in self.components_spec():
            field = c["field"]
            raw = row.get(field)
            val = num_parse(raw)
            if val is None and not is_empty_val(raw, treat_zero_as_empty=False):
                unreadable.append(field)      # مقدار هست ولی عدد نیست
            comps[field] = val or 0.0

        ikco = num_parse(row.get("STOCK_IKCO"))
        sapco = num_parse(row.get("STOCK_SAPCO"))
        transit = num_parse(row.get("IN_TRANSIT_QTY")) or 0.0
        customs = num_parse(row.get("IN_CUSTOMS_QTY")) or 0.0
        need = num_parse(row.get("DAILY_NEED"))

        has_stock = ikco is not None or sapco is not None
        has_need = need is not None

        total = sum(comps.values())
        warehouse = (ikco or 0.0) + (sapco or 0.0)

        for _f in unreadable:
            self.unreadable_cells[_f] = self.unreadable_cells.get(_f, 0) + 1

        if unreadable or not has_stock or not has_need:
            days = wh_days = None
            band = self._band(BAND_UNKNOWN)
        elif need <= 0:
            days = wh_days = None
            band = self._band(BAND_NO_CONSUMPTION)
        else:
            # موجودی منفی (اضافه‌برداشت) نباید «مقاومت منفی» بدهد؛ عددِ
            # منفیِ روز بی‌معناست و در مرتب‌سازی هم رفتار عجیب می‌سازد.
            days = round(min(max(total, 0.0) / need, self.max_days), 1)
            wh_days = round(min(max(warehouse, 0.0) / need, self.max_days), 1)
            band = (self._band(BAND_STOCKOUT) if total <= 0
                    else self.band_for_days(days))

        return CriticalityResult(
            resistance_days=days,
            resistance_warehouse=wh_days,
            band=band["code"],
            band_fa=band.get("fa", band["code"]),
            band_short=band.get("short_fa", band["code"]),
            sort_rank=int(band.get("sort", 9)),
            action=band.get("action", ""),
            risk_score=self.scores.get(band["code"], 0.0),
            stock_ikco=ikco or 0.0, stock_sapco=sapco or 0.0,
            in_transit_qty=transit, in_customs_qty=customs,
            daily_need=need or 0.0, components=comps,
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
