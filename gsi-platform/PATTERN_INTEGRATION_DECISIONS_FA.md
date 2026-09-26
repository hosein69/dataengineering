# تصمیم ادغام ایده‌های clips/pattern با GSI

تاریخ: ۲۰۲۶-۰۹-۲۵

## منبع بررسی‌شده
مخزن `clips/pattern` روی GitHub و شاخه `master` در commit زیر بررسی شد:

`af754685cca3713db0abc4f020f2e94467c19d85`

README فعلی مخزن صریحاً اعلام می‌کند پروژه دیگر نگهداری نمی‌شود و به‌روزرسانی، رفع باگ یا patch امنیتی دریافت نمی‌کند. نسخه مستندشده Pattern نیز 3.6 و متعلق به نسل قدیمی Python است. بنابراین **خود پکیج Pattern به dependency محصول GSI اضافه نشده است**.

## چه ایده‌ای پذیرفته شد؟
از لایه `pattern.search` این مفاهیم به‌صورت مستقل و کوچک برای GSI بازطراحی شد:

- الگو = دنباله‌ای از constraintهای صریح روی Activityها؛
- alternative و wildcard برای نام Activity؛
- constraint اختیاری و `one_or_more` با رفتار greedy و backtracking محدود؛
- taxonomy صریح و سلسله‌مراتبی برای گروه‌بندی فعالیت‌ها؛
- capture group برای اینکه هر نتیجه دقیقاً بگوید کدام Activity و کدام source row باعث Match شده است؛
- anchor ابتدا/انتها برای قواعدی که باید از مرز Case شروع/تمام شوند.

پیاده‌سازی مستقل در `gsi/process_intelligence/patterns.py` است و هیچ کدی از مخزن upstream کپی نشده است.

## چه چیزهایی عمداً پذیرفته نشد؟
- `pattern` به requirements اضافه نشده است؛ دلیل: archived/unmaintained و ریسک ناسازگاری/امنیت.
- POS tagging، sentiment، WordNet، classifier و سایر NLPهای Pattern برای متن فارسی GSI استفاده نمی‌شوند؛ مدل معتبر فارسی و مجموعه ارزیابی سازمانی نداریم.
- Match به «ریسک»، «تخلف»، «SLA breach» یا «علت» تبدیل نمی‌شود. Match فقط مشاهده قابل ردیابی است.
- هیچ Rule از روی داده خودکار ساخته یا فعال نمی‌شود؛ config باید صریح و قابل ممیزی باشد.
- الگوها هیچ Action یا ایمیلی را خودکار ارسال نمی‌کنند.

## قرارداد ایمنی Matcher
حداکثر ۵۰ الگو، حداکثر ۱۲ constraint برای هر الگو، حداکثر ۱۰۰۰ term در taxonomy و حداکثر ۱۰هزار Match در یک اجرا. taxonomy cyclic، شناسه نامعتبر، config بیش از ۱ MiB یا constraint مبهم fail-closed می‌شود.

هر Match شامل `case_key`، `pattern_id`، Activityهای Match شده، `source_rows` و captureهاست. این lineage برای بازبینی انسانی حفظ می‌شود.

## فعال‌سازی
پیش‌فرض **غیرفعال** است. نمونه فقط برای ساختار config در:

`config/process_patterns.example.json`

CLI:

```bat
python -m gsi.process_intelligence --events C:\GSI_INPUT\events.csv --reference 2026-09-25 --publish-root "\\SERVER\Share\GSI_REPORTS" --pattern-config config\process_patterns.example.json
```

در Streamlit فقط وقتی متغیر `GSI_PROCESS_PATTERN_CONFIG` به فایل JSON معتبر اشاره کند، Matcher فعال می‌شود.

## نسبت با تصمیم‌های قبلی GSI
این قابلیت جایگزین قرارداد Case/Event، Evidence، Quality Gate یا Handoff نیست؛ لایه‌ای مشاهده‌ای روی Eventهای قبلاً اعتبارسنجی‌شده است. Missing همچنان Missing است؛ هیچ مقدار، Activity، Owner یا زمان ساخته نمی‌شود.
