# اتصال GSI به AnythingLLM — V29.1

معماری اتصال **Sidecar** است: AnythingLLM مستقل اجرا می‌شود و GSI فقط از Developer API و Embed Widget آن استفاده می‌کند. به این ترتیب ارتقای AnythingLLM، Streamlit یا DWH کمترین coupling را دارد.

## تنظیمات محیطی

```powershell
$env:ANYTHINGLLM_BASE_URL="http://localhost:3001"
$env:ANYTHINGLLM_API_KEY="YOUR_SERVER_API_KEY"
$env:ANYTHINGLLM_WORKSPACE_SLUG="gsi-academy"
$env:ANYTHINGLLM_EMBED_ID="YOUR_PUBLIC_EMBED_ID"
```

- `API_KEY` فقط در سمت Streamlit استفاده می‌شود و هرگز وارد HTML نمی‌شود.
- HTML فقط `EMBED_ID` و Base URL عمومی را دریافت می‌کند.
- اگر Embed تنظیم نشده باشد، آموزش هفتگی همچنان داخل HTML دیده می‌شود ولی Q&A آنلاین غیرفعال است.

## Streamlit

از Sidebar وارد `آکادمی هوشمند` شوید. این بخش شامل:

1. وضعیت اتصال API و Embed
2. تست اتصال AnythingLLM
3. نمایش و انتخاب آموزش هفتگی
4. پرسش از همان آموزش با context محدودشده به محتوای درس
5. نمایش source citations بازگشتی AnythingLLM، در صورت وجود
6. ویرایش و ذخیره `config/weekly_lessons.json`

## HTML

در Report Studio گزینه `آموزش هفتگی + Q&A` اضافه شده است. در هر خروجی HTML:

- عنوان، خلاصه و متن درس جاری درج می‌شود.
- سؤال‌های پیشنهادی نمایش داده می‌شوند.
- در صورت وجود Embed ID، widget رسمی AnythingLLM بارگذاری می‌شود.
- هیچ API key یا secret داخل HTML serialize نمی‌شود.

## فایل‌های اصلی

- `gsi/learning/anythingllm.py` — API client سمت سرور
- `gsi/learning/weekly.py` — lesson store سبک
- `app/learning_view.py` — آکادمی داخل Streamlit
- `gsi/studio_core/html_export.py` — بخش آموزشی + Embed در HTML
- `config/weekly_lessons.json` — محتوای هفتگی

## اصل امنیتی

برای HTML از Developer API مستقیم در مرورگر استفاده نمی‌شود، چون نیازمند API Key است و secret را افشا می‌کند. Q&A داخل HTML فقط از Public Embed رسمی AnythingLLM استفاده می‌کند.


## قرارداد نسخهٔ ادغام‌شده

`AnythingLLMClient.ask()` پاسخ خام API را برمی‌گرداند. برای مصرف سمت سرورِ پاسخ دارای منبع، `ask_evidence()` اضافه شده است: حالت query درخواست می‌شود و اگر فرادادهٔ منبع وجود نداشته باشد متن تولیدشده نمایش داده نمی‌شود. خروجی دارای منبع نیز `verified=False` دارد؛ منبع داشتن اثبات صحت مالی یا معنایی نیست.

این helper به ویجت عمومی AnythingLLM تزریق نشده و تنظیمات ویجت را کنترل نمی‌کند. مسیر فعلی Knowledge Desk داخلی، بازیابی و استخراج متن/دادهٔ منتشرشده است. در این تحویل اتصال زنده به یک Workspace واقعی یا مدل بیرونی آزموده نشده است.
