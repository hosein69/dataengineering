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
from .. import health
from .logging_setup import log

_EXTS = (".xlsx", ".xlsm", ".xls")
BASELINE_SOURCE_FILES = {
    "abbasi": "BLs Tracking.xlsx",
    "moghavemat": "Commercial Expert Data.xlsx",
}


def find_files(spec: SourceSpec, quiet: bool = False) -> List[str]:
    """همه فایل‌های منطبق با الگو، مرتب‌شده از جدید به قدیم."""
    baseline = BASELINE_SOURCE_FILES.get(spec.key)
    if baseline:
        configured = spec.opt("file_names")
        if configured and {str(name).casefold() for name in configured} != {baseline.casefold()}:
            raise ValueError(f"BASE_SOURCE_CONTRACT: {spec.key} must use {baseline}; "
                             f"configured file_names={configured!r}")
    if not spec.folder or not os.path.isdir(spec.folder):
        if not quiet:
            log.warning(f"❌ اتصال به سورس '{spec.key}' برقرار نشد: پوشه یافت نشد ({spec.folder})")
        return []
    if baseline:
        # The agreed workbook identity outranks a broad pattern and mtime,
        # including when GSI_SOURCES_YAML points to an older external registry.
        matches = [entry.path for entry in os.scandir(spec.folder)
                   if entry.is_file() and entry.name.casefold() == baseline.casefold()]
        if not matches and not quiet:
            log.error("BASE_SOURCE_FILE_MISSING: %s requires %s in %s; variants are review-only",
                      spec.key, baseline, spec.folder)
        return matches[:1]
    found: List[str] = []
    for ext in _EXTS:
        found.extend(glob.glob(os.path.join(spec.folder, f"{spec.pattern}{ext}")))
    found = [f for f in found if not os.path.basename(f).startswith("~$")]
    if spec.opt("file_names"):
        accepted = {str(name).casefold() for name in spec.opt("file_names")}
        found = [f for f in found if os.path.basename(f).casefold() in accepted]
    if not found:
        if not quiet:
            log.warning(f"❌ اتصال به سورس '{spec.key}' برقرار نشد: فایلی با الگوی {spec.pattern} یافت نشد.")
        return []
    return sorted(found, key=os.path.getmtime, reverse=True)


def source_targets(source_key: str, quiet: bool = False):
    """(مشخصات سورس، فایل‌هایی که خوانده می‌شوند به همان ترتیب خواندن)."""
    spec = get_source(source_key)
    files = find_files(spec, quiet=quiet)
    return spec, (files if spec.multi_file else files[:1])


def find_file(source_key: str) -> Optional[str]:
    """جدیدترین فایل یک سورس."""
    spec = get_source(source_key)
    files = find_files(spec)
    if not files:
        return None
    log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {os.path.basename(files[0])}")
    return files[0]


