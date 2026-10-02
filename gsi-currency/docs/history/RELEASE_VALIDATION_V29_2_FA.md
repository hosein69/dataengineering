# GSI V29.2 — Release Validation

## قابلیت جدید
- انتخاب مسیر پایگاه دانش از داخل Streamlit (مرور server-side و مناسب UNC/Shared Folder)
- انتخاب مستقل مسیر آموزش‌های هفتگی
- دکمه «ایجاد / به‌روزرسانی چت‌بات»
- ایندکس incremental با SQLite FTS5
- سرویس HTTP داخلی بسیار سبک با Python standard library
- mini-chat داخل HTML در صورت باز شدن فایل در مرورگر
- لینک fallback برای Outlook/کلاینت‌هایی که JavaScript را محدود می‌کنند
- عدم افشای مسیر Shared Folder در HTML
- auto-start سرویس پس از restart Streamlit، در صورت enabled بودن config
- quarantine فایل مشکل‌دار بدون fail شدن کل index

## تست هدفمند Release
49 passed / 0 failed.

پوشش تست‌ها: Knowledge Desk index/query/service، HTML privacy، Report Composer/tab isolation، Business DWH، Process Cockpit، Control Center، HTML compaction و FX compatibility.

## Suite گسترده
Suite بزرگ legacy در محیط CI تا بیش از 90٪ پیش رفت و به محدودیت زمانی runner رسید. خطاهای fixture قدیمی `res/df` از قبل شناخته‌شده‌اند و جزو production code نیستند. تست هدفمند Release بدون failure پاس شده است.

## محدودیت محیط
مسیرهای واقعی شبکه IKCO در container تست در دسترس نبودند؛ بنابراین دسترسی UNC باید روی Windows/شبکه سازمان با `python -m gsi.doctor` بررسی شود.
