# -*- coding: utf-8 -*-
"""نسخه پکیج و قراردادهای بین‌ماژولی.

## چرا این فایل وجود دارد

خطای واقعی که در اجرا رخ داد:
    AttributeError: 'SourceSpec' object has no attribute 'frame_map'

علت: ``pipeline.py`` به‌روزرسانی شده بود ولی ``config/sources.py`` نسخه قدیمی
مانده بود. پایتون هیچ مکانیزمی برای تشخیص این «اختلاف نسخه فایل‌ها» ندارد و
خطا صد خط پایین‌تر و با پیام گمراه‌کننده ظاهر می‌شود.

## راه‌حل

هر ماژولی که رابط عمومی‌اش را در اختیار ماژول‌های دیگر می‌گذارد، یک عدد
``__contract__`` اعلام می‌کند. مصرف‌کننده حداقل نسخه لازم را در
``REQUIRED_CONTRACTS`` ثبت می‌کند. ``python -m aibl.doctor`` پیش از هر اجرا
این‌ها را می‌سنجد و دقیقاً می‌گوید **کدام یک فایل** باید به‌روز شود.

قاعده افزایش شماره قرارداد:
    +1  هرگاه متد/فیلد/کلیدی که ماژول دیگری به آن تکیه دارد اضافه یا عوض شود.
        افزودن قابلیت داخلی که کسی به آن وابسته نیست، شماره را عوض نمی‌کند.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from .factsheet import VERSION as PACKAGE_VERSION   # تنها منبع نسخه

#: حداقل نسخه قرارداد که هسته سیستم به آن نیاز دارد.
#: کلید = مسیر ماژول نسبت به aibl ، مقدار = حداقل __contract__
REQUIRED_CONTRACTS: Dict[str, int] = {
    "config.sources": 3,      # SourceSpec.frame_map()  ← علت خطای AttributeError
    "adapters.base": 3,       # KEY_MATERIAL و add_material_key()
    "core.text": 2,           # clean_order_ref() و order_ref_base()
    "core.jalali": 1,
    "dataio.merge": 1,
    "rulebook.loader": 1,
    "engines.criticality": 1,
    "stages.base": 1,
}

#: توضیح فارسی هر قرارداد، برای پیام خطای قابل فهم
CONTRACT_NOTES: Dict[str, str] = {
    "config.sources": "متد frame_map() روی SourceSpec — برای سورس‌های چندفریمی مثل Oracle",
    "adapters.base": "کلید KEY_MATERIAL و متد add_material_key() — برای اتصال موجودی",
    "core.text": "توابع clean_order_ref و order_ref_base — برای مرجع سفارش مقاومت",
    "core.jalali": "موتور تقویم (نام قبلی calendar.py بود)",
    "dataio.merge": "safe_merge با گارد انفجار سطر (نام پکیج قبلاً io بود)",
    "rulebook.loader": "بارگذار کتابخانه قوانین YAML",
    "engines.criticality": "موتور مقاومت قطعه",
    "stages.base": "قرارداد مرحله‌های خط لوله",
}


@dataclass
class ContractIssue:
    module: str
    found: Optional[int]
    required: int
    note: str

    @property
    def message(self) -> str:
        where = f"aibl/{self.module.replace('.', '/')}.py"
        if self.found is None:
            return (f"فایل «{where}» نسخه قدیمی است (قرارداد اعلام نشده). "
                    f"نسخه {self.required} لازم است — {self.note}")
        return (f"فایل «{where}» نسخه {self.found} است ولی نسخه {self.required} "
                f"لازم است — {self.note}")


def check_contracts() -> List[ContractIssue]:
    """فهرست فایل‌هایی که نسخه‌شان با بقیه پکیج نمی‌خواند."""
    issues: List[ContractIssue] = []
    for mod_path, required in REQUIRED_CONTRACTS.items():
        note = CONTRACT_NOTES.get(mod_path, "")
        try:
            mod = importlib.import_module(f"aibl.{mod_path}")
        except Exception as ex:
            issues.append(ContractIssue(mod_path, None, required,
                                        f"{note} (import ناموفق: {ex})"))
            continue
        found = getattr(mod, "__contract__", None)
        if found is None or int(found) < required:
            issues.append(ContractIssue(mod_path, found, required, note))
    return issues
