# اصلاح جستجوی متریال — V29.5.0

- کد متریال یک شناسه TEXT است، نه عدد.
- جستجوی کد متریال از BL/Base mart مستقل شد.
- از تمام ردیف‌های `moghavemat/lines` یک mart مستقل `material_evidence` ساخته می‌شود.
- کلید جستجو `MATERIAL_SEARCH_KEY = clean_part_no(KEY_MATERIAL)` است.
- Match کد متریال exact است؛ اختلاف شرح، PR، PR Item یا Order هیچ ردیفی را حذف نمی‌کند.
- این mart فقط Evidence/Search است و در KPIها تزریق نمی‌شود.
- در نمای «متریال محور» نتایج source-grain جستجو مستقیماً نمایش داده می‌شوند.

Regression case: Material `9654003280` با Row No. 57،124،168،169،170 همگی بازیابی شدند، با وجود تفاوت شرح و PR.
