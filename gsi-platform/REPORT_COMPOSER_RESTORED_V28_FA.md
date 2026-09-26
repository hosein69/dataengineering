# GSI V28 — بازگردانی Report Composer

این نسخه قابلیت‌های حذف‌شده‌ی Studio را روی معماری Process-first بازمی‌گرداند.

## Composer هر تب
هر تب خروجی مستقل می‌تواند Blockهای زیر را داشته باشد یا نداشته باشد و ترتیب آن‌ها نیز مستقل است:
- KPI
- نمودارها
- Process / Process Mining
- Kanban / Scrum Action Board
- جدول تفصیلی

با `streamlit-sortables==0.3.1` ترتیب Blockها Drag & Drop است. در نبود این dependency، ترتیب انتخاب‌شده به‌عنوان fallback حفظ می‌شود.

## Header
Header HTML و Email مستقل‌اند. سه preset اولیه وجود دارد: Figma Aqua، Executive Navy و Minimal. عنوان و زیرعنوان قابل ویرایش‌اند و همراه Design ذخیره می‌شوند.

## Persona
Persona از Template جدا شده است: Expert / Manager / Executive / Analyst. بنابراین مثلاً گزارش Process می‌تواند برای Manager ساخته شود. نام فایل persona را در انتها دارد تا artifactهای نقش‌های مختلف روی هم overwrite نشوند.

## Process و Kanban در HTML
Process Summary و Kanban/Scrum Action Board اکنون first-class blockهای HTML هستند. Kanban فقط از `case_actions` واقعی ساخته می‌شود؛ velocity/burndown ساختگی تولید نمی‌شود.

## Criticality contract
طبقه بحرانی اصلی بر اساس `(STOCK_IKCO + STOCK_SAPCO) / DAILY_NEED` است. Supplier / Transit / Customs برای دید کل زنجیره و مقاومت‌های تکمیلی‌اند و Missing آن‌ها Criticality اصلی را UNKNOWN نمی‌کند.

## Validation
- Targeted regression: 14/14 PASS
- Independent release suite: 47/47 PASS
- تست‌های وابسته به share واقعی IKCO در محیط build قابل اجرا نیستند.
- fixtureهای قدیمی `res/df` در برخی تست‌های legacy مستقل از این release باقی مانده‌اند.
