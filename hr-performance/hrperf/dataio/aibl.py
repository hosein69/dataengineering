# -*- coding: utf-8 -*-
"""پل AIBL → عملکرد: از پروندهٔ زنجیره تأمین به سنجهٔ فردی.

## ایدهٔ اصلی

AIBL یک ردیف به‌ازای هر پرونده می‌سازد و در آن می‌گوید **کجا، توسط چه
کسی، چه زمانی**. HR همان ردیف‌ها را می‌خواند و به‌ازای هر کارشناس، در
**حوزهٔ خودش**، سنجه می‌سازد. تعریف سنجه‌ها اینجاست، نه در AIBL: AIBL
منبعِ واقعیت است، HR مالکِ مدل عملکرد.

## چرا سه بار روی داده رد می‌شویم

هر پرونده سه صاحب دارد. یک ردیف، سه بار خوانده می‌شود — یک‌بار برای هر
حوزه — و هر بار فقط سنجه‌هایی محاسبه می‌شود که در حوزهٔ همان نفر است.
جمع کردن هر سه در یک عدد، یعنی نسبت دادن رسوب گمرکی به کارشناس
بازرگانی. این کار را نمی‌کنیم.

## آنچه محاسبه نمی‌شود، اعلام می‌شود

اگر ستون لازم در خروجی AIBL نباشد، سنجه **صفر نمی‌شود** — اصلاً ساخته
نمی‌شود و نامش در ``AiblExtract.missing`` می‌آید. صفرِ ساختگی، امتیاز
کسی را پایین می‌آورد بدون آنکه کسی بفهمد چرا.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..core.calendar import CalendarEngine
from ..identity import keys as keymod
from ..identity.scopes import ANY, OWNER_SCOPE, SCOPES, Scope

LONG_COLUMNS = ["person_key", "person_code", "metric_key", "value",
                "sample_n", "source", "scope"]

#: نامزدهای هر ستون در خروجی AIBL (نام‌ها بین نسخه‌ها کمی فرق می‌کنند)
COLS: Dict[str, Tuple[str, ...]] = {
    "owner_code": ("MOGH_KEY_EMP", "KEY_EMP"),
    "owner_name": ("PART_OWNER", "CANONICAL_EXPERT"),
    "owner_gap": ("PART_OWNER_DATA_GAP",),
    "status_stage": ("STATUS_STAGE",),
    "status_age": ("STATUS_AGE_DAYS",),
    "status_missing": ("STATUS_MISSING",),
    "status_basis": ("STATUS_BASIS",),
    "waiting_scope": ("WAITING_ON_SCOPE",),
    "conformance": ("امتیاز انطباق (٪)", "امتیاز انطباق"),
    "skipped": ("فعالیت‌های جاافتاده",),
    "violation": ("نقض ترتیب",),
    "overdue_days": ("روزهای تأخیر",),
    "dwell_days": ("روزهای رسوب",),
    "alloc_date": ("NTSW_ALLOC_DATE",),
    "buy_date": ("BUY_DATE",),
    "full_clear": ("FULL_CLEAR_DATE",),
    "partial_clear": ("PARTIAL_CLEAR_DATE",),
    "sata": ("SATA_NO",),
    "cot_date": ("COT_DATE",),
    "fin_receipt": ("FIN_RECEIPT_DATE",),
    "part_no": ("CANONICAL_PART_NO", "PART_NO"),
    "criticality": ("کد طبقه بحرانی", "CRITICALITY"),
    "value": ("CB_VALUE",),
    "transport": ("TRANSPORT_MODE", "روش حمل"),
}

#: طبقه‌هایی که «بحرانی» شمرده می‌شوند (همان تعریف drivers.py در AIBL)
CRITICAL_BANDS = ("STOCKOUT", "CRITICAL")

#: آستانهٔ «کهنه» برای صف انتظار — روز
AGING_DAYS = 30

_EMPTY = {"", "nan", "none", "nat", "-", "--", "null", "ندارد", "نامشخص"}


def _col(df: pd.DataFrame, name: str) -> Optional[str]:
    for cand in COLS.get(name, ()):
        if cand in df.columns:
            return cand
    return None


def _txt(df: pd.DataFrame, name: str) -> Optional[pd.Series]:
    c = _col(df, name)
    return df[c].fillna("").astype(str).str.strip() if c else None


def _filled(df: pd.DataFrame, name: str) -> Optional[pd.Series]:
    """آیا این فیلد پر است؟ (تهی‌های فارسی هم تهی شمرده می‌شوند)"""
    s = _txt(df, name)
    return None if s is None else ~s.str.lower().isin(_EMPTY)


def _num(df: pd.DataFrame, name: str) -> Optional[pd.Series]:
    c = _col(df, name)
    return pd.to_numeric(df[c], errors="coerce") if c else None


def _days(df: pd.DataFrame, start: str, end: str) -> Optional[pd.Series]:
    """اختلاف دو تاریخ شمسی/میلادی — با موتور تقویم، نه pandas."""
    a, b = _col(df, start), _col(df, end)
    if not a or not b:
        return None
    out = [CalendarEngine.days_between(x, y) for x, y in zip(df[a], df[b])]
    return pd.Series([np.nan if v is None else float(v) for v in out],
                     index=df.index)


@dataclass
class AiblExtract:
    """نتیجهٔ تبدیل: جدول بلند + آنچه ساخته نشد و چرا."""
    long: pd.DataFrame
    people: pd.DataFrame
    missing: Dict[str, str] = field(default_factory=dict)
    rows: int = 0
    by_scope: Dict[str, int] = field(default_factory=dict)

    @property
    def notes(self) -> List[str]:
        out = [f"{self.rows:,} ردیف پرونده از AIBL خوانده شد؛ "
               + "، ".join(f"{k}: {v} نفر" for k, v in self.by_scope.items())]
        if self.missing:
            out.append(f"{len(self.missing)} سنجه ساخته نشد چون ستونش در "
                       f"خروجی AIBL نبود: " + "، ".join(sorted(self.missing)))
        return out


# ═══════════ سنجه‌ها ═══════════
# هر تابع یک (value, sample_n) برمی‌گرداند، یا None اگر داده‌اش نیست.
Rate = Tuple[Optional[pd.Series], Optional[pd.Series]]


def _rate(mask: Optional[pd.Series]) -> Optional[pd.Series]:
    return None if mask is None else mask.astype(float)


def _scope_rows(g: pd.DataFrame, scope: Scope) -> pd.Series:
    """ردیف‌هایی که پرونده در مرحلهٔ همین حوزه ایستاده است."""
    st = _txt(g, "status_stage")
    if st is None:
        return pd.Series(True, index=g.index)
    return st.isin(scope.stages)


def _waiting(g: pd.DataFrame, scope: Scope) -> Optional[pd.Series]:
    """ردیف‌هایی که AIBL گفته توپ در زمین همین حوزه است."""
    w = _txt(g, "waiting_scope")
    if w is None:
        return None
    return w.eq(scope.fa) | w.eq(scope.key)


def _metrics_for(g: pd.DataFrame, scope: Scope) -> Dict[str, Tuple[float, int]]:
    """همهٔ سنجه‌های یک نفر در یک حوزه."""
    out: Dict[str, Tuple[float, int]] = {}

    def put(key: str, series: Optional[pd.Series]) -> None:
        if series is None:
            return
        s = pd.to_numeric(series, errors="coerce").dropna()
        if s.empty:
            return
        out[key] = (float(s.mean()), int(len(s)))

    def put_med(key: str, series: Optional[pd.Series]) -> None:
        if series is None:
            return
        s = pd.to_numeric(series, errors="coerce").dropna()
        if s.empty:
            return
        out[key] = (float(s.median()), int(len(s)))

    overdue = _num(g, "overdue_days")
    conf = _num(g, "conformance")
    skipped = _filled(g, "skipped")
    violation = _filled(g, "violation")

    on_time = None if overdue is None else overdue.le(0)
    docs = [_filled(g, n) for n in ("sata", "cot_date", "fin_receipt")]
    docs = [d for d in docs if d is not None]
    doc_ok = None
    if docs:
        doc_ok = pd.concat(docs, axis=1).all(axis=1)
    no_dev = None
    if skipped is not None or violation is not None:
        parts = [~x for x in (skipped, violation) if x is not None]
        no_dev = pd.concat(parts, axis=1).all(axis=1)

    # ── اتکاپذیری ──
    put("on_time_stage_rate", _rate(on_time))
    put("doc_accuracy_rate", _rate(doc_ok))
    full, partial = _filled(g, "full_clear"), _filled(g, "partial_clear")
    if full is not None and scope.key == "EXPERT_LOGISTICS":
        touched = full | (partial if partial is not None else False)
        if bool(touched.any()):
            put("in_full_rate", _rate(full[touched]))
    perfect = [x for x in (on_time, doc_ok, no_dev) if x is not None]
    if len(perfect) >= 2:      # «همه‌یا‌هیچ» فقط وقتی معنا دارد که چند شرط داشته باشیم
        put("perfect_flow_rate", _rate(pd.concat(perfect, axis=1).all(axis=1)))

    # ── انطباق ──
    if conf is not None:
        put("conformance_score", conf / 100.0)
    put("skipped_activity_rate", _rate(skipped))
    put("order_violation_rate", _rate(violation))

    # ── پاسخ‌گویی ──
    age = _num(g, "status_age")
    wait = _waiting(g, scope)
    if age is not None and wait is not None and bool(wait.any()):
        put_med("ball_in_court_days", age[wait])
        put("aging_backlog_rate", _rate(age[wait].gt(AGING_DAYS)))
    if age is not None:
        own = _scope_rows(g, scope)
        if bool(own.any()):
            put_med("own_leg_median_days", age[own])

    # ── صیانت ──
    if scope.key == "EXPERT_COMMERCIAL":
        put("overdue_commitment_rate", _rate(None if overdue is None
                                             else overdue.gt(0)))
        put_med("allocation_lag_days", _days(g, "alloc_date", "buy_date"))
    if scope.key == "EXPERT_LOGISTICS":
        put_med("customs_dwell_days", _num(g, "dwell_days"))

    # ── کیفیت داده ──
    if scope.owner:
        gap = _filled(g, "owner_gap")
        put("owner_field_completeness", _rate(None if gap is None else ~gap))
    miss = _filled(g, "status_missing")
    put("status_traceability", _rate(None if miss is None else ~miss))

    # ── همکاری ──
    if no_dev is not None:
        put("clean_handover_rate", _rate(no_dev))

    # ── بار و زمینه (امتیاز نمی‌گیرند) ──
    out["case_load"] = (float(len(g)), int(len(g)))
    pn = _txt(g, "part_no")
    if pn is not None:
        out["distinct_parts"] = (float(pn[pn.ne("")].nunique()), int(len(g)))
    tm = _txt(g, "transport")
    if tm is not None and tm.ne("").any():
        share = tm[tm.ne("")].value_counts(normalize=True)
        out["transport_mix_difficulty"] = (float(1 - (share ** 2).sum()),
                                           int(tm.ne("").sum()))
    put("value_at_risk", _num(g, "value"))
    if scope.owner:
        band = _txt(g, "criticality")
        if band is not None:
            put("part_criticality_mix",
                _rate(band.str.upper().isin(CRITICAL_BANDS)))
    return out


# ═══════════ تبدیل ═══════════
def _person_of(df: pd.DataFrame, scope: Scope) -> Optional[pd.DataFrame]:
    """کلید و نام هر ردیف برای این حوزه."""
    if scope.key not in df.columns:
        return None
    name = df[scope.key].fillna("").astype(str).str.strip()
    code = None
    if scope.owner:
        c = _col(df, "owner_code")
        if c:
            code = df[c].fillna("").astype(str).str.strip()
    raw = code if code is not None else pd.Series("", index=df.index)
    raw = raw.where(raw.ne(""), name)          # کد نبود؟ نام، کلید می‌شود
    out = pd.DataFrame({"raw": raw, "name": name})
    return out[out["raw"].ne("")]


def to_long(df: pd.DataFrame, source: str = "aibl") -> AiblExtract:
    """جدول پروندهٔ AIBL → جدول بلند سنجه‌های فردی، به تفکیک حوزه."""
    rows: List[Dict[str, object]] = []
    people: List[Dict[str, str]] = []
    by_scope: Dict[str, int] = {}
    seen_metrics: set = set()

    for scope in SCOPES:
        who = _person_of(df, scope)
        if who is None or who.empty:
            continue
        by_scope[scope.fa] = int(who["raw"].nunique())
        for raw_key, idx in who.groupby("raw").groups.items():
            g = df.loc[idx]
            key = keymod.clean_person_key(raw_key)
            if not key:
                continue
            code = keymod.display_code(who.loc[idx, "raw"])
            nm = who.loc[idx, "name"]
            nm = next((x for x in nm if str(x).strip()), code)
            people.append({"person_key": key, "person_code": code,
                           "full_name": str(nm), "scope": scope.key,
                           # نقش کاری در سطح **حوزه** اعلام می‌شود، نه یکی از
                           # زیرنقش‌ها: نامیدنِ هر کارشناس بازرگانی
                           # «کارشناس ثبت سفارش»، حدسی است که در گزارش
                           # به‌عنوان واقعیت خوانده می‌شود.
                           "job_family": scope.fa})
            for mk, (val, n) in _metrics_for(g, scope).items():
                seen_metrics.add(mk)
                rows.append({"person_key": key, "person_code": code,
                             "metric_key": mk, "value": val, "sample_n": n,
                             "source": source, "scope": scope.key})

    long = (pd.DataFrame(rows) if rows
            else pd.DataFrame(columns=LONG_COLUMNS))
    ppl = (pd.DataFrame(people).drop_duplicates("person_key")
           if people else pd.DataFrame(columns=["person_key", "person_code",
                                                "full_name", "scope",
                                                "job_family"]))
    return AiblExtract(long=long, people=ppl, missing=_missing(df, seen_metrics),
                       rows=int(len(df)), by_scope=by_scope)


#: سنجه → ستونی که بدون آن ساخته نمی‌شود (برای پیام «چرا نیامد»)
_NEEDS: Dict[str, str] = {
    "on_time_stage_rate": "overdue_days", "conformance_score": "conformance",
    "skipped_activity_rate": "skipped", "order_violation_rate": "violation",
    "ball_in_court_days": "waiting_scope", "own_leg_median_days": "status_age",
    "overdue_commitment_rate": "overdue_days", "customs_dwell_days": "dwell_days",
    "owner_field_completeness": "owner_gap", "status_traceability": "status_missing",
    "in_full_rate": "full_clear", "allocation_lag_days": "alloc_date",
    "part_criticality_mix": "criticality", "value_at_risk": "value",
}


def _missing(df: pd.DataFrame, built: set) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for metric, need in _NEEDS.items():
        if metric in built:
            continue
        if _col(df, need) is None:
            out[metric] = f"ستون «{COLS[need][0]}» نبود"
    return out


def read_cases(path: str | Path) -> pd.DataFrame:
    """یک فایل یا یک پوشه از فایل‌های پروندهٔ AIBL را می‌خواند."""
    p = Path(path)
    files: Sequence[Path]
    if p.is_dir():
        files = [f for f in sorted(p.iterdir())
                 if f.is_file() and not f.name.startswith("~$")
                 and f.suffix.lower() in (".xlsx", ".xlsm", ".csv")]
    elif p.is_file():
        files = [p]
    else:
        return pd.DataFrame()
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f) if f.suffix.lower() == ".csv"
                          else pd.read_excel(f, header=2))
        except Exception:
            continue
    return (pd.concat(frames, ignore_index=True).drop_duplicates()
            if frames else pd.DataFrame())
