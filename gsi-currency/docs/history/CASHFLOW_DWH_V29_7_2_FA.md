# اصلاح Cash Flow از SQLite Business DWH — V29.7.2

## نتیجه

Cash Flow دیگر برای ورودی پیش‌فرض به `fx_money_ledger` یا جمعیت flat mart متکی نیست. نقطه شروع، شواهد native-grain ذخیره‌شده در **SQLite Business DWH** است.

سیاست اولویت شواهد از این نسخه:

1. **فایل کارشناسان (Commercial Expert / moghavemat) + NTSW** — درجه اول و وزن معنایی 1.00.
2. **عباسی + SATA** — درجه دوم و وزن معنایی 0.95.
3. FX Transaction / Credit / IL Append — شواهد مکمل، نه مرجع اولویت اصلی.

`merge_order` فنی flat mart عمداً با «اولویت حقیقت» یکی نشده است؛ SATA ممکن است برای ساخت فنی mart تخت زودتر join شود، اما در DWH/Cash Flow حق تقدم معنایی ندارد.

## علت خالی‌شدن Cash Flow

سه علت مستقل پیدا شد:

- Bridge قدیمی، ردیف‌های عملیاتی را با `status=OBSERVED` وارد موتور می‌کرد، درحالی‌که موتور فقط رویداد `POSTED` را می‌پذیرفت؛ در نتیجه حتی ledger پر، صفر رویداد پذیرفته‌شده می‌داد.
- UI قبل از محاسبه، رویدادها را با REG موجود در flat mart محدود می‌کرد؛ اختلاف دانه/کلید بین DWH و flat mart می‌توانست کل Cash Flow را صفر کند.
- `COMMITMENT_BALANCE` تاریخ مهلت رفع تعهد را به‌جای تاریخ مشاهده Snapshot مصرف می‌کرد و Snapshot می‌توانست Future/Invalid شود.

## اصلاحات

- ماژول `gsi/cashflow/dwh.py` اضافه شد و `dwh_fact_source_row` آخرین DWH منتشرشده را مستقیم می‌خواند.
- Commercial Expert از ORDER و NTSW از REG/REG_FILE استفاده می‌کنند. مسیر مستند `NTSW Import Licence: REG_FILE→REG` + `IL/NTSW: REG_FILE→ORDER` برای اتصال ORDER کارشناسان به REG به‌کار می‌رود؛ fuzzy join وجود ندارد.
- در تعارض کلید، NTSW بالاتر از SATA است. تعارض هم‌وزن بی‌صدا resolve نمی‌شود و diagnostic تولید می‌کند.
- `NTSW_KEY_REG` به‌صورت source-prefixed حفظ می‌شود تا در mergeهای flat از بین نرود.
- موتور حالت `SOURCE_FACT` را می‌پذیرد؛ این حالت مبلغ و چرخه را محاسبه می‌کند اما حساب بانکی ساختگی تولید نمی‌کند. حساب/حرکت بانکی فقط با سند واقعی POSTED ساخته می‌شود.
- کدهای ledger شامل SWIFT به `BANK_DOCS` نگاشت می‌شوند؛ balance/released snapshotها دوباره به‌عنوان cash event شمرده نمی‌شوند.
- Snapshot مانده تعهد NTSW در **تاریخ گزارش** ثبت می‌شود؛ deadline فقط deadline باقی می‌ماند.
- scope داشبورد از ORDER/BL موجود در DWH به REG گسترش می‌یابد و نبود REG در flat mart دیگر به‌تنهایی گزارش را صفر نمی‌کند.
- standalone `app/cashflow.py` نیز بدون upload، DWH منتشرشده را ورودی پیش‌فرض می‌گیرد.

## کنترل رگرسیون

در محیط ساخت این بسته، مجموعه تست‌های متمرکز Cash Flow/DWH/Source/Material برابر **83 passed, 1 deselected** بود. تست کنارگذاشته‌شده به `streamlit.testing` وابسته بود و Streamlit در runtime تست نصب نبود؛ این مورد به‌عنوان «تست اجرا نشده» ثبت شده و pass تلقی نشده است.

تست جدید تعارض عمدی ایجاد می‌کند: NTSW برای یک ORDER ثبت سفارش `11111111` و SATA مقدار `22222222` می‌دهد. خروجی باید `11111111` را انتخاب کند و مبلغ PI فایل کارشناسان را به همان پرونده متصل کند.
