# GSI / AIBL V26.16 — FX Traceability & Import Obligation Intelligence

## اضافه‌شده
- Stage بومی `fx_traceability` با grain ثبت سفارش و Event Ledger مستقل.
- تفکیک FX Purchase، Bank Funding و SWIFT.
- سه Bucket مستقل برای سند ترخیص، مابه‌التفاوت نرخ ارز و وثیقه.
- ثبت مسیر تخصیص مستقیم/غیرمستقیم/نامشخص.
- anomaly engine برای توالی زمانی، مانده تعهد، پوشش Evidence و تناقض مالی–گمرکی.
- خروجی‌های FX در Dashboard، Report Builder و HTML Process Explorer.
- Snapshot مقررات ۱۴۰۵ در RuleBook و اصلاح استناد مهلت انبار گمرکی به ماده 24.
- Overlay مشروط 65882/48174 تا پایان شهریور ۱۴۰۵ و Rule مشروط تسهیل SATA/EPL (بدون اعمال خودکار).

## اصلاح‌شده
- Conformance Ruleها با نام Activityهای واقعی Event Log همسان شدند.
- کنترل ترتیب بر اساس جایگاه زمانی واقعی اجرا می‌شود.
- الزام عمومی «FX قبل از Shipment» حذف شد و به مدل ابزار پرداخت وابسته می‌شود.
- 540/360 و نرخ‌های جریمه قدیمی از «ادعای قانونی» به SLA/سناریوی داخلی تنزل داده شدند.
- عنوان‌ها و Fact Sheet از محاسبه قطعی جریمه حقوقی فاصله گرفتند.

## تست
- 36/36 تست معماری موفق.
- تست اختصاصی V26.16 برای fan-out، obligation buckets، conformance و rule snapshot موفق.
- تست HTML exporter نیز موفق.

## محدودیت
در این محیط مسیر شبکه Production سازمان قابل دسترس نیست؛ تست روی داده زنده باید در شبکه داخلی انجام شود.
