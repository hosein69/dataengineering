# -*- coding: utf-8 -*-
"""ارزش و ارز ثبت سفارش، فقط از مرجع ثبت سفارش.

مرجع (تصمیم مالک، ۱۴۰۵/۰۷/۰۶): ایمپورت لایسنس NTSW («مبلغ کل پیش فاکتور»،
«نوع ارز») و IL Append («ارزش ثبت سفارش»، «نوع ارز»). پس از آن نسخه اعتبارات
اسنادی از همان پروفرم، و در نبود همه، جمع PI سفارش‌ها فقط به‌عنوان برآورد.

آنچه عمداً مبنا نیست:
  * **درخواست تخصیص.** ارز تخصیص می‌تواند به‌حق با ارز ثبت سفارش فرق کند (زمانی
    برات دلاری مجاز بود) و درخواست رد یا باطل‌شده اصلاً ارزی تعیین نمی‌کند.
  * **تعهد NTSW.** تعهد پس از تأمین ارز و به ارز تأمین ساخته می‌شود؛ تا 29.15.13
    «تعهد اولیه» مبنای دوم ارزش ثبت سفارش بود و ارز تعهدِ یک درخواست باطل (یوان)
    به‌جای ارز ثبت سفارش (یورو) نشست.

ارز فقط وقتی معلوم است که یک ارز شناخته‌شده باشد. وقتی منبع‌ها در ارز یا مبلغ
اختلاف دارند، مرجع بالاتر انتخاب می‌شود و اختلاف صریحاً گزارش می‌شود، نه پنهان.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..adapters.base import KEY_REG
from ..core.text import clean_key, is_empty_val, normalize_persian_text
from ..warehouse.numeric import number

BASIS_LICENSE = "ایمپورت لایسنس (NTSW)"
BASIS_IL = "IL Append"
BASIS_CREDIT = "ارزش پروفرم (اعتبارات اسنادی)"
BASIS_PI = "جمع PI سفارش‌ها (برآورد، نه ثبت سفارش)"
BASIS_NONE = "ارزش ثبت سفارش در هیچ منبعی نیست"

SOURCE_OF_BASIS = {BASIS_LICENSE: "ntsw/import_license", BASIS_IL: "ilappend/main",
                   BASIS_CREDIT: "credit/main", BASIS_PI: "moghavemat/main"}
#: ستون تاریخ و وضعیت هر مرجع، برای رویداد «ارزش ثبت سفارش» در دفتر مبلغی
BASIS_FIELDS = {BASIS_LICENSE: (("NTSW_REG_DATE",), "NTSW_LICENSE_STATUS"),
                BASIS_IL: (("IL_REG_DATE",), "IL_STATUS"),
                BASIS_CREDIT: (("CRD_REG_DATE",), "CRD_LAST_STATUS")}
#: اختلاف نسبی مجاز مبلغ ثبت سفارش میان منبع‌ها (گردکردن)
VALUE_TOLERANCE = 0.005
_VOID = ("باطل", "ابطال", "لغو", "انصراف", "منقضی")
_ISO_CODE = re.compile(r"[A-Z]{3}")


def currency_coder(rb: Any = None) -> Callable[[Any], str]:
    """متن ارز → کد ISO شناخته‌شده، وگرنه ``""``: متن ناشناخته («نامشخص»، «حواله») ارز نیست
    و دو متن ناشناخته هم‌ارز نیستند. قاعده‌نامه‌ای که فهرست ارزها را ندارد (آزمون) فقط کد
    سه‌حرفی لاتین را می‌پذیرد. یک پیاده‌سازی برای ثبت سفارش، جریان پول، پیوند بارنامه و ریسک."""
    if rb is None:
        from ..rulebook import get_rulebook
        rb = get_rulebook()
    strict = getattr(rb, "currency_code", None)
    loose = getattr(rb, "normalize_currency", None)

    def code(v: Any) -> str:
        if is_empty_val(v):
            return ""
        try:
            if strict is not None:
                return strict(v) or ""
            c = (loose(v) if loose is not None else str(v).strip().upper()) or ""
            return c if _ISO_CODE.fullmatch(c) else ""
        except Exception:
            return ""
    return code


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> Optional[float]:
    """عدد یا None؛ متن غیرعددی («*»، «دارد») صفر نمی‌شود."""
    if is_empty_val(v, treat_zero_as_empty=False):
        return None
    x = number(v)
    return x if math.isfinite(x) else None


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name] if name in df.columns else pd.Series([None] * len(df), index=df.index, dtype=object)


def is_void_status(text: Any) -> bool:
    """وضعیت باطل، ابطال، لغو، انصراف یا منقضی (پس از یکسان‌سازی متن)."""
    return _void(text)


def _void(text: Any) -> bool:
    t = normalize_persian_text(text)
    return bool(t) and any(normalize_persian_text(w) in t for w in _VOID)


def _unique_value(values: Iterable[Any]) -> Tuple[Optional[float], bool]:
    known = sorted({round(v, 2) for v in (_num(x) for x in values) if v is not None})
    if not known:
        return None, False
    if len(known) > 1:
        return None, True
    return known[0], False


def _unique_ccy(values: Iterable[Any], code: Callable[[Any], str]) -> Tuple[str, bool]:
    codes = {c for c in (code(v) for v in values) if c}
    if len(codes) == 1:
        return next(iter(codes)), False
    return "", len(codes) > 1


def _amendment_no(v: Any) -> int:
    k = clean_key(v)
    return int(k) if k.isdigit() else 0


def _by_reg(df: Optional[pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or KEY_REG not in df.columns:
        return {}
    regs = df[KEY_REG].map(_s)
    return {r: g for r, g in df.groupby(regs, sort=False) if r}


def _candidate(g: pd.DataFrame, value_col: str, ccy_col: str, status_col: str, label: str,
               code: Callable[[Any], str]) -> Dict[str, Any]:
    """مبلغ و ارز یکتای یک منبع برای یک ثبت سفارش؛ ردیف باطل‌شده فقط وقتی چیز دیگری نیست."""
    flags: List[str] = []
    live = g[~_col(g, status_col).map(_void)] if status_col in g.columns else g
    if live.empty and not g.empty:
        live = g
        flags.append(f"ثبت سفارش در {label} باطل‌شده است")
    value, v_conflict = _unique_value(_col(live, value_col))
    ccy, c_conflict = _unique_ccy(_col(live, ccy_col), code)
    if v_conflict:
        flags.append(f"چند مبلغ متفاوت در {label}")
    if c_conflict:
        flags.append(f"چند ارز متفاوت در {label}")
    raw = sorted({_s(x) for x in _col(live, ccy_col) if _s(x) and not code(x)})
    if raw:
        flags.append(f"ارز ناشناخته در {label}: " + "، ".join(raw))
    return {"value": value, "currency": ccy, "flags": flags, "rows": live}


def _il_candidate(g: pd.DataFrame, code: Callable[[Any], str]) -> Dict[str, Any]:
    """IL Append: ردیف‌های آخرین اصلاحیه؛ «تغییر واحد ارز» یا «تغییر مبلغ کل پروفرم»
    فقط وقتی جای مقدار را می‌گیرد که واقعاً یک ارز یا یک مبلغ باشد."""
    live = g[~_col(g, "IL_STATUS").map(_void)] if "IL_STATUS" in g.columns else g
    base = live if not live.empty else g
    amend = _col(base, "IL_AMENDMENT_NO").map(_amendment_no)
    latest = base[amend.eq(amend.max())] if len(base) else base
    out = _candidate(latest, "IL_REG_VALUE", "IL_CURRENCY", "IL_STATUS", BASIS_IL, code)
    if live.empty and not g.empty:
        out["flags"].insert(0, f"ثبت سفارش در {BASIS_IL} باطل‌شده است")
    n = int(amend.max()) if len(base) else 0
    new_ccy, _ = _unique_ccy(_col(latest, "IL_CHANGE_CURRENCY"), code)
    new_val, _ = _unique_value(x for x in _col(latest, "IL_CHANGE_PROFORMA_TOTAL") if (_num(x) or 0) > 0)
    if new_ccy and new_ccy != out["currency"]:
        out["currency"] = new_ccy
        out["flags"].append(f"ارز از اصلاحیه {n} ({new_ccy})")
    if new_val is not None and new_val != out["value"]:
        out["value"] = new_val
        out["flags"].append(f"مبلغ از اصلاحیه {n}")
    return out


def _pi_candidate(g: pd.DataFrame, code: Callable[[Any], str]) -> Dict[str, Any]:
    if "MOGH_PI_VALUE_SUM" not in g.columns or "KEY_ORDER" not in g.columns:
        return {"value": None, "currency": "", "flags": [], "rows": None}
    per_order = g[g["KEY_ORDER"].map(_s) != ""].drop_duplicates("KEY_ORDER")
    vals = [_num(x) for x in per_order["MOGH_PI_VALUE_SUM"]]
    ccy, multi = _unique_ccy(_col(per_order, "MOGH_CURRENCY"), code)
    if vals and all(x is not None for x in vals) and ccy and not multi:
        return {"value": round(sum(vals), 2), "currency": ccy, "flags": [], "rows": per_order}
    return {"value": None, "currency": "", "flags": [], "rows": None}


def _fmt(v: Optional[float], c: str) -> str:
    return ("—" if v is None else f"{v:,.2f}") + (f" {c}" if c else "")


def registration_values(sheet: Callable[[str, str], Optional[pd.DataFrame]],
                        code: Callable[[Any], str],
                        mart: Optional[pd.DataFrame] = None,
                        regs: Optional[Iterable[str]] = None) -> Dict[str, Dict[str, Any]]:
    """برای هر ثبت سفارش: مبلغ، ارز، مبنا، منبع و فهرست اختلاف منبع‌ها.

    ``sheet(source, frame)`` فریم استانداردشده منبع را می‌دهد و ``code`` متن ارز را
    به کد ISO شناخته‌شده (یا ``""``) تبدیل می‌کند. ``regs`` جمعیت را تعیین می‌کند؛
    بی آن، همه ثبت سفارش‌های هر چهار منبع.
    """
    lic = _by_reg(sheet("ntsw", "import_license"))
    il = _by_reg(sheet("ilappend", "main"))
    cr = _by_reg(sheet("credit", "main"))
    pi = _by_reg(mart) if mart is not None else {}
    population = set(regs) if regs is not None else (set(lic) | set(il) | set(cr) | set(pi))
    out: Dict[str, Dict[str, Any]] = {}
    for reg in sorted(r for r in population if r):
        cands: List[Tuple[str, Dict[str, Any]]] = []
        if reg in lic:
            cands.append((BASIS_LICENSE, _candidate(lic[reg], "NTSW_LICENSE_VALUE", "NTSW_LICENSE_CURRENCY",
                                                    "NTSW_LICENSE_STATUS", BASIS_LICENSE, code)))
        if reg in il:
            cands.append((BASIS_IL, _il_candidate(il[reg], code)))
        if reg in cr:
            # LC ابطال‌شده («ابطال شده»، «ابطال شد») مبنای ارزش نیست، مگر هیچ LC دیگری نباشد
            cands.append((BASIS_CREDIT, _candidate(cr[reg], "CRD_PROFORMA_VALUE", "CRD_CURRENCY",
                                                   "CRD_LAST_STATUS", BASIS_CREDIT, code)))
        chosen = next(((b, c) for b, c in cands if c["value"] is not None and c["currency"]), None)
        partial = [(b, x) for b, x in cands if x["value"] is not None and not x["currency"]]
        flags: List[str] = [f for _, c in cands for f in c["flags"]]
        if chosen is None and partial:
            # مبلغ مرجع ثبت سفارش هست ولی ارز آن معلوم نیست: مبلغ با ارز نامعلوم می‌ماند (با بارنامه مقایسه
            # و جمع نمی‌شود) و جمع PI سفارش‌ها، که فقط برآورد است، جای آن نمی‌نشیند
            chosen = partial[0]
            flags.append("مبلغ هست ولی ارز آن معلوم نیست: " + "، ".join(
                f"{b}={_fmt(x['value'], '')}" for b, x in partial))
        elif chosen is None and reg in pi:
            est = _pi_candidate(pi[reg], code)
            if est["value"] is not None:
                chosen = (BASIS_PI, est)
        if chosen is not None and not chosen[1]["currency"]:
            basis, c = chosen
            value, ccy = c["value"], ""
        elif chosen is not None:
            basis, c = chosen
            value, ccy = c["value"], c["currency"]
            others = [(b, x) for b, x in cands if b != basis]
            diff_ccy = [(b, x) for b, x in others if x["currency"] and x["currency"] != ccy]
            if diff_ccy:
                flags.append("ارز ثبت سفارش در منبع‌ها یکی نیست: " + "، ".join(
                    f"{b}={x['currency']}" for b, x in [(basis, c)] + diff_ccy))
            diff_val = [(b, x) for b, x in others if x["currency"] == ccy and x["value"] is not None
                        and abs(x["value"] - value) > VALUE_TOLERANCE * max(abs(value), abs(x["value"]), 1e-9)]
            if diff_val:
                flags.append("مبلغ ثبت سفارش در منبع‌ها یکی نیست: " + "، ".join(
                    f"{b}={_fmt(x['value'], x['currency'])}" for b, x in [(basis, c)] + diff_val))
        else:
            basis, value, ccy = BASIS_NONE, None, ""
        # ردیف‌های شاهد: مرجع انتخاب‌شده، وگرنه اولین منبعی که ردیف داشت ولی مبلغ یا ارزش نامعلوم بود
        ev_basis, ev = (chosen if chosen is not None else
                        next(((b, c) for b, c in cands), (BASIS_NONE, {"rows": None})))
        rows = ev.get("rows")
        date_cols, status_col = BASIS_FIELDS.get(ev_basis, ((), ""))
        out[reg] = {
            "value": value, "currency": ccy, "basis": basis,
            "source": SOURCE_OF_BASIS.get(basis, ""),
            "flags": list(dict.fromkeys(flags)),
            "candidates": {b: (x["value"], x["currency"]) for b, x in cands},
            "evidence_basis": ev_basis,
            "evidence_source": SOURCE_OF_BASIS.get(ev_basis, ""),
            "rows": rows,
            "date": _first_date(rows, date_cols),
            "status": _first_text(rows, status_col),
        }
    return out


def _first_text(rows: Optional[pd.DataFrame], col: str) -> str:
    if rows is None or not col or col not in rows.columns:
        return ""
    return next((_s(x) for x in rows[col] if _s(x)), "")


def _first_date(rows: Optional[pd.DataFrame], cols: Iterable[str]) -> str:
    """زودترین تاریخ ثبت در ردیف‌های شاهد (متن اصلی منبع، بی‌تغییر)."""
    from ..core.jalali import CalendarEngine
    if rows is None:
        return ""
    for col in cols:
        if col not in rows.columns:
            continue
        found = [(d, _s(x)) for x in rows[col] for d in [CalendarEngine.parse(x)] if d]
        if found:
            return min(found)[1]
    return ""
