# انتقال دانش نسل قدیم به GSI / AIBL V26.19

## هدف

فایل‌های قدیمی به‌عنوان **Legacy Knowledge Pack** استفاده شده‌اند؛ نه به‌عنوان داده جاری و نه به‌عنوان قانون امروز. دانش استخراج‌شده به اشیای versioned و قابل ممیزی تبدیل شده تا تجربه تیم قبلی در کد بماند، اما Rule تاریخی به‌صورت خام وارد موتور تصمیم‌گیری نشود.

## منابع انتقال تجربه

- `OF - 2026-05-02.xlsx` — نمونه واقعی گزارش رفع تعهد و رابطه Payment/BL.
- `BL-Dates-OF.xlsx` — lineage قدیمی تاریخ ارائه اسناد، کد رهگیری، مجوز بارگیری، ترخیص، تخصیص، خرید ارز و تعهد.
- `ETS.xlsx` — نمونه نوع/مبلغ جریمه؛ فقط semantics تاریخی.
- `Rates.xlsx` — نرخ ثابت مرجع گزارش قدیمی؛ **برای P&L واقعی مجاز نیست**.
- `ZMM58.xlsx` — رابطه REG ↔ BL ↔ مبلغ/ارز/Shipment/کارشناس.
- `NTSW.xlsx` — ساختار نمونه CB / Release Commitment / Allocation.
- `Append.xlsx` — نگاشت کارشناس و روابط BL/Order/REG.
- `OF-Final-Revision.ipynb` — الگوریتم قدیمی FIFO تخصیص Payment به BL و الگوهای فنی نسل قبل.
- `نکات رفع تعهد.pdf` — مدل تاریخی A/B/C، مدارک عملیاتی و موانع رفع تعهد.

## دانش منتقل‌شده به چه کلاس‌هایی تبدیل شد؟

1. `historical_rule` — مانند مدل سه ساعت A/B/C. فقط برای بازسازی/فهم سابقه؛ `binding=false`.
2. `operational_practice` — مانند FIFO قدیمی Payment→BL یا اختلاف رویه بانک در مبدأ تعهد.
3. `data_mapping` — lineage بین NTSW / Payment / IKCO / BL / REG.
4. `root_cause` — نزول/بیش‌بود ارزش، اختلاف تعرفه، کسر تخلیه، عدم ورود کالا، مغایرت اظهارنامه، خطای شماره ابزار پرداخت و غیره.
5. `evidence_requirement` — بسته شواهد پیشنهادی برای بررسی پرونده.
6. `technical_antipattern` — fan-out مالی، نرخ ثابت برای P&L، شناسه Payment مصنوعی، وابستگی به Desktop Automation.

## تغییرات کد

### 1) کاتالوگ versioned

فایل `aibl/rules/legacy_knowledge.yaml` 22 Knowledge Item دارد. هر مورد provenance، نوع، confidence، binding و evidence مورد نیاز دارد.

### 2) گارد حاکمیتی

`aibl/knowledge/legacy.py` تابع `can_auto_enforce()` را پیاده می‌کند. Legacy source حتی اگر اشتباهاً `binding=true` شود، بدون `verified + official source class` اجازه auto-enforcement نمی‌گیرد.

### 3) Stage جدید 57

`aibl/stages/s57_legacy_knowledge.py` بعد از Money Flow Control و قبل از Narrator اجرا می‌شود و این خروجی‌ها را می‌سازد:

- `FX_KNOWLEDGE_SIGNAL_COUNT`
- `FX_ROOT_CAUSE_HINTS`
- `FX_EVIDENCE_REQUIREMENTS`
- `FX_KNOWLEDGE_PROVENANCE`
- `FX_RATE_SEMANTIC_GAPS`
- `FX_PAYMENT_WITHOUT_BL_SIGNAL`
- `FX_LEGACY_RULE_GUARD`

خروجی stage **Investigation Guidance** است، نه حکم تقلب یا نظر حقوقی قطعی.

### 4) Payment without BL

در گزارش قدیمی، مانده Payment بدون BL به‌صورت یک ردیف فاقد BL دیده می‌شد. در V26.19 این مفهوم به `UNALLOCATED_PAYMENT_CANDIDATE` تبدیل شده است. BL مصنوعی ساخته نمی‌شود و پول باید با Allocation Edge واقعی به Order/BL متصل شود.

### 5) نرخ و تبدیل ارز

`Rates.xlsx` نشان می‌داد نسل قدیم برای normalization از نرخ ثابت استفاده می‌کرد. در V26.19 این نرخ فقط historical reference است. نرخ‌های زیر مستقل‌اند:

- نرخ خرید ارز (`FX_PURCHASE_RATE`)
- نرخ پرداخت به تأمین‌کننده (`SUPPLIER_SETTLEMENT_RATE`)
- Cross Rate
- نرخ حسابداری
- کارمزدها

اگر ارز خریداری‌شده و ارز پرداختی متفاوت باشند ولی شواهد نرخ/مبلغ کامل نباشند، سیستم `FX_RATE_SEMANTIC_GAPS` می‌سازد و P&L جعلی تولید نمی‌کند.

### 6) Root Cause Library

موانع قدیمی رفع تعهد به Root-cause candidate تبدیل شده‌اند. تطبیق بر اساس متن/ساختار واقعی پرونده انجام می‌شود و کنار هر candidate، Evidence لازم برای بررسی نمایش داده می‌شود.

### 7) UI و Excel

در Process View پرونده، بخش «انتقال دانش تاریخی — Root Cause و Evidence» اضافه شده است. شیت `FX. رهگیری مالی-ارزی` نیز Knowledge Signal، Evidence و کاتالوگ Provenance را نمایش می‌دهد.

## مواردی که عمداً منتقل نشدند

- مهلت‌های قدیمی A/B/C به‌عنوان قانون جاری.
- نرخ‌های قدیمی `Rates.xlsx` به‌عنوان نرخ واقعی معامله.
- مبلغ/نوع جریمه `ETS.xlsx` به‌عنوان حکم جاری.
- FIFO قدیمی به‌عنوان تخصیص واقعی پول.
- جمع ردیفی Payment بعد از join به چند BL.
- شناسه Payment ساخته‌شده از `REG + Amount + Date`.
- Desktop Automation و مسیرهای Share ثابت به‌عنوان هسته سیستم.

## اصل نهایی

**تجربه حفظ می‌شود، اما ادعای حقوقی/مالی فقط از Evidence جاری و Rule تأییدشده می‌آید.**
