# نصب و اجرا — راهنمای دقیق

## چرا اجرای قبلی خطا داد

خطای شما:
```
ImportError: attempted relative import with no known parent package
  File "...\_strptime.py", line 16, in <module>
    import calendar
```

سه علت هم‌زمان داشت:

**۱. فایل‌ها تخت (flat) کپی شده بودند.** در پوشه `material` فایل‌هایی مثل
`partition.py` مستقیم کنار هم بودند، نه داخل زیرپوشه‌های `aibl/`.

**۲. `calendar.py` روی ماژول استاندارد پایتون سایه انداخت.** وقتی pandas
داخلاً `import calendar` می‌زند، پایتون اول پوشه جاری را می‌گردد و به فایل من
می‌رسد. آن فایل `from .text import ...` دارد که بدون پکیج والد کار نمی‌کند.
**این اشتباه من بود** — دیگر ماژولی با نام کتابخانه استاندارد وجود ندارد:

| نام قبلی | نام جدید |
|---|---|
| `aibl/core/calendar.py` | `aibl/core/jalali.py` |
| `aibl/io/` | `aibl/dataio/` |

**۳. `aibl.py` نسخه ۲۰.۱ هنوز در همان پوشه بود.** دستور `python -m aibl.pipeline`
اول به آن فایل می‌رسید و اجرایش می‌کرد.

---

## نصب صحیح

### گام ۱ — پوشه کاری تمیز
پوشه فعلی `material` هم `aibl.py` قدیمی دارد و هم فایل‌های تخت.
یک پوشه تازه بسازید (ترجیحاً روی درایو محلی، نه مسیر UNC شبکه):

```powershell
mkdir D:\AIBL
cd D:\AIBL
```

> اجرای پایتون از مسیر `\\ikco.com\...` کند و ناپایدار است. کد را محلی بگذارید؛
> فقط **داده‌ها** از شبکه خوانده می‌شوند.

### گام ۲ — کپی با حفظ ساختار درختی
ساختار باید **دقیقاً** این باشد:

```
D:\AIBL\
├── aibl\
│   ├── __init__.py
│   ├── __main__.py
│   ├── doctor.py
│   ├── pipeline.py
│   ├── adapters\      __init__.py  base.py  moghavemat.py  bl_sources.py  order_sources.py
│   ├── config\        __init__.py  settings.py  sources.py  sources.yaml  business_rules.py
│   ├── core\          __init__.py  text.py  jalali.py  columns.py
│   ├── dataio\        __init__.py  logging_setup.py  reader.py  merge.py
│   ├── engines\       __init__.py  commitment.py  risk.py  math_engine.py
│   ├── narrate\       __init__.py  narrator.py
│   ├── report\        __init__.py  dashboard.py  extracts.py  palette.py
│   ├── resolve\       __init__.py  canonical.py  org_mapper.py  partition.py
│   ├── rulebook\      __init__.py  loader.py  validate.py
│   └── rules\         _manifest.yaml + ۸ فایل YAML
├── tests\
├── run_all_tests.py
└── README.md
```

اگر با Explorer کپی می‌کنید، **پوشه `aibl` را یکجا** بکشید — نه محتویاتش را.

### گام ۳ — کتابخانه‌ها
```powershell
python -m pip install --upgrade pandas numpy openpyxl pyyaml
python -m pip install jdatetime          # اختیاری
```

`jdatetime` لازم نیست؛ مبدل شمسی داخلی نوشته‌ام و تست شده
(`1404/01/15 → 2025-04-04`).

### گام ۴ — عیب‌یابی قبل از اجرا
```powershell
cd D:\AIBL
python -m aibl.doctor
```

Doctor پنج چیز را بررسی می‌کند:
۱. سایه‌اندازی روی کتابخانه استاندارد ۲. ساختار پکیج و وجود `aibl.py` قدیمی
۳. کتابخانه‌ها ۴. سلامت قوانین و adapterها ۵. دسترسی به ۶ پوشه شبکه و قابل‌نوشتن بودن خروجی

تا وقتی خروجی `0 خطا` نیست، اجرا نکنید. Doctor مسیر دقیق هر فایل مشکل‌دار را می‌گوید.

### گام ۵ — اجرای اول
```powershell
$env:AIBL_STRICT_ADAPTERS = "1"
python -m aibl.pipeline
```

با این پرچم، اولین ناسازگاری هدر بلافاصله اجرا را متوقف می‌کند به‌جای اینکه
بی‌صدا رد شود. پس از اطمینان از هدرها:

```powershell
Remove-Item Env:\AIBL_STRICT_ADAPTERS
python -m aibl.pipeline
```

