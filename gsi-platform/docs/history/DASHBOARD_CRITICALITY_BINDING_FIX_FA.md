# Dashboard Criticality Binding Fix — V28

مشکل: در برخی DataFrameهای main/warehouse، ستون مقاومت در لایه ارائه از Oracle ترمیم می‌شد اما `کد طبقه بحرانی` و `بحرانی (کوتاه)` همچنان UNKNOWN/نامشخص باقی می‌ماندند. در نتیجه Dashboard مقاومت معتبر داشت ولی بحرانی را نامشخص نشان می‌داد.

اصلاح:
- `ensure_criticality_columns()` پس از repair مقاومت، فقط bandهای خالی/UNKNOWN را با `CriticalityEngine` رسمی دوباره طبقه‌بندی می‌کند.
- band معتبر موجود هرگز overwrite نمی‌شود.
- مقاومت 0 → STOCKOUT؛ زیر 10 → CRITICAL؛ 10 تا زیر 20 → BECOMING_CRITICAL؛ سپس WATCH/SAFE طبق RuleBook.
- نیاز روزانه <= 0 → NO_CONSUMPTION.
- Missing همچنان Zero نیست.
- Dashboard و Process Cockpit هر دو از همین defensive contract استفاده می‌کنند.
- KPI «نیازمند اقدام» = STOCKOUT + CRITICAL + BECOMING_CRITICAL در سطح متریال یکتا.
