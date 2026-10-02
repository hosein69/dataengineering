# -*- coding: utf-8 -*-
"""GSI — ممیزی دانه‌بندی، افزونگی، کلید کسب‌وکار و کلید اصلی روی همه سورس‌ها.

فقط می‌خواند و گزارش می‌دهد؛ هیچ فایل سورس یا انبار داده اصلی را تغییر نمی‌دهد.
  * فایل‌های سورس فقط خوانده می‌شوند.
  * آداپترهای خود اپ اجرا می‌شوند تا فریم‌ها دقیقاً همان باشند که اپ می‌سازد، ولی هر چیزی که
    آداپترها در انبار داده می‌نویسند به یک انبار موقت در پوشه خروجی همین اسکریپت می‌رود
    (پایان کار پاک می‌شود).
  * انبار داده اصلی (warehouse.sqlite) فقط با حالت فقط‌خواندنی SQLite باز می‌شود.

بخش‌های خروجی (یک فایل Excel):
  ۰ خلاصه یافته‌ها با شدت و تعداد
  ۱ فایل‌ها و شیت‌ها: فایل انتخاب‌شده هر سورس، شیت مورد انتظار هست یا نه، فهرست شیت‌ها
  ۲ هدرها: ستون بی‌نام، هدر تکراری، ستون همیشه خالی، ستون هم‌محتوا با ستون دیگر
  ۳ دانه فریم‌ها: هر فریم آداپتر در برابر کلید اعلام‌شده‌اش (کلید خالی، کلید تکراری، تکراری متناقض)
  ۴ کلیدهای کسب‌وکار: شکل مقدارها و کلیدهایی که فقط با نرمال‌سازی شل در دو سورس به هم می‌رسند
  ۵ جدول‌های انبار: ردیف‌هایی که به‌خاطر کلید تکراری یا کلید ناقص در جدول واقعیت نمی‌نشینند
  ۶ جمعیت گزارش: دانه ردیف‌های گزارش تخت، ضریب تکرار، رابطه‌های بی‌شاهد بارنامه × متریال
  ۷ ستون‌های جدول تخت (اختیاری، mart = yes): دانه اعلام‌شده در برابر دانه واقعی و جمع‌های چندبرابر
  ۸ انبار منتشرشده: نسخه باز تکراری، ناهمخوانی موجودیت و بعد، رابطه‌های چندسورسی و کاردینالیتی
  ۱۰ فروریختگی: احتمال اینکه یک ستون در گروه کلید چند مقدار داشته باشد و فریم تجمیعی فقط یکی را نگه دارد
  ۱۱ واژگان: هر مقدار خام ستون‌هایی که با واژگان rulebook نگاشت می‌شوند؛ مقدار نگاشت‌نشده و سهم مقدار اثرپذیر
  ۱۲ تطبیق: بازشماری مستقل فایل کارشناسان (هر محموله یک بار) در برابر خروجی‌های اپ + گراف ایستای ستون‌ها

اجرا (از پوشه اپ، همان جایی که پوشه gsi هست):
    python grain_audit\\gsi_grain_audit.py
    python grain_audit\\gsi_grain_audit.py --mart            (بخش ۷ هم ساخته شود؛ کندتر)
    python grain_audit\\gsi_grain_audit.py --ini D:\\x\\grain_audit.ini
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
VERSION = "1.1"

# کلید ini → متغیر محیطی که اپ GSI می‌خواند
PATH_KEYS = {
    "foreign": "GSI_FOREIGN",
    "bls": "GSI_BLS",
    "clearance": "GSI_CLEARANCE",
    "hr": "GSI_HR",
    "gs_full_chain": "GSI_GS_FULL_CHAIN",
    "gs_combine": "GSI_GS_COMBINE",
    "esmaeili": "GSI_ESMAEILI",
    "mohamadi": "GSI_MOHAMADI",
}


# ───────────────────────────── پیکربندی ─────────────────────────────
def read_ini(path: Path) -> dict:
    out = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";", "[")):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip().lower()] = v.strip().strip('"')
    return out


def read_env_cmd(path: Path) -> dict:
    """set "GSI_X=..." یا set GSI_X=... از یک GSI_ENV.cmd قدیمی (فقط خوانده می‌شود، اجرا نمی‌شود)."""
    out = {}
    if not path.is_file():
        return out
    for enc in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
            break
        except Exception:
            text = ""
    for line in text.splitlines():
        m = re.match(r'\s*set\s+"?((?:GSI|AIBL)_[A-Z0-9_]+)=([^"\r\n]*)"?\s*$', line, re.I)
        if m:
            out[m.group(1).upper()] = m.group(2).strip()
    return out


def find_app_dir(hint: str) -> Path:
    cands = []
    if hint:
        cands.append(Path(hint))
    cands += [HERE.parent, HERE, HERE.parent.parent, Path.cwd(), Path.cwd() / "app"]
    for c in cands:
        if (c / "gsi" / "__init__.py").is_file():
            return c.resolve()
    raise SystemExit("پوشه اپ (جایی که پوشه gsi هست) پیدا نشد. مقدار app_dir را در grain_audit.ini بنویسید.")


# ───────────────────────────── کمکی‌ها ─────────────────────────────
class Ctx:
    def __init__(self, samples: int, mask: bool):
        self.samples = samples
        self.mask = mask
        self.findings = []          # (شدت, بخش, موضوع, تعداد, توضیح, نمونه)
        self.sheets = {}            # نام شیت → list[dict]
        self.errors = []

    def key(self, v) -> str:
        s = "" if v is None else str(v).replace("\r", "").replace("\n", "⏎")
        if self.mask and s:
            return "#" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]
        return s

    def sample(self, values) -> str:
        vals = []
        for v in values:
            if isinstance(v, tuple):
                v = " | ".join(self.key(x) for x in v)
            else:
                v = self.key(v)
            if v not in vals:
                vals.append(v)
            if len(vals) >= self.samples:
                break
        return " ؛ ".join(vals)

    def find(self, severity, section, subject, count, note, sample=""):
        self.findings.append({"شدت": severity, "بخش": section, "موضوع": subject,
                              "تعداد": count, "توضیح": note, "نمونه": sample})

    def add(self, sheet, row: dict):
        self.sheets.setdefault(sheet, []).append(row)

    def fail(self, where, ex):
        msg = f"{where}: {type(ex).__name__}: {ex}"
        self.errors.append({"کجا": where, "خطا": f"{type(ex).__name__}: {ex}",
                            "جزئیات": traceback.format_exc()[-1500:]})
        print("   ⚠️ " + msg)


SEV_ORDER = {"بحرانی": 0, "بالا": 1, "متوسط": 2, "پایین": 3, "اطلاع": 4}
JUNK_HEADER = re.compile(r"^(unnamed[:_ ]?\s*\d+|__unnamed_\d+|column\d+|\d+)$|(\.\d+|__\d+)$", re.I)
LOCATION_COLS = {"_SOURCE_ROW", "_SOURCE_FILE", "_SOURCE_FILE_ID", "_SOURCE_SHEET", "MOGH_ROW_NO",
                 "SAP_SOURCE_ROW", "MOGH_SOURCE_ROWS"}


def clean(v) -> str:
    if v is None:
        return ""
    try:
        import pandas as pd
        if v is pd.NA:
            return ""
    except Exception:
        pass
    t = str(v).strip()
    return "" if t.lower() in {"nan", "none", "<na>", "nat"} else t


def shape(v: str) -> str:
    s = re.sub(r"[0-9]", "9", v)
    s = re.sub(r"[A-Za-z]", "A", s)
    s = re.sub(r"[\u0600-\u06FF]", "ف", s)
    s = re.sub(r"(.)\1{2,}", lambda m: m.group(1) + "{" + str(len(m.group(0))) + "}", s)
    return s


def loose(v: str) -> str:
    s = str(v).upper()
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"\.0$", "", s)
    s = re.sub(r"[^0-9A-Z]", "", s)
    return s.lstrip("0") or s


def col_signature(series) -> str:
    import pandas as pd
    vals = series.map(clean)
    return hashlib.sha1("\x1f".join(vals.tolist()).encode("utf-8")).hexdigest()


def profile_columns(df, where: str, ctx: Ctx, sheet: str, extra: dict):
    """ستون خالی، ستون هم‌محتوا، هدر بی‌نام و هدر تکراری."""
    import pandas as pd
    headers = [str(c) for c in df.columns]
    norm = Counter(re.sub(r"\s+", " ", h).strip().lower() for h in headers)
    sig_of = {}
    empties, junk, dups, twins = [], [], [], []
    for i, c in enumerate(df.columns):
        h = headers[i]
        s = df.iloc[:, i]
        vals = s.map(clean)
        nonempty = int((vals != "").sum())
        distinct = int(vals[vals != ""].nunique())
        sig = col_signature(s) if nonempty else ""
        twin = sig_of.get(sig, "") if sig else ""
        if sig and not twin:
            sig_of[sig] = h
        is_junk = bool(JUNK_HEADER.search(h.strip())) or not h.strip()
        is_dup = norm[re.sub(r"\s+", " ", h).strip().lower()] > 1
        if nonempty == 0:
            empties.append(h)
        if is_junk:
            junk.append(h)
        if is_dup:
            dups.append(h)
        if twin:
            twins.append(f"{h} = {twin}")
        ctx.add(sheet, {**extra, "ستون": h, "ردیف پر": nonempty, "مقدار یکتا": distinct,
                        "همیشه خالی": nonempty == 0, "هدر بی‌نام/مکانیکی": is_junk,
                        "هدر تکراری": is_dup, "هم‌محتوا با": twin})
    return empties, junk, dups, twins


# ───────────────────────────── ۱ و ۲: فایل‌ها، شیت‌ها و هدرها ─────────────────────────────
def audit_files(ctx: Ctx):
    import pandas as pd
    from gsi.config.sources import SOURCES
    from gsi.dataio.reader import find_files
    print("۱) فایل‌ها، شیت‌ها و هدرها ...")
    for key, spec in SOURCES.items():
        try:
            files = find_files(spec, quiet=True)
            used = files if spec.multi_file else files[:1]
            base = {"سورس": key, "پوشه": spec.folder, "پوشه هست": os.path.isdir(spec.folder or ""),
                    "الگو": spec.pattern, "الزامی": bool(spec.required),
                    "فایل‌های منطبق": len(files),
                    "فایل‌های منطبق (جدیدترین اول)": " ؛ ".join(os.path.basename(f) for f in files[:6])}
            if not files:
                ctx.add("1_فایل_و_شیت", {**base, "فایل خوانده‌شده": "", "شیت مورد انتظار": ", ".join(map(str, spec.sheets)),
                                          "شیت پیدا شد": False, "شیت‌های فایل": ""})
                ctx.find("بالا" if spec.required else "متوسط", "فایل", f"{key}: فایل پیدا نشد", 0,
                         f"در {spec.folder} فایلی با الگوی {spec.pattern} نیست.")
                continue
            if not spec.multi_file and len(files) > 1:
                ctx.find("متوسط", "فایل", f"{key}: چند فایل با یک الگو", len(files),
                         "اپ فقط جدیدترین فایل را می‌خواند؛ فایل اضافه (مثلاً کپی) می‌تواند جای فایل اصلی را بگیرد.",
                         " ؛ ".join(os.path.basename(f) for f in files[:4]))
            for f in used[:5]:
                try:
                    with pd.ExcelFile(f) as xl:
                        names = list(xl.sheet_names)
                        for want in spec.sheets:
                            if want is None:
                                target = names[0] if names else None
                            else:
                                target = want if want in names else {n.strip().lower(): n for n in names}.get(str(want).strip().lower())
                            ctx.add("1_فایل_و_شیت", {**base, "فایل خوانده‌شده": os.path.basename(f),
                                                     "تاریخ فایل": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M"),
                                                     "شیت مورد انتظار": str(want), "شیت پیدا شد": target is not None,
                                                     "شیت‌های فایل": " ؛ ".join(names)})
                            if target is None:
                                import difflib
                                low = {n.strip().lower() for n in names}
                                alt_found = any(o is not None and o != want and o.strip().lower() in low and
                                                difflib.SequenceMatcher(None, str(want).lower(), o.lower()).ratio() > 0.85
                                                for o in spec.sheets)
                                if alt_found:
                                    continue      # نام جایگزین همین شیت (مثل License/Licence) پیدا شده است
                                if len(spec.sheets) == 1:
                                    ctx.find("بحرانی", "فایل", f"{key}: شیت «{want}» در فایل نیست", 1,
                                             f"فایل {os.path.basename(f)} شیت‌های {names} را دارد. سورس هیچ داده‌ای نمی‌دهد و "
                                             f"انتشار با SOURCE_SCHEMA_CONTRACT_BROKEN بسته می‌شود.")
                                else:
                                    ctx.find("بالا", "فایل", f"{key}: شیت «{want}» در فایل نیست", 1,
                                             f"فایل {os.path.basename(f)} شیت‌های {names} را دارد؛ فریم این شیت ساخته نمی‌شود.")
                                continue
                            raw = xl.parse(target, header=None, dtype=str)
                            if raw.empty:
                                continue
                            filled = raw.head(20).notna().sum(axis=1)
                            best = int(filled.idxmax())
                            df = raw.iloc[1:].copy()
                            df.columns = [("" if pd.isna(x) else str(x)) for x in raw.iloc[0].tolist()]
                            df = df.dropna(how="all")
                            empties, junk, dups, twins = profile_columns(
                                df, key, ctx, "2_هدرها", {"سورس": key, "فایل": os.path.basename(f), "شیت": target})
                            ctx.add("2_هدرها_خلاصه", {"سورس": key, "فایل": os.path.basename(f), "شیت": target,
                                                      "ردیف": len(df), "ستون": df.shape[1],
                                                      "ردیف هدر در اپ": 1, "پرترین ردیف ۲۰ ردیف اول": best + 1,
                                                      "هدر بی‌نام/مکانیکی": len(junk), "هدر تکراری": len(dups),
                                                      "ستون همیشه خالی": len(empties), "ستون هم‌محتوا": len(twins),
                                                      "نمونه بی‌نام": " ؛ ".join(junk[:6]),
                                                      "نمونه تکراری": " ؛ ".join(dups[:6]),
                                                      "نمونه هم‌محتوا": " ؛ ".join(twins[:6])})
                            if junk:
                                ctx.find("متوسط", "هدر", f"{key}/{target}: هدر بی‌نام یا مکانیکی", len(junk),
                                         "ستون بدون عنوان در فایل؛ pandas نامی مثل Unnamed: 12 می‌سازد.", " ؛ ".join(junk[:6]))
                            if dups:
                                ctx.find("بالا", "هدر", f"{key}/{target}: هدر تکراری", len(dups),
                                         "دو ستون با یک نام؛ کدام خوانده می‌شود به ترتیب بستگی دارد.", " ؛ ".join(dups[:6]))
                            if twins:
                                ctx.find("پایین", "هدر", f"{key}/{target}: ستون هم‌محتوا", len(twins),
                                         "دو ستون با مقدار یکسان در همه ردیف‌ها (افزونگی).", " ؛ ".join(twins[:4]))
                            if best != 0 and filled.iloc[best] > filled.iloc[0] * 1.5:
                                ctx.find("متوسط", "هدر", f"{key}/{target}: ردیف هدر شاید ردیف ۱ نباشد", 1,
                                         f"پرترین ردیف ردیف {best + 1} است؛ اپ برای این سورس ردیف ۱ را هدر می‌گیرد.")
                except Exception as ex:
                    ctx.fail(f"فایل {key}: {os.path.basename(f)}", ex)
        except Exception as ex:
            ctx.fail(f"سورس {key}", ex)


# ───────────────────────────── بارگذاری آداپترها ─────────────────────────────
def load_frames(ctx: Ctx):
    from gsi.adapters import discover
    print("۲) اجرای آداپترهای اپ (خواندن کامل سورس‌ها) ...")
    sources, timing = {}, {}
    for key, cls in discover().items():
        t0 = time.time()
        try:
            sources[key] = cls().load() or {}
        except Exception as ex:
            sources[key] = {}
            ctx.fail(f"آداپتر {key}", ex)
            ctx.find("بالا", "آداپتر", f"{key}: آداپتر خطا داد", 1, f"{type(ex).__name__}: {str(ex)[:300]}")
        timing[key] = round(time.time() - t0, 1)
        n = sum(len(v) for v in sources[key].values() if hasattr(v, "__len__"))
        print(f"   {key:16s} {len(sources[key])} فریم، {n} ردیف، {timing[key]}s")
    return sources, timing


# ───────────────────────────── ۳: دانه فریم‌ها ─────────────────────────────
BUILTIN_KEYS = {
    "moghavemat/main": ["KEY_ORDER", "KEY_MATERIAL"],
    "moghavemat/inventory": ["KEY_ORDER", "KEY_MATERIAL"],
    "moghavemat/order_material_pr_item": ["KEY_ORDER", "KEY_MATERIAL", "KEY_PR", "MOGH_PR_ITEM"],
}


def declared_keys(app: Path) -> dict:
    import yaml
    p = app / "gsi" / "config" / "source_keys.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out = {k: dict(v or {}) for k, v in (data.get("frames") or {}).items()}
    for k, v in BUILTIN_KEYS.items():
        out.setdefault(k, {"keys": v, "role": "summary", "builtin": True})
    return out


def audit_frames(sources, specs, ctx: Ctx):
    import pandas as pd
    print("۳) دانه فریم‌ها ...")
    for src, frames in sources.items():
        for name, df in frames.items():
            if not isinstance(df, pd.DataFrame):
                continue
            fk = f"{src}/{name}"
            spec = specs.get(fk, {})
            keys = list(spec.get("keys") or [])
            row = {"فریم": fk, "ردیف": len(df), "ستون": df.shape[1], "کلید اعلام‌شده": " + ".join(keys) or "(ندارد)",
                   "نقش": spec.get("role", "rows")}
            junk = [c for c in df.columns if JUNK_HEADER.search(str(c)) and str(c) not in LOCATION_COLS]
            empty = [c for c in df.columns if df[c].map(clean).eq("").all()] if len(df) else []
            row["ستون مکانیکی/بی‌نام"] = len(junk)
            row["ستون همیشه خالی"] = len(empty)
            row["نمونه ستون مکانیکی"] = " ؛ ".join(map(str, junk[:6]))
            if junk:
                ctx.find("متوسط", "هدر", f"{fk}: ستون مکانیکی وارد فریم اپ شده", len(junk),
                         "ستون بی‌نام فایل تا فریم استاندارد اپ رسیده است.", " ؛ ".join(map(str, junk[:6])))
            if not keys or df.empty:
                ctx.add("3_دانه_فریم", row)
                continue
            missing = [k for k in keys if k not in df.columns]
            row["ستون کلید غایب"] = ", ".join(missing)
            if missing:
                ctx.find("بالا", "کلید اصلی", f"{fk}: ستون کلید در فریم نیست", len(missing),
                         "کلید اعلام‌شده در source_keys.yaml ساخته نشده است.", ", ".join(missing))
                ctx.add("3_دانه_فریم", row)
                continue
            kv = pd.DataFrame({k: df[k].map(clean) for k in keys})
            blank_any = kv.eq("").any(axis=1)
            blank_all = kv.eq("").all(axis=1)
            keyed = kv[~blank_any]
            dup_mask = keyed.duplicated(keep=False)
            groups = keyed[dup_mask].groupby(keys, sort=False).size() if dup_mask.any() else pd.Series(dtype=int)
            content_cols = [c for c in df.columns if str(c) not in LOCATION_COLS]
            conflicting, conf_cols, conf_samples = 0, Counter(), []
            if dup_mask.any():
                sub = df.loc[keyed.index[dup_mask]]
                subk = keyed[dup_mask]
                for kt, idx in subk.groupby(keys, sort=False).groups.items():
                    part = sub.loc[idx, content_cols].astype(str)
                    diff = [c for c in content_cols if part[c].nunique(dropna=False) > 1]
                    if diff:
                        conflicting += 1
                        conf_cols.update(diff)
                        if len(conf_samples) < ctx.samples:
                            conf_samples.append(kt if isinstance(kt, tuple) else (kt,))
            row.update({"ردیف با کلید ناقص": int(blank_any.sum()), "ردیف بی‌کلید کامل": int(blank_all.sum()),
                        "کلید تکراری (گروه)": int(len(groups)), "ردیف در گروه تکراری": int(dup_mask.sum()),
                        "گروه تکراری متناقض": conflicting,
                        "ستون‌های متفاوت در تکراری‌ها": " ؛ ".join(f"{c}({n})" for c, n in conf_cols.most_common(8)),
                        "نمونه کلید تکراری": ctx.sample(conf_samples or list(groups.index[: ctx.samples]))})
            ctx.add("3_دانه_فریم", row)
            summary = spec.get("role") == "summary"
            if len(groups):
                sev = "بالا" if summary and conflicting else ("متوسط" if conflicting else "پایین")
                ctx.find(sev, "دانه", f"{fk}: کلید اعلام‌شده یکتا نیست", int(len(groups)),
                         (f"{conflicting} گروه محتوای متفاوت دارند؛ ستون‌های متفاوت: "
                          + ", ".join(c for c, _ in conf_cols.most_common(5))) if conflicting else
                         "ردیف‌های هم‌کلید محتوای یکسان دارند (تکرار کامل).",
                         row["نمونه کلید تکراری"])
            if blank_any.any() and summary:
                ctx.find("متوسط", "کلید اصلی", f"{fk}: ردیف با کلید ناقص", int(blank_any.sum()),
                         "بخشی از کلید خالی است؛ این ردیف‌ها در جدول‌های کلیددار انبار نمی‌نشینند.")


# ───────────────────────────── ۴: کلیدهای کسب‌وکار ─────────────────────────────
ENTITY_COLS = {"ORDER": ["KEY_ORDER"], "MATERIAL": ["KEY_MATERIAL", "SAP_PO_MATERIAL"], "BL": ["KEY_BL"],
               "REG": ["KEY_REG", "NTSW_KEY_REG", "SATA_KEY_REG", "FX_KEY_REG", "CRD_KEY_REG", "IL_KEY_REG"],
               "REG_FILE": ["KEY_REG_FILE"], "PR": ["KEY_PR", "SAP_PO_PR"], "PO": ["KEY_PO"],
               "EMP": ["KEY_EMP", "MOGH_KEY_EMP"]}
# نرمال‌ساز مرجع هر موجودیت (همان تابع‌های خود اپ)؛ مقداری که با آن عوض شود یعنی این فریم
# کلید را با قاعده دیگری ساخته و با سورس‌های دیگر جفت نمی‌شود.
REF_NORMALIZER = {"ORDER": "clean_order_ref", "MATERIAL": "clean_part_no", "BL": "clean_bl",
                  "PR": "clean_key", "PO": "clean_key", "REG": "clean_key", "REG_FILE": "clean_key",
                  "EMP": "clean_employee_code"}
EXPECT = {"REG": re.compile(r"^\d{8}$")}
PLACEHOLDER = re.compile(r"^(0+|-+|\*+|N/?A|NULL|\?+|.)$", re.I)


def audit_keys(sources, ctx: Ctx):
    import pandas as pd
    print("۴) کلیدهای کسب‌وکار ...")
    for ent, cols in ENTITY_COLS.items():
        by_src = {}
        for src, frames in sources.items():
            for name, df in frames.items():
                if not isinstance(df, pd.DataFrame) or df.empty:
                    continue
                for col in cols:
                    if col not in df.columns:
                        continue
                    vals = df[col].map(clean)
                    vals = vals[vals != ""]
                    if vals.empty:
                        continue
                    uniq = pd.Series(vals.unique())
                    shapes = Counter(uniq.map(shape))
                    flags = {
                        "فاصله داخلی": int(uniq.str.contains(r"\s").sum()),
                        "حرف کوچک": int(uniq.str.contains(r"[a-z]").sum()),
                        "صفر ابتدایی": int(uniq.str.match(r"^0\d").sum()),
                        "پسوند .0": int(uniq.str.endswith(".0").sum()),
                        "رقم فارسی/عربی": int(uniq.str.contains(r"[۰-۹٠-٩]").sum()),
                        "خط تیره/اسلش": int(uniq.str.contains(r"[-/\\]").sum()),
                    }
                    bad = int((~uniq.map(lambda v: bool(EXPECT[ent].match(v)))).sum()) if ent in EXPECT else 0
                    placeholders = uniq[uniq.map(lambda v: bool(PLACEHOLDER.match(v)))]
                    changed = pd.Series([], dtype=object)
                    try:
                        import gsi.core.text as T
                        fn = getattr(T, REF_NORMALIZER.get(ent, ""), None)
                        if fn is not None:
                            normed = uniq.map(lambda v: fn(v) or "")
                            changed = uniq[normed != uniq]
                    except Exception as ex:
                        ctx.fail(f"نرمال‌ساز {ent}", ex)
                    flags["مقدار جانگهدار (0، -، ...)"] = int(len(placeholders))
                    flags["عوض می‌شود با نرمال‌ساز مرجع"] = int(len(changed))
                    ctx.add("4_کلید_کسب‌وکار", {"موجودیت": ent, "فریم": f"{src}/{name}", "ستون": col,
                                                "مقدار یکتا": len(uniq),
                                                "شکل‌های رایج": " ؛ ".join(f"{s}×{n}" for s, n in shapes.most_common(5)),
                                                "تعداد شکل": len(shapes), **flags,
                                                "خارج از الگوی مجاز": bad,
                                                "نمونه": ctx.sample(uniq.head(ctx.samples))})
                    if ent in EXPECT and bad:
                        ctx.find("متوسط", "کلید کسب‌وکار", f"{ent} در {src}/{name}.{col}: خارج از الگو", bad,
                                 "کد ثبت سفارش باید ۸ رقم باشد؛ این مقدارها در جمعیت گزارش کنار می‌روند.",
                                 ctx.sample(uniq[~uniq.map(lambda v: bool(EXPECT[ent].match(v)))].head(ctx.samples)))
                    if len(placeholders):
                        ctx.find("بالا", "کلید کسب‌وکار", f"{ent} در {src}/{name}.{col}: مقدار جانگهدار به‌جای کلید",
                                 int(len(placeholders)),
                                 "مقداری مثل 0 یا - کلید واقعی نیست؛ اگر کلید حساب شود همه ردیف‌های آن به هم وصل می‌شوند (ضرب دکارتی).",
                                 ctx.sample(placeholders.head(ctx.samples)))
                    if len(changed):
                        ctx.find("بالا", "کلید کسب‌وکار", f"{ent} در {src}/{name}.{col}: با قاعده مرجع پاک نشده", int(len(changed)),
                                 f"{REF_NORMALIZER.get(ent)} این مقدارها را عوض می‌کند؛ همان کلید در سورس دیگر به شکل دیگری است.",
                                 ctx.sample([(v, fn(v)) for v in changed.head(ctx.samples)]))
                    if col.startswith("KEY_"):
                        by_src.setdefault(src, set()).update(uniq.tolist())
        # همان موجودیت در دو سورس با دو شکل متفاوت
        if len(by_src) < 2:
            continue
        loose_map = defaultdict(lambda: defaultdict(set))
        for src, keys in by_src.items():
            for k in keys:
                loose_map[loose(k)][src].add(k)
        mism, samples = 0, []
        pair_counts = Counter()
        for lk, per in loose_map.items():
            forms = set().union(*per.values())
            if len(per) >= 2 and len(forms) > 1:
                exact_shared = set.intersection(*[set(v) for v in per.values()])
                if not exact_shared:
                    mism += 1
                    srcs = sorted(per)
                    pair_counts[" ↔ ".join(srcs[:2])] += 1
                    if len(samples) < ctx.samples:
                        samples.append(tuple(sorted(forms))[:3])
        srcs = sorted(by_src)
        for i, a in enumerate(srcs):
            for b in srcs[i + 1:]:
                ea = by_src[a] & by_src[b]
                la = {loose(x) for x in by_src[a]} & {loose(x) for x in by_src[b]}
                ctx.add("4_هم‌پوشانی_سورس‌ها", {"موجودیت": ent, "سورس الف": a, "سورس ب": b,
                                              "یکتای الف": len(by_src[a]), "یکتای ب": len(by_src[b]),
                                              "مشترک دقیق": len(ea), "مشترک با نرمال‌سازی شل": len(la),
                                              "فقط با نرمال‌سازی شل": len(la) - len(ea)})
        if mism:
            ctx.find("بالا", "کلید کسب‌وکار", f"{ent}: یک کلید با دو شکل در دو سورس", mism,
                     "بعد از حذف فاصله، خط تیره، صفر ابتدایی و .0 یکی می‌شوند ولی دقیقاً یکی نیستند؛ رابطه ساخته نمی‌شود "
                     "یا دو موجودیت جدا ساخته می‌شود. پرتکرارترین جفت‌ها: "
                     + ", ".join(f"{k}({n})" for k, n in pair_counts.most_common(4)),
                     ctx.sample(samples))


# ───────────────────────────── ۵: جدول‌های واقعیت انبار ─────────────────────────────
FACT_KEYS = {
    "dwh_fact_supply_position": (["KEY_ORDER", "KEY_MATERIAL"], 2),
    "dwh_bridge_order_material_pr_item": (["KEY_ORDER", "KEY_MATERIAL", "KEY_PR", "MOGH_PR_ITEM"], 3),
    "dwh_fact_sap_pr_item": (["KEY_PR", "SAP_PR_ITEM"], 1),
    "dwh_fact_sap_po_item": (["KEY_PO", "SAP_PO_ITEM"], 1),
    "dwh_fact_oracle_material": (["KEY_MATERIAL"], 1),
    "dwh_fact_ntsw_allocation_request": (["NTSW_REQUEST_KEY"], 1),
    "dwh_fact_ntsw_commitment": (["KEY_REG"], 1),
}


def audit_facts(sources, ctx: Ctx):
    import pandas as pd
    print("۵) جدول‌های واقعیت انبار ...")
    try:
        from gsi.warehouse.business_dwh import FACT_INPUTS, TABLES
    except Exception as ex:
        ctx.fail("business_dwh", ex)
        return
    for table, (src, frame) in FACT_INPUTS.items():
        df = (sources.get(src) or {}).get(frame)
        spec = TABLES.get(table)
        pk = " + ".join(spec.keys) if spec else ""
        if not isinstance(df, pd.DataFrame) or df.empty:
            ctx.add("5_جدول_انبار", {"جدول": table, "فریم ورودی": f"{src}/{frame}", "کلید جدول": pk, "ردیف ورودی": 0})
            continue
        if table not in FACT_KEYS:
            ctx.add("5_جدول_انبار", {"جدول": table, "فریم ورودی": f"{src}/{frame}", "کلید جدول": pk,
                                     "ردیف ورودی": len(df),
                                     "توضیح": "کلید از محتوای ردیف ساخته می‌شود؛ ویرایش یک رویداد، رویداد تازه می‌سازد نه نسخه تازه."})
            continue
        cols, required = FACT_KEYS[table]
        kv = pd.DataFrame({c: (df[c].map(clean) if c in df.columns else pd.Series("", index=df.index)) for c in cols})
        if table == "dwh_fact_ntsw_allocation_request":
            reg = df["KEY_REG"].map(clean) if "KEY_REG" in df.columns else pd.Series("", index=df.index)
            ok = kv[cols[0]].ne("") & reg.ne("")
        else:
            ok = kv[cols[:required]].ne("").all(axis=1)
        kept = kv[ok]
        dup = kept.duplicated(keep=False)
        lost = int(kept.duplicated(keep="last").sum())
        content_cols = [c for c in df.columns if str(c) not in LOCATION_COLS]
        conflicting, samples = 0, []
        if dup.any():
            sub = df.loc[kept.index[dup], content_cols].astype(str)
            for kt, idx in kept[dup].groupby(cols, sort=False).groups.items():
                if len(sub.loc[idx].drop_duplicates()) > 1:
                    conflicting += 1
                    if len(samples) < ctx.samples:
                        samples.append(kt if isinstance(kt, tuple) else (kt,))
        ctx.add("5_جدول_انبار", {"جدول": table, "فریم ورودی": f"{src}/{frame}", "کلید جدول": pk,
                                 "ردیف ورودی": len(df), "ردیف با کلید ناقص (نمی‌نشیند)": int((~ok).sum()),
                                 "کلید یکتا": int(len(kept.drop_duplicates())),
                                 "ردیف جاافتاده (آخری می‌ماند)": lost, "کلید تکراری متناقض": conflicting,
                                 "نمونه": ctx.sample(samples)})
        if lost:
            ctx.find("بحرانی" if conflicting else "متوسط", "کلید اصلی",
                     f"{table}: کلید جدول از دانه فریم درشت‌تر است", lost,
                     f"{lost} ردیف از {src}/{frame} هم‌کلید ردیف دیگری‌اند و فقط آخری در انبار می‌ماند"
                     + (f"؛ {conflicting} کلید محتوای متفاوت دارند (داده از دست می‌رود)." if conflicting else "."),
                     ctx.sample(samples))
        if (~ok).any():
            ctx.find("پایین", "کلید اصلی", f"{table}: ردیف با کلید ناقص", int((~ok).sum()),
                     f"این ردیف‌های {src}/{frame} در جدول واقعیت نیستند (فقط در سوابق منبع).")


# ───────────────────────────── ۶: جمعیت گزارش ─────────────────────────────
def audit_population(sources, ctx: Ctx):
    import pandas as pd
    print("۶) جمعیت گزارش تخت ...")
    try:
        from gsi.resolve.population import build_primary_population
        from gsi.resolve.registration_bridge import build_ntsw_order_reg_bridge
        from gsi.studio_core.grain import fanout
    except Exception as ex:
        ctx.fail("import population", ex)
        return None
    try:
        bridge, amb = build_ntsw_order_reg_bridge(sources)
        if isinstance(bridge, pd.DataFrame) and not bridge.empty and "KEY_ORDER" in bridge.columns:
            b = bridge.copy()
            b["_o"] = b["KEY_ORDER"].map(clean)
            b["_r"] = b.get("NTSW_KEY_REG", pd.Series("", index=b.index)).map(clean)
            multi = b[b["_o"].ne("")].groupby("_o")["_r"].nunique()
            multi = multi[multi > 1]
            ctx.add("6_جمعیت", {"شاخص": "سفارش با بیش از یک ثبت سفارش در پل NTSW", "مقدار": int(len(multi)),
                                "توضیح": "جمعیت فقط اولی را نگه می‌دارد (drop_duplicates روی سفارش).",
                                "نمونه": ctx.sample(multi.index[: ctx.samples])})
            if len(multi):
                ctx.find("بالا", "رابطه", "سفارش با چند ثبت سفارش: فقط اولی به ردیف گزارش می‌رسد", int(len(multi)),
                         "بقیه ثبت سفارش‌ها به‌صورت پرونده جدا بدون سفارش می‌آیند یا اصلاً نمی‌آیند.",
                         ctx.sample(multi.index[: ctx.samples]))
        ctx.add("6_جمعیت", {"شاخص": "نگاشت مبهم سفارش ↔ ثبت سفارش (حدس زده نشد)",
                            "مقدار": int(len(amb)) if isinstance(amb, pd.DataFrame) else 0})
    except Exception as ex:
        ctx.fail("پل NTSW", ex)
    try:
        base, diag, meta = build_primary_population(sources)
    except Exception as ex:
        ctx.fail("جمعیت اصلی", ex)
        return None
    for k, v in (meta or {}).items():
        ctx.add("6_جمعیت", {"شاخص": k, "مقدار": v})
    role = base.get("MOGH_ITEM_ROLE", pd.Series("", index=base.index)).fillna("").astype(str)
    for r, n in role.value_counts().items():
        ctx.add("6_جمعیت", {"شاخص": f"نقش ردیف {r or '(خالی)'}", "مقدار": int(n)})
    try:
        for rec in fanout(base).to_dict("records"):
            ctx.add("6_ضریب_تکرار", rec)
    except Exception as ex:
        ctx.fail("fanout", ex)
    o = base.get("KEY_ORDER", pd.Series("", index=base.index)).map(clean)
    m = base.get("KEY_MATERIAL", pd.Series("", index=base.index)).map(clean)
    bl = base.get("KEY_BL", pd.Series("", index=base.index)).map(clean)
    dups = pd.DataFrame({"o": o, "m": m, "b": bl}).duplicated(keep=False)
    ctx.add("6_جمعیت", {"شاخص": "ردیف با (سفارش، متریال، بارنامه) تکراری", "مقدار": int(dups.sum()),
                        "نمونه": ctx.sample(list(zip(o[dups], m[dups], bl[dups]))[: ctx.samples])})
    if dups.any():
        ctx.find("بالا", "دانه", "ردیف تکراری در جمعیت گزارش", int(dups.sum()),
                 "دو ردیف با همان سفارش، متریال و بارنامه؛ شمارش و جمع ردیفی دوبرابر می‌شود.",
                 ctx.sample(list(zip(o[dups], m[dups], bl[dups]))[: ctx.samples]))
    work = pd.DataFrame({"o": o, "m": m, "b": bl, "role": role})
    work = work[work.o.ne("")]
    mats = work.groupby("o")["m"].nunique()
    bls = work[work.b.ne("")].groupby("o")["b"].nunique()
    both = sorted(set(mats[mats > 1].index) & set(bls[bls >= 1].index))
    unproven = int(work[work.o.isin(both) & work.b.ne("")].shape[0])
    ctx.add("6_جمعیت", {"شاخص": "سفارش چندمتریاله که بارنامه دارد", "مقدار": len(both),
                        "توضیح": "بارنامه‌ها فقط روی ردیف متریال اول می‌نشینند؛ اینکه آن بارنامه همان متریال را حمل کرده شاهد ندارد.",
                        "نمونه": ctx.sample(both[: ctx.samples])})
    if both:
        ctx.find("بالا", "رابطه", "رابطه بارنامه × متریال بی‌شاهد در ردیف‌های گزارش", unproven,
                 f"در {len(both)} سفارش چندمتریاله، {unproven} ردیف بارنامه به متریال اول سفارش چسبیده است؛ "
                 "ستون‌هایی مثل «متریال بحرانی بارنامه» روی این ردیف‌ها رابطه‌ای را نشان می‌دهند که سورس نگفته است.",
                 ctx.sample(both[: ctx.samples]))
    multi_bl = bls[bls > 1]
    ctx.add("6_جمعیت", {"شاخص": "سفارش با چند بارنامه (ردیف سفارش تکرار می‌شود)", "مقدار": int(len(multi_bl))})
    return base


# ───────────────────────────── ۷: ستون‌های جدول تخت ─────────────────────────────
def audit_mart(sources, ctx: Ctx):
    import numpy as np
    import pandas as pd
    print("۷) ساخت جدول تخت با مرحله‌های اپ (بدون انتشار) ...")
    try:
        from gsi.pipeline import Pipeline
        from gsi.studio_core.grain import column_grain, prefix_grain_map, GRAIN_KEYS, fanout, safe_agg
        p = Pipeline()
        p.sources = sources
        p.ctx.sources = sources
        df = p.build_base()
        df = p.run_stages(df)
    except Exception as ex:
        ctx.fail("جدول تخت", ex)
        return None
    analyze_mart(df, ctx)
    return df


def analyze_mart(df, ctx: Ctx):
    import pandas as pd
    from gsi.studio_core.grain import column_grain, prefix_grain_map, fanout, safe_agg
    pm = prefix_grain_map()
    try:
        for rec in fanout(df).to_dict("records"):
            ctx.add("7_ضریب_تکرار_تخت", rec)
    except Exception as ex:
        ctx.fail("fanout تخت", ex)
    grains = {"ثبت سفارش": ["KEY_REG"], "سفارش": ["KEY_ORDER"], "بارنامه": ["KEY_BL"],
              "سفارش×متریال": ["KEY_ORDER", "KEY_MATERIAL"]}
    const = {}
    for gname, keys in grains.items():
        if any(k not in df.columns for k in keys):
            continue
        kv = df[keys].astype(str).apply(lambda s: s.str.strip())
        mask = (kv != "").all(axis=1) & ~kv.isin(["nan", "None", "<NA>"]).any(axis=1)
        sub = df[mask]
        if sub.empty:
            continue
        g = sub.groupby([sub[k].astype(str).str.strip() for k in keys], sort=False)
        sizes = g.size()
        multi_groups = sizes[sizes > 1]
        if multi_groups.empty:
            continue
        const[gname] = (g, multi_groups)
    rows = []
    cols = list(df.columns)
    seen_sig = {}
    for c in cols:
        s = df[c]
        vals = s.map(clean)
        nonempty = int((vals != "").sum())
        num = pd.to_numeric(s, errors="coerce")
        ident = str(c).startswith(("KEY_", "CANONICAL_")) or bool(re.search(r"(_KEY|_NO|_ID|_CODE|_REG|_BL)$", str(c)))
        is_num = (not ident) and num.notna().sum() > 0 and num.notna().sum() >= 0.8 * max(nonempty, 1)
        sig = col_signature(s) if nonempty else ""
        twin = seen_sig.get(sig, "") if sig else ""
        if sig and not twin:
            seen_sig[sig] = c
        try:
            declared = column_grain(c, pm)
        except Exception:
            declared = "?"
        rec = {"ستون": c, "ردیف پر": nonempty, "مقدار یکتا": int(vals[vals != ""].nunique()),
               "عددی": bool(is_num), "دانه اعلام‌شده": declared, "هم‌محتوا با": twin,
               "همیشه خالی": nonempty == 0, "ثابت": int(vals[vals != ""].nunique()) == 1}
        coarsest = ""
        for gname in ("ثبت سفارش", "سفارش", "بارنامه", "سفارش×متریال"):
            if gname not in const or nonempty == 0:
                continue
            g, multi_groups = const[gname]
            try:
                nun = g[c].agg(lambda x: x.map(clean).nunique())
                share = float((nun.loc[multi_groups.index] <= 1).mean())
            except Exception:
                continue
            rec[f"ثابت در هر {gname} (٪)"] = round(100 * share, 1)
            if share >= 0.99 and not coarsest:
                coarsest = gname
        rec["دانه واقعی (درشت‌ترین)"] = coarsest or "ردیف"
        if is_num and nonempty:
            try:
                app_sum = float(safe_agg(df, c, "sum", pm))
            except Exception:
                app_sum = float("nan")
            if coarsest:
                keys = grains[coarsest]
                kv = df[keys].astype(str).apply(lambda s_: s_.str.strip())
                keyed = (kv != "").all(axis=1) & ~kv.isin(["nan", "None", "<NA>"]).any(axis=1)
                part = pd.concat([df[keyed].drop_duplicates(subset=keys), df[~keyed]])
                true_sum = float(pd.to_numeric(part[c], errors="coerce").sum())
            else:
                true_sum = float(num.sum())
            rec["جمع ردیفی"] = round(float(num.sum()), 2)
            rec["جمع اپ (safe_agg)"] = round(app_sum, 2)
            rec["جمع درست (دانه واقعی)"] = round(true_sum, 2)
            if app_sum == app_sum and abs(app_sum - true_sum) > max(1e-6, 0.005 * abs(true_sum)):
                rec["خطر جمع چندبرابر"] = True
        rows.append(rec)
    for r in rows:
        ctx.add("7_ستون_جدول_تخت", r)
    risky = [r["ستون"] for r in rows if r.get("خطر جمع چندبرابر")]
    if risky:
        ctx.find("بالا", "دانه", "ستون عددی که جمع اپ با جمع درست یکی نیست", len(risky),
                 "جمع «بی‌دوباره‌شماری» خود اپ (safe_agg) با جمع روی دانه واقعی ستون فرق دارد؛ "
                 "یعنی دانه ثبت‌شده برای این ستون غلط است و جمع آن در گزارش و Studio چندبرابر یا کم است.",
                 " ؛ ".join(map(str, risky[:8])))
    empty = [r["ستون"] for r in rows if r["همیشه خالی"]]
    twins = [f'{r["ستون"]} = {r["هم‌محتوا با"]}' for r in rows if r["هم‌محتوا با"]]
    ctx.add("7_ستون_جدول_تخت_خلاصه", {"ستون کل": len(rows), "همیشه خالی": len(empty), "هم‌محتوا": len(twins),
                                      "ثابت": sum(1 for r in rows if r["ثابت"]), "خطر جمع چندبرابر": len(risky)})
    if empty:
        ctx.find("پایین", "افزونگی", "ستون همیشه خالی در جدول تخت", len(empty), "", " ؛ ".join(map(str, empty[:8])))
    if twins:
        ctx.find("پایین", "افزونگی", "ستون هم‌محتوا در جدول تخت", len(twins), "", " ؛ ".join(twins[:6]))


# ───────────────────────────── ۸: انبار منتشرشده (فقط‌خواندنی) ─────────────────────────────
def audit_warehouse(path: str, ctx: Ctx):
    print(f"۸) انبار داده منتشرشده (فقط‌خواندنی): {path}")
    if not path or not os.path.isfile(path):
        ctx.find("اطلاع", "انبار", "انبار داده پیدا نشد", 0, f"مسیر: {path}. مقدار warehouse را در ini بنویسید.")
        return
    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    except Exception as ex:
        ctx.fail("باز کردن انبار", ex)
        return
    try:
        from gsi.warehouse.business_dwh import TABLES
    except Exception:
        TABLES = {}
    tabs = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    for name in sorted(tabs):
        if not (name.startswith("dwh_") or name.startswith("src_")):
            continue
        cols = [r[1] for r in conn.execute(f'pragma table_info("{name}")')]
        total = conn.execute(f'select count(*) from "{name}"').fetchone()[0]
        has_ver = "to_seq" in cols
        open_n = conn.execute(f'select count(*) from "{name}" where to_seq is null').fetchone()[0] if has_ver else total
        spec = TABLES.get(name)
        keys = list(spec.keys) if spec else (["source", "frame", "rkey", "occ"] if name == "src_record" else [])
        keys = [k for k in keys if k in cols]
        dup_open = 0
        if keys and has_ver:
            kl = ",".join(f'"{k}"' for k in keys)
            dup_open = conn.execute(f'select count(*) from (select {kl} from "{name}" where to_seq is null '
                                    f'group by {kl} having count(*)>1)').fetchone()[0]
        uniq_idx = [r[1] for r in conn.execute(f'pragma index_list("{name}")') if r[2]]
        ctx.add("8_انبار", {"جدول": name, "ردیف کل (همه نسخه‌ها)": total, "ردیف باز (نسخه جاری)": open_n,
                            "کلید طبیعی": " + ".join(keys), "کلید طبیعی تکراری در نسخه باز": dup_open,
                            "شاخص یکتا": " ؛ ".join(uniq_idx)})
        if dup_open:
            ctx.find("بحرانی", "کلید اصلی", f"{name}: دو نسخه باز برای یک کلید", dup_open,
                     "نسخه جاری یک کلید باید یکتا باشد؛ خواننده‌ها ممکن است هر دو را ببینند.")
    # موجودیت در برابر بعدها
    dims = {"ORDER": ("dwh_dim_order", "order_key"), "MATERIAL": ("dwh_dim_material", "material_key"),
            "BL": ("dwh_dim_bl", "bl_key"), "REG": ("dwh_dim_registration", "reg_key"),
            "REG_FILE": ("dwh_dim_registration_file", "reg_file_key"), "PR": ("dwh_dim_pr", "pr_key"),
            "PO": ("dwh_dim_po", "po_key"), "EMP": ("dwh_dim_employee", "emp_key")}
    if "dwh_entity" in tabs:
        for typ, (t, k) in dims.items():
            if t not in tabs:
                continue
            try:
                a = {r[0] for r in conn.execute("select business_key from dwh_entity where entity_type=? and to_seq is null", (typ,))}
                b = {r[0] for r in conn.execute(f'select "{k}" from "{t}" where to_seq is null')}
                ctx.add("8_موجودیت_و_بعد", {"نوع": typ, "در dwh_entity": len(a), f"در {t}": len(b),
                                           "فقط در entity": len(a - b), "فقط در بعد": len(b - a),
                                           "نمونه اختلاف": ctx.sample(list((a - b) | (b - a))[: ctx.samples])})
                if a != b:
                    ctx.find("متوسط", "افزونگی", f"{typ}: dwh_entity و {t} هم‌خوان نیستند", len(a ^ b),
                             "یک واقعیت در دو جدول نگه داشته می‌شود و از هم جدا شده است.")
            except Exception as ex:
                ctx.fail(f"entity/{typ}", ex)
    if "dwh_relation" in tabs:
        try:
            q = ("select left_type,right_type,count(*),count(distinct left_key||'\x1f'||right_key) "
                 "from dwh_relation where to_seq is null group by 1,2")
            for lt, rt, n, d in conn.execute(q):
                l_multi = conn.execute("select count(*) from (select left_key from dwh_relation where to_seq is null and "
                                       "left_type=? and right_type=? group by left_key having count(distinct right_key)>1)",
                                       (lt, rt)).fetchone()[0]
                r_multi = conn.execute("select count(*) from (select right_key from dwh_relation where to_seq is null and "
                                       "left_type=? and right_type=? group by right_key having count(distinct left_key)>1)",
                                       (lt, rt)).fetchone()[0]
                lefts = conn.execute("select count(distinct left_key) from dwh_relation where to_seq is null and left_type=? and right_type=?",
                                     (lt, rt)).fetchone()[0]
                rights = conn.execute("select count(distinct right_key) from dwh_relation where to_seq is null and left_type=? and right_type=?",
                                      (lt, rt)).fetchone()[0]
                ctx.add("8_رابطه‌ها", {"چپ": lt, "راست": rt, "ردیف رابطه": n, "جفت یکتا": d,
                                      "ردیف تکراری از چند سورس/قاعده": n - d,
                                      "چپ یکتا": lefts, "راست یکتا": rights,
                                      "چپ با بیش از یک راست": l_multi, "راست با بیش از یک چپ": r_multi})
        except Exception as ex:
            ctx.fail("رابطه‌ها", ex)
    try:
        last = conn.execute("select seq,id,started,finished,status from wh_run order by seq desc limit 5").fetchall()
        for r in last:
            ctx.add("8_اجراها", dict(zip(["seq", "run_id", "شروع", "پایان", "وضعیت"], r)))
    except Exception:
        pass
    conn.close()


# ───────────────────────────── ۱۰، ۱۱ و ۱۲: کمکی‌های مشترک ─────────────────────────────
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
MULTI_SEP = re.compile(r"\s*[،؛;|,\n]\s*")
NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")
ID_LIKE = re.compile(r"(^KEY_|^CANONICAL_|_KEY$|_NO$|_ID$|_CODE$|_REG$|_BL$|_REF$|_ITEM$)")


def norm_value(v) -> str:
    """مقدار برای مقایسه: بدون فاصله اضافه، ارقام لاتین، حروف بزرگ؛ «5.0» و «5» یکی‌اند."""
    s = re.sub(r"\s+", " ", clean(v)).translate(DIGITS).upper()
    if s and NUM_RE.match(s.replace(",", "")):
        try:
            f = float(s.replace(",", ""))
            if f == f:
                return str(int(f)) if f.is_integer() else repr(f)
        except Exception:
            pass
    return s


def norm_bl(v) -> str:
    """شماره بارنامه فقط با A-Z و 0-9 (فاصله، نقطه، خط تیره و پسوند .0 حذف)."""
    s = clean(v).translate(DIGITS).upper()
    s = re.sub(r"\.0$", "", s)
    return re.sub(r"[^A-Z0-9]", "", s)


def split_multi(v) -> list:
    """مقدار یک ستون فهرستی («a، b | c») به اجزایش؛ خود مقدار کامل هم برگردانده می‌شود."""
    s = clean(v)
    if not s:
        return []
    parts = [p for p in MULTI_SEP.split(s) if p.strip()]
    return list(dict.fromkeys([s] + parts))


def _composite(df, keys):
    import pandas as pd
    kv = pd.DataFrame({k: df[k].map(clean) for k in keys}, index=df.index)
    ok = kv.ne("").all(axis=1)
    comp = kv[keys[0]].astype(str)
    for k in keys[1:]:
        comp = comp + "\x1f" + kv[k].astype(str)
    return comp, ok


def _col_kind(vals) -> str:
    """vals: مقدارهای نرمال‌شده پر. «عددی»، «بولی» یا «متنی»."""
    if vals.empty:
        return "متنی"
    if vals.isin(["TRUE", "FALSE", "0", "1"]).all() and vals.isin(["TRUE", "FALSE"]).any():
        return "بولی"
    if vals.map(lambda x: bool(NUM_RE.match(x))).mean() >= 0.8:
        return "عددی"
    return "متنی"


def find_counterparts(col: str, agg_cols) -> dict:
    """ستون‌های فریم تجمیعی که همه مقدارهای ستون را نگه می‌دارند.

    «value»: همان ستون یا ستون *_ALL / *S_ALL / *ES_ALL (بلندترین نام منطبق اول)؛ «count»: ستون *_COUNT.
    """
    agg_cols = [str(c) for c in agg_cols]
    aset = set(agg_cols)
    col = str(col)
    toks = col.split("_")
    prefix, body = (toks[0] + "_", toks[1:]) if len(toks) > 1 else ("", toks)
    # فقط پسوند/پیشوند شناسه (KEY_…، …_NO، …_CODE، …_ID) کنار گذاشته می‌شود. تطبیق زیررشته آزاد
    # (مثلاً QTY_IN_PART با PARTS_ALL که شماره فنی سازنده است) هشدار دروغ «یک مقدار نگه داشته شد» می‌ساخت.
    subs = [body]
    core = list(body)
    if len(core) > 1 and core[0] == "KEY":
        core = core[1:]
        subs.append(core)
    if len(core) > 1 and core[-1] in ("NO", "CODE", "ID", "NUMBER"):
        subs.append(core[:-1])
    subs.sort(key=lambda s: -len(s))
    out = {"self": col if col in aset else "", "value": "", "count": ""}
    for sub in subs:
        b = "_".join(sub)
        if not out["value"]:
            for suf in ("_ALL", "S_ALL", "ES_ALL"):
                if prefix + b + suf in aset:
                    out["value"] = prefix + b + suf
                    break
        if not out["count"] and prefix + b + "_COUNT" in aset:
            out["count"] = prefix + b + "_COUNT"
    return out


# ───────────────────────────── ۱۰: احتمال فروریختگی ─────────────────────────────
COLLAPSE_EXPLICIT = [
    ("moghavemat", "lines", "main", ["KEY_ORDER", "KEY_MATERIAL"]),
    ("moghavemat", "lines", "inventory", ["KEY_ORDER", "KEY_MATERIAL"]),
    ("moghavemat", "lines", "main", ["KEY_ORDER"]),
]
KEEP_ALL = "همه مقدارها نگه داشته شد"
KEEP_ONE = "یک مقدار نگه داشته شد"


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    """بازه اطمینان ویلسون برای نسبت k/n: احتمال این‌که گروه (سفارش) تازه هم چندمقداری باشد."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def collapse_metrics(detail, agg, keys, ctx: Ctx, pair: str = "", cache=None) -> list:
    """برای هر ستون فریم جزئی: چند گروه کلید، سهم گروه‌های چندمقداری، و آیا فریم تجمیعی همه مقدارها را نگه داشته.

    agg=None یعنی فریم تجمیعی نداریم (فقط احتمال چندمقداری زیر کلید اعلام‌شده).
    """
    import pandas as pd
    if detail is None or detail.empty or any(k not in detail.columns for k in keys):
        return []
    comp, ok = _composite(detail, keys)
    d = detail[ok]
    comp = comp[ok]
    n_groups = int(comp.nunique())
    if not n_groups:
        return []
    agg_comp = None
    if agg is not None and not agg.empty and all(k in agg.columns for k in keys):
        agg_comp, agg_ok = _composite(agg, keys)
        agg = agg[agg_ok]
        agg_comp = agg_comp[agg_ok]
    elif agg is not None:
        agg = None
    agg_sets_cache = {}

    def agg_sets(c):
        if c not in agg_sets_cache:
            m = defaultdict(set)
            for k, v in zip(agg_comp.tolist(), agg[c].tolist()):
                for part in split_multi(v):
                    m[k].add(norm_value(part))
            agg_sets_cache[c] = m
        return agg_sets_cache[c]

    rows = []
    for col in d.columns:
        if col in keys or str(col) in LOCATION_COLS or isinstance(detail[col], pd.DataFrame):
            continue      # ستون تکراری در بخش ۳ گزارش می‌شود
        ck = (id(detail), str(col))
        if cache is not None and ck in cache:
            vals = cache[ck][ok]
        else:
            full = detail[col].map(norm_value)
            if cache is not None:
                cache[ck] = full
            vals = full[ok]
        filled = vals.ne("")
        nun = vals.where(filled).groupby(comp).nunique()
        multi = nun[nun > 1]
        share = len(multi) / n_groups
        in_multi = comp.isin(multi.index)
        rows_multi = int(in_multi.sum())
        kind = _col_kind(vals[filled])
        rec = {"جفت": pair, "ستون": str(col), "کلید گروه": " + ".join(keys), "نوع ستون": kind,
               "گروه کلید": n_groups, "گروه چندمقداری": int(len(multi)),
               "احتمال چندمقداری": round(share, 4),
               "بازه ۹۵٪ (ویلسون)": "{:.3f} تا {:.3f}".format(*wilson(len(multi), n_groups)),
               "ردیف در گروه چندمقداری": rows_multi}
        lost_keys = []
        cp = {"self": "", "value": "", "count": ""}
        if agg is None:
            status = "بدون فریم تجمیعی"
            rows_lost = rows_multi
        else:
            cp = find_counterparts(col, agg.columns)
            has_sep = bool(cp["self"]) and agg[cp["self"]].astype(str).str.contains("،|\\|", regex=True).any()
            if (not cp["self"] and f"{col}_CODE" in detail.columns
                    and any(find_counterparts(f"{col}_CODE", agg.columns).values())):
                # متن خام (مثلاً «دریایی») با کد نرمالش (SEA) سنجیده می‌شود، نه با فهرست کدها.
                status = f"سنجیده در {col}_CODE"
                cp = {"self": "", "value": "", "count": ""}
            elif not (cp["self"] or cp["value"] or cp["count"]):
                status = "ستون در فریم تجمیعی نیست"
            elif kind == "عددی" and not cp["value"]:
                status = "سنجه عددی (تجمیع)"
            elif kind == "بولی" and not cp["value"]:
                status = "پرچم بولی (any/all)"
            elif multi.empty:
                status = (KEEP_ALL + " (ساختاری)") if (cp["value"] or cp["count"] or has_sep) else \
                         "یک مقدار (هنوز چندمقداری دیده نشد)"
            else:
                sub = pd.DataFrame({"k": comp[in_multi], "v": vals[in_multi]})
                sub = sub[sub.v.ne("")]
                det = sub.groupby("k")["v"].agg(lambda s: set(s)).to_dict()
                value_cols = [c for c in (cp["self"], cp["value"]) if c]
                for k, want in det.items():
                    have = set()
                    for c in value_cols:
                        have |= agg_sets(c).get(k, set())
                    covered = want <= have
                    if not covered and cp["count"] and not value_cols[1:] and not has_sep:
                        cnt = agg_sets(cp["count"]).get(k, set())
                        covered = str(len(want)) in cnt
                    if not covered:
                        lost_keys.append(k)
                status = KEEP_ALL if not lost_keys else KEEP_ONE
            rows_lost = int(comp.isin(lost_keys).sum()) if lost_keys else 0
        risk = share * rows_lost if status in (KEEP_ONE, "بدون فریم تجمیعی") else 0.0
        samples = []
        for k in (lost_keys if agg is not None else list(multi.index))[: ctx.samples]:
            vs = sorted(set(vals[comp.eq(k) & filled]))[:3]
            samples.append(tuple(k.split("\x1f")) + (" / ".join(vs),))
        rec.update({"ستون در فریم تجمیعی": " ؛ ".join(x for x in (cp["self"], cp["value"], cp["count"]) if x),
                    "وضعیت نگهداری": status, "گروه از دست رفته": len(lost_keys),
                    "ردیف اثرپذیر": rows_lost, "ریسک (سهم × ردیف)": round(risk, 2),
                    "نمونه": ctx.sample(samples)})
        rows.append(rec)
    rows.sort(key=lambda r: -r["ریسک (سهم × ردیف)"])
    return rows


