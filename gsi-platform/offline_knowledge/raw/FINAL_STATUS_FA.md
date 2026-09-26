# وضعیت نهایی مرحله NTSW — GSI 29.8.2 RC4-OPT2-H1

## نتیجه اجرایی
این بسته ادامه مستقیم `H1 Review-Verified` است و Greenfield نیست. دامنه این مرحله اجرای واقعی `NTSW-IKCO.xlsx` و بستن خطاهای مشاهده‌شده در همان اجراست. فایل ورودی داخل بسته کد کپی نشده و SHA-256 آن `380631a763bc5cc3b75d0d403c1da99dcbf89974470ab71a10e531c31878538d` ثبت شده است.

**وضعیت انتشار:** `NTSW VERIFIED FINAL` برای دامنه NTSW؛ `production_certified=false` برای کل سامانه چندمنبعی.

## قرارداد هویتی قطعی
- `REG`: ثبت سفارش = شماره ثبت سفارش = کد ثبت سفارش.
- `ORDER`: سفارش = شماره سفارش = `Order No.` = `Our Reference`.
- `REG_FILE`: شماره پرونده = شماره پرونده ثبت سفارش؛ این هویت با REG یکی نیست.
- `BL`: بارنامه / شماره بارنامه / `BL No.` هویت مستقل است.
- `KEY_MATERIAL` برای gate فعلی NTSW شرط نیست و نبود آن نباید اجرای ثبت سفارش/تعهد/تخصیص را متوقف کند.

## شواهد اجرای واقعی NTSW
- Import License: 1,000 ردیف، 1,000 `REG_FILE` و 840 `REG`.
- 840 رابطه مستقیم `REG_FILE ↔ REG`؛ صفر `REG_FILE→چند REG` و صفر `REG→چند REG_FILE` در این snapshot.
- 160 پرونده ثبت سفارش در Import License شماره ثبت سفارش ندارند و unresolved نگه داشته شدند؛ مقدار ساخته نشده است.
- Allocation: 3,286 ردیف history، 2,834 fact معتبر، 1,418 پرونده REG تجمیعی.
- Release Commitment: 4,007 ردیف تعهد، 2,390 REG.
- Cashflow/DWH: 7,082 رویداد در 2,621 REG/case؛ diagnostics گزارش‌شده در این audit برابر صفر.
- توزیع ارز بعد از اصلاح normalization: EUR 3346، CNY 2681، AED 884، KRW 77، JPY 45، INR 31، USD 16، IRR 1، RUB 1.
- 53 تاریخ «صدور پیش‌فاکتور» بعد از تاریخ snapshot بین 2025-09-01 تا 2025-12-06 وجود دارد؛ به‌عنوان future-dated evidence ثبت می‌شود و تاریخ مرجع را تغییر نمی‌دهد.

## اصلاحات این مرحله نسبت به H1 Verified
فقط سه فایل production و دو تست جدید تغییر کرده‌اند:
1. `gsi/rulebook/loader.py`: normalization متن فارسی/عربی و whitespace قبل از currency alias lookup؛ نمونه واقعی `ین  ژاپن` اکنون `JPY` است.
2. `gsi/resolve/process_evidence.py`: pre-index شدن case+stage برای حذف فیلترهای تکراری؛ semantic contract ثابت مانده است.
3. `gsi/stages/s56_money_flow_control.py`: pre-aggregation برای حذف mask/filterهای quadratic روی REGهای واقعی؛ منطق status/risk ثابت نگه داشته شده است.
4. `tests/test_currency_normalization_ntsw_v29_8_2.py`: قرارداد normalization ارز.
5. `tests/test_business_key_alias_contract_v29_8_2.py`: قفل قرارداد REG / REG_FILE / ORDER.

## تست و regression
- baseline H1 قبلی: 528/528 تست قابل اجرا PASS؛ 3 AppTest محیطی به‌علت نبود Streamlit blocked.
- تست هدفمند delta فعلی: **49/49 PASS**.
- regression مستقیم توابع تغییرکرده و مصرف‌کنندگان آن‌ها: **92/92 PASS**.
- collection فعلی: 536 تست canonical.
- سه AppTest فعلی مجدداً اجرا شدند و هر سه فقط با `ModuleNotFoundError: No module named 'streamlit'` متوقف شدند.
- اجرای تمام 533 تست قابل اجرا در یک regression شاردشده در این محیط به سقف زمانی ابزار رسید؛ بنابراین ادعای ساختگی `533/533 PASS` در این گزارش وجود ندارد.

## ORDER و BL
فایل NTSW حاضر `ORDER` و `BL` را حمل نمی‌کند. در نتیجه این بسته هیچ سفارش یا بارنامه‌ای را از روی REG/REG_FILE حدس نمی‌زند. اتصال زنجیره `ORDER ↔ REG_FILE ↔ REG ↔ BL` برای production به فایل‌های واقعی bridge مانند IL Append و Abbasi/SATA (یا منبع معتبر معادل) نیاز دارد. در فایل‌های قابل دسترسی این جلسه، خود workbookهای bridge موجود نبودند؛ فقط evidence ساختارشان موجود است.

## Gate نهایی
**بسته برای تحلیل/ادامه NTSW و اجرای DWH/مالی روی همین scope قابل تحویل است.** برای اعلام `Production Certified` کل GSI هنوز سه مورد باز است: داده واقعی ORDER/BL bridge، اجرای سه AppTest در محیط دارای Streamlit، و reconciliation/performance چندمنبعی کامل.
