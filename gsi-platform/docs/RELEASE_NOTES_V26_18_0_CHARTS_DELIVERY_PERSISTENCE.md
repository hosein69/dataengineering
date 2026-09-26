# AIBL V26.18.0 — Charts, Delivery & Persistence

## تحویل و UX
- کاتالوگ مشترک ۱۵ نموداری برای HTML و Email با انتخاب مستقل در Studio.
- انواع نمودار: bar، donut، grouped bar و scatter.
- Process chart در نبود Event/Transition history به توزیع مرحله فعلی fallback می‌کند و صفحه خالی نمی‌ماند.
- HTML با هویت بصری Automotive Supply Chain و نوار زنجیره تأمین خودرو.
- Email Composer برای TO، CC، Subject، Header، متن مقدمه و Profileهای پایدار.

## HTML بدون افت داده
- حذف silent `max_payload_cells` truncation که می‌توانست درخواست ۳۰۰۰ ردیف را به حدود ۹۰۰ کاهش دهد.
- payload آرایه‌ای compact به‌جای object-per-row برای حذف تکرار نام ستون‌ها.
- pagination سمت DOM با ۱۰۰ ردیف در صفحه؛ فیلتر/Excel روی کل payload فعال اجرا می‌شود.
- محدودیت ردیف فقط وقتی کاربر/Template صریحاً `max_rows` تعیین کرده باشد و در Artifact اعلام می‌شود.

## Warehouse پایدار بین نسخه‌ها
- durable pointer در `~/.aibl/warehouse.path` یا `%AIBL_HOME%/warehouse.path`.
- اولویت path: `AIBL_WAREHOUSE_PATH` > pointer پایدار > Settings legacy.
- Schema v2 با `app_profile` برای تنظیمات پایدار Studio/Email.
- backup خودکار SQLite در اولین باز شدن توسط Release جدید و پیش از schema migration؛ migration افزایشی و بدون reset تاریخچه.
- UUID در run_id برای refreshهای متوالی بدون collision.

## فارسی/فونت/Excel
- Native Excel chart title/axis/data-label با `IRANSans`, `fa-IR`, `rtl=1`.
- نام شیت‌ها/KPIهای Custom Excel فارسی شده‌اند.
- Outlook body از IRANSans استفاده می‌کند؛ PNG نمودار از IRANSans نصب‌شده یا `AIBL_FONT_PATH` استفاده می‌کند و Studio نبودن فونت را آشکار هشدار می‌دهد.
- فایل فونت داخل Release توزیع نمی‌شود.

## صحت
- Commitment chart رسمی نیز از Grain Registry (`safe_agg`) استفاده می‌کند.
- نمودار Process رسمی Excel نیز در نبود bottleneck واقعی fallback مرحله فعلی دارد.
