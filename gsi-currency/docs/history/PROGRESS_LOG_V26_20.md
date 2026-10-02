# GSI V26.20 — Progress Log

**Product:** GSI | Global Sourcing Intelligence  
**Theme:** Data • Process • Decision  
**Reference date:** 2026-09-17  
**Release:** 26.20.0

این فایل فقط وضعیت انجام‌شده در Workspace را ثبت می‌کند؛ طراحی یا برنامه‌ی انجام‌نشده با علامت Complete گزارش نمی‌شود.

## 1) Baseline & architecture — COMPLETE
- V26.19 به‌عنوان baseline تثبیت شد.
- نام پکیج اجرایی از `aibl` به `gsi` منتقل شد؛ CLI مرجع `python -m gsi` است.
- Contract checking، Manifest و Doctor برای نام جدید فعال‌اند.

## 2) Supply Position / inventory truth model — COMPLETE
- سه سبد `نزد سازنده / در راه / گمرک` از سورس کارشناسان به‌عنوان ورودی کمی اصلی Supply Position تعریف شدند.
- Oracle فقط موجودی IKCO/SAPCO و نیاز روزانه را اضافه می‌کند؛ هیچ‌کدام دیگری را overwrite نمی‌کنند.
- Grain موجودی کارشناسی: `ORDER × MATERIAL`.
- `UNKNOWN != ZERO`: مقدار خالی هیچ‌گاه به صفر تبدیل نمی‌شود.
- `SUPPLY_TOTAL_CONFIRMED` فقط با وجود هر پنج جزء محاسبه می‌شود.
- در داده ناقص، `SUPPLY_TOTAL_LOWER_BOUND` + Coverage + Evidence Gap گزارش می‌شود.
- Snapshot تکراری یک موجودی دوباره جمع نمی‌شود؛ تعارض چند مقدار ثبت می‌شود.

## 3) Allocation Queue Request Ledger — COMPLETE
- NTSW Allocation از جمع ساده ردیف‌ها به Request-level Ledger تبدیل شد.
- Snapshot/status history یک درخواست دوباره‌شماری نمی‌شود.
- تفکیک: Allocated / Open Queue / Rejected.
- `PARTIAL_ALLOCATED` وقتی یک tranche تخصیص گرفته ولی tranche دیگری هنوز در صف است.
- Queue Rank فقط در صورت وجود در export گزارش می‌شود؛ مقدار ساختگی تولید نمی‌شود.

## 4) Money Flow lifecycle — COMPLETE
Timeline پرونده اکنون مرحله‌های زیر را مستقل نگه می‌دارد:
1. Registration / Order
2. Allocation Queue
3. Allocation
4. FX Purchase
5. Funding
6. SWIFT / Currency Conversion
7. Shipment
8. Customs Entry
9. Physical Clearance
10. Bank Customs-Document Presentation/Matching
11. Settlement / Release of Commitment

- Physical Clearance با ارائه/تطبیق سند ترخیص نزد بانک یکی نیست.
- SATA/Cotage جایگزین خودکار تاریخ ارائه سند به بانک نمی‌شود.
- FX P&L فقط با نرخ‌ها/مبالغ قابل مقایسه و evidence کافی محاسبه می‌شود.
- Cross-currency بدون Cross Rate/fee/evidence به‌جای سود/زیان ساختگی، Evidence Gap می‌دهد.

## 5) Case Action Queue & email — COMPLETE
- Rule pack `case_actions.yaml` اضافه شد.
- برای پرونده‌ها Action پیشنهادی با Priority، Owner، Due، Rationale، Evidence Gap و Rule Basis ساخته می‌شود.
- Action پیش‌فرض `PENDING_REVIEW` و `HUMAN_REVIEW_REQUIRED=True` است.
- در Process View با انتخاب REG پیشنهادها دیده می‌شوند.
- دکمه Outlook فقط Draft را باز می‌کند؛ ارسال خودکار پیش‌فرض خاموش است.
- Reallocation بدون مجوز `Investigation Signal` است، نه Fraud Finding.

## 6) Regulatory / operational source verification — COMPLETE WITH FAIL-CLOSED ITEMS
- تفکیک تعهد «ارائه سند ترخیص مطابق» از «مابه‌التفاوت نرخ ارز» در مقررات جاری لحاظ شد.
- مسیر مستقیم/غیرمستقیم تأمین ارز به‌عنوان attribute پرونده نگه داشته می‌شود.
- SATA waiver فقط در صورت احراز شرایط و evidence قابل استفاده است؛ نبود SATA به‌تنهایی تخلف نیست.
- Emergency deadline overlays به‌صورت conditional هستند؛ blanket extension اعمال نمی‌شود.
- Bale `ntsw_ir` منبع Operational high-priority است؛ تبدیل یک اطلاعیه به Binding Rule نیازمند اصل ابلاغ/تاریخ اثر است.
- Telegram/Bale غیررسمی یا آموزشی Field Intelligence هستند و به‌تنهایی Rule الزام‌آور نمی‌سازند.
- 19 Rule موجود همچنان `needs_verification` و Fail-Closed هستند.

## 7) GSI visual/product identity — COMPLETE
- Package/CLI: `gsi`.
- Header: `GSI | Global Sourcing Intelligence`.
- Visual semantics: Navy=Data/Trust، Teal=Process/Flow، Gold=Decision.
- Studio sidebar: `▦ Data • ⛓ Process • ◉ Decision`.
- فایل‌های خروجی و subjectهای جاری با GSI نام‌گذاری می‌شوند.
- Aliasهای محیطی قدیمی فقط برای migration compatibility باقی مانده‌اند.

## 8) Regression & release controls — COMPLETE
- 20 test suites به‌صورت مستقل اجرا شدند: **517 passed / 0 failed**.
- `python -m gsi.factsheet`: version 26.20.0، 12 rule packs، 16 pipeline stages، 20 test files.
- `python -m gsi.rulebook.validate`: **0 structural errors**، 19 items نیازمند verification.
- Manifest بازتولید شد: **105 tracked files**.
- `python -m gsi.doctor`: **0 errors / 8 warnings**.
- Warningها: 6 network shares غیرقابل‌دسترسی از محیط فعلی، `jdatetime` اختیاری، 19 rule نیازمند verification.

## Release readiness
**READY FOR CONTROLLED PILOT / UAT.**  
Production certainty for inventory and case lifecycle depends on actual corporate exports/network shares. Missing production evidence must surface as UNKNOWN/Evidence Gap, not zero or inferred completion.
