# اصلاح مانیفست نسخه Consolidated

Doctor نسخه تجمیع‌شده را با مانیفست V28 پایه مقایسه می‌کرد و بنابراین فایل‌هایی را که عمداً در فرآیند ادغام تغییر کرده بودند به‌عنوان «قدیمی یا دست‌کاری‌شده» گزارش می‌داد.

در این Build، `gsi/MANIFEST.json` از خود سورس نهایی Consolidated بازتولید شده است. 152 فایل Python/YAML رسمی ثبت شده‌اند؛ از جمله Oracle multi-sheet، FX obligation، HTML/Studio hardening، report/history.py و config/metrics.yaml.

اعتبارسنجی انجام‌شده:
- `gsi.manifest.verify()` = صفر اختلاف
- قراردادهای بین‌ماژولی = سازگار
- تست‌های حساس Oracle/FX/HTML/Report Builder/Warehouse = 39/39 پاس

هشدار `GSI_PROFILE_ROOT` محیطی است و باید روی کلاینت با مسیر واقعی Store مشترک تنظیم شود؛ مقدار پیش‌فرضی در پکیج تحمیل نشده است.
