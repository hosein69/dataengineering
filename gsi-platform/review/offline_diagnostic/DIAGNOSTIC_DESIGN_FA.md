# طراحی Offline Diagnostic GSI — 2026-09-24

## هدف

این بسته برای یک چرخهٔ «اجرا در محیط واقعی → ارسال فقط feedback → اصلاح مستقیم» ساخته شده است. اینترنت در زمان اجرا لازم نیست و دادهٔ خام در feedback کپی نمی‌شود.

## لایه‌های تست

1. **Frozen independent suite — 173 scenario**: همان ممیزی مستقل که بدون استفاده از expected outputهای قدیمی ساخته شد؛ IA01..IA17.
2. **Extended diagnostic suite — 77 scenario**: قرارداد هویت کاربر، near-miss headerها، incomplete composite، NTSW بدون Material، metamorphic row-order/currency/REG isolation، nonfinite/unknown و lineage.
3. **Internal regression — تمام فایل‌های test پروژه**: file-by-file تا state leak یا hang یک فایل مانع پوشش بقیه نشود.
4. **Source inventory**: مسیر، sheet/header، اندازه/hash و schema drift بدون کپی ردیف خام.
5. **NTSW semantic probe**: اگر NTSW قابل دسترس باشد، آمار REG_FILE/REG/ORDER و cardinality به شکل aggregate ثبت می‌شود.
6. **Knowledge integrity**: hash تمام اسناد دانش آفلاین و provenance قواعد test oracle کنترل می‌شود.

## Baseline فعلی روی آخرین پکیج قبل از اصلاح 17 خانواده

- Frozen independent: 130 PASS / 43 FAIL.
- Extended diagnostic: 44 PASS / 33 FAIL.
- Failureهای frozen همگی به IA01..IA17 map می‌شوند؛ failure ناشناخته در آن suite وجود ندارد.
- Knowledge manifest سالم است.

این اعداد «قبولی» نیستند؛ baseline تشخیصی‌اند تا اجرای سیستم واقعی با همان taxonomy قابل مقایسه باشد.

## Contract فیدبک

کاربر فقط `GSI_FEEDBACK_*.zip` را برمی‌گرداند. فایل شامل log/JUnit/test_results، source schema inventory، aggregate NTSW probe، environment، manifest verification و failure taxonomy است. داده خام سازمانی کپی نمی‌شود.
