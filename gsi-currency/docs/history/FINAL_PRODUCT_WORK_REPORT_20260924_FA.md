# گزارش کار نهایی GSI — Final Production Rewrite — 2026-09-24

## 1. وضعیت تحویل

**محصول تحویلی:** Build نهایی کد/پکیج GSI بر پایه `29.8.2 RC4-OPT2 H1` با بازنویسی runtime، quality gate و warm-start.

**اصل محافظت:** پروژه از صفر بازنویسی نشده است. معماری و قابلیت‌های تثبیت‌شده حفظ شده و تغییرات روی مرزهای معیوب production متمرکز شده‌اند.

**وضعیت gate در محیط build:**
- Frozen independent audit: **173/173 PASS**
- Extended diagnostic audit: **77/77 PASS**
- Affected/internal regression: **128/128 PASS**
- Compile-all: **PASS**
- Snapshot→Excel smoke test: **PASS**
- Post-pack validation روی ZIP کاندید انجام شد: CRC/manifest سالم، Frozen **173/173 PASS**، Extended **77/77 PASS**، تست‌های اختصاصی rewrite **9/9 PASS**، compile-all **PASS** و Snapshot→Excel smoke **PASS**.
- ZIP تحویلی نهایی پس از همین گزارش دوباره ساخته و از روی bytes نهایی بازاستخراج/تأیید شده است؛ sidecar `FINAL_PRODUCT_POSTPACK_GATE_20260924.json` نتیجه و SHA-256 فایل تحویلی را ثبت می‌کند.

سه AppTest وابسته به `streamlit.testing` در محیط build حاضر قابل اجرا نیستند چون خود پکیج Streamlit در runtime ممیزی نصب نیست. تست‌های static/warm-start مرتبط داخل regression 128تایی پاس شده‌اند. این مورد به‌عنوان «PASS ساختگی» گزارش نشده است.

---

## 2. چیزی که تحویل گرفتم

### 2.1 Baseline کد
فایل پایه:
`GSI_29_8_2_RC4_OPT2_H1_ALGO_KNOWLEDGE_FINAL_20260924.zip`

SHA-256 baseline:
`37f9d963de9cf1343e67b98f485d741ae68e772eb72a9da84d2a141bd3c855fd`

این baseline حاصل زنجیره قبلی remediation بود و ممیزی مستقل frozen/extended روی آن وجود داشت؛ بنابراین نقطه شروع Greenfield نبود.

### 2.2 قراردادهای کسب‌وکاری که حفظ شدند
- `REG` = شماره/کد ثبت سفارش.
- `REG_FILE` = شماره پرونده ثبت سفارش و از REG مستقل است.
- `ORDER` = سفارش / Order No. / Our Reference در قرارداد منبع معتبر.
- `BL` = بارنامه و مستقل است.
- اتصال مورد انتظار: `ORDER ↔ REG_FILE ↔ REG ↔ BL` فقط با شاهد منبع.
- SAP PO با ORDER یکی فرض نمی‌شود مگر قرارداد منبع صریحاً آن را اثبات کند.
- هیچ ORDER یا BL از REG/REG_FILE ساخته نمی‌شود.
- Material برای gate NTSW الزام نشده است.

### 2.3 شواهد اجرای واقعی Windows که مبنای بازنویسی شدند
اجرای production-like کاربر در 2026-09-24 نشان داد:

- SAP `pr`: 17,029×47
- SAP `pack`: 9,141×14
- SAP `po`: 69,608×46
- SAP `inbound`: 50,301×16
- SAP `GR`: 380,909×21
- SAP `raw_rows`: 526,988
- فاصله `pr → pack`: حدود **25 دقیقه**
- `process_integrity`: حدود **287.58 ثانیه**
- process cases: 78,926
- process evidence: 1,241,596
- explicit gaps: 47,476
- unkeyed evidence preserved: 1,013
- بعد از پیام قدیمی «پایان خط لوله» بیش از **16 دقیقه** زمان صرف شد.
- در نهایت Publish با این gate متوقف شد:
  `sap/raw_rows:GRAIN_UNIQUENESS`
