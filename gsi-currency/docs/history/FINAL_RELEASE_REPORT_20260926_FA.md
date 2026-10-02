# گزارش تحویل نهایی GSI — 2026-09-26

## مبنا
مبنای این تحویل، بسته `GSI_29_8_2_process_diagram_fix.zip` بود. منطق و قابلیت‌های تثبیت‌شده نسخه قبلی شامل composite grain برای SAP، F031، Early Quality Gate، Snapshot-first UI/email و جداسازی START/REFRESH/EXPORT حفظ شده‌اند.

## ایرادهایی که در بسته ورودی پیدا شد
1. داده runtime داخل release: `D:\GSI_DATA/warehouse.sqlite` و frame-cacheها.
2. `_demo_html_out`، `.pytest_cache` و `__pycache__` داخل ZIP.
3. package hash manifest قدیمی و ناسازگار با محتوای واقعی ZIP.
4. قرارداد فونت Excel از `IRANSans Light` به `IRANSansWeb` تغییر کرده بود و legacy regression واقعی را می‌شکست.

## اصلاح نهایی
- release builder قطعی در `tools/build_clean_release.py` اضافه شد؛ runtime/cache/sqlite/pickle/demo/pycache را هرگز بسته‌بندی نمی‌کند.
- `FONT_EXCEL` به `IRANSans Light` برگشت؛ stack وب دست‌نخورده و IRANSansWeb-first باقی ماند.
- Process Explorer فقط در لایه UX بهتر شد: active selection، evidence-quality chips، keyboard zoom/reset/Escape و disabled-state کنترل zoom. هیچ منطق adjacency، conformance، KPI یا کسب‌وکار تغییر نکرد.
- نمونه‌های HTML از مسیر واقعی Pipeline با داده ساختگی ساخته و در `samples/release_html/` قرار داده شدند.

## نتیجه تست روی bytes استخراج‌شده کاندید
- Compile: PASS
- Independent frozen audit: 173/173 PASS
- Extended audit: 77/77 PASS
- Targeted release regression: 85/85 PASS
- Runtime/cache artifacts داخل package: 0
- Package SHA manifest: missing=0, mismatch=0, extra=0

## نمونه‌های HTML
- `GSI_SAMPLE_EXECUTIVE.html`
- `GSI_SAMPLE_MANAGER.html`
- `GSI_SAMPLE_EXPERT.html`
- `GSI_SAMPLE_ANALYST.html`
- `GSI_SAMPLE_DAILY_EMAIL.html`
- `index.html` برای دسترسی سریع به همه نمونه‌ها

نمونه‌ها حاوی داده واقعی سازمانی نیستند.

## محدودیت صریح
چهار AppTest وابسته به `streamlit.testing` در محیط build قابل اجرا نیستند چون Streamlit نصب نیست؛ برای آن‌ها ادعای PASS نشده است. همچنین قوانین موقت منقضی‌شده به‌صورت خودکار تمدید نشده‌اند و RuleBook طبق governance موجود fail-closed می‌ماند تا منبع رسمی جانشین ارائه شود.
