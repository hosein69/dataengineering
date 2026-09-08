# -*- coding: utf-8 -*-
"""خواندن سورس‌ها به یک قالب بلندِ واحد.

هر سورس، هرچه باشد، در نهایت به همین جدول بلند تبدیل می‌شود:

    person_key | metric_key | value | sample_n | source

مزیت: افزودن سورس جدید فقط یک reader می‌خواهد، نه دست بردن در موتور.
پکیج قبلی منطق خواندن، محاسبه و گزارش را در سه اسکریپت ~۱۰٬۰۰۰ خطی
درهم بافته بود و همین باعث می‌شد تغییر یک نگاشت، کل زنجیره را بلرزاند.
"""
from __future__ import annotations

__contract__ = 1

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

LONG_COLUMNS = ["person_key", "metric_key", "value", "sample_n", "source"]

#: نام‌های محتمل هر ستون در فایل‌های ورودی (تحمل نویز نام‌گذاری)
ALIASES: Dict[str, List[str]] = {
    "person_key": ["person_key", "personnel_id", "کد پرسنلی", "شماره پرسنلی",
                   "employee_id", "کد ملی پرسنلی"],
    "full_name": ["full_name", "employee_name", "نام", "نام و نام خانوادگی",
                  "کارشناس", "نام کارشناس"],
    "metric_key": ["metric_key", "metric", "شاخص", "kpi", "kpi_key"],
    "value": ["value", "مقدار", "val", "raw_value"],
    "sample_n": ["sample_n", "n", "denominator", "مخرج", "حجم نمونه"],
}


def _pick(df: pd.DataFrame, target: str) -> Optional[str]:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for cand in ALIASES.get(target, [target]):
        c = lower.get(cand.strip().lower())
        if c is not None:
            return c
    return None


def normalize_long(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """یک جدول بلندِ آماده را به قالب استاندارد می‌آورد."""
    out = pd.DataFrame()
    for col in ("person_key", "metric_key", "value", "sample_n"):
        src = _pick(df, col)
        out[col] = df[src] if src else None
    out["source"] = source
    out["person_key"] = out["person_key"].astype(str).str.strip()
    out["metric_key"] = out["metric_key"].astype(str).str.strip()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["sample_n"] = pd.to_numeric(out["sample_n"], errors="coerce")
    return out.dropna(subset=["person_key", "metric_key"])


def melt_wide(df: pd.DataFrame, source: str,
              metric_columns: Optional[Iterable[str]] = None,
              sample_suffix: str = "_n") -> pd.DataFrame:
    """جدول عریض (هر شاخص یک ستون) را به قالب بلند تبدیل می‌کند.

    اگر ستون ``<metric>_n`` وجود داشته باشد، به‌عنوان اندازه نمونه همان
    شاخص برداشته می‌شود.
    """
    pk = _pick(df, "person_key")
    if pk is None:
        return pd.DataFrame(columns=LONG_COLUMNS)
    ignore = {pk} | {c for c in df.columns if str(c).endswith(sample_suffix)}
    name_col = _pick(df, "full_name")
    if name_col:
        ignore.add(name_col)
    cols = list(metric_columns) if metric_columns else [
        c for c in df.columns if c not in ignore
        and pd.to_numeric(df[c], errors="coerce").notna().any()]
    rows = []
    for c in cols:
        n_col = f"{c}{sample_suffix}"
        rows.append(pd.DataFrame({
            "person_key": df[pk].astype(str).str.strip(),
            "metric_key": str(c),
            "value": pd.to_numeric(df[c], errors="coerce"),
            "sample_n": (pd.to_numeric(df[n_col], errors="coerce")
                         if n_col in df.columns else None),
            "source": source,
        }))
    if not rows:
        return pd.DataFrame(columns=LONG_COLUMNS)
    return pd.concat(rows, ignore_index=True).dropna(subset=["value"])


def read_any(path: str | Path, source: str) -> pd.DataFrame:
    """Excel یا CSV — بلند یا عریض — را می‌خواند و استاندارد می‌کند."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=LONG_COLUMNS)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)
    if _pick(df, "metric_key") is not None:
        return normalize_long(df, source)
    return melt_wide(df, source)


def read_org_map(path: str | Path) -> pd.DataFrame:
    """نقشه سازمانی — قالب ``{"people": {name: {...}}}`` یا جدول تخت."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    if p.suffix.lower() == ".json":
        raw = json.loads(p.read_text(encoding="utf-8"))
        people = raw.get("people", raw) if isinstance(raw, dict) else {}
        rows = []
        for name, rec in people.items():
            rec = dict(rec or {})
            rec.setdefault("full_name", name)
            rows.append(rec)
        df = pd.DataFrame(rows)
    else:
        df = pd.read_excel(p) if p.suffix.lower().startswith(".xls") else pd.read_csv(p)
    ren = {"name": "full_name", "management": "management", "head": "head",
           "manager": "manager", "role": "role", "responsible": "responsible",
           "department": "department", "job_family": "job_family"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    for c in ("full_name", "management", "department", "job_family", "role",
              "manager", "head", "person_key", "personnel_id", "vice"):
        if c not in df.columns:
            df[c] = ""
    return df


def load_inputs(input_dir: str | Path,
                patterns: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """همه فایل‌های پوشه ورودی را می‌خواند و یک جدول بلند می‌سازد."""
    d = Path(input_dir)
    if not d.exists():
        return pd.DataFrame(columns=LONG_COLUMNS)
    patterns = patterns or {
        "document_checking": "*ocument*hecking*",
        "il_analysis": "*IL*",
        "other_units": "*",
    }
    seen: set = set()
    frames = []
    for source, pat in patterns.items():
        for f in sorted(d.glob(pat)):
            if f.name.startswith("~$") or f in seen or f.is_dir():
                continue
            if f.suffix.lower() not in (".xlsx", ".xlsm", ".xls", ".csv"):
                continue
            seen.add(f)
            frames.append(read_any(f, source))
    if not frames:
        return pd.DataFrame(columns=LONG_COLUMNS)
    return pd.concat(frames, ignore_index=True)
