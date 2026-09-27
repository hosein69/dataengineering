# -*- coding: utf-8 -*-
"""حل موجودیت کانونی + ممیزی تعارض.

اصلاحات:
  B5 (FIX) نسخه ۲۰.۱ برای هر ردیف کل لیست discrepancies را خطی جست‌وجو می‌کرد
           (پیچیدگی O(n²)). اینجا ایندکس دیکشنری ساخته می‌شود ⟹ O(n).
  B4 (FIX) نام ستون‌های کاندید دیگر حدسی نیست؛ نام‌های استاندارد adapter است.
  §۷      برای «شماره سفارش» الگوی ۸ رقمی اولویت مطلق دارد.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..config.sources import SOURCE_WEIGHTS
from ..core.text import is_empty_val, normalize_persian_text
from ..dataio.logging_setup import log

_EIGHT_DIGIT = re.compile(r"^\d{8}$")

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARNING = "WARNING"


class CanonicalEntityResolver:
    """انتخاب مقدار معیار از میان سورس‌های متعارض و ثبت ممیزی."""

    def __init__(self) -> None:
        self.discrepancies: List[Dict[str, Any]] = []
        self._by_bl: Dict[str, List[int]] = defaultdict(list)

    # ── حل یک صفت برای کل دیتافریم (برداری، نه ردیف‌به‌ردیف) ──
    def resolve(
        self,
        df: pd.DataFrame,
        attr_name: str,
        candidates: List[Tuple[str, str]],   # [(نام ستون, کلید سورس)]
        is_key: bool = False,
        bl_col: str = "KEY_BL",
        order_col: str = "KEY_ORDER",
    ) -> pd.Series:
        present = [(c, s) for c, s in candidates if c in df.columns]
        if not present:
            log.warning(f"⚠️ [resolver] هیچ ستون کاندیدی برای «{attr_name}» موجود نیست.")
            return pd.Series([""] * len(df), index=df.index, dtype="object")

        # مرتب‌سازی کاندیدها بر اساس وزن سورس (نزولی)
        present.sort(key=lambda cs: SOURCE_WEIGHTS.get(cs[1], 0.5), reverse=True)

        norm_cols = {c: df[c].map(normalize_persian_text) for c, _ in present}
        empty_mask = {c: df[c].map(is_empty_val) for c, _ in present}

        result = pd.Series([""] * len(df), index=df.index, dtype="object")
        for c, _ in present:
            need = (result == "") & (~empty_mask[c])
            result.loc[need] = norm_cols[c].loc[need]

        # ── تشخیص تعارض ──
        for i in df.index:
            vals = [(norm_cols[c][i], s, c) for c, s in present if not empty_mask[c][i]]
            if len(vals) < 2:
                continue
            uniq = {v[0] for v in vals}
            if len(uniq) < 2:
                continue

            chosen = result[i]
            explanation = "مقدار سورس با بالاترین وزن انتخاب شد."
            if attr_name == "شماره سفارش":
                eight = [v[0] for v in vals if _EIGHT_DIGIT.match(v[0])]
                if eight:
                    chosen = eight[0]
                    result[i] = chosen
                    explanation = f"طبق استاندارد ۸ رقمی، مقدار «{chosen}» انتخاب گردید."

            details = " | ".join(f"{s}({c}): «{v}»" for v, s, c in vals)
            bl = df.at[i, bl_col] if bl_col in df.columns else ""
            idx = len(self.discrepancies)
            self.discrepancies.append({
                "شماره بارنامه": bl,
                "شماره سفارش": df.at[i, order_col] if order_col in df.columns else "",
                "موجودیت": attr_name,
                "تعارض مشاهده شده": details,
                "شرح تفاوت الگوریتمی": explanation,
                "مقدار انتخاب شده (معیار)": chosen,
                "نوع اهمیت": SEVERITY_CRITICAL if is_key else SEVERITY_WARNING,
                "زمان ثبت ممیزی": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            if bl:
                self._by_bl[bl].append(idx)

        n_conf = sum(1 for d in self.discrepancies if d["موجودیت"] == attr_name)
        log.info(f"🧭 [resolver] «{attr_name}» از {len(present)} سورس حل شد — {n_conf} تعارض ثبت گردید.")
        return result

    def conflict_for_bl(self, bl: str) -> Optional[str]:
        """O(1) — جایگزین جست‌وجوی خطی نسخه قبلی."""
        idxs = self._by_bl.get(bl)
        if not idxs:
            return None
        return self.discrepancies[idxs[0]]["شرح تفاوت الگوریتمی"]

    def audit_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.discrepancies)