def read_sheet(path: str, sheet: Optional[str], source_key: str = "",
               header_row: int = 0) -> Optional[pd.DataFrame]:
    """خواندن یک شیت مشخص. ``sheet=None`` یعنی «شیت اول، هرچه باشد».

    ## چرا اینجا fail-closed است

    تا نسخه ۲۶٫۱۰ اگر شیت خواسته‌شده پیدا نمی‌شد، **شیت اول فایل** خوانده
    می‌شد و فقط یک warning در لاگ می‌نشست. زنجیره‌اش این بود:

        شیت «Expert Data» نبود → شیت اول خوانده شد → ستون‌ها نگاشت نشدند
        → فریم تقریباً خالی ولی «موجود» → خط لوله ادامه داد
        → گزارش تولید شد و هیچ‌جا ننوشت که مبنایش عوض شده

    یعنی داده‌ی اشتباه با ظاهر معتبر. در سیستمی که روی خروجی‌اش تصمیم
    عملیاتی گرفته می‌شود، این بدترین حالت ممکن است — بدتر از خطا دادن.

    قاعده جدید: شیتی که **صریحاً نام برده شده** یا هست یا نیست. اگر نیست،
    ``None`` برمی‌گردد و شکاف اسکیما در «سلامت سیستم» ثبت می‌شود. تنها
    جایی که شیت اول خوانده می‌شود، وقتی است که پیکربندی خودش گفته باشد
    ``sheet=None`` — یعنی «شیت اول، هرچه باشد».
    """
    try:
        # Windows keeps the temporary .xlsx locked while an ExcelFile/openpyxl
        # reader is alive.  Always close the reader *before* TemporaryDirectory
        # cleanup; otherwise shutil.rmtree raises WinError 32 after a successful read.
        with pd.ExcelFile(path) as xl:
            if sheet is None:
                target = xl.sheet_names[0]
            elif sheet in xl.sheet_names:
                target = sheet
            else:
                # تطبیق بدون حساسیت به حروف/فاصله — این هنوز مجاز است، چون
                # همان شیت است با املای متفاوت، نه شیتی دیگر.
                norm = {s.strip().lower(): s for s in xl.sheet_names}
                key = sheet.strip().lower()
                if key in norm:
                    target = norm[key]
                else:
                    gap = (f"شیت «{sheet}» در {os.path.basename(path)} نیست "
                           f"(شیت‌های موجود: {xl.sheet_names})")
                    log.error(f"❌ [{source_key}] {gap} — این فریم نامعتبر اعلام شد "
                              f"و به شیت دیگری fallback نمی‌شود.")
                    health.current().schema_gap(source_key or "?", gap)
                    return None
            df = xl.parse(target, dtype=str, header=header_row)
        # At this point the underlying workbook/file handle is already closed.
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
    spec, targets = source_targets(source_key)
    if not targets:
        return {}
    if spec.multi_file:
        log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {len(targets)} فایل")
    else:
        log.info(f"🔌 اتصال موفق به سورس '{spec.key}' → {os.path.basename(targets[0])}")

    # Capture original bytes before any semantic parsing; every physical cell
    # remains in the warehouse. Native OOXML adapters need the physical rows in
    # Python. Legacy readers do not: retaining them duplicates the workbook in
    # memory before pandas parses the exact archived bytes again.
    from ..warehouse.excel import capture, frame
    if source_key in ('oracle', 'fx_transaction', 'ntsw'):
        result = {}
        for f in targets:
            fid, blob, sheets = capture(f, source_key, keep_sheets=True)
            for name, rows in sheets.items():
                df = frame(rows, source_key, name, fid)
                if source_key=='oracle':
                    forbidden={'وضعیت','قطعه بحرانی','شماره نامه','تاریخ ثبت','توضیحات','شماره پرسنلی','کارشناس خرید خارجی','ریسک پذیری','Column18'}
                    df=df.drop(columns=[col for col in df if col in forbidden],errors='ignore')
                if not df.empty:
                    from ..warehouse.store import Warehouse
                    from ..warehouse.marts import stage
                    stage(df,source_key,name,fid)
                    Warehouse().frame(df,'staging',source_key+'/'+name)
                    if name in result:
                        result[name] = pd.concat([result[name],df],ignore_index=True)
                    else: result[name] = df
            # Let each workbook's large physical-row structure be released before
            # the next multi-file source is captured.
            del sheets, blob
        return result

    # Legacy readers parse the exact archived bytes, not a changing network file.
    # Capture and materialize one file at a time so a multi-file source does not
    # keep all workbook byte blobs + physical row dictionaries resident together.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='gsi_input_') as tmp:
        local_targets = []
        for f in targets:
            # Abbasi's workbook carries many auxiliary worksheets. The complete
            # original file is archived by capture; physical-cell indexing of
            # auxiliary sheets is deferred to a dedicated forensic scan.
            contracted = spec.sheets if source_key == 'abbasi' else None
            fid, blob, _ = capture(f, source_key, keep_sheets=False,
                                   archive_sheets=contracted)
            directory = os.path.join(tmp, fid)
            os.makedirs(directory, exist_ok=True)
            local = os.path.join(directory, os.path.basename(f))
            with open(local, 'wb') as handle:
                handle.write(blob)
            local_targets.append(local)
            del blob
        return _read_targets(spec, local_targets)


