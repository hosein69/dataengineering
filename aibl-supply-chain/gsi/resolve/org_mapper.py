# -*- coding: utf-8 -*-
"""تطبیق سازمانی HR.

اصلاحات:
  B2/FIX-10  کلید ``expert`` در ساختار person_data اضافه شد. نبودش در نسخه
             ۲۰.۱ باعث ``KeyError`` می‌شد هر بار که تطبیق HR *موفق* بود.
  FIX-11/12  کارشناس از طریق Employee Code (۸ رقمی zero-pad) بازیابی می‌شود،
             چون سورس مقاومت دیگر نام کارشناس ندارد.
  زنجیره سقوط: مدیر → رئیس → مسئول → «نامشخص».
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict, Optional

import pandas as pd

from ..config.settings import SETTINGS
from ..core.text import clean_employee_code, is_empty_val, normalize_persian_text
from ..dataio.logging_setup import log

UNKNOWN = "نامشخص"
DEFAULT_DEPT = "مدیریت خرید خارجی"
DEFAULT_VICE = "معاونت خرید"

PersonData = Dict[str, str]


def _blank_person(expert_name: str = "", emp_code: str = "") -> PersonData:
    return {
        "id": emp_code,
        "name": normalize_persian_text(expert_name) or UNKNOWN,
        "expert": normalize_persian_text(expert_name) or UNKNOWN,  # FIX-10
        "supervisor": UNKNOWN,
        "head": UNKNOWN,
        "manager": UNKNOWN,
        "dept": DEFAULT_DEPT,
        "vice": DEFAULT_VICE,
        "match_type": "پیش‌فرض",
    }


class DynamicOrgMapper:
    """پایگاه پرسنلی + تطبیق دقیق/فازی."""

    def __init__(self, df_hr: Optional[pd.DataFrame]) -> None:
        self.by_id: Dict[str, PersonData] = {}
        self.by_name: Dict[str, PersonData] = {}
        if df_hr is not None and not df_hr.empty:
            self._build(df_hr)
        log.info(f"👥 پایگاه HR ساخته شد: {len(self.by_id)} کد پرسنلی، {len(self.by_name)} نام.")

    def _build(self, df: pd.DataFrame) -> None:
        def g(row, col, default=""):
            v = row.get(col, default)
            return "" if is_empty_val(v) else str(v).strip()

        for _, row in df.iterrows():
            emp = clean_employee_code(row.get("KEY_EMP", ""))
            full = normalize_persian_text(g(row, "HR_FULL_NAME"))
            if not full:
                fn, ln = g(row, "HR_FIRST_NAME"), g(row, "HR_LAST_NAME")
                full = normalize_persian_text(f"{fn} {ln}").strip()
            if not emp and not full:
                continue

            sup, head, mgr = g(row, "HR_SUPERVISOR"), g(row, "HR_HEAD"), g(row, "HR_MANAGER")
            manager = mgr or head or sup or UNKNOWN   # زنجیره سقوط

            person: PersonData = {
                "id": emp,
                "name": full or UNKNOWN,
                "expert": full or UNKNOWN,             # FIX-10
                "supervisor": sup or UNKNOWN,
                "head": head or UNKNOWN,
                "manager": manager,
                "dept": g(row, "HR_DEPT") or DEFAULT_DEPT,
                "vice": g(row, "HR_VICE") or DEFAULT_VICE,
                "match_type": "دقیق",
            }
            if emp:
                self.by_id[emp] = person
            if full:
                self.by_name[full] = person

    def map(self, expert_name: str = "", employee_code: str = "") -> PersonData:
        emp = clean_employee_code(employee_code)
        if emp and emp in self.by_id:
            return {**self.by_id[emp], "match_type": "کد پرسنلی"}

        name = normalize_persian_text(expert_name)
        if name and name in self.by_name:
            return {**self.by_name[name], "match_type": "نام کامل"}

        if name and name != UNKNOWN and self.by_name:
            best_name, best_score = "", 0.0
            for cand in self.by_name:
                sc = SequenceMatcher(None, name, cand).ratio()
                if sc > best_score:
                    best_score, best_name = sc, cand
            if best_score >= SETTINGS.FUZZY_THRESHOLD:
                return {**self.by_name[best_name],
                        "match_type": f"فازی ({best_score:.2f})"}

        return _blank_person(expert_name, emp)

    @staticmethod
    def format_chain(p: PersonData) -> str:
        return (f"معاونت: {p['vice']} | مدیریت: {p['dept']} | مدیر: {p['manager']} | "
                f"رئیس: {p['head']} | کارشناس: {p['expert']}")
