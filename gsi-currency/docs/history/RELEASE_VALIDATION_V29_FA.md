# Release Validation — GSI V29

## Code / unit regression

- Independent test suite: **174 passed**
- V29 focused reliability/business tests: **8 passed**
- Python compile: passed for all modified modules.

## End-to-end synthetic run

با Excelهای synthetic دارای هدرهای تولیدی:

- تمام 13 source adapters load شدند.
- NTSW Import Licence: 3 پرونده، 3 کد ثبت سفارش.
- DWH: 70 Silver source rows، 34 entity و 61 direct relation.
- Registration Hub نمونه:
  - `664823825 -> 98404279 -> 502805`
  - `664851493 -> 79668513 -> 501807`
  - `664851595 -> 89212481 -> 501317`
- `quality_gate_passed=True`
- `PRAGMA foreign_key_check = []`
- `PRAGMA integrity_check = ok`
- `report` و `dwh` هر دو به یک Run منتشرشده اشاره کردند.

## Failure injection

ستون `شماره پرونده ثبت سفارش` از NTSW Import Licence حذف شد:

- Pipeline diagnostic snapshot کامل شد.
- Quality Gate خطای `ntsw/import_license:NULL_OR_BLANK_KEY` ثبت کرد.
- Publish با ValueError متوقف شد.
- `report` و `dwh` pointer هر دو روی Run سالم قبلی باقی ماندند.

## محدودیت محیط تست

Share واقعی IKCO در محیط build در دسترس نیست. چند فایل تست legacy نیز fixtureهای `res/df` را در خود pytest تعریف نکرده‌اند. یک تست قدیمی FX HTML از نسخه قبل با قرارداد compact HTML تعارض دارد و در این Release تغییر داده نشده است. این موارد جزو تست مستقل 174 پاس‌شده محاسبه نشده‌اند.
