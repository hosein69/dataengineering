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
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ..identity import keys as keymod
from . import aibl as aiblmod
from . import registry as regmod

LONG_COLUMNS = ["person_key", "person_code", "metric_key", "value",
                "sample_n", "source"]

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
    # کلید متعارف (اتصال) و شکل خام (نمایش) — «GS-1234» و «1234» یک نفرند.
    out = keymod.attach(out)
    out["metric_key"] = out["metric_key"].astype(str).str.strip()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["sample_n"] = pd.to_numeric(out["sample_n"], errors="coerce")
    out = out.dropna(subset=["person_key", "metric_key"])
    return out[out["person_key"].ne("")]


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
            "person_key": df[pk].map(keymod.clean_person_key),
            "person_code": df[pk].map(keymod.clean_text),
            "metric_key": str(c),
            "value": pd.to_numeric(df[c], errors="coerce"),
            "sample_n": (pd.to_numeric(df[n_col], errors="coerce")
                         if n_col in df.columns else None),
            "source": source,
        }))
    if not rows:
        return pd.DataFrame(columns=LONG_COLUMNS)
    out = pd.concat(rows, ignore_index=True).dropna(subset=["value"])
    return out[out["person_key"].ne("")]


def is_aibl(df: pd.DataFrame) -> bool:
    """آیا این جدول، پروندهٔ زنجیره تأمین است؟

    نشانه: دست‌کم یکی از ستون‌های حوزه مسئولیت. این ستون‌ها را فقط AIBL
    می‌سازد، پس تشخیص قطعی است و حدس نیست.
    """
    return any(s.key in df.columns for s in aiblmod.SCOPES)


