# GSI V29.4.4 — رفع کندی Streamlit بعد از ذخیره Excel رسمی

## علت‌های اصلی

1. فایل بزرگ `Systemmatic Material.xlsx` در هر rerun فقط برای رندر دکمه دانلود با `read_bytes()` کامل خوانده می‌شد.
2. هر Mart پس از ذخیره در SQLite بلافاصله دوباره deserialize می‌شد؛ این round-trip برای صحت لازم نبود.
3. `last_report()` همه Martها، از جمله audit/excluded/to_resolve و تمام extrasهای Process/FX را eagerly می‌خواند؛ حتی اگر صفحه جاری از آن‌ها استفاده نمی‌کرد.
4. بازسازی DataFrame پهن از JSON rowهای SQLite برای UI هزینه‌بر است.

## اصلاح

- Excel رسمی فقط پس از زدن «آماده‌سازی دانلود» خوانده می‌شود.
- persistence فقط یک بار می‌نویسد؛ round-trip کامل فقط با `GSI_DWH_VERIFY_ROUNDTRIP=1` برای QA فعال می‌شود.
- `last_report` فقط `df` و `main` را برای First Paint می‌خواند؛ extras به‌صورت Lazy هنگام نیاز هر View بارگذاری می‌شوند.
- یک cache محلی و disposable برای DataFrameها ساخته می‌شود تا rehydration UI سریع باشد. SQLite همچنان منبع حقیقت است؛ حذف یا خرابی cache باعث fallback خودکار به SQLite و بازسازی cache می‌شود.

## اصل معماری

Performance cache هیچ داده کسب‌وکار جدیدی تولید نمی‌کند و در تصمیم‌گیری دخالت ندارد. تمام integrity/reconciliation/publish gateها روی SQLite باقی مانده‌اند.
