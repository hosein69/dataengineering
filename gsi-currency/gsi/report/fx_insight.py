# -*- coding: utf-8 -*-
"""بینش چرخه ارز و رفع تعهد: یک مدل داده برای Studio، HTML ارسالی و Excel.

Studio، گزارش HTML که برای کاربران فرستاده می‌شود و سه خروجی Excel همه از همین
ماژول می‌خوانند. پس عددی که مدیر در HTML می‌بیند همان عددی است که کارشناس در
Studio دیده و همان عددی است که در Excel دانلود می‌شود.

این ماژول هیچ محاسبه مالی تازه‌ای نمی‌سازد و فقط خروجی‌های منتشرشده را کنار هم
می‌گذارد:

    fx_lifecycle، registration_value_recon، bl_registration_link، allocation_queue  (s59)
    fx_money_reconciliation، fx_money_ledger، fx_control_summary، fx_financial_decisions  (s56)
    expert_material_positions (دفتر سفارش × متریال کارشناسان) و مارت اصلی

قواعد:
  * هر مبلغ در دانه خودش می‌ماند: ارزش ثبت سفارش روی ثبت سفارش، ارزش PI روی
    سفارش و ارزش فاکتور روی بارنامه. هیچ مبلغی روی ردیف متریال تکرار نمی‌شود،
    پس جمع زدن ستون مبلغ هیچ جدولی چندبار شمردن نمی‌سازد.
  * جمع فقط داخل یک ارز انجام می‌شود. نامعلوم شمرده می‌شود ولی جمع زده نمی‌شود
    و «—» نمایش داده می‌شود، نه صفر.
  * نبود یک جدول (Snapshot قدیمی‌تر) یعنی بخش خالی با پیام، نه صفر.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from ..i18n import columns as C
from ..stages.s59_bl_registration_link import LIFECYCLE
from . import critical_board as CB

#: دوازده مرحله چرخه به‌علاوه «بسته‌شده»
STAGES: List[Tuple[str, str]] = list(LIFECYCLE) + [("CLOSED", "بسته‌شده (رفع تعهد)")]
STAGE_FA: Dict[str, str] = dict(STAGES)
STAGE_INDEX: Dict[str, int] = {c: i for i, (c, _) in enumerate(STAGES)}
DONE = "انجام شد"
OVERDUE = "سررسید گذشته"

#: گام‌های پول به ترتیب جریان، همه به ارز خود ردیف
MONEY_STEPS: List[Tuple[str, str]] = [
    ("REGISTRATION_AMOUNT", "ارزش ثبت سفارش"), ("REQUESTED_AMOUNT", "درخواست تخصیص"),
    ("ALLOCATED_AMOUNT", "تخصیص"), ("PURCHASED_AMOUNT", "خرید ارز"),
    ("SUPPLIER_PAID_AMOUNT", "پرداخت به ذی‌نفع"), ("SHIPPED_BL_VALUE", "حمل‌شده (بارنامه)"),
    ("COMMITMENT_INITIAL", "تعهد اولیه"), ("COMMITMENT_RELEASED", "رفع‌شده"),
    ("COMMITMENT_BALANCE", "مانده تعهد"),
]
MONEY_FA = dict(MONEY_STEPS)
RECON_FA = {"OK": "هم‌خوان", "EVIDENCE_GAP": "شکاف شاهد", "MISMATCH": "مغایرت", "VARIANCE": "مغایرت",
            "NO_COMMITMENT_EVIDENCE": "بدون شاهد تعهد", "NO_AMOUNT_EVIDENCE": "بدون شاهد مبلغ",
            # وضعیت‌های خود تطبیق جریان پول (مرحله ۵۶) که تا 29.15.13 خام و لاتین نمایش داده می‌شدند
            "RECONCILED": "هم‌خوان", "OPEN_AMOUNT_GAP": "اختلاف مبلغ باز",
            "ACCOUNTING_MISMATCH": "مغایرت حسابداری", "REJECTED_REQUESTS_ONLY": "فقط درخواست ردشده"}
DEADLINE_FA = {"OVERDUE": "سررسید گذشته", "DUE_SOON": "نزدیک سررسید", "ON_TRACK": "در مهلت",
               "NO_DEADLINE": "بدون مهلت", "CLOSED": "بسته‌شده"}
QUEUE_FA = {"IN_QUEUE": "در صف", "OPEN": "در صف", "PENDING": "در صف", "ALLOCATED": "تخصیص‌یافته",
            "PARTIAL_ALLOCATED": "تخصیص جزئی، درخواست باز دارد", "REJECTED": "ردشده",
            "CLOSED": "بسته‌شده بدون شاهد تخصیص", "NO_REQUEST": "بدون درخواست"}
#: رنگ وضعیت مرحله و پیوند — یک منبع برای Studio، HTML و Excel
STATUS_TONE = {"انجام شد": "good", "در انتظار": "neutral", "هشدار": "warning",
               "سررسید گذشته": "critical", "بدون شاهد": "unknown"}
LINK_TONE = {"حمل بیش از ارزش ثبت سفارش": "critical", "ارز بارنامه ≠ ارز ثبت سفارش": "critical",
             "بارنامه بدون ثبت سفارش": "critical", "ارزش ثبت سفارش نامعلوم": "warning",
             "ارزش بارنامه نامعلوم": "warning", "ارز نامعلوم": "warning", "حمل جزئی": "neutral",
             "ثبت سفارش بدون بارنامه": "neutral",
             "حمل کامل": "good", "پیوند معتبر": "good"}
RECON_TONE = {"OK": "good", "EVIDENCE_GAP": "warning", "MISMATCH": "critical", "VARIANCE": "critical",
              "NO_COMMITMENT_EVIDENCE": "unknown", "NO_AMOUNT_EVIDENCE": "unknown",
              "RECONCILED": "good", "OPEN_AMOUNT_GAP": "warning", "ACCOUNTING_MISMATCH": "critical",
              "REJECTED_REQUESTS_ONLY": "neutral"}
CLEAR_TONE = {"ترخیص کامل": "good", "ترخیص جزئی": "warning", "ترخیص نشده": "critical"}


# ═══════════════════════════════ کمکی ═══════════════════════════════
def s(v: Any) -> str:
    """متن تمیز؛ NaN/None/NaT ← رشته خالی."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    t = str(v).strip()
    return "" if t.lower() in ("nan", "none", "nat", "<na>") else t