- Snapshot قبلی منتشرشده جابه‌جا نشد.

همان اجرای واقعی همچنین نشان داد که `s20_derive` هنوز برای شش ستون مالی Unknown را به 0 تبدیل می‌کرد و فقط flag همزاد می‌گذاشت؛ این رفتار با قرارداد تصمیم‌سازی سازگار نبود.

---

## 3. مسیر تشخیص تا ریشه مشکل

### 3.1 Quality Gate اشتباه SAP
در adapter، `SAP_SOURCE_ROW` برای هر شیت از ابتدا شماره‌گذاری می‌شود. بنابراین:

`pr row 1` و `po row 1` و `GR row 1`

سه ردیف فیزیکی متفاوت‌اند. قرارداد قدیمی فقط `SAP_SOURCE_ROW` را natural key گرفته بود؛ در نتیجه restart طبیعی شماره ردیف بین شیت‌ها duplicate مصنوعی می‌ساخت.

**ریشه:** grain قرارداد با grain فیزیکی workbook یکی نبود.

**اصلاح:**
`sap/raw_rows = SAP_SOURCE_SHEET + SAP_SOURCE_ROW`

تست جدید هم دو حالت را قفل می‌کند:
- row number یکسان در دو شیت متفاوت → معتبر.
- sheet+row یکسان دوباره تکرار شود → gate block.

### 3.2 SAP workbook چند بار باز می‌شد
مسیر قدیمی برای export native ابتدا workbook را برای discovery باز می‌کرد و بعد `read_sheet()` برای هر شیت یک `ExcelFile` جدید باز می‌کرد.

برای 5 شیت native تعداد handle/openها:
- قبل: **6**
- بعد: **1**

در Build جدید یک `pd.ExcelFile` برای workbook باز می‌شود و `pr/pack/po/inbound/GR` از همان handle parse می‌شوند و سپس handle قطعی بسته می‌شود.

این تغییر مستقیماً bottleneck 25 دقیقه‌ای مشاهده‌شده را هدف می‌گیرد. زمان production جدید فقط پس از اجرای مجدد روی همان workbook Windows قابل اندازه‌گیری است؛ عدد ساختگی برای آن ادعا نشده است.

### 3.3 Process Integrity در Python-loop ساخته می‌شد
Stage matrix تقریباً case×stage است. در اجرای واقعی 78,926 case، بیش از یک میلیون سطر projection ساخته می‌شود. نسخه قبلی برای هر case/stage دیکشنری Python تولید می‌کرد و فیلترهای تکراری داشت.

**اصلاح:** cross-join برداری case×stage + aggregate یک‌باره observationها + merge برداری.

Benchmark مصنوعی یکسان، 20,000 case / 320,000 stage rows:
- قبل: **6.553793 s**
- بعد: **0.969531 s**
- سرعت نسبی: **6.76×**

### 3.4 SAP evidence و Business DWH دوباره‌کاری داشتند
وقتی `sap/raw_rows` وجود داشت، همان داده فیزیکی دوباره در projectionهای `pr_items`, `po_items`, `workflow_rows`, `inbound_deliveries`, `goods_receipts` به‌عنوان source-row archive پردازش می‌شد.

این دو مشکل ایجاد می‌کرد:
1. archive تکراری و شمارش evidence بیشتر از فیزیک منبع؛
2. میلیون‌ها scalar INSERT/UPDATE روی SQLite.

**اصلاح:**
- وقتی `raw_rows` وجود دارد، فقط همان فریم archive فیزیکی SAP است.
- semantic frames حذف نشده‌اند؛ همچنان factهای تخصصی `SAP PR/PO/workflow` را می‌سازند.
- generic source-row insert به `executemany` chunked تبدیل شد.
- entityها unique و batch-upsert می‌شوند.
- relationها قبل از SQLite aggregate و batch-insert می‌شوند.

Benchmark مصنوعی DWH:
- raw rows: 20,000
- semantic projection rows: 8,000
- قبل: **4.586234 s**, archive count=28,000
- بعد: **1.170251 s**, archive count=20,000
- factهای semantic PR/PO/workflow حفظ شدند.
- سرعت نسبی benchmark: **3.92×**

