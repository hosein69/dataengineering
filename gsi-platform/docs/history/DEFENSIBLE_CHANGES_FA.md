# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# دلایل تغییرات — 29.7.8 RC2

- مرحلهٔ SWIFT در تولید شواهد وجود داشت ولی مصرف‌کننده آن را نمی‌شناخت؛ ثبت مرحله جلوی حذف شاهد را می‌گیرد، بدون اینکه آن را معادل پرداخت کند.
- تبدیل مقدار نامعلوم به صفر در مشتقات قدیمی پنهان بود؛ پرچم‌های نامعلوم و کنترل DEGRADED اضافه شد. مقدار نامعتبر و غیرمتناهی نیز نامعلوم است؛ اصلاح تمام مسیرهای قدیمی ادعا نشده است.
- هنگام خالی‌بودن DWH، گزارش می‌توانست از دادهٔ میانی نامقید ساخته شود یا دامنهٔ نامشخص به همهٔ پرونده‌ها گسترش یابد؛ مسیر پیش‌فرض اکنون اجرای منتشرشده و همان دامنه را حفظ می‌کند.
- خرابی SQLite یا JSON قبلاً می‌توانست شبیه نبود داده دیده شود؛ خطای منبع اکنون جدا و آشکار است.
- شباهت عنوان سفارش و ثبت سفارش می‌توانست اتصال غلط بسازد؛ نام‌های ثبت و پرونده از تشخیص ORDER کنار گذاشته شد.
- تکرار یک شناسه همراه وضعیت متعارض، و تخصیص با تاریخ برابر، قبلاً ممکن بود شاهدی را به ترتیب ردیف انتخاب کند؛ تاریخچه حفظ و تعارض قرنطینه می‌شود.
- محیط مالی ابتدا ورودی و جدول متراکم نشان می‌داد؛ اکنون زمینهٔ منبع و تاریخ، انتخاب پرونده/ارز، جریان، رفع تعهد، شواهد و کیفیت تفکیک شده‌اند. جمع ارزهای متفاوت نمایش داده نمی‌شود.

هر تغییر به کد و تست قابل ردیابی است: review/rc2_validation/ACCEPTED_CHANGES.md، changes_from_rc1.patch و tests/test_final_financial_contracts.py. تغییرات از بازنویسی موتور محاسباتی مستقل‌اند؛ محدودیت‌های قدیمی در KNOWN_LIMITATIONS.md حفظ شده‌اند.
