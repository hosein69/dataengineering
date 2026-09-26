# -*- coding: utf-8 -*-
"""The GSI field rules and decision contracts, in one editable place.

Adding a decision to the trust layer is meant to be a data change, not a code
change: append a :class:`DecisionContract` here and the grade, the blocking
fields, the owner worklist and the trend all follow automatically.

Every column named below exists in the published mart. A contract that names a
column the mart does not have is not an error — the field is simply reported as
absent, which is itself the honest answer and shows up as a gap rather than
crashing the run.
"""
from __future__ import annotations

__contract__ = 1

from typing import Dict, Tuple

from .fitness import ADDITIVE, DISTRIBUTIONAL, DecisionContract
from .profiling import CrossSourceRule, CURRENCY, DATE, KEY, NUMBER, TEXT, FieldRule

# ── entity types ────────────────────────────────────────────────────────────
REG = "REG"            # کد ثبت سفارش — the financial/commitment case
MATERIAL = "MATERIAL"  # کد متریال — the part
BL = "BL"              # بارنامه — the shipment

KEY_COLUMN: Dict[str, str] = {
    REG: "CANONICAL_REG",
    MATERIAL: "KEY_MATERIAL",
    BL: "CANONICAL_BL",
}

ENTITY_FA: Dict[str, str] = {
    REG: "ثبت سفارش",
    MATERIAL: "متریال",
    BL: "بارنامه",
}