def pair_overlap(detail, agg, keys) -> float:
    """سهم ستون‌های فریم جزئی که در فریم تجمیعی (همان نام یا *_ALL/*_COUNT) هستند؛ برای یافتن جفت واقعی."""
    cols = [c for c in detail.columns if c not in keys and str(c) not in LOCATION_COLS]
    if not cols:
        return 0.0
    hit = sum(1 for c in cols if any(find_counterparts(c, agg.columns).values()))
    return hit / len(cols)


def collapse_pairs(sources, specs) -> list:
    """(سورس، فریم جزئی، فریم تجمیعی یا None، کلید) — صریح + هر summary با فریم ردیفی هم‌سورس + هر کلید اعلام‌شده."""
    import pandas as pd
    out, seen = [], set()

    def add(src, d, a, keys):
        t = (src, d, a, tuple(keys))
        if t not in seen:
            seen.add(t)
            out.append((src, d, a, list(keys)))

    for src, d, a, keys in COLLAPSE_EXPLICIT:
        if isinstance((sources.get(src) or {}).get(d), pd.DataFrame) and \
                isinstance((sources.get(src) or {}).get(a), pd.DataFrame):
            add(src, d, a, keys)
    for src, frames in sources.items():
        for s_name, s_df in frames.items():
            spec = specs.get(f"{src}/{s_name}", {})
            keys = list(spec.get("keys") or [])
            if not isinstance(s_df, pd.DataFrame) or not keys or spec.get("role") != "summary":
                continue
            for d_name, d_df in frames.items():
                if d_name == s_name or not isinstance(d_df, pd.DataFrame) or d_df.empty:
                    continue
                if specs.get(f"{src}/{d_name}", {}).get("role") == "summary" or len(d_df) < len(s_df):
                    continue
                if all(k in d_df.columns for k in keys) and pair_overlap(d_df, s_df, keys) >= 0.3:
                    add(src, d_name, s_name, keys)
    for src, frames in sources.items():
        for name, df in frames.items():
            keys = list(specs.get(f"{src}/{name}", {}).get("keys") or [])
            if isinstance(df, pd.DataFrame) and keys and all(k in df.columns for k in keys):
                add(src, name, None, keys)
    return out


