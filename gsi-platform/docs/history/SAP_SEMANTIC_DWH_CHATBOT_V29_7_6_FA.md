# V29.7.6 — SAP Semantic DWH + Smart Chatbot

## اصلاح معماری SAP
- `raw_rows`: هر ردیف استانداردشده فایل SAP برای lineage/replay.
- `pr_items`: Grain = PR × Item؛ از تکثیر Quantity/Value به‌علت چند PO جلوگیری می‌کند.
- `workflow_rows`: تاریخچه Workflow/Package بدون حذف وضعیت‌های میانی.
- `po_items`: Grain = Purchasing Document × Item.
- `main`: فقط projection سازگار با UI قدیمی در سطح PR.

## تاریخ‌ها
Excel serial، تاریخ شمسی و YYYYMMDD همزمان پذیرفته می‌شوند. مقدار خام حفظ و ستون ISO تحلیلی ساخته می‌شود.

## Business DWH
- `PO` به Entityهای DWH اضافه شد.
- Factهای مستقل `dwh_fact_sap_pr_item`, `dwh_fact_sap_po_item`, `dwh_fact_sap_workflow` اضافه شدند.
- Relationهای SAP فقط از `raw_rows` ساخته می‌شوند؛ semantic frame مشتق Evidence جدید تولید نمی‌کند.
- قرارداد legacy که PR Item ندارد همچنان قابل استفاده است و Item ساختگی تولید نمی‌شود.

## Chatbot
- سؤال‌های دارای شناسه PR/PO/REG/MATERIAL از Published Business DWH و روابط مستقیم پاسخ داده می‌شوند.
- پاسخ عملیاتی `as-of run` و Source را اعلام می‌کند.
- نبود Evidence به معنی انجام‌نشدن قطعی مرحله تفسیر نمی‌شود.
- سؤال‌های رویه‌ای/دانشی همچنان از Knowledge Base مستند پاسخ می‌گیرند.
- Static chatbot هنگام publish یک snapshot فشرده از PRهای DWH را نیز index می‌کند.

## UI
تمام `use_container_width`ها به API جدید `width="stretch/content"` مهاجرت کردند.

## اعتبارسنجی
- SAP + Process + DWH + Cash Flow + Authority + Knowledge Desk: 41 تست منتخب پاس.
- Validation Pipeline مستقل: 6/6 پاس.
- Architecture event-log مستقل: پاس.
- Doctor: 0 خطا، 11 هشدار محیطی/قانونی.
- تست Streamlit UI در محیط ساخت به‌دلیل نصب نبودن Streamlit اجرا نشد.
