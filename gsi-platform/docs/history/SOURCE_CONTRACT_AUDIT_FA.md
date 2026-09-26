# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# ممیزی سورس و حدود تأیید — 29.7.8 RC2

## ورودی جدید چه بود؟
`GSI_SOURCE_PROFILER_EVIDENCE_PACK_TOOL.zip` ابزار تولید Evidence Pack است؛ هیچ Excel واقعی SAP/NTSW/Oracle/Expert و هیچ `source_catalog.json` یا `model_context_pack.md` تولیدشده در آن نیست. تنظیمات آن هفت مسیر نمونه `C:/GSI/data/...` دارد. ابزار بدون تغییر در `tools/source_profiler` قرار گرفته و ورودی جدیدِ محاسبات هیچ گزارشی نیست.

کد ابزار بررسی شد. تشخیص Grain و Key در آن heuristic است؛ REG_FILE ممکن است هم‌زمان REG تشخیص داده شود، عنوان‌های تاریخ/وضعیت هم ممکن است نقش شناسه بگیرند و ترکیب دو نقش با یک ستون ممکن است relation_examples را بشکند. نتیجهٔ probe در `review/rc2_validation/SOURCE_AUDIT.json` ثبت است. این نقش‌ها هرگز جایگزین قرارداد canonical سیستم نشده‌اند. نمونه‌گیری محدود نیز کل تاریخچه وضعیت‌ها یا همه تعارض‌ها را اثبات نمی‌کند.

## تفکیک شناسه‌ها

| مفهوم | کلید | قرارداد و محدودیت |
|---|---|---|
| شماره پرونده ثبت سفارش | KEY_REG_FILE | شناسه پرونده مجوز؛ در قرارداد فعلی ۹ رقم یا بیشتر. خودِ کد ثبت سفارش نیست. |
| ثبت سفارش / شماره ثبت سفارش / کد ثبت سفارش | KEY_REG | شناسه قانونی ثبت سفارش؛ در قرارداد فعلی ۸ رقمی. عنوان هر سورس باید با معنای فیلد تطبیق داده شود. |
| سفارش / شماره سفارش | KEY_ORDER | مرجع سفارش تجاری IKCO؛ نه PR، نه PO و نه REG. |
| Our Reference در Commercial Expert | MOGH_ORDER_REF → KEY_ORDER | فقط بر مبنای قرارداد همان سورس، مرجع سفارش است. |
| po.Our Reference / po.Your Reference در SAP | SAP_PO_OUR_REFERENCE / SAP_PO_YOUR_REFERENCE | ویژگی مرجع سند PO؛ به‌طور عمومی ORDER یا REG تلقی نمی‌شود. |
| Reference / refrence بدون زمینه | بدون alias عمومی | ممکن است شماره نامه، سند یا مرجع طرف مقابل باشد؛ از روی نام یا شباهت عدد، join ساخته نمی‌شود. |
| درخواست خرید و قلم | KEY_PR × SAP_PR_ITEM | Grain مستقل درخواست خرید؛ چند PO ممکن است به یک قلم مربوط باشد. |
| سفارش خرید SAP و قلم | KEY_PO × SAP_PO_ITEM | PO با ORDER تجاری یکسان فرض نمی‌شود. |

اصلاح ID-01 جلوی انتخاب fuzzy ستون «ثبت سفارش» برای ORDER را می‌گیرد. تست سه شناسه متفاوت در یک ردیف و نبود ORDER اضافه شده است.

## ماتریس منابع موجود در رجیستری

| Source | نقش / Grain مهم | کلیدهای اصلی | ملاحظات |
|---|---|---|---|
| moghavemat / Commercial Expert | Tier 1؛ ردیف خرید و projection سفارش، موجودی سفارش×متریال | ORDER، MATERIAL، PR | Our Reference منبع‌محور؛ BL مشکوک قرنطینه می‌شود. |
| ntsw | Tier 1؛ مجوز، درخواست تخصیص، ردیف تعهد | REG_FILE، REG، REQUEST_KEY، COMMIT_ROW | وضعیت و تاریخ snapshot با هم بررسی می‌شوند. |
| abbasi | Tier 2؛ enrichment بارنامه | BL، ORDER | به‌تنهایی جمعیت اصلی نمی‌سازد. |
| sata | Tier 2؛ پل مستقیم لجستیکی/ثبت سفارش | BL، ORDER، REG | تنها مسیر ارتباط با NTSW نیست. |
| clearance | ردیف ترخیص چندفایلی | BL | قرارداد شیت‌ها و جهت واردات/صادرات هنوز نیازمند داده واقعی است. |
| cotage | اظهار/کوتاژ و وضعیت ترخیص | BL | ستارهٔ وضعیت، تاریخ واقعی ایجاد نمی‌کند. |
| oracle | موجودی/نیاز متریال | MATERIAL | grain مخازن و جمع‌پذیری نیازمند تأیید مالک داده است. |
| fx_transaction | خرید ارز و پرداخت مستند احتمالی | REG، ORDER، BL | خرید، سوئیفت و پرداخت یک رویداد واحد نیستند. |
| credit | اعتبار، تأمین وجه، سوئیفت | REG، ORDER | سوئیفت اثبات وصول ذی‌نفع نیست. |
| ilappend | الحاقیه و پل شماره پرونده | REG_FILE، REG، ORDER | پرونده و کد ثبت سفارش جدا نگه داشته می‌شوند. |
| sap | raw row / PR item / PO item / workflow | PR، PR item، PO، PO item | یک ردیف Export می‌تواند چند grain حمل کند. |
| doccheck | سند / projection آخرین وضعیت سفارش | ORDER | doc_rows برای حفظ شواهد باقی است. |
| hr | پرسنل و ساختار سازمانی | EMP | گزارش نقش/سازمان به داده HR موجود وابسته است. |
| missmohammadi | غیرفعال | BL | نبود آن وابستگی تازه‌ای ایجاد نمی‌کند. |

نگاشت‌های literal ستون‌های adapterها، شیت‌ها، الگوها و وضعیت enabled/required از کد استخراج و در SOURCE_AUDIT.json ضمیمه شده‌اند. این اشراف به قرارداد پیاده‌شده است، نه ادعای دیدن همه سلول‌های منابع تولیدی.

## تکرار شماره پرونده و وضعیت

- تکرار REG یا REG_FILE دلیل کافی برای حذف نیست؛ ممکن است چند درخواست، چند ردیف تعهد یا چند snapshot باشد.
- Import Licence همه ردیف‌ها و وضعیت‌ها را نگه می‌دارد؛ چند وضعیت برای یک شماره پرونده با `NTSW_LICENSE_STATUS_CONFLICT` مشخص می‌شود. برچسب «تأیید» به‌تنهایی مجوز انتخاب به‌عنوان آخرین نسخه نیست.
- تخصیص با شناسه درخواست و تاریخ مرتب می‌شود؛ تکرار کاملاً یکسان یک‌بار وارد ledger می‌شود، تاریخچه محفوظ است. وضعیت/مبلغ/ارز متعارض در تاریخ مساوی AMBIGUOUS و قرنطینه می‌شود.
- برای یک شناسه ردیف تعهد، تعارض وضعیت رفع تعهد یا مهلت نیز مانند تعارض مبلغ بررسی می‌شود. ردیف‌های بی‌شناسه و مبهم از جمع قطعی خارج می‌شوند.
- این قواعد ادعای رفع تمام ریسک‌های legacy یا تأیید همه معنای وضعیت‌های واقعی نیستند.
