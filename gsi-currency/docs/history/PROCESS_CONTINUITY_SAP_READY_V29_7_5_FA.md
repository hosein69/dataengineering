# تداوم فرایند و آمادگی SAP — V29.7.5

## هدف
این نسخه یک Patch موضعی نیست. هدف آن این است که هیچ شاهد، وضعیت مثبت/منفی/میانی یا شاخه مستقل فرایند به‌خاطر تکمیل یک جریان دیگر حذف یا متوقف نشود و اضافه‌شدن SAP کامل در آینده قراردادهای فعلی را نشکند.

## اصلاحات سیستمی

### 1) تاریخچه SAP دیگر فشرده و حذف نمی‌شود
Adapter SAP دو خروجی دارد:
- `main`: آخرین وضعیت هر PR برای سازگاری با مصرف‌کنندگان قبلی.
- `workflow_rows`: تمام رویدادها/تغییرات PR در grain بومی.

Business DWH هر دو را ذخیره می‌کند. بنابراین Created/Approved/Rejected/Rework و هر وضعیت میانی در آینده قابل ممیزی است.

### 2) Process Evidence Ledger مستقل از Flat Report
مرحله `process_integrity` از تمام frameهای native یک دفتر شواهد می‌سازد و سه خروجی پایدار تولید می‌کند:
- `process_evidence`: تمام شواهد منبعی و مرحله‌ای.
- `process_cases`: پرونده‌های متصل‌شده فقط با کلیدهای مستقیم مستند.
- `process_stage_matrix`: وضعیت هر مرحله برای هر پرونده.

هیچ fuzzy join ساخته نمی‌شود. اگر یک کلید به چند پرونده محتمل برسد، `AMBIGUOUS_LINK` ثبت می‌شود و سیستم حدس نمی‌زند.

### 3) Later Evidence هرگز حذف نمی‌شود
اگر مثلاً ترخیص دیده شود ولی حمل/کوتاژ قبلی در شواهد نباشد:
- شاهد ترخیص حفظ می‌شود.
- مرحله قبلی `EVIDENCE_GAP` می‌شود.
- جریان متوقف یا به عقب overwrite نمی‌شود.

### 4) Missing Data با Process Failure یکی نیست
مرحله‌ای که سورس آن هنوز در دسترس یا کامل نیست `NOT_MEASURED` / `SOURCE_COVERAGE_GAP` می‌گیرد؛ نه `EVIDENCE_GAP`.
برای SAP فعلی که `known_incomplete` است این تفکیک جلوی هشدار کاذب را می‌گیرد.

### 5) شاهد بدون کلید حذف نمی‌شود
هر ردیف native یک `SOURCE_OBSERVATION` می‌گیرد. اگر PR/ORDER/REG/BL/MATERIAL قابل اتصال نداشته باشد، با `ORPHAN_NO_BUSINESS_KEY` در `process_orphan_evidence` باقی می‌ماند تا با تکمیل SAP یا mapping بعدی قابل اتصال باشد.

### 6) Quality Gate برای عدم حذف ردیف
Gate جدید `PROCESS_ROW_PRESERVATION` تعداد ردیف‌های native مورد انتظار را با `SOURCE_OBSERVATION`های حفظ‌شده مقایسه می‌کند. اختلاف، publication را Block می‌کند.

### 7) جداسازی خرابی شاخه‌های tolerant
پیش از این `tolerant=True` فقط نبودن ستون ورودی را تحمل می‌کرد؛ exception داخل stage می‌توانست کل Run را متوقف کند. اکنون خرابی stageهای tolerant قرنطینه می‌شود، row count حفظ می‌شود، `stage_failures` ثبت می‌شود و شاخه‌های مستقل ادامه می‌دهند. Stageهای core غیر-tolerant همچنان fail-fast هستند تا گزارش ناسالم منتشر نشود.

## مدل فرایند آماده SAP

`PLANNING_PR → EXPERT_INTAKE → ORDER_CREATED → REGISTRATION → ALLOCATION_REQUEST → ALLOCATION → COMMITMENT → FX_PURCHASE → FUNDING → PAYMENT → SHIPMENT → CUSTOMS → CLEARANCE → BANK_DOCS → SETTLEMENT`

این Sequence یک projection کنترلی است؛ شواهد منبعی مستقل از آن نگه داشته می‌شوند. وجود مرحله دیرتر هرگز به معنی ساخت مصنوعی مرحله قبلی نیست.

## سازگاری با 29.7.4
- Population گزارش تخت همچنان Experts + NTSW است؛ Abbasi/SATA enrichment هستند.
- SAP-only PRها به زور وارد Main Flat Report نمی‌شوند، ولی از همین حالا در Process Inventory و DWH حفظ می‌شوند.
- وقتی فایل SAP کامل شود، بدون تغییر قرارداد adapter می‌توان Planning PRها را به Expert/Order/REG از طریق PRهای co-observed متصل کرد.
- Cash Flow DWH-first و قواعد عدم ساخت Settlement/Bank Flow مصنوعی حفظ شده‌اند.

## خروجی‌های جدید قابل ممیزی
- `extras/process_evidence`
- `extras/process_cases`
- `extras/process_stage_matrix`
- `extras/process_orphan_evidence`
- `process_evidence_summary`
- ستون‌های `PROCESS_*` در Flat Report برای projection بدون تغییر grain.

