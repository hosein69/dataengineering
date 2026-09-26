# V29.6.4 — Runtime visibility + material HTML verification

این نسخه برای رفع ابهام «کد جدید واقعاً اجرا شده یا نه» ساخته شده است.

- نسخه `29.6.4` در Sidebar خود Studio دیده می‌شود.
- مسیر واقعی `app/studio.py` در Sidebar دیده می‌شود.
- HTML خروجی در Footer عبارت `Build 29.6.4` دارد.
- `REPORT_META.gsi_build` داخل HTML نیز `29.6.4` است.
- منطق V29.6.3 حفظ شده: اگر `KEY_MATERIAL` در دیتاست گزارش مقدار واقعی داشته باشد، به همه tabهای HTML تزریق می‌شود و برای cardinality بالا فیلتر متنی مستقل دارد.
- فایل `VERIFY_RUNTIME_V29_6_4.cmd` مسیر واقعی ماژول‌های لودشده را چاپ می‌کند تا اجرای نسخه قدیمی/کپی موازی فوراً مشخص شود.

نکته: material evidence که فقط در Commercial Expert evidence وجود دارد و رابطه اثبات‌شده‌ای با Base mart ندارد عمداً به KPI grain تزریق نمی‌شود؛ این اصل V29.5 حفظ شده است.
