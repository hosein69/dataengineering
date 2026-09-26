# GSI — Process Intelligence آفلاین، راهنمای شروع نهایی

این افزونه روی GSI 29.8.2 موجود سوار می‌شود و موتور مالی، authority، DWH و refresh تثبیت‌شده را جایگزین نمی‌کند. سه View عملیاتی از یک Scope و Reference Time ساخته می‌شوند: «وضعیت و اقدام»، «مسیر فرآیند» و «تحویل بین واحدها».

## منابعی که واقعاً در این تحویل استفاده شدند
- Figma زنده: سه فایل GSI خوانده و Foundations (`T9Ps72EYpriHdov9fmNFQu`, node `3:2`) به‌عنوان Design Source of Truth تأیید شد.
- OrderFlow و Organizational Knowledge Flow: تصمیم‌های قبلی درباره transition timing، unique case/occurrence، handoff، missing data و عدم auto-send حفظ شده‌اند.
- `clips/pattern`: commit `af754685cca3713db0abc4f020f2e94467c19d85` بررسی شد. چون upstream archived/unmaintained است، dependency مستقیم اضافه نشد؛ فقط ایده‌های constraint/taxonomy/capture در matcher مستقل GSI اقتباس شد.
- Process Documentation plugin: برای Runbook بهره گرفته شد و خروجی آن با قرارداد fail-closed GSI اصلاح شد.

## خروجی Process Bundle
- `report.html` — RTL و SVG، بدون JavaScript/منبع اینترنتی و بدون font binary.
- `email-body.html` — Table-based برای Outlook؛ بدون SVG/Send.
- `report.xlsx` — KPI، Route، Stage، وضعیت و اقدام، Handoff و در صورت فعال بودن Pattern؛ متن ورودی Formula نمی‌شود.
- `evidence.json` — Evidence کامل با source row.
- `process-analysis.json` — سه View و تحلیل Route/Handoff/Pattern بدون payload مالی جدید.
- `outlook-draft.eml` — `X-Unsent: 1`، بدون ارسال خودکار.
- `manifest.json` — Task ID و SHA-256 هر Artifact.

## CLI
```bat
python -m gsi.process_intelligence --events C:\GSI_INPUT\events.csv --reference 2026-09-25 --publish-root "\\SERVER\Share\GSI_REPORTS"
```

Pattern صریح اختیاری:
```bat
python -m gsi.process_intelligence --events C:\GSI_INPUT\events.csv --reference 2026-09-25 --publish-root "\\SERVER\Share\GSI_REPORTS" --pattern-config config\process_patterns.example.json
```

ستون‌های پایه: `_CASE_KEY` یا `CASE_KEY`، `ACTIVITY_FA`، `EVENTTIME`. Event هم‌زمان در یک Case باید `_SORTING` معتبر و متمایز داشته باشد. Handoff فقط وقتی محاسبه می‌شود که `FROM_TEAM` و `TO_TEAM` صریح وجود داشته باشند؛ زمان‌ها و سندها اختیاری‌اند و نبودشان صفر نیست.

## فیوزها
`GSI_AUTOMATION_DISABLED=1` ساخت/انتشار را می‌بندد. فایل `.paused` در مقصد Share انتشار را می‌بندد. Publication با lock + staging + hash verification انجام می‌شود و Artifact تغییرکرده overwrite نمی‌شود.

## فونت
Figma زنده در تمام صفحات بررسی‌شده IRANSansWeb دارد. کد نیز آن را اولویت می‌دهد، اما **این ZIP هیچ فایل font binary توزیع نمی‌کند**. سازمان باید IRANSansWeb دارای مجوز را روی سیستم نصب/تأمین کند.

## وضعیت پذیرش
Build و Regression این نسخه در `FINAL_RELEASE_GATE_20260925.json` ثبت می‌شود. Outlook/SMB/Windows real-source acceptance هنوز باید در محیط سازمان اجرا شود؛ تا آن زمان `production_certified=false` است.