#: کاهش عمدی چند مقدار به یک مقدار که قاعده‌اش در کد آداپتر نوشته شده؛ «یک مقدار طبق قاعده» گزارش می‌شود نه
#: فروریختگی. (سورس، فریم تجمیعی، ستون یا «*») → قاعده.
BY_DESIGN = {
    ("ntsw", "commitment", "NTSW_DEADLINE"): "زودترین مهلت تعهدهای زنده (محافظه‌کارانه)",
    ("ntsw", "commitment", "NTSW_COMMIT_DATE"): "زودترین تاریخ ایجاد تعهد؛ آخرین در NTSW_LAST_COMMIT_DATE",
    ("ntsw", "commitment_by_currency", "NTSW_DEADLINE"): "زودترین مهلت تعهدهای زنده همان ارز",
    ("ntsw", "commitment_by_currency", "NTSW_COMMIT_DATE"): "زودترین تاریخ ایجاد؛ آخرین در NTSW_LAST_COMMIT_DATE",
    ("ntsw", "allocation", "*"): "یک ردیف برای هر ثبت سفارش با درخواست تعیین‌کننده (دور ۷)؛ همه درخواست‌ها در "
                                 "allocation_rows و allocation_history می‌مانند",
}
BY_DESIGN_STATUS = "یک مقدار طبق قاعده"


