# -*- coding: utf-8 -*-
"""موتور روایت داده و تحلیل فرآیند — از «چه شد» به «پس چه کنیم».

## مسئله‌ای که حل می‌کند

نسخه قبلی یک تابع ``story()`` داخل جاوااسکریپت HTML داشت که سه جمله
می‌ساخت: تعداد بحرانی، کمترین مقاومت، بزرگ‌ترین گلوگاه. سه عدد درست، ولی
یک روایت نبود — چون به سه سؤالی که تصمیم‌گیرنده واقعاً می‌پرسد جواب نمی‌داد:

    نسبت به دیروز بهتر شدیم یا بدتر؟      ← بدون مقایسه، هر عدد بی‌معناست
    این عدد چقدر غیرعادی است؟              ← «۵۴ بحرانی» زیاد است یا کم؟
    فردا صبح دقیقاً روی چه چیزی کار کنم؟   ← بدون موضوع مشخص، گزارش بایگانی می‌شود

## ساختار روایت

از الگوی هرم مینتو (Situation → Complication → Resolution) استفاده می‌شود،
چون همان ساختاری است که مدیر در جلسه انتظار دارد:

    وضعیت    اندازه و شکل سبد امروز — زمینه‌ای که بقیه اعداد در آن معنا دارند
    گره      چه چیزی از حالت عادی خارج شده و به چه میزان
    اقدام    مشخص‌ترین موضوع قابل‌اقدام، با نام قطعه/سفارش و عدد

هر یافته (:class:`Finding`) سه جزء اجباری دارد: **بزرگی**، **مقایسه** و
**پس چه**. یافته‌ای که «پس چه» ندارد ساخته نمی‌شود — همان قاعده‌ای که مانع
تبدیل گزارش به فهرست اعداد می‌شود.

## تحلیل فرآیند

معیارها عمداً از ادبیات روز فرآیندکاوی و Lean گرفته شده‌اند، نه از میانگین
ساده:

* **میانه و صدک ۹۰** به‌جای میانگین. توزیع زمان چرخه در زنجیره تأمین
  راست‌چوله است؛ میانگین را چند پرونده‌ی گیرکرده جابه‌جا می‌کند و مدیر را
  به جای اشتباه می‌فرستد.
* **تمرکز واریانت** — سهم پرتکرارترین مسیرها از کل پرونده‌ها. شاخص
  استانداردسازی فرآیند: عدد پایین یعنی فرآیند عملاً هر بار از نو اختراع
  می‌شود.
* **نرخ دوباره‌کاری** — پرونده‌هایی که یک فعالیت را بیش از یک بار ثبت
  کرده‌اند. این هزینه‌ی پنهانی است که در نقشه فرآیند دیده نمی‌شود.
* **کارایی جریان (Flow Efficiency)** — نسبت زمان مؤثر به کل زمان چرخه.
  در زنجیره تأمین وارداتی معمولاً زیر ۲۰٪ است و همان‌جاست که پول می‌سوزد.
* **قانون لیتل** — ``WIP = نرخ ورود × زمان چرخه``. برای اعتبارسنجی متقابل
  ظرفیت: اگر عدد مشاهده‌شده با آن نخواند، یا لاگ ناقص است یا ظرفیت گلوگاه.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from .design_system import STATUS

#: طبقه‌هایی که «بحرانی» شمرده می‌شوند — هم کد لاتین و هم برچسب فارسی،
#: چون بسته به مسیر گزارش هر دو ممکن است در ستون بنشیند.
CRITICAL_TOKENS = ("STOCKOUT", "CRITICAL", "توقف خط", "بحرانی")
STOP_TOKENS = ("STOCKOUT", "توقف خط")


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _first_col(df: pd.DataFrame, names: Sequence[str]) -> Optional[str]:
    return next((c for c in names if c in df.columns), None)


def _nunique(df: pd.DataFrame, col: str, mask=None) -> int:
    if col not in df.columns:
        return 0
    s = df[col] if mask is None else df.loc[mask, col]
    return int(s.replace("", pd.NA).nunique())


def _fa_num(value: Any, digits: int = 0) -> str:
    """عدد با جداکننده هزارگان. فارسی‌سازی رقم در لایه نمایش انجام می‌شود."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if digits <= 0:
        return f"{v:,.0f}"
    return f"{v:,.{digits}f}"