def read_any(path: str | Path, source: str) -> pd.DataFrame:
    """Excel یا CSV — بلند یا عریض — را می‌خواند و استاندارد می‌کند."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=LONG_COLUMNS)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)
    if is_aibl(df):
        return aiblmod.to_long(df, source).long
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
        people = raw.get("people", raw) if isinstance(raw, dict) else raw
        rows = []
        if isinstance(people, dict):          # {نام: {…}}
            for name, rec in people.items():
                rec = dict(rec or {})
                rec.setdefault("full_name", name)
                rows.append(rec)
        elif isinstance(people, list):        # [{…}, {…}] — همان‌قدر رایج
            rows = [dict(r) for r in people if isinstance(r, dict)]
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
    # کلید فرد ممکن است نیامده باشد؛ از کد پرسنلی و در نهایت از نام پر می‌شود.
    key = df["person_key"].astype(str).str.strip()
    for alt in ("personnel_id", "full_name"):
        blank = key.eq("") | key.str.lower().isin(("nan", "none"))
        if blank.any():
            key = key.mask(blank, df[alt].astype(str).str.strip())
    df["person_code"] = key.map(keymod.clean_text)
    df["person_key"] = key.map(keymod.clean_person_key)
    return df


#: نام‌های محتملِ فایل نقشه سازمانی در پوشه ورودی
ORG_MAP_PATTERNS = ("organization_map.json", "org_map.json", "*rganization*.json",
                    "*rganization*.xlsx", "*ساختار*.xlsx", "*سازمان*.xlsx")


def find_org_map(input_dir: str | Path) -> Optional[Path]:
    """نقشه سازمانی را در پوشه ورودی پیدا می‌کند — با چند نام محتمل.

    بدون این، خط فرمان ساختار سازمانی را اصلاً نمی‌خواند و همه در یک
    «گروه همتای عمومی» می‌افتادند: مقایسه کارشناس ترخیص با کارشناس
    اعتبارات، که دقیقاً همان بی‌عدالتی‌ای است که این پکیج قرار است
    جلویش را بگیرد.
    """
    d = Path(input_dir)
    if not d.is_dir():
        return None
    for pat in ORG_MAP_PATTERNS:
        for f in sorted(d.glob(pat)):
            if f.is_file() and not f.name.startswith("~$"):
                return f
    return None


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


def explain_missing(chosen: str | Path) -> str:
    """چرا داده‌ای پیدا نشد — با فهرست **هر مسیری که واقعاً بررسی شد**.

    پیام قبلی فقط یک مسیر ثابت را نشان می‌داد. کاربری که پکیج را جای
    دیگری باز کرده بود، از آن پیام می‌فهمید «سورس تعریف نشده»، در حالی
    که مشکل «سورس همان‌جا بود، ولی کد جای دیگر را گشت» بود.
    """
    from ..config.settings import DATA_SUFFIXES, has_data, input_candidates

    chosen_p = Path(chosen).resolve()
    lines = ["هیچ فردی برای سنجش پیدا نشد.", "",
             "مسیرهایی که برای پوشه ورودی بررسی شدند:"]
    seen: List[Path] = []
    for c in [chosen_p] + [x for x in input_candidates()]:
        c = Path(c).resolve()
        if c in seen:
            continue
        seen.append(c)
        if not c.is_dir():
            state = "وجود ندارد"
        else:
            files = [f for f in c.iterdir() if f.is_file()
                     and f.suffix.lower() in DATA_SUFFIXES
                     and not f.name.startswith("~$")]
            state = (f"{len(files)} فایل داده" if files
                     else "هست ولی فایل داده‌ای ندارد")
        mark = "◀ انتخاب‌شده" if c == chosen_p else ""
        lines.append(f"  • {c} — {state} {mark}".rstrip())
    lines += [
        "",
        "یکی از این سه راه:",
        f"  ۱) فایل‌های xlsx/csv واحدها را در «{chosen_p}» بگذارید",
        "  ۲) یا مسیر را صریح بدهید:  set HRP_INPUT=<مسیر پوشه>",
        "  ۳) یا برای دموی بدون داده:  python -m hrperf.cli demo",
        "",
        "قالب فایل — یکی از این دو:",
        "  بلند:  person_key | metric_key | value | sample_n",
        "  عریض:  person_key | <شاخص> | <شاخص>_n | ...",
        "نقشه سازمانی (اختیاری): organization_map.json در همان پوشه.",
    ]
    return "\n".join(lines)


def load_all(input_dir: str | Path) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    """همه سورس‌ها + افرادی که از خود سورس شناخته می‌شوند + یادداشت‌ها.

    پروندهٔ AIBL علاوه بر سنجه، **حوزه مسئولیت و نقش کاری** هر نفر را هم
    می‌گوید. آن را دور نمی‌ریزیم: بدون حوزه، سنجهٔ تخصصی به آدم اشتباه
    نسبت داده می‌شود.
    """
    d = Path(input_dir)
    frames: List[pd.DataFrame] = []
    peoples: List[pd.DataFrame] = []
    notes: List[str] = []
    if not d.is_dir():
        return (pd.DataFrame(columns=LONG_COLUMNS), pd.DataFrame(), notes)

    custom = regmod.load()
    seen: set = set()
    for f in sorted(d.glob("*")):
        if (f.is_dir() or f.name.startswith("~$") or f in seen
                or f.suffix.lower() not in (".xlsx", ".xlsm", ".xls", ".csv")):
            continue
        seen.add(f)
        try:
            raw = (pd.read_csv(f) if f.suffix.lower() == ".csv"
                   else pd.read_excel(f))
        except Exception as ex:                      # فایل خراب، کل اجرا را نمی‌کشد
            notes.append(f"فایل «{f.name}» خوانده نشد: {str(ex)[:60]}")
            continue
        spec = next((sp for sp in custom.values() if sp.accepts(f.name)), None)
        if spec is not None and not is_aibl(raw):
            got, msg = regmod.read(raw, spec)
            notes.extend(msg)
            if not got.empty:
                frames.append(got)
            continue
        if is_aibl(raw):
            ex_ = aiblmod.to_long(raw, f.stem)
            frames.append(ex_.long)
            peoples.append(ex_.people)
            notes.extend(ex_.notes)
        elif _pick(raw, "metric_key") is not None:
            frames.append(normalize_long(raw, f.stem))
        else:
            frames.append(melt_wide(raw, f.stem))

    long = (pd.concat(frames, ignore_index=True) if frames
            else pd.DataFrame(columns=LONG_COLUMNS))
    people = (pd.concat(peoples, ignore_index=True).drop_duplicates("person_key")
              if peoples else pd.DataFrame())
    return long, people, notes
