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

#: نسخه قرارداد این ماژول — gsi/version.py آن را می‌سنجد.
#: با هر تغییر در رابط عمومی، این عدد یکی زیاد می‌شود.
__contract__ = 2


from typing import List, Optional, Union

import pandas as pd

from .. import health
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
    out = df[df[key].notna() & ~df[key].astype(str).str.strip().str.lower().isin(["", "nan", "none", "<na>"])].copy()
    n_empty = n0 - len(out)
    if keep_by and keep_by in out.columns:
        # ⚠️ مرتب‌سازی رشته‌ای روی تاریخ شمسی، داده سالم را بی‌صدا می‌خورد:
        # «98/12/27» رشته‌ای بزرگ‌تر از «1403/12/13» است. jalali_sort_key
        # همه را به میلادی یکدست می‌کند و مقدار خراب را همیشه بازنده می‌گذارد.
        from ..core.jalali import jalali_sort_key
        sort_col = "__gsi_sort__"
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
    zero_match_degraded: bool = True,
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
            import json
            valid = frame[parts].notna().all(axis=1)
            for c in parts:
                valid &= ~frame[c].astype(str).str.strip().str.lower().isin(["", "nan", "none", "<na>"])
            frame[tmp] = [json.dumps([str(v) for v in row], ensure_ascii=False) if ok else ""
                          for row, ok in zip(frame[parts].itertuples(index=False, name=None), valid)]
        log.info(f"   🔗 [{label}] ادغام با کلید مرکب {' + '.join(parts)}")
        out = safe_merge(left, right.drop(columns=parts, errors="ignore"),
                         tmp, label, keep_by=keep_by, columns=columns, strict=strict,
                         zero_match_degraded=zero_match_degraded)
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
    duplicates = r[r[key].notna() & r.duplicated(subset=[key], keep=False)]
    if not duplicates.empty:
        health.current().find("ادغام", health.WARN,
                              f"{label}: projection of {len(duplicates)} RHS observations onto {key}",
                              "Native rows remain in source evidence; this table is a representative compatibility projection, not an additive fact.")
    r = dedupe_on_key(r, key, keep_by=keep_by, label=label)
    if r.empty:
        log.warning(f"⚠️ [{label}] پس از پاک‌سازی کلید، رکوردی نماند؛ ادغام رد شد.")
        return left

    # جلوگیری از برخورد نام ستون‌ها (adapterها باید پیشوند بگذارند).
    # Physical lineage is the exception: dropping _SOURCE_* destroys replay/audit
    # for the RHS source. Namespace those columns by source label before merge.
    clash = [c for c in r.columns if c != key and c in left.columns]
    lineage = {"_SOURCE_ROW", "_SOURCE_FILE_ID", "_SOURCE_SHEET", "_SOURCE_FILE"}
    lineage_clash = [c for c in clash if c in lineage]
    if lineage_clash:
        import re as _re
        prefix = _re.sub(r"[^A-Za-z0-9]+", "_", str(label)).strip("_").upper() or "RHS"
        rename = {}
        for c in lineage_clash:
            candidate = f"{prefix}_{c.lstrip('_')}"
            n = 2
            while candidate in left.columns or candidate in r.columns or candidate in rename.values():
                candidate = f"{prefix}_{c.lstrip('_')}_{n}"; n += 1
            rename[c] = candidate
        r = r.rename(columns=rename)
        log.info(f"🧬 [{label}] lineage سمت راست حفظ شد: {rename}")
    clash = [c for c in r.columns if c != key and c in left.columns]
    if clash:
        log.warning(f"⚠️ [{label}] ستون‌های هم‌نام غیر-lineage کنار گذاشته شدند: {clash[:8]}")
        r = r.drop(columns=clash)

    n_before = len(left)
    merged = left.merge(r, on=key, how="left", validate="many_to_one")
    n_after = len(merged)

    if n_after != n_before:
        msg = (f"❌ [{label}] انفجار سطر: {n_before} → {n_after} "
               f"(کلید {key} در سمت راست یکتا نیست)")
        health.current().join(health.JoinHealth(
            label=label, key=key, rows_before=n_before, rows_after=n_after,
            status=health.FAILED, note="انفجار سطر — ادغام اعمال نشد"))
        health.current().find("ادغام", health.ERROR, msg)
        if strict:
            raise RowExplosionError(msg)
        log.error(msg)
        return left

    matched = merged[[c for c in r.columns if c != key]].notna().any(axis=1).sum() if len(r.columns) > 1 else 0
    # ادغامی که هیچ ردیفی منطبق نکند، «موفق» نیست — یعنی کلید دو طرف
    # هم‌جنس نیست و کسی متوجه نمی‌شود مگر اینکه ثبت شود.
    rate = (matched / n_before) if n_before else 0.0
    if rate > 0:
        status = health.OK
        note = ""
    elif zero_match_degraded:
        status = health.DEGRADED
        note = "هیچ ردیفی منطبق نشد — relation نیازمند بررسی است"
    else:
        status = health.OK
        note = "سورس ناقصِ شناخته‌شده؛ zero-match فعلاً از ارزیابی سلامت کل خارج است"
    health.current().join(health.JoinHealth(
        label=label, key=key, rows_before=n_before, rows_after=n_after,
        matched=int(matched), status=status, note=note))
    if n_before and not matched and len(r.columns) > 1:
        if zero_match_degraded:
            health.current().find(
                "ادغام", health.WARN,
                f"ادغام «{label}» روی کلید {key} هیچ انطباقی نداشت",
                "ستون‌های این سورس در جدول اصلی خالی می‌مانند؛ semantics/scope را بررسی کنید.")
        else:
            health.current().find(
                "ادغام", health.INFO,
                f"ادغام «{label}» فعلاً از ارزیابی سلامت خارج است",
                "سورس ناقصِ شناخته‌شده است؛ با تکمیل سورس این استثناء حذف شود.")
    log.info(f"🔗 [{label}] ادغام روی {key} انجام شد — {matched} ردیف منطبق از {n_before}")
    return merged
