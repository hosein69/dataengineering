# جمعیت درجه‌اول گزارش و زنجیره Cash Flow — V29.7.4

## هدف انتشار
این نسخه دو تغییر معماری را همزمان اعمال می‌کند:

1. **Population کل گزارش** دیگر از Abbasi/BLs Tracking شروع نمی‌شود. جمعیت پایه از اجتماع دو مرجع درجه‌اول، یعنی فایل کارشناسان (`moghavemat`) و NTSW ساخته می‌شود. Abbasi و SATA فقط برای enrichment، تکمیل خلأ و ثبت اختلاف استفاده می‌شوند و نمی‌توانند به‌تنهایی پرونده جدید وارد گزارش اصلی کنند.
2. **Cash Flow** از مجموعه‌ای از رویدادهای پراکنده به زنجیره شواهد قابل ممیزی از PI تا مانده تعهد ارتقا یافته است. شکاف‌های زنجیره صریح اعلام می‌شوند و موتور هیچ پرداخت، رفع تعهد، حساب بانکی یا تبدیل ارزی را بدون شاهد مستند نمی‌سازد.

## 1) Primary Population
ماژول جدید `gsi/resolve/population.py` جمعیت اولیه را می‌سازد.

### منابع سازنده جمعیت
- Commercial Expert / `moghavemat/main`: یک پرونده بر مبنای ORDER و اطلاعات کارشناسی.
- NTSW: ORDER/REGهای مستند در Import Licence و REGهای مشاهده‌شده در Commitment/Allocation.

قاعده اصلی:

```text
Primary Population = Expert ∪ NTSW
```

اگر یک ORDER هم در کارشناسان و هم در NTSW دیده شده باشد، یک Case پایه ساخته می‌شود و شاهد NTSW به آن متصل می‌شود. اگر NTSW فقط REG داشته باشد و ORDER قابل اثبات نباشد، REG به‌صورت پرونده مستقل حفظ می‌شود و سیستم ORDER حدسی نمی‌سازد.

### نقش Abbasi و SATA
Abbasi می‌تواند BLهای مستند را به ORDER موجود در Population درجه‌اول اضافه کند؛ در صورت وجود چند BL واقعی برای یک ORDER، همان ORDER به چند ردیف لجستیکی مستند گسترش می‌یابد. **ORDERی که فقط در Abbasi باشد، جمعیت جدید ایجاد نمی‌کند.** SATA نیز پس از ساخته‌شدن جمعیت به‌عنوان پل/شاهد درجه‌دوم استفاده می‌شود و نمی‌تواند NTSW را override کند.

### Partition
در V29.7.4 عضویت در Main برابر است با حضور در حداقل یکی از منابع درجه‌اول:

```text
IS_IN_MOGHAVEMAT OR IS_IN_NTSW_PRIMARY
```

بنابراین پرونده NTSW-only دیگر صرفاً به علت نبود فایل کارشناسان به `to_resolve` منتقل نمی‌شود.

### ابهام کلید
ارتباط NTSW فقط از مسیرهای مستند پذیرفته می‌شود:

```text
ORDER + REG     (مشاهده مستقیم)
REG_FILE → REG  +  REG_FILE → ORDER  (هاب exact)
```

در نگاشت چندمعنا، سیستم حدس یا fuzzy join نمی‌زند؛ مورد در diagnostics باقی می‌ماند.

## 2) Cash Flow Evidence Chain
مسیر پیش‌فرض Cash Flow همچنان Published SQLite Business DWH است و flat mart فقط fallback اضطراری است.

خروجی جدید `chain` برای هر `REG` این مراحل را نمایش می‌دهد:

```text
1. PI / REGISTRATION
2. ALLOCATION_REQUEST / QUEUE
3. ALLOCATION
4. COMMITMENT
5. FX_BUY
6. FUNDING
7. PAYMENT
8. SETTLEMENT / COMMITMENT_RETURN
9. REMAINING_COMMITMENT
```

برای هر مرحله تعداد شاهد، مبلغ‌ها، تاریخ‌ها، اسناد، مبلغ لینک‌شده، status، gap code و توضیح ثبت می‌شود.

### قواعد ضد حدس
- مانده NTSW یک Measurement/Snapshot است، نه Cash Event.
- Deadline فقط `due_date` است و تراکنش محسوب نمی‌شود.
- کاهش مانده NTSW به‌تنهایی Settlement تولید نمی‌کند.
- تعهد فقط با Link صریح `OBLIGATION_SETTLEMENT` یا `OBLIGATION_RETURN` کاهش می‌یابد.
- اگر مانده NTSW کمتر از تعهد اولیه باشد ولی سند Settlement/Return در Ledger وجود نداشته باشد، `MISSING_SETTLEMENT_EVIDENCE` صادر می‌شود.
- اگر Commitment وجود داشته باشد اما Snapshot مانده موجود نباشد، `MISSING_COMMITMENT_BALANCE_SNAPSHOT` صادر می‌شود.
- FX Buy و Payment فقط وقتی با `SOURCE_RECORD_FLOW` به هم متصل می‌شوند که در **همان رکورد بومی FX** و با ارز یکسان همزمان مشاهده شده باشند. مقدار لینک‌شده از Payment بیشتر نمی‌شود؛ باقیمانده حدس زده نمی‌شود.
- حساب بانکی و conversion rate ساختگی تولید نمی‌شود.

### وضعیت‌های Chain
از جمله:
- `EVIDENCED`
- `PARTIALLY_LINKED`
- `UNLINKED`
- `GAP`
- `NOT_YET_EVIDENCED`
- `MATCH` / `MISMATCH`
- `LEDGER_ONLY`
- `NOT_APPLICABLE`

هدف این وضعیت‌ها این است که نبود یک Stage فقط وقتی Gap شود که شواهد پایین‌دستی نشان دهد آن مرحله باید قابل ردیابی می‌بود؛ در غیر این صورت «هنوز شاهد نشده» گزارش می‌شود تا هشدار کاذب کم شود.

## 3) خروجی‌ها
Excel و HTML Cash Flow اکنون شیت/تب **«زنجیره PI تا رفع تعهد»** دارند. Standalone Cash Flow نیز همین جدول را نمایش می‌دهد.

## 4) سازگاری و Fail-safe
- اگر هر دو Source درجه‌اول واقعاً خالی باشند، ساخت Population متوقف می‌شود؛ سیستم به Abbasi-only برنمی‌گردد.
- `required:false` در تنظیمات Source به معنی اجازه استفاده از Snapshot سالم قبلی یا اجرای یک‌منبعی است؛ به معنی تنزل Authority نیست.
- Quality Gate و Published DWH همچنان از انتشار Run خراب جلوگیری می‌کنند.
- منطق V29.7.3 برای Source Authority حفظ شده است.

## 5) تست‌های اختصاصی V29.7.4
تست‌های جدید اثبات می‌کنند:
- Abbasi-only وارد Population نمی‌شود.
- Expert + NTSW سازنده Population هستند.
- NTSW-only در Main باقی می‌ماند.
- چند BL مستند Abbasi برای یک ORDER درجه‌اول حفظ می‌شود.
- کاهش Snapshot بدون Settlement به Gap تبدیل می‌شود و Settlement جعلی ساخته نمی‌شود.
- Link صریح Settlement مانده Ledger را reconcile می‌کند.
- هم‌مشاهده FX Buy و Payment در یک رکورد DWH، لینک مستند ایجاد می‌کند و `UNTRACED_PAYMENT` را رفع می‌کند.
