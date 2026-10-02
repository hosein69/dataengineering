# GSI V29.4 — Resilient ETL + Iranian Editorial Data UX

## 1) ETL بدون خاموش‌کردن کل فرآیند

اصل نسخه: **Stop the damaged branch, not the whole pipeline.**

- Adapterها مستقل بارگذاری می‌شوند؛ خطای یک سورس، واکشی بقیه را متوقف نمی‌کند.
- در خطای واکشی، اگر از همان سورس در آخرین Run منتشرشده Frame استاندارد وجود داشته باشد، همان Frame به‌صورت **Stale Fallback** استفاده می‌شود.
- Stale Fallback هرگز تازه تلقی نمی‌شود و در `wh_quality_check` با `STALE_FALLBACK_USED` ثبت می‌شود.
- خرابی سورس‌های غیرستون‌فقرات مثل SATA می‌تواند وضعیت Run را `DEGRADED` کند بدون خواباندن کل Publish.
- خرابی ستون‌فقرات `abbasi / ntsw / ilappend` یا Join انفجاری، Run را تا انتهای تشخیص جلو می‌برد ولی Publish را Block می‌کند؛ Pointerهای سالم قبلی حفظ می‌شوند.
- Row explosion در Join قرنطینه می‌شود و شاخه‌های بعدی برای تولید diagnostics ادامه پیدا می‌کنند.
- SQLite `FK`، `integrity_check`، Grain Contract، Schema Drift و Row Preservation همچنان Gate نهایی‌اند.

### چرا داده قدیمی را صفر نمی‌کنیم؟
`Missing ≠ Zero ≠ Failure ≠ Stale`.
در UI وضعیت Stale/Degraded جدا دیده می‌شود و عدد قدیمی به‌عنوان داده تازه معرفی نمی‌شود.

## 2) زبان بصری جدید

هدف: یک **Iranian Editorial Data System**، نه تم تزئینی ایرانی.

قاعده 80/15/5:
- 80٪ Enterprise و بسیار تمیز
- 15٪ Data Journalism و Storytelling
- 5٪ شخصیت ایرانی/دستی بسیار ظریف

رنگ‌ها:
- سفید: سطح اصلی و وضوح
- Aqua/Teal: جریان، Process و Interaction
- Navy: داده و اعتماد
- Warm Paper: فقط روایت، آموزش و annotation
- Gold: فقط Decision/Highlight

نمودارها هندسی و دقیق باقی می‌مانند؛ حس دست‌کشیده فقط در grid ظریف، annotation، rule و highlight دیده می‌شود. فرم‌ها، جداول و DWH Control Room عمداً صنعتی و ساده مانده‌اند.

## 3) شفافیت وضعیت داده

صفحه اصلی یک Data Health cue آرام دارد. جزئیات Reliability در DWH Control Room قابل مشاهده است:
- Critical / Blocking
- Degraded branch
- Warning
- Stale fallback
- تمام Quality Checks

پیچیدگی Reliability زیر سطح می‌ماند و رابط اصلی آرام و ساده است.
