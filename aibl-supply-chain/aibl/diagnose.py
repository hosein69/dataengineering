# -*- coding: utf-8 -*-
"""بازرس رابطه‌ها (Join Diagnostics) — «کجا ریلیشن نشده؟»

## مسئله‌ای که این ابزار حل می‌کند

خط لوله می‌گوید «۰ ردیف منطبق» ولی **نمی‌گوید چرا**. سه علت کاملاً متفاوت
خروجی یکسانی دارند:

    ۱. فایل اصلاً پیدا نشد            → الگوی فایل غلط است
    ۲. فایل هست ولی ستون کلید نبود    → نگاشت ستون غلط است
    ۳. هر دو کلید هست ولی هم‌شکل نیست → نرمال‌سازی کلید غلط است
       (مثلاً «503110D» در یک سورس و «503110-D» یا «0503110» در سورس دیگر)

بدون تفکیک این سه، کاربر مجبور است حدس بزند. این ابزار هر سه را با **نمونه
واقعی کلیدها از دو طرف** تفکیک می‌کند و می‌گوید کدام‌یک است.

## اجرا

    python -m aibl.diagnose              گزارش کنسولی
    python -m aibl.diagnose --excel      + فایل اکسل تشخیصی در پوشه خروجی
"""
from __future__ import annotations

__contract__ = 1

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd

from .adapters import discover as discover_adapters
from .adapters.base import KEY_BL, KEY_EMP, KEY_MATERIAL, KEY_ORDER, KEY_REG
from .config.settings import SETTINGS
from .config.sources import MERGE_ORDER, SOURCES, get_source
from .dataio.logging_setup import log

_KEY_BY_JOIN = {"BL": KEY_BL, "ORDER": KEY_ORDER, "REG": KEY_REG,
                "EMP": KEY_EMP, "MATERIAL": KEY_MATERIAL}

# تشخیص علت: کد → (عنوان فارسی، اقدام پیشنهادی)
CAUSES = {
    "FILE_MISSING": ("فایل پیدا نشد",
                     "الگوی pattern در config/sources.yaml را با نام واقعی فایل تطبیق دهید."),
    "SHEET_EMPTY": ("فایل هست ولی شیت خالی است",
                    "نام شیت را در sources.yaml بررسی کنید."),
    "KEY_COLUMN_MISSING": ("ستون کلید در سورس پیدا نشد",
                           "فهرست کاندیدهای ستون کلید را در adapter همان سورس اضافه کنید."),
    "KEY_ALL_EMPTY": ("ستون کلید هست ولی همه مقادیر تهی یا نامعتبرند",
                      "تابع نرمال‌سازی کلید (clean_bl / clean_part_no) مقادیر را رد می‌کند."),
    "NO_OVERLAP": ("هر دو طرف کلید دارند ولی هیچ اشتراکی ندارند",
                   "شکل کلید در دو سورس یکی نیست — نمونه‌ها را در جدول زیر مقایسه کنید."),
    "PARTIAL": ("اشتراک ناقص", "بخشی از کلیدها هم‌شکل نیستند."),
    "OK": ("سالم", ""),
}

LOW_COVERAGE_THRESHOLD = 0.30      # زیر ۳۰٪ انطباق = مشکوک


