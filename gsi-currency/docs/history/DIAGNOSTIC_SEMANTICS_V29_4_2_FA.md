# V29.4.2 — Business-aware Diagnostics

این hotfix خودِ ابزار تشخیص را اصلاح می‌کند، نه داده واقعی را.

## خطاهای تشخیصی اصلاح‌شده
- REG و REG_FILE کاملاً جدا شدند. `IL_FILE_NO` دیگر هرگز وارد universe کد ثبت سفارش نمی‌شود.
- NTSW commitment/allocation ابتدا با REG موجود در Import Licence سنجیده می‌شوند.
- IL Append در تشخیص اصلی با REG_FILE به Import Licence وصل می‌شود.
- SAP با PR بررسی می‌شود؛ نبود BL در SAP دیگر خطا گزارش نمی‌شود.
- فریم inventory مقاومت با grain ترکیبی ORDER+MATERIAL بررسی می‌شود؛ BL برای آن معیار نیست.
- پوشش پایین دیگر خودکار به «فرمت کلید اشتباه» تعبیر نمی‌شود؛ ممکن است پوشش طبیعی یک زیرمجموعه بیزینس باشد.

## KPI diagnostics
- KEY_MATERIAL مقاومت در grain inventory سنجیده می‌شود، نه main سفارش.
- Additional Data در lines سنجیده می‌شود.
- Clearance از نام واقعی `CL_CLEAR_DATE` استفاده می‌کند.
- `FULL_CLEAR_DATE` در derive اکنون `CL_CLEAR_DATE` و `COT_FULL_CLEAR_DATE` را می‌شناسد.
- FX_CB_VALUE دیگر به‌عنوان ستون اجباری FX گزارش نمی‌شود؛ CB_VALUE chain از NTSW_INITIAL_COMMIT و fallbackهای معتبر ساخته می‌شود.
- فیلدهای مستقیم supplier/transit/customs اگر در فایل رسمی وجود نداشته باشند Missing گزارش می‌شوند، نه خطای adapter و نه Zero.

## اصل
تشخیص باید semantics بیزینس را بداند؛ صفر overlap به‌تنهایی اثبات خرابی normalization نیست.
