# -*- coding: utf-8 -*-
"""کشف فایل و خواندن شیت‌های اکسل.

اصلاحات کلیدی:
  * fallback به شیت ۰ دیگر بی‌صدا نیست؛ WARNING صریح ثبت می‌شود (FIX-13).
  * نام شیت‌ها فقط از رجیستری سورس‌ها خوانده می‌شود، نه هاردکد در pipeline.
  * نبود سورس ⇒ رد شدن با هشدار، نه کرش (مگر required=True).
"""
from __future__ import annotations

import glob
import os
from typing import Dict, List, Optional

import pandas as pd

from ..config.sources import SourceSpec, get_source
from ..core.text import normalize_col_name
from .logging_setup import log

_EXTS = (".xlsx", ".xlsm", ".xls")


def find_files(spec: SourceSpec) -> List[str]:
    """همه فایل‌های منطبق با الگو، مرتب‌شده از جدید به قدیم."""
    if not spec.folder or not os.path.isdir(spec.folder):
        log.warning(f"❌ اتصال به سورس '{spec.key}' برقرار نشد: پوشه یافت نشد ({spec.folder})")
        return []
    found: List[str] = []
    for ext in _EXTS:
        found.extend(glob.glob(os.path.join(spec.folder, f"{spec.pattern}{ext}")))
    found = [f for f in found if not os.path.basename(f).startswith("~$")]
    if not found:
        log.warning(f"❌ اتصال به سورس '{spec.key}' برقرار نشد: فایلی با الگوی {spec.pattern} یافت نشد.")
        return []
    return sorted(found, key=os.path.getmtime, reverse=True)


def find_file(source_key: str) -> Optional[str]:
    """جدیدترین فایل یک سورس."""
    spec = get_source(source_key)
    files = find_files(spec)
    if not files:
        return None
    log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {os.path.basename(files[0])}")
    return files[0]


def read_sheet(path: str, sheet: Optional[str], source_key: str = "") -> Optional[pd.DataFrame]:
    """خواندن یک شیت مشخص. ``sheet=None`` یعنی شیت ۰."""
    try:
        xl = pd.ExcelFile(path)
        if sheet is None:
            target = xl.sheet_names[0]
        elif sheet in xl.sheet_names:
            target = sheet
        else:
            # تطبیق بدون حساسیت به حروف/فاصله
            norm = {s.strip().lower(): s for s in xl.sheet_names}
            key = sheet.strip().lower()
            if key in norm:
                target = norm[key]
            else:
                target = xl.sheet_names[0]
                log.warning(
                    f"⚠️ [{source_key}] شیت «{sheet}» در {os.path.basename(path)} نبود؛ "
                    f"به شیت «{target}» fallback شد. شیت‌های موجود: {xl.sheet_names}"
                )
        df = xl.parse(target, dtype=str)
        df.columns = [normalize_col_name(c) for c in df.columns]
        df = df.loc[:, [c for c in df.columns if c != ""]]
        log.info(f"📥 [{source_key}] شیت «{target}» خوانده شد — {len(df)} ردیف × {len(df.columns)} ستون")
        return df
    except Exception as ex:
        log.error(f"❌ خطا در خواندن «{sheet}» از {path}: {ex}")
        return None


def read_source(source_key: str) -> Dict[str, pd.DataFrame]:
    """تمام شیت‌های یک سورس را برمی‌گرداند: {نام شیت: DataFrame}.

    برای سورس‌های multi_file (مثل clearance) همه فایل‌ها concat می‌شوند.
    """
    spec = get_source(source_key)
    files = find_files(spec)
    if not files:
        return {}
    targets = files if spec.multi_file else files[:1]
    if spec.multi_file:
        log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {len(targets)} فایل")
    else:
        log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {os.path.basename(targets[0])}")

    out: Dict[str, pd.DataFrame] = {}

    # استراتژی all_data_sheets: نام شیت در هر فایل فرق دارد (مثل Clearance که
    # Sea/Air/Land/chabahar است). به‌جای نام ثابت، بزرگ‌ترین شیت داده هر فایل
    # خوانده می‌شود و شیت‌های کمکی رد می‌شوند.
    if spec.opt("sheet_strategy") == "all_data_sheets":
        skip = {str(x).strip().lower() for x in (spec.opt("skip_sheets") or [])}
        frames = []
        for f in targets:
            try:
                xl = pd.ExcelFile(f)
            except Exception as ex:
                log.error(f"❌ [{spec.key}] {os.path.basename(f)}: {ex}")
                continue
            best, best_rows = None, -1
            for sh in xl.sheet_names:
                if sh.strip().lower() in skip:
                    continue
                try:
                    tmp = xl.parse(sh, dtype=str)
                except Exception:
                    continue
                if len(tmp) > best_rows:
                    best, best_rows = sh, len(tmp)
            if best is None:
                log.warning(f"⚠️ [{spec.key}] در {os.path.basename(f)} شیت داده‌ای نبود.")
                continue
            df = read_sheet(f, best, spec.key)
            if df is not None and not df.empty:
                df["_SOURCE_FILE"] = os.path.basename(f)
                df["_SOURCE_SHEET"] = best
                frames.append(df)
        if frames:
            out["main"] = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
            log.info(f"   📚 [{spec.key}] {len(frames)} شیت داده از {len(targets)} فایل "
                     f"ادغام شد — مجموع {len(out['main'])} ردیف")
        return out

    for sheet in spec.sheets:
        frames = []
        for f in targets:
            df = read_sheet(f, sheet, spec.key)
            if df is not None and not df.empty:
                df["_SOURCE_FILE"] = os.path.basename(f)
                frames.append(df)
        if frames:
            label = sheet or "__first__"
            out[label] = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    return out
