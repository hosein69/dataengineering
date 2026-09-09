# -*- coding: utf-8 -*-
"""سه حوزه کارشناسی — و **مالک قطعه**.

## مسئله کسب‌وکار

نسخه ۲۶٫۶ هفت نقش تفکیک‌شده ساخت تا نام کارشناس ترخیص زیر عنوان کارشناس
خرید ننشیند. آن کار درست بود، ولی برای تصمیم‌گیری **زیادی ریز** است:
مدیر نمی‌پرسد «کارشناس کوتاژ کیست»، می‌پرسد **«این قطعه معطل کدام
حوزه است و مالکش کیست؟»**

سه حوزه واقعی مسئولیت در این زنجیره وجود دارد:

| حوزه | کارِ آن | مراحل چرخه عمر |
|---|---|---|
| **کارشناس خرید** ★ | چرخه خرید قطعه و تصفیه آن | PR ، PO ، RELEASE |
| **کارشناس بازرگانی** | تخصیص ارز، خرید ارز، رفع تعهد، اسناد بانکی | ORDER_REG ، ALLOCATION ، FX_SUPPLY ، SETTLEMENT ، DOCS |
| **کارشناس حمل و لجستیک** | حمل، گمرک و ترخیص | SHIPMENT ، CUSTOMS |

★ **مالک و مسئول قطعه**. قطعه از ابتدا تا انتهای فرآیند مال اوست، حتی
وقتی توپ در زمین حوزه دیگری است.

## چرا مالک از «Commercial Expert Data» می‌آید

این سورس را خودِ کارشناس خرید پر می‌کند: PR، PO، تأمین‌کننده، PI،
بارنامه و مقدار ترخیص‌شده — یعنی کل عمر قطعه در یک ردیف. ستون
``Employee Code`` همان کد پرسنلی اوست و از HR به نام تبدیل می‌شود.

**باگ نسخه‌های ۲۶٫۶ تا ۲۶٫۹:** ``expert_roles.py`` نقش «کارشناس بازرگانی»
را از ستونی به نام ``MOGH_EXPERT`` می‌خواند که **هیچ‌وقت ساخته نمی‌شود** —
آداپتور ستون ``MOGH_EMP_CODE`` / ``MOGH_KEY_EMP`` می‌سازد. نتیجه: ستون
مهم‌ترین کارشناس همیشه خالی بود و در لاگ هم «این نقش داده ندارد» چاپ
می‌شد. اینجا از کد پرسنلی به نام می‌رسیم و مسئله حل می‌شود.

## قاعده‌ای که شکسته نمی‌شود

داده ناقصِ مالک **حذف نمی‌شود**. اگر کارشناس خرید فیلدی را پر نکرده،
ردیف سر جایش می‌ماند و سیستم از داده حوزه‌های دیگر (تاریخ بارنامه،
کوتاژ، تخصیص ارز) می‌گوید قطعه واقعاً کجاست — و در ستون جداگانه‌ای ثبت
می‌کند که **چه چیزی از مالک کم است**. حذف داده ناقص یعنی پاک کردن صورت
مسئله؛ ما علت را برمی‌گردانیم به مالک.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .expert_roles import _clean


@dataclass(frozen=True)
class Scope:
    key: str                       # نام ستون خروجی
    fa: str                        # برچسب فارسی
    short: str                     # نام کوتاه برای نمودار و گروه‌بندی
    duties: Tuple[str, ...]        # کارهایی که این حوزه انجام می‌دهد
    stages: Tuple[str, ...]        # مراحل چرخه عمر (هم‌نام با s80_eventlog)
    roles: Tuple[str, ...]         # ستون‌های نقش ریز که به این حوزه می‌ریزند
    emp_code_col: str = ""         # کد پرسنلی، اگر نام مستقیم در سورس نباشد
    owner: bool = False            # مالک و مسئول قطعه


#: افزودن/جابه‌جایی مسئولیت = ویرایش همین جدول. هیچ فایل دیگری عوض نمی‌شود.
SCOPES: List[Scope] = [
    Scope("EXPERT_PURCHASING", "کارشناس خرید", "خرید",
          duties=("چرخه خرید قطعه", "تصفیه"),
          stages=("PR", "PO", "RELEASE"),
          roles=("EXPERT_BUYER",),
          emp_code_col="MOGH_KEY_EMP",
          owner=True),
    Scope("EXPERT_COMMERCIAL", "کارشناس بازرگانی", "بازرگانی",
          duties=("تخصیص ارز", "خرید ارز", "رفع تعهد ارزی", "اسناد بانکی"),
          stages=("ORDER_REG", "ALLOCATION", "FX_SUPPLY", "SETTLEMENT", "DOCS"),
          roles=("EXPERT_ORDER_REG", "EXPERT_CREDIT", "EXPERT_SETTLEMENT",
                 "EXPERT_DOC")),
    Scope("EXPERT_LOGISTICS", "کارشناس حمل و لجستیک", "حمل و لجستیک",
          duties=("حمل", "گمرک", "ترخیص"),
          stages=("SHIPMENT", "CUSTOMS"),
          roles=("EXPERT_CLEARANCE",)),
]

BY_KEY: Dict[str, Scope] = {s.key: s for s in SCOPES}
SCOPE_LABELS: Dict[str, str] = {s.key: s.fa for s in SCOPES}
OWNER_SCOPE: Scope = next(s for s in SCOPES if s.owner)

#: مرحله چرخه عمر → حوزه مسئول. مبنای پاسخ «معطل چه کسی است».
STAGE_TO_SCOPE: Dict[str, str] = {st: s.key for s in SCOPES for st in s.stages}

#: مراحلی که **هیچ رویداد تاریخ‌داری** در سورس‌ها ندارند.
#:
#: این‌ها حالت‌های غیرقابل‌رسیدن (unreachable) ماشین وضعیت‌اند: حوزه‌ای
#: مالکشان اعلام شده، ولی چون ستون تاریخی برایشان وجود ندارد، وضعیت هیچ
#: قطعه‌ای هرگز روی آن‌ها نمی‌ایستد و «معطل رفع تعهد ارزی» هرگز گزارش
#: نمی‌شود — در حالی که مدل ادعا می‌کند این مرحله را پوشش می‌دهد.
#:
#: صریح اعلامشان می‌کنیم تا ادعای پوشش با واقعیت بخواند، و تست معماری
#: هر مرحله بی‌رویدادِ *اعلام‌نشده* را قرمز می‌کند. رفع واقعی، افزودن
#: ستون تاریخ این دو مرحله به سورس است — که کار داده است، نه کد.
UNOBSERVABLE_STAGES: Dict[str, str] = {
    "PR": "سورس، تاریخ ثبت درخواست خرید را نمی‌دهد",
    "SETTLEMENT": "سورس، تاریخ رفع تعهد ارزی را به‌صورت رویداد نمی‌دهد",
}

#: نام ستون‌های خروجی
OWNER_NAME = "PART_OWNER"
OWNER_SOURCE = "PART_OWNER_SOURCE"
OWNER_GAP = "PART_OWNER_DATA_GAP"

#: فیلدهایی که پر کردنشان وظیفه مالک است. نبودشان دلیل حذف ردیف نیست —
#: دلیل ثبت «شکاف داده مالک» است.
OWNER_FIELDS: List[Tuple[str, str]] = [
    ("MOGH_KEY_PR", "شماره درخواست خرید"),
    ("MOGH_PO_SENT_DATE", "تاریخ ابلاغ سفارش"),
    ("MOGH_VENDOR_CODE", "کد تأمین‌کننده"),
    ("MOGH_PI_VALUE_SUM", "ارزش PI"),
    ("MOGH_BL_NO", "شماره بارنامه در سورس خرید"),
    ("MOGH_CLEARED_QTY_SUM", "مقدار ترخیص‌شده"),
]

#: ستونی که اصلاً در داده نیست، **شکاف ردیفی نیست** — شکاف سورس است.
#: نسخه اول همین ماژول ستون غایب را برای همه ردیف‌ها «کمبود» می‌شمرد و
#: نتیجه‌اش این بود که هر ردیف شکاف داشت، حتی وقتی مالک کارش را کامل کرده
#: بود. آن هشدارِ همیشه-روشن، هشدار نیست.
MISSING_SOURCE = "PART_OWNER_SOURCE_GAP"


def _name_from_code(codes: pd.Series, mapper) -> pd.Series:
    """کد پرسنلی → نام کامل، از HR. بدون mapper، رشته خالی."""
    if mapper is None:
        return pd.Series("", index=codes.index, dtype=object)
    cache: Dict[str, str] = {}

    def one(code: str) -> str:
        code = str(code or "").strip()
        if not code:
            return ""
        if code not in cache:
            person = mapper.map("", code)
            name = str(person.get("expert", "") or "").strip()
            # UNKNOWN از org_mapper یعنی «کد در HR نبود» — نام جعل نمی‌کنیم.
            cache[code] = "" if name in ("نامشخص", "") else name
        return cache[code]

    return codes.map(one)


def resolve_scopes(df: pd.DataFrame, mapper=None) -> pd.DataFrame:
    """سه ستون حوزه‌ای می‌سازد؛ هیچ حوزه‌ای با نام حوزه دیگر پر نمی‌شود."""
    out = df
    for scope in SCOPES:
        col = pd.Series("", index=out.index, dtype=object)
        for role_col in scope.roles:
            if role_col not in out.columns:
                continue
            cand = _clean(out[role_col])
            col = col.where(col.ne(""), cand)
        # کد پرسنلی فقط وقتی به کار می‌آید که نام مستقیمی نباشد
        if scope.emp_code_col and scope.emp_code_col in out.columns:
            byc = _name_from_code(out[scope.emp_code_col].fillna("").astype(str), mapper)
            col = col.where(col.ne(""), byc)
        out[scope.key] = col
    return out


def resolve_owner(df: pd.DataFrame, mapper=None) -> pd.DataFrame:
    """مالک قطعه و منبع شناسایی او، به‌علاوه شکاف داده‌ای که باید پر کند."""
    out = df
    name = _clean(out[OWNER_SCOPE.key]) if OWNER_SCOPE.key in out.columns \
        else pd.Series("", index=out.index, dtype=object)
    src = pd.Series("", index=out.index, dtype=object)

    code_col = OWNER_SCOPE.emp_code_col
    has_code = (out[code_col].fillna("").astype(str).str.strip().ne("")
                if code_col in out.columns
                else pd.Series(False, index=out.index))
    src = src.mask(name.ne("") & has_code, "Commercial Expert Data (کد پرسنلی)")
    src = src.mask(name.ne("") & ~has_code, "سورس خرید (نام مستقیم)")
    src = src.mask(name.eq(""), "شناسایی نشد")

    out[OWNER_NAME] = name
    out[OWNER_SOURCE] = src

    gaps: List[pd.Series] = []
    absent: List[str] = []
    for col, label in OWNER_FIELDS:
        if col not in out.columns:
            absent.append(label)
            continue
        empty = out[col].isna() | out[col].astype(str).str.strip().isin(
            ("", "nan", "None", "-", "—", "NaT", "0"))
        gaps.append(pd.Series(label, index=out.index).where(empty, ""))
    if gaps:
        joined = pd.concat(gaps, axis=1)
        out[OWNER_GAP] = joined.apply(
            lambda r: "، ".join([x for x in r if x]), axis=1)
    else:
        out[OWNER_GAP] = ""
    # شکاف سورس یک بار گزارش می‌شود، نه به پای تک‌تک ردیف‌ها
    out[MISSING_SOURCE] = "، ".join(absent)
    return out


def coverage(df: pd.DataFrame) -> pd.DataFrame:
    """پوشش هر حوزه — چند درصد ردیف‌ها نام دارند و چند نفر یکتا."""
    rows = []
    n = max(len(df), 1)
    for scope in SCOPES:
        s = _clean(df[scope.key]) if scope.key in df.columns \
            else pd.Series("", index=df.index, dtype=object)
        filled = s.ne("")
        rows.append({
            "حوزه": scope.fa,
            "مالک قطعه": "بله" if scope.owner else "خیر",
            "کار": "، ".join(scope.duties),
            "ردیف دارای نام": int(filled.sum()),
            "پوشش": round(float(filled.sum()) / n, 4),
            "نفرات یکتا": int(s[filled].nunique()),
        })
    return pd.DataFrame(rows)