class JoinDiagnostics:
    """بدون اجرای کامل خط لوله، وضعیت هر رابطه را می‌سنجد."""

    def __init__(self) -> None:
        self.sources: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.base: Optional[pd.DataFrame] = None
        self.rows: List[Dict[str, Any]] = []
        self.samples: List[Dict[str, Any]] = []

    # ── بارگذاری ──
    def load(self) -> None:
        for key, cls in discover_adapters().items():
            try:
                self.sources[key] = cls().load()
            except Exception as ex:
                log.error(f"❌ [{key}] adapter شکست خورد: {ex}")
                self.sources[key] = {}
        self.base = self.sources.get("abbasi", {}).get("main")

    # ── سنجش یک رابطه ──
    def _check(self, src: str, frame: str, join_on: str) -> Dict[str, Any]:
        spec = get_source(src)
        key = _KEY_BY_JOIN.get(join_on, KEY_BL)
        right = self.sources.get(src, {}).get(frame)
        left = self.base

        row: Dict[str, Any] = {
            "سورس": src, "فریم": frame, "کلید": key,
            "الگوی فایل": spec.pattern, "پوشه": spec.folder,
            "ردیف سورس": 0, "کلید معتبر در سورس": 0, "کلید یکتا در سورس": 0,
            "کلید یکتا در جدول پایه": 0, "اشتراک کلید": 0, "پوشش (٪)": 0.0,
            "علت": "OK", "اقدام": "",
        }

        if right is None or len(right) == 0:
            exists = os.path.isdir(spec.folder)
            row["علت"] = "FILE_MISSING" if not exists or not self.sources.get(src) else "SHEET_EMPTY"
            return row

        row["ردیف سورس"] = len(right)
        if key not in right.columns:
            row["علت"] = "KEY_COLUMN_MISSING"
            return row

        rk = right[key].astype(str).str.strip()
        rk = rk[rk != ""]
        row["کلید معتبر در سورس"] = int(len(rk))
        row["کلید یکتا در سورس"] = int(rk.nunique())
        if len(rk) == 0:
            row["علت"] = "KEY_ALL_EMPTY"
            self._sample(src, frame, key, set(), set(right[key].astype(str)))
            return row

        if left is not None and key in left.columns:
            lk_series = left[key].astype(str).str.strip()
            lk = set(lk_series[lk_series != ""])
        else:
            # کلید مشتق است (MATERIAL/REG/EMP): از سورس‌هایی که آن را تغذیه
            # می‌کنند بازسازی می‌شود، وگرنه رابطه شکسته «سالم» گزارش می‌شد.
            lk = self._derived_left_keys(key)
            if not lk:
                row["علت"] = "KEY_ALL_EMPTY"
                row["اقدام"] = (f"هیچ سورسی کلید {key} را تولید نکرد؛ "
                                f"ابتدا سورس تغذیه‌کننده را درست کنید.")
                return row
        rset = set(rk)
        row["کلید یکتا در جدول پایه"] = len(lk)
        overlap = lk & rset
        row["اشتراک کلید"] = len(overlap)
        row["پوشش (٪)"] = round(len(overlap) / max(len(lk), 1) * 100, 1)

        if not overlap:
            row["علت"] = "NO_OVERLAP"
        elif row["پوشش (٪)"] < LOW_COVERAGE_THRESHOLD * 100:
            row["علت"] = "PARTIAL"
        else:
            row["علت"] = "OK"

        if row["علت"] in ("NO_OVERLAP", "PARTIAL"):
            self._sample(src, frame, key, lk - rset, rset - lk)
        return row

    #: کدام سورس/ستون کلید مشتق را تغذیه می‌کند (هم‌راستا با pipeline._ensure_key)
    DERIVED_SOURCES = {
        KEY_MATERIAL: [("moghavemat", "main", "MOGH_MATERIAL"),
                       ("sap", "main", "SAP_MATERIAL"),
                       ("abbasi", "main", "BL_PART_NO"),
                       ("moghavemat", "main", "MOGH_MFR_PART_NO")],
        KEY_REG:      [("ilappend", "main", "IL_FILE_NO"),
                       ("fx_transaction", "main", "FX_KEY_REG")],
        KEY_EMP:      [("moghavemat", "main", "MOGH_KEY_EMP"),
                       ("ilappend", "main", "IL_KEY_EMP")],
    }

    def _derived_left_keys(self, key: str) -> set:
        """کلید مشتق را از سورس‌های تغذیه‌کننده بازسازی می‌کند."""
        from .core.text import clean_key, clean_part_no
        norm = clean_part_no if key == KEY_MATERIAL else clean_key
        out: set = set()
        for src, frame, col in self.DERIVED_SOURCES.get(key, []):
            df = self.sources.get(src, {}).get(frame)
            if df is None or col not in df.columns:
                continue
            vals = {norm(v) for v in df[col]}
            out |= {v for v in vals if v}
        return out

    def _sample(self, src: str, frame: str, key: str,
                only_left: set, only_right: set, n: int = 6) -> None:
        """نمونه کلیدهای دو طرف که با هم جور نشدند — قلب تشخیص."""
        l = sorted(str(x) for x in list(only_left)[:200])[:n]
        r = sorted(str(x) for x in list(only_right)[:200])[:n]
        for i in range(max(len(l), len(r))):
            self.samples.append({
                "سورس": src, "فریم": frame, "کلید": key,
                "نمونه کلید در جدول پایه": l[i] if i < len(l) else "",
                "نمونه کلید در سورس": r[i] if i < len(r) else "",
            })

    # ── اجرای کامل ──
    def run(self) -> pd.DataFrame:
        self.load()
        checked = set()
        for src in list(MERGE_ORDER) + [s for s in SOURCES if s not in MERGE_ORDER]:
            if src in checked or src not in SOURCES:
                continue
            checked.add(src)
            spec = get_source(src)
            frames = (spec.frame_map() if hasattr(spec, "frame_map")
                      else {"main": spec.join_on})
            available = set(self.sources.get(src, {}).keys())
            for frame, join_on in frames.items():
                if frame not in available and available:
                    continue          # این سورس فریم دیگری دارد؛ نبودِ این یکی خطا نیست
                self.rows.append(self._check(src, frame, join_on))
        # NTSW دو فریم غیراستاندارد دارد
        for frame in ("commitment", "allocation"):
            if self.sources.get("ntsw", {}).get(frame) is not None:
                self.rows.append(self._check("ntsw", frame, "REG"))
        return pd.DataFrame(self.rows)

    # ── پوشش ستون‌های حیاتی ──
    def critical_columns(self) -> pd.DataFrame:
        """آیا ستون‌هایی که KPIها به آن‌ها وابسته‌اند، اصلاً پر شده‌اند؟"""
        want = [
            ("ORC_STOCK_IKCO", "oracle", "main", "موجودی ایران‌خودرو — صورت کسر مقاومت"),
            ("ORC_STOCK_SAPCO", "oracle", "main", "موجودی ساپکو — صورت کسر مقاومت"),
            ("ORC_DAILY_NEED", "oracle", "main", "نیاز روزانه — مخرج کسر مقاومت"),
            # «تاریخ تخلیه» در هیچ فایل ترخیص نیست؛ در abbasi ستون ۱۶ است
            ("BL_DISCHARGE_DATE", "abbasi", "main", "تاریخ تخلیه — مبنای روزهای رسوب"),
            ("CL_FULL_CLEAR_DATE", "clearance", "main", "تاریخ ترخیص کامل"),
            ("NTSW_BALANCE", "ntsw", "commitment", "مانده تعهد — مبنای جریمه"),
            ("NTSW_COMMIT_DATE", "ntsw", "commitment", "تاریخ CB — مبنای مهلت قانونی"),
            ("SATA_NO", "sata", "main", "کد ساتا — شاهد گمرکی"),
            ("COT_NO", "cotage", "main", "کوتاژ — شاهد گمرکی"),
            ("MOGH_ADDITIONAL_DATA", "moghavemat", "main", "وضعیت بازرگانی/لجستیک"),
            ("DOC_SUBMIT_DATE", "doccheck", "main", "تاریخ ارائه اسناد"),
            ("FX_CB_VALUE", "fx_transaction", "main", "ارزش CB — مبنای ارزش در معرض خطر"),
        ]
        out = []
        for col, src, frame, why in want:
            df = self.sources.get(src, {}).get(frame)
            if df is None or len(df) == 0:
                out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                            "ردیف": 0, "پرشده": 0, "نرخ پر بودن (٪)": 0.0,
                            "وضعیت": "❌ سورس در دسترس نیست"})
                continue
            if col not in df.columns:
                out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                            "ردیف": len(df), "پرشده": 0, "نرخ پر بودن (٪)": 0.0,
                            "وضعیت": "❌ ستون ساخته نشد (نگاشت adapter)"})
                continue
            col_s = df[col]
            if pd.api.types.is_numeric_dtype(col_s):
                # ⚠️ برای ستون عددی، صفر یک مقدار معتبر است نه فقدان مقدار.
                # «مانده تعهد = ۰» یعنی رفع تعهد شده، نه اینکه داده نیست.
                filled = int(col_s.notna().sum())
                nonzero = int((col_s.fillna(0) != 0).sum())
            else:
                t = col_s.astype(str).str.strip().replace(
                    {"nan": "", "None": "", "NaT": "", "<NA>": "", "*": ""})
                filled = int(t.ne("").sum())
                nonzero = filled
            pct = round(filled / max(len(df), 1) * 100, 1)
            pct_nz = round(nonzero / max(len(df), 1) * 100, 1)
            status = ("✅ سالم" if pct >= 50 else
                      "⚠️ کم" if pct > 0 else "❌ همه تهی — ستون اشتباه انتخاب شده")
            if pct >= 50 and pct_nz < 20:
                status = "✅ پر است (اکثراً صفر — و صفر مقدار معتبری است)"
            out.append({"ستون": col, "سورس": f"{src}/{frame}", "کاربرد": why,
                        "ردیف": len(df), "پرشده": filled,
                        "نرخ پر بودن (٪)": pct, "نرخ غیرصفر (٪)": pct_nz,
                        "وضعیت": status})
        return pd.DataFrame(out)

    # ── ستون‌های واقعی هر سورس، برای تطبیق دستی ──
    def raw_headers(self) -> pd.DataFrame:
        out = []
        for src, frames in self.sources.items():
            for frame, df in frames.items():
                if df is None or len(df) == 0:
                    continue
                out.append({"سورس": src, "فریم": frame, "ردیف": len(df),
                            "تعداد ستون": len(df.columns),
                            "ستون‌ها": " | ".join(str(c) for c in list(df.columns)[:40])})
        return pd.DataFrame(out)


