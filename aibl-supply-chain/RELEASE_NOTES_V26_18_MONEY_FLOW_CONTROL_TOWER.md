# AIBL / GSI V26.18 — Money Flow Control Tower

## هدف
شفاف‌سازی End-to-End جریان پول در سطح ثبت سفارش و پیوند آن با Order/BL، نرخ خرید ارز، ارز پرداختی به تأمین‌کننده، تبدیل ارز، Deadline و رفع تعهد.

## قابلیت‌های جدید
- Stepper نه‌مرحله‌ای: ثبت سفارش، تخصیص، خرید ارز، تأمین وجه، سوئیفت/تبدیل، حمل، ورود/EPL، ترخیص، رفع تعهد.
- سه آمپر پرونده‌ای: ریسک کنترل پول، پیشرفت مراحل، پوشش Evidence.
- نزدیک‌ترین Deadline با تاریخ، روز باقی‌مانده، مبنا و سطح اعتبار Rule.
- `fx_rate_bridge`: تفکیک ارز خریداری‌شده از ارز پرداخت‌شده و محاسبه اثر ریالی تبدیل فقط در صورت وجود شواهد کافی.
- `fx_reallocations`: کشف جابه‌جایی صریح یا مغایرت REG ↔ Order/BL و تفکیک `AUTHORIZED` از `UNEXPLAINED`.
- `fx_stage_timeline`: وضعیت هر مرحله (`DONE / CURRENT / WARNING / OVERDUE / EVIDENCE_GAP / PENDING`).
- `fx_control_summary`: امتیاز ریسک ۰ تا ۱۰۰ و وضعیت پرونده برای داشبورد/HTML/Excel.
- حفظ ردیف‌های خام Allocation در `ntsw/allocation_rows` برای ممیزی تاریخچه تخصیص.
- پشتیبانی اختیاری از فیلدهای پرداخت به ذی‌نفع، Cross Rate، کارمزد تبدیل و مجوز جابه‌جایی در فایل Foreign Exchange Transaction.
- Registry منابع Field Intelligence شامل پنج کانال/گروه معرفی‌شده پروژه با سیاست «Signal ≠ Binding Rule».

## اصول کنترلی
- خرید ارز ≠ تأمین وجه ≠ SWIFT ≠ دریافت وجه توسط تأمین‌کننده.
- Cross-Currency بدون شاهد نرخ/مبلغ، `EVIDENCE_GAP` است و P&L ساختگی تولید نمی‌شود.
- جابه‌جایی بین پرونده‌ها بدون `AUTH_REF` فقط Investigation Signal است؛ سیستم تقلب را قطعی اعلام نمی‌کند.
- Deadlineهای NTSW بر SLA داخلی اولویت دارند؛ SLA داخلی با برچسب `internal` نمایش داده می‌شود.
- Deadline رسوب ۴۵ روزه صرفاً Operational SLA است و جایگزین مهلت قانونی ماده ۲۴ نیست.

## خروجی‌ها
- Streamlit Process View: Money Flow Control Tower در ابتدای تب فرآیند.
- Excel Dashboard: شیت FX با Stage/Risk/Deadline/Conversion/Reallocation و جداول تفصیلی.
- Report Builder: چهار جدول جدید «برج کنترل پول»، «مراحل جریان پول»، «پل نرخ و تبدیل ارز»، «جابجایی بین پرونده‌ها».
- HTML Process Explorer: KPIهای ریسک جریان پول و جدول پرونده‌های پرریسک.

## تست اختصاصی
`tests/test_money_flow_v26_18.py` سناریوی EUR→CNY، محاسبه اثر ریالی، Reallocation بدون/با مجوز، Deadline NTSW و Registry منابع میدانی را پوشش می‌دهد.


## وضعیت Release
- نسخه: `26.18.0`
- تست Release: **486 موفق / 0 ناموفق** در **18 مجموعه**.
- RuleBook: 10 بسته فعال + manifest؛ قواعد `needs_verification` عمداً auto-enforce نمی‌شوند.
- `aibl doctor`: خطای ساختاری صفر؛ هشدارهای محیطی شامل Shareهای داخلی خارج از دسترس این محیط و قواعد نیازمند تطبیق رسمی است.