#: ستون‌های قراردادی ترخیص؛ همان نام‌هایی که ClearanceAdapter می‌پذیرد، نه حدس تازه.
CLEARANCE_BL_HEADERS = ("بارنامه", "شماره بارنامه")
CLEARANCE_FILE_HEADERS = ("پرونده ترخیص",)
#: چند ردیف اول که ممکن است عنوان یا خط خالی بالای هدر باشد.
CLEARANCE_HEADER_SCAN_ROWS = 10


def clearance_header(xl, sheet: str) -> dict:
    """ردیف هدر قراردادی یک شیت ترخیص: {sheet, header_row (یا None), headers, missing}.

    هدر اغلب ردیف اول است؛ فایلی که بالای هدر عنوان یا خط خالی دارد هم پذیرفته می‌شود، به شرط اینکه
    همان ستون‌های قراردادی در یکی از چند ردیف اول باشند."""
    from ..warehouse.excel import header_normal
    try:
        head = xl.parse(sheet, header=None, nrows=CLEARANCE_HEADER_SCAN_ROWS, dtype=str)
    except Exception as ex:
        return {"sheet": sheet, "header_row": None, "headers": [], "missing": [f"read error: {ex}"]}
    first = []
    for i in range(len(head)):
        cells = [str(v) for v in head.iloc[i].tolist() if pd.notna(v) and str(v).strip()]
        norm = {header_normal(c) for c in cells}
        if not first:
            first = cells
        if norm & set(CLEARANCE_BL_HEADERS) and norm & set(CLEARANCE_FILE_HEADERS):
            return {"sheet": sheet, "header_row": i, "headers": cells, "missing": []}
    norm = {header_normal(c) for c in first}
    missing = [("/".join(names)) for names in (CLEARANCE_BL_HEADERS, CLEARANCE_FILE_HEADERS)
               if not norm & set(names)]
    return {"sheet": sheet, "header_row": None, "headers": first, "missing": missing}


def clearance_gap_text(file_name: str, seen: List[dict]) -> str:
    """پیام شکاف که خودش می‌گوید کدام فایل، کدام شیت و کدام ستون قراردادی نبود."""
    parts = []
    for s in seen:
        heads = " | ".join(s["headers"][:40])
        parts.append(f"شیت «{s['sheet']}»: ستون قراردادی نیست: {'، '.join(s['missing']) or '?'}؛ "
                     f"هدر دیده‌شده: {heads or '(خالی)'}")
    return (f"No contracted clearance sheet in {file_name} — "
            + (" ؛ ".join(parts) if parts else "هیچ شیت داده‌ای (غیر از شیت‌های کمکی) ندارد"))


