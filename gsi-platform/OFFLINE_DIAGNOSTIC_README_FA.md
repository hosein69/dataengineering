# اجرای ممیزی آفلاین همه‌جانبه GSI

این نسخه **Diagnostic Release** است، نه گواهی Production. هیچ دسترسی اینترنتی برای تست لازم نیست.

## اجرا روی Windows

1. ZIP را در یک پوشه جدید Extract کنید.
2. اگر فایل‌های واقعی منابع در مسیرهای تعریف‌شده‌ی GSI قابل دسترس‌اند، همان تنظیمات محیطی قبلی را نگه دارید. اگر فقط یک پوشه داده محلی دارید، می‌توانید آن را بدهید:

```bat
RUN_OFFLINE_DIAGNOSTIC.cmd --data-dir "D:\GSI_DATA"
```

بدون `--data-dir` نیز runner مسیرهای `sources.yaml` و environment variables موجود را بررسی می‌کند.

3. runner هیچ وب‌سایتی را فراخوانی نمی‌کند، DWH تست را در مسیر موقت خودش می‌سازد و فایل‌های منبع را تغییر نمی‌دهد.
4. در پایان پوشه `offline_feedback` یک فایل مانند `GSI_FEEDBACK_YYYYMMDD_HHMMSS.zip` ایجاد می‌شود.
5. **فقط همان ZIP feedback را برای من بفرستید.** نیازی به ارسال دوباره فایل‌های خام سازمانی نیست، مگر خود گزارش صریحاً بگوید برای یک مورد خاص evidence کافی وجود ندارد.

## چه چیزهایی سنجیده می‌شود

- integrity و hash بسته و knowledge snapshot؛
- ۱۷۳ سناریوی مستقل frozen audit؛
- تست‌های افزوده business-key، grain، currency، unknown/zero، row-order invariance، lineage و NTSW بدون Material؛
- تمام تست‌های داخلی پروژه به‌صورت file-by-file تا یک hang مانع بقیه نشود؛
- availability/schema منابع واقعی بدون کپی کردن داده خام؛
- اگر NTSW واقعی پیدا شود، probe محدود semantic روی REG_FILE/REG/ORDER و frame counts؛
- طبقه‌بندی failureهای شناخته‌شده IA01..IA17 و جداکردن failureهای جدید.

## محرمانگی feedback

source probe فقط metadata، hash (برای فایل‌های با اندازه مناسب)، نام sheet/header، شمارش‌ها و آمار کلیدی را ذخیره می‌کند. ردیف‌های خام کسب‌وکاری در feedback ZIP کپی نمی‌شوند.


## نسخه Visible Runner

اگر فایل‌های داده کنار پوشه استخراج‌شده پکیج هستند، فقط `RUN_OFFLINE_DIAGNOSTIC.cmd` را اجرا کنید؛ مسیر همان پوشه به‌طور خودکار به‌عنوان `--data-dir` استفاده می‌شود. runner از شروع هر مرحله پیام می‌دهد و هر ۱۰ ثانیه heartbeat چاپ می‌کند. در پایان پنجره با `pause` باز می‌ماند. خروجی `Gate HOLD` خطای runner نیست؛ یعنی تست کامل شده و finding دارد.
