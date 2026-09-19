# AIBL V26.16.0 — Production Hardening & Decision Governance

این نسخه بر اساس بازبینی معماری، UX و نیاز مدیریتی سخت‌سازی شده است.

## تغییرات کلیدی

- **Semantic Metric Registry**: نوع سنجه دیگر از یکتایی/بزرگی مقدار عددی حدس زده نمی‌شود. مبالغ، نسبت‌ها و شناسه‌ها قرارداد معنایی صریح دارند.
- **Grain-safe commitment charts**: نمودار تعهد Excel نیز از `safe_agg` استفاده می‌کند و دوباره‌شماری سطح ثبت سفارش حذف شده است.
- **Artifact access scope**: محدودیت اداره/کارشناس و حذف فیلدهای حساس پیش از ساخت HTML/Excel اعمال می‌شود؛ فیلتر مرورگر دیگر به‌عنوان کنترل دسترسی تلقی نمی‌شود.
- **HTML template fidelity**: گزینه‌های `visuals` و `tables` واقعاً روی HTML اثر می‌گذارند و Process Explorer فقط در قالب‌های فرآیندی مرتبط نمایش داده می‌شود.
- **Filter-aware Process Explorer**: در صورت وجود Event Log و CASE_KEY، گلوگاه‌های فرآیند بر اساس برش فعال مرورگر دوباره محاسبه می‌شوند.
- **Narrative consistency**: بزرگ‌ترین گلوگاه همیشه بعد از sort شدن انتخاب می‌شود.
- **HTML lifecycle fix**: اسکریپت تکراری و listenerهای دوبل حذف شده‌اند؛ render lifecycle واحد شده است.
- **HTML payload guard**: حجم داده جاسازی‌شده با سقف cell کنترل می‌شود و در صورت truncate شدن، پیام شفاف به کاربر نشان داده می‌شود؛ Excel رسمی مرجع جزئیات کامل باقی می‌ماند.
- **Excel labeling**: خروجی مرورگر با عنوان «استخراج داده فیلترشده (Excel)» از گزارش رسمی Excel تفکیک شده است.
- **Headless analytics import**: توابع محاسباتی Analytics بدون نصب Streamlit نیز قابل import/test هستند؛ فقط render UI نیازمند Streamlit است.
- **Release consistency**: نسخه مرجع به `26.16.0` ارتقا یافته و Manifest دوباره تولید شده است.

## کنترل کیفیت

- تست‌های مستقیم Hardening + HTML + Report Builder + Studio: 12/12 پاس.
- مجموعه Dashboard مستقل: 77/77 پاس.
- مجموعه Supply Views مستقل: 55/55 پاس.
- Runner رسمی 17 فایل تست را ثبت می‌کند. اجرای یک‌باره کل runner در محیط بازبینی به سقف زمانی ابزار رسید؛ suiteهای تغییرخورده جداگانه اجرا و سبز شده‌اند.
