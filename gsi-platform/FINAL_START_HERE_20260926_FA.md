# شروع سریع — GSI Final Clean Release — 2026-09-26

این بسته بر مبنای `GSI_29_8_2_process_diagram_fix.zip` ساخته شده و قابلیت‌های قبلی را حفظ می‌کند.

## اجرای روزمره
- `START_GSI.cmd` — فقط Snapshot منتشرشده را باز می‌کند؛ ETL خودکار اجرا نمی‌شود.
- `REFRESH_GSI_DATA.cmd` — Refresh صریح داده‌ها.
- `EXPORT_GSI_EXCEL.cmd` — Excel از Snapshot/DWH منتشرشده.

## نمونه‌های HTML
پوشه `samples/release_html/` را باز کنید و `index.html` را اجرا کنید. نمونه‌ها از داده ساختگی و مسیر واقعی گزارش‌سازی GSI تولید شده‌اند و داده واقعی سازمانی ندارند.

## نکات این release
- runtime warehouse/cache/demo داخل ZIP نهایی وجود ندارد.
- Process Explorer با design tokenهای GSI، انتخاب پایدار، zoom قابل کنترل با صفحه‌کلید و chips کیفیت شواهد ارائه می‌شود.
- منطق استخراج adjacency، conformance، KPI و داده‌های کسب‌وکار تغییر نکرده است.
- Excel از `IRANSans Light` استفاده می‌کند؛ HTML همچنان IRANSansWeb-first است.
