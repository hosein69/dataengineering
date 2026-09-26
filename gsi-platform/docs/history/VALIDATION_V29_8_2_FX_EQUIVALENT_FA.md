# Validation — GSI 29.8.2 RC4-OPT2

## دامنه
اعتبارسنجی این نسخه روی تغییرات Source-authority FX Equivalent، backward compatibility
خروجی‌های مالی و regression مسیرهای Cash Flow / Warehouse / Process انجام شده است.

## تست‌های اختصاصی 29.8.2
فایل `tests/test_fx_equivalent_authority_v29_8_2.py` موارد زیر را پوشش می‌دهد:
- جداسازی native amount چندارزی و جمع صحیح Equivalentهای مستقیم EUR/IRR.
- عدم تبدیل missing equivalent به صفر و نمایش coverage.
- استفاده از Source Equivalent فقط برای همان REG + همان Currency.
- ممنوعیت استفاده از نرخ پرونده یا ارز دیگر.
- fallback نرخ Allocation فقط برای همان REG + Currency.
- identity برای تعهد Native EUR.
- dedupe fan-out در جمع Portfolio Equivalent.
- integration Stage برای خرید همزمان USD/EUR.
- dedupe Snapshot تکراری Credit بر مبنای LC.
- عدم guess در conflict Equivalent یک LC.
- انتشار مستقیم `CRD_EUR_AMOUNT` / `CRD_RIAL_AMOUNT` در FX Ledger.

نتیجه آخرین اجرای اختصاصی: **10 passed**.

## Money Flow regression بعد از اصلاح نرخ چندارزی
مجموعه تست FX Equivalent + Money Flow اجرا شد و نتیجه: **17 passed**.
در پرونده چندارزی نرخ موزون واحد تولید نمی‌شود؛ نرخ‌ها به تفکیک Currency نمایش داده می‌شوند.

## Regression گسترده نهایی
پس از تکمیل Source Equivalent خرید ارز و Credit، نرخ چندارزی، خروجی‌ها و versioning،
دو مجموعه regression مرتبط با RC4 مجدداً روی همین worktree اجرا شدند:
- مجموعه decision/export/FX/RC integrity: **112 passed**.
- مجموعه cashflow/DWH/process/source/warehouse: **92 passed**.

جمع اجرای این دو مجموعه: **204 passed**. هیچ failure در این gate ثبت نشد.

## نکات دقت
- `FX_EUR_VALUE`, `FX_RIAL_VALUE`, `CRD_EUR_AMOUNT`, `CRD_RIAL_AMOUNT` Source facts
  هستند و به‌صورت مستقیم حفظ می‌شوند.
- `FX_NTSW_BALANCE_*_EQ` Source-reported NTSW equivalent نیست؛ reference valuation است.
- basis هر reference valuation قابل مشاهده است.
- partial Source coverage پنهان نمی‌شود.

## محدودیت محیط
workbookهای واقعی UNC/شبکه سازمانی در این محیط موجود نبودند؛ بنابراین header mapping و
reconciliation نهایی production باید روی Snapshot واقعی سازمان اجرا شود. این محدودیت به
معنی failure تست کد نیست، اما مانع ادعای production certification است.

## Final package gate
- `python -m compileall -q gsi app`: PASS
- regression decision/export/FX/RC: **112 passed**
- regression cashflow/DWH/process/warehouse: **92 passed**
- تست اختصاصی Source Equivalent: **10 passed** (داخل مجموعه 112 نیز اجرا شده است)
- تست ترکیبی Equivalent + Money Flow: **17 passed** (زیرمجموعه regression)
- Manifest داخلی GSI: **188 فایل، 0 issue**.
- بررسی قرارداد ماژول‌ها: **0 issue**.
- `PACKAGE_SHA256.json`: **686 فایل** در build قبل از ZIP ثبت و کنترل شد.
- ZIP پس از ساخت مجدداً extract شد: version=`29.8.2`، Manifest=`0 issue`، package hash=`0 mismatch`.
- smoke regression مستقیماً از محتوای extract‌شده ZIP: **13 passed**.
- SHA-256 نهایی خود ZIP در فایل `GSI_29_8_2_RC4_OPT2_SHA256.txt` ثبت می‌شود.
