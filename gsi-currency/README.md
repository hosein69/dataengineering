# GSi: خرید ارز و رفع تعهد

اپ Streamlit و گزارش‌های HTML برای ثبت سفارش، صف تخصیص، خرید ارز، بارنامه‌های متصل به سفارش، جریان وجوه، ترخیص و
رفع تعهد (کد رهگیری ساتا). این پوشه آخرین نسخه بسته است: دور ۱۰ به‌اضافه فضای دیتا استوری‌تلینگ و عنوان GSi.
شرح تغییرات این نسخه در `RELEASE_NOTES_FA.md` و راهنمای نصب در `INSTALL.md` و `00_READ_ME_FIRST_FA.txt` است.

## آنچه در این مخزن نیست
این مخزن عمومی است، پس این موارد عمداً کنار گذاشته شده‌اند:
* **فایل‌های فونت دارای مجوز** (Ravi و IRANSans). فایل‌های خودتان را در `assets/fonts` بگذارید؛ بدون آن‌ها فونت پیش‌فرض سیستم استفاده می‌شود.
* پوشه‌های شواهد بازبینی و اجرا (`review`، `release_evidence`، `audit`، `offline_knowledge/raw`)، لاگ‌ها و فایل ضمیمه واقعی
  جریان وجوه (`samples/cashflow/attached_*`)، چون از داده واقعی منابع ساخته شده‌اند.
* انبار داده (`*.sqlite`)، `.venv` و کش‌ها.

## اجرا (Windows، PowerShell، Python 3.13)
```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app\studio.py
```