@dataclass
class Finding:
    """یک یافته قابل‌اقدام.

    سه جزء اجباری: ``magnitude`` (بزرگی)، ``comparison`` (نسبت به چه) و
    ``so_what`` (پس چه). یافته بدون «پس چه» ساخته نمی‌شود.
    """
    key: str
    headline: str
    magnitude: str
    comparison: str
    so_what: str
    tone: str = "neutral"          # کلید پالت وضعیت
    focus: str = ""                # موضوع مشخص برای اقدام (قطعه/سفارش/گذار)
    metric: float = 0.0
    delta: Optional[float] = None  # تغییر نسبت به snapshot قبلی

    @property
    def color(self) -> str:
        return STATUS.get(self.tone, STATUS["neutral"]).ink

    def as_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "headline": self.headline, "magnitude": self.magnitude,
                "comparison": self.comparison, "so_what": self.so_what, "tone": self.tone,
                "focus": self.focus, "metric": self.metric, "delta": self.delta,
                "color": self.color}


@dataclass
class Story:
    """روایت کامل یک برش داده."""
    headline: str = ""
    situation: str = ""
    complication: str = ""
    resolution: str = ""
    findings: List[Finding] = field(default_factory=list)
    process: Dict[str, Any] = field(default_factory=dict)
    trend: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"headline": self.headline, "situation": self.situation,
                "complication": self.complication, "resolution": self.resolution,
                "findings": [f.as_dict() for f in self.findings],
                "process": self.process, "trend": self.trend}


