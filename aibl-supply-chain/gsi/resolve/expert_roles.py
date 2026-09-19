# -*- coding: utf-8 -*-
"""نقش‌های کارشناسی — هر مرحله مالک خودش را دارد.

## چرا این ماژول ساخته شد

تا نسخه ۲۶٫۵ یک ستون واحد به نام ``CANONICAL_EXPERT`` وجود داشت که با
«اولین مقدار غیرتهی» از پنج سورس پر می‌شد:

```python
"CANONICAL_EXPERT": [ORC_BUYER, CL_EXPERT, SATA_CREDIT_EXPERT,
                     CRD_EXPERT, DOC_EXPERT]
```

و چون ``ORC_BUYER`` (کارشناس خرید خارجی) طبق HEADERS_MAP فقط **۱۷٫۳٪**
پر است، برای بیشترِ ردیف‌ها به کاندید بعدی می‌افتاد و **نام کارشناس
ترخیص زیر عنوان «نام کارشناس» می‌نشست**. یعنی عملکرد ترخیص به پای خرید
نوشته می‌شد و برعکس — بینش تولیدشده از پایه غلط بود.

## قاعده جدید

هر نقش ستون مستقل خودش را دارد و **هرگز با نقش دیگر پر نمی‌شود**:

| ستون | نقش | سورس |
|---|---|---|
| ``EXPERT_BUYER``      | کارشناس خرید خارجی | oracle، credit |
| ``EXPERT_CLEARANCE``  | کارشناس ترخیص | clearance |
| ``EXPERT_CREDIT``     | کارشناس اعتبارات | sata، credit |
| ``EXPERT_ORDER_REG``  | کارشناس ثبت سفارش | ilappend، sata |
| ``EXPERT_SETTLEMENT`` | کارشناس رفع تعهد ارزی | ntsw، fx_transaction |
| ``EXPERT_DOC``        | کارشناس کنترل اسناد | doccheck |
| ``EXPERT_COMMERCIAL`` | کارشناس بازرگانی | moghavemat |

``CANONICAL_EXPERT`` حذف نشده — ولی دیگر یک ادغام خاموش نیست: مالکِ
**مرحله فعلی پرونده** است و ستون ``EXPERT_ROLE`` می‌گوید آن نام متعلق به
کدام نقش است، پس هیچ‌وقت معلوم نیست‌نبودن رخ نمی‌دهد.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class ExpertRole:
    key: str            # نام ستون خروجی
    fa: str             # برچسب فارسی نقش
    short: str          # نام کوتاه برای گروه‌بندی
    sources: List[Tuple[str, str]]   # (ستون، سورس) به ترتیب اولویت
    stage: str = ""     # مرحله‌ای از چرخه که این نقش مالکش است


#: تعریف نقش‌ها. افزودن نقش جدید = یک ورودی اینجا، بدون تغییر موتور.
ROLES: List[ExpertRole] = [
    ExpertRole("EXPERT_BUYER", "کارشناس خرید خارجی", "خرید",
               [("ORC_BUYER", "oracle"), ("CRD_BUYER", "credit")], "PO"),
    ExpertRole("EXPERT_ORDER_REG", "کارشناس ثبت سفارش", "ثبت سفارش",
               [("IL_EXPERT", "ilappend"), ("SATA_REG_EXPERT", "sata")], "ORDER_REG"),
    ExpertRole("EXPERT_CREDIT", "کارشناس اعتبارات", "اعتبارات",
               [("SATA_CREDIT_EXPERT", "sata"), ("CRD_EXPERT", "credit")], "LC"),
    ExpertRole("EXPERT_SETTLEMENT", "کارشناس رفع تعهد ارزی", "رفع تعهد",
               [("NTSW_EXPERT", "ntsw"), ("FX_EXPERT", "fx_transaction")], "SETTLEMENT"),
    ExpertRole("EXPERT_CLEARANCE", "کارشناس ترخیص", "ترخیص",
               [("CL_EXPERT", "clearance"), ("COT_EXPERT", "cotage")], "CUSTOMS"),
    ExpertRole("EXPERT_DOC", "کارشناس کنترل اسناد", "کنترل اسناد",
               [("DOC_EXPERT", "doccheck")], "DOCS"),
    ExpertRole("EXPERT_COMMERCIAL", "کارشناس بازرگانی", "بازرگانی",
               [("MOGH_EXPERT", "moghavemat")], "PR"),
]

BY_KEY: Dict[str, ExpertRole] = {r.key: r for r in ROLES}
ROLE_LABELS: Dict[str, str] = {r.key: r.fa for r in ROLES}
ROLE_SHORT: Dict[str, str] = {r.key: r.short for r in ROLES}

#: ترتیب مالکیت مرحله — برای تعیین «مالک فعلی پرونده»
#: هرچه پرونده جلوتر رفته باشد، مالک فعلی جلوتر است.
STAGE_ORDER: List[str] = ["EXPERT_COMMERCIAL", "EXPERT_BUYER", "EXPERT_ORDER_REG",
                          "EXPERT_CREDIT", "EXPERT_SETTLEMENT", "EXPERT_CLEARANCE",
                          "EXPERT_DOC"]


def _clean(s: pd.Series) -> pd.Series:
    out = s.fillna("").astype(str).str.strip()
    # نام‌های ترکیبی مثل «خسروی/مظاهری» دست‌نخورده می‌مانند؛ تفکیکشان
    # تصمیم سازمانی است نه فنی، و اینجا حدس زده نمی‌شود.
    return out.replace({"nan": "", "None": "", "-": "", "—": ""})


def resolve_roles(df: pd.DataFrame) -> pd.DataFrame:
    """برای هر نقش، ستون مستقل می‌سازد. هیچ نقشی با نقش دیگر پر نمی‌شود."""
    out = df
    for role in ROLES:
        col = pd.Series("", index=out.index, dtype=object)
        for src_col, _source in role.sources:
            if src_col not in out.columns:
                continue
            cand = _clean(out[src_col])
            col = col.where(col.astype(str).str.strip() != "", cand)
        out[role.key] = col
    return out


def current_owner(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """(نام مالک فعلی، نقش مالک فعلی).

    مالک فعلی = آخرین نقشی در ترتیب مرحله که برای آن ردیف نام دارد.
    برخلاف نسخه قبل، نقش هم برگردانده می‌شود تا هرگز معلوم نباشد که این
    نام متعلق به کیست.
    """
    name = pd.Series("", index=df.index, dtype=object)
    role = pd.Series("", index=df.index, dtype=object)
    for key in STAGE_ORDER:
        if key not in df.columns:
            continue
        cand = _clean(df[key])
        has = cand.str.strip() != ""
        name = name.mask(has, cand)
        role = role.mask(has, BY_KEY[key].fa if key in BY_KEY else key)
    return name, role


def coverage(df: pd.DataFrame) -> pd.DataFrame:
    """درصد پرشدگی هر نقش — برای اینکه معلوم باشد کدام نقش داده ندارد."""
    n = max(len(df), 1)
    rows = []
    for r in ROLES:
        if r.key not in df.columns:
            rows.append({"نقش": r.fa, "ستون": r.key, "پرشدگی (٪)": 0.0,
                         "افراد یکتا": 0, "سورس": "، ".join(s for _c, s in r.sources)})
            continue
        s = _clean(df[r.key])
        filled = int((s.str.strip() != "").sum())
        rows.append({
            "نقش": r.fa, "ستون": r.key,
            "پرشدگی (٪)": round(100 * filled / n, 1),
            "افراد یکتا": int(s[s.str.strip() != ""].nunique()),
            "سورس": "، ".join(s2 for _c, s2 in r.sources),
        })
    return pd.DataFrame(rows)
