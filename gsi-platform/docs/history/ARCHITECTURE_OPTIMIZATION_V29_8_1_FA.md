# ممیزی معماری و بهینه‌سازی GSI 29.8.1 — RC4-OPT1

## حکم معماری

RC4 از نظر جهت معماری نیازمند بازنویسی نیست. مشکل اصلی در این ممیزی دو دسته بود:

1. **هزینه I/O و حافظه در ingest/persistence** که برای حجم‌های بزرگ بی‌دلیل داده را دوباره در RAM تکثیر می‌کرد.
2. **خروجی‌های مالی تصمیم‌ساز** که در چند مسیر از قرارداد Grain Registry عبور نمی‌کردند و می‌توانستند یک مانده سطح ثبت سفارش را روی جدول BL×Material چند بار جمع کنند یا ارزهای متفاوت را در یک عدد بی‌واحد ادغام کنند.

اصل اصلاح این نسخه: business rule یا source authority تغییر نکند؛ فقط persistence کم‌هزینه‌تر و presentation/aggregation قابل اتکاتر شود.

## یافته‌های Severity بالا

### A-01 — fan-out مانده تعهد در خروجی‌های تصمیم‌ساز

جدول اصلی می‌تواند در دانه بارنامه×متریال باشد، درحالی‌که «مانده تعهد» و «جریمه برآوردی» در دانه REG هستند. جمع ساده روی ردیف‌ها می‌تواند یک ثبت سفارش دارای چند بارنامه/متریال را چند برابر کند.

مسیرهای اصلاح‌شده:

- `app/studio.py`
- `gsi/report/dashboard.py`
- `gsi/report/charts.py`
- `gsi/report/insight.py`
- `gsi/studio_core/excel_export.py`
- `gsi/integrations/daily_email.py`
- `gsi/report/history.py`
- `gsi/warehouse/historical_store.py`
- `gsi/stages/s50_commitment.py`

### A-02 — جمع cross-currency

عددهایی مثل `100 EUR + 200 USD = 300` از نظر تصمیم‌سازی معتبر نیستند. `gsi/report/financial_summary.py` اکنون نقطه مرکزی نمایش مالی است و مبلغ را بر `(registration, currency)` یکتا می‌کند. خروجی چندارزی به شکل مستقل نمایش داده می‌شود، مثلاً `50.00 EUR | 100.00 USD`.

### A-03 — unknown balance به‌عنوان zero/settled

در قرارداد legacy موتور، مقدار نامعلوم می‌تواند همراه با `BALANCE_IS_UNKNOWN=True` عدد صفر داشته باشد. در نمودار قبلی `fillna(0)` و شرط `balance <= 0` می‌توانست این مورد را «تسویه‌شده» نشان دهد. مسیرهای تصمیم‌ساز اکنون flag را محترم می‌شمارند و مورد نامعلوم را از جمع عددی خارج و به‌صورت diagnostic آشکار می‌کنند.

## بهینه‌سازی‌های Performance

### P-01 — SQLite frame persistence

`Warehouse.frame` قبلاً همه payloadهای JSON را در یک list بزرگ می‌ساخت و سپس `executemany` می‌کرد. نسخه جدید با `GSI_WAREHOUSE_FRAME_CHUNK_ROWS` (پیش‌فرض 1000) batch می‌نویسد، اما همان transaction واحد، `row_no`، metadata، dtype/index/attrs و atomicity را حفظ می‌کند.

### P-02 — Excel physical archive reuse

آرشیو Excel همچنان content-addressed و physical-cell است. اگر SHA همان workbook قبلاً کامل در `wh_sheet` موجود باشد، worksheet XML دوباره parse نمی‌شود. برای native reader در صورت نیاز rows از SQLite rehydrate می‌شوند.

### P-03 — Legacy Excel ingest بدون cell-map اضافی

برای readerهای Legacy که downstream خود فایل Excel را با pandas می‌خواند، `capture(..., keep_sheets=False)` استفاده می‌شود. bytes آرشیوی و physical audit همچنان ذخیره می‌شود، اما dict حجیم تمام cellها هم‌زمان در RAM نگه داشته نمی‌شود. در multi-file source نیز هر فایل بلافاصله پردازش و reference آن آزاد می‌شود.

## benchmark محلی مصنوعی

این اعداد **production throughput نیستند**؛ فقط مقایسه A/B روی یک ماشین و workload یکسان‌اند.

| workload | RC4 | 29.8.1 OPT | تغییر |
|---|---:|---:|---:|
| SQLite frame، 12k×72 | 0.6615 s | 0.6394 s | حدود 3.3٪ سریع‌تر |
| peak افزوده همان serialization | ~3.0 MiB | ~0.625 MiB | حدود 79٪ کمتر |
| SQLite frame، 18k×120 | 1.729 s | 1.627 s | حدود 5.9٪ سریع‌تر |
| capture مجدد workbook یکسان، 3×5000×18 | 1.189 s | 0.641 s | حدود 46٪ سریع‌تر |
| legacy capture، 4×7000×16، peak افزوده | ~252 MiB | ~137 MiB | حدود 46٪ کمتر |

اندازه DB در benchmark frame یکسان ماند؛ یعنی کاهش مصرف حافظه با حذف داده یا فشرده‌سازی lossy به‌دست نیامده است.

## تصمیم‌های عمداً انجام‌نشده

- فرمول‌های حقوقی/جریمه RuleBook تغییر نکردند.
- Source authority و join keyها تغییر نکردند.
- قرارداد legacy `CommitmentEngine` که unknown را همراه flag به numeric legacy تبدیل می‌کند شکسته نشد؛ اصلاح فقط در decision surfaces اعمال شد.
- هیچ نرخ تبدیل FX برای تبدیل همه ارزها به یک ارز پایه جعل نشد. تا وقتی نرخ/تاریخ authority مشخص نباشد، ارزها جدا می‌مانند.

## توصیه برای استقرار

قبل از production sign-off یک reconciliation روی workbookهای واقعی سازمان اجرا شود: تعداد rows/sheets، SHA archive، تعداد REG یکتا، مجموع مانده به تفکیک currency، unknown flags، و مقایسه خروجی RC4 با RC4-OPT1. برای Streamlit نیز تست startup/browser باید در محیطی با dependencies رسمی اجرا شود.
