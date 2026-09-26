# GSI V29.4.6 — Knowledge Desk Self-Index Guard

## علت خطای مشاهده‌شده
پوشه خروجی chatbot به‌عنوان مسیر آموزش/دانش انتخاب شده بود و `chatbot.html` تولیدشده دوباره به‌عنوان Lesson خوانده می‌شد. نتیجه: CSS/HTML در بخش آموزش نمایش داده شد و Build با `documents=0/chunks=0` نیز به اشتباه موفق اعلام شد.

## اصلاحات
- فایل‌های تولیدی `chatbot.html`, `knowledge_index.json`, `weekly_lessons.json`, `manifest.json` هرگز ایندکس یا Lesson نمی‌شوند.
- خروجی نمی‌تواند دقیقاً همان مسیر منبع یا والد منبع باشد. خروجی به‌صورت زیرپوشه منبع مجاز است و از crawl مستثنی می‌شود.
- Build بدون هیچ chunk واقعی با `BLOCKED_EMPTY_KNOWLEDGE` متوقف می‌شود و Success کاذب نمی‌دهد.
- validation مسیر Publish فقط در مرحله Publish/UI الزامی است؛ Index مستقل باقی مانده تا coupling ایجاد نشود.
- رکوردهای self-index قدیمی در build بعدی از ACTIVE خارج می‌شوند.

## تست
Regression test برای self-index، همپوشانی مسیرها، build خالی و publish زیرپوشه منبع اضافه شد.