def by_design(src, agg_name, col):
    return BY_DESIGN.get((src, agg_name, col)) or BY_DESIGN.get((src, agg_name, "*"))


def audit_collapse(sources, specs, ctx: Ctx):
    import pandas as pd
    print("۱۰) احتمال فروریختگی (چند مقدار ← یک مقدار) ...")
    all_rows, cache = [], {}
    for src, d_name, a_name, keys in collapse_pairs(sources, specs):
        try:
            d = sources[src][d_name]
            a = sources[src].get(a_name) if a_name else None
            label = f"{src}/{d_name} → {a_name}" if a_name else f"{src}/{d_name} (کلید اعلام‌شده)"
            rows = collapse_metrics(d, a, keys, ctx, label, cache)
            # ستونی که نه چندمقداری است نه در فریم تجمیعی آمده، چیزی برای گفتن ندارد
            rows = [r for r in rows if r["گروه چندمقداری"] or
                    (a_name and r["وضعیت نگهداری"] != "ستون در فریم تجمیعی نیست")]
            for r in rows:
                why = by_design(src, a_name, r["ستون"]) if r["وضعیت نگهداری"] == KEEP_ONE else None
                if why:
                    r["وضعیت نگهداری"] = f"{BY_DESIGN_STATUS}: {why}"
                    r["ریسک (سهم × ردیف)"] = 0.0
            lost_cols = [r for r in rows if r["وضعیت نگهداری"] == KEEP_ONE]
            ctx.add("10_فروریختگی_جفت‌ها", {
                "جفت": label, "کلید گروه": " + ".join(keys), "ردیف جزئی": len(d),
                "ردیف تجمیعی": len(a) if isinstance(a, pd.DataFrame) else "",
                "ستون سنجیده": len(rows), "ستون با فروریختگی": len(lost_cols),
                "ستون چندمقداری": sum(1 for r in rows if r["گروه چندمقداری"]),
                "بیشترین ریسک": max((r["ریسک (سهم × ردیف)"] for r in rows), default=0),
                "ستون‌های پرریسک": " ؛ ".join(r["ستون"] for r in lost_cols[:6])})
            all_rows += rows
            if lost_cols:
                top = lost_cols[:5]
                ctx.find("بالا", "فروریختگی", f"{label}: چند مقدار به یک مقدار تبدیل می‌شود", len(lost_cols),
                         f"در گروه‌های {' + '.join(keys)} این ستون‌ها بیش از یک مقدار دارند ولی خروجی فقط یکی را نگه "
                         "می‌دارد (مثل first_valid): " + "، ".join(
                             f"{r['ستون']} ({round(100 * r['احتمال چندمقداری'], 1)}٪ گروه‌ها، {r['ردیف اثرپذیر']} ردیف)"
                             for r in top), top[0]["نمونه"])
        except Exception as ex:
            ctx.fail(f"فروریختگی {src}/{d_name}", ex)
    all_rows.sort(key=lambda r: -r["ریسک (سهم × ردیف)"])
    for r in all_rows:
        ctx.add("10_فروریختگی", r)
    n_col = sum(1 for r in all_rows if r["وضعیت نگهداری"] == KEEP_ONE)
    n_pairs = len({r["جفت"] for r in all_rows})
    ctx.find("اطلاع", "۱۰ فروریختگی", "خلاصه بخش ۱۰", n_col,
             f"{n_pairs} جفت/فریم و {len(all_rows)} ستون سنجیده شد؛ {n_col} ستون چندمقداری به یک مقدار می‌رسند. "
             "رتبه‌بندی با ریسک = احتمال چندمقداری × ردیف اثرپذیر در برگه 10_فروریختگی.")