# ── field rules per entity ──────────────────────────────────────────────────
# ``check_conflict`` is set only where two sources genuinely describe the same
# fact; a field that legitimately varies across a case's rows must not be
# flagged as contradictory.
REG_RULES: Tuple[FieldRule, ...] = (
    FieldRule("CANONICAL_REG", KEY, "کد ثبت سفارش",
              owner_column="EXPERT_ORDER_REG", owner_role_fa="کارشناس ثبت سفارش"),
    FieldRule("مانده تعهد", NUMBER, "مانده تعهد ارزی", check_conflict=True,
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    FieldRule("FX_NTSW_CURRENCY", CURRENCY, "ارز تعهد", check_conflict=True,
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    FieldRule("مهلت قانونی رفع تعهد", DATE, "مهلت رفع تعهد",
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    FieldRule("NTSW_RELEASE_STATUS", TEXT, "وضعیت رفع تعهد",
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    FieldRule("جریمه برآوردی", NUMBER, "جریمه برآوردی", required=False,
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    FieldRule("FX_NTSW_INITIAL", NUMBER, "تعهد اولیه", required=False,
              owner_column="EXPERT_SETTLEMENT", owner_role_fa="کارشناس رفع تعهد ارزی"),
    # مبنای سررسید برات (تصمیم مالک، ۱۴۰۵/۰۷/۰۴). امروز هیچ فایلی این ستون را
    # ندارد، پس `FIELD_NEVER_POPULATED` می‌گیردش و به‌صورت «قرارداد سورس»
    # گزارش می‌شود — نه به‌صورت کار کارشناس. تا وقتی سازمان شروع به ثبتش
    # نکند، سررسید برات و جریمه تأخیر نامعلوم می‌مانند.
    FieldRule("INVOICE_DATE", DATE, "تاریخ فاکتور تجاری",
              owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
    FieldRule("INVOICE_VALUE", NUMBER, "ارزش فاکتور", required=False,
              owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
)

MATERIAL_RULES: Tuple[FieldRule, ...] = (
    FieldRule("KEY_MATERIAL", KEY, "کد متریال",
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
    # Inventory and daily need come from the Commercial Expert Data workbook,
    # so the commercial expert — not the buyer — is the one who can fill them.
    FieldRule("نیاز روزانه", NUMBER, "نیاز روزانه",
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
    FieldRule("موجودی ایران خودرو", NUMBER, "موجودی ایران‌خودرو",
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
    FieldRule("موجودی ساپکو", NUMBER, "موجودی ساپکو",
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
    FieldRule("موجودی نزد سازنده", NUMBER, "موجودی نزد سازنده", required=False,
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
    FieldRule("مقاومت (روز)", NUMBER, "مقاومت قطعی (روز)", required=False,
              owner_column="EXPERT_COMMERCIAL", owner_role_fa="کارشناس بازرگانی"),
)

BL_RULES: Tuple[FieldRule, ...] = (
    FieldRule("CANONICAL_BL", KEY, "شماره بارنامه",
              owner_column="EXPERT_LOGISTICS", owner_role_fa="کارشناس لجستیک"),
    # عمداً BL_DATE نیست. تاریخ *صدور* بارنامه هیچ سورسی ندارد، پس ارجاعش به
    # کارشناس یعنی فرستادن او دنبال سلولی که وجود ندارد. آن یک تصمیمِ مالک
    # کسب‌وکار است و از مسیر `derive_coverage.declared_unmeasured` گزارش
    # می‌شود، نه از فهرست کار کارشناس. اینجا شاهدی سنجیده می‌شود که واقعاً
    # در سورس هست و واقعاً قابل تکمیل است.
    FieldRule("SHIPPED_EVIDENCE_DATE", DATE, "شاهد حرکت محموله",
              owner_column="EXPERT_LOGISTICS", owner_role_fa="کارشناس لجستیک"),
    FieldRule("ARRIVAL_DATE", DATE, "تاریخ ورود", required=False,
              owner_column="EXPERT_LOGISTICS", owner_role_fa="کارشناس لجستیک"),
    FieldRule("COTAGE_NO", TEXT, "شماره کوتاژ", required=False,
              owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
    FieldRule("FULL_CLEAR_DATE", DATE, "تاریخ ترخیص کامل", required=False,
              owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
)

#: یک واقعیت که چند سورس ادعایش را دارند. ادغام، یکی را با ترتیب authority
#: انتخاب می‌کند و بقیه را بی‌صدا دور می‌ریزد — برای شناسه درست، برای مبلغ نه.
#: مالک کسب‌وکار (۱۴۰۵/۰۷/۰۴) تعیین کرد که فاکتور تجاری مبنای تعهد است، پس
#: سازگاری همین عدد بین سورس‌ها باید پیش از هر تصمیمی سنجیده شود.
CROSS_SOURCE: Dict[str, Tuple[CrossSourceRule, ...]] = {
    REG: (
        CrossSourceRule(
            column="INVOICE_VALUE",
            sources=("CL_INVOICE_VALUE", "SATA_INVOICE_VALUE", "COT_INVOICE_VALUE"),
            title_fa="ارزش فاکتور",
            owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
        CrossSourceRule(
            column="CURRENCY",
            sources=("CL_CURRENCY", "SATA_CURRENCY", "NTSW_CURRENCY", "FX_CURRENCY"),
            title_fa="ارز فاکتور", kind=CURRENCY,
            owner_column="EXPERT_CLEARANCE", owner_role_fa="کارشناس ترخیص"),
    ),
}

RULES: Dict[str, Tuple[FieldRule, ...]] = {
    REG: REG_RULES,
    MATERIAL: MATERIAL_RULES,
    BL: BL_RULES,
}

# ── decision contracts ──────────────────────────────────────────────────────
CONTRACTS: Tuple[DecisionContract, ...] = (
    DecisionContract(
        id="FX_COMMITMENT_TOTAL",
        title_fa="جمع مانده تعهد ارزی",
        question_fa="در این لحظه چقدر تعهد ارزی باز داریم؟",
        entity_type=REG,
        required=("CANONICAL_REG", "مانده تعهد", "FX_NTSW_CURRENCY"),
        aggregation=ADDITIVE,
        amount_field="مانده تعهد",
        currency_field="FX_NTSW_CURRENCY",
        note_fa="جمع مبلغ است: یک پرونده نامعلوم، کل عدد را غلط می‌کند. "
                "بخش معلوم و تعداد نامعلوم جدا گزارش می‌شوند.",
    ),
    DecisionContract(
        id="FX_DEADLINE_RISK",
        title_fa="ریسک مهلت رفع تعهد",
        question_fa="کدام پرونده‌ها از مهلت قانونی عقب‌اند یا نزدیک مهلت‌اند؟",
        entity_type=REG,
        required=("CANONICAL_REG", "مهلت قانونی رفع تعهد", "مانده تعهد"),
        aggregation=DISTRIBUTIONAL,
        amount_field="مانده تعهد",
        currency_field="FX_NTSW_CURRENCY",
        decision_floor=95.0,
        directional_floor=70.0,
        note_fa="رتبه‌بندی ریسک با پوشش ۹۵٪ هم قابل اتکاست؛ ولی رقم جریمه رسمی نیست.",
    ),
    DecisionContract(
        id="PENALTY_EXPOSURE",
        title_fa="برآورد جریمه تأخیر",
        question_fa="اگر امروز تسویه نشود، چقدر جریمه برآوردی داریم؟",
        entity_type=REG,
        required=("CANONICAL_REG", "مانده تعهد", "FX_NTSW_CURRENCY",
                  "مهلت قانونی رفع تعهد"),
        aggregation=ADDITIVE,
        amount_field="جریمه برآوردی",
        currency_field="FX_NTSW_CURRENCY",
        note_fa="جریمه از مانده و مهلت مشتق می‌شود؛ نبود هرکدام، برآورد را بی‌اعتبار می‌کند.",
    ),
    DecisionContract(
        id="PART_CRITICALITY",
        title_fa="طبقه بحرانی قطعات",
        question_fa="کدام قطعات خط تولید را می‌خوابانند؟",
        entity_type=MATERIAL,
        required=("KEY_MATERIAL", "نیاز روزانه", "موجودی ایران خودرو", "موجودی ساپکو"),
        aggregation=DISTRIBUTIONAL,
        decision_floor=95.0,
        directional_floor=70.0,
        note_fa="مقاومت = (موجودی ایران‌خودرو + ساپکو) ÷ نیاز روزانه. "
                "نبود نیاز روزانه یعنی مقاومت اصلاً قابل محاسبه نیست.",
    ),
    DecisionContract(
        id="SHIPMENT_TRACKING",
        title_fa="رهگیری محموله",
        question_fa="هر محموله الان کجاست؟",
        entity_type=BL,
        required=("CANONICAL_BL", "SHIPPED_EVIDENCE_DATE"),
        aggregation=DISTRIBUTIONAL,
        decision_floor=98.0,
        directional_floor=85.0,
        note_fa="عمداً کم‌توقع است: پرونده‌ای که تاریخ ترخیص ندارد، برای «کجاست؟» "
                "کاملاً قابل استناد است. همین، مثال زنده «درجه به تصمیم می‌چسبد، نه رکورد».",
    ),
)

BY_ID: Dict[str, DecisionContract] = {c.id: c for c in CONTRACTS}


def cross_source_for(entity_type: str) -> Tuple[CrossSourceRule, ...]:
    return CROSS_SOURCE.get(entity_type, ())


def contracts_for(entity_type: str) -> Tuple[DecisionContract, ...]:
    return tuple(c for c in CONTRACTS if c.entity_type == entity_type)


def entity_types() -> Tuple[str, ...]:
    """Entity types that have both rules and at least one decision."""
    return tuple(e for e in RULES if contracts_for(e))


__all__ = [
    "REG", "MATERIAL", "BL", "KEY_COLUMN", "ENTITY_FA",
    "REG_RULES", "MATERIAL_RULES", "BL_RULES", "RULES",
    "CONTRACTS", "BY_ID", "contracts_for", "entity_types",
]