def _print(df: pd.DataFrame, title: str) -> None:
    print("\n" + "═" * 78)
    print(title)
    print("═" * 78)
    if df.empty:
        print("   (خالی)")
        return
    with pd.option_context("display.width", 200, "display.max_colwidth", 46):
        print(df.to_string(index=False))


def main() -> int:
    print("═" * 78)
    print("AIBL — بازرس رابطه‌ها: کجا ریلیشن برقرار نشده؟")
    print("═" * 78)

    d = JoinDiagnostics()
    joins = d.run()

    view = joins.copy()
    view["تشخیص"] = view["علت"].map(lambda c: CAUSES.get(c, ("?", ""))[0])
    view["اقدام لازم"] = [r["اقدام"] or CAUSES.get(r["علت"], ("", ""))[1]
                          for _, r in joins.iterrows()]
    _print(view[["سورس", "فریم", "کلید", "ردیف سورس", "کلید یکتا در سورس",
                 "اشتراک کلید", "پوشش (٪)", "تشخیص"]],
           "۱) وضعیت هر رابطه")

    broken = view[view["علت"] != "OK"]
    if not broken.empty:
        print("\n🔧 اقدامات لازم:")
        for _, r in broken.iterrows():
            print(f"   • [{r['سورس']}/{r['فریم']}] {r['تشخیص']}")
            print(f"     ← {r['اقدام لازم']}")
            if r["علت"] == "FILE_MISSING":
                print(f"     ← الگوی فعلی: {r['الگوی فایل']}")
                print(f"     ← پوشه: {r['پوشه']}")

    samples = pd.DataFrame(d.samples)
    _print(samples, "۲) نمونه کلیدهایی که جور نشدند (شکل دو طرف را مقایسه کنید)")

    cols = d.critical_columns()
    _print(cols[["ستون", "سورس", "نرخ پر بودن (٪)", "نرخ غیرصفر (٪)",
                 "وضعیت", "کاربرد"]],
           "۳) پر بودن ستون‌های حیاتی — علت صفر شدن KPIها")

    if "--headers" in sys.argv:
        _print(d.raw_headers(), "۴) ستون‌های واقعی هر سورس")

    if "--excel" in sys.argv:
        os.makedirs(SETTINGS.OUTPUT_DIR, exist_ok=True)
        path = os.path.join(SETTINGS.OUTPUT_DIR, "AIBL_Join_Diagnostics.xlsx")
        with pd.ExcelWriter(path) as w:
            view.to_excel(w, sheet_name="وضعیت رابطه‌ها", index=False)
            samples.to_excel(w, sheet_name="کلیدهای جورنشده", index=False)
            cols.to_excel(w, sheet_name="ستون‌های حیاتی", index=False)
            d.raw_headers().to_excel(w, sheet_name="هدرهای واقعی", index=False)
        print(f"\n📄 گزارش تشخیصی: {path}")

    n_bad = int((view["علت"] != "OK").sum())
    print("\n" + "═" * 78)
    print(f"نتیجه: {len(view) - n_bad} رابطه سالم | {n_bad} رابطه مشکل‌دار")
    print("═" * 78)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
