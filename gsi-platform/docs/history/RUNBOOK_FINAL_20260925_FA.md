# Runbook عملیاتی بسته نهایی GSI — ۲۰۲۶-۰۹-۲۵

این Runbook با استفاده از گردش‌کار SOP تولیدشده توسط ابزار Process Documentation و سپس با قرارداد واقعی GSI اصلاح شده است. یک اصلاح مهم: **داده Missing هرگز صفر یا مقدار پیش‌فرض نمی‌شود**؛ در Gate متوقف یا با وضعیت «مشاهده نشده/قابل محاسبه نیست» حفظ می‌شود.

## ۱. راه‌اندازی
روی Windows سازمان از ریشه بسته `START_GSI.cmd` را اجرا کنید. UI باید Published Snapshot را بخواند و با بازشدن UI هیچ ETL پنهانی شروع نشود. اگر IRANSansWeb مجاز روی سیستم نصب است، UI آن را در اولویت می‌گیرد؛ بسته فایل فونت را حمل نمی‌کند.

## ۲. Refresh داده واقعی
Refresh فقط با اقدام صریح `REFRESH_GSI_DATA.cmd` یا `python -m gsi refresh` انجام شود. Source، Grain، Key و Quality Gate قبل از Publish بررسی شوند. خطای منبع واقعی نباید به Demo fallback کند.

## ۳. Fail-closed
موارد زیر انتشار نتیجه معتبر را متوقف می‌کنند: Case/Activity خالی، زمان نامعتبر، ترتیب مبهم Eventهای هم‌زمان، Conflictهای مالی/authority تثبیت‌شده، Handoff ناقص وقتی قرارداد Handoff ارائه شده، Pattern config نامعتبر و خرابی Manifest/Hash.

Owner/SLA/Document/Time غایب اگر برای یک محاسبه ضروری باشد، خروجی آن محاسبه «قابل محاسبه نیست» است؛ مقدار صفر ساخته نمی‌شود.

## ۴. گزارش سه‌نمایی
گزارش Process باید هر سه View را از یک Scope و Reference واحد بسازد:
- وضعیت و اقدام؛
- مسیر فرآیند؛
- تحویل بین واحدها.

Unique Case با Occurrence یکی نیست. Median/P90 زمان Route فقط فاصله Eventهای مشاهده‌شده است و به‌خودی‌خود Waste یا SLA breach نیست.

## ۵. Pattern config اختیاری
پیش‌فرض غیرفعال. برای CLI، `--pattern-config <json>`؛ برای UI متغیر `GSI_PROCESS_PATTERN_CONFIG`.

Matcher فقط Observation با source-row lineage تولید می‌کند. خروجی آن مجوز ارسال ایمیل، Alert قطعی، Risk score، تخلف یا تغییر Workflow نیست. هر Rule باید صریح، Version-controlled و UAT شود.

## ۶. Export و Outlook
Bundle شامل `report.html`، `email-body.html`، `report.xlsx`، `evidence.json`، `process-analysis.json`، `outlook-draft.eml` و `manifest.json` است. `X-Unsent: 1` و نبود SMTP/Send باید حفظ شود. فرستادن نهایی کار انسانی است.

## ۷. انتشار روی Share
وجود `.paused` در مقصد یا `GSI_AUTOMATION_DISABLED=1` انتشار را متوقف می‌کند. ناشر با `.gsi-publish.lock` قفل می‌گیرد، ابتدا staging می‌سازد، Hashها را Verify می‌کند و سپس rename می‌کند. خروجی موجود فقط در صورت صحت کامل reuse می‌شود؛ overwrite فایل تغییرکرده انجام نمی‌شود.

اگر بعد از قطع برق lock باقی ماند، آن را خودکار نشکنید. مسئول محیط ابتدا باید مطمئن شود ناشر فعال دیگری وجود ندارد، سپس lock/staging باقی‌مانده را مدیریت کند.

## ۸. کنترل نهایی قبل از بهره‌برداری
روی Windows/SMB/Outlook واقعی سازمان: یک Refresh موفق، تطبیق Case/Route با Source، بازشدن HTML، بررسی RTL و IRANSansWeb محیطی، بازشدن Draft در Outlook، آزمون دو Publisher هم‌زمان، قطع Share، Permission Denied و Hash tampering اجرا شود.

تا زمانی که این Acceptance روی داده و شبکه واقعی انجام نشده، `production_certified=false` باقی می‌ماند.