# ───────────────────────────── ۱۱: پوشش واژگان ─────────────────────────────
#: (سورس، فریم، ستون خام، تابع rulebook، ستون مقدار برای سهم)
LEXICON_CHECKS = [
    ("moghavemat", "lines", "MOGH_ORDER_STATUS", "part_state", "MOGH_QTY_IN_PART"),
    ("moghavemat", "lines", "MOGH_TRANSPORT_MODE", "transport_mode", "MOGH_QTY_IN_PART"),
    ("moghavemat", "lines", "MOGH_ADDITIONAL_DATA", "parse_status_note", "MOGH_QTY_IN_PART"),
    ("abbasi", "main", "BL_TRIP_MODE", "transport_mode", None),
    ("abbasi", "main", "BL_SHIP_STATUS", "transport_mode", None),
    ("clearance", "main", "CL_TRANSPORT_MODE", "transport_mode", None),
]
LEXICON_NOTE = {
    "part_state": "Order Status → status_lexicon.part_states؛ ناشناخته = UNRECOGNIZED",
    "transport_mode": "→ transport.modes؛ ناشناخته = کد خالی برای مقدار پر",
    "parse_status_note": "Additional Data → status_lexicon.phrases؛ ناشناخته = مرحله خالی",
    "currency_code": "مقدار ستون ارز پس از normalize_currency آداپتر (متن خام در فریم نمانده) → کد ISO؛ ناشناخته = کد خالی",
}


def map_lexicon(rb, mapper: str, raw):
    """(کد نگاشت‌شده، نگاشت نشد؟) برای یک مقدار پر."""
    if mapper == "part_state":
        code = str(rb.part_state(raw) or "")
        known = set((rb.get("status_lexicon.part_states", {}) or {}).keys()) if hasattr(rb, "get") else set()
        return code, (code == "UNRECOGNIZED" or not code or (known and code not in known))
    if mapper == "parse_status_note":
        code = str((rb.parse_status_note(raw) or {}).get("STAGE", "") or "")
        return code, not code
    fn = getattr(rb, mapper)
    code = str(fn(raw) or "")
    return code, not code


def lexicon_coverage(df, column: str, mapper: str, rb, qty_col=None, frame: str = "", max_rows: int = 5000):
    """(ردیف‌های هر مقدار یکتا، ردیف خلاصه). مقدار خالی شمرده ولی ناشناخته حساب نمی‌شود."""
    import pandas as pd
    raw = df[column].map(clean)
    qty = pd.to_numeric(df[qty_col], errors="coerce") if qty_col and qty_col in df.columns else None
    total_q = float(qty.sum()) if qty is not None else None
    rows = []
    stats = Counter()
    unm_vals, unm_q = [], 0.0
    counts = raw.value_counts(dropna=False)
    for v, n in counts.items():
        q = float(qty[raw.eq(v)].sum()) if qty is not None else None
        if v == "":
            code, bad = "", False
        else:
            try:
                code, bad = map_lexicon(rb, mapper, v)
            except Exception as ex:
                code, bad = f"خطا: {type(ex).__name__}", True
        stats["rows"] += int(n)
        if v == "":
            stats["empty"] += int(n)
        if bad:
            stats["unm_rows"] += int(n)
            unm_vals.append(v)
            if q is not None:
                unm_q += q
        rows.append({"فریم": frame, "ستون": column, "نگاشت": mapper, "مقدار خام": v or "(خالی)", "تعداد": int(n),
                     "کد نگاشت‌شده": code, "نگاشت نشد": bool(bad),
                     "جمع مقدار": round(q, 4) if q is not None else "",
                     "سهم از مقدار": round(q / total_q, 4) if (q is not None and total_q) else ""})
    rows.sort(key=lambda r: (not r["نگاشت نشد"], -r["تعداد"]))
    truncated = max(0, len(rows) - max_rows)
    filled = stats["rows"] - stats["empty"]
    summary = {"فریم": frame, "ستون": column, "نگاشت": mapper, "توضیح نگاشت": LEXICON_NOTE.get(mapper, ""),
               "ردیف": stats["rows"], "ردیف پر": filled, "مقدار یکتا": int(len(counts)),
               "مقدار یکتای نگاشت‌نشده": len(unm_vals), "ردیف نگاشت‌نشده": stats["unm_rows"],
               "سهم ردیف نگاشت‌نشده (از پر)": round(stats["unm_rows"] / filled, 4) if filled else "",
               "ستون مقدار": qty_col or "", "جمع مقدار کل": round(total_q, 4) if total_q is not None else "",
               "مقدار اثرپذیر": round(unm_q, 4) if qty is not None else "",
               "سهم مقدار اثرپذیر": round(unm_q / total_q, 4) if (qty is not None and total_q) else "",
               "مقدارهای نگاشت‌نشده": " ؛ ".join(unm_vals[:10]),
               "ردیف حذف‌شده از فهرست": truncated}
    return rows[:max_rows], summary


def rb_calls_in_adapters(app: Path) -> list:
    """نگاشت‌های rulebook که در کد آداپترها دیده می‌شود (فایل، تابع، ستون)."""
    out = []
    for f in sorted((app / "gsi" / "adapters").glob("*.py")):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r"(?:\brb|get_rulebook\(\))\.([a-z_]+)\b(?!\s*=)", text):
            line = text[: m.start()].count("\n") + 1
            src_line = text.splitlines()[line - 1].strip()[:140]
            out.append({"فایل": f.name, "خط": line, "تابع": m.group(1), "کد": src_line})
    return out


