# -*- coding: utf-8 -*-
"""Oracle — متریال، موجودی و نیاز روزانه. مبنای محاسبه مقاومت قطعه.

هدرهای واقعی (۲۱ ستون، Total_Report):
شماره فني | کد جنس | شرح جنس | گروه تامين | گروه ساخت | گروه برنامه ريزي |
گروه قطعه | رده بندي قطعه | درصد سهم خريد خارجي | وضعيت | قطعه بحراني |
کد آلترناتيو | شماره نامه | تاريخ ثبت | توضيحات | شماره پرسنلي |
کارشناس خريد خارجي | موجودي انبار ايران خودرو | موجودي انبار ساپکو |
تعداد خودرو کف | نياز روزانه قطعات

⚠️ دو نکته که در HEADERS_MAP تأیید شد:
  • ستون «قطعه بحراني» **صفر درصد پر است** — پس بحرانی بودن باید محاسبه شود،
    نه خوانده. نسخه قبل دنبال ستون آماده «مقاومت» می‌گشت که اصلاً وجود ندارد.
  • این فایل بارنامه ندارد؛ نقش «وضعیت بارنامه» که قبلاً به Oracle نسبت داده
    شده بود، اشتباه بود و حذف شد.

Oracle همچنین «شماره پرسنلي» و «کارشناس خريد خارجي» دارد (۱۷٪ پر) که مسیر
دومی برای اتصال به HR است، در سطح قطعه به‌جای سطح سفارش.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict

import pandas as pd

from ..core.text import clean_employee_code, num_safe
from ..dataio.logging_setup import log
from .base import KEY_MATERIAL, SourceAdapter, register


@register
class OracleAdapter(SourceAdapter):
    key, prefix = "oracle", "ORC"

    COLUMN_MAP = {
        "PART_NO":         ["شماره فني", "شماره فنی"],
        "MATERIAL_CODE":   ["کد جنس"],
        "MATERIAL_DESC":   ["شرح جنس"],
        "SUPPLY_GROUP":    ["گروه تامين", "گروه تامین"],
        "BUILD_GROUP":     ["گروه ساخت"],
        "PLANNING_GROUP":  ["گروه برنامه ريزي", "گروه برنامه ریزی"],
        "PART_GROUP":      ["گروه قطعه"],
        "PART_CLASS":      ["رده بندي قطعه", "رده بندی قطعه"],
        "FOREIGN_SHARE":   ["درصد سهم خريد خارجي", "درصد سهم خرید خارجی"],
        "STATUS":          ["وضعيت", "وضعیت"],
        "CRITICAL_FLAG":   ["قطعه بحراني", "قطعه بحرانی"],
        "ALTERNATIVE":     ["کد آلترناتيو", "کد آلترناتیو"],
        "REGISTER_DATE":   ["تاريخ ثبت", "تاریخ ثبت"],
        "EMP_CODE":        ["شماره پرسنلي", "شماره پرسنلی"],
        "BUYER":           ["کارشناس خريد خارجي", "کارشناس خرید خارجی"],
        "STOCK_IKCO":      ["موجودي انبار ايران خودرو", "موجودی انبار ایران خودرو"],
        "STOCK_SAPCO":     ["موجودي انبار ساپکو", "موجودی انبار ساپکو"],
        "CARS_ON_FLOOR":   ["تعداد خودرو کف"],
        "DAILY_NEED":      ["نياز روزانه قطعات", "نیاز روزانه قطعات", "نیاز روزانه"],
    }

    #: بدون این‌ها مقاومت قابل محاسبه نیست
    ESSENTIAL = ["STOCK_IKCO", "STOCK_SAPCO", "DAILY_NEED"]

    NUMERIC = ["STOCK_IKCO", "STOCK_SAPCO", "CARS_ON_FLOOR", "DAILY_NEED",
               "FOREIGN_SHARE"]

    def transform(self, sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """ادغام امن تمام شیت‌های Oracle.

        Oracle در عمل ممکن است دو شیت با هدرهای تقریباً یکسان داشته باشد
        (مثلاً «موجودی» و «مصرف»). نسخه قدیمی فقط اولین شیت را می‌خواند و
        بنابراین اختلاف‌ها/داده تکمیل‌تر شیت دوم بی‌صدا از دست می‌رفت.

        منطق جدید:
          1) هدرهای هر شیت با COLUMN_MAP تطبیق داده می‌شوند.
          2) completeness هر شیت روی فیلدهای کلیدی محاسبه می‌شود.
          3) ردیف‌ها بر اساس KEY_MATERIAL هم‌تراز می‌شوند.
          4) برای هر فیلد، مقدار غیرخالی از شیت با رتبه تکمیل بالاتر ترجیح داده
             می‌شود؛ اگر همان شیت خالی باشد، از شیت دیگر fallback می‌شود.
          5) منبع انتخاب‌شده در ORC_SOURCE_SHEET ثبت می‌شود تا نتیجه قابل ممیزی باشد.

        هیچ مقدار خالی به صفر تبدیل نمی‌شود؛ صفر واقعی با خالی متفاوت است.
        """
        usable = [(name, df) for name, df in (sheets or {}).items()
                  if isinstance(df, pd.DataFrame) and not df.empty]
        if not usable:
            return {}

        ranked = []
        for name, df in usable:
            std = self.std(df, self.COLUMN_MAP, exclude=["توضیح"])
            self.add_material_key(std, df, ["شماره فني", "شماره فنی"])
            for f in self.NUMERIC:
                col = self.p(f)
                if col in std.columns:
                    std[col] = std[col].map(num_safe)
            emp = self.p("EMP_CODE")
            if emp in std.columns:
                std[emp] = std[emp].map(clean_employee_code)
            key = KEY_MATERIAL
            valid = std[key].astype(str).str.strip().ne("")
            # امتیاز تکمیل: فیلدهای حیاتی وزن بیشتری دارند، سپس پوشش کلی.
            essential_fill = []
            for f in self.ESSENTIAL:
                c = self.p(f)
                if c in std.columns:
                    essential_fill.append(std.loc[valid, c].map(lambda x: str(x).strip() != "").mean())
            overall = std.loc[valid].apply(
                lambda col: col.map(lambda x: str(x).strip() != "").mean()).mean() if valid.any() else 0.0
            score = (sum(essential_fill) / max(len(essential_fill), 1)) * 0.7 + overall * 0.3
            ranked.append((float(score), name, std.loc[valid].copy()))

        ranked.sort(key=lambda x: (-x[0], str(x[1])))
        # اولویت شیت کامل‌تر؛ در صورت مساوی بودن نام شیت فقط tie-break است.
        best_score, best_name, _ = ranked[0]
        frames = []
        for score, name, frame in ranked:
            x = frame.copy()
            x["ORC_SOURCE_SHEET"] = str(name)
            x["ORC_COMPLETENESS_SCORE"] = round(score, 6)
            frames.append(x)

        allf = pd.concat(frames, ignore_index=True, sort=False)
        key = KEY_MATERIAL
        value_cols = [c for c in allf.columns if c not in {key, "ORC_SOURCE_SHEET", "ORC_COMPLETENESS_SCORE"}]

        rows = []
        for material, grp in allf.groupby(key, sort=False, dropna=False):
            g = grp.copy()
            # هر مقدار از ردیفی که completeness بالاتری دارد انتخاب می‌شود؛
            # این کار اختلاف دو شیت را فقط در همان فیلد حل می‌کند.
            g = g.sort_values("ORC_COMPLETENESS_SCORE", ascending=False, kind="stable")
            row = {key: material}
            chosen = []
            for c in value_cols:
                vals = g[c] if c in g.columns else pd.Series(dtype=object)
                pick = ""
                for v in vals.tolist():
                    if pd.notna(v) and str(v).strip() != "":
                        pick = v
                        break
                row[c] = pick
            srcs = []
            for _, rr in g.iterrows():
                src = str(rr.get("ORC_SOURCE_SHEET", "")).strip()
                if src and src not in srcs: srcs.append(src)
            row["ORC_SOURCE_SHEET"] = " | ".join(srcs)
            row["ORC_COMPLETENESS_SCORE"] = float(g["ORC_COMPLETENESS_SCORE"].max()) if not g.empty else best_score
            rows.append(row)
        out = pd.DataFrame(rows)

        self._report_multisheet(usable, ranked, out, best_name)
        return {"main": self._aggregate(out)}

    def _report_multisheet(self, usable, ranked, out, best_name):
        log.info("   🔎 [oracle] مقایسه شیت‌ها: " + " | ".join(
            f"{name}: {len(df):,} ردیف، امتیاز تکمیل {score:.1%}" for score, name, df in ranked))
        if len(usable) > 1:
            log.info(f"   🧩 [oracle] شیت مرجع کامل‌تر: «{best_name}»؛ اختلاف‌ها در سطح هر متریال/فیلد با fallback شیت دیگر تکمیل شد.")
        p = self.p
        for f in self.ESSENTIAL:
            c = p(f)
            if c in out.columns:
                filled = out[c].map(lambda x: pd.notna(x) and str(x).strip() != "").mean()
                log.info(f"   {'✅' if filled else '⚠️'} [oracle] {f}: پوشش نهایی {filled:.1%}")

    # ── گزارش صریح پوشش ستون‌های حیاتی ──
    def _report(self, df: pd.DataFrame, out: pd.DataFrame) -> None:
        from ..core.columns import find_col
        p = self.p
        missing = []
        for f in self.ESSENTIAL:
            col = find_col(df, self.COLUMN_MAP[f], exclude=["توضیح"])
            (missing.append(f) if col is None
             else log.info(f"   ✅ [oracle] «{f}» ← «{col}»"))
        if missing:
            log.critical(
                "🚨 [oracle] ستون‌های " + " و ".join(missing) + " یافت نشد ⇒ "
                "مقاومت محاسبه نمی‌شود.\n"
                f"   ستون‌های موجود: {list(df.columns)[:25]}")
            return
        need = out[p("DAILY_NEED")].astype(float)
        log.info(f"   📦 [oracle] {len(out)} ردیف متریال | "
                 f"{int((need > 0).sum())} قطعه با نیاز روزانه > ۰ | "
                 f"جمع موجودی IKCO {out[p('STOCK_IKCO')].sum():,.0f} + "
                 f"ساپکو {out[p('STOCK_SAPCO')].sum():,.0f}")

    # ── یک ردیف به ازای هر متریال ──
    def _aggregate(self, out: pd.DataFrame) -> pd.DataFrame:
        p = self.p
        out = out[out[KEY_MATERIAL].astype(str).str.strip() != ""]
        if out.empty:
            log.warning("   ⚠️ [oracle] هیچ متریال با کلید معتبر نبود.")
            return out
        n0 = len(out)
        agg = {}
        for c in out.columns:
            if c == KEY_MATERIAL:
                continue
            if c in (p("STOCK_IKCO"), p("STOCK_SAPCO"), p("CARS_ON_FLOOR")):
                agg[c] = "sum"       # موجودی چند انبار جمع می‌شود
            elif c == p("DAILY_NEED"):
                agg[c] = "max"       # نیاز روزانه تکرار می‌شود، جمع نمی‌شود
            else:
                agg[c] = "first"
        res = out.groupby(KEY_MATERIAL, as_index=False).agg(agg)
        if len(res) != n0:
            log.info(f"   🧮 [oracle] {n0} ردیف → {len(res)} متریال یکتا (موجودی جمع شد)")
        return res
