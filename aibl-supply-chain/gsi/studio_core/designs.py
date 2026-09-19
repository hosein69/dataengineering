# -*- coding: utf-8 -*-
"""ذخیره و بازیابی «طرح گزارش» برای GSI Studio.

طرح فقط تنظیمات گزارش است، نه داده حساس. به‌صورت JSON ذخیره می‌شود:
قالب، فیلدها، تب‌های HTML/Excel و نمودارهای ایمیل.
"""
from __future__ import annotations
__contract__ = 1

import json, os, re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DESIGNS_DIR = Path(
    os.environ.get("GSI_DESIGNS", str(Path.home() / ".gsi" / "designs"))
)

@dataclass
class ReportDesign:
    name: str
    template: str = "executive"
    fields: List[str] = field(default_factory=list)
    tabs: List[Dict[str, Any]] = field(default_factory=list)
    formats: List[str] = field(default_factory=lambda: ["excel", "html", "pdf"])
    visuals: bool = True
    tables: bool = True
    max_rows: int = 5000
    file_stem: str = "GSI Report"
    email_charts: List[str] = field(default_factory=list)
    title: str = "GSI"

def designs_dir() -> Path:
    p = Path(os.environ.get("GSI_DESIGNS", str(DEFAULT_DESIGNS_DIR))).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", str(name).strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:120] or "گزارش"

def path_for(name: str) -> Path:
    return designs_dir() / f"{_safe_name(name)}.json"

def save_design(design: ReportDesign | Dict[str, Any]) -> Path:
    if isinstance(design, dict):
        design = ReportDesign(**design)
    p = path_for(design.name)
    payload = asdict(design)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

def load_design(name: str) -> ReportDesign:
    p = path_for(name)
    data = json.loads(p.read_text(encoding="utf-8"))
    return ReportDesign(**data)

def list_designs() -> List[str]:
    return sorted(p.stem for p in designs_dir().glob("*.json"))

def delete_design(name: str) -> bool:
    p = path_for(name)
    if not p.exists():
        return False
    p.unlink()
    return True


# کلیدها با نمودارهای شیت Charts در گزارش رسمی هم‌ترازند.
#: عنوان فارسی هر نمودار. هر کلیدی که رندر می‌شود باید اینجا عنوان داشته
#: باشد؛ وگرنه کاربر «sediment_vs_resistance» را به‌عنوان تیتر می‌بیند.
EMAIL_CHARTS = {
    "criticality": "وضعیت بحرانی متریال — توزیع",
    "low_resistance": "۱۰ متریال کم‌مقاومت",
    "stock_vs_total": "مقاومت انبار و کل",
    "commitment": "مانده تعهد ارزی",
    "bottlenecks": "گلوگاه فرآیند",
    "risk_mix": "ترکیب سبد ریسک",
    "org_workload": "بار کاری سازمانی",
    "expert_workload": "بار کاری کارشناسان",
    "transport_mix": "ترکیب شیوه حمل",
    "stage_distribution": "توزیع مرحله فعلی پرونده‌ها",
    "top_orders": "سفارش‌های دارای بیشترین اقلام",
    "top_bl": "بارنامه‌های دارای بیشترین اقلام",
    "supplier_mix": "تمرکز تأمین‌کنندگان",
    "sediment_vs_resistance": "مقاومت در برابر روزهای رسوب",
    "delay_vs_commitment": "مانده تعهد در برابر روزهای تأخیر",
    "pareto_delay": "تمرکز تأخیر — قاعده ۸۰/۲۰",
    "overdue_bucket": "توزیع پرونده‌ها بر حسب روزهای تأخیر",
}

#: سؤال تصمیم‌سازی که هر نمودار به آن جواب می‌دهد. زیر عنوان نمایش داده
#: می‌شود: نموداری که نمی‌شود گفت به چه سؤالی جواب می‌دهد، جای آن در گزارش نیست.
CHART_QUESTIONS = {
    "criticality": "چند قطعه در آستانه توقف خط است؟",
    "low_resistance": "کدام قطعات باید امروز پیگیری شوند؟",
    "stock_vs_total": "چه میزان از پوشش به کالای در راه/گمرک وابسته است؟",
    "commitment": "چه مبلغی در معرض جریمه/تأخیر است؟",
    "bottlenecks": "کدام گذار بیشترین انتظار را دارد؟",
    "risk_mix": "ترکیب ریسک پرونده‌ها چگونه است؟",
    "org_workload": "پرونده‌ها روی کدام واحدها متمرکز شده‌اند؟",
    "expert_workload": "بار عملیاتی روی کدام کارشناسان است؟",
    "transport_mix": "سبد حمل چگونه توزیع شده است؟",
    "stage_distribution": "پرونده‌ها اکنون در کدام مرحله متوقف‌اند؟",
    "top_orders": "تمرکز عملیات روی کدام سفارش‌هاست؟",
    "top_bl": "کدام بارنامه‌ها بیشترین درگیری عملیاتی دارند؟",
    "supplier_mix": "ریسک تمرکز تأمین روی کدام Vendor است؟",
    "sediment_vs_resistance": "کدام قطعه هم رسوب بالا و هم مقاومت پایین دارد؟",
    "delay_vs_commitment": "جریمه کجا انباشته می‌شود: پرونده بزرگ یا کهنه؟",
    "pareto_delay": "چند درصد از کل تأخیر روی چند پرونده متمرکز است؟",
    "overdue_bucket": "انباشت تأخیر در چه بازه‌ای است؟",
}
