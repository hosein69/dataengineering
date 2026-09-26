# V29.6.8 — Material Dashboard Runtime Enforcement

## مشکل واقعی
مسیر HTML داخل `app/dashboard.py` مستقیماً `build_dynamic_html()` را صدا می‌زد و برخلاف Report Composer، `build_material_html_view()` را پاس نمی‌داد. بنابراین اصلاح Advisory نسخه 29.6.7 در HTML دانلودشده از Dashboard اعمال نمی‌شد.

## اصلاح
`build_dynamic_html()` اکنون در صورت وجود `KEY_MATERIAL` و نبود View صریح، خودش `build_material_html_view(df)` را می‌سازد. این موتور به نقطه واحد اجرای قرارداد تبدیل شد و هر سه مسیر Dashboard / Report Composer / Email رفتار یکسان دارند.

در تب «دید تأمین — متریال محور»:
- Commercial Expert و NTSW وضعیت/موقعیت عملیاتی را تعیین نمی‌کنند.
- فیلدهای خام مالکیت/متن کارشناسی وارد وضعیت عملیاتی نمی‌شوند.
- خروجی این دو منبع فقط در «هشدار کارشناسان / کامنت کارشناسان / هشدار NTSW / کامنت NTSW» نمایش داده می‌شود.
- Search روی payload کامل دید متریال انجام می‌شود و `max_rows` فقط سقف نمایش پس از فیلتر است.

## تست رگرسیون
تست جدید `test_material_dashboard_runtime_v29_6_8.py` دقیقاً الگوی فراخوانی `app/dashboard.py` را بدون پارامتر `material_supply_view` بازسازی می‌کند.
