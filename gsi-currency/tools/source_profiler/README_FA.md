# GSI Source Profiler

این ابزار از Sourceهای واقعی یک **Evidence Pack کوچک اما پرمحتوا** می‌سازد تا به مدل هوش مصنوعی بدهید.

## خروجی چه چیزهایی دارد؟

- مسیر Source و Sheet
- Headerها و تعداد ردیف/ستون
- Grain احتمالی
- Candidate Keyها
- PR / PO / ORDER / REG / BL / Cottage / Material / Supplier / Workflow columns
- Statusهای واقعی و فراوانی آنها
- Duplicate/repeated-key signals
- Fan-outهای مهم مثل یک PR با چند PO
- Relationهای co-observed
- نمونه ردیف‌های هوشمند و edge-case
- Schema JSON
- Manifest + SHA256 داخلی هر فایل خروجی

## نصب

```bash
pip install pandas openpyxl pyyaml
```

## اجرا

1. `gsi_sources.yaml` را با آدرس واقعی فایل‌ها اصلاح کنید.
2. اجرا کنید:

```bash
python gsi_source_profiler.py --config gsi_sources.yaml --output gsi_evidence_pack --sample-rows 18
```

## چه چیزی برای مدل بفرستم؟

بهترین حالت: کل پوشه `gsi_evidence_pack` را ZIP کنید.

اگر محدودیت حجم دارید، این ترتیب را بفرستید:

1. `executive_summary.md`
2. `model_context_pack.md`
3. `process_key_index.json`
4. Schema JSONهای Sourceهای مهم
5. Sample CSVهای SAP / Expert / NTSW / FX / Customs

## منطق Sampling

Sample صرفاً Random نیست. ابزار عمداً ردیف‌هایی را انتخاب می‌کند که بیشترین اطلاعات فرایندی را بدهند:

- ردیف‌های دارای Business Keyهای زیاد
- Statusهای متفاوت
- Hub Keyهایی که چند رابطه دارند
- Fan-outها
- ردیف ناقص برای آشکارشدن Gap
- چند ردیف Random برای جلوگیری از Bias کامل

این Sample برای شناخت **Process / Grain / Relations** است، نه تحلیل آماری.

## هشدار

Relationهای `co-observed` فقط می‌گویند دو شناسه در یک ردیف منبع کنار هم مشاهده شده‌اند. این ابزار هیچ Fuzzy Join را Truth اعلام نمی‌کند.