def audit_lexicon(sources, ctx: Ctx, rb=None, app: Path = None):
    import pandas as pd
    print("۱۱) پوشش واژگان rulebook ...")
    try:
        if rb is None:
            from gsi.rulebook import get_rulebook
            rb = get_rulebook()
    except Exception as ex:
        ctx.fail("rulebook", ex)
        return
    checks = list(LEXICON_CHECKS)
    for src, frames in sources.items():
        for name, df in frames.items():
            if isinstance(df, pd.DataFrame):
                for c in df.columns:
                    if re.search(r"CURRENCY$", str(c)) and not str(c).endswith("_ALL"):
                        checks.append((src, name, str(c), "currency_code", None))
    checked = set()
    n_cols, n_bad = 0, 0
    for src, name, col, mapper, qty_col in checks:
        df = (sources.get(src) or {}).get(name)
        if not isinstance(df, pd.DataFrame) or col not in df.columns:
            ctx.add("11_واژگان_خلاصه", {"فریم": f"{src}/{name}", "ستون": col, "نگاشت": mapper,
                                         "توضیح نگاشت": "ستون در خروجی آداپتر نیست؛ سنجیده نشد"})
            continue
        try:
            rows, summ = lexicon_coverage(df, col, mapper, rb, qty_col, f"{src}/{name}")
        except Exception as ex:
            ctx.fail(f"واژگان {src}/{name}.{col}", ex)
            continue
        checked.add(mapper)
        n_cols += 1
        for r in rows:
            ctx.add("11_واژگان", r)
        ctx.add("11_واژگان_خلاصه", summ)
        if summ["ردیف نگاشت‌نشده"]:
            n_bad += 1
            sev = {"part_state": "بحرانی" if (summ["مقدار اثرپذیر"] or 0) > 0 else "بالا",
                   "transport_mode": "متوسط", "currency_code": "متوسط"}.get(mapper, "پایین")
            if col == "BL_SHIP_STATUS":
                sev = "پایین"
            extra = (f"؛ {summ['مقدار اثرپذیر']} از {summ['جمع مقدار کل']} واحد "
                     f"({round(100 * (summ['سهم مقدار اثرپذیر'] or 0), 2)}٪) {qty_col}") if qty_col else ""
            ctx.find(sev, "واژگان", f"{src}/{name}.{col}: مقدار بیرون از واژگان {mapper}",
                     summ["ردیف نگاشت‌نشده"],
                     f"{summ['مقدار یکتای نگاشت‌نشده']} مقدار یکتا کد نگرفت{extra}. "
                     "این ردیف‌ها در شمارش وضعیت/روش حمل نمی‌آیند یا «نامشخص» می‌شوند.",
                     summ["مقدارهای نگاشت‌نشده"])
    if app is not None:
        for r in rb_calls_in_adapters(app):
            r["سنجیده در این بخش"] = r["تابع"] in checked or r["تابع"] in ("normalize_currency",) and "currency_code" in checked
            ctx.add("11_نگاشت‌های_کد", r)
    ctx.find("اطلاع", "۱۱ واژگان", "خلاصه بخش ۱۱", n_bad,
             f"{n_cols} ستون با واژگان rulebook سنجیده شد؛ {n_bad} ستون مقدار نگاشت‌نشده دارد (برگه 11_واژگان).")


# ───────────────────────────── ۱۲: تطبیق کارشناس و گزارش ─────────────────────────────
DEFAULT_PART_STATES = (("AT_SUPPLIER", "QTY_AT_SUPPLIER"), ("READY", "QTY_READY"),
                       ("IN_TRANSIT", "QTY_IN_TRANSIT"), ("IN_CUSTOMS", "QTY_IN_CUSTOMS"))
LINEAGE_COLUMNS = ["MOGH_BL_NO", "MOGH_ORDER_STATUS", "MOGH_TRANSPORT_MODE_CODE", "CANONICAL_BL", "KEY_BL", "MOGH_QTY_*"]
APP_BL_COLS = ["CANONICAL_BL", "KEY_BL", "MOGH_BL_NO", "MOGH_BLS_ALL"]
APP_STATUS_COLS = ["MOGH_ORDER_STATUS", "MOGH_ORDER_STATUSES_ALL"]


def part_state_columns() -> tuple:
    """({کد وضعیت: ستون MOGH_QTY_*}, ستون وضعیت نامشخص) از آداپتر اپ؛ اگر نبود پیش‌فرض."""
    states, unknown = DEFAULT_PART_STATES, "QTY_STATE_UNKNOWN"
    try:
        import gsi.adapters.moghavemat as M
        got = getattr(M, "PART_STATES", None)
        if got:
            states = tuple((t[0], t[-1]) for t in got)
        unknown = getattr(M, "STATE_UNKNOWN_QTY", unknown)
    except Exception:
        pass
    return {str(c): "MOGH_" + str(col) for c, col in states}, "MOGH_" + str(unknown)


def _col(df, *names):
    import pandas as pd
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([""] * len(df), index=df.index, dtype=object)


def status_key(rb, v) -> str:
    fn = getattr(rb, "_state_key", None)
    try:
        if fn is not None:
            return fn(v)
    except Exception:
        pass
    return re.sub(r"\s+", "", clean(v).replace("‌", " ")).lower()


def expert_positions(lines, rb, state_codes=None):
    """موقعیت مستقل هر Order×Material از ردیف‌های فایل کارشناسان.

    قاعده (شفاف): هر محموله یک بار شمرده می‌شود؛ شناسه محموله = Part No.، وگرنه BL نرمال‌شده، وگرنه
    Transport No.، وگرنه خود ردیف. ردیف‌های هم‌شناسه (تکرار یک محموله در چند قلم PR) = ردیف با بیشترین
    Quantity In Part. وضعیت از Order Status همان ردیف با واژگان rulebook (part_state)؛ خالی یا ناشناخته =
    «نامشخص». اگر مقدار نامشخص > 0 باشد، وضعیت‌های صفر نامعلوم (خالی) می‌مانند؛ اگر هیچ محموله‌ای مقدار
    نداشت همه خالی‌اند. در گمرک خالص = Quantity In Part − Customs Cleared Quantity (کمینه ۰).
    """
    import numpy as np
    import pandas as pd
    codes_known = list(state_codes or [c for c, _ in DEFAULT_PART_STATES])
    o = _col(lines, "KEY_ORDER").map(clean)
    m = _col(lines, "KEY_MATERIAL").map(clean)
    status_raw = _col(lines, "MOGH_ORDER_STATUS")
    qty = pd.to_numeric(_col(lines, "MOGH_QTY_IN_PART"), errors="coerce")
    cleared = pd.to_numeric(_col(lines, "MOGH_CLEARED_QTY"), errors="coerce")
    part = _col(lines, "MOGH_PART_NO_PARTIAL").map(clean)
    bl_raw = _col(lines, "MOGH_BL_RAW", "MOGH_BL_NO")
    bl = bl_raw.map(norm_bl)
    tno = _col(lines, "MOGH_TRANSPORT_NO").map(norm_value)
    sraw = status_raw.map(clean)
    st_of, sk_of = {}, {}
    for v in sraw.unique():     # واژگان برای هر مقدار یکتا یک بار
        c = str(rb.part_state(v) or "") if v else ""
        st_of[v] = c if c and c != "UNRECOGNIZED" else "UNKNOWN"
        sk_of[v] = status_key(rb, v) if v else ""
    w = pd.DataFrame({"o": o, "m": m, "st": sraw.map(st_of), "q": qty, "cl": cleared, "bl": bl,
                      "blraw": bl_raw.map(clean), "sk": sraw.map(sk_of), "sraw": sraw}, index=lines.index)
    w["ident"] = np.where(part.ne(""), "P:" + part,
                          np.where(bl.ne(""), "B:" + bl,
                                   np.where(tno.ne(""), "T:" + tno, "R:" + pd.Series(lines.index.astype(str), index=lines.index))))
    w = w[w.m.ne("")]
    seen_codes = sorted(set(w.st) - {"UNKNOWN"} - set(codes_known))
    all_codes = codes_known + seen_codes
    gk = ["o", "m"]
    # هر محموله: ردیف با بیشترین Quantity In Part (ردیف بی‌مقدار فقط وقتی همه بی‌مقدارند، و آن‌وقت شمرده نمی‌شود)
    w["_ord"] = np.arange(len(w))
    top = w.sort_values(["q", "_ord"], ascending=[False, True], na_position="last") \
           .drop_duplicates(gk + ["ident"], keep="first")
    top = top[top.q.notna()].copy()
    top["net"] = (top.q - top.cl.fillna(0.0)).clip(lower=0.0).where(top.st.eq("IN_CUSTOMS"), 0.0)
    known = w[w.st.ne("UNKNOWN")]
    conf = known.groupby(gk + ["ident"], sort=False)["st"].nunique()
    conf = (conf[conf > 1].reset_index().groupby(gk).size() if (conf > 1).any() else pd.Series(dtype=int))
    by_state = top.pivot_table(index=gk, columns="st", values="q", aggfunc="sum") if len(top) else pd.DataFrame()
    net = top.groupby(gk)["net"].sum() if len(top) else pd.Series(dtype=float)
    base = w.groupby(gk, sort=False).agg(ROWS=("ident", "size"), SHIPMENTS=("ident", "nunique"))
    bls, sts = defaultdict(dict), defaultdict(dict)
    for oo, mm, b_, r_, k_, s_ in zip(w.o, w.m, w.bl, w.blraw, w.sk, w.sraw):
        if b_:
            bls[(oo, mm)].setdefault(b_, r_)
        if k_:
            sts[(oo, mm)].setdefault(k_, s_)
    state_of = by_state.to_dict("index") if len(by_state) else {}
    conf_of = conf.to_dict() if len(conf) else {}
    net_of = net.to_dict() if len(net) else {}
    out = []
    for (order, mat), n_rows, n_ship in zip(base.index, base.ROWS, base.SHIPMENTS):
        k = (order, mat)
        any_qty = k in state_of
        srow = state_of.get(k, {})
        val = (lambda c: float(srow[c]) if (c in srow and srow[c] == srow[c]) else 0.0)
        unknown = val("UNKNOWN")
        rec = {"KEY_ORDER": order, "KEY_MATERIAL": mat, "ROWS": int(n_rows), "SHIPMENTS": int(n_ship),
               "CONFLICT_SHIPMENTS": int(conf_of.get(k, 0)),
               "BLS": dict(bls.get(k, {})), "STATUSES": dict(sts.get(k, {}))}
        for c in all_codes:
            v = val(c)
            rec[f"QTY_{c}"] = (v if (v > 0 or unknown == 0) else np.nan) if any_qty else np.nan
        rec["QTY_UNKNOWN"] = unknown if any_qty else np.nan
        n = float(net_of.get(k, 0.0))
        rec["QTY_IN_CUSTOMS_NET"] = ((n if (n > 0 or unknown == 0) else np.nan)
                                     if any_qty and "IN_CUSTOMS" in all_codes else np.nan)
        out.append(rec)
    cols = ["KEY_ORDER", "KEY_MATERIAL", "ROWS", "SHIPMENTS", "CONFLICT_SHIPMENTS", "BLS", "STATUSES"] + \
           [f"QTY_{c}" for c in all_codes] + ["QTY_UNKNOWN", "QTY_IN_CUSTOMS_NET"]
    return pd.DataFrame(out, columns=cols)


def expert_item_totals(lines):
    """مقدار سفارش و ارزش PI هر سفارش از ردیف‌های فایل کارشناسان، هر قلم یک بار (قاعده مستقل).

    قلم = متریال + PR + قلم PR + PI فروشنده. «Quantity In Order» و «PI Line Value» روی هر پارت همان قلم
    تکرار می‌شوند؛ اگر ردیف‌های یک قلم دست‌کم دو محموله متفاوت‌اند و هر ردیف یک محموله است، مقدار
    تکراری یک بار شمرده می‌شود (دو مقدار متفاوت = نامعلوم). ارزش PI فقط وقتی همه خط‌های سفارش یک ارز دارند.
    """
    import numpy as np
    import pandas as pd
    o = _col(lines, "KEY_ORDER").map(clean)
    item = (_col(lines, "KEY_MATERIAL").map(clean) + "\x1f" + _col(lines, "MOGH_PR_NO").map(clean) + "\x1f"
            + _col(lines, "MOGH_PR_ITEM").map(clean) + "\x1f" + _col(lines, "MOGH_VENDOR_PI_NO").map(clean))
    part = _col(lines, "MOGH_PART_NO_PARTIAL").map(clean)
    bl = _col(lines, "MOGH_BL_RAW", "MOGH_BL_NO").map(norm_bl)
    tno = _col(lines, "MOGH_TRANSPORT_NO").map(norm_value)
    ship = pd.Series(np.where(part.ne(""), "P:" + part, np.where(bl.ne(""), "B:" + bl,
                              np.where(tno.ne(""), "T:" + tno, ""))), index=lines.index)
    cur = _col(lines, "MOGH_CURRENCY").map(clean)
    out = []
    for order, g in lines[o.ne("")].groupby(o[o.ne("")], sort=False):
        rec = {"KEY_ORDER": order}
        for name, col, need_all in (("ORDER_QTY", "MOGH_QTY_IN_ORDER", False), ("PI_VALUE", "MOGH_PI_LINE_VALUE", True)):
            v = pd.to_numeric(_col(g, col), errors="coerce")
            total = 0.0
            for _, idx in item.loc[g.index].groupby(item.loc[g.index], sort=False).groups.items():
                vi, sh = v.loc[idx], {x for x in ship.loc[idx] if x}
                if len(sh) >= 2 and len(sh) == len(idx):
                    k = vi.dropna().unique()
                    if len(k) == 1:
                        total += float(k[0]); continue
                    if len(k) == 0 and not need_all:
                        continue
                    total = float("nan"); break
                if need_all and vi.isna().any():
                    total = float("nan"); break
                total += float(vi.sum())
            rec[name] = total
        cs = set(cur.loc[g.index])
        if len(cs) != 1 or "" in cs:
            rec["PI_VALUE"] = float("nan")
        rec["ROWS_SUM_ORDER_QTY"] = float(pd.to_numeric(_col(g, "MOGH_QTY_IN_ORDER"), errors="coerce").sum())
        out.append(rec)
    return pd.DataFrame(out, columns=["KEY_ORDER", "ORDER_QTY", "PI_VALUE", "ROWS_SUM_ORDER_QTY"])