یا کوتاه‌تر — که خودش اول doctor را می‌زند و فقط در صورت سلامت اجرا می‌کند:
```powershell
python -m aibl run
```

---

---

## وقتی KPIها صفر یا غیرمنطقی‌اند

اگر گزارش ساخته شد ولی اعداد بی‌معنی بودند (مثلاً «۱٬۲۷۸ تعهد قرمز» ولی
«جمع مانده تعهد = ۰»)، یعنی سورس خوانده شده اما **به جدول اصلی نچسبیده**.

```powershell
python -m aibl.diagnose --excel
```

سه جدول می‌دهد:

**۱) وضعیت هر رابطه** — با تفکیک سه علتِ کاملاً متفاوت که خروجی یکسان دارند:

| تشخیص | یعنی | اقدام |
|---|---|---|
| فایل پیدا نشد | الگوی `pattern` غلط است | `config/sources.yaml` |
| ستون کلید پیدا نشد | نگاشت ستون غلط است | `COLUMN_MAP` همان adapter |
| کلید هست ولی همه تهی | نرمال‌سازی مقادیر را رد می‌کند | تابع `clean_*` |
| هیچ اشتراکی ندارند | شکل کلید در دو سورس یکی نیست | جدول ۲ را ببینید |

**۲) نمونه کلیدهای جورنشده** — دو ستون کنار هم، همان چیزی که تشخیص را قطعی می‌کند:

```
کلید           جدول پایه      سورس
KEY_MATERIAL   MAT001         M-MAT001      ← پیشوند اضافه
KEY_BL         MSCU1234567    MSCU-1234567  ← خط تیره
```

**۳) پر بودن ستون‌های حیاتی** — می‌گوید کدام KPI به کدام ستون وابسته است و
آن ستون چند درصد پر شده. اگر `ORC_STOCK_QTY` صفر درصد باشد، «قطعات بحرانی»
هم صفر می‌ماند و علتش همان‌جا نوشته است.

با `--headers` فهرست ستون‌های واقعی هر فایل هم چاپ می‌شود تا نگاشت را
دستی تطبیق دهید.

## دستورات

| دستور | کار |
|---|---|
| `python -m aibl.doctor` | عیب‌یابی محیط |
| `python -m aibl.diagnose --excel` | **عیب‌یابی رابطه‌ها — چرا KPI صفر است** |
| `python -m aibl.rulebook.validate` | اعتبارسنجی قوانین + فهرست ۱۹ قاعده نیازمند تطبیق |
| `python -m aibl.pipeline` | اجرای کامل |
| `python -m aibl run` | doctor سپس اجرا |
| `python run_all_tests.py` | هر ۳۴۶ تست |

---

## فهرست گیرندگان ایمیل — پیکربندی محرمانه

نشانی‌های کارکنان **داده شخصی**اند و از نسخه ۲۶٫۴٫۰ داخل سورس نگه‌داری
نمی‌شوند. فهرست را یکی از این چهار راه بدهید (به همین ترتیب اولویت):

```powershell
# ۱) متغیر محیطی
$env:AIBL_EMAIL_TO = "a.person@example.invalid; b.person@example.invalid"

# ۲) فایل مشخص
$env:AIBL_RECIPIENTS_FILE = "D:\secure\recipients.yaml"

# ۳) فایل پیش‌فرض
#    %USERPROFILE%\.aibl\recipients.yaml

# ۴) مستقیم از سورس HR  ← توصیه‌شده
$env:AIBL_EMAIL_FROM_HR = "1"
```

### گزینه ۴: گیرنده از سورس HR (توصیه‌شده)

ستون `Email` همان فایل پرسنلی (`HR_Main_Updated.xlsx`) منبع گیرندگان
می‌شود. مزیتش این است که **هیچ کپی جانبی‌ای ساخته نمی‌شود**: فهرست
همیشه با آخرین وضعیت پرسنلی هم‌گام است و کسی که غیرفعال شده، خودکار از
گیرندگان بیرون می‌رود — برخلاف فایل جانبی که کهنه می‌شود و کسی خبردار
نمی‌شود.

فیلترها، همه به‌صورت «شامل بودنِ متن» و با هم AND:

| متغیر | پیش‌فرض | کار |
|---|---|---|
| `AIBL_EMAIL_FROM_HR=1` | خاموش | فعال‌سازی این مسیر |
| `AIBL_EMAIL_HR_POSTS` | `مدیر,رئیس,معاون` | فیلتر روی شرح پست |
| `AIBL_EMAIL_HR_MANAGEMENTS` | — | فیلتر روی مدیریت |
| `AIBL_EMAIL_HR_OFFICES` | — | فیلتر روی اداره |
| `AIBL_EMAIL_HR_MAX` | — | سقف تعداد گیرنده |

