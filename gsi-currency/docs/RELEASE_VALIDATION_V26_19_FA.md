# اعتبارسنجی Release — GSI / AIBL V26.19

**نسخه:** `26.19.0`  
**تاریخ:** 2026-09-17

## نتیجه

نسخه V26.19 انتقال دانش فایل‌های قدیمی را به یک لایه کدنویسی‌شده، versioned و قابل ممیزی تبدیل کرده است. منابع قدیمی به‌عنوان دانش تاریخی/عملیاتی نگهداری می‌شوند و به‌طور پیش‌فرض هیچ Rule لازم‌الاجرای جاری تولید نمی‌کنند.

## کنترل‌های انجام‌شده

- 19 مجموعه تست ثبت‌شده؛ مجموع **502 تست موفق / 0 ناموفق**.
- تست اختصاصی V26.19: **16/16 موفق**.
- RuleBook Validator: **0 خطای ساختاری**.
- 19 Rule جاری همچنان `needs_verification` هستند؛ این عدد مستقل از Legacy Knowledge Pack است.
- Manifest پس از تغییرات بازتولید شد: **102 فایل هسته**.
- AIBL Doctor: **0 خطا / 8 هشدار**.
- گراف فرآیند: **14 Stage** و Stage جدید `legacy_knowledge_transfer` در محل صحیح بین `money_flow_control` و `narrate` قرار دارد.

## هشدارهای باقی‌مانده

هشدارهای Doctor ناشی از خرابی کد نیستند:

- `jdatetime` اختیاری نصب نیست؛ مبدل شمسی داخلی فعال است.
- 19 Rule جاری نیازمند تطبیق رسمی با آخرین بخشنامه‌اند و عمداً Fail-Closed باقی مانده‌اند.
- شش Share داخلی `\\ikco.com\\...` از محیط فعلی قابل دسترس نیستند؛ Reconciliation با داده Production باید داخل شبکه سازمان انجام شود.

## کنترل انتقال دانش

- Historical A/B/C deadlines → فقط Historical Rule، نه Deadline لازم‌الاجرا.
- Payment without BL → `UNALLOCATED_PAYMENT_CANDIDATE`، نه BL مصنوعی.
- Legacy FIFO → الگوریتم کاندید؛ Allocation Edge مستند اولویت دارد.
- نرخ ثابت تاریخی → صرفاً reference/normalization؛ ممنوع برای Real P&L.
- Cross-currency → P&L فقط با شواهد کافی؛ در غیر این صورت Evidence Gap.
- Root Causeهای قدیمی → Candidate + Evidence Requirement؛ نه حکم قطعی تخلف/تقلب.
- Provenance/Source/Confidence در UI و گزارش قابل مشاهده است.

## جمع‌بندی

Release از نظر ساختار پکیج، RuleBook، Manifest، Stage Graph و تست‌های ثبت‌شده سالم است. تنها کار باقی‌مانده برای بهره‌برداری سازمانی، اجرای داده زنده و تطبیق Ruleهای جاری در شبکه داخلی است.