def compare_measures(expected, app_df, measures, frame: str, ctx: Ctx,
                     keys=("KEY_ORDER", "KEY_MATERIAL")) -> list:
    """measures: [(عنوان، ستون مورد انتظار، ستون اپ)]؛ ناهمخوانی هر سنجه در دانه keys."""
    import pandas as pd
    keys = list(keys)
    rows = []
    if app_df is None or any(k not in app_df.columns for k in keys):
        return rows
    ek = list(zip(*[expected[k].map(clean) for k in keys])) if len(expected) else []
    akeys = list(zip(*[app_df[k].map(clean) for k in keys])) if len(app_df) else []
    app_keyset = set(akeys)
    for label, ecol, acol in measures:
        rec = {"خروجی اپ": frame, "سنجه": label, "ستون اپ": acol, "گروه مقایسه‌شده": len(ek)}
        if acol not in app_df.columns:
            rec["توضیح"] = "ستون در این خروجی نیست"
            rows.append(rec)
            continue
        av = defaultdict(set)
        for k, v in zip(akeys, pd.to_numeric(app_df[acol], errors="coerce")):
            if v == v:
                av[k].add(round(float(v), 6))
        cnt = Counter()
        samples = []
        for k, e in zip(ek, expected[ecol] if ecol in expected.columns else [float("nan")] * len(ek)):
            e = float(e) if e == e else None
            if k not in app_keyset:
                cnt["در خروجی اپ نیست"] += 1
                continue
            a = av.get(k, set())
            if len(a) > 1:
                cat = "چند مقدار در اپ"
            elif not a:
                cat = "هر دو خالی" if e is None else "کارشناس دارد، اپ خالی"
            else:
                x = next(iter(a))
                if e is None:
                    cat = "اپ دارد، کارشناس خالی"
                else:
                    cat = "برابر" if abs(x - e) <= max(1e-6, 1e-9 * abs(e)) else "مقدار متفاوت"
            cnt[cat] += 1
            if cat not in ("برابر", "هر دو خالی") and len(samples) < ctx.samples:
                samples.append(tuple(k) + (f"کارشناس={'' if e is None else round(e, 4)} اپ={' / '.join(str(x) for x in sorted(a))}",))
        bad = sum(cnt[c] for c in ("مقدار متفاوت", "کارشناس دارد، اپ خالی", "اپ دارد، کارشناس خالی", "چند مقدار در اپ"))
        compared = len(ek) - cnt["در خروجی اپ نیست"]
        for c in ("برابر", "هر دو خالی", "مقدار متفاوت", "کارشناس دارد، اپ خالی", "اپ دارد، کارشناس خالی",
                  "چند مقدار در اپ", "در خروجی اپ نیست"):
            rec[c] = cnt[c]
        rec["ناهمخوانی"] = bad
        rec["نرخ ناهمخوانی"] = round(bad / compared, 4) if compared else ""
        rec["نمونه"] = ctx.sample(samples)
        rows.append(rec)
    return rows


def compare_sets(expected_sets: dict, app_df, keys, app_cols, normalizer, frame: str, what: str, ctx: Ctx,
                 classify=None) -> tuple:
    """مقدارهای هر کلید در فایل کارشناسان که در ستون‌های اپ نیست.

    expected_sets: {کلید tuple: {مقدار نرمال: مقدار خام}}. خروجی: (ردیف‌ها برای هر ستون و «همه ستون‌ها»، فهرست گمشده‌ها).
    """
    keys = list(keys)
    rows, missing_all = [], []
    if app_df is None or any(k not in app_df.columns for k in keys):
        return rows, missing_all
    present = [c for c in app_cols if c in app_df.columns]
    akeys = list(zip(*[app_df[k].map(clean) for k in keys])) if len(app_df) else []
    app_keyset = set(akeys)
    per_col = {}
    for c in present:
        m = defaultdict(set)
        for k, v in zip(akeys, app_df[c].tolist()):
            for part in split_multi(v):
                n = normalizer(part)
                if n:
                    m[k].add(n)
        per_col[c] = m
    total = sum(len(v) for v in expected_sets.values())
    for c in present + (["همه ستون‌ها"] if present else []):
        cnt = Counter()
        samples, miss = [], []
        for k, vals in expected_sets.items():
            if k not in app_keyset:
                cnt["کلید در خروجی نیست"] += len(vals)
                continue
            have = per_col[c].get(k, set()) if c in per_col else set().union(*[per_col[x].get(k, set()) for x in present])
            for n, raw in vals.items():
                if n in have:
                    cnt["پیدا شد"] += 1
                else:
                    cnt["نیست"] += 1
                    cls = classify(raw) if classify else ""
                    if cls:
                        cnt[f"نیست: {cls}"] += 1
                    miss.append((k, n, raw, cls))
                    if len(samples) < ctx.samples:
                        samples.append(tuple(k) + (raw,))
        in_scope = cnt["پیدا شد"] + cnt["نیست"]
        rec = {"خروجی اپ": frame, "موضوع": what, "ستون اپ": c, "دانه": " + ".join(keys),
               "مقدار در فایل کارشناسان": total, "کلید در خروجی نیست": cnt["کلید در خروجی نیست"],
               "پیدا شد": cnt["پیدا شد"], "نیست": cnt["نیست"],
               "نرخ نبودن": round(cnt["نیست"] / in_scope, 4) if in_scope else ""}
        for lab in sorted(x for x in cnt if x.startswith("نیست: ")):
            rec[lab] = cnt[lab]
        rec["نمونه"] = ctx.sample(samples)
        rows.append(rec)
        if c == "همه ستون‌ها":
            missing_all = miss
    if not present:
        rows.append({"خروجی اپ": frame, "موضوع": what, "ستون اپ": "", "دانه": " + ".join(keys),
                     "مقدار در فایل کارشناسان": total, "توضیح": "هیچ‌کدام از ستون‌ها در این خروجی نیست: " + ", ".join(app_cols)})
    return rows, missing_all


def column_lineage(app: Path, columns=LINEAGE_COLUMNS) -> list:
    """گراف ایستا: کدام فایل‌های gsi/ و app/ نام هر ستون را می‌خوانند (جایی که عیب آن ستون دیده می‌شود)."""
    files = []
    for top in ("gsi", "app"):
        root = app / top
        if root.is_dir():
            files += [f for f in root.rglob("*.py") if "__pycache__" not in f.parts]
    texts = {}
    for f in files:
        try:
            texts[f] = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
    rows = []
    for col in columns:
        if col.endswith("*"):
            base = col[:-1]
            pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(base) + r"[A-Z0-9_]+")
            short = base.split("_", 1)[1] if base.startswith("MOGH_") else ""
        else:
            pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(col) + r"(?![A-Za-z0-9_])")
            short = col.split("_", 1)[1] if col.startswith("MOGH_") else ""
        # داخل آداپتر ستون‌های MOGH_ با p("…") ساخته می‌شوند
        pat_p = re.compile(r"\bp\(\s*[\"']" + re.escape(short) + (r"[A-Z0-9_]*" if col.endswith("*") else "") + r"[\"']\s*\)") \
            if short else None
        hits, names = [], set()
        for f, t in texts.items():
            n = len(pat.findall(t)) + (len(pat_p.findall(t)) if pat_p else 0)
            if n:
                hits.append((f, n))
                names.update(pat.findall(t) if col.endswith("*") else [])
        hits.sort(key=lambda x: -x[1])
        layers = Counter()
        for f, _ in hits:
            rel = f.relative_to(app).parts
            layers["/".join(rel[:2]) if len(rel) > 2 else rel[0]] += 1
        rows.append({"ستون": col, "تعداد فایل": len(hits), "تعداد رخداد": sum(n for _, n in hits),
                     "لایه‌ها": "، ".join(f"{k}({v})" for k, v in layers.most_common(8)),
                     "فایل‌ها (بیشترین رخداد اول)": " ؛ ".join(
                         f"{f.relative_to(app).as_posix()}({n})" for f, n in hits[:10]),
                     "نام‌های منطبق": "، ".join(sorted(names)[:12])})
    return rows


