# تحویل GSI — Customizable HTML + Cash Flow — 2026-09-26

## هدف
این pass روی همان baseline نهایی `GSI 29.8.2 RC4-OPT2 H1` انجام شده و هیچ تغییر معنایی در DWH، KPI، grain، source authority، publication gate یا Process evidence ایجاد نمی‌کند. هدف فقط این است که خروجی HTML واقعاً قابل شخصی‌سازی و قابل ارسال باشد.

## قابلیت‌های افزوده‌شده
- Drag & Drop برای بلوک‌های اصلی هر تب.
- Drag & Drop مستقل برای کارت‌های نمودار.
- Drag & Drop مستقل برای پنل‌های Process Mining.
- کنترل جایگزین دسترس‌پذیر بالا/پایین برای کاربرانی که Drag استفاده نمی‌کنند.
- تغییر اندازه هر جزء: تمام‌عرض، نیم‌عرض، یک‌سوم، یک‌چهارم.
- حذف از خروجی و Restore از پنل موارد حذف‌شده.
- Reset به چیدمان پایه.
- نگهداری چیدمان در مرورگر به‌صورت local-only.
- دکمه «دانلود HTML سفارشی» که چیدمان انتخابی را داخل خود فایل HTML embed می‌کند؛ گیرنده همان layout را بدون سرویس خارجی می‌بیند.

## Cash Flow
در بازبینی مشخص شد runtime مربوط به `Money Flow Control Tower` و `renderFx()` در HTML وجود داشت اما target واقعی برای نمایش آن ساخته نشده بود. بنابراین وجود کد به معنی نمایش واقعی Cash Flow نبود.

اصلاح:
- `cashflow` به عنوان Block رسمی Composer اضافه شد.
- در layoutهای پیش‌فرض Expert / Manager / Executive / Analyst قرار گرفت.
- HTML واقعی target مستقل `process-fx` می‌سازد.
- `renderFx()` در render فعال فراخوانی می‌شود و تمام targetهای Cash Flow موجود در تب‌ها را پر می‌کند.
- خود Cash Flow نیز مانند سایر بلوک‌ها قابل Drag / Resize / Hide / Restore است.

## حفاظت معنایی
Customizer فقط DOM presentation state را تغییر می‌دهد. هیچ داده‌ای از `DATA`/`PROC` بازنویسی نمی‌شود، فیلتر یا aggregation عوض نمی‌شود، و هیچ تغییر DWH یا publish انجام نمی‌شود.

## تست این pass
- HTML/Composer regression: **18/18 PASS**
- JavaScript combined syntax compile: **PASS**
- Python compile: **PASS**
- Browser Playwright validation در این محیط قابل اجرا نیست چون dependency `playwright` نصب نیست؛ برای آن ادعای PASS نشده است.

## Sample
`samples/release_html/GSI_SAMPLE_CUSTOMIZABLE_CASHFLOW.html`

این Sample با داده ساختگی ساخته شده و برای تست مستقیم Drag & Drop، Resize، حذف/بازگردانی، دانلود HTML سفارشی و نمایش Cash Flow است.