def n(v: Any) -> Optional[float]:
    """عدد متناهی یا ``None`` (نامعلوم هرگز صفر نمی‌شود)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(str(v).replace(",", "")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def tr(text: Any, lang: str) -> str:
    """متن رابط در زبان خواسته‌شده (``columns.phrase``)؛ نامعلوم ← رشته خالی."""
    return C.phrase(s(text), lang)


#: ستون‌هایی که مقدارشان برچسب رابط است (مرحله، سطح، وضعیت)، نه داده؛ در حالت
#: انگلیسی همراه عنوان ستون ترجمه می‌شوند. نام کالا، کارشناس و متن آزاد داده‌اند.
ENUM_COLS = frozenset({
    "سطح", "مرحله", "مرحله جاری", "وضعیت مرحله", "مبنای ارزش", "وضعیت پیوند", "سطح بحرانی",
    "بدترین سطح بحرانی", "وضعیت مهلت", "وضعیت صف", "گام‌های بدون شاهد", "کجاست", "منبع", "ترخیص",
    "وضعیت ترخیص", "وضعیت تطبیق", "شکاف شاهد", "حالت", "گام", "توضیح تاریخ", "وضعیت",
    "وضعیت سفارش", "بحرانی بودن سفارش", "ابطال", "ارز", "ارز PI", "ارز فاکتور", "مغایرت",
    "مغایرت ارز گام‌ها",
})


def truthy(v: Any) -> bool:
    return v is True or s(v).lower() in ("true", "1", "yes", "بله")


def _col(df: pd.DataFrame, *names: str) -> pd.Series:
    for c in names:
        if c in df.columns:
            return df[c]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def _first(values: Iterable[Any]) -> str:
    return next((s(v) for v in values if s(v)), "")


def _first_num(values: Iterable[Any]) -> Optional[float]:
    return next((x for x in (n(v) for v in values) if x is not None), None)


def _uniq(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for v in values:
        t = s(v)
        if t and t not in out:
            out.append(t)
    return out


def worst_level(codes: Iterable[Any]) -> str:
    """بدترین سطح بحرانی بین کدها؛ بدون کد معتبر ← رشته خالی."""
    valid = [s(c) for c in codes if s(c) in CB.LEVELS]
    return min(valid, key=CB.level_rank) if valid else ""


def _frame(extras: Any, key: str) -> pd.DataFrame:
    try:
        v = extras.get(key) if extras is not None else None
    except Exception:
        v = None
    return v.copy() if isinstance(v, pd.DataFrame) else pd.DataFrame()


def _by(frame: pd.DataFrame, key: str) -> Dict[str, pd.DataFrame]:
    if frame.empty or key not in frame.columns:
        return {}
    k = frame[key].map(s)
    return {r: g for r, g in frame.assign(_K=k).groupby("_K") if r}


# ═══════════════════════════════ داده ═══════════════════════════════
_MART_COLS = ("KEY_REG", "KEY_ORDER", "CANONICAL_ORDER", "KEY_MATERIAL", "MATERIAL_DESC", "CANONICAL_GOODS_DESC",
              "MOGH_PI_VALUE_SUM", "MOGH_CURRENCY", "MOGH_PR_NO", "MOGH_ORDER_QTY_SUM", "ORDER_STAGE_FA",
              "ORDER_CRITICAL_LEVEL", "کد طبقه بحرانی", "مقاومت (روز)", "STATUS_WHERE", "CANONICAL_BL", "KEY_BL",
              "IS_FULL_CLEARED", "IS_PARTIAL_CLEARED", "روزهای رسوب", "COTAGE_NO", "BL_DISCHARGE_DATE",
              "DISCHARGE_DATE", "BL_CRITICAL_LEVEL", "CANONICAL_EXPERT", "IS_CANCELLED", "اقدام پیشنهادی مقاومت",
              "DEST_CUSTOMS", "FULL_CLEAR_DATE")


@dataclass
class FxData:
    """همه جدول‌های چرخه ارز یک Snapshot، با دسترسی گروه‌بندی‌شده به هر ثبت سفارش."""
    lc: pd.DataFrame
    link: pd.DataFrame
    recon: pd.DataFrame
    ledger: pd.DataFrame
    money: pd.DataFrame
    queue: pd.DataFrame
    control: pd.DataFrame
    decisions: pd.DataFrame
    positions: pd.DataFrame
    mart: pd.DataFrame
    ref_date: str = ""
    missing: List[str] = field(default_factory=list)
    _orders: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict, repr=False)

    @property
    def available(self) -> bool:
        return not self.lc.empty and "KEY_REG" in self.lc.columns

    @cached_property
    def mart_by_reg(self) -> Dict[str, pd.DataFrame]:
        return _by(self.mart, "KEY_REG")

    @cached_property
    def mart_by_bl(self) -> Dict[str, pd.DataFrame]:
        m = self.mart
        if m.empty:
            return {}
        return _by(m.assign(_BL=_col(m, "CANONICAL_BL", "KEY_BL").map(s)), "_BL")

    @cached_property
    def positions_by_order(self) -> Dict[str, pd.DataFrame]:
        return _by(self.positions, "KEY_ORDER")

    @cached_property
    def link_by_reg(self) -> Dict[str, pd.DataFrame]:
        return _by(self.link, "KEY_REG")

    @cached_property
    def money_by_reg(self) -> Dict[str, pd.DataFrame]:
        return _by(self.money, "KEY_REG")

    @cached_property
    def ledger_by_reg(self) -> Dict[str, pd.DataFrame]:
        return _by(self.ledger, "KEY_REG")

    @cached_property
    def decisions_by_reg(self) -> Dict[str, pd.DataFrame]:
        return _by(self.decisions, "KEY_REG")

    @cached_property
    def recon_by_reg(self) -> Dict[str, pd.Series]:
        if self.recon.empty or "KEY_REG" not in self.recon.columns:
            return {}
        return {s(r["KEY_REG"]): r for _, r in self.recon.iterrows() if s(r["KEY_REG"])}

    @cached_property
    def control_by_reg(self) -> Dict[str, pd.Series]:
        if self.control.empty or "KEY_REG" not in self.control.columns:
            return {}
        return {s(r["KEY_REG"]): r for _, r in self.control.iterrows() if s(r["KEY_REG"])}

    @cached_property
    def queue_by_reg(self) -> Dict[str, pd.Series]:
        if self.queue.empty or "KEY_REG" not in self.queue.columns:
            return {}
        return {s(r["KEY_REG"]): r for _, r in self.queue.iterrows() if s(r["KEY_REG"])}

    @cached_property
    def lc_by_reg(self) -> Dict[str, pd.Series]:
        if not self.available:
            return {}
        return {s(r["KEY_REG"]): r for _, r in self.lc.iterrows() if s(r["KEY_REG"])}

    @cached_property
    def reg_table(self) -> pd.DataFrame:
        return registrations(self)


def load(df: Optional[pd.DataFrame], extras: Any, ref_date: str = "") -> FxData:
    """جدول‌های منتشرشده را از extras و مارت برمی‌دارد؛ نبود هر جدول در ``missing`` ثبت می‌شود."""
    names = {"lc": "fx_lifecycle", "link": "bl_registration_link", "recon": "registration_value_recon",
             "ledger": "fx_money_ledger", "money": "fx_money_reconciliation", "queue": "allocation_queue",
             "control": "fx_control_summary", "decisions": "fx_financial_decisions",
             "positions": "expert_material_positions"}
    frames = {k: _frame(extras, v) for k, v in names.items()}
    missing = [v for k, v in names.items() if frames[k].empty and k in ("lc", "link", "recon", "money")]
    mart = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if not mart.empty:
        mart = mart[[c for c in _MART_COLS if c in mart.columns]].copy()
    return FxData(mart=mart, ref_date=ref_date, missing=missing, **frames)


# ═══════════════════════════ ثبت سفارش‌ها ═══════════════════════════
REG_COLUMNS_FA: Dict[str, str] = {
    "STAGE": "مرحله جاری", "KEY_REG": "ثبت سفارش", "REG_FILE_NO": "پرونده", "STAGE_STATUS": "وضعیت مرحله",
    "STAGE_DAYS": "روز در مرحله", "PROGRESS_PCT": "پیشرفت (٪)", "REG_VALUE": "ارزش ثبت سفارش",
    "REG_CURRENCY": "ارز", "REG_VALUE_BASIS": "مبنای ارزش",
    # ارز هر گام کنار ارز ثبت سفارش؛ هیچ‌کدام جای آن نمی‌نشیند و مبلغشان با آن جمع نمی‌شود
    "CURRENCY_CHECK": "مغایرت ارز گام‌ها", "ALLOC_CURRENCY": "ارز تخصیص", "PURCHASE_CURRENCY": "ارز خرید",
    "COMMITMENT_CURRENCY": "ارز تعهد", "REJECTED_REQUEST_CURRENCIES": "ارز درخواست‌های ردشده",
    "SHIPPED_VALUE": "حمل‌شده",
    "SHIPPED_PCT": "حمل‌شده (٪)", "UNSHIPPED_VALUE": "مانده حمل‌نشده", "LINK_STATUS": "وضعیت پیوند",
    "ORDER_COUNT": "سفارش", "MATERIAL_COUNT": "متریال", "BL_COUNT": "بارنامه",
    "CRITICAL_LEVEL_FA": "بدترین سطح بحرانی", "CRITICAL_MATERIALS": "متریال بحرانی",
    "COMMITMENT_BALANCE_TEXT": "مانده تعهد (به تفکیک ارز)", "DEADLINE_DATE": "مهلت رفع تعهد",
    "DAYS_REMAINING": "روز تا مهلت", "DEADLINE_STATUS_FA": "وضعیت مهلت", "RISK_SCORE": "امتیاز ریسک",
    "QUEUE_STATE_FA": "وضعیت صف", "GAP_STAGES": "گام‌های بدون شاهد", "EXPERT": "کارشناس",
}


def _fmt_amount(v: Optional[float], ccy: str = "") -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}" + (f" {ccy}" if ccy else "")


def registrations(fx: FxData) -> pd.DataFrame:
    """یک ردیف برای هر ثبت سفارش: مرحله، روز، پیشرفت، ارزش، دانه‌های زیرین، بحرانی و مهلت."""
    cols = ["KEY_REG", "REG_FILE_NO", "STAGE_CODE", "STAGE", "STAGE_STATUS", "STAGE_DAYS", "PROGRESS_PCT",
            "GAP_STAGES", "GAP_COUNT", "REG_VALUE", "REG_CURRENCY", "REG_VALUE_BASIS",
            "CURRENCY_CHECK", "CURRENCY_MISMATCH", "ALLOC_CURRENCY", "PURCHASE_CURRENCY", "COMMITMENT_CURRENCY",
            "REJECTED_REQUEST_CURRENCIES", "SHIPPED_VALUE",
            "SHIPPED_PCT", "SHIPPED_IS_LOWER_BOUND", "UNSHIPPED_VALUE", "LINK_STATUS", "LINK_FLAGS",
            "ORDER_COUNT", "MATERIAL_COUNT", "BL_COUNT", "CRITICAL_LEVEL", "CRITICAL_LEVEL_FA",
            "CRITICAL_MATERIALS", "COMMITMENT_BALANCE_TEXT", "DEADLINE_DATE", "DAYS_REMAINING",
            "DEADLINE_STATUS", "DEADLINE_STATUS_FA", "RISK_SCORE", "RISK_BAND", "QUEUE_STATE",
            "QUEUE_STATE_FA", "EXPERT"]
    if not fx.available:
        return pd.DataFrame(columns=cols)
    rows = []
    for reg, r in fx.lc_by_reg.items():
        rec = fx.recon_by_reg.get(reg)
        ctl = fx.control_by_reg.get(reg)
        q = fx.queue_by_reg.get(reg)
        g = fx.mart_by_reg.get(reg, pd.DataFrame())
        tree = orders(fx, reg)
        mats = {m["key"] for o in tree for m in o["materials"]}
        crit_codes = [m["level"] for o in tree for m in o["materials"]]
        level = worst_level(crit_codes)
        crit_n = len({m["key"] for o in tree for m in o["materials"] if m["level"] in CB.DEFAULT_LEVELS})
        bal = []
        for _, m in fx.money_by_reg.get(reg, pd.DataFrame()).iterrows():
            v = n(m.get("COMMITMENT_BALANCE"))
            if v is not None:
                bal.append(_fmt_amount(v, s(m.get("CURRENCY"))))
        gaps = [x for x in s(r.get("GAP_STAGES")).split(" · ") if x]
        code = s(r.get("CURRENT_STAGE_CODE")) or "CLOSED"
        rows.append({
            "KEY_REG": reg, "REG_FILE_NO": s(r.get("REG_FILE_NO")),
            "STAGE_CODE": code, "STAGE": s(r.get("CURRENT_STAGE")) or STAGE_FA.get(code, code),
            "STAGE_STATUS": s(r.get("CURRENT_STAGE_STATUS")), "STAGE_DAYS": n(r.get("CURRENT_STAGE_DAYS")),
            "PROGRESS_PCT": n(r.get("PROGRESS_PCT")), "GAP_STAGES": " · ".join(gaps), "GAP_COUNT": len(gaps),
            "REG_VALUE": n(r.get("VALUE_REG_VALUE")), "REG_CURRENCY": s(r.get("VALUE_REG_CURRENCY")),
            "REG_VALUE_BASIS": s(rec.get("REG_VALUE_BASIS")) if rec is not None else "",
            "CURRENCY_CHECK": s(r.get("CURRENCY_CHECK")), "CURRENCY_MISMATCH": truthy(r.get("CURRENCY_MISMATCH")),
            "ALLOC_CURRENCY": s(r.get("ALLOC_CURRENCY")), "PURCHASE_CURRENCY": s(r.get("PURCHASE_CURRENCY")),
            "COMMITMENT_CURRENCY": s(r.get("COMMITMENT_CURRENCY")),
            "REJECTED_REQUEST_CURRENCIES": s(r.get("REJECTED_REQUEST_CURRENCIES")),
            "SHIPPED_VALUE": n(r.get("VALUE_SHIPPED_VALUE")), "SHIPPED_PCT": n(r.get("VALUE_SHIPPED_PCT")),
            "SHIPPED_IS_LOWER_BOUND": truthy(rec.get("SHIPPED_IS_LOWER_BOUND")) if rec is not None else False,
            "UNSHIPPED_VALUE": n(r.get("VALUE_UNSHIPPED_VALUE")), "LINK_STATUS": s(r.get("VALUE_STATUS")),
            "LINK_FLAGS": s(rec.get("FLAGS")) if rec is not None else "",
            "ORDER_COUNT": len(tree), "MATERIAL_COUNT": len(mats),
            "BL_COUNT": len(fx.link_by_reg.get(reg, pd.DataFrame())),
            "CRITICAL_LEVEL": level, "CRITICAL_LEVEL_FA": CB.level_label(level) if level else "",
            "CRITICAL_MATERIALS": crit_n, "COMMITMENT_BALANCE_TEXT": " · ".join(bal),
            "DEADLINE_DATE": s(ctl.get("FX_DEADLINE_DATE")) if ctl is not None else "",
            "DAYS_REMAINING": n(ctl.get("FX_DAYS_REMAINING")) if ctl is not None else None,
            "DEADLINE_STATUS": s(ctl.get("FX_DEADLINE_STATUS")) if ctl is not None else "",
            "DEADLINE_STATUS_FA": DEADLINE_FA.get(s(ctl.get("FX_DEADLINE_STATUS")), s(ctl.get("FX_DEADLINE_STATUS")))
            if ctl is not None else "",
            "RISK_SCORE": n(ctl.get("FX_CONTROL_RISK_SCORE")) if ctl is not None else None,
            "RISK_BAND": s(ctl.get("FX_CONTROL_RISK_BAND")) if ctl is not None else "",
            "QUEUE_STATE": s(q.get("QUEUE_STATE")) if q is not None else "",
            "QUEUE_STATE_FA": QUEUE_FA.get(s(q.get("QUEUE_STATE")), s(q.get("QUEUE_STATE"))) if q is not None else "",
            "EXPERT": _first(_col(g, "CANONICAL_EXPERT")) if not g.empty else (s(q.get("EXPERT")) if q is not None else ""),
        })
    out = pd.DataFrame(rows, columns=cols)
    out["_o"] = out["STAGE_CODE"].map(lambda c: STAGE_INDEX.get(c, 99))
    out["_c"] = out["CRITICAL_LEVEL"].map(lambda c: CB.level_rank(c) if c else 99)
    out = out.sort_values(["_o", "_c", "STAGE_DAYS"], ascending=[True, True, False], na_position="last")
    return out.drop(columns=["_o", "_c"]).reset_index(drop=True)


def reg_display(frame: pd.DataFrame) -> pd.DataFrame:
    """ستون‌های نمایشی ثبت سفارش با عنوان فارسی (زبان ستون را col_lang/localize عوض می‌کند)."""
    keep = [c for c in REG_COLUMNS_FA if c in frame.columns]
    return frame[keep].rename(columns=REG_COLUMNS_FA)


# ═══════════════════════════ سفارش ← متریال ═══════════════════════════
def orders(fx: FxData, reg: str) -> List[Dict[str, Any]]:
    """سفارش‌های یک ثبت سفارش، هرکدام با متریال‌هایش (دانه سفارش × متریال).

    متریال‌هایی که فقط در دفتر کارشناسان هستند (سفارش چندمتریالی) هم می‌آیند؛
    سطح بحرانی‌شان اگر در مارت نیست «نامشخص» می‌ماند. نتیجه کش می‌شود و نباید
    تغییر داده شود؛ برای فیلتر، کپی بسازید."""
    if reg not in fx._orders:
        fx._orders[reg] = _orders(fx, reg)
    return fx._orders[reg]


def _orders(fx: FxData, reg: str) -> List[Dict[str, Any]]:
    g = fx.mart_by_reg.get(reg)
    if g is None or g.empty:
        return []
    okey = _col(g, "KEY_ORDER", "CANONICAL_ORDER").map(s)
    out = []
    for o, og in g.assign(_O=okey).groupby("_O", sort=True):
        if not o:
            continue
        mats: Dict[str, Dict[str, Any]] = {}
        # R8: بارنامه‌ها فقط روی ردیف متریال اول سفارش نشسته‌اند و منبعی نمی‌گوید کدام بارنامه
        # کدام متریال را حمل می‌کند؛ پس «bls» هر متریال = بارنامه‌های سفارش آن (سطح سفارش).
        order_bls = _uniq(_col(og, "CANONICAL_BL", "KEY_BL"))
        mkey = _col(og, "KEY_MATERIAL").map(s)
        for m, mg in og.assign(_M=mkey).groupby("_M", sort=True):
            if not m:
                continue
            lvl = worst_level(_col(mg, "کد طبقه بحرانی"))
            res = [x for x in (n(v) for v in _col(mg, "مقاومت (روز)")) if x is not None]
            mats[m] = {"key": m, "desc": _first(_col(mg, "MATERIAL_DESC", "CANONICAL_GOODS_DESC")),
                       "level": lvl, "level_fa": CB.level_label(lvl) if lvl else "نامشخص",
                       "resistance": min(res) if res else None, "where": " · ".join(_uniq(_col(mg, "STATUS_WHERE"))),
                       "bls": list(order_bls), "bls_scope": "order",
                       "action": _first(_col(mg, "اقدام پیشنهادی مقاومت")), "source": "مارت"}
        pos = fx.positions_by_order.get(o)
        if pos is not None:
            for _, p in pos.iterrows():
                m = s(p.get("KEY_MATERIAL"))
                if not m:
                    continue
                q = {"in_transit": n(p.get("IN_TRANSIT_QTY")), "in_customs": n(p.get("IN_CUSTOMS_QTY")),
                     "ready": n(p.get("READY_QTY")), "at_supplier": n(p.get("SUPPLIER_QTY")),
                     "daily_need": n(p.get("DAILY_NEED")), "stock": n(p.get("SUPPLY_ORACLE_STOCK"))}
                if m in mats:
                    mats[m].update(q)
                else:
                    mats[m] = {"key": m, "desc": s(p.get("MOGH_MATERIAL_DESCS_ALL")) or s(p.get("ORC_MATERIAL_DESC")),
                               "level": "", "level_fa": "نامشخص", "resistance": None, "where": "",
                               "bls": list(order_bls), "bls_scope": "order",
                               "action": "", "source": "دفتر کارشناسان", **q}
        ml = sorted(mats.values(), key=lambda x: (CB.level_rank(x["level"]) if x["level"] else 99, x["key"]))
        out.append({
            "key": o, "pr": _first(_col(og, "MOGH_PR_NO")),
            # ارزش PI روی هر ردیف سفارش تکرار شده؛ یک بار برداشته می‌شود، جمع زده نمی‌شود
            "pi_value": _first_num(_col(og, "MOGH_PI_VALUE_SUM")), "pi_currency": _first(_col(og, "MOGH_CURRENCY")),
            "qty": _first_num(_col(og, "MOGH_ORDER_QTY_SUM")), "status": _first(_col(og, "ORDER_STAGE_FA")),
            "cancelled": any(truthy(v) for v in _col(og, "IS_CANCELLED")),
            "level": worst_level(list(_col(og, "ORDER_CRITICAL_LEVEL")) + [x["level"] for x in ml]),
            "materials": ml, "bls": order_bls,          # R8: بارنامه‌ها در سطح سفارش
        })
    out.sort(key=lambda x: (CB.level_rank(x["level"]) if x["level"] else 99, x["key"]))
    for o in out:
        o["level_fa"] = CB.level_label(o["level"]) if o["level"] else "نامشخص"
    return out


# ═══════════════════════════ بارنامه، پول، مراحل ═══════════════════════════
def bls(fx: FxData, reg: str) -> List[Dict[str, Any]]:
    """بارنامه‌های یک ثبت سفارش با ارزش فاکتور به ارز خودش، سهم و محل فعلی."""
    out = []
    for _, b in fx.link_by_reg.get(reg, pd.DataFrame()).iterrows():
        key = s(b.get("KEY_BL"))
        mg = fx.mart_by_bl.get(key, pd.DataFrame())
        full = any(truthy(v) for v in _col(mg, "IS_FULL_CLEARED")) if not mg.empty else False
        part = any(truthy(v) for v in _col(mg, "IS_PARTIAL_CLEARED")) if not mg.empty else False
        dem = [x for x in (n(v) for v in _col(mg, "روزهای رسوب")) if x is not None] if not mg.empty else []
        lvl = worst_level(_col(mg, "BL_CRITICAL_LEVEL")) if not mg.empty else ""
        out.append({
            "key": key, "value": n(b.get("BL_INVOICE_VALUE")), "currency": s(b.get("BL_CURRENCY")),
            "basis": s(b.get("BL_VALUE_BASIS")), "share_pct": n(b.get("SHARE_PCT")), "status": s(b.get("STATUS")),
            "flags": s(b.get("FLAGS")), "orders": s(b.get("ORDERS")), "materials": s(b.get("MATERIALS")),
            "where": " · ".join(_uniq(_col(mg, "STATUS_WHERE"))) if not mg.empty else "",
            "clearance": "ترخیص کامل" if full else ("ترخیص جزئی" if part else "ترخیص نشده"),
            "demurrage_days": max(dem) if dem else None,
            "cotage": _first(_col(mg, "COTAGE_NO")) if not mg.empty else "",
            "level": lvl, "level_fa": CB.level_label(lvl) if lvl else "",
        })
    return out


def money(fx: FxData, reg: Optional[str] = None) -> pd.DataFrame:
    """جریان پول به تفکیک ثبت سفارش × ارز؛ حمل‌شده فقط از بارنامه‌های هم‌ارز (s59)."""
    cols = (["KEY_REG", "CURRENCY"] + [k for k, _ in MONEY_STEPS]
            + ["REJECTED_REQUEST_AMOUNT", "RECON_STATUS", "EVIDENCE_GAPS", "CROSS_CURRENCY_NOTE"])
    m = fx.money if reg is None else fx.money_by_reg.get(reg, pd.DataFrame())
    if m is None or m.empty:
        return pd.DataFrame(columns=cols)
    m = m.copy()
    m["KEY_REG"] = m["KEY_REG"].map(s)
    shipped = {(k, s(r.get("REG_CURRENCY"))): n(r.get("SHIPPED_VALUE")) for k, r in fx.recon_by_reg.items()}
    ccy = m["CURRENCY"] if "CURRENCY" in m.columns else pd.Series([""] * len(m), index=m.index)
    m["SHIPPED_BL_VALUE"] = [shipped.get((r, s(c))) for r, c in zip(m["KEY_REG"], ccy)]
    for c in cols:
        if c not in m.columns:
            m[c] = None
    for k in [k for k, _ in MONEY_STEPS] + ["REJECTED_REQUEST_AMOUNT"]:
        m[k] = m[k].map(n)
    return m[cols].reset_index(drop=True)


#: درخواست رد یا باطل‌شده گام جریان پول نیست (جزو تقاضا نیست)؛ فقط برای دیدن کنار آن می‌آید
REJECTED_FA = "درخواست ردشده یا باطل"
MONEY_HEADS = (["ثبت سفارش", "ارز"] + [fa for _, fa in MONEY_STEPS]
               + [REJECTED_FA, "وضعیت تطبیق", "شکاف شاهد"])


def gaps_fa(v: Any) -> str:
    """«ALLOCATED_AMOUNT | PURCHASED_AMOUNT» ← «تخصیص، خرید ارز»."""
    return "، ".join(MONEY_FA.get(g.strip(), g.strip()) for g in s(v).split("|") if g.strip())


def money_display(fx: FxData, regs: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """جریان پول ثبت سفارش × ارز با عنوان فارسی (همان جدول Studio، HTML و Excel)."""
    m = money(fx)
    if regs is not None:
        keep = {s(r) for r in regs}
        m = m[m["KEY_REG"].isin(keep)]
    if m.empty:
        return pd.DataFrame(columns=MONEY_HEADS)
    m = m.copy()
    m["RECON_STATUS"] = m["RECON_STATUS"].map(lambda v: RECON_FA.get(s(v), s(v)))
    m["EVIDENCE_GAPS"] = m["EVIDENCE_GAPS"].map(gaps_fa)
    return m.rename(columns={"KEY_REG": "ثبت سفارش", "CURRENCY": "ارز", **MONEY_FA,
                             "REJECTED_REQUEST_AMOUNT": REJECTED_FA,
                             "RECON_STATUS": "وضعیت تطبیق", "EVIDENCE_GAPS": "شکاف شاهد"})[MONEY_HEADS]


def money_totals_display(frame: pd.DataFrame) -> pd.DataFrame:
    """جمع هر گام به تفکیک ارز + تعداد بی‌شاهد هر گام، با عنوان فارسی."""
    t = money_totals(frame)
    cols = ["ارز", "ثبت سفارش"]
    out = pd.DataFrame({"ارز": t.get("CURRENCY", []), "ثبت سفارش": t.get("REGISTRATIONS", [])})
    for k, fa in MONEY_STEPS:
        out[fa] = t[k] if k in t else None
        out[fa + " · بی‌شاهد"] = t["N_UNKNOWN_" + k] if ("N_UNKNOWN_" + k) in t else None
        cols += [fa, fa + " · بی‌شاهد"]
    return out[cols]


def money_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """جمع هر گام به تفکیک ارز. ``N_UNKNOWN_<گام>`` تعداد ردیف‌های بی‌شاهد را جدا نگه می‌دارد.

    ارز نامعلوم («نامشخص») ردیف جدا دارد ولی جمع ندارد: مبلغ‌های بی‌ارز ممکن است
    به چند ارز متفاوت باشند و جمعشان عدد بی‌معنایی می‌سازد (``SUMMED`` = False).
    """
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["CURRENCY", "REGISTRATIONS"])
    rows = []
    ccy = frame["CURRENCY"].map(lambda c: s(c) or "نامشخص")
    for c, g in frame.assign(_C=ccy).groupby("_C", sort=True):
        summed = c != "نامشخص"
        rec: Dict[str, Any] = {"CURRENCY": c, "REGISTRATIONS": int(g["KEY_REG"].nunique()), "SUMMED": summed}
        for k, _ in MONEY_STEPS:
            vals = [x for x in g[k] if x is not None and not (isinstance(x, float) and math.isnan(x))]
            rec[k] = float(sum(vals)) if vals and summed else None
            rec["N_UNKNOWN_" + k] = int(len(g) - len(vals))
        rows.append(rec)
    return pd.DataFrame(rows)


def path(fx: FxData, reg: str) -> List[Dict[str, str]]:
    """مسیر ۱۲ مرحله یک ثبت سفارش با وضعیت نمایشی done/current/gap/todo."""
    r = fx.lc_by_reg.get(reg)
    if r is None:
        return []
    cur = s(r.get("CURRENT_STAGE_CODE")) or "CLOSED"
    passed = cur == "CLOSED"
    out = []
    for code, fa in LIFECYCLE:
        status = s(r.get(code + "__STATUS"))
        if code == cur:
            state, passed = "current", True
        elif status == DONE:
            state = "done"
        elif not passed:
            state = "gap"
        else:
            state = "todo"
        out.append({"code": code, "label": fa, "state": state, "status": status or "—",
                    "date": s(r.get(code + "__DATE")), "evidence": s(r.get(code + "__EVIDENCE"))})
    return out


def ledger(fx: FxData, reg: Optional[str] = None) -> pd.DataFrame:
    cols = ["KEY_REG", "EVENT_FA", "EVENT_DATE", "AMOUNT", "CURRENCY", "SOURCE", "REFERENCE", "STATUS", "NOTE"]
    f = fx.ledger if reg is None else fx.ledger_by_reg.get(reg, pd.DataFrame())
    if f is None or f.empty:
        return pd.DataFrame(columns=cols)
    f = f.copy()
    for c in cols:
        if c not in f.columns:
            f[c] = None
    f["AMOUNT"] = f["AMOUNT"].map(n)
    return f[cols].reset_index(drop=True)


def decisions(fx: FxData, reg: Optional[str] = None) -> pd.DataFrame:
    cols = ["KEY_REG", "CURRENCY", "STAGE_CODE", "OBSERVED_GAP_AMOUNT", "AMOUNT_MEANING", "POSSIBLE_CAUSE",
            "PROCESS_OWNER", "SUGGESTED_ACTION", "EVIDENCE_GAP", "DECISION_STATUS"]
    f = fx.decisions if reg is None else fx.decisions_by_reg.get(reg, pd.DataFrame())
    if f is None or f.empty:
        return pd.DataFrame(columns=cols)
    f = f.copy()
    for c in cols:
        if c not in f.columns:
            f[c] = None
    f["STAGE_CODE"] = f["STAGE_CODE"].map(lambda c: STAGE_FA.get(s(c), s(c)))
    f["OBSERVED_GAP_AMOUNT"] = f["OBSERVED_GAP_AMOUNT"].map(n)
    return f[cols].reset_index(drop=True)


# ═══════════════════════════ مرحله‌ها ═══════════════════════════
def _levels_ok(level: str, levels: Sequence[str]) -> bool:
    return bool(level) and level in levels


def stage_summary(fx: FxData, critical_only: bool = False,
                  levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    """یک ردیف برای هر مرحله: تعداد، روزها، سررسید گذشته، شکاف شاهد و ثبت سفارش بحرانی.

    هیچ مبلغی اینجا نیست؛ مبلغ‌ها در :func:`stage_values` به تفکیک ارزند."""
    regs = fx.reg_table
    if critical_only:
        regs = regs[regs["CRITICAL_LEVEL"].map(lambda c: _levels_ok(c, levels))]
    rows = []
    total = max(len(regs), 1)
    for code, fa in STAGES:
        g = regs[regs["STAGE_CODE"].eq(code)]
        days = pd.to_numeric(g["STAGE_DAYS"], errors="coerce")
        uc = unique_counts(fx, g["KEY_REG"])       # R8: یکتا روی اجتماع، نه جمع شمارش هر ثبت سفارش
        rows.append({"STAGE_CODE": code, "STAGE": fa, "REGISTRATIONS": len(g),
                     "SHARE_PCT": round(len(g) / total * 100, 1) if len(regs) else None,
                     "DAYS_MEDIAN": float(days.median()) if days.notna().any() else None,
                     "DAYS_MAX": float(days.max()) if days.notna().any() else None,
                     "OVERDUE": int(g["STAGE_STATUS"].eq(OVERDUE).sum()),
                     "WITH_GAPS": int((g["GAP_COUNT"] > 0).sum()),
                     "CRITICAL_REGS": int(g["CRITICAL_LEVEL"].map(lambda c: _levels_ok(c, levels)).sum()),
                     "CRITICAL_MATERIALS": uc["critical_materials"],
                     "ORDERS": uc["orders"], "BLS": uc["bls"]})
    return pd.DataFrame(rows)


def unique_counts(fx: FxData, regs: Optional[Iterable[str]] = None) -> Dict[str, int]:
    """R8: شمار یکتای بارنامه، سفارش و متریال بحرانی روی اجتماع ثبت سفارش‌ها.

    بارنامه‌ای که به دو ثبت سفارش وصل است (یا سفارشی که زیر دو ثبت سفارش آمده)
    یک بار شمرده می‌شود؛ جمع ``BL_COUNT``/``ORDER_COUNT`` هر ثبت سفارش دوبار می‌شمرد."""
    if regs is None:
        keys = list(fx.reg_table["KEY_REG"]) if not fx.reg_table.empty else []
    else:
        keys = list(regs)
    bls_u: set = set()
    orders_u: set = set()
    crit_u: set = set()
    for reg in keys:
        reg = s(reg)
        if not reg:
            continue
        link = fx.link_by_reg.get(reg)
        if link is not None and not link.empty:
            bls_u |= {s(b) for b in _col(link, "KEY_BL") if s(b)}
        for o in orders(fx, reg):
            orders_u.add(o["key"])
            crit_u |= {m["key"] for m in o["materials"] if m["level"] in CB.DEFAULT_LEVELS}
    return {"bls": len(bls_u), "orders": len(orders_u), "critical_materials": len(crit_u)}


def stage_values(fx: FxData, critical_only: bool = False,
                 levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    """ارزش ثبت سفارش‌های هر مرحله به تفکیک ارز؛ ارز نامعلوم ردیف جدا و بی‌جمع."""
    regs = fx.reg_table
    if critical_only:
        regs = regs[regs["CRITICAL_LEVEL"].map(lambda c: _levels_ok(c, levels))]
    cols = ["STAGE_CODE", "STAGE", "CURRENCY", "REGISTRATIONS", "REG_VALUE", "UNKNOWN_VALUE_REGS",
            "SHIPPED_VALUE", "UNSHIPPED_VALUE", "OVERSHIPPED_REGS", "UNSHIPPED_UPPER_BOUND_REGS"]
    rows = []
    for code, fa in STAGES:
        g = regs[regs["STAGE_CODE"].eq(code)]
        if g.empty:
            continue
        for c, cg in g.assign(_C=g["REG_CURRENCY"].map(lambda x: s(x) or "نامشخص")).groupby("_C", sort=True):
            known = [n(x) for x in cg["REG_VALUE"] if n(x) is not None]
            sh = [n(x) for x in cg["SHIPPED_VALUE"] if n(x) is not None]
            # مانده منفی یعنی حمل بیش از ارزش ثبت سفارش؛ جدا شمرده می‌شود تا مانده
            # ثبت سفارش‌های دیگر را کم نکند
            un_all = [n(x) for x in cg["UNSHIPPED_VALUE"] if n(x) is not None]
            un = [x for x in un_all if x > 0]
            ok = c != "نامشخص"
            # مانده ثبت سفارشی که حمل‌شده‌اش «حداقل» است، «حداکثر» است؛ جمعش هم حداکثر است
            lb_col = cg["SHIPPED_IS_LOWER_BOUND"] if "SHIPPED_IS_LOWER_BOUND" in cg.columns else [False] * len(cg)
            upper = int(sum(1 for lb, u in zip(lb_col, cg["UNSHIPPED_VALUE"])
                            if truthy(lb) and (n(u) or 0) > 0)) if ok else 0
            rows.append({"STAGE_CODE": code, "STAGE": fa, "CURRENCY": c, "REGISTRATIONS": len(cg),
                         "REG_VALUE": float(sum(known)) if known and ok else None,
                         "UNKNOWN_VALUE_REGS": int(len(cg) - len(known)) if ok else len(cg),
                         "SHIPPED_VALUE": float(sum(sh)) if sh and ok else None,
                         "UNSHIPPED_VALUE": float(sum(un)) if un and ok else (0.0 if un_all and ok else None),
                         "OVERSHIPPED_REGS": sum(1 for x in un_all if x < 0),
                         "UNSHIPPED_UPPER_BOUND_REGS": upper})
    return pd.DataFrame(rows, columns=cols)


def busiest_stage(summary: pd.DataFrame) -> str:
    """پرکارترین مرحله باز (بسته‌شده فقط اگر همه بسته‌اند)."""
    if summary.empty or summary["REGISTRATIONS"].sum() == 0:
        return ""
    open_ = summary[summary["STAGE_CODE"].ne("CLOSED") & summary["REGISTRATIONS"].gt(0)]
    pick = open_ if not open_.empty else summary[summary["REGISTRATIONS"].gt(0)]
    return str(pick.sort_values("REGISTRATIONS", ascending=False, kind="stable").iloc[0]["STAGE_CODE"])


def reg_node(fx: FxData, reg: str, critical_only: bool = False,
             levels: Sequence[str] = CB.DEFAULT_LEVELS) -> Dict[str, Any]:
    """همه جزئیات یک ثبت سفارش برای نمایش سلسله‌مراتبی."""
    row = fx.reg_table[fx.reg_table["KEY_REG"].eq(reg)]
    base = row.iloc[0].to_dict() if not row.empty else {"KEY_REG": reg}
    tree = orders(fx, reg)
    if critical_only:
        tree = [dict(o, materials=[m for m in o["materials"] if _levels_ok(m["level"], levels)]) for o in tree]
        tree = [o for o in tree if o["materials"]]
    base.update({"orders": tree, "bls": bls(fx, reg), "money": money(fx, reg).to_dict("records"),
                 "path": path(fx, reg), "decisions": decisions(fx, reg).to_dict("records")})
    return base


def explorer(fx: FxData, critical_only: bool = False, levels: Sequence[str] = CB.DEFAULT_LEVELS,
             max_regs: Optional[int] = None) -> List[Dict[str, Any]]:
    """مدل کامل «مرحله ← ثبت سفارش ← سفارش ← متریال» برای نمای کلیک‌پذیر.

    ``max_regs`` فقط تعداد ثبت سفارش نمایش‌داده‌شده در هر مرحله را محدود می‌کند؛
    شمارش و مبلغ‌ها همیشه از همه ثبت سفارش‌های مرحله‌اند."""
    summ = stage_summary(fx, critical_only, levels)
    vals = stage_values(fx, critical_only, levels)
    regs = fx.reg_table
    if critical_only:
        regs = regs[regs["CRITICAL_LEVEL"].map(lambda c: _levels_ok(c, levels))]
    out = []
    for _, srow in summ.iterrows():
        code = srow["STAGE_CODE"]
        g = regs[regs["STAGE_CODE"].eq(code)]
        keys = g["KEY_REG"].tolist()
        shown = keys if max_regs is None else keys[:max_regs]
        out.append({"code": code, "label": srow["STAGE"], "count": int(srow["REGISTRATIONS"]),
                    "share_pct": srow["SHARE_PCT"], "days_median": srow["DAYS_MEDIAN"], "days_max": srow["DAYS_MAX"],
                    "overdue": int(srow["OVERDUE"]), "with_gaps": int(srow["WITH_GAPS"]),
                    "critical_regs": int(srow["CRITICAL_REGS"]), "critical_materials": int(srow["CRITICAL_MATERIALS"]),
                    "values": vals[vals["STAGE_CODE"].eq(code)].to_dict("records"),
                    "regs": [reg_node(fx, k, critical_only, levels) for k in shown],
                    "hidden": len(keys) - len(shown)})
    return out


# ═══════════════════════ جدول‌های تخت هر دانه (برای Excel) ═══════════════════════
def orders_frame(fx: FxData, regs: Optional[Iterable[str]] = None, critical_only: bool = False,
                 levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    """دانه سفارش: یک ردیف برای هر سفارش با ارزش PI خودش."""
    table = fx.reg_table.set_index("KEY_REG") if not fx.reg_table.empty else pd.DataFrame()
    rows = []
    for reg in (regs if regs is not None else table.index):
        stage = table.loc[reg, "STAGE"] if reg in table.index else ""
        for o in orders(fx, reg):
            mats = o["materials"] if not critical_only else [m for m in o["materials"] if _levels_ok(m["level"], levels)]
            if critical_only and not mats:
                continue
            rows.append({"مرحله جاری": stage, "ثبت سفارش": reg, "سفارش": o["key"], "درخواست خرید (PR)": o["pr"],
                         "وضعیت سفارش": o["status"], "ارزش PI": o["pi_value"], "ارز PI": o["pi_currency"],
                         "تعداد سفارش": o["qty"], "بدترین سطح بحرانی": o["level_fa"],
                         "متریال": len(mats), "ابطال": "بله" if o["cancelled"] else ""})
    return pd.DataFrame(rows, columns=["مرحله جاری", "ثبت سفارش", "سفارش", "درخواست خرید (PR)", "وضعیت سفارش",
                                       "ارزش PI", "ارز PI", "تعداد سفارش", "بدترین سطح بحرانی", "متریال", "ابطال"])


#: R8: عنوان‌های صادق — رابطه بارنامه↔متریال در هیچ منبعی نیست، فقط بارنامه↔سفارش
BL_OF_ORDER = "بارنامه‌های سفارش این متریال"
MATS_OF_ORDERS = "متریال‌های سفارش"


def materials_frame(fx: FxData, regs: Optional[Iterable[str]] = None, critical_only: bool = False,
                    levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    """دانه سفارش × متریال؛ بدون هیچ مبلغی (مبلغ در دانه سفارش و بارنامه است)."""
    table = fx.reg_table.set_index("KEY_REG") if not fx.reg_table.empty else pd.DataFrame()
    cols = ["مرحله جاری", "ثبت سفارش", "سفارش", "متریال", "شرح", "سطح بحرانی", "مقاومت (روز)", "کجاست",
            BL_OF_ORDER, "در راه", "در گمرک", "آماده حمل", "نزد سازنده", "نیاز روزانه", "اقدام پیشنهادی", "منبع"]
    rows = []
    for reg in (regs if regs is not None else table.index):
        stage = table.loc[reg, "STAGE"] if reg in table.index else ""
        for o in orders(fx, reg):
            for m in o["materials"]:
                if critical_only and not _levels_ok(m["level"], levels):
                    continue
                rows.append({"مرحله جاری": stage, "ثبت سفارش": reg, "سفارش": o["key"], "متریال": m["key"],
                             "شرح": m["desc"], "سطح بحرانی": m["level_fa"], "مقاومت (روز)": m["resistance"],
                             "کجاست": m["where"], "بارنامه‌های سفارش این متریال": "، ".join(m["bls"]),
                             "در راه": m.get("in_transit"), "در گمرک": m.get("in_customs"),
                             "آماده حمل": m.get("ready"), "نزد سازنده": m.get("at_supplier"),
                             "نیاز روزانه": m.get("daily_need"), "اقدام پیشنهادی": m["action"],
                             "منبع": m["source"]})
    return pd.DataFrame(rows, columns=cols)


def bls_frame(fx: FxData, regs: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """دانه بارنامه × ثبت سفارش با ارزش فاکتور به ارز خود بارنامه."""
    table = fx.reg_table.set_index("KEY_REG") if not fx.reg_table.empty else pd.DataFrame()
    cols = ["مرحله جاری", "ثبت سفارش", "بارنامه", "ارزش فاکتور", "ارز فاکتور", "مبنای ارزش", "سهم از ثبت سفارش (٪)",
            "وضعیت پیوند", "مغایرت", "کجاست", "ترخیص", "روزهای رسوب", "کوتاژ", "سطح بحرانی", "سفارش‌ها", MATS_OF_ORDERS]
    rows = []
    for reg in (regs if regs is not None else table.index):
        stage = table.loc[reg, "STAGE"] if reg in table.index else ""
        for b in bls(fx, reg):
            rows.append({"مرحله جاری": stage, "ثبت سفارش": reg, "بارنامه": b["key"], "ارزش فاکتور": b["value"],
                         "ارز فاکتور": b["currency"], "مبنای ارزش": b["basis"], "سهم از ثبت سفارش (٪)": b["share_pct"],
                         "وضعیت پیوند": b["status"], "مغایرت": b["flags"], "کجاست": b["where"],
                         "ترخیص": b["clearance"], "روزهای رسوب": b["demurrage_days"], "کوتاژ": b["cotage"],
                         "سطح بحرانی": b["level_fa"], "سفارش‌ها": b["orders"], "متریال‌های سفارش": b["materials"]})
    return pd.DataFrame(rows, columns=cols)


def critical_by_stage(fx: FxData, levels: Sequence[str] = CB.DEFAULT_LEVELS) -> pd.DataFrame:
    """ماتریس مرحله × سطح بحرانی: تعداد متریال بحرانی (سفارش × متریال) در هر مرحله."""
    mf = materials_frame(fx, critical_only=True, levels=levels)
    lvl_labels = [CB.level_label(c) for c in levels]
    rows = []
    for code, fa in STAGES:
        g = mf[mf["مرحله جاری"].eq(fa)]
        rec: Dict[str, Any] = {"مرحله": fa}
        for lab in lvl_labels:
            rec[lab] = int(g["سطح بحرانی"].eq(lab).sum())
        rec["ثبت سفارش"] = int(g["ثبت سفارش"].nunique())
        rows.append(rec)
    return pd.DataFrame(rows, columns=["مرحله"] + lvl_labels + ["ثبت سفارش"])
