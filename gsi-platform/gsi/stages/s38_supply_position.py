# -*- coding: utf-8 -*-
"""مرحله ۳۸ — Supply Position Ledger.

V26.20 یک اصل بیزینسی را صریح می‌کند:

    موجودی قابل اتکا = Oracle(IKCO + SAPCO)
                      + Expert(نزد سازنده + در راه + گمرک)

سه bucket کارشناسی **مقدار اصلی عملیاتی** هستند و از وضعیت BL/گمرک استنتاج
نمی‌شوند. Oracle موجودی انبار و نیاز روزانه را می‌دهد. Missing با Zero یکی
نیست: اگر کارشناس مقدار یک bucket را نداده باشد، جمع قطعی ساخته نمی‌شود و فقط
«حداقل قابل اثبات» گزارش می‌گردد.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

import numpy as np

from ..core.text import is_empty_val
from ..dataio.logging_setup import log
from .base import (ColumnSpec, FMT_DECIMAL, GROUP_ANALYTIC, GROUP_DETAIL,
                   GROUP_MAIN, PipelineContext, Stage, register)


def _present(v: Any) -> bool:
    return not is_empty_val(v, treat_zero_as_empty=False)


def _num_or_none(v: Any):
    if not _present(v):
        return None
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace(",", "").strip())
        except Exception:
            return None


def _numeric_or_nan(s: pd.Series) -> pd.Series:
    """معادل برداریِ :func:`_num_or_none` روی یک ستون کامل.

    ## چرا برداری

    نسخه قبلی این مرحله ``df.to_dict("records")`` می‌گرفت و ردیف‌به‌ردیف در
    پایتون حلقه می‌زد: به ازای هر ردیف یک dict و پنج فراخوانی تابع.

    ## چرا با factorize، نه با بازنویسی منطق

    وسوسه این است که ``_num_or_none`` با زنجیره‌ای از ``.str`` بازنویسی
    شود. آن راه یک تله دارد: ``float("۱۲۳")`` در پایتون کار می‌کند (هر رقم
    دهدهیِ یونیکد را می‌پذیرد) ولی ``pd.to_numeric("۱۲۳")`` نه — و در این
    پکیج عدد فارسی‌نویس در فایل مبدأ کاملاً عادی است. یعنی یک بازنویسی
    «معادل به‌نظر»، بی‌صدا هر عدد فارسی را «نامشخص» می‌کرد.

    پس منطق **بازنویسی نمی‌شود**. ستون به مقادیر یکتا تجزیه می‌شود و همان
    ``_num_or_none`` روی یکتاها اجرا می‌گردد. ستون موجودی با ۲۰۰ هزار ردیف
    معمولاً چند هزار مقدار یکتا دارد، پس کار پایتونی چند ده برابر کم می‌شود
    و تعریف معنا **یکی** می‌ماند — نه دو نسخه که با هم فرق کنند.

    ## قاعده‌ای که نباید بشکند

    ``Missing`` با ``Zero`` یکی نیست. خروجی برای سلول «نامشخص» ``NaN`` است،
    نه ``0`` — دقیقاً مثل ``None`` در نسخه قبلی. اگر این تمایز از بین برود،
    «موجودی نداریم» و «نمی‌دانیم چقدر داریم» یک عدد می‌شوند و کل منطق
    «حداقل قابل اثبات» بی‌معنا می‌شود.
    """
    if s.dtype.kind in "if":                      # عددی خالص: کار تمام است
        return s.astype("float64")

    codes, uniq = pd.factorize(s, use_na_sentinel=False)
    lut = np.empty(len(uniq), dtype="float64")
    for i, u in enumerate(uniq):
        v = _num_or_none(u)
        lut[i] = np.nan if v is None else v
    return pd.Series(lut[codes], index=s.index, dtype="float64")


def _text_or_blank(s: pd.Series) -> pd.Series:
    """معادل برداریِ ``str(v).strip()`` با ``NaN`` → رشته تهی.

    همان الگوی یکتاسازی: ستون تعارض در عمل چند مقدار متمایز دارد، نه
    ۲۰۰ هزار تا.
    """
    codes, uniq = pd.factorize(s, use_na_sentinel=False)
    lut = np.array([("" if (u is None or u != u) else str(u).strip()) for u in uniq],
                   dtype=object)
    return pd.Series(lut[codes], index=s.index, dtype=object)


@register
class SupplyPositionStage(Stage):
    name = "supply_position"
    title = "یکپارچه‌سازی موجودی کارشناسی + Oracle با تفکیک Missing از Zero"
    order = 38
    requires = ["STOCK_IKCO", "STOCK_SAPCO", "SUPPLIER_QTY",
                "IN_TRANSIT_QTY", "IN_CUSTOMS_QTY", "DAILY_NEED"]
    provides = [
        "SUPPLY_ORACLE_STOCK", "SUPPLY_EXPERT_STOCK", "SUPPLY_TOTAL_CONFIRMED",
        "SUPPLY_TOTAL_LOWER_BOUND", "SUPPLY_POSITION_COVERAGE_PCT",
        "SUPPLY_POSITION_STATUS", "SUPPLY_POSITION_GAPS", "SUPPLY_POSITION_LINEAGE",
        "SUPPLY_EXPERT_COVERAGE_PCT", "SUPPLY_ORACLE_COVERAGE_PCT",
        "SUPPLY_POSITION_CONFLICT", "SUPPLY_POSITION_ASOF",
    ]

    ORACLE = (("STOCK_IKCO", "Oracle/IKCO"), ("STOCK_SAPCO", "Oracle/SAPCO"))
    EXPERT = (("SUPPLIER_QTY", "Expert/نزد سازنده"),
              ("IN_TRANSIT_QTY", "Expert/در راه"),
              ("IN_CUSTOMS_QTY", "Expert/گمرک"))

    LINEAGE = ("Oracle: STOCK_IKCO + STOCK_SAPCO | Expert: "
               "SUPPLIER_QTY + IN_TRANSIT_QTY + IN_CUSTOMS_QTY")

    @staticmethod
    def _text_col(df: pd.DataFrame, name: str) -> pd.Series:
        """معادل برداریِ ``str(r.get(name) or "").strip()``.

        نکته‌ای که در نسخه ردیفی پنهان بود: ``r.get()`` برای سلول خالیِ
        pandas مقدار ``NaN`` می‌دهد و ``NaN or ""`` در پایتون خودِ ``NaN``
        است (چون ``bool(nan)`` درست است)، پس ``str(...)`` رشته ``"nan"``
        می‌ساخت. روی ستون تعارض، همین یعنی **هر ردیفِ بدون تعارض، تعارض‌دار
        شمرده می‌شد** — و وضعیت آن ردیف ``CONFLICT`` می‌آمد. اینجا ``NaN``
        به رشته تهی نگاشت می‌شود، که همان چیزی است که کد قصدش را داشت.
        """
        if name not in df.columns:
            return pd.Series("", index=df.index, dtype=object)
        return _text_or_blank(df[name])

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        fields = (*self.ORACLE, *self.EXPERT)
        n_oracle, n_expert = len(self.ORACLE), len(self.EXPERT)

        # ── یک بار تبدیل عددی برای هر ستون، نه یک بار برای هر سلول ──
        vals = pd.DataFrame(
            {f: _numeric_or_nan(df[f]) if f in df.columns
                else pd.Series(np.nan, index=df.index, dtype="float64")
             for f, _ in fields},
            index=df.index)
        known = vals.notna()

        ok_oracle = known[[f for f, _ in self.ORACLE]]
        ok_expert = known[[f for f, _ in self.EXPERT]]
        k_oracle, k_expert = ok_oracle.sum(axis=1), ok_expert.sum(axis=1)
        k_all = k_oracle + k_expert

        oracle_complete = k_oracle == n_oracle
        expert_complete = k_expert == n_expert
        complete = oracle_complete & expert_complete

        sum_oracle = vals[[f for f, _ in self.ORACLE]].sum(axis=1, skipna=True)
        sum_expert = vals[[f for f, _ in self.EXPERT]].sum(axis=1, skipna=True)
        sum_all = vals.sum(axis=1, skipna=True)

        conflict = self._text_col(df, "EXPERT_INV_CONFLICT")
        status = pd.Series(
            np.select(
                [conflict != "", complete, k_all > 0],
                ["CONFLICT", "COMPLETE", "PARTIAL"],
                default="MISSING"),
            index=df.index, dtype=object)

        # ── شکاف‌ها: ۵ ستون یعنی ۳۲ ترکیب ممکن؛ جدول جست‌وجو می‌سازیم و
        #    به‌جای join کردن رشته در هر ردیف، یک map می‌زنیم.
        code = pd.Series(0, index=df.index, dtype="int64")
        for i, (f, _) in enumerate(fields):
            code += (~known[f]).astype("int64") * (1 << i)
        lut = {k: "، ".join(label for i, (_, label) in enumerate(fields) if k >> i & 1)
               for k in range(1 << len(fields))}

        df["SUPPLY_ORACLE_STOCK"] = self._none_if_all_missing(sum_oracle.where(oracle_complete))
        df["SUPPLY_EXPERT_STOCK"] = self._none_if_all_missing(sum_expert.where(expert_complete))
        df["SUPPLY_TOTAL_CONFIRMED"] = self._none_if_all_missing(sum_all.where(complete))
        df["SUPPLY_TOTAL_LOWER_BOUND"] = self._none_if_all_missing(sum_all.where(k_all > 0))
        df["SUPPLY_POSITION_COVERAGE_PCT"] = (100 * k_all / len(fields)).round(1)
        df["SUPPLY_EXPERT_COVERAGE_PCT"] = (100 * k_expert / n_expert).round(1)
        df["SUPPLY_ORACLE_COVERAGE_PCT"] = (100 * k_oracle / n_oracle).round(1)
        df["SUPPLY_POSITION_STATUS"] = status
        df["SUPPLY_POSITION_GAPS"] = code.map(lut)
        df["SUPPLY_POSITION_CONFLICT"] = conflict
        df["SUPPLY_POSITION_ASOF"] = self._text_col(df, "EXPERT_INV_ASOF")
        df["SUPPLY_POSITION_LINEAGE"] = self.LINEAGE

        ctx.extras["supply_position"] = self._ledger(df)

        # پوشش مؤلفه‌ها را صریح گزارش می‌کنیم تا «مقاومت صفر» قابل تشخیص باشد.
        component_cov = {}
        for field, label in fields:
            filled = int(known[field].sum())
            component_cov[field] = {
                "label": label, "filled": filled, "rows": int(len(df)),
                "pct": round(100.0 * filled / max(len(df), 1), 1),
            }
        ctx.extras["supply_position_component_coverage"] = component_cov
        cov_text = " | ".join(
            f"{k} {v['pct']:.1f}% ({v['filled']}/{v['rows']})"
            for k, v in component_cov.items())
        log.info(f"🧮 [supply-position] پوشش مؤلفه‌ها: {cov_text}")

        daily_known = _numeric_or_nan(df["DAILY_NEED"]).notna() if "DAILY_NEED" in df.columns \
            else pd.Series(False, index=df.index)
        material_known = (df["KEY_MATERIAL"].astype(str).str.strip().ne("")
                          if "KEY_MATERIAL" in df.columns else pd.Series(False, index=df.index))
        log.info(
            "🔗 [supply-position] KEY_MATERIAL معتبر %d/%d | DAILY_NEED معتبر %d/%d | "
            "Oracle کامل %d | Expert کامل %d",
            int(material_known.sum()), len(df), int(daily_known.sum()), len(df),
            int(oracle_complete.sum()), int(expert_complete.sum()))

        complete_n = int((df["SUPPLY_POSITION_STATUS"] == "COMPLETE").sum())
        partial_n = int((df["SUPPLY_POSITION_STATUS"] == "PARTIAL").sum())
        missing_n = int((df["SUPPLY_POSITION_STATUS"] == "MISSING").sum())
        conflict_n = int((df["SUPPLY_POSITION_STATUS"] == "CONFLICT").sum())
        log.info(
            f"📦 [supply-position] کامل {complete_n} | ناقص {partial_n} | "
            f"فاقد داده {missing_n} | تعارض {conflict_n}; Missing هرگز Zero نشده است."
        )
        return df

    @staticmethod
    def _none_if_all_missing(s: pd.Series) -> pd.Series:
        """اگر هیچ ردیفی مقدار ندارد، ستون object با ``None`` بده.

        نسخه ردیفی، ستونی که همه‌اش ``None`` بود را object می‌ساخت و نه
        float. این تفاوت در Excel دیده می‌شود (سلول خالی در برابر ``NaN``)،
        پس عمداً حفظ شده است.
        """
        return (pd.Series([None] * len(s), index=s.index, dtype=object)
                if s.isna().all() else s)

    @staticmethod
    def _ledger(df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in [
            "KEY_MATERIAL", "CANONICAL_ORDER", "CANONICAL_BL",
            "STOCK_IKCO", "STOCK_SAPCO", "SUPPLIER_QTY", "IN_TRANSIT_QTY",
            "IN_CUSTOMS_QTY", "SUPPLY_ORACLE_STOCK", "SUPPLY_EXPERT_STOCK",
            "SUPPLY_TOTAL_CONFIRMED", "SUPPLY_TOTAL_LOWER_BOUND",
            "SUPPLY_POSITION_COVERAGE_PCT", "SUPPLY_POSITION_STATUS",
            "SUPPLY_POSITION_GAPS", "SUPPLY_POSITION_CONFLICT", "SUPPLY_POSITION_ASOF",
            "DAILY_NEED",
        ] if c in df.columns]
        if not cols:
            return pd.DataFrame()
        return df[cols].drop_duplicates().reset_index(drop=True)

    def columns(self) -> List[ColumnSpec]:
        return [
            ColumnSpec("SUPPLIER_QTY", "موجودی نزد سازنده", 16, GROUP_MAIN,
                       fmt=FMT_DECIMAL, order=4),
            ColumnSpec("IN_TRANSIT_QTY", "موجودی در راه", 14, GROUP_MAIN,
                       fmt=FMT_DECIMAL, order=5),
            ColumnSpec("IN_CUSTOMS_QTY", "موجودی در گمرک", 14, GROUP_MAIN,
                       fmt=FMT_DECIMAL, order=6),
            ColumnSpec("SUPPLY_TOTAL_CONFIRMED", "موجودی کل تأییدشده", 17,
                       GROUP_MAIN, fmt=FMT_DECIMAL, order=7),
            ColumnSpec("SUPPLY_TOTAL_LOWER_BOUND", "حداقل موجودی قابل اثبات", 18,
                       GROUP_DETAIL, fmt=FMT_DECIMAL, order=8),
            ColumnSpec("SUPPLY_POSITION_COVERAGE_PCT", "پوشش داده موجودی (٪)", 17,
                       GROUP_ANALYTIC, fmt=FMT_DECIMAL, color_rule="scale_low_bad", order=91),
            ColumnSpec("SUPPLY_POSITION_STATUS", "وضعیت صحت موجودی", 17,
                       GROUP_ANALYTIC, order=92),
            ColumnSpec("SUPPLY_POSITION_GAPS", "شکاف‌های موجودی", 36,
                       GROUP_ANALYTIC, wrap=True, order=93),
            ColumnSpec("SUPPLY_POSITION_CONFLICT", "تعارض snapshot کارشناسی", 36,
                       GROUP_ANALYTIC, wrap=True, order=94),
        ]

    def kpis(self, df: pd.DataFrame, ctx: PipelineContext) -> Dict[str, tuple]:
        if "SUPPLY_POSITION_STATUS" not in df.columns:
            return {}
        return {
            "موجودی با پوشش کامل": (
                int((df["SUPPLY_POSITION_STATUS"] == "COMPLETE").sum()),
                "Oracle + نزد سازنده + در راه + گمرک"),
            "شکاف داده موجودی": (
                int(df["SUPPLY_POSITION_STATUS"].isin(["PARTIAL", "MISSING", "CONFLICT"]).sum()),
                "Unknown با Zero یکی نشده است"),
        }

    def math_docs(self, ctx: PipelineContext) -> Dict[str, Dict[str, Any]]:
        return {"Supply Position V26.20": {
            "جمع قطعی": "Oracle(IKCO+SAPCO) + Expert(Supplier+Transit+Customs)",
            "حداقل قابل اثبات": "جمع فقط مؤلفه‌های دارای شاهد کمی",
            "قاعده Missing": "هر bucket خالی = UNKNOWN؛ هرگز 0 فرض نمی‌شود",
            "دانه کارشناسی": "Order × Material",
        }}