def _read_targets(spec, targets):
    out: Dict[str, pd.DataFrame] = {}

    # استراتژی all_data_sheets: نام شیت در هر فایل فرق دارد (مثل Clearance که
    # Sea/Air/Land/chabahar است). به‌جای نام ثابت، تمام شیت‌های دارای هدر قراردادی هر فایل
    # خوانده می‌شود و شیت‌های کمکی رد می‌شوند.
    if spec.opt("sheet_strategy") == "all_data_sheets":
        skip = {str(x).strip().lower() for x in (spec.opt("skip_sheets") or [])}
        frames = []
        export_frames = []
        for f in targets:
            try:
                # Close the discovery workbook deterministically as well.  Leaving
                # it open is enough to lock a temp file on Windows even if the
                # subsequent read_sheet() instance is correctly closed.
                seen = []
                with pd.ExcelFile(f) as xl:
                    selected_sheets = []
                    for sh in xl.sheet_names:
                        if sh.strip().lower() in skip:
                            continue
                        found = clearance_header(xl, sh)
                        if found["header_row"] is not None:
                            selected_sheets.append((sh, found["header_row"]))
                        else:
                            seen.append(found)
            except Exception as ex:
                log.error(f"❌ [{spec.key}] {os.path.basename(f)}: {ex}")
                continue
            if not selected_sheets:
                gap = clearance_gap_text(os.path.basename(f), seen)
                log.error(f"❌ [{spec.key}] {gap}")
                health.current().schema_gap(spec.key, gap)
            for name, header_row in selected_sheets:
                df = read_sheet(f, name, spec.key, header_row=header_row)
                if df is not None and not df.empty:
                    df["_SOURCE_FILE"] = os.path.basename(f)
                    df["_SOURCE_SHEET"] = name
                    if spec.key == 'clearance' and 'export' in os.path.basename(f).casefold():
                        export_frames.append(df)
                    else:
                        frames.append(df)
        if frames:
            out["main"] = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
            log.info(f"   📚 [{spec.key}] {len(frames)} شیت داده از {len(targets)} فایل "
                     f"ادغام شد — مجموع {len(out['main'])} ردیف")
        if export_frames:
            out['export'] = pd.concat(export_frames, ignore_index=True) if len(export_frames)>1 else export_frames[0]
            log.info('📦 [%s] %d ردیف Export در فریم مستقل نگهداری شد؛ وارد KPI واردات نمی‌شود.',
                     spec.key, len(out['export']))
        return out

    # evidence.txt SAP profiles 0–4. Select the native export when present;
    # retain legacy Data compatibility without falling back to an unrelated sheet.
    if spec.opt("native_sheets"):
        # Large SAP workbooks used to be opened once for discovery and then once
        # again per selected sheet. On the production GS_Full Chain workbook this
        # dominated startup time. Keep one ExcelFile open, parse every contracted
        # native sheet from that handle, then close it deterministically (Windows-safe).
        selected = {}
        for f in targets:
            try:
                with pd.ExcelFile(f) as xl:
                    names = {name.strip().lower(): name for name in xl.sheet_names}
                    present = [names[str(name).lower()] for name in spec.opt("native_sheets")
                               if str(name).lower() in names]
                    for name in present:
                        try:
                            df = xl.parse(name, dtype=str)
                        except Exception as ex:
                            log.error(f"❌ [{spec.key}] خطا در خواندن شیت «{name}» از {os.path.basename(f)}: {ex}")
                            health.current().schema_gap(spec.key, f"native sheet read failed: {name}: {ex}")
                            continue
                        df.columns = [normalize_col_name(c) for c in df.columns]
                        df = df.loc[:, [c for c in df.columns if c != ""]]
                        log.info(f"📥 [{spec.key}] شیت «{name}» خوانده شد — {len(df)} ردیف × {len(df.columns)} ستون")
                        df["_SOURCE_SHEET"] = name
                        df["_SOURCE_FILE"] = os.path.basename(f)
                        df["_SOURCE_ROW"] = range(2, len(df) + 2)
                        selected[name] = df
            except Exception as ex:
                log.error(f"❌ [{spec.key}] {os.path.basename(f)}: {ex}")
                health.current().schema_gap(spec.key, f"native workbook read failed: {ex}")
        if selected:
            return selected

    for sheet in spec.sheets:
        frames = []
        for f in targets:
            df = read_sheet(f, sheet, spec.key)
            if df is not None and not df.empty:
                df["_SOURCE_FILE"] = os.path.basename(f)
                df["_SOURCE_SHEET"] = sheet or "__first__"
                frames.append(df)
        if frames:
            label = sheet or "__first__"
            out[label] = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    return out
