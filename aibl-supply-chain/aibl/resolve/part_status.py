# -*- coding: utf-8 -*-
"""وضعیت قطعه: **کجا، توسط چه کسی، چه زمانی** — و معطل چه کسی.

## چرا این ماژول

نسخه ۲۶٫۹ نمای «متریال محور» را اضافه کرد که موقعیت را از ستون‌های موجودی
حدس می‌زد:

```python
if _num(g,"موجودی در گمرک") > 0: return "گمرک"
```

این حدس است، نه شاهد. موجودی گمرکِ مثبت می‌تواند باقی‌مانده یک محموله
قبلی باشد؛ و مهم‌تر اینکه **هیچ تاریخی همراهش نیست**. مدیر نمی‌تواند
بپرسد «از کِی؟» و همین سؤال، سؤالِ اصلی است.

## روش: آخرین رویداد مشاهده‌شده

خط لوله از قبل جدول فعالیت استاندارد (Celonis) دارد: ۱۳ فعالیت، هرکدام
با یک ستون تاریخ و یک مرحله چرخه عمر. وضعیت قطعه یعنی:

    کجا   = مرحلهٔ آخرین فعالیتی که **تاریخ ثبت‌شده** دارد
    چه زمانی = همان تاریخ، و «چند روز است در این وضعیت مانده»
    چه کسی  = حوزه‌ای که مالک آن مرحله است + نام کارشناس همان حوزه
    معطل کی = حوزه‌ای که مالک **اولین فعالیت بعدیِ انجام‌نشده** است

این همان الگویی است که برج کنترل‌های زنجیره تأمین (control tower) و
process mining به کار می‌برند: وضعیت از رویداد استخراج می‌شود نه از
اسنپ‌شات، چون رویداد تاریخ دارد و اسنپ‌شات ندارد.

## چرا این پاسخگویی را ممکن می‌کند

سه ستون ``STATUS_WHERE`` / ``STATUS_WHO`` / ``STATUS_WHEN`` کنار هم یک
جمله کامل می‌سازند و ``WAITING_ON_SCOPE`` می‌گوید **توپ در زمین کیست**.
اگر تاریخی ثبت نشده باشد، به‌جای حدس، ستون ``STATUS_BASIS`` می‌گوید
«شاهد تاریخ‌دار موجود نیست» و ``STATUS_MISSING`` می‌گوید کدام تاریخ کم
است — یعنی همان چیزی که باید از مالک خواست.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .. import health
from ..core.jalali import CalendarEngine
from .expert_scope import SCOPE_LABELS, STAGE_TO_SCOPE

#: (ستون تاریخ، نام فارسی فعالیت، ترتیب، مرحله چرخه عمر)
#: عمداً هم‌ترتیب با ``s80_eventlog.ACTIVITIES`` است؛ تست، یکسانی را
#: تضمین می‌کند تا این دو هرگز از هم جدا نیفتند.
TIMELINE: List[Tuple[str, str, int, str]] = [
    ("PO_SENT_DATE",       "ابلاغ سفارش به تأمین‌کننده",  30, "PO"),
    ("NTSW_COMMIT_DATE",   "ایجاد تعهد ارزی",             40, "ORDER_REG"),
    ("NTSW_ALLOC_DATE",    "تخصیص ارز",                   50, "ALLOCATION"),
    ("BUY_DATE",           "خرید ارز",                    60, "FX_SUPPLY"),
    ("BL_DATE",            "صدور بارنامه (حمل)",          70, "SHIPMENT"),
    ("ARRIVAL_DATE",       "ورود محموله",                 75, "SHIPMENT"),
    ("DISCHARGE_DATE",     "تخلیه محموله",                80, "CUSTOMS"),
    ("DOC_SUBMIT_DATE",    "ارائه اسناد به بانک",         85, "DOCS"),
    ("COT_DATE",           "ثبت کوتاژ گمرکی",             90, "CUSTOMS"),
    ("SATA_DATE",          "صدور کد ساتا",                95, "CUSTOMS"),
    ("PARTIAL_CLEAR_DATE", "ترخیص درصدی",                100, "CUSTOMS"),
    ("FULL_CLEAR_DATE",    "ترخیص کامل",                 105, "CUSTOMS"),
    ("FIN_RECEIPT_DATE",   "ثبت رسید مالی",              110, "RELEASE"),
]

STAGE_FA: Dict[str, str] = {
    "PR": "درخواست خرید", "PO": "سفارش خرید", "ORDER_REG": "ثبت سفارش",
    "ALLOCATION": "تخصیص ارز", "FX_SUPPLY": "تأمین ارز",
    "SETTLEMENT": "رفع تعهد ارزی", "SHIPMENT": "حمل",
    "CUSTOMS": "گمرک و ترخیص", "DOCS": "اسناد بانکی", "RELEASE": "تحویل و تصفیه",
}

WHERE, WHERE_CODE = "STATUS_WHERE", "STATUS_STAGE"
WHEN, AGE = "STATUS_WHEN", "STATUS_AGE_DAYS"
ACTIVITY = "STATUS_ACTIVITY"
WHO, WHO_SCOPE = "STATUS_WHO", "STATUS_WHO_SCOPE"
BASIS = "STATUS_BASIS"
ANOMALY = "STATUS_TIME_ANOMALY"
PLANNED = "STATUS_PLANNED_DATES"
NEXT_ACT, WAITING_SCOPE, WAITING_WHO = "NEXT_ACTIVITY", "WAITING_ON_SCOPE", "WAITING_ON_WHO"
MISSING = "STATUS_MISSING"

OUTPUT_COLUMNS = [WHERE, WHERE_CODE, ACTIVITY, WHEN, AGE, WHO, WHO_SCOPE,
                  BASIS, NEXT_ACT, WAITING_SCOPE, WAITING_WHO, MISSING,
                  ANOMALY, PLANNED]

_UNKNOWN = "نامشخص"
_NO_EVIDENCE = "هیچ فعالیت تاریخ‌داری برای این ردیف ثبت نشده است"


def _to_date(s: pd.Series) -> pd.Series:
    """رشته تاریخ → Timestamp، با **تشخیص تقویم**.

    این ستون‌ها شمسی‌اند («1405/01/29»). ``pd.to_datetime`` آن را سال ۱۴۰۵
    میلادی می‌خواند و «سن وضعیت» ۲۲۷٬۰۰۰ روز درمی‌آید — عددی که در گزارش
    مدیریتی هم بی‌معناست هم بی‌سروصدا غلط. موتور تقویم خود پکیج هر دو
    تقویم را تشخیص می‌دهد و همان مرجع واحد است.
    """
    uniq = s.dropna().astype(str).str.strip()
    uniq = pd.Index(uniq[uniq.ne("")].unique())
    lookup = {u: CalendarEngine.parse(u) for u in uniq}
    return pd.to_datetime(s.map(lambda v: lookup.get(str(v).strip())),
                          errors="coerce")


def _dates(df: pd.DataFrame, today: pd.Timestamp
           ) -> Tuple[pd.DataFrame, pd.DataFrame, List[Tuple[str, str, int, str]]]:
    """ماتریس تاریخ فعالیت‌های موجود — برداری، بدون حلقه روی ردیف.

    برمی‌گرداند: (ماتریس گذشته، ماتریس خام، فهرست فعالیت‌های موجود).
    ماتریس گذشته برای «وضعیت فعلی» است؛ خام برای تشخیص ناسازگاری.
    """
    present = [a for a in TIMELINE if a[0] in df.columns]
    if not present:
        return pd.DataFrame(index=df.index), pd.DataFrame(index=df.index), []
    raw = pd.DataFrame({a[0]: _to_date(df[a[0]]) for a in present}, index=df.index)
    # تاریخ آینده شاهد وضعیت فعلی نیست (تاریخ برنامه‌ای یا غلط تایپی) —
    # ولی از داده پاک نمی‌شود؛ جداگانه به‌عنوان «تاریخ برنامه‌ای» گزارش می‌شود.
    mat = raw.mask(raw > today + pd.Timedelta(days=1))
    return mat, raw, present


def _anomalies(raw: pd.DataFrame, present: List[Tuple[str, str, int, str]],
               today: pd.Timestamp) -> Tuple[pd.Series, pd.Series]:
    """دو ناسازگاری زمانی که در سکوت وضعیت را خراب می‌کنند.

    **۱) ترتیب معکوس.** کوتاژ ۰۱-۰۹ و ترخیص ۲۵-۰۸ یعنی ترخیص پیش از کوتاژ
    ثبت شده. چنین پرونده‌ای نه فقط وضعیتش مشکوک است، بلکه گراف فرآیند را
    هم آلوده می‌کند — و هیچ‌جا اعلام نمی‌شد.

    **۲) تاریخ آینده.** تاریخی که هنوز نرسیده احتمالاً برنامه‌ای است؛ نباید
    «وضعیت فعلی» را تعیین کند، ولی حذفش هم غلط است — داده برنامه‌ای است و
    باید دیده شود.
    """
    idx = raw.index
    if raw.empty or not present:
        return pd.Series("", index=idx, dtype=object), pd.Series("", index=idx, dtype=object)

    order = [a[2] for a in present]
    labels = [a[1] for a in present]
    seq = sorted(range(len(present)), key=lambda i: order[i])

    anomaly = pd.Series("", index=idx, dtype=object)
    prev_i: Optional[int] = None
    for i in seq:
        if prev_i is not None:
            a, b = raw.iloc[:, prev_i], raw.iloc[:, i]
            bad = a.notna() & b.notna() & (b < a)
            if bad.any():
                txt = f"«{labels[i]}» پیش از «{labels[prev_i]}» ثبت شده"
                anomaly = anomaly.mask(
                    bad, anomaly.where(anomaly.eq(""), anomaly + " ؛ ").fillna("") + txt)
        prev_i = i

    future = raw > today + pd.Timedelta(days=1)
    lbl = np.array(labels, dtype=object)
    planned = pd.Series(["، ".join(lbl[row]) for row in future.to_numpy()], index=idx)
    return anomaly, planned


def resolve(df: pd.DataFrame, today: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """ستون‌های «کجا / چه کسی / چه زمانی / معطل کی» را اضافه می‌کند."""
    out = df
    today = pd.Timestamp(today).normalize() if today is not None \
        else pd.Timestamp.today().normalize()
    mat, raw, present = _dates(out, today)
    n = len(out)

    if not present:
        for c in OUTPUT_COLUMNS:
            out[c] = "" if c != AGE else np.nan
        out[WHERE] = _UNKNOWN
        out[BASIS] = "هیچ ستون تاریخی در داده نیست"
        out[MISSING] = "، ".join(a[1] for a in TIMELINE)
        return out

    order = [a[2] for a in present]
    cols = [a[0] for a in present]
    has = mat.notna()

    # ── آخرین فعالیت انجام‌شده: بزرگ‌ترین «ترتیب» که تاریخ دارد ──
    rank = pd.DataFrame(np.where(has.to_numpy(), np.array(order), -1),
                        index=out.index, columns=cols)
    best = rank.to_numpy().argmax(axis=1)
    any_event = has.to_numpy().any(axis=1)

    pick = np.array(cols, dtype=object)[best]
    act_fa = np.array([a[1] for a in present], dtype=object)[best]
    stage = np.array([a[3] for a in present], dtype=object)[best]

    when = pd.Series(mat.to_numpy()[np.arange(n), best], index=out.index)
    when = pd.to_datetime(when, errors="coerce")

    out[WHERE_CODE] = pd.Series(np.where(any_event, stage, ""), index=out.index)
    out[WHERE] = out[WHERE_CODE].map(lambda s: STAGE_FA.get(s, s) if s else _UNKNOWN)
    out[ACTIVITY] = pd.Series(np.where(any_event, act_fa, ""), index=out.index)
    out[WHEN] = when.where(pd.Series(any_event, index=out.index))
    out[AGE] = (today - out[WHEN]).dt.days
    out[BASIS] = pd.Series(
        np.where(any_event,
                 pd.Series(pick, index=out.index).astype(str) + " (تاریخ ثبت‌شده در سورس)",
                 _NO_EVIDENCE),
        index=out.index)

    # ── مسئول وضعیت فعلی ──
    scope_now = out[WHERE_CODE].map(STAGE_TO_SCOPE).fillna("")
    out[WHO_SCOPE] = scope_now.map(lambda k: SCOPE_LABELS.get(k, "")).fillna("")
    out[WHO] = _pick_by_scope(out, scope_now)

    # ── اولین فعالیت بعدیِ انجام‌نشده = توپ در زمین کیست ──
    nxt_i = _next_missing(has.to_numpy(), np.array(order), best, any_event)
    valid = nxt_i >= 0
    nxt_fa = np.where(valid, np.array([a[1] for a in present], dtype=object)[nxt_i], "")
    nxt_stage = np.where(valid, np.array([a[3] for a in present], dtype=object)[nxt_i], "")
    out[NEXT_ACT] = pd.Series(np.where(valid, nxt_fa, "چرخه کامل است"), index=out.index)
    scope_next = pd.Series(nxt_stage, index=out.index).map(STAGE_TO_SCOPE).fillna("")
    out[WAITING_SCOPE] = scope_next.map(lambda k: SCOPE_LABELS.get(k, "")).fillna("")
    out[WAITING_WHO] = _pick_by_scope(out, scope_next)

    # ── چه تاریخی کم است تا وضعیت کامل معلوم شود ──
    lbl = np.array([a[1] for a in present], dtype=object)
    miss = has.to_numpy() == False  # noqa: E712 — ماتریس بولی، not روی numpy
    out[MISSING] = ["، ".join(lbl[row]) for row in miss]

    # ── ناسازگاری زمانی ──
    out[ANOMALY], out[PLANNED] = _anomalies(raw, present, today)
    n_bad = int(out[ANOMALY].ne("").sum())
    if n_bad:
        health.current().find(
            "زمان‌بندی", health.WARN,
            f"{n_bad} ردیف ترتیب زمانی معکوس دارد",
            "تاریخ یک فعالیت پیش از فعالیت قبلی‌اش ثبت شده؛ "
            "وضعیت و گراف فرآیند این ردیف‌ها قابل اتکا نیست.")
    n_plan = int(out[PLANNED].ne("").sum())
    if n_plan:
        health.current().find(
            "زمان‌بندی", health.INFO,
            f"{n_plan} ردیف تاریخ آینده (برنامه‌ای) دارد",
            "این تاریخ‌ها وضعیت فعلی را تعیین نکردند ولی در داده باقی‌اند.")
    return out


def _pick_by_scope(df: pd.DataFrame, scope_keys: pd.Series) -> pd.Series:
    """نام کارشناس همان حوزه‌ای که مسئول است — نه هر نامی که پیدا شود."""
    res = pd.Series("", index=df.index, dtype=object)
    for key in scope_keys.dropna().unique():
        if not key or key not in df.columns:
            continue
        sel = scope_keys.eq(key)
        res = res.mask(sel, df[key].fillna("").astype(str).str.strip())
    return res.replace({"nan": "", "None": ""})


def _next_missing(has: np.ndarray, order: np.ndarray, best: np.ndarray,
                  any_event: np.ndarray) -> np.ndarray:
    """اندیس اولین فعالیتِ بدون تاریخ که ترتیبش از آخرین رویداد بالاتر است.

    فقط فعالیت‌هایی در نظر گرفته می‌شوند که **ستون تاریخشان در داده هست**.
    درباره مرحله‌ای که اصلاً قابل مشاهده نیست ادعایی نمی‌کنیم — نه اینکه
    انجام شده و نه اینکه معطل مانده.
    """
    n, m = has.shape
    sort_idx = np.argsort(order, kind="stable")
    out = np.full(n, -1, dtype=int)
    cur_order = np.where(any_event, order[best], -1)
    for j in sort_idx:
        need = (out < 0) & (~has[:, j]) & (order[j] > cur_order)
        out[need] = j
    return out


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """جمع‌بندی «کجا / معطل چه حوزه‌ای / چند روز» برای گزارش مدیریتی."""
    if WHERE not in df.columns:
        return pd.DataFrame()
    g = df.groupby([WHERE, WAITING_SCOPE], dropna=False)
    out = g.agg(**{
        "تعداد ردیف": (WHERE, "size"),
        "میانگین سن وضعیت (روز)": (AGE, "mean"),
        "بیشترین سن وضعیت (روز)": (AGE, "max"),
    }).reset_index()
    out.columns = ["موقعیت فعلی", "معطل حوزه", "تعداد ردیف",
                   "میانگین سن وضعیت (روز)", "بیشترین سن وضعیت (روز)"]
    return out.sort_values("تعداد ردیف", ascending=False, ignore_index=True)
