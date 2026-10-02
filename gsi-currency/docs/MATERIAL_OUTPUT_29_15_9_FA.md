# گزارش اصلاح مسیر خروجی متریال — GSI 29.15.9

تاریخ: 2026-09-27

## نتیجهٔ صریح

در 29.15.8 دادهٔ چندمتریاله در adapter و دفتر مستقل `Order×Material` حفظ می‌شد، اما دو شکاف خروجی وجود داشت:

1. ماتریس رسمی، فیلد «همهٔ کدهای متریال» را در کاتالوگ انتشار اعلام نمی‌کرد؛ بنابراین مصرف‌کنندهٔ ماتریس می‌توانست فقط متریال سازگاری/نماینده را ببیند.
2. شیت «۱۴. متریال محور» از mart تخت سفارش/بارنامه ساخته می‌شد و دفتر کامل `expert_material_positions` را نمی‌گرفت. HTML نیز پارامتر `material_supply_view` را می‌پذیرفت ولی از آن استفاده نمی‌کرد. نتیجه: متریال دوم/سوم یک سفارش می‌توانست در DWH حفظ شده باشد اما در Excel/HTML قابل مشاهده نباشد.

## اصلاح انجام‌شده

- `MOGH_MATERIALS_ALL` و `MOGH_KEY_MATERIAL_COUNT` در کنار `MOGH_MATERIAL_DESCS_ALL` و `MOGH_MATERIAL_DESC_COUNT` وارد ماتریس رسمی و field catalog شدند.
- شیت «۱۴. متریال محور» علاوه بر نمای عملیاتی قبلی، یک جدول مستقل و فیلترپذیر `ExpertMaterialEvidence` در دانهٔ دقیق Order×Material دارد.
- HTML دفتر کامل شواهد کارشناسان را در همان تب متریال نشان می‌دهد. این جدول evidence-only است و هیچ موقعیت، مالک یا بارنامه‌ای را از سفارش به متریال خواهر تعمیم نمی‌دهد.
- Export صریح Published Snapshot، در صورت وجود ledger منتشرشده، شیت `Material Evidence` با جدول `PublishedExpertMaterialEvidence` اضافه می‌کند؛ ETL یا source workbook را دوباره اجرا/نمی‌خواند.
- تب‌های HTML ذخیره‌شده، در صورت وجود، `MOGH_MATERIALS_ALL` و `MOGH_MATERIAL_DESCS_ALL` را نیز به‌عنوان lineage قابل مشاهده حمل می‌کنند.

## چیزی که عمداً تغییر نکرد

- فرمول‌های مالی و Missing≠Zero
- قواعد بحرانی و rulebook
- منطق event/process و duration
- مرجع مالک، وضعیت حمل، رابطهٔ Order/BL و authority آن‌ها
- grain عملیاتی mart اصلی
- Snapshot-first / explicit refresh lifecycle

## مرز ایمنی

Commercial Expert برای این دفتر، **شاهد Order×Material** است؛ نه منبع مجاز برای ساختن رابطهٔ عملیاتی بارنامه/مالک/مرحله. به همین دلیل ledger جدا نگه داشته شده است. این جداسازی عمداً از join کردن متریال‌های هم‌سفارش به وضعیت یک BL جلوگیری می‌کند.

## اعتبارسنجی اجراشده پیش از بسته‌بندی

- 68/68 تست affected/regression/release در اجرای یکپارچه: PASS (22.58 s)؛ شامل Material، Expert ledger، source-boundary، Feedback، Process Context، Shipping، Supply Views، Validation/Report integration، Manifest و Documentation.
- compile فایل‌های production تغییرکرده: PASS
- اجرای full-suite عمومی دو بار در سقف زمانی محیط ابزار متوقف شد و نتیجهٔ نهایی نداد؛ بنابراین Full Suite در این نسخه PASS اعلام نشده است.
- regression مستقل چندمتریاله: کد 9654003280 با دو شرح + متریال دوم B-2؛ هر دو Order×Material و هر دو شرح در Excel/HTML حفظ شدند و payload جعلی `BYPASS` نتوانست authority عملیاتی را دور بزند.

Post-pack روی ZIP تمیز نیز انجام شد: CRC سالم، 1106/1106 هش فایل مطابق `PACKAGE_SHA256.json`، بدون SQLite/pyc/cache، و 68/68 تست affected/release پس از Extract مجدد PASS شد. Full Suite عمومی در این محیط بدون نتیجهٔ نهایی به سقف زمان خورد و PASS اعلام نشده است.

## محدودیت دادهٔ واقعی موجود در این محیط

فایل واقعی `NTSW-IKCO.xlsx` بررسی شد. شیت‌های آن عبارت‌اند از Import License، Allocation، Release Commitment، Quota، Overall Quota، Quota Season و Assistant؛ **Commercial Expert Data / Expert Data در آن وجود ندارد**. بنابراین این فایل نمی‌تواند شاخهٔ Commercial Expert → Order×Material را end-to-end روی دادهٔ واقعی سازمان تأیید کند. این مورد PASS اعلام نشده است. پذیرش نهایی این شاخه روی فایل واقعی کارشناسان سازمان باید با همان تست‌های 29.15.9 انجام شود.

## فایل‌های اصلی تغییرکرده

- `gsi/stages/s10_resolve.py`
- `gsi/studio_core/field_catalog.py`
- `gsi/report/supply_views.py`
- `gsi/report/dashboard.py`
- `gsi/pipeline.py`
- `gsi/studio_core/html_export.py`
- `gsi/studio_core/report_builder.py`
- `gsi/warehouse/export_snapshot.py`
- `app/dashboard.py`
- `gsi/integrations/daily_email.py`
- `tests/test_material_output_propagation_v29_15_9.py`