### 3.5 Gate دیر اجرا می‌شد
در مسیر قبلی، source/grain error قبل از Business DWH معلوم بود اما سیستم ابتدا DWH سنگین را می‌ساخت و بعد quality check را record/publish می‌کرد. این دقیقاً علت آن بود که کاربر بعد از پایان core حدود 16 دقیقه منتظر ماند و تازه بعد `GRAIN_UNIQUENESS` دریافت کرد.

**اصلاح معماری:** Early Publication Gate.

ترتیب جدید:
1. core pipeline
2. source/grain/schema/runtime/process/partition checks
3. **early gate**
4. فقط اگر early gate PASS → Business DWH
5. SQLite integrity/FK check
6. final gate
7. atomic publish

اگر early gate رد شود:
- Business DWH skip می‌شود.
- Excel skip می‌شود.
- diagnostics همان run ذخیره می‌شوند.
- publish تلاش می‌کند و همان `QualityGateBlockedError` استاندارد را می‌دهد.
- Snapshot سالم قبلی باقی می‌ماند.

تست جدید صریحاً verify می‌کند که در grain failure تابع Business DWH حتی فراخوانی نمی‌شود.

### 3.6 Unknown مالی هنوز Zero می‌شد — F031 runtime path
مسیر واقعی `s20_derive` برای این ستون‌ها Unknown را صفر می‌کرد:
- `CB_VALUE`
- `BALANCE`
- `ALLOCATED_AMOUNT`
- `OPEN_QUEUE_AMOUNT`
- `REJECTED_ALLOC_AMOUNT`
- `ALLOC_REQUESTED_GROSS`

**اصلاح:**
- invalid/missing/non-finite evidence → `NaN/Missing`
- numeric 0 source evidence → `0`
- `*_IS_UNKNOWN` حفظ شد.
- `unknown_defaulted_to_zero={}`
- coverage جدید `unknown_preserved_as_missing` ثبت می‌شود.

تست جدید روی `[NaN, 0, bad, inf, 12.5]` صریحاً ثابت می‌کند که فقط صفر واقعی صفر می‌ماند.

### 3.7 Lineage در merge از بین می‌رفت
در clashهای RHS، ستون‌هایی مثل `_SOURCE_ROW`, `_SOURCE_FILE_ID`, `_SOURCE_SHEET` ممکن بود حذف شوند.

**اصلاح:** lineage RHS حذف نمی‌شود؛ namespaced می‌شود، مثل:
- `FX_TRANSACTION_SOURCE_ROW`
- `FX_TRANSACTION_SOURCE_FILE_ID`

اگر clash وجود نداشته باشد، نام اصلی حفظ می‌شود.

### 3.8 پیام پایان pipeline زود چاپ می‌شد
پیام قدیمی «خط لوله با موفقیت پایان یافت» قبل از Business DWH/Gate/Publish چاپ می‌شد و باعث برداشت اشتباه از hang می‌شد.

**اصلاح:**
- پایان core: پیام «هسته محاسباتی پایان یافت؛ ... ادامه دارد»
- timer جدا برای Business DWH / quality gate / Excel / publish
- تنها پیام موفقیت نهایی بعد از atomic publish:
  `🏁 اجرای کامل GSI با موفقیت پایان یافت و Snapshot جدید منتشر شد.`

### 3.9 Event log NaN در KPI مدیریتی
اگر پرونده بسته قابل‌اندازه‌گیری نبود، log عبارت `nan روز` نشان می‌داد.

**اصلاح:** `N/A (شاهد کافی برای پرونده بسته نداریم)`؛ Unknown به عدد ظاهری تبدیل نمی‌شود.

---

## 4. بازنویسی lifecycle محصول

### قبل
Streamlit/تاریخ مرجع می‌توانست در نبود Snapshot دقیق، pipeline سنگین را دوباره راه بیندازد؛ Excel نیز در lifecycle اجرای pipeline قرار داشت.