```powershell
# فقط مدیران و رؤسای مدیریت مواد اولیه
$env:AIBL_EMAIL_FROM_HR      = "1"
$env:AIBL_EMAIL_HR_POSTS     = "مدیر,رئیس"
$env:AIBL_EMAIL_HR_MANAGEMENTS = "مواد اولیه"
python -m aibl email
```

نکته‌های امنیتی که در پیاده‌سازی رعایت شده:

* پیش‌فرض عمداً **فقط سطوح مدیریتی** است؛ گزارش روزانه سند مدیریتی است و
  ارسال آن به کل پرسنل نه مفید است نه محتاطانه.
* فقط پرسنل **فعال** انتخاب می‌شوند.
* نشانی‌های بدشکل حذف می‌شوند (اعتبارسنجی الگو).
* در لاگ فقط **تعداد** گیرنده نوشته می‌شود، هرگز خود نشانی‌ها:
  `👥 12 گیرنده از سورس HR انتخاب شد (از 430 پرسنل؛ نشانی‌ها لاگ نمی‌شوند).`
* اگر `AIBL_EMAIL_FROM_HR` تنظیم نشود، سورس HR اصلاً برای ایمیل خوانده
  نمی‌شود.

قالب فایل (`recipients.example.yaml` را کپی کنید):

```yaml
recipients:
  - a.person@example.invalid
  - b.person@example.invalid
```

اگر هیچ‌کدام تنظیم نشود، ساخت گزارش و نمودارها کار می‌کند ولی **ارسال با
خطای صریح متوقف می‌شود** — عمداً، تا هرگز به فهرستی قدیمی ارسال نشود.

> `recipients.yaml` در `.gitignore` است و نباید به مخزن اضافه شود.
> حساب فرستنده هم با `AIBL_EMAIL_SENDER` تنظیم می‌شود؛ خالی یعنی حساب
> پیش‌فرض Outlook.

---

## متغیرهای محیطی

| متغیر | کار |
|---|---|
| `AIBL_STRICT_ADAPTERS=1` | توقف در اولین خطای adapter |
| `AIBL_OUTPUT` | مسیر خروجی (پیش‌فرض `D:\of\blstotal\output`) |
| `AIBL_LOGS` | مسیر لاگ |
| `AIBL_RULES_DIR` | قوانین از پوشه بیرونی خوانده شود |
| `AIBL_SOURCES_YAML` | رجیستری سورس از فایل دیگر |
| `AIBL_TODAY` | تاریخ مرجع ثابت (برای بازتولید گزارش قدیمی) |
| `AIBL_EMAIL_TO` / `AIBL_RECIPIENTS_FILE` / `AIBL_EMAIL_SENDER` | گیرندگان و فرستنده ایمیل (محرمانه) |
| `AIBL_EMAIL_FROM_HR` / `AIBL_EMAIL_HR_POSTS` / `AIBL_EMAIL_HR_MANAGEMENTS` / `AIBL_EMAIL_HR_OFFICES` / `AIBL_EMAIL_HR_MAX` | گیرندگان مستقیم از ستون Email سورس HR |
| `AIBL_FOREIGN` / `AIBL_BLS` / `AIBL_CLEARANCE` / `AIBL_HR` / `AIBL_ESMAEILI` / `AIBL_MOHAMADI` | مسیر سورس‌ها |

---

## اگر باز خطا گرفتید

خروجی کامل `python -m aibl.doctor` را بفرستید. برخلاف traceback خام،
دقیقاً می‌گوید کدام فایل کجاست و چه باید کرد.

خطاهای رایج:

| پیام | علت | راه‌حل |
|---|---|---|
| `attempted relative import` | فایل هم‌نام ماژول استاندارد در مسیر | خروجی doctor بخش ۱ را ببینید |
| `No module named aibl.pipeline; aibl is not a package` | `aibl.py` قدیمی در مسیر | نامش را به `aibl_legacy_v20.py.bak` تغییر دهید |
| `RowExplosionError` | کلید یک سورس یکتا نیست | لاگ نام سورس را می‌گوید؛ `dedupe_by` را در `sources.yaml` تنظیم کنید |
| `ستون X یافت نشد` | تغییر هدر در فایل اکسل | نگاشت مربوطه را در adapter همان سورس اصلاح کنید |
| `کتابخانه قوانین خطای ساختاری دارد` | YAML خراب یا مجموع وزن‌ها ≠ ۱ | `python -m aibl.rulebook.validate` |
