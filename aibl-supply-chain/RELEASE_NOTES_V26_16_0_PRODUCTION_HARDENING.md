# AIBL V26.16.0 — Production Hardening, Semantic Metrics, Secure HTML & Management Trend

این نسخه نتیجه بازبینی معماری، UX و نیازهای مدیریتی/کارشناسی پکیج V26.15 است و تغییرات زیر را اعمال می‌کند:

## P0 — صحت و اعتماد به عدد
- Semantic Metric Registry در `aibl/config/metrics.yaml` اضافه شد.
- تشخیص Amount/Ratio/Identifier دیگر از شکل مقادیر عددی حدس زده نمی‌شود.
- مبلغ‌های یکتا مثل `INVOICE_VALUE`, `DUTY_AMOUNT`, `NTSW_BALANCE`, `CB_VALUE` به اشتباه Identifier نمی‌شوند.
- KPI مانده تعهد، جریمه، نمودار تعهد، Insight و History با aggregation دانه‌ای محاسبه می‌شوند.
- Registry دانه، aggregation، unit و توضیح سنجه را نگه می‌دارد.

## P0 — HTML قابل اتکا
- lifecycle جاوااسکریپت دوگانه حذف شد و فقط یک render/listener flow وجود دارد.
- Process Explorer با فیلتر فعال از Event Log case-level باز-محاسبه می‌شود.
- اگر داده case-level کافی نباشد، عدد stale نمایش داده نمی‌شود و بخش صریحاً unavailable می‌شود.
- Narrative بزرگ‌ترین گلوگاه را بعد از sort واقعی انتخاب می‌کند.
- `visuals`, `tables`, `process` واقعاً در DOM اعمال می‌شوند.
- payload با سقف row/cell محافظت می‌شود تا HTML چندصد مگابایتی ساخته نشود.
- دکمه Excel مرورگری به «استخراج داده فیلترشده» تغییر نام داد و مقادیر عددی را numeric می‌نویسد.

## P0 — امنیت خروجی مستقل
- Access Scope پیش از serialize شدن داده اضافه شد.
- محدودسازی بر اساس `ORG_DEPT` و `CANONICAL_EXPERT` قبل از HTML/Excel اعمال می‌شود.
- فیلدهای حساس ایمیل/تلفن/شناسه شخصی به‌صورت پیش‌فرض از خروجی اشتراکی حذف می‌شوند.
- UI فیلتر HTML دیگر به‌عنوان کنترل دسترسی تلقی نمی‌شود.
- Tab سفارشی همان policy ستونی را دریافت می‌کند و نمی‌تواند PII حذف‌شده را دوباره وارد HTML/Excel کند.
- کلیدهای Grain پنهان به surrogate تبدیل می‌شوند؛ شناسه واقعی فقط وقتی embed می‌شود که خود کاربر آن را به‌عنوان فیلد مجاز انتخاب کرده باشد.
- Process payload به Event Log حداقلی (`CASE`, `ACTIVITY`, `EVENTTIME`) محدود شده و `case_table`/ستون‌های خصوصی embed نمی‌شوند.
- JSON داخل `<script>` در برابر script-breakout (`</script>`) escape می‌شود.

## P1 — UX نقش‌محور و تصمیم‌محور
- قالب‌های جدید «مدیریتی» و «سرپرستی» اضافه شدند.
- «صف تصمیم و اقدام» برای Executive/Manager/Supervisor اضافه شد؛ اولویت بر اساس توقف/بحرانی، مقاومت، تأخیر و مانده تعهد است.
- مالک، واحد و دلیل/اقدام کنار هر مورد نمایش داده می‌شود.
- قالب‌های Executive / Management / Supervisor / Operational / Process / Audit اکنون شخصیت خروجی متفاوت دارند.

## P1 — Trend مدیریتی
- Snapshot روزانه KPI به `AIBL_KPI_History.csv` اضافه شد.
- شیت جدید `۱۸. روند مدیریتی` به گزارش رسمی اضافه شد.
- روند متریال بحرانی و مانده تعهد برای پاسخ به «بهتر شدیم یا بدتر؟» نگهداری می‌شود.

## تست و Release Engineering
- نسخه مرجع به 26.16.0 ارتقا یافت.
- MANIFEST با نسخه 26.16.0 دوباره تولید شد و اثر انگشت 99 فایل پکیج با Doctor تأیید شده است.
- تست `test_v26_16_hardening.py` Semantic Registry، Access Scope، Grain-safe aggregation، کنترل Template، syntax JavaScript، جلوگیری از بازگشت PII در Tab سفارشی، حداقل‌سازی Process payload و snapshot روند را پوشش می‌دهد.
- import ماژول analytics در CI بدون Streamlit برای توابع pure ممکن شد.


## وضعیت اعتبارسنجی نهایی
- `python -m aibl.doctor`: **0 خطا**؛ هشدارهای باقی‌مانده فقط مسیرهای شبکه/وابستگی اختیاری محیط تست هستند.
- 18 فایل تست در Runner ثبت شده‌اند؛ **491 تست الزامی موفق** و 1 تست Chromium اختیاری است.
- Smoke Test با داده synthetic تولیدی: 13/13 سورس، 409 ستون نهایی، Workbook رسمی 18 شیتی، System Health و Management Trend حاضر، History CSV ساخته شد.
- `pipeline.py` پس از افزودن قابلیت‌ها همچنان قرارداد thin orchestrator را با 298 خط مؤثر رعایت می‌کند.