### بعد
سه مسئولیت مستقل:

#### `START_GSI.cmd`
- فقط Published Snapshot.
- ETL خودکار ندارد.
- اگر Snapshot تاریخ انتخابی وجود ندارد، آخرین Published Snapshot را با حالت stale نمایش می‌دهد.

#### `REFRESH_GSI_DATA.cmd`
- تنها مسیر صریح rebuild داده.
- `Pipeline().run(build_report=False)`؛ Excel مانع publish/UI نیست.

#### `EXPORT_GSI_EXCEL.cmd`
- از DWH منتشرشده Excel می‌سازد.
- source workbook نمی‌خواند.
- ETL اجرا نمی‌کند.
- Smoke test واقعی روی warehouse موقت و xlsx تولیدی پاس شد.

این جداسازی یعنی هزینه refresh می‌تواند سنگین باشد، اما startup روزمره UI نباید وابسته به آن باشد.

---

## 5. DWH و محل ذخیره

Default رسمی این Build:
`D:\GSI_DATA\warehouse.sqlite`

اولویت path:
1. `GSI_DWH_PATH`
2. `GSI_DATA_ROOT\warehouse.sqlite`
3. default فوق

SQLite همچنان local-only است؛ UNC/mapped network drive برای فایل اصلی SQLite مجاز نیست تا lock/corruption ریسک شبکه وارد هسته transaction نشود.

---

## 6. فایل‌های production تغییرکرده

- `gsi/warehouse/reliability.py` — composite SAP raw grain.
- `gsi/dataio/reader.py` — single-open native SAP workbook.
- `gsi/dataio/merge.py` — lineage-preserving RHS namespace.
- `gsi/stages/s20_derive.py` — F031 Unknown≠Zero در شش فیلد runtime.
- `gsi/resolve/process_evidence.py` — physical row refs، جلوگیری از duplicate SAP evidence، vectorized stage matrix.
- `gsi/stages/s54_process_integrity.py` — row-preservation count مطابق physical SAP archive.
- `gsi/stages/s80_eventlog.py` — N/A به‌جای NaN KPI.
- `gsi/warehouse/business_dwh.py` — SAP archive once + batch DWH writes.
- `gsi/warehouse/bridge.py` — early gate + stage timers + true final publish message.
- `gsi/warehouse/store.py` — D-drive default و read/write separation موجود حفظ شده است.
- `gsi/pipeline.py` — core-complete message اصلاح شد.
- `app/studio.py` — snapshot-first/no implicit ETL.
- `app/dashboard.py` — snapshot-first/no implicit ETL.
- `gsi/warehouse/export_snapshot.py` — Excel از Published Snapshot، بدون ETL.
- `gsi/__main__.py` — commandهای `refresh` و `export-excel`.

Launcherهای جدید/اصلاح‌شده:
- `START_GSI.cmd`
- `REFRESH_GSI_DATA.cmd`
- `EXPORT_GSI_EXCEL.cmd`
- `RUN_STUDIO_V28.cmd`

تست اختصاصی جدید:
- `tests/test_final_runtime_rewrite_20260924.py`

---

## 7. تست و اعتبارسنجی نهایی

### Gate A — Frozen independent audit
`173 passed`

این همان ممیزی frozen است؛ برای سازگار کردن تست‌ها با کد جدید دست‌کاری نشده است.

### Gate B — Extended independent diagnostics
`77 passed`

### Gate C — Affected/internal regression
`128 passed`

شامل warehouse, reliability gate, business DWH, process integrity, finance contracts, SAP semantic DWH, output integrity, dashboard startup, reader isolation و تست‌های rewrite جدید.

### Gate D — Compile
تمام Python production/test modules compile شدند.

### Gate E — Snapshot Excel
Published warehouse موقت ساخته شد، `export_published_snapshot()` بدون Pipeline اجرا شد و xlsx معتبر تولید شد.

### Gate F — Synthetic performance regression
نتایج raw در `release_evidence/final_rewrite_20260924/BENCHMARKS.json` ثبت شده است.


