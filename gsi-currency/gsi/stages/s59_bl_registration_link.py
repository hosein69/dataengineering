# -*- coding: utf-8 -*-
"""مرحله ۵۹ — پیوند مبلغی بارنامه ↔ ثبت سفارش و چرخه کامل ارز تا رفع تعهد.

پرسشی که این مرحله پاسخ می‌دهد:

    «این بارنامه با ارزش فاکتور X و ارز Y، مربوط به کدام ثبت سفارش با
     مبلغ Z و ارز W است؛ چند درصد از آن ثبت سفارش تا امروز حمل شده و
     چه مقدار هنوز حمل نشده است؟»

مرحله‌های ۵۵ و ۵۶ پول را در سطح ثبت سفارش (REG) رهگیری می‌کنند؛ این مرحله
حلقه‌ی گمشده‌ی میان «حمل» و «ثبت سفارش» را می‌بندد و یک نمای یکپارچه از کل
چرخه — پرونده ثبت سفارش ← صدور ثبت سفارش ← صف تخصیص ← تخصیص ← خرید ارز ←
تأمین وجه/سوئیفت ← حمل ← ترخیص ← ارائه سند به بانک ← رفع تعهد — می‌سازد.

قواعدی که این مرحله نمی‌شکند (همان قواعد ۵۵/۵۶):
  * **نامعلوم ≠ صفر.** نبود ارزش فاکتور یا ارزش ثبت سفارش ``None`` می‌ماند.
  * **جمع بین‌ارزی ممنوع.** ارزش بارنامه فقط وقتی به حمل‌شده‌ی ثبت سفارش
    اضافه می‌شود که ارزش هم‌ارز با ارز ثبت سفارش باشد؛ هیچ نرخی اعمال نمی‌شود.
    ارز نامعلوم (چه ارز بارنامه، چه ارز ثبت سفارش) هم‌ارز هیچ ارزی نیست: آن
    ارزش جمع زده نمی‌شود و «ارز نامعلوم» گزارش می‌شود.
  * **تعارض پوشانده نمی‌شود.** وقتی ارزش فاکتور ساتا برای یک بارنامه تعارض دارد،
    ارزش اظهار گمرکی جایش نمی‌نشیند؛ جایگزین گمرک فقط برای ارزشِ نبودهٔ ساتاست.
  * **fan-out ایمن.** مارت در دانه بارنامه×متریال است؛ ارزش هر بارنامه یک بار
    شمرده می‌شود، نه به تعداد متریال‌هایش.
  * **سهم نامعلوم، تقسیم نمی‌شود.** بارنامه‌ای که به بیش از یک ثبت سفارش وصل
    است سهم هر ثبت سفارش را در منبع ندارد؛ ارزش آن به هیچ‌کدام اضافه نمی‌شود
    و صریحاً «سهم نامعلوم» گزارش می‌شود.

خروجی‌ها:
  * ستون‌های ``BLREG_*`` روی هر ردیف مارت
  * ctx.extras['bl_registration_link']      یک ردیف برای هر بارنامه×ثبت سفارش
  * ctx.extras['registration_value_recon']  یک ردیف برای هر ثبت سفارش
  * ctx.extras['fx_lifecycle']              چرخه کامل هر ثبت سفارش (یک ردیف)
  * ctx.extras['allocation_queue']          صف تخصیص ارز، مرتب بر اساس انتظار
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..adapters.base import KEY_REG
from ..core.jalali import CalendarEngine
from ..core.text import is_empty_val, num_safe
from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_CURRENCY, FMT_DECIMAL, FMT_INT, GROUP_ANALYTIC,
                   GROUP_DETAIL, PipelineContext, Stage, register)

#: تلورانس گردکردن در مقایسه‌ی حمل‌شده با ارزش ثبت سفارش (نسبی)
TOLERANCE = 0.005
#: اختلاف نسبی مجاز بین ارزش فاکتور ساتا و ارزش فاکتور گمرک
SOURCE_TOLERANCE = 0.01

# ── وضعیت‌های پیوند (سطح ثبت سفارش) ──
ST_NO_REG = "بارنامه بدون ثبت سفارش"
ST_NO_BL = "ثبت سفارش بدون بارنامه"
ST_REG_UNKNOWN = "ارزش ثبت سفارش نامعلوم"
ST_CCY_MISMATCH = "ارز بارنامه ≠ ارز ثبت سفارش"
ST_OVER = "حمل بیش از ارزش ثبت سفارش"
ST_FULL = "حمل کامل"
ST_PARTIAL = "حمل جزئی"
ST_BL_UNKNOWN = "ارزش بارنامه نامعلوم"
ST_CCY_UNKNOWN = "ارز نامعلوم"
ST_LINKED = "پیوند معتبر"

#: ترتیب شدت برای مرتب‌سازی و رنگ
STATUS_SEVERITY = {
    ST_OVER: 5, ST_CCY_MISMATCH: 4, ST_NO_REG: 4, ST_REG_UNKNOWN: 3,
    ST_BL_UNKNOWN: 3, ST_CCY_UNKNOWN: 3, ST_PARTIAL: 1, ST_LINKED: 0, ST_NO_BL: 1, ST_FULL: 0,
}

#: مراحل چرخه ارز — مرحله اول (پرونده) اینجا اضافه می‌شود، بقیه از خط زمانی ۵۶
LIFECYCLE = [
    ("REG_FILE", "پرونده ثبت سفارش"),
    ("ORDER_REG", "صدور ثبت سفارش"),
    ("ALLOCATION_QUEUE", "صف تخصیص"),
    ("ALLOCATION", "تخصیص ارز"),
    ("FX_PURCHASE", "خرید ارز"),
    ("FUNDING", "تأمین وجه"),
    ("SWIFT_CONVERSION", "سوئیفت / وصول ذی‌نفع"),
    ("SHIPMENT", "حمل (بارنامه)"),
    ("CUSTOMS", "ورود / کوتاژ"),
    ("CLEARANCE", "ترخیص"),
    ("BANK_DOCS", "ارائه سند به بانک"),
    ("SETTLEMENT", "رفع تعهد"),
]
STATUS_FA = {"DONE": "انجام شد", "PENDING": "در انتظار", "WARNING": "هشدار",
             "OVERDUE": "سررسید گذشته", "EVIDENCE_GAP": "بدون شاهد", "": "—"}


def _s(v: Any) -> str:
    return "" if is_empty_val(v) else str(v).strip()


def _num(v: Any) -> Optional[float]:
    if is_empty_val(v, treat_zero_as_empty=False):
        return None
    try:
        x = num_safe(v)
        if x is None:
            return None
        x = float(x)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name] if name in df.columns else pd.Series([None] * len(df), index=df.index, dtype=object)


def _unique_value(values) -> Tuple[Optional[float], bool]:
    """مقدار یکتای معلوم؛ دو مقدار متفاوت = تعارض (None, True)."""
    known = sorted({round(v, 2) for v in (_num(x) for x in values) if v is not None})
    if not known:
        return None, False
    if len(known) > 1:
        return None, True
    return known[0], False


def _ccy_of(values, norm) -> Tuple[str, bool]:
    codes = {c for c in (norm(v) for v in values) if c}
    if len(codes) == 1:
        return next(iter(codes)), False
    return "", len(codes) > 1


def _rel_diff(a: float, b: float) -> float:
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base


@register
class BLRegistrationLinkStage(Stage):
    name = "bl_registration_link"
    title = "پیوند مبلغی بارنامه ↔ ثبت سفارش و چرخه ارز"
    order = 59
    tolerant = True
    requires: List[str] = []
    provides = [
        "BLREG_BL_INVOICE_VALUE", "BLREG_BL_CURRENCY", "BLREG_BL_VALUE_BASIS",
        "BLREG_REG_VALUE", "BLREG_REG_CURRENCY", "BLREG_REG_VALUE_BASIS",
        "BLREG_BL_SHARE_PCT", "BLREG_REG_BL_COUNT", "BLREG_REG_SHIPPED_VALUE",
        "BLREG_REG_SHIPPED_PCT", "BLREG_REG_UNSHIPPED_VALUE", "BLREG_STATUS",
        "BLREG_FLAGS", "LIFECYCLE_STAGE", "LIFECYCLE_STAGE_DAYS", "LIFECYCLE_DONE_COUNT", "LIFECYCLE_GAPS",
    ]

    # ─────────────────────────────── اجرا ───────────────────────────────
    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        norm = self._normalizer(ctx)
        reg_values = self._registration_values(df, ctx, norm)
        link = self._bl_link(df, norm)
        recon, link = self._reconcile(link, reg_values)
        lifecycle = self._lifecycle(df, ctx, recon, self._currency_facts(ctx, norm))
        queue = self._allocation_queue(df, ctx)

        ctx.extras["bl_registration_link"] = link
        ctx.extras["registration_value_recon"] = recon
        ctx.extras["fx_lifecycle"] = lifecycle
        ctx.extras["allocation_queue"] = queue
        df = self._write_columns(df, link, recon, lifecycle)
        log.info(f"   🔗 پیوند بارنامه↔ثبت سفارش: {len(link)} جفت · {len(recon)} ثبت سفارش · "
                 f"صف تخصیص باز: {len(queue)}")
        return df

    @staticmethod
    def _normalizer(ctx: PipelineContext):
        """متن ارز → کد ISO شناخته‌شده، وگرنه «». دو متن ناشناخته (مثلاً «نامشخص»)
        هم‌ارز نیستند؛ تا 29.15.13 متن ناشناخته خودش «ارز» حساب می‌شد."""
        from ..finance.registration import currency_coder
        return currency_coder(getattr(ctx, "rb", None))

    # ─────────────────── ارزش هر ثبت سفارش (با مبنا) ───────────────────
    def _registration_values(self, df: pd.DataFrame, ctx: PipelineContext, norm) -> Dict[str, Dict[str, Any]]:
        """ارزش و ارز ثبت سفارش از ایمپورت لایسنس → IL Append → پروفرم اعتبارات → جمع PI (برآورد).

        تعهد NTSW و درخواست تخصیص مبنا نیستند؛ ارزشان جدا در چرخه مقایسه می‌شود.
        جمعیت همان قبلی است: ثبت سفارش‌های مارت و فایل اعتبارات.
        """
        from ..finance.registration import registration_values
        population = {_s(x) for x in _col(df, KEY_REG)}
        cr = ctx.sheet("credit", "main")
        if cr is not None and not cr.empty and KEY_REG in cr.columns:
            population |= {_s(x) for x in cr[KEY_REG]}
        population.discard("")
        return registration_values(ctx.sheet, norm, mart=df, regs=population)

    # ───────────────────── جدول بارنامه × ثبت سفارش ─────────────────────
    def _bl_link(self, df: pd.DataFrame, norm) -> pd.DataFrame:
        cols = ["KEY_BL", "KEY_REG", "ORDERS", "MATERIALS", "BL_INVOICE_VALUE", "BL_CURRENCY",
                "BL_VALUE_BASIS", "CUSTOMS_INVOICE_VALUE", "CUSTOMS_CURRENCY", "BL_REG_COUNT", "FLAGS"]
        if df.empty:
            return pd.DataFrame(columns=cols)
        bl = (_col(df, "CANONICAL_BL") if "CANONICAL_BL" in df.columns else _col(df, "KEY_BL")).map(_s)
        reg = _col(df, KEY_REG).map(_s)
        work = df.assign(_BL=bl, _REG=reg)
        work = work[(work["_BL"] != "") | (work["_REG"] != "")]
        # تعداد ثبت سفارش هر بارنامه (برای سهم نامعلوم)
        regs_per_bl = work[work["_BL"] != ""].groupby("_BL")["_REG"].agg(lambda s: len({x for x in s if x}))
        # R8: بارنامه فقط روی ردیف متریال اول سفارش نشسته؛ منبعی نمی‌گوید کدام بارنامه کدام متریال را
        # حمل می‌کند. MATERIALS = متریال‌های سفارش‌های این بارنامه (همه ردیف‌های سفارش، از جمله ADDITIONAL).
        okey = _col(df, "KEY_ORDER").map(_s)
        mkey = _col(df, "KEY_MATERIAL").map(_s)
        mats_of_order: Dict[str, List[str]] = {}
        for o, m in zip(okey, mkey):
            if o and m and m not in mats_of_order.setdefault(o, []):
                mats_of_order[o].append(m)
        rows: List[Dict[str, Any]] = []
        for (b, r), g in work.groupby(["_BL", "_REG"], sort=True):
            if not b:
                continue  # ردیف بدون بارنامه (مثلاً متریال ADDITIONAL) — در سطح REG دیده می‌شود
            flags: List[str] = []
            value, conflict = _unique_value(_col(g, "INVOICE_VALUE"))
            ccy, multi = _ccy_of(_col(g, "INVOICE_CURRENCY"), norm)
            basis = "فاکتور تجاری (ساتا)"
            if value is None and not conflict:
                # جایگزین: ارزش فاکتور اظهارشده در گمرک — فقط وقتی ساتا ارزشی ندارد؛
                # تعارض ساتا با یک عدد گمرک «حل» نمی‌شود و نامعلوم می‌ماند
                cv, _ = _unique_value(_col(g, "CL_INVOICE_VALUE"))
                cc, _m = _ccy_of(_col(g, "CL_CURRENCY"), norm)
                if cv is not None and cc:
                    value, ccy, basis = cv, cc, "ارزش فاکتور اظهار گمرکی"
            if conflict:
                flags.append("چند ارزش متفاوت فاکتور برای یک بارنامه")
                basis = "تعارض"
            if multi:
                flags.append("چند ارز برای یک بارنامه")
                value, ccy = None, ""
            unknown_txt = sorted({_s(x) for x in _col(g, "INVOICE_CURRENCY") if _s(x) and not norm(x)})
            if unknown_txt:
                flags.append("ارز ناشناخته در منبع: " + "، ".join(unknown_txt))
            cust_v, _ = _unique_value(_col(g, "CL_INVOICE_VALUE"))
            cust_c, _ = _ccy_of(_col(g, "CL_CURRENCY"), norm)
            # دو مبلغ فقط وقتی سنجیده می‌شوند که ارز هر دو معلوم و یکی باشد؛ عدد گمرکِ بی‌ارز
            # نه «هم‌خوان» است نه «متعارض» (همان عدد می‌تواند به ارز دیگری باشد).
            if value is not None and cust_v is not None and basis.startswith("فاکتور") and cust_c and ccy:
                if cust_c != ccy:
                    flags.append(f"ارز فاکتور ساتا ({ccy}) با ارز اظهار گمرکی ({cust_c}) یکی نیست")
                elif _rel_diff(value, cust_v) > SOURCE_TOLERANCE:
                    flags.append(f"اختلاف ارزش فاکتور ساتا و گمرک ({_rel_diff(value, cust_v) * 100:,.1f}٪)")
            n_regs = int(regs_per_bl.get(b, 0))
            if n_regs > 1:
                flags.append(f"بارنامه به {n_regs} ثبت سفارش وصل است؛ سهم هر یک در منبع نیست")
            orders = sorted({_s(x) for x in _col(g, "KEY_ORDER") if _s(x)})
            mats = sorted({m for o in orders for m in mats_of_order.get(o, [])})
            rows.append({
                "KEY_BL": b, "KEY_REG": r, "ORDERS": "، ".join(orders), "MATERIALS": "، ".join(mats),
                "BL_INVOICE_VALUE": value, "BL_CURRENCY": ccy,
                "BL_VALUE_BASIS": basis if value is not None or conflict else "نامعلوم",
                "CUSTOMS_INVOICE_VALUE": cust_v, "CUSTOMS_CURRENCY": cust_c,
                "BL_REG_COUNT": n_regs, "FLAGS": " · ".join(flags),
            })
        return pd.DataFrame(rows, columns=cols)

    # ───────────────── تطبیق ارزش حمل‌شده با ثبت سفارش ─────────────────
    def _reconcile(self, link: pd.DataFrame, reg_values: Dict[str, Dict[str, Any]]):
        regs = sorted(set(reg_values) | {r for r in link.get("KEY_REG", pd.Series(dtype=str)) if r})
        recon_rows: List[Dict[str, Any]] = []
        link = link.copy()
        for col in ("REG_VALUE", "REG_CURRENCY", "REG_VALUE_BASIS", "SHARE_PCT", "STATUS"):
            link[col] = None
        for reg in regs:
            rv = reg_values.get(reg, {"value": None, "currency": "", "basis": "ارزش ثبت سفارش در هیچ منبعی نیست"})
            value, ccy = rv["value"], rv["currency"]
            mask = link["KEY_REG"].eq(reg) if not link.empty else pd.Series(dtype=bool)
            g = link[mask] if not link.empty else link
            shipped = 0.0
            unknown_bl, other_ccy, shared, unknown_ccy = 0, set(), 0, 0
            for idx, b in g.iterrows():
                bv, bc = b["BL_INVOICE_VALUE"], _s(b["BL_CURRENCY"])
                share = None
                if b["BL_REG_COUNT"] > 1:
                    shared += 1
                    st = ST_BL_UNKNOWN
                elif bv is None or (isinstance(bv, float) and math.isnan(bv)):
                    unknown_bl += 1
                    st = ST_BL_UNKNOWN
                elif not bc:
                    # ارزش هست ولی ارزش به چه ارزی است معلوم نیست: هم‌ارز فرض نمی‌شود
                    unknown_ccy += 1
                    st = ST_CCY_UNKNOWN
                elif not ccy:
                    # ارز ثبت سفارش نامعلوم است؛ ارزش بارنامه با آن مقایسه یا جمع نمی‌شود
                    st = ST_CCY_UNKNOWN
                elif bc != ccy:
                    other_ccy.add(bc)
                    st = ST_CCY_MISMATCH
                else:
                    shipped += float(bv)
                    st = ST_LINKED
                    if value:
                        share = round(float(bv) / value * 100, 2)
                link.at[idx, "REG_VALUE"] = value
                link.at[idx, "REG_CURRENCY"] = ccy
                link.at[idx, "REG_VALUE_BASIS"] = rv["basis"]
                link.at[idx, "SHARE_PCT"] = share
                link.at[idx, "STATUS"] = st
            n_bl = len(g)
            # بی ارز ثبت سفارش، «حمل‌شده» ارزی ندارد که به آن بیان شود: نامعلوم، نه جمع بی‌ارز
            comparable = bool(ccy) and n_bl > 0
            pct = round(shipped / value * 100, 2) if value and comparable else None
            if value is None:
                remaining = None
            elif n_bl == 0:
                remaining = round(value, 2)
            else:
                remaining = round(value - shipped, 2) if comparable else None
            flags: List[str] = []
            if n_bl == 0:
                status = ST_NO_BL
            elif value is None:
                status = ST_REG_UNKNOWN
            elif not ccy:
                status = ST_CCY_UNKNOWN
            elif other_ccy:
                status = ST_CCY_MISMATCH
                flags.append("ارز بارنامه‌ها: " + "، ".join(sorted(other_ccy)) + f" · ارز ثبت سفارش: {ccy}")
            elif shipped > value * (1 + TOLERANCE):
                status = ST_OVER
            elif shipped >= value * (1 - TOLERANCE) and not unknown_bl and not shared and not unknown_ccy:
                status = ST_FULL
            else:
                status = ST_PARTIAL
            if n_bl and not ccy:
                flags.append("ارز ثبت سفارش نامعلوم؛ ارزش بارنامه‌ها با آن مقایسه و جمع نشد")
            flags.extend(rv.get("flags", []))
            if unknown_bl:
                flags.append(f"{unknown_bl} بارنامه با ارزش نامعلوم (در جمع نیامد)")
            if unknown_ccy:
                flags.append(f"{unknown_ccy} بارنامه با ارز نامعلوم (در جمع نیامد)")
            if shared:
                flags.append(f"{shared} بارنامه مشترک با ثبت سفارش دیگر (سهم نامعلوم)")
            shipped_value = round(shipped, 2) if comparable else None
            # جمع حمل‌شده وقتی بخشی نامعلوم است «حداقل» است نه «دقیق»، و مانده حمل‌نشده «حداکثر»
            lower_bound = shipped_value is not None and bool(unknown_bl or shared or other_ccy or unknown_ccy)
            if lower_bound and remaining is not None and remaining > 0:
                flags.append("مانده حمل‌نشده حداکثر است، چون بخشی از حمل در جمع نیامد")
            recon_rows.append({
                "KEY_REG": reg, "REG_VALUE": value, "REG_CURRENCY": ccy, "REG_VALUE_BASIS": rv["basis"],
                "BL_COUNT": n_bl, "SHIPPED_VALUE": shipped_value,
                "SHIPPED_IS_LOWER_BOUND": lower_bound, "SHIPPED_PCT": pct,
                "UNSHIPPED_VALUE": remaining,
                "STATUS": status, "SEVERITY": STATUS_SEVERITY.get(status, 0),
                "FLAGS": " · ".join(flags),
                "BL_LIST": "، ".join(g["KEY_BL"].tolist()) if n_bl else "",
            })
        # بارنامه‌هایی که هیچ ثبت سفارشی ندارند
        if not link.empty:
            orphan = link["KEY_REG"].eq("")
            link.loc[orphan, "STATUS"] = ST_NO_REG
        recon = pd.DataFrame(recon_rows, columns=[
            "KEY_REG", "REG_VALUE", "REG_CURRENCY", "REG_VALUE_BASIS", "BL_COUNT", "SHIPPED_VALUE",
            "SHIPPED_IS_LOWER_BOUND", "SHIPPED_PCT", "UNSHIPPED_VALUE", "STATUS", "SEVERITY", "FLAGS", "BL_LIST"])
        return recon, link

    # ───────────────────────── چرخه کامل ثبت سفارش ─────────────────────────
    # ─────────── ارز هر گام: ثبت سفارش، تخصیص، خرید، تعهد (بدون ادغام) ───────────
    @staticmethod
    def _currency_facts(ctx: PipelineContext, norm) -> Dict[str, Dict[str, str]]:
        """ارز تخصیص (فقط درخواست تخصیص‌یافته)، ارز خرید، ارز تعهد و ارز درخواست‌های رد یا
        باطل‌شده برای هر ثبت سفارش. این‌ها کنار ارز ثبت سفارش نمایش داده و مقایسه
        می‌شوند؛ هیچ‌کدام جای ارز ثبت سفارش نمی‌نشیند و مبلغشان با آن جمع نمی‌شود."""
        from ..finance.equivalents import _actual_purchase_rows
        facts: Dict[str, Dict[str, str]] = {}

        def put(reg: Any, field: str, values) -> None:
            reg = _s(reg)
            codes = sorted({c for c in (norm(v) for v in values) if c})
            if reg and codes:
                facts.setdefault(reg, {})[field] = "، ".join(codes)

        al = ctx.sheet("ntsw", "allocation_rows")
        if al is not None and not al.empty and KEY_REG in al.columns and "NTSW_REQUEST_STATE" in al.columns:
            for reg, g in al.groupby(al[KEY_REG].map(_s)):
                state = g["NTSW_REQUEST_STATE"].map(_s)
                put(reg, "ALLOC_CURRENCY", _col(g[state.eq("ALLOCATED")], "NTSW_REQ_CURRENCY"))
                put(reg, "OPEN_REQUEST_CURRENCY", _col(g[state.eq("OPEN")], "NTSW_REQ_CURRENCY"))
                put(reg, "REJECTED_REQUEST_CURRENCIES",
                    _col(g[state.isin(["REJECTED", "CLOSED"])], "NTSW_REQ_CURRENCY"))
        fx = _actual_purchase_rows(ctx.sheet("fx_transaction", "main"))
        if fx is not None and not fx.empty and KEY_REG in fx.columns:
            for reg, g in fx.groupby(fx[KEY_REG].map(_s)):
                put(reg, "PURCHASE_CURRENCY", _col(g, "FX_CURRENCY"))
        cm = ctx.sheet("ntsw", "commitment_by_currency")
        if cm is None or cm.empty:
            cm = ctx.sheet("ntsw", "commitment")
        if cm is not None and not cm.empty and KEY_REG in cm.columns:
            for reg, g in cm.groupby(cm[KEY_REG].map(_s)):
                put(reg, "COMMITMENT_CURRENCY", _col(g, "NTSW_CURRENCY"))
        return facts

    @staticmethod
    def _currency_check(reg_ccy: str, f: Dict[str, str]) -> List[str]:
        """مغایرت ارز میان گام‌ها؛ هرکدام فقط گزارش می‌شود و مبلغ‌ها هم‌ارز فرض نمی‌شوند."""
        def cs(key: str) -> set:
            return {x for x in f.get(key, "").split("، ") if x}

        alloc, buy, com = cs("ALLOC_CURRENCY"), cs("PURCHASE_CURRENCY"), cs("COMMITMENT_CURRENCY")
        txt = lambda xs: "، ".join(sorted(xs))
        out: List[str] = []
        if reg_ccy and alloc and alloc != {reg_ccy}:
            out.append(f"ارز تخصیص ({txt(alloc)}) با ارز ثبت سفارش ({reg_ccy}) یکی نیست")
        if buy and alloc and buy != alloc:
            out.append(f"ارز خرید ({txt(buy)}) با ارز تخصیص ({txt(alloc)}) یکی نیست")
        elif buy and not alloc and reg_ccy and buy != {reg_ccy}:
            out.append(f"ارز خرید ({txt(buy)}) با ارز ثبت سفارش ({reg_ccy}) یکی نیست")
        if com and alloc and com != alloc:
            out.append(f"ارز تعهد ({txt(com)}) با ارز تخصیص ({txt(alloc)}) یکی نیست")
        elif com and not alloc and reg_ccy and com != {reg_ccy}:
            out.append(f"ارز تعهد ({txt(com)}) با ارز ثبت سفارش ({reg_ccy}) یکی نیست")
        return out

    def _lifecycle(self, df: pd.DataFrame, ctx: PipelineContext, recon: pd.DataFrame,
                   currency_facts: Optional[Dict[str, Dict[str, str]]] = None) -> pd.DataFrame:
        tl = ctx.extras.get("fx_stage_timeline")
        tl = tl if isinstance(tl, pd.DataFrame) else pd.DataFrame()
        il = ctx.sheet("ilappend", "main")
        today = ctx.today
        regs = sorted(({_s(x) for x in _col(df, KEY_REG)} | set(recon.get("KEY_REG", []))) - {""})
        by_reg_tl = {r: g for r, g in tl.groupby("KEY_REG")} if not tl.empty and "KEY_REG" in tl.columns else {}
        il_by_reg: Dict[str, pd.DataFrame] = {}
        if il is not None and not il.empty and KEY_REG in il.columns:
            il_by_reg = {r: g for r, g in il.groupby(il[KEY_REG].map(_s)) if r}
        file_by_reg: Dict[str, str] = {}
        if "KEY_REG_FILE" in df.columns:
            for r, f in zip(_col(df, KEY_REG).map(_s), _col(df, "KEY_REG_FILE").map(_s)):
                if r and f:
                    file_by_reg.setdefault(r, f)
        recon_by = recon.set_index("KEY_REG") if not recon.empty else pd.DataFrame()
        rows: List[Dict[str, Any]] = []
        for reg in regs:
            rec: Dict[str, Any] = {"KEY_REG": reg}
            # ۱) پرونده ثبت سفارش — شاهد: شماره پرونده / ردیف ilappend
            ilg = il_by_reg.get(reg)
            file_no = file_by_reg.get(reg) or (_s(next((x for x in _col(ilg, "IL_FILE_NO") if _s(x)), "")) if ilg is not None else "")
            status_txt = ""
            if ilg is not None:
                # وضعیت آخرین اصلاحیه، نه ردیف اول فایل
                amend_no = _col(ilg, "IL_AMENDMENT_NO").map(lambda v: int(_s(v)) if _s(v).isdigit() else 0)
                latest = ilg.assign(_n=amend_no.values).sort_values("_n", kind="mergesort")
                status_txt = _s(next((x for x in reversed(_col(latest, "IL_STATUS").tolist()) if _s(x)), ""))
            amendments = len({_s(x) for x in _col(ilg, "IL_AMENDMENT_NO") if _s(x)}) if ilg is not None else 0
            rec["REG_FILE_NO"] = file_no
            rec["REG_FILE_STATUS"] = status_txt
            rec["REG_AMENDMENTS"] = amendments
            stages: Dict[str, Tuple[str, str, str]] = {
                "REG_FILE": ("DONE" if file_no else "EVIDENCE_GAP", "", file_no)}
            g = by_reg_tl.get(reg)
            if g is not None:
                for _, t in g.iterrows():
                    stages[_s(t.get("STAGE_CODE"))] = (_s(t.get("STATUS")), _s(t.get("EVENT_DATE")) or _s(t.get("DUE_DATE")),
                                                      _s(t.get("EVIDENCE")))
            done = 0
            last_done_idx = -1
            for i, (code, fa) in enumerate(LIFECYCLE):
                st, dt, ev = stages.get(code, ("", "", ""))
                rec[f"{code}__STATUS"] = STATUS_FA.get(st, st)
                rec[f"{code}__DATE"] = dt
                rec[f"{code}__EVIDENCE"] = ev
                if st == "DONE":
                    done += 1
                    last_done_idx = i
            # مرحله جاری = گام بعد از پیشرفته‌ترین گام انجام‌شده؛ گام‌های بی‌شاهدِ
            # پیش از آن «گام بدون شاهد» گزارش می‌شوند، نه مرحله جاری.
            gaps = [fa for code, fa in LIFECYCLE[:max(last_done_idx, 0)]
                    if stages.get(code, ("",))[0] != "DONE"]
            if last_done_idx == len(LIFECYCLE) - 1:
                current_code, current_fa = "", ""
            else:
                current_code, current_fa = LIFECYCLE[last_done_idx + 1]
            rec["DONE_COUNT"] = done
            rec["STAGE_COUNT"] = len(LIFECYCLE)
            rec["PROGRESS_PCT"] = round((last_done_idx + 1) / len(LIFECYCLE) * 100, 1)
            rec["CURRENT_STAGE_CODE"] = current_code or "CLOSED"
            rec["CURRENT_STAGE"] = current_fa or "بسته‌شده (رفع تعهد)"
            rec["CURRENT_STAGE_STATUS"] = STATUS_FA.get(stages.get(current_code, ("",))[0], "") if current_code else "انجام شد"
            rec["GAP_STAGES"] = " · ".join(gaps)
            # روزهای ماندن در مرحله جاری = امروز − آخرین تاریخ گام انجام‌شده
            last_done = None
            for code, _fa in LIFECYCLE[:last_done_idx + 1]:
                st, dt, _ = stages.get(code, ("", "", ""))
                d = CalendarEngine.parse(dt) if st == "DONE" and dt else None
                if d and (last_done is None or d > last_done):
                    last_done = d
            rec["CURRENT_STAGE_DAYS"] = (today - last_done).days if last_done and current_code else None
            if not recon_by.empty and reg in recon_by.index:
                rr = recon_by.loc[reg]
                for k in ("REG_VALUE", "REG_CURRENCY", "BL_COUNT", "SHIPPED_VALUE", "SHIPPED_PCT",
                          "UNSHIPPED_VALUE", "STATUS"):
                    rec[f"VALUE_{k}"] = rr[k]
            facts = (currency_facts or {}).get(reg, {})
            for k in ("ALLOC_CURRENCY", "OPEN_REQUEST_CURRENCY", "PURCHASE_CURRENCY", "COMMITMENT_CURRENCY",
                      "REJECTED_REQUEST_CURRENCIES"):
                rec[k] = facts.get(k, "")
            checks = self._currency_check(_s(rec.get("VALUE_REG_CURRENCY")), facts)
            rec["CURRENCY_CHECK"] = " · ".join(checks)
            rec["CURRENCY_MISMATCH"] = bool(checks)
            rows.append(rec)
        return pd.DataFrame(rows)

    # ─────────────────────────── صف تخصیص ارز ───────────────────────────
    def _allocation_queue(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        cols = ["KEY_REG", "QUEUE_STATE", "QUEUE_RANK", "QUEUE_ENTER_DATE", "WAIT_DAYS", "OPEN_AMOUNT",
                "CURRENCY", "REQUESTS_OPEN", "REQUESTS_ALLOCATED", "REQUESTS_REJECTED", "ORDERS",
                "CRITICAL_LEVEL", "CRITICAL_MATERIALS", "EXPERT", "WAIT_NOTE"]
        if df.empty or KEY_REG not in df.columns:
            return pd.DataFrame(columns=cols)
        rank = {"STOCKOUT": 0, "CRITICAL": 1, "BECOMING_CRITICAL": 2, "WATCH": 3, "SAFE": 4}
        rows = []
        for reg, g in df.groupby(df[KEY_REG].map(_s)):
            if not reg:
                continue
            state = _s(next((x for x in _col(g, "ALLOC_QUEUE_STATE") if _s(x)), ""))
            open_n = _num(next((x for x in _col(g, "OPEN_ALLOC_REQUESTS") if _num(x) is not None), None)) or 0
            if state not in ("IN_QUEUE", "OPEN", "PENDING") and open_n <= 0:
                continue
            enter = _s(next((x for x in _col(g, "ALLOC_QUEUE_ENTER_DATE") if _s(x)), "")) or \
                _s(next((x for x in _col(g, "NTSW_REQ_DATE") if _s(x)), ""))
            d = CalendarEngine.parse(enter) if enter else None
            levels = [_s(x) for x in _col(g, "ORDER_CRITICAL_LEVEL") if _s(x) in rank]
            level = min(levels, key=lambda x: rank[x]) if levels else ""
            crit_mats = sorted({_s(x) for x in _col(g, "ORDER_CRITICAL_MATERIALS") if _s(x)})
            # ورود بعد از تاریخ مرجع: انتظار منفی معنا ندارد ← نامعلوم با توضیح (نه صفر)
            wait = (ctx.today - d).days if d else None
            note = ""
            if wait is not None and wait < 0:
                wait, note = None, "ورود به صف بعد از تاریخ مرجع"
            rows.append({
                "KEY_REG": reg, "QUEUE_STATE": state or "OPEN",
                "QUEUE_RANK": _num(next((x for x in _col(g, "ALLOC_QUEUE_RANK") if _num(x) is not None), None)),
                "QUEUE_ENTER_DATE": d.isoformat() if d else enter,
                "WAIT_DAYS": wait, "WAIT_NOTE": note,
                "OPEN_AMOUNT": _num(next((x for x in _col(g, "OPEN_QUEUE_AMOUNT") if _num(x) is not None), None)),
                # ارز همان مبلغ باز، فقط از درخواست‌های باز؛ نه از درخواست رد یا باطل‌شده
                # و نه از درخواست تخصیص‌یافته‌ای که ارز دیگری دارد
                "CURRENCY": _s(next((x for c in ("OPEN_QUEUE_CURRENCY", "NTSW_OPEN_CURRENCY")
                                     for x in _col(g, c) if _s(x)), "")),
                "REQUESTS_OPEN": int(open_n),
                "REQUESTS_ALLOCATED": int(_num(next((x for x in _col(g, "ALLOCATED_REQUESTS") if _num(x) is not None), 0)) or 0),
                "REQUESTS_REJECTED": int(_num(next((x for x in _col(g, "REJECTED_ALLOC_REQUESTS") if _num(x) is not None), 0)) or 0),
                "ORDERS": "، ".join(sorted({_s(x) for x in _col(g, "KEY_ORDER") if _s(x)})),
                "CRITICAL_LEVEL": level, "CRITICAL_MATERIALS": " · ".join(crit_mats),
                "EXPERT": _s(next((x for x in _col(g, "EXPERT_CREDIT") if _s(x)), "")) or
                          _s(next((x for x in _col(g, "CANONICAL_EXPERT") if _s(x)), "")),
            })
        out = pd.DataFrame(rows, columns=cols)
        if not out.empty:
            out["_crit"] = out["CRITICAL_LEVEL"].map(lambda x: rank.get(x, 9))
            out = out.sort_values(["_crit", "WAIT_DAYS"], ascending=[True, False], na_position="last").drop(columns="_crit")
        return out.reset_index(drop=True)

    # ──────────────────────── نوشتن ستون‌های مارت ────────────────────────
    def _write_columns(self, df: pd.DataFrame, link: pd.DataFrame, recon: pd.DataFrame,
                       lifecycle: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        bl = (_col(df, "CANONICAL_BL") if "CANONICAL_BL" in df.columns else _col(df, "KEY_BL")).map(_s)
        reg = _col(df, KEY_REG).map(_s)
        lk = {(r["KEY_BL"], r["KEY_REG"]): r for _, r in link.iterrows()} if not link.empty else {}
        rc = {r["KEY_REG"]: r for _, r in recon.iterrows()} if not recon.empty else {}
        lc = {r["KEY_REG"]: r for _, r in lifecycle.iterrows()} if not lifecycle.empty else {}

        def pick(src, key, field, default=None):
            row = src.get(key)
            if row is None:
                return default
            v = row.get(field, default)
            return default if v is None or (isinstance(v, float) and math.isnan(v)) else v

        keys = list(zip(bl, reg))
        df["BLREG_BL_INVOICE_VALUE"] = [pick(lk, k, "BL_INVOICE_VALUE") for k in keys]
        df["BLREG_BL_CURRENCY"] = [pick(lk, k, "BL_CURRENCY", "") for k in keys]
        df["BLREG_BL_VALUE_BASIS"] = [pick(lk, k, "BL_VALUE_BASIS", "") for k in keys]
        df["BLREG_BL_SHARE_PCT"] = [pick(lk, k, "SHARE_PCT") for k in keys]
        df["BLREG_REG_VALUE"] = [pick(rc, r, "REG_VALUE") for r in reg]
        df["BLREG_REG_CURRENCY"] = [pick(rc, r, "REG_CURRENCY", "") for r in reg]
        df["BLREG_REG_VALUE_BASIS"] = [pick(rc, r, "REG_VALUE_BASIS", "") for r in reg]
        df["BLREG_REG_BL_COUNT"] = [pick(rc, r, "BL_COUNT") for r in reg]
        df["BLREG_REG_SHIPPED_VALUE"] = [pick(rc, r, "SHIPPED_VALUE") for r in reg]
        df["BLREG_REG_SHIPPED_PCT"] = [pick(rc, r, "SHIPPED_PCT") for r in reg]
        df["BLREG_REG_UNSHIPPED_VALUE"] = [pick(rc, r, "UNSHIPPED_VALUE") for r in reg]

        def status(b, r):
            if b and not r:
                return ST_NO_REG
            return pick(rc, r, "STATUS", "") if r else ""
        df["BLREG_STATUS"] = [status(b, r) for b, r in keys]
        df["BLREG_FLAGS"] = [" · ".join(x for x in (pick(lk, (b, r), "FLAGS", ""), pick(rc, r, "FLAGS", "")) if x)
                             for b, r in keys]
        df["LIFECYCLE_STAGE"] = [pick(lc, r, "CURRENT_STAGE", "") for r in reg]
        df["LIFECYCLE_STAGE_DAYS"] = [pick(lc, r, "CURRENT_STAGE_DAYS") for r in reg]
        df["LIFECYCLE_DONE_COUNT"] = [pick(lc, r, "DONE_COUNT") for r in reg]
        df["LIFECYCLE_GAPS"] = [pick(lc, r, "GAP_STAGES", "") for r in reg]
        for c in ("BLREG_BL_INVOICE_VALUE", "BLREG_BL_SHARE_PCT", "BLREG_REG_VALUE", "BLREG_REG_BL_COUNT",
                  "BLREG_REG_SHIPPED_VALUE", "BLREG_REG_SHIPPED_PCT", "BLREG_REG_UNSHIPPED_VALUE",
                  "LIFECYCLE_STAGE_DAYS", "LIFECYCLE_DONE_COUNT"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    # ─────────────────────────── گزارش ───────────────────────────
    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("LIFECYCLE_STAGE", "مرحله جاری چرخه ارز", 20, GROUP_DETAIL, order=72),
            ColumnSpec("LIFECYCLE_STAGE_DAYS", "روز در مرحله جاری", 14, GROUP_DETAIL, fmt=FMT_INT,
                       order=72, color_rule="scale_high_bad"),
            ColumnSpec("LIFECYCLE_GAPS", "گام‌های بدون شاهد چرخه ارز", 36, GROUP_ANALYTIC, wrap=True,
                       order=109, color_rule="flag_nonempty"),
            ColumnSpec("BLREG_BL_INVOICE_VALUE", "ارزش فاکتور بارنامه", 18, GROUP_DETAIL, fmt=FMT_CURRENCY, order=73),
            ColumnSpec("BLREG_BL_CURRENCY", "ارز بارنامه", 10, GROUP_DETAIL, order=73),
            ColumnSpec("BLREG_REG_VALUE", "ارزش ثبت سفارش", 18, GROUP_DETAIL, fmt=FMT_CURRENCY, order=74),
            ColumnSpec("BLREG_REG_CURRENCY", "ارز ثبت سفارش", 10, GROUP_DETAIL, order=74),
            ColumnSpec("BLREG_BL_SHARE_PCT", "سهم بارنامه از ثبت سفارش (٪)", 14, GROUP_DETAIL,
                       fmt=FMT_DECIMAL, order=75),
            ColumnSpec("BLREG_REG_SHIPPED_PCT", "حمل‌شده از ثبت سفارش (٪)", 14, GROUP_DETAIL,
                       fmt=FMT_DECIMAL, order=75),
            ColumnSpec("BLREG_REG_UNSHIPPED_VALUE", "مانده حمل‌نشده ثبت سفارش", 18, GROUP_DETAIL,
                       fmt=FMT_CURRENCY, order=76),
            ColumnSpec("BLREG_STATUS", "وضعیت پیوند بارنامه/ثبت سفارش", 22, GROUP_DETAIL, order=76,
                       color_rule="flag_nonempty"),
            ColumnSpec("BLREG_REG_VALUE_BASIS", "مبنای ارزش ثبت سفارش", 28, GROUP_ANALYTIC, wrap=True, order=108),
            ColumnSpec("BLREG_BL_VALUE_BASIS", "مبنای ارزش بارنامه", 22, GROUP_ANALYTIC, order=108),
            ColumnSpec("BLREG_FLAGS", "مغایرت پیوند بارنامه/ثبت سفارش", 48, GROUP_ANALYTIC, wrap=True,
                       order=109, color_rule="flag_nonempty"),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        recon = ctx.extras.get("registration_value_recon")
        queue = ctx.extras.get("allocation_queue")
        if not isinstance(recon, pd.DataFrame) or recon.empty:
            return {}
        risky = int(recon["STATUS"].isin([ST_OVER, ST_CCY_MISMATCH]).sum())
        unknown = int(recon["STATUS"].eq(ST_REG_UNKNOWN).sum())
        return {
            "ثبت سفارش با مغایرت حمل/ارز": (risky, "حمل بیش از ارزش ثبت سفارش یا ارز بارنامه متفاوت"),
            "ثبت سفارش با ارزش نامعلوم": (unknown, "ارزش پروفرم/تعهد در هیچ منبعی نیست"),
            "پرونده در صف تخصیص": (0 if not isinstance(queue, pd.DataFrame) else len(queue),
                                  "درخواست تخصیص باز در NTSW"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {
            "پیوند مبلغی بارنامه ↔ ثبت سفارش": {
                "فرمول": "حمل‌شده(REG) = Σ ارزش فاکتور بارنامه‌های تک‌ثبت‌سفارشی هم‌ارز با ارز REG "
                         "(ارز نامعلوم هم‌ارز هیچ ارزی نیست)؛ "
                         "مانده = ارزش REG − حمل‌شده؛ درصد = حمل‌شده ÷ ارزش REG",
                "پارامترها": f"تلورانس حمل کامل/بیش از حد = {TOLERANCE * 100:.1f}٪؛ "
                              f"تلورانس اختلاف ساتا/گمرک = {SOURCE_TOLERANCE * 100:.0f}٪",
                "مبنا": "ارزش و ارز REG: ایمپورت لایسنس NTSW ← IL Append (آخرین اصلاحیه) ← پروفرم اعتبارات "
                        "← جمع PI سفارش‌ها (فقط برآورد). درخواست تخصیص و تعهد NTSW هرگز مبنای ارز ثبت سفارش "
                        "نیستند و درخواست رد یا باطل‌شده ارزی تعیین نمی‌کند؛ ارز تخصیص، خرید یا تعهد اگر فرق "
                        "داشته باشد در «مغایرت ارز گام‌ها» گزارش می‌شود و مبلغ‌ها هم‌ارز فرض نمی‌شوند. "
                        "بارنامه چندثبت‌سفارشی، ارزش نامعلوم و ارز نامعلوم در جمع نمی‌آیند و جمع «حداقل» "
                        "علامت می‌خورد؛ اگر ارز ثبت سفارش نامعلوم باشد حمل‌شده و مانده نامعلوم است. "
                        "تعارض ارزش فاکتور ساتا با ارزش گمرک جایگزین نمی‌شود.",
            }
        }
