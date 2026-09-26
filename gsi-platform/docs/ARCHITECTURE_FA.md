# معماری GSI 29.11.0

این سند نقشه فنی فعلی را از روی کد توصیف می‌کند (نه برنامه آینده). نمودارهای مهندسی
Mermaid/DOT/SVG در `design/diagrams/` هستند.

## ۱) لایه‌ها و جریان داده

```
فایل‌های عملیاتی (شبکه، فقط خواندن)
  │  dataio/reader.py        کشف فایل، شیت قراردادی، fail-closed (بدون fallback به شیت دیگر)
  │  warehouse/excel.py      بایت اصلی + سلول فیزیکی (hidden/formula) → SQLite، content-addressed
  ▼
adapters/  (۱۲ سورس، یکی برای هر سورس)            ← grain بومی، کلیدهای صریح KEY_*
  abbasi(BL) sata(SATA) clearance(CL) cotage(COT) oracle(ORC) ntsw(NTSW)
  fx_transaction(FX) credit(CRD) ilappend(IL) sap(SAP) doccheck(DOC) hr(HR) moghavemat(MOGH)
  │  core/numeric_parse.py   parser عددی واحد (Unknown = None/NaN، هرگز صفر)
  │  core/jalali.py          تقویم شمسی/میلادی/سریال Excel؛ تاریخ نامعتبر رد می‌شود
  │  core/text.py            نرمال‌سازی متن و کلیدها (ارقام، نویسه‌های نامرئی، ی/ک)
  │  rulebook/ + rules/*.yaml ارز، مهلت، آستانه‌ها — با پنجره اعتبار
  ▼
pipeline.py  build_base → ادغام امن (dataio/merge.py: many_to_one، ضد انفجار سطر)
  ▼
stages/  (به ترتیب order؛ هر stage سطر اضافه/حذف نمی‌کند)
  10 resolve              کلیدهای کانونی و حل تعارض
  20 derive               ستون‌های دامنه‌ای؛ شش فیلد مالی حساس بدون جعل صفر (F031)
  30 org / 35 scope       کارشناس، سلسله‌مراتب، مالک قطعه
  38 supply_position      موجودی کارشناسی + Oracle؛ Missing ≠ Zero
  39 warehouse_declaration  قبض انبار و شکاف شاهد پس از ترخیص
  40 criticality          مقاومت = (IKCO + SAPCO) ÷ نیاز روزانه؛ سرایت به BL/سفارش
  50 commitment           مهلت، سناریوی جریمه، هشدار رفع تعهد
  54 process_integrity    زنجیره فرایند با حفظ شواهد فیزیکی
  55 fx_traceability      دفترکل REG: خرید ارز ≠ تأمین وجه ≠ سوئیفت؛ معادل‌ها با basis
  56 money_flow_control   برج کنترل پول، نرخ، جابه‌جایی، مهلت‌ها
  57 legacy_knowledge     دانش قدیمی فقط به‌صورت سرنخ غیرالزام‌آور
  58 case_actions         صف اقدام + پیش‌نویس ایمیل (بازبینی انسانی)
  60 narrate / 70 risk    روایت و امتیاز ریسک
  80 eventlog / 85 conformance   لاگ رویداد و انطباق فرایند
  90 sort
  ▼
warehouse/  run → quality gate → publish اتمیک (wh_current)
  store.py      فریم‌ها (JSON سطری + کش pickle)، اجرای منتشرشده، قفل نویسنده
  business_dwh  جدول‌های fact/dim تجاری؛ reliability.py قراردادهای کیفیت
  ▼
مصرف‌کننده‌ها (همه از Snapshot منتشرشده می‌خوانند؛ ETL خودکار ندارند)
  app/studio.py      Studio: فیلتر، KPI، گزارش‌ساز، HTML/Excel/ایمیل
  app/dashboard.py   مرکز عملیات فرآیند
  app/cashflow.py    فضای مالی: gsi/cashflow (دفتر Decimal) + Process Explorer پول
  studio_core/html_export.py   HTML آفلاین قابل شخصی‌سازی
  integrations/daily_email.py  بسته ایمیل (Outlook فقط Draft)
```

## ۲) قراردادهای صحت داده

| قرارداد | محل اجرا | تست قفل |
|---|---|---|
| عدد نامعلوم None/NaN است، نه 0 | `core/numeric_parse.py`، `warehouse/numeric.py` | `test_data_accuracy_v29_9` |
| تاریخ شمسی نامعتبر رد می‌شود؛ کبیسه = حساب ۳۳ساله مبدل | `core/jalali.py` | همان + مقایسه روزبه‌روز با jdatetime |
| کلید ادغام بدون نویسه نامرئی | `core/text.clean_key` | همان |
| ارز: طولانی‌ترین نام؛ مبهم = خالی؛ ناشناخته = متن کامل | `rulebook/loader.normalize_currency` | همان |
| جمع فقط در یک ارز و در grain ثبت سفارش | `report/financial_summary.py`، `finance/equivalents.py` | `test_rc4_financial_accuracy_hardening` |
| ادغام many-to-one، انفجار سطر = خطا | `dataio/merge.safe_merge` | `test_architecture` |
| Snapshot = تنها منبع UI | `warehouse/service.last_report` | `test_fullstack_v29_6_10` |

## ۳) عملیات و امنیت محلی

* `.streamlit/config.toml`: `127.0.0.1`، بدون telemetry، toolbar در حالت viewer، تم از
  `gsi/design/tokens.py` (تست `test_platform_hardening_v29_9` هم‌خوانی را قفل می‌کند).
* SQLite فقط روی دیسک محلی (`warehouse/store.local_path` مسیر UNC/درایو شبکه را رد می‌کند).
* یک نویسنده در هر زمان (`warehouse/writer_lock.py`)؛ خواننده‌های Streamlit DDL اجرا نمی‌کنند.
* فایل‌های `.cmd` فقط ASCII و CRLF (`.gitattributes`).

## ۴) کارایی — اصول به‌کاررفته

* دیتافریم‌های گسترده (صدها ستون) قبل از `groupby` به ستون‌های مصرفی محدود می‌شوند.
* فیلتر «به‌ازای هر پرونده» روی کل فریم ممنوع است؛ یک بار index بر اساس REG/case ساخته می‌شود.
* `DataFrame.attrs` فقط `SharedList` نگه می‌دارد (pandas ≥ 2.1 روی هر عملیات attrs را deepcopy می‌کند).
* موتور Cash Flow رویدادها، لینک‌ها و نرخ‌ها را یک بار index می‌کند (`PreparedRates`)؛ ترتیب
  جمع Decimal حفظ شده تا خروجی بیت‌به‌بیت با نسخه قبل یکسان باشد.
* هر بهینه‌سازی با مقایسه ۳۴ فریم خروجی خط لوله روی داده مقیاس‌شده تأیید شده است.

## ۵) نقاط توسعه

* سورس جدید: یک فایل در `gsi/adapters/` + یک ورودی در `gsi/config/sources.yaml`.
* قاعده/آستانه جدید: فقط YAML در `gsi/rules/` (یا مسیر بیرونی با `GSI_RULES_DIR`).
* ارز جدید: یک بلوک در `gsi/rules/currencies.yaml` با aliasهای فارسی/انگلیسی.
* stage جدید: کلاس با `order`، `requires`، `provides` و `tolerant` در `gsi/stages/`.
