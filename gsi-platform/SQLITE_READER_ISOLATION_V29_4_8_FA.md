# GSI V29.4.8 — SQLite Reader Isolation

## مشکل
Streamlit هنگام Lazy Load یک mart، `Warehouse(...)` تازه می‌ساخت. سازنده در نسخه‌های قبلی `CREATE TABLE IF NOT EXISTS` و `PRAGMA user_version` را اجرا می‌کرد؛ بنابراین یک عملیات کاملاً خواندنی می‌توانست با writer خط لوله برای قفل SQLite رقابت کند و `database is locked` بدهد.

## اصلاح
- Lazy reader با `initialize=False` باز می‌شود و هیچ DDL اجرا نمی‌کند.
- مسیر خواندن SQLite از مسیر نوشتن جدا و `query_only` شده است.
- `busy_timeout` محدود برای تراکنش‌های کوتاه writer وجود دارد.
- `read_frame` ابتدا cache محلی frame را می‌خواند و در cache-hit اصلاً SQLite را لمس نمی‌کند.
- قفل موقت یک mart جانبی دیگر کل Streamlit را crash نمی‌کند؛ همان mart `Missing` می‌ماند و خطای `DWH_READ_BUSY` ثبت می‌شود. Missing به صفر تبدیل نمی‌شود.
- سازنده روی DWH سالم موجود، در fast path دیگر schema DDL اجرا نمی‌کند.

## اصل
Single Writer حفظ شده است؛ این تغییر writer concurrency ایجاد نمی‌کند. فقط Readerها را از Writer جدا می‌کند.