# ── تحلیل فرآیند ──────────────────────────────────────────────────────────
def process_metrics(extras: Optional[Dict[str, Any]] = None,
                    df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """معیارهای فرآیند از لاگ رویداد؛ با افت نرم به «مرحله فعلی».

    وقتی Event Log هنوز عمق تاریخی ندارد (روزهای اول استقرار)، هیچ عدد
    فرضی ساخته نمی‌شود: ``basis`` روی ``"stage"`` می‌رود و مصرف‌کننده
    می‌داند که نمای جایگزین می‌بیند.
    """
    extras = extras or {}
    out: Dict[str, Any] = {"basis": "empty", "cases": 0, "bottleneck": None,
                           "cycle_median": None, "cycle_p90": None,
                           "variant_concentration": None, "variant_count": 0,
                           "rework_rate": None, "flow_efficiency": None,
                           "wip_littles_law": None, "top_variants": [],
                           "bottlenecks": []}

    ev = extras.get("eventlog")
    if isinstance(ev, pd.DataFrame) and not ev.empty:
        case_col = _first_col(ev, ["_CASE_KEY", "CASE_KEY"])
        act_col = _first_col(ev, ["ACTIVITY_FA", "ACTIVITY_EN", "ACTIVITY"])
        if case_col and act_col and "EVENTTIME" in ev.columns:
            e = ev[[case_col, act_col, "EVENTTIME"]].copy()
            e.columns = ["case", "activity", "t"]
            e["t"] = pd.to_datetime(e["t"], errors="coerce")
            e = e.dropna(subset=["case", "activity", "t"]).sort_values(["case", "t"])
            if not e.empty:
                out["basis"] = "eventlog"
                out["cases"] = int(e["case"].nunique())

                # زمان چرخه — میانه و صدک ۹۰، نه میانگین
                span = e.groupby("case")["t"].agg(["min", "max"])
                cycle = (span["max"] - span["min"]).dt.total_seconds() / 86400.0
                cycle = cycle[cycle >= 0]
                if not cycle.empty:
                    out["cycle_median"] = round(float(cycle.median()), 2)
                    out["cycle_p90"] = round(float(cycle.quantile(0.9)), 2)

                # گذارها و انتظار بین فعالیت‌ها
                e["next_act"] = e.groupby("case")["activity"].shift(-1)
                e["next_t"] = e.groupby("case")["t"].shift(-1)
                tr = e.dropna(subset=["next_act", "next_t"]).copy()
                tr["wait"] = (tr["next_t"] - tr["t"]).dt.total_seconds() / 86400.0
                tr = tr[tr["wait"] >= 0]
                if not tr.empty:
                    agg = (tr.groupby(["activity", "next_act"])
                             .agg(median_days=("wait", "median"),
                                  p90_days=("wait", lambda s: s.quantile(0.9)),
                                  cases=("case", "nunique"),
                                  total_days=("wait", "sum"))
                             .reset_index()
                             .sort_values("total_days", ascending=False))
                    out["bottlenecks"] = [
                        {"from": str(r["activity"]), "to": str(r["next_act"]),
                         "median_days": round(float(r["median_days"]), 2),
                         "p90_days": round(float(r["p90_days"]), 2),
                         "cases": int(r["cases"]),
                         "total_days": round(float(r["total_days"]), 1)}
                        for _, r in agg.head(12).iterrows()]
                    if out["bottlenecks"]:
                        out["bottleneck"] = out["bottlenecks"][0]
                    # کارایی جریان: گذار «مؤثر» آن است که زیر میانه کل بماند؛
                    # انتظارهای بلندتر از آن، زمان تلف‌شده تلقی می‌شود.
                    total = float(tr["wait"].sum())
                    if total > 0:
                        cut = float(tr["wait"].median())
                        effective = float(tr.loc[tr["wait"] <= cut, "wait"].sum())
                        out["flow_efficiency"] = round(100.0 * effective / total, 1)

                # دوباره‌کاری: پرونده‌ای که یک فعالیت را بیش از یک بار دارد
                per_case = e.groupby(["case", "activity"]).size()
                rework_cases = per_case[per_case > 1].index.get_level_values(0).nunique()
                out["rework_rate"] = round(100.0 * rework_cases / max(out["cases"], 1), 1)

                # تمرکز واریانت — شاخص استانداردسازی فرآیند
                variants = (e.groupby("case")["activity"]
                             .apply(lambda s: " ← ".join(s.astype(str)))
                             .value_counts())
                out["variant_count"] = int(len(variants))
                top = variants.head(5)
                out["variant_concentration"] = round(
                    100.0 * float(top.sum()) / max(out["cases"], 1), 1)
                out["top_variants"] = [{"path": str(k), "cases": int(v),
                                        "share": round(100.0 * v / max(out["cases"], 1), 1)}
                                       for k, v in top.items()]

                # قانون لیتل — اعتبارسنجی متقابل ظرفیت
                horizon = (span["max"].max() - span["min"].min()).total_seconds() / 86400.0
                if horizon > 0 and out["cycle_median"]:
                    arrival = out["cases"] / horizon
                    out["wip_littles_law"] = round(arrival * out["cycle_median"], 1)
                return out

    # افت نرم: جدول گلوگاه از پیش محاسبه‌شده
    bt = extras.get("bottlenecks")
    if isinstance(bt, pd.DataFrame) and not bt.empty and {"از فعالیت", "به فعالیت"} <= set(bt.columns):
        val = next((c for c in bt.columns if "میانگین" in str(c)), None)
        if val:
            b = bt.sort_values(val, ascending=False).head(12)
            out["basis"] = "bottleneck_table"
            out["bottlenecks"] = [
                {"from": str(r["از فعالیت"]), "to": str(r["به فعالیت"]),
                 "median_days": round(float(pd.to_numeric(r[val], errors="coerce") or 0), 2),
                 "p90_days": None,
                 "cases": int(pd.to_numeric(r.get("تعداد پرونده", 0), errors="coerce") or 0),
                 "total_days": None}
                for _, r in b.iterrows()]
            out["bottleneck"] = out["bottlenecks"][0]
            return out

    # آخرین افت: توزیع مرحله فعلی — هیچ گلوگاه فرضی ساخته نمی‌شود
    if df is not None and not df.empty:
        stage = _first_col(df, ["STAGE_FA", "ORDER_STAGE_FA", "LIFECYCLE_STAGE"])
        if stage:
            vc = df[stage].fillna("").astype(str).replace("", "نامشخص").value_counts()
            if len(vc):
                out["basis"] = "stage"
                out["cases"] = int(len(df))
                out["stage_distribution"] = [{"stage": str(k), "cases": int(v)}
                                             for k, v in vc.head(12).items()]
    return out


# ── روند ──────────────────────────────────────────────────────────────────
#: KPIهایی که روند آن‌ها معنا دارد، با جهت «بهتر» هر کدام.
TREND_METRICS: Dict[str, Dict[str, Any]] = {
    "متریال بحرانی":   {"better": "down", "unit": "قطعه", "tone_bad": "critical"},
    "متریال توقف خط":  {"better": "down", "unit": "قطعه", "tone_bad": "stockout"},
    "مانده تعهد معوق": {"better": "down", "unit": "ارز", "tone_bad": "serious"},
    "میانگین مقاومت":  {"better": "up", "unit": "روز", "tone_bad": "warning"},
    "میانگین رسوب":    {"better": "down", "unit": "روز", "tone_bad": "warning"},
}


def trend_series(history: Optional[pd.DataFrame], limit: int = 30) -> Dict[str, Any]:
    """سری زمانی KPI برای نمودار روند و مقایسه با دوره قبل.

    ورودی جدول تاریخچه :mod:`aibl.report.history` است. نبودِ تاریخچه خطا
    نیست — روز اول استقرار هیچ گذشته‌ای وجود ندارد — و خروجی خالی برمی‌گردد.
    """
    out: Dict[str, Any] = {"dates": [], "series": {}, "deltas": {}, "points": 0}
    if history is None or getattr(history, "empty", True) or "تاریخ" not in history.columns:
        return out
    h = history.copy()
    h["تاریخ"] = h["تاریخ"].astype(str)
    h = h.drop_duplicates("تاریخ", keep="last").sort_values("تاریخ").tail(limit)
    out["dates"] = [str(x) for x in h["تاریخ"]]
    out["points"] = len(h)
    for metric, meta in TREND_METRICS.items():
        if metric not in h.columns:
            continue
        vals = pd.to_numeric(h[metric], errors="coerce")
        if vals.notna().sum() < 1:
            continue
        series = [None if pd.isna(v) else round(float(v), 2) for v in vals]
        out["series"][metric] = series
        clean = vals.dropna()
        if len(clean) >= 2:
            last, prev = float(clean.iloc[-1]), float(clean.iloc[-2])
            change = last - prev
            pct = (change / abs(prev) * 100.0) if prev else None
            improving = (change < 0) if meta["better"] == "down" else (change > 0)
            out["deltas"][metric] = {
                "last": round(last, 2), "prev": round(prev, 2),
                "change": round(change, 2),
                "pct": None if pct is None else round(pct, 1),
                "improving": bool(improving) if change else None,
                "better": meta["better"], "unit": meta["unit"],
            }
    return out


def load_history(limit: int = 30) -> Dict[str, Any]:
    """تاریخچه ذخیره‌شده را می‌خواند؛ اگر نبود، خالی برمی‌گرداند."""
    try:
        from .history import _path
        p = _path()
        if not p.exists():
            return trend_series(None, limit)
        return trend_series(pd.read_csv(p, encoding="utf-8-sig"), limit)
    except Exception:
        return trend_series(None, limit)


# ── ساخت روایت ────────────────────────────────────────────────────────────
def _band_series(df: pd.DataFrame) -> pd.Series:
    col = _first_col(df, ["بحرانی (کوتاه)", "کد طبقه بحرانی"])
    if not col:
        return pd.Series(dtype=str)
    return df[col].fillna("").astype(str)


def _delta_phrase(delta: Optional[Dict[str, Any]]) -> str:
    """جمله مقایسه با اجرای قبلی — بدون تاریخچه، صریح می‌گوید که ندارد."""
    if not delta:
        return "مبنای مقایسه با اجرای قبلی هنوز ثبت نشده است."
    change, pct = delta["change"], delta.get("pct")
    if change == 0:
        return "نسبت به اجرای قبلی بدون تغییر."
    word = "بهبود" if delta.get("improving") else "بدتر شدن"
    size = f"{abs(change):,.1f}".rstrip("0").rstrip(".")
    pct_txt = f" ({abs(pct):.0f}٪)" if pct else ""
    return f"نسبت به اجرای قبلی {size}{pct_txt} {word}."


def build_story(df: pd.DataFrame, extras: Optional[Dict[str, Any]] = None,
                trend: Optional[Dict[str, Any]] = None,
                ref_date: str = "") -> Story:
    """روایت کامل یک برش: وضعیت، گره، اقدام و یافته‌های کمّی."""
    extras = extras or {}
    trend = trend if trend is not None else {"deltas": {}, "series": {}, "points": 0}
    deltas = trend.get("deltas") or {}
    st = Story()
    rows = len(df)

    if rows == 0:
        st.headline = "این برش خالی است."
        st.situation = "هیچ ردیفی با فیلترهای فعلی باقی نمانده است."
        st.complication = "بدون داده، هیچ نتیجه‌ای قابل استناد نیست."
        st.resolution = "یک فیلتر را بردارید یا بازه تاریخ را بازتر کنید."
        return st

    band = _band_series(df)
    crit_mask = band.isin(CRITICAL_TOKENS) if not band.empty else pd.Series(False, index=df.index)
    stop_mask = band.isin(STOP_TOKENS) if not band.empty else pd.Series(False, index=df.index)
    mat_col = "KEY_MATERIAL" if "KEY_MATERIAL" in df.columns else None
    crit_mat = _nunique(df, mat_col, crit_mask) if mat_col else int(crit_mask.sum())
    stop_mat = _nunique(df, mat_col, stop_mask) if mat_col else int(stop_mask.sum())
    total_mat = _nunique(df, mat_col) if mat_col else rows
    crit_share = 100.0 * crit_mat / max(total_mat, 1)

    orders = _nunique(df, "CANONICAL_ORDER")
    bls = _nunique(df, "CANONICAL_BL")

    # ── وضعیت ──
    parts = [f"{_fa_num(rows)} ردیف"]
    if total_mat:
        parts.append(f"{_fa_num(total_mat)} قطعه یکتا")
    if orders:
        parts.append(f"{_fa_num(orders)} سفارش")
    if bls:
        parts.append(f"{_fa_num(bls)} بارنامه")
    st.situation = "این برش شامل " + "، ".join(parts) + " است" + (
        f" و تاریخ مرجع آن {ref_date} است." if ref_date else ".")

    # ── یافته ۱: ریسک توقف خط ──
    if total_mat:
        d = deltas.get("متریال بحرانی")
        tone = "stockout" if stop_mat else ("critical" if crit_mat else "good")
        if crit_mat:
            focus = ""
            if mat_col and "مقاومت (روز)" in df.columns:
                sub = df.loc[crit_mask, [mat_col, "مقاومت (روز)"]].copy()
                sub["مقاومت (روز)"] = pd.to_numeric(sub["مقاومت (روز)"], errors="coerce")
                sub = sub.dropna().sort_values("مقاومت (روز)")
                if not sub.empty:
                    focus = str(sub.iloc[0][mat_col])
            st.findings.append(Finding(
                key="critical_parts",
                headline="ریسک توقف خط",
                magnitude=f"{_fa_num(crit_mat)} قطعه بحرانی، شامل {_fa_num(stop_mat)} قطعه در توقف خط",
                comparison=f"{crit_share:.1f}٪ از {_fa_num(total_mat)} قطعه این برش — " + _delta_phrase(d),
                so_what=("پیگیری امروز از کم‌مقاومت‌ترین قطعه شروع شود"
                         + (f": {focus}" if focus else "") + "."),
                tone=tone, focus=focus, metric=float(crit_mat),
                delta=(d or {}).get("change")))
        else:
            st.findings.append(Finding(
                key="critical_parts", headline="ریسک توقف خط",
                magnitude="هیچ قطعه بحرانی در این برش نیست",
                comparison=f"از {_fa_num(total_mat)} قطعه — " + _delta_phrase(d),
                so_what="ظرفیت پیگیری امروز را صرف تعهد معوق یا گلوگاه فرآیند کنید.",
                tone="good", metric=0.0, delta=(d or {}).get("change")))

    # ── یافته ۲: پوشش مقاومت ──
    res = _num(df, "مقاومت (روز)").dropna()
    if not res.empty:
        median_res = float(res.median())
        p10 = float(res.quantile(0.10))
        d = deltas.get("میانگین مقاومت")
        st.findings.append(Finding(
            key="resistance",
            headline="پوشش مقاومت",
            magnitude=f"میانه {_fa_num(median_res, 1)} روز؛ ضعیف‌ترین دهک زیر {_fa_num(p10, 1)} روز",
            comparison=("میانه به‌جای میانگین گزارش می‌شود چون توزیع مقاومت "
                        "راست‌چوله است — " + _delta_phrase(d)),
            so_what=(f"قطعاتی که زیر {_fa_num(p10, 1)} روز پوشش دارند، "
                     "پیش از رسیدن به طبقه بحرانی باید سفارش‌گذاری شوند."),
            tone="warning" if p10 < 10 else "good", metric=median_res,
            delta=(d or {}).get("change")))

    # ── یافته ۳: تعهد در معرض جریمه ──
    if "مانده تعهد" in df.columns:
        try:
            from ..studio_core.grain import safe_agg
            late = _num(df, "روزهای تأخیر").fillna(0)
            overdue_bal = safe_agg(df.loc[late > 0].copy(), "مانده تعهد", "sum")
            total_bal = safe_agg(df.copy(), "مانده تعهد", "sum")
        except Exception:
            overdue_bal = total_bal = 0.0
        if total_bal:
            share = 100.0 * overdue_bal / total_bal
            d = deltas.get("مانده تعهد معوق")
            worst = ""
            if "CANONICAL_ORDER" in df.columns and "روزهای تأخیر" in df.columns:
                late_rows = df.loc[_num(df, "روزهای تأخیر").fillna(0) > 0]
                if not late_rows.empty:
                    idx = _num(late_rows, "روزهای تأخیر").idxmax()
                    worst = str(late_rows.loc[idx, "CANONICAL_ORDER"])
            st.findings.append(Finding(
                key="commitment",
                headline="تعهد ارزی در معرض جریمه",
                magnitude=f"{_fa_num(overdue_bal)} از {_fa_num(total_bal)} مانده تعهد معوق است",
                comparison=f"{share:.1f}٪ از کل تعهد باز — " + _delta_phrase(d),
                so_what=("تمدید یا تسویه از دیرکردترین پرونده شروع شود"
                         + (f": {worst}" if worst else "") + "."),
                tone="serious" if share > 20 else ("warning" if share else "good"),
                focus=worst, metric=float(overdue_bal), delta=(d or {}).get("change")))

    # ── یافته ۴: تمرکز عملیاتی ──
    owner = _first_col(df, ["ORG_DEPT", "ORG_VICE", "CANONICAL_EXPERT"])
    if owner and rows:
        vc = df[owner].fillna("").astype(str).replace("", "نامشخص").value_counts()
        if len(vc) >= 2:
            top_share = 100.0 * int(vc.iloc[0]) / rows
            st.findings.append(Finding(
                key="workload",
                headline="تمرکز بار عملیاتی",
                magnitude=f"«{vc.index[0]}» با {_fa_num(int(vc.iloc[0]))} ردیف بیشترین بار را دارد",
                comparison=f"{top_share:.0f}٪ از بار این برش روی یک واحد از {len(vc)} واحد",
                so_what=("اگر این تمرکز عمدی نیست، توزیع مجدد پرونده‌ها "
                         "زمان انتظار را سریع‌تر از هر اقدام دیگری کم می‌کند."),
                tone="warning" if top_share > 45 else "neutral",
                focus=str(vc.index[0]), metric=top_share))

    # ── فرآیند ──
    pm = process_metrics(extras, df)
    st.process = pm
    if pm.get("bottleneck"):
        b = pm["bottleneck"]
        extra = ""
        if pm.get("rework_rate") is not None:
            extra = f" نرخ دوباره‌کاری {pm['rework_rate']}٪ است."
        st.findings.append(Finding(
            key="bottleneck",
            headline="گلوگاه فرآیند",
            magnitude=(f"«{b['from']} ← {b['to']}» با میانه {_fa_num(b['median_days'], 1)} روز انتظار"
                       + (f" و صدک ۹۰ برابر {_fa_num(b['p90_days'], 1)} روز" if b.get("p90_days") else "")),
            comparison=(f"روی {_fa_num(b['cases'])} پرونده"
                        + (f"؛ میانه زمان چرخه کل {_fa_num(pm['cycle_median'], 1)} روز" if pm.get("cycle_median") else "")
                        + extra),
            so_what=("کوتاه‌کردن همین یک گذار بیشترین اثر را بر زمان چرخه دارد؛ "
                     "صدک ۹۰ نشان می‌دهد دم توزیع چقدر بلند است."),
            tone="serious", focus=f"{b['from']} ← {b['to']}",
            metric=float(b["median_days"] or 0)))
    elif pm.get("basis") == "stage":
        st.findings.append(Finding(
            key="bottleneck", headline="نقطه شروع فرآیند",
            magnitude="لاگ گذار هنوز برای اندازه‌گیری انتظار کافی نیست",
            comparison="به‌جای آن، توزیع مرحله فعلی پرونده‌ها نشان داده می‌شود",
            so_what=("با اجرای روزانه، Transition Log ساخته می‌شود و از آن پس "
                     "گلوگاه واقعی — نه حدس — قابل اندازه‌گیری است."),
            tone="neutral"))

    st.trend = trend

    # ── سرخط، گره و اقدام ──
    actionable = [f for f in st.findings if f.tone in ("stockout", "critical", "serious", "warning")]
    actionable.sort(key=lambda f: ("stockout", "critical", "serious", "warning").index(f.tone))
    if actionable:
        lead = actionable[0]
        st.headline = f"{lead.headline}: {lead.magnitude}"
        st.complication = f"{lead.magnitude} — {lead.comparison}"
        st.resolution = lead.so_what
        if len(actionable) > 1:
            st.resolution += f" سپس: {actionable[1].so_what}"
    else:
        st.headline = "هیچ ریسک فعالی در این برش دیده نمی‌شود."
        st.complication = "معیارهای بحرانی، تعهد و فرآیند همگی در محدوده امن‌اند."
        st.resolution = "این برش نیازی به اقدام فوری ندارد؛ بازه یا فیلتر را بازتر کنید."
    return st
