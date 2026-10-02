# GSI V29 — System Reliability & Business DWH

این نسخه لایه انبار داده را از «ذخیره خروجی گزارش» به یک Core بیزینسی قابل ممیزی ارتقا می‌دهد.

## اصول معماری

- `REG_FILE` و `REG` دو موجودیت مستقل هستند و هیچ‌وقت alias یکدیگر نیستند.
- مسیر اتصال NTSW مطابق بیزینس: `Import Licence -> REG_FILE -> IL Append -> REG/ORDER` و سپس سایر بخش‌ها.
- Bridge فقط از **direct co-observation** ساخته می‌شود؛ رابطه ترانزیتی به‌عنوان evidence ذخیره نمی‌شود.
- BL خام Commercial Expert در relation graph بارنامه استفاده نمی‌شود.
- `Missing != Zero` در همه Factهای موجودی/نیاز/مقاومت حفظ شده است.
- Factهای Order×Material، Oracle Material، NTSW Allocation Request و NTSW Commitment دارای grain مستقل‌اند.
- Raw/Bronze و Silver source rows نگه داشته می‌شوند تا هیچ داده‌ای بی‌ردپا حذف نشود.

## Reliability Gate

قبل از Publish، موارد زیر بررسی می‌شود:

1. Required columns
2. Null/blank key
3. Grain uniqueness و composite-key drift
4. Schema drift نسبت به baseline نخستین اجرای پذیرفته‌شده
5. Row-preservation بین `main / to_resolve / excluded`
6. SQLite `foreign_key_check`
7. SQLite `integrity_check`
8. Join row-explosion guard موجود در `safe_merge`

هر Check سطح `BLOCK/WARN/INFO` دارد. فقط BLOCK ناموفق Publish را متوقف می‌کند.

## Failure isolation

`report` و `dwh` pointer در یک transaction جابه‌جا می‌شوند. اگر Quality Gate رد شود:

- Run و diagnostics باقی می‌مانند؛
- Snapshot خراب current نمی‌شود؛
- هر دو pointer روی آخرین Run سالم باقی می‌مانند.

## DWH Core

Dimensionها:

- `dwh_dim_order`
- `dwh_dim_material`
- `dwh_dim_bl`
- `dwh_dim_registration`
- `dwh_dim_registration_file`
- `dwh_dim_pr`
- `dwh_dim_employee`

Evidence graph:

- `dwh_entity`
- `dwh_relation`
- `dwh_registration_hub`

Factها:

- `dwh_fact_source_row` — Silver evidence row بدون حذف
- `dwh_fact_supply_position` — Grain: Order×Material
- `dwh_fact_oracle_material` — Grain: Material
- `dwh_fact_ntsw_allocation_request` — Grain: Allocation Request
- `dwh_fact_ntsw_commitment` — Grain: Registration

Forensics:

- `dwh_unresolved_relation`
- `wh_quality_check`
- `wh_schema_baseline`
- `wh_publish_event`

## Streamlit DWH Control Room

در محیط «دیتاورهوس» امکان‌های زیر وجود دارد:

- Trigger کامل واکشی سورس + Pipeline + DWH + Quality Gate
- مشاهده Runها و reconciliation
- مشاهده Checkهای Reliability
- Source Profiler برای Raw header / metadata / چند ردیف فیزیکی
- Relation Explorer و Registration Hub
- مشاهده unresolved relations
- دریافت Backup SQLite

## تست واقعی این Release

- تست مستقل بسته: `174 passed`
- تست‌های اختصاصی V29: Grain duplicate, missing key, schema drift, atomic publish, business registration hub
- Synthetic end-to-end: `quality_gate_passed=True`, `foreign_key_check=[]`, `integrity_check=ok`
- Failure injection: حذف `شماره پرونده ثبت سفارش` از NTSW Import Licence باعث `BLOCK` شد و هر دو current pointer بدون تغییر روی Run سالم قبلی ماندند.

تست‌های وابسته به share واقعی IKCO و تست‌های legacy دارای fixture تعریف‌نشده در این محیط اجرا نشده‌اند؛ این موضوع در Release Validation ثبت شده است.
