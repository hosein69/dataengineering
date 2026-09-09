# -*- coding: utf-8 -*-
"""حوزه مسئولیت — چه کسی برای چه چیزی پاسخگوست.

## چرا این ماژول، هستهٔ عدالت این پکیج است

یک پروندهٔ خرید خارجی از دست سه کارشناس رد می‌شود: خرید، بازرگانی، و حمل
و لجستیک. اگر محموله ۹۰ روز در گمرک بماند و ما این ۹۰ روز را به هر سه
نسبت دهیم، دو نفر بابت کاری که در اختیارشان نبوده جریمه شده‌اند.

پس قاعده این است: **هر کارشناس فقط روی مرحله‌هایی سنجیده می‌شود که در
حوزهٔ اوست.** این همان تفکیکی است که ``aibl/resolve/expert_scope.py``
روی پروندهٔ زنجیره تأمین انجام می‌دهد و اینجا عیناً بازتاب داده می‌شود تا
دو پکیج یک تعریف داشته باشند.

پژوهش‌های ۲۰۲۵ روی ادراک انصاف از ارزیابی الگوریتمی همین را تأیید
می‌کند: کارکنان ویژگی‌هایی را منصفانه می‌دانند که **در حیطهٔ اختیار
خودشان** و مرتبط با تخصصشان باشد، و آنچه بیرون از کنترلشان است را
ناعادلانه می‌بینند.

## مالکیت قطعه

کارشناس خرید علاوه بر مرحله‌های خودش، **مالک قطعه** است: کل چرخه را باید
پیگیری کند. پس یک دسته سنجه (پیامد عملیاتی قطعه) فقط به او نسبت داده
می‌شود — ولی با کنترل سختیِ ذاتی قطعه، وگرنه کسی که قطعات سخت گرفته
جریمه می‌شود.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Scope:
    """یک حوزه مسئولیت، آینهٔ ``aibl.resolve.expert_scope.Scope``."""
    key: str                       # کلید انگلیسی، همان کلید ستون در AIBL
    fa: str                        # عنوان فارسی
    short: str                     # نام کوتاه برای نمودار
    duties: Tuple[str, ...]        # کارهایی که در این حوزه است
    stages: Tuple[str, ...]        # مرحله‌های چرخه که این حوزه پاسخگوی آن است
    families: Tuple[str, ...] = () # نقش‌های کاری HR که در این حوزه می‌افتند
    owner: bool = False            # مالک قطعه؟


#: سه حوزه — عیناً مطابق پکیج زنجیره تأمین.
SCOPES: List[Scope] = [
    Scope("EXPERT_PURCHASING", "کارشناس خرید", "خرید",
          duties=("چرخه خرید قطعه", "تصفیه"),
          stages=("PR", "PO", "RELEASE"),
          families=("buyer",),
          owner=True),
    Scope("EXPERT_COMMERCIAL", "کارشناس بازرگانی", "بازرگانی",
          duties=("تخصیص ارز", "خرید ارز", "رفع تعهد ارزی", "اسناد بانکی"),
          stages=("ORDER_REG", "ALLOCATION", "FX_SUPPLY", "SETTLEMENT", "DOCS"),
          families=("order_reg", "credit", "settlement", "doc_control",
                    "commercial")),
    Scope("EXPERT_LOGISTICS", "کارشناس حمل و لجستیک", "حمل و لجستیک",
          duties=("حمل", "گمرک", "ترخیص"),
          stages=("SHIPMENT", "CUSTOMS"),
          families=("clearance",)),
]

#: حوزه‌ای که مالک قطعه است.
OWNER_SCOPE: Scope = next(s for s in SCOPES if s.owner)

#: کلید حوزه‌ای که به همه تعلق دارد (سنجه‌های مشترک مثل کیفیت داده).
ANY = "ANY"

BY_KEY: Dict[str, Scope] = {s.key: s for s in SCOPES}
BY_FAMILY: Dict[str, Scope] = {f: s for s in SCOPES for f in s.families}

#: مرحله‌ها → حوزه‌ای که پاسخگوی آن است (وارونهٔ ``Scope.stages``).
STAGE_OWNER: Dict[str, str] = {st: s.key for s in SCOPES for st in s.stages}


def of_family(job_family: str) -> Optional[Scope]:
    """نقش کاری HR → حوزه مسئولیت. ناشناخته یعنی None، نه حدس."""
    return BY_FAMILY.get(str(job_family or "").strip())


def owns_stage(scope_key: str, stage: str) -> bool:
    return STAGE_OWNER.get(str(stage or "").strip()) == scope_key


def applies(metric_scope: str, person_scope: Optional[str]) -> bool:
    """آیا این سنجه برای این فرد معنا دارد؟

    ``ANY`` برای همه؛ حوزهٔ ناشناختهٔ فرد یعنی فقط سنجه‌های مشترک، چون
    نسبت دادن سنجهٔ تخصصی به کسی که حوزه‌اش معلوم نیست، حدس است.
    """
    ms = str(metric_scope or ANY).strip() or ANY
    if ms == ANY:
        return True
    return person_scope is not None and ms == person_scope


def labels() -> Dict[str, str]:
    out = {ANY: "مشترک (همه حوزه‌ها)"}
    out.update({s.key: s.fa for s in SCOPES})
    return out
