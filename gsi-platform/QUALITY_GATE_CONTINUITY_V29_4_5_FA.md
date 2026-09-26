# V29.4.5 — Quality Gate Continuity

## مسئله
در NTSW / Import Licence وجود حتی یک ردیف با KEY_REG_FILE یا KEY_REG خالی، کل انتشار را با `NULL_OR_BLANK_KEY` مسدود می‌کرد و Streamlit نیز به‌جای آخرین Snapshot سالم، صفحه را متوقف می‌کرد.

## اصلاح بیزینسی
Import Licence یک جدول evidence/hub است. ردیف ناقص نباید bridge مستقیم بسازد، اما نباید کل Pipeline را هم متوقف کند.

- ستون‌های KEY_REG_FILE و KEY_REG همچنان اجباری‌اند.
- ردیف کامل (هر دو کلید موجود) evidence مستقیم معتبر است.
- ردیف ناقص حفظ می‌شود و در `dwh_unresolved_relation` با reason code ثبت می‌شود.
- وجود ردیف ناقص => WARN `PARTIAL_KEY_EVIDENCE`.
- فقط اگر هیچ ردیف کامل و قابل‌استفاده‌ای وجود نداشته باشد => BLOCK `USABLE_KEY_EVIDENCE`.
- duplicate grain فقط روی ردیف‌های دارای natural key کامل سنجیده می‌شود.

## تداوم Dashboard
Quality Gate failure اکنون Exception تایپ‌شده `QualityGateBlockedError` دارد.
Streamlit آن را Data Quality failure می‌شناسد، `gsi.doctor` را پیشنهاد نمی‌دهد و در صورت وجود Snapshot سالم قبلی، همان Snapshot را با برچسب واضح `QUALITY_GATE_BLOCKED` نمایش می‌دهد.

اصل: Run ناموفق برای Forensics باقی می‌ماند، current pointer جابه‌جا نمی‌شود، و Dashboard روی آخرین نسخه معتبر زنده می‌ماند.
