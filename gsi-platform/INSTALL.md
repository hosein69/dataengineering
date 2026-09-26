# نصب و راه‌اندازی GSI 29.10.0

> راهنمای قدیمی (مهاجرت از نسخه ۲۰) در `docs/history/INSTALL_V29_8_2.md` حفظ شده است.

## پیش‌نیازها

| مورد | حداقل | توضیح |
|---|---|---|
| Windows | 10 / Server 2016 | اجرا با `.cmd`؛ روی Linux/macOS هم با دستورهای Python کار می‌کند |
| Python | **3.11** یا بالاتر | همه فایل‌های کد روی 3.11 کامپایل می‌شوند (تست `test_platform_hardening_v29_9`) |
| دیسک محلی | ~2 GB آزاد | کد و انبار داده باید روی دیسک محلی باشند؛ SQLite روی مسیر شبکه/UNC ممنوع است |
| دسترسی خواندن | پوشه‌های سورس | فقط خواندن فایل‌های Excel از شبکه لازم است |

وابستگی‌ها در `requirements.txt` با **سقف major تست‌شده** آمده‌اند (مثلاً `pandas<3`،
`streamlit<2`). برای نصب کاملاً تکرارپذیر همان نسخه‌های اعتبارسنجی‌شده از
`requirements-validated.txt` استفاده کنید.

## نصب خودکار (پیشنهادی)

1. کل پوشه را در مسیر محلی Extract کنید، مثلاً `D:\GSI_APP\`.
2. در صورت نیاز مسیرها را فقط در `OPS\GSI_ENV.cmd` تنظیم کنید
   (`GSI_DATA_ROOT` و در صورت لزوم مسیر سورس‌ها).
3. `00_RUN_GSI.cmd` را اجرا کنید. اسکریپت `OPS\INSTALL_RUNTIME.cmd`:
   * Python 3.11+ را پیدا می‌کند (`py -3` یا `python`)،
   * `.venv` را کنار بسته می‌سازد و `requirements.txt` را نصب می‌کند،
   * import همه کتابخانه‌های runtime را می‌سنجد (`RUNTIME_IMPORTS=PASS`).
4. در کنترل‌پنل به ترتیب: **[7] Doctor → [3] Refresh → [2] Verify → [4] Start GSI**.

## نصب دستی

```powershell
cd D:\GSI_APP
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m gsi doctor
.venv\Scripts\python.exe -u -m gsi refresh
.venv\Scripts\python.exe -m streamlit run app\studio.py
```

Streamlit تنظیمات را از `.streamlit\config.toml` در **پوشه جاری** می‌خواند؛ همه
launcherها ابتدا به ریشه بسته `cd` می‌کنند. این فایل:
* سرور را فقط روی `127.0.0.1` باز می‌کند (داده مالی روی شبکه داخلی دیده نمی‌شود)،
* ارسال آمار استفاده Streamlit به اینترنت را خاموش می‌کند،
* دکمه Deploy را پنهان و تم را با توکن‌های طراحی GSI هم‌رنگ می‌کند.

## متغیرهای محیطی مهم

| متغیر | پیش‌فرض | کاربرد |
|---|---|---|
| `GSI_DATA_ROOT` | `D:\GSI_DATA` (غیر Windows: `~/GSI_DATA`) | ریشه داده عملیاتی |
| `GSI_DWH_PATH` | `%GSI_DATA_ROOT%\warehouse.sqlite` | انبار داده منتشرشده |
| `GSI_TODAY` | تاریخ Snapshot منتشرشده | تاریخ مرجع؛ شمسی (`1405/06/09`) یا میلادی |
| `GSI_RULES_DIR` | `gsi/rules` | کتابخانه قوانین بیرونی بدون نصب مجدد |
| `GSI_FOREIGN`، `GSI_BLS`، … | مسیرهای شبکه IKCO | در `OPS\GSI_ENV.cmd` |

## بررسی سلامت نصب

```powershell
VERIFY_RUNTIME.cmd                       # کدام کد و کدام نسخه واقعاً اجرا می‌شود
.venv\Scripts\python.exe run_all_tests.py  # باید «0 ناموفق» گزارش شود
```

## به‌روزرسانی از 29.8.2

* بسته جدید را در پوشه جدا Extract کنید؛ `.venv` قبلی را کپی نکنید (بسازید).
* انبار داده (`D:\GSI_DATA`) سازگار است؛ مهاجرت schema لازم نیست.
* یک بار **Refresh** اجرا کنید: اصلاحات صحت داده (عدد، تاریخ، ارز) فقط روی اجرای جدید
  اثر دارند و Snapshotهای قبلی همان‌طور که منتشر شده‌اند می‌مانند.
* میان‌برهای قبلی کار می‌کنند: `RUN_STUDIO_V28.cmd` اکنون همان `START_GSI.cmd` است و
  `VERIFY_RUNTIME_V29_6_4.cmd` به `VERIFY_RUNTIME.cmd` تغییر نام داد.
