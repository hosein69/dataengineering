# -*- coding: utf-8 -*-
"""موتور ادغام امن — مهم‌ترین اصلاح کل بازنویسی.

سه بیماری نسخه ۲۰.۱ اینجا درمان می‌شود:

  B3 (FIX)  انفجار دکارتی روی کلید خالی: ``clean_bl`` برای مقادیر نامعتبر ""
            برمی‌گرداند و merge روی "" همه ردیف‌های بی‌کلید را در هم ضرب می‌کرد.
  FIX-6     نبود ``drop_duplicates`` روی سمت راست (خصوصاً clearance).
  B4 (FIX)  اتکا به suffix خودکار pandas. اکنون هر adapter ستون‌هایش را با
            پیشوند صریح rename می‌کند و merge هیچ suffix پنهانی نمی‌سازد.

هر merge تعداد سطر قبل/بعد را می‌سنجد و در صورت تغییر، خطای صریح می‌دهد.
"""
from __future__ import annotations

#: نسخه قرارداد این ماژول — aibl/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 1


from typing import List, Optional, Union

import pandas as pd

from .logging_setup import log


class RowExplosionError(RuntimeError):
    """وقتی یک ادغام left تعداد سطرها را تغییر دهد."""


def dedupe_on_key(df: pd.DataFrame, key: str, keep_by: Optional[str] = None,
                  label: str = "") -> pd.DataFrame:
    """حذف کلیدهای خالی + یکتاسازی روی کلید.

    ``keep_by``: نام ستون تاریخ/عددی که بر اساس آن جدیدترین رکورد نگه داشته شود.
    """
    if df is None or df.empty or key not in df.columns:
        return df
    n0 = len(df)
    out = df[df[key].astype(str).str.strip() != ""].copy()
    n_empty = n0 - len(out)
    if keep_by and keep_by in out.columns:
        # ⚠️ مرتب‌سازی رشته‌ای روی تاریخ شمسی، داده سالم را بی‌صدا می‌خورد:
        # «98/12/27» رشته‌ای بزرگ‌تر از «1403/12/13» است. jalali_sort_key
        # همه را به میلادی یکدست می‌کند و مقدار خراب را همیشه بازنده می‌گذارد.
        from ..core.jalali import jalali_sort_key
        sort_col = "__aibl_sort__"
        out[sort_col] = out[keep_by].map(jalali_sort_key)
        # mergesort پایدار است: در تساوی تاریخ، ترتیب ورود فایل‌ها حفظ می‌شود
        # و نتیجه dedupe بین دو اجرا عوض نمی‌شود.
        out = out.sort_values(by=sort_col, ascending=False, kind="mergesort")
        out = out.drop(columns=[sort_col])

    n1 = len(out)
    out = out.drop_duplicates(subset=[key], keep="first")
    n_dup = n1 - len(out)
    if n_empty or n_dup:
        log.info(f"   🧹 [{label or key}] {n_empty} ردیف بدون کلید و {n_dup} ردیف تکراری حذف شد "
                 f"({n0} → {len(out)})")
    return out


def safe_merge(
    left: pd.DataFrame,
    right: Optional[pd.DataFrame],
    key: Union[str, List[str]],
    label: str,
    keep_by: Optional[str] = None,
    columns: Optional[List[str]] = None,
    strict: bool = True,
) -> pd.DataFrame:
    """ادغام left-join تضمین‌شده بدون تکثیر سطر.

    ``key`` می‌تواند یک ستون یا **فهرستی از ستون‌ها** (کلید مرکب) باشد.
    در حالت مرکب، یک ستون موقت از چسباندن اجزا ساخته می‌شود، ادغام روی آن
    انجام می‌گیرد و در پایان حذف می‌شود — پس منطق ضد تکثیر سطر دست‌نخورده
    باقی می‌ماند.
    """
    if right is None or right.empty:
        log.warning(f"⚠️ [{label}] سمت راست خالی است؛ ادغام رد شد.")
        return left

    if isinstance(key, (list, tuple)):
        parts = list(key)
        missing_l = [c for c in parts if c not in left.columns]
        missing_r = [c for c in parts if c not in right.columns]
        if missing_l or missing_r:
            log.warning(f"⚠️ [{label}] اجزای کلید مرکب موجود نیستند "
                        f"(چپ: {missing_l}، راست: {missing_r})؛ ادغام رد شد.")
            return left
        tmp = f"__CK_{label}__"
        left = left.copy()
        right = right.copy()
        for frame in (left, right):
            joined = frame[parts[0]].astype(str)
            for c in parts[1:]:
                joined = joined + "|" + frame[c].astype(str)
            frame[tmp] = joined
        log.info(f"   🔗 [{label}] ادغام با کلید مرکب {' + '.join(parts)}")
        out = safe_merge(left, right.drop(columns=parts, errors="ignore"),
                         tmp, label, keep_by=keep_by, columns=columns, strict=strict)
        return out.drop(columns=[tmp], errors="ignore")

    if key not in left.columns:
        log.warning(f"⚠️ [{label}] کلید «{key}» در جدول اصلی نیست؛ ادغام رد شد.")
        return left
    if key not in right.columns:
        log.warning(f"⚠️ [{label}] کلید «{key}» در سورس {label} نیست؛ ادغام رد شد.")
        return left

    r = right
    if columns:
        keep = [key] + [c for c in columns if c in r.columns and c != key]
        r = r[keep]
    r = dedupe_on_key(r, key, keep_by=keep_by, label=label)
    if r.empty:
        log.warning(f"⚠️ [{label}] پس از پاک‌سازی کلید، رکوردی نماند؛ ادغام رد شد.")
        return left

    # جلوگیری از برخورد نام ستون‌ها (adapterها باید پیشوند بگذارند)
    clash = [c for c in r.columns if c != key and c in left.columns]
    if clash:
        log.warning(f"⚠️ [{label}] ستون‌های هم‌نام کنار گذاشته شدند: {clash[:8]}")
        r = r.drop(columns=clash)

    n_before = len(left)
    merged = left.merge(r, on=key, how="left")
    n_after = len(merged)

    if n_after != n_before:
        msg = (f"❌ [{label}] انفجار سطر: {n_before} → {n_after} "
               f"(کلید {key} در سمت راست یکتا نیست)")
        if strict:
            raise RowExplosionError(msg)
        log.error(msg)
        return left

    matched = merged[[c for c in r.columns if c != key]].notna().any(axis=1).sum() if len(r.columns) > 1 else 0
    log.info(f"🔗 [{label}] ادغام روی {key} انجام شد — {matched} ردیف منطبق از {n_before}")
    return merged
