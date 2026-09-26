# اصلاحات تکمیلی GSI V28

این بسته بر پایه GSI 28.0.0 ساخته شده و اصلاحات پس از بسته نهایی اولیه را شامل می‌شود.

## اصلاحات

- `gsi/studio_core/html_export.py`
  - امن‌سازی JSON تعبیه‌شده داخل `<script>` در HTML داینامیک و جلوگیری از شکستن context توسط `</script>`.
  - حذف وابستگی به silent downcast در `fillna` برای payloadهای نمایشی.
- `gsi/stages/s80_eventlog.py`
  - تبدیل صریح `ORDER_CERTAIN` به nullable boolean و سپس bool برای سازگاری پایدارتر با pandas.
- `gsi/pipeline.py`
  - حفظ قرارداد ثابت Workbook با 17 شیت حتی وقتی سورس اختیاری Commercial Expert Data خالی است.
- `run_all_tests.py`
  - ایزوله‌سازی Warehouse هر suite در دیتابیس موقت برای جلوگیری از اثر اجرای قبلی و تداخل تست‌ها.
- `tests/test_html_export_v26_15.py`
  - افزودن regression test برای جلوگیری از خروج از script context.
- `gsi/MANIFEST.json`
  - بازسازی مانیفست و اثرانگشت فایل‌ها پس از اصلاحات.

## اعتبارسنجی انجام‌شده

- `python -m gsi.doctor`: بدون خطا، مانیفست سازگار.
- `tests/test_html_export_v26_15.py`: 2/2 موفق.
- `tests/test_architecture.py`: 42/42 موفق.
- `tests/test_warehouse_v28.py`: 17/17 موفق.
- `tests/test_v26_20_runtime_and_grain.py`: 11/11 موفق.
- `tests/test_dashboard.py`: 79/79 موفق.
- `tests/test_report_builder.py`: 35/35 موفق.
- `tests/test_validation.py`: موفق در اجرای هدفمند این hotfix.

اجرای کامل `run_all_tests.py` در محیط ساخت به سقف زمان نشست رسید؛ بنابراین این سند ادعای اجرای کامل مجدد suite پس از hotfix را ندارد. مجموعه تست کامل بسته پایه پیش از این اصلاحات طبق `RELEASE_VALIDATION_V28_FA.md` برابر 816 موفق و صفر ناموفق بوده است.