### Gate G — وضعیت مقررات منقضی در تاریخ تحویل
دو قاعده موقت با `expires_on=2026-09-22` در تاریخ 2026-09-24 منقضی‌اند. سیستم آن‌ها را با `active()` در تصمیم‌گیری اجرا نمی‌کند؛ Doctor طبق قرارداد governance قبلی آن‌ها را error نگه می‌دارد تا جانشین authoritative ثبت شود. هیچ تمدید خودکار یا ساختگی در این Build انجام نشده است. این وضعیت مانع استفاده از Published Snapshot/Streamlit/Export نمی‌شود، اما refresh مقررات‌محور باید با governance سازمان هماهنگ شود.

### AppTestهای محیطی
سه تست browser-level به `streamlit.testing` نیاز دارند و در build runtime موجود نیستند. آن‌ها PASS اعلام نشده‌اند. مسیر startup به‌صورت static/regression تست شده است و محیط Windows کاربر Streamlit دارد؛ پذیرش نهایی browser با اجرای همان package در آن محیط انجام می‌شود.

---

## 8. چیزهایی که عمداً تغییر نکردند

- authority بین REG / REG_FILE / ORDER / BL.
- عدم جعل business key.
- سیاست currency-safe و ممنوعیت جمع native currencyهای متفاوت.
- fail-closed allocation/rate conflict.
- preserve raw evidence و orphan evidence.
- atomic snapshot publication.
- source rulebook/regulatory ruleها.
- تصمیم‌های legal deadline که `needs_verification` بودند خودکار enforce نشدند.
- historical review artifacts پاک نشده‌اند؛ آن‌ها evidence تاریخچه‌اند و نباید به‌عنوان وضعیت فعلی release خوانده شوند. وضعیت فعلی این گزارش و `FINAL_PRODUCT_GATE_20260924.json` است.

---

## 9. نحوه استفاده از محصول تحویلی

### استفاده روزانه
`START_GSI.cmd`

### داده جدید / refresh
`REFRESH_GSI_DATA.cmd`

### Excel
`EXPORT_GSI_EXCEL.cmd`

### CLI معادل
- `python -m gsi refresh`
- `python -m gsi export-excel`
- `python -m gsi studio`

---

## 10. معیار پذیرش روی Windows واقعی

در اولین اجرای `REFRESH_GSI_DATA.cmd` روی داده‌های واقعی، این موارد باید دیده شوند:

1. SAP native sheets با یک lifecycle workbook خوانده شوند.
2. `sap/raw_rows:GRAIN_UNIQUENESS` برای restart شماره سطر بین شیت‌ها fail نشود.
3. اگر duplicate واقعی sheet+row وجود داشته باشد، gate باید fail کند.
4. log `Unknown → Zero` برای شش فیلد حساس وجود نداشته باشد؛ Unknown باید Missing بماند.
5. stage timers باید Business DWH / gate / publish را جدا نشان دهند.
6. پیام نهایی فقط پس از publish چاپ شود.
7. بستن و بازکردن `START_GSI.cmd` نباید Refresh کامل را خودکار اجرا کند.
8. `EXPORT_GSI_EXCEL.cmd` نباید SAP یا سایر source workbookها را دوباره بخواند.

این هشت مورد تعریف روشن پذیرش runtime هستند؛ اگر یکی نقض شود، آن رفتار defect است، نه «کندی طبیعی» یا «محدودیت مبهم».

---

## 11. جمع‌بندی تحویل

مسیر رسیدن به این محصول از سه لایه عبور کرد:

1. **ممیزی مستقل و remediation معنایی**؛
2. **اجرای واقعی چندمنبعی روی Windows و مشاهده رفتار production**؛
3. **بازنویسی محدودِ مرزهای runtime بر اساس همان evidence واقعی**.

نتیجه نهایی فقط patch `GRAIN_UNIQUENESS` نیست؛ lifecycle محصول اصلاح شده است:
**Refresh صریح، Snapshot اتمیک، UI سریع از DWH، Excel مستقل از ETL، gate زودهنگام، lineage حفظ‌شده، Unknown≠Zero و SAP physical grain صحیح.**
