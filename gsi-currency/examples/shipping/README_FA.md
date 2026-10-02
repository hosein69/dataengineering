# قالب مرحلهٔ بعد برای رویدادهای حمل

این CSV نمونهٔ **ستون‌ها** است و هیچ ردیف یا تاریخ ساختگی ندارد. در نسخهٔ
29.15.8 به‌طور خودکار وارد محاسبه نمی‌شود؛ پیش از اتصال رسمی باید با
مالک داده و اسناد واقعی تطبیق شود.

- `BL_NO` شماره بارنامهٔ مستند، `CONTAINER_NO` شماره کانتینر (در صورت وجود).
- `EVENT_CODE`: `CARGO_READY`, `BOOKING_CONFIRMED`, `GATE_IN`, `HUB_ARRIVED`,
  `HUB_DEPARTED`, `BL_SWITCH_REQUESTED`, `BL_SWITCH_COMPLETED`, `ETA_PUBLISHED`,
  `ARRIVAL_NOTICE`, `DO_REQUESTED`, `DO_PAYMENT_CONFIRMED`, `DO_ISSUED`,
  `DO_RECEIVED`, `CONTAINER_RETURNED`.
- `EVENT_AT` زمان واقعی رویداد با ناحیهٔ زمانی و مبنای سند؛ `RECORDED_AT`
  زمان ثبت در سازمان. این دو نباید یکی فرض شوند.
- `LOCATION`, `PROVIDER`, `RESPONSIBLE_TEAM` فقط با شاهد ثبت می‌شوند؛
  `EVIDENCE_REF` شناسهٔ سند یا پیام، بدون پیوست حساس در فایل اشتراکی.
- `CONTRACT_REF`, `FREE_TIME_END`, `AMOUNT`, `CURRENCY` فقط برای رویداد و
  قرارداد مربوط. نرخ/مهلت همگانی از این قالب ساخته نمی‌شود.

برای سوئیچ بارنامه، زنجیرهٔ سند اولیه و جایگزین و مجوز/انطباق قانونی باید
در مخزن مجاز و ممیزی‌شده باقی بماند؛ این قالب دستور تغییر سند نیست.
