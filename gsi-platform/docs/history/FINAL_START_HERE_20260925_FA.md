# GSI — بسته نهایی ۲۰۲۶-۰۹-۲۵

این نسخه ادامه مستقیم GSI 29.8.2 RC4-OPT2 H1 است؛ معماری مالی/داده‌ای تثبیت‌شده بازنویسی نشده است. افزونه Process Intelligence به سه View تثبیت‌شده رسیده و ایده‌های مناسب `clips/pattern` به‌صورت مستقل، محدود و قابل ممیزی وارد شده‌اند.

## شروع سریع
- اجرای روزانه: `START_GSI.cmd`
- Refresh صریح: `REFRESH_GSI_DATA.cmd`
- Excel Published Snapshot: `EXPORT_GSI_EXCEL.cmd`
- گزارش Process از CSV: `python -m gsi.process_intelligence --events <csv> --reference <date> --publish-root <folder>`
- Pattern اختیاری: همان فرمان + `--pattern-config config\process_patterns.example.json`

## تغییرات اصلی این Build
- سه View یکپارچه: وضعیت و اقدام / مسیر فرآیند / تحویل بین واحدها.
- Unique Case و Occurrence جدا؛ Median/P90 فاصله Eventها به Route اضافه شد.
- Handoff فقط از from_team/to_team صریح؛ Missing به Zero تبدیل نمی‌شود.
- Event Pattern Engine مستقل با wildcard/optional/repetition/taxonomy/capture و source-row lineage؛ به‌صورت پیش‌فرض خاموش و observational-only.
- خروجی جدید `process-analysis.json`.
- Excel/HTML با همان Facts و با محافظت Formula Injection/HTML escaping.
- Design tokens با Figma زنده ۲۰۲۶-۰۹-۲۵ همگام و IRANSansWeb فونت طراحی است.
- هیچ فایل فونت باینری در این بسته توزیع نمی‌شود.
- هیچ Send خودکار، Cloud SDK جدید یا dependency روی `clips/pattern` اضافه نشده است.

## تصمیم درباره clips/pattern
مخزن upstream در README فعلی archived/unmaintained اعلام شده است. بنابراین dependency مستقیم رد شد؛ فقط ایده‌های `pattern.search` برای sequence constraint/taxonomy/capture با پیاده‌سازی کوچک مستقل اقتباس شدند. جزئیات: `PATTERN_INTEGRATION_DECISIONS_FA.md`.

## مرز پذیرش
Gateهای Build و Regression این ZIP در `FINAL_RELEASE_GATE_20260925.json` ثبت می‌شوند. Certification عملیاتی همچنان به اولین Refresh/Publish موفق روی Windows، Sourceهای واقعی، SMB و Outlook سازمان وابسته است.

## نقشه‌ها و مدل مهندسی
سه افزونه درخواستی روی همین Build اعمال شده‌اند: Diagram Maker برای معماری، Flowchart Maker برای Swimlane و EW AI Flowchart برای مدل EFD 2.1. فایل شروع تصویری `design/diagrams/GSI_FINAL_DIAGRAMS.html` است. مدل ماشین‌خوان در `design/efd/GSI_FINAL_OPERATING_MODEL.efd.json` قرار دارد و validation آن صفر خطای ساختاری دارد؛ نام رسمی واحد/عنوان مسئول انسانی عمداً pending مانده است تا در استقرار سازمانی تأیید شود.