def load_published_mart(wh_path: str):
    """جدول تخت منتشرشده (لایه mart، df) از انبار با اتصال فقط‌خواندنی. (فریم یا None، توضیح)."""
    if not wh_path or not os.path.isfile(wh_path):
        return None, f"انبار پیدا نشد: {wh_path}"
    try:
        uri = Path(wh_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            row = conn.execute("select run_id from wh_current where slot='report'").fetchone()
            if not row:
                return None, "نسخه منتشرشده (wh_current/report) نیست"
            fr = conn.execute("select name,object_sha,row_count from wh_frame where run_id=? and layer='mart' "
                              "and name in ('df','main') order by case name when 'df' then 0 else 1 end",
                              (row[0],)).fetchone()
        finally:
            conn.close()
        if not fr:
            return None, "فریم جدول تخت (mart/df) در نسخه منتشرشده نیست"
        from gsi.warehouse.objects import ObjectStore, objects_root
        from gsi.warehouse.framecodec import decode_frame
        df = decode_frame(ObjectStore(objects_root(Path(wh_path))).get(fr[1], "parquet"))
        return df, f"mart/{fr[0]} از اجرای {row[0]} ({len(df)} ردیف)"
    except Exception as ex:
        return None, f"خواندن جدول تخت منتشرشده ممکن نشد: {type(ex).__name__}: {ex}"


def reconcile(lines, app_frames: dict, ctx: Ctx, rb, main_frame=None):
    """app_frames: {عنوان: (فریم، دانه بارنامه/وضعیت)}؛ مقدارها با فریم‌هایی که ستون MOGH_QTY_* دارند."""
    state_cols, unknown_col = part_state_columns()
    exp = expert_positions(lines, rb, list(state_cols))
    codes = [c[4:] for c in exp.columns if c.startswith("QTY_") and c not in ("QTY_UNKNOWN", "QTY_IN_CUSTOMS_NET")]
    measures = [(f"وضعیت {c}", f"QTY_{c}", state_cols.get(c, f"MOGH_QTY_{c}")) for c in codes]
    measures.append(("وضعیت نامشخص", "QTY_UNKNOWN", unknown_col))
    if "IN_CUSTOMS" in codes:
        measures.append(("در گمرک خالص (منهای ترخیص‌شده)", "QTY_IN_CUSTOMS_NET", state_cols.get("IN_CUSTOMS", "MOGH_QTY_IN_CUSTOMS")))
    qty_rows, set_rows = [], []
    item_tot = expert_item_totals(lines)
    for label, (df, grain) in app_frames.items():
        if df is None:
            continue
        qty_rows += compare_measures(exp, df, measures, label, ctx)
        if any(c in df.columns for c in ("MOGH_ORDER_QTY_SUM", "MOGH_PI_VALUE_SUM")):
            # مقدار و ارزش سطح قلم که روی هر پارت تکرار می‌شوند؛ جمع ساده روی ردیف‌ها چندبرابر می‌کند.
            qty_rows += compare_measures(item_tot, df, [
                ("مقدار سفارش (هر قلم یک بار)", "ORDER_QTY", "MOGH_ORDER_QTY_SUM"),
                ("ارزش PI سفارش (هر قلم یک بار، یک ارز)", "PI_VALUE", "MOGH_PI_VALUE_SUM")],
                label, ctx, keys=("KEY_ORDER",))
        by = ["KEY_ORDER", "KEY_MATERIAL"] if grain == "om" else ["KEY_ORDER"]
        bl_sets, st_sets = defaultdict(dict), defaultdict(dict)
        for _, r in exp.iterrows():
            k = tuple(clean(r[x]) for x in by)
            bl_sets[k].update(r["BLS"])
            st_sets[k].update(r["STATUSES"])

        def bl_class(raw):
            try:
                ok, _ = rb.validate_bl(raw)
                return "معتبر در rulebook" if ok else "رد در rulebook"
            except Exception:
                return ""
        rows, _ = compare_sets({k: v for k, v in bl_sets.items() if v}, df, by, APP_BL_COLS, norm_bl, label,
                               "بارنامه", ctx, classify=bl_class if hasattr(rb, "validate_bl") else None)
        set_rows += rows
        rows, _ = compare_sets({k: v for k, v in st_sets.items() if v}, df, by, APP_STATUS_COLS,
                               lambda v: status_key(rb, v), label, "Order Status", ctx)
        set_rows += rows
    return exp, qty_rows, set_rows


def audit_reconcile(sources, ctx: Ctx, app: Path, wh_path: str = "", mart_df=None, rb=None):
    import pandas as pd
    print("۱۲) تطبیق فایل کارشناسان با خروجی‌های اپ ...")
    try:
        if rb is None:
            from gsi.rulebook import get_rulebook
            rb = get_rulebook()
    except Exception as ex:
        ctx.fail("rulebook", ex)
        return
    mogh = sources.get("moghavemat") or {}
    lines = mogh.get("lines")
    n_bad = 0
    if not isinstance(lines, pd.DataFrame) or lines.empty:
        ctx.find("اطلاع", "۱۲ تطبیق", "خلاصه بخش ۱۲", 0, "فریم moghavemat/lines نیست یا خالی است؛ تطبیق انجام نشد.")
    else:
        pub, note = load_published_mart(wh_path)
        ctx.add("12_تطبیق_منبع", {"منبع": "جدول تخت منتشرشده", "وضعیت": note})
        frames = {"moghavemat/inventory": (mogh.get("inventory"), "om"),
                  "moghavemat/main": (mogh.get("main"), "om"),
                  "جدول تخت منتشرشده": (pub, "order")}
        if isinstance(mart_df, pd.DataFrame):
            frames["جدول تخت همین اجرا (--mart)"] = (mart_df, "order")
            ctx.add("12_تطبیق_منبع", {"منبع": "جدول تخت همین اجرا", "وضعیت": f"{len(mart_df)} ردیف"})
        try:
            exp, qty_rows, set_rows = reconcile(lines, frames, ctx, rb)
            ctx.add("12_تطبیق_منبع", {"منبع": "فایل کارشناسان (moghavemat/lines)",
                                       "وضعیت": f"{len(lines)} ردیف، {len(exp)} Order×Material، "
                                                f"{int(exp['SHIPMENTS'].sum()) if len(exp) else 0} محموله"})
            for r in qty_rows:
                ctx.add("12_تطبیق_مقدار", r)
                if r.get("ناهمخوانی"):
                    n_bad += 1
                    ctx.find("بالا", "تطبیق", f"{r['خروجی اپ']}: {r['سنجه']} با فایل کارشناسان نمی‌خواند",
                             r["ناهمخوانی"], f"نرخ ناهمخوانی {r['نرخ ناهمخوانی']} در {r['گروه مقایسه‌شده']} Order×Material "
                             f"(ستون {r['ستون اپ']}). قاعده مستقل: هر محموله یک بار.", r.get("نمونه", ""))
            for r in set_rows:
                ctx.add("12_تطبیق_بارنامه_وضعیت", r)
                if r.get("ستون اپ") == "همه ستون‌ها" and r.get("نیست"):
                    n_bad += 1
                    valid_missing = r.get("نیست: معتبر در rulebook", 0)
                    rejected = r.get("نیست: رد در rulebook", 0)
                    sev = ("بالا" if valid_missing else "متوسط") if r["موضوع"] == "بارنامه" else "متوسط"
                    split = (f" از این‌ها {valid_missing} بارنامه معتبر در rulebook است و {rejected} را "
                             "validate_bl رد کرده (شاید بارنامه هوایی یا شماره با فاصله/نقطه باشد؛ نمونه را ببینید)."
                             if r["موضوع"] == "بارنامه" else "")
                    ctx.find(sev, "تطبیق", f"{r['خروجی اپ']}: {r['موضوع']} فایل کارشناسان در خروجی نیست", r["نیست"],
                             f"در دانه {r['دانه']}، {r['نیست']} مقدار (نرخ {r['نرخ نبودن']}) در هیچ ستون "
                             f"{'، '.join(APP_BL_COLS if r['موضوع'] == 'بارنامه' else APP_STATUS_COLS)} نیامده است."
                             + split, r.get("نمونه", ""))
            conf = int(exp["CONFLICT_SHIPMENTS"].sum()) if len(exp) else 0
            if conf:
                ctx.find("متوسط", "تطبیق", "محموله با چند وضعیت در فایل کارشناسان", conf,
                         "یک شناسه محموله (Part No./BL/Transport No.) در ردیف‌های مختلف وضعیت متفاوت دارد.")
        except Exception as ex:
            ctx.fail("تطبیق کارشناس", ex)
        ctx.find("اطلاع", "۱۲ تطبیق", "خلاصه بخش ۱۲", n_bad,
                 f"{n_bad} سنجه/ستون با فایل کارشناسان نمی‌خواند (برگه‌های 12_تطبیق_*). جدول تخت منتشرشده: {note}")
    try:
        for r in column_lineage(app):
            ctx.add("12_گراف_ستون‌ها", r)
    except Exception as ex:
        ctx.fail("گراف ستون‌ها", ex)


# ───────────────────────────── نوشتن خروجی ─────────────────────────────
SHEET_TITLES = {
    "0_خلاصه": "خلاصه یافته‌ها",
}


def sheet_order(name: str):
    """ترتیب عددی برگه‌ها (۹ پیش از ۱۰)."""
    m = re.match(r"(\d+)_", name)
    return (int(m.group(1)) if m else 99, name)


def write_excel(ctx: Ctx, out: Path, meta: dict):
    import pandas as pd
    ctx.findings.sort(key=lambda f: (SEV_ORDER.get(f["شدت"], 9), f["بخش"]))
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        pd.DataFrame(ctx.findings or [{"شدت": "اطلاع", "موضوع": "یافته‌ای نبود"}]).to_excel(xw, sheet_name="0_خلاصه", index=False)
        pd.DataFrame([{"کلید": k, "مقدار": v} for k, v in meta.items()]).to_excel(xw, sheet_name="0_اجرا", index=False)
        sheets = dict(ctx.sheets)
        if ctx.errors:
            sheets["9_خطاها"] = ctx.errors
        for name in sorted(sheets, key=sheet_order):
            pd.DataFrame(sheets[name]).to_excel(xw, sheet_name=name[:31], index=False)
        for ws in xw.book.worksheets:
            ws.sheet_view.rightToLeft = True
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max((len(str(c.value)) for c in list(col)[:200] if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)


def write_text(ctx: Ctx, out: Path, meta: dict):
    lines = [f"GSI grain audit {VERSION}"] + [f"{k}: {v}" for k, v in meta.items()] + [""]
    for f in ctx.findings:
        lines.append(f"[{f['شدت']}] {f['بخش']} | {f['موضوع']} | تعداد {f['تعداد']}")
        if f["توضیح"]:
            lines.append(f"    {f['توضیح']}")
        if f["نمونه"]:
            lines.append(f"    نمونه: {f['نمونه']}")
    if ctx.errors:
        lines += ["", "خطاهای خود اسکریپت:"] + [f"  {e['کجا']}: {e['خطا']}" for e in ctx.errors]
    out.write_text("\n".join(lines), encoding="utf-8")


GRAPH_TOP = 24


def write_graph(ctx: Ctx, out: Path, app: Path):
    """گراف HTML آفلاین: ستون‌های چندمقداری فایل جزئی ← وضعیت نگهداری در فریم تجمیعی ← فایل‌های کد خواننده.

    پهنای نوار = احتمال چندمقداری (با بازه ۹۵٪)؛ رنگ: قرمز = مقدار از دست رفت، کهربایی = فریم تجمیعی ندارد یا
    ستون در آن نیست، سبز = همه مقدارها ماند. جای احتمالی رخداد تازه = ستون قرمز یا کهربایی با احتمال بالا که
    فایل‌های زیادی آن را می‌خوانند. هیچ مقدار داده‌ای (نمونه) در گراف نیست.
    """
    import html as H
    rows = [r for r in ctx.sheets.get("10_فروریختگی", []) if (r.get("گروه چندمقداری") or 0) > 0]
    best = {}
    for r in rows:              # هر ستون: بدترین جفت
        k = r["ستون"]
        score = (r.get("وضعیت نگهداری") == KEEP_ONE, r.get("ریسک (سهم × ردیف)", 0), r.get("احتمال چندمقداری", 0))
        if k not in best or score > best[k][0]:
            best[k] = (score, r)
    items = [r for _, r in sorted(best.values(), key=lambda x: x[0], reverse=True)][:GRAPH_TOP]
    cols = [r["ستون"] for r in items]
    lineage = {}
    try:
        for L in column_lineage(app, cols):
            files = [x.rsplit("(", 1)[0] for x in str(L.get("فایل‌ها (بیشترین رخداد اول)", "")).split(" ؛ ") if x]
            lineage[L["ستون"]] = files[:6]
    except Exception as ex:
        ctx.fail("گراف HTML", ex)
    files = []
    for c in cols:
        for f in lineage.get(c, []):
            if f not in files:
                files.append(f)

    def color(st):
        if st == KEEP_ONE:
            return "#c0392b"
        if st.startswith(BY_DESIGN_STATUS):
            return "#5d6d7e"
        if st.startswith(KEEP_ALL) or st.startswith("سنجیده") or st.startswith("سنجه") or st.startswith("پرچم"):
            return "#138d75"
        return "#d68910"
    rowh, top = 30, 60
    h = top + max(len(cols), len(files), 1) * rowh + 40
    W = 1400
    x_bar, x_status, x_edge, xs_file = 960, 830, 600, 380
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="100%" direction="ltr" '
           f'style="direction:ltr" font-family="Ravi, IRANSans, Tahoma, sans-serif" font-size="12">']
    svg.append(f'<text x="{W - 20}" y="30" direction="rtl" text-anchor="start" font-size="15" font-weight="700">'
               f'ستون فایل جزئی (احتمال چندمقداری) ← فایل‌های کد که آن را می‌خوانند</text>')
    ypos_file = {f: top + i * rowh for i, f in enumerate(files)}
    for i, r in enumerate(items):
        y = top + i * rowh
        st = str(r.get("وضعیت نگهداری", ""))
        pr = float(r.get("احتمال چندمقداری") or 0)
        c = color(st)
        for f in lineage.get(r["ستون"], []):
            yf = ypos_file[f]
            svg.append(f'<path d="M{x_edge},{y} C{x_edge - 110},{y} {xs_file + 110},{yf} {xs_file + 10},{yf}" '
                       f'fill="none" stroke="{c}" stroke-opacity="0.35" stroke-width="{1 + 5 * pr:.1f}"/>')
        svg.append(f'<rect x="{x_bar - 120}" y="{y - 9}" width="120" height="18" rx="3" fill="#eef2f3"/>')
        svg.append(f'<rect x="{x_bar - 120 * pr:.1f}" y="{y - 9}" width="{120 * pr:.1f}" height="18" rx="3" '
                   f'fill="{c}" fill-opacity="0.85"/>')
        svg.append(f'<text x="{W - 20}" y="{y + 4}" direction="rtl" text-anchor="start"><tspan font-weight="700">{H.escape(r["ستون"])}</tspan>'
                   f' · {pr * 100:.1f}٪ ({H.escape(str(r.get("بازه ۹۵٪ (ویلسون)", "")))})</text>')
        svg.append(f'<text x="{x_status}" y="{y + 4}" direction="rtl" text-anchor="start" fill="{c}" font-size="11">'
                   f'{H.escape(st[:40])}</text>')
    for f, y in ypos_file.items():
        svg.append(f'<circle cx="{xs_file}" cy="{y}" r="5" fill="#0e6655"/>')
        svg.append(f'<text x="{xs_file - 12}" y="{y + 4}" text-anchor="end" direction="ltr">{H.escape(f)}</text>')
    svg.append("</svg>")
    legend = ("<p><b style='color:#c0392b'>قرمز</b>: فریم تجمیعی فقط یک مقدار نگه داشت (از دست رفتن مقدار). "
              "<b style='color:#d68910'>کهربایی</b>: ستون چندمقداری است ولی فریم تجمیعی ندارد یا ستون در آن نیست. "
              "<b style='color:#138d75'>سبز</b>: همه مقدارها ماند. <b style='color:#5d6d7e'>خاکستری</b>: یک مقدار طبق قاعده نوشته‌شده "
              "(مثل زودترین مهلت تعهد). درصد = سهم سفارش‌هایی که در این ستون بیش از یک "
              "مقدار دارند؛ داخل پرانتز بازه اطمینان ۹۵٪ ویلسون برای سفارش تازه. ضخامت خط = همان احتمال.</p>"
              "<p>جای احتمالی رخداد تازه: ستون قرمز یا کهربایی با درصد بالا، در فایل‌هایی که بیشترین خط به آن‌ها "
              "می‌رسد. جزئیات در برگه‌های 10_فروریختگی و 12_گراف_ستون‌ها.</p>")
    page = ('<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>گراف فروریختگی GSI</title><style>body{font-family:Ravi,IRANSans,Tahoma,sans-serif;'
            'margin:16px;color:#1b2631;background:#fff}p{max-width:980px;line-height:1.8}</style></head><body>'
            f'<h2>گراف احتمال فروریختگی و مسیر ستون‌ها</h2>{legend}'
            + ("".join(svg) if items else "<p>هیچ ستون چندمقداری دیده نشد.</p>") + "</body></html>")
    out.write_text(page, encoding="utf-8")


# ───────────────────────────── اصلی ─────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GSI grain / redundancy / key audit (read-only)")
    ap.add_argument("--ini", default=str(HERE / "grain_audit.ini"))
    ap.add_argument("--mart", action="store_true", help="بخش ۷ (جدول تخت) هم ساخته شود")
    ap.add_argument("--no-files", action="store_true", help="بخش ۱ و ۲ (پروفایل خام فایل‌ها) رد شود")
    ap.add_argument("--keep-temp", action="store_true")
    a = ap.parse_args(argv)

    ini = read_ini(Path(a.ini))
    app = find_app_dir(ini.get("app_dir", ""))
    env_cmd = read_env_cmd(app / "GSI_ENV.cmd")
    applied = {}
    for k, var in PATH_KEYS.items():
        v = ini.get(k, "")
        if v:
            os.environ[var] = v
            applied[var] = f"{v} (ini)"
        elif var in os.environ:
            applied[var] = f"{os.environ[var]} (محیط)"
        elif env_cmd.get(var):
            os.environ[var] = env_cmd[var]
            applied[var] = f"{env_cmd[var]} (GSI_ENV.cmd)"
        else:
            applied[var] = "(پیش‌فرض اپ)"
    for var, v in env_cmd.items():
        if var not in os.environ and var in ("GSI_DATA_ROOT", "GSI_DWH_PATH"):
            os.environ[var] = v

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = Path(ini.get("out") or (HERE / "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = int(ini.get("samples", "5") or 5)
    mask = ini.get("mask_keys", "no").strip().lower() in ("1", "yes", "true", "on", "بله")
    want_mart = a.mart or ini.get("mart", "no").strip().lower() in ("1", "yes", "true", "on", "بله")

    sys.path.insert(0, str(app))
    os.chdir(app)
    # انبار اصلی: پیش از هدایت نوشتن‌ها به انبار موقت پیدا می‌شود
    real_wh = ini.get("warehouse", "") or os.environ.get("GSI_DWH_PATH", "")
    if not real_wh:
        try:
            from gsi.warehouse.store import default_data_root
            real_wh = str(default_data_root() / "warehouse.sqlite")
        except Exception:
            real_wh = ""
    tmp = Path(tempfile.mkdtemp(prefix="gsi_grain_audit_", dir=str(out_dir)))
    os.environ["GSI_DWH_PATH"] = str(tmp / "audit_scratch.sqlite")
    os.environ["GSI_HISTORICAL_WAREHOUSE_PATH"] = str(tmp / "audit_hist.sqlite3")
    os.environ["GSI_OUTPUT"] = str(tmp / "output")
    os.environ["GSI_LOGS"] = str(tmp / "logs")
    os.environ.setdefault("GSI_DAILY_REPORT_ROOT", str(tmp / "daily"))

    ctx = Ctx(samples, mask)
    t0 = time.time()
    meta = {"نسخه اسکریپت": VERSION, "زمان": datetime.now().strftime("%Y-%m-%d %H:%M"), "پوشه اپ": str(app),
            "انبار اصلی (فقط‌خواندنی)": real_wh, "پنهان‌سازی کلیدها": mask, "بخش جدول تخت": want_mart}
    try:
        from gsi.version import PACKAGE_VERSION
        meta["نسخه اپ"] = PACKAGE_VERSION
    except Exception:
        pass
    meta.update({f"مسیر {k}": v for k, v in applied.items()})
    print(f"GSI grain audit {VERSION} | اپ: {app}")
    try:
        if not a.no_files:
            audit_files(ctx)
        sources, timing = load_frames(ctx)
        meta["زمان آداپترها (ثانیه)"] = json.dumps(timing, ensure_ascii=False)
        specs = declared_keys(app)
        audit_frames(sources, specs, ctx)
        audit_keys(sources, ctx)
        audit_facts(sources, ctx)
        audit_population(sources, ctx)
        mart_df = None
        if want_mart:
            mart_df = audit_mart(sources, ctx)
        audit_warehouse(real_wh, ctx)
        audit_collapse(sources, specs, ctx)
        audit_lexicon(sources, ctx, app=app)
        audit_reconcile(sources, ctx, app, real_wh, mart_df)
    except Exception as ex:
        ctx.fail("اجرای کلی", ex)
    finally:
        meta["مدت کل (ثانیه)"] = round(time.time() - t0, 1)
        xlsx = out_dir / f"GSI_GRAIN_AUDIT_{stamp}.xlsx"
        txt = out_dir / f"GSI_GRAIN_AUDIT_{stamp}_summary.txt"
        try:
            write_excel(ctx, xlsx, meta)
        except Exception as ex:
            ctx.fail("نوشتن Excel", ex)
        write_text(ctx, txt, meta)
        graph = out_dir / f"GSI_GRAIN_AUDIT_{stamp}_graph.html"
        try:
            write_graph(ctx, graph, app)
        except Exception as ex:
            print(f"⚠️ گراف HTML ساخته نشد: {ex}")
        if not a.keep_temp:
            import gc
            gc.collect()
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n✅ پایان. {len(ctx.findings)} یافته، {len(ctx.errors)} خطای اسکریپت.")
    print(f"   {xlsx}\n   {txt}\n   {graph}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
