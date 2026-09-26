# GSI 29.8.2 RC4-OPT2 — معماری Authority نرخ ارز و Equivalent

## هدف
این اصلاح برای «ساخت نرخ جدید» نیست. سورس‌های موجود GSI از قبل نرخ ارز و معادل‌های
EUR/IRR را در چند نقطه گزارش می‌کنند. هدف نسخه 29.8.2 این است که همان Source Facts
بدون مخلوط‌کردن ارزها، بدون دوباره‌شماری fan-out و با lineage روشن وارد KPI و Report شوند.

## Source Authority

### 1. خرید ارز (`fx_transaction`)
فیلدهای مستقیم Source:
- `FX_AMOUNT` — مبلغ Native خرید ارز
- `FX_CURRENCY` — ارز Native
- `FX_RATE` — نرخ خرید ارز گزارش‌شده
- `FX_EUR_VALUE` — معادل یورویی گزارش‌شده Source
- `FX_RIAL_VALUE` — مبلغ/معادل ریالی گزارش‌شده Source

قانون 29.8.2:
- Native فقط درون همان Currency جمع می‌شود.
- `FX_EUR_VALUE` و `FX_RIAL_VALUE` چون واحد مشترک دارند قابل جمع‌اند، اما coverage
  نیز کنار آن‌ها نگه داشته می‌شود تا missing equivalent به صفر تبدیل نشود.
- اگر یک REG چند ارز خرید داشته باشد، `FX_PURCHASED_AMOUNT` عمداً خالی/NaN است و
  `FX_PURCHASED_NATIVE_DISPLAY` مقادیر را به تفکیک Currency نگه می‌دارد.

### 2. اعتبارات (`credit`)
فیلدهای مستقیم Source:
- `CRD_EUR_AMOUNT` — مبلغ به یورو
- `CRD_RIAL_AMOUNT` — مبلغ به ریال
- `CRD_LC_NO` — شماره اعتبار/حواله

قانون 29.8.2:
- Equivalent مستقیم Credit باز محاسبه نمی‌شود؛ همان مقدار Source مصرف می‌شود.
- Snapshotهای تکراری یک `CRD_LC_NO` یک‌بار شمرده می‌شوند.
- اگر یک LC برای یک Equivalent دو مقدار متناقض داشته باشد، مقدار conflict شده
  withheld می‌شود و `FX_CREDIT_EQ_STATUS=CONFLICTING_SOURCE_EQUIVALENTS` ثبت می‌شود.
- چند ردیف بدون LC که هویت مستقل آن‌ها اثبات‌پذیر نیستند به‌صورت محافظه‌کارانه
  جمع نمی‌شوند.

### 3. مانده تعهد NTSW
`NTSW_BALANCE` و `NTSW_CURRENCY` Source authority مبلغ Native مانده‌اند.
در قرارداد فعلی Release Commitment ستون مستقیمی برای «معادل EUR مانده» یا
«معادل IRR مانده» وجود ندارد. بنابراین فیلدهای زیر reference valuation هستند:
- `FX_NTSW_BALANCE_EUR_EQ`
- `FX_NTSW_BALANCE_RIAL_EQ`

این اعداد به‌عنوان «گزارش مستقیم NTSW» برچسب نمی‌خورند.

## ترتیب Authority برای Reference Valuation مانده NTSW

### EUR
1. اگر Currency خود تعهد EUR باشد: identity، یعنی 1 EUR = 1 EUR.
2. در غیر این صورت: نسبت `sum(FX_EUR_VALUE) / sum(FX_AMOUNT)` فقط روی ردیف‌های
   خرید ارز **همان REG + همان Currency**.
3. اگر شاهد موجود نباشد: EUR Equivalent خالی می‌ماند.

### IRR
1. اگر Currency خود تعهد IRR باشد: identity.
2. `sum(FX_RIAL_VALUE) / sum(FX_AMOUNT)` روی همان REG + Currency.
3. در نبود آن، نرخ `FX_RATE` همان REG + Currency.
4. در نبود شاهد خرید ارز، آخرین نرخ Allocation فقط از **همان REG + همان Currency**.
5. اگر هیچ‌کدام وجود نداشته باشد: IRR Equivalent خالی می‌ماند.

فیلدهای `FX_NTSW_EUR_EQ_BASIS` و `FX_NTSW_RIAL_EQ_BASIS` دقیقاً اعلام می‌کنند
کدام قاعده عدد را ساخته است. هیچ global rate و هیچ نرخ پرونده دیگر استفاده نمی‌شود.

## نرخ خرید چندارزی
`FX_PURCHASE_WAVG_RATE` فقط وقتی معنی دارد که REG یک Currency خرید داشته باشد.
در پرونده چندارزی این فیلد NaN می‌ماند و `FX_PURCHASE_RATE_DISPLAY` نرخ هر Currency
را جدا نشان می‌دهد. مقدار صفر به‌عنوان placeholder نرخ ممنوع شده است.

## Decision Surfaces اصلاح‌شده
- Pipeline / FX Ledger
- Studio KPI
- Dashboard KPI و scatter
- Money Flow Control Tower
- Excel FX Traceability
- Commitment / Scorecard Excel
- HTML process/commitment visualizations
- field catalog و export metadata

قراردادهای قدیمی Excel/UI تا حد امکان حفظ شده‌اند؛ ستون‌ها/اطلاعات جدید additive هستند.

## Invariants تصمیم‌ساز
1. EUR + USD + CNY به‌عنوان Native هرگز یک naked total نمی‌شوند.
2. Missing equivalent هیچ‌وقت صفر تلقی نمی‌شود.
3. نرخ از REG دیگر ممنوع است.
4. نرخ از Currency دیگر ممنوع است.
5. Source Equivalent مستقیم بر محاسبه مجدد مقدم است.
6. fan-out BL/Material نباید مبلغ REG را چندبار کند.
7. conflict Source به‌جای guess علامت می‌خورد.
8. Reference valuation مانده NTSW باید Basis قابل ممیزی داشته باشد.

## محدودیت
این اصلاح از قرارداد فیلدهای کد و داده‌های تست بسته تأیید شده است، اما workbookهای واقعی
UNC شبکه سازمانی در محیط ممیزی حاضر نبودند. بنابراین production reconciliation روی فایل
واقعی هنوز gate نهایی است و این بسته production certification محسوب نمی‌شود.
