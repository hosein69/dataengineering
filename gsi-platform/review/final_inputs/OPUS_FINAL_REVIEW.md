# OPUS_FINAL_REVIEW — حکم نهایی GSI 29.7.7 RC1

**تاریخ:** 2026-09-23
**ورودی:** `GSI_29_7_7_RC1_OPUS_REVIEW.zip` + `HANDOFF_FOR_OPUS.md`
**مبنای مقایسه:** `GSI_V29_7_6_SAP_SEMANTIC_DWH_SMART_CHATBOT.zip` (دست‌نخورده) و `OPUS_REVIEW.md` (بازبینی قبلی من)
**نسخه سند:** 1.0 — این سند قابل استناد است؛ هر ادعا به فایل/خط یا نام probe ارجاع دارد.

---

## 0. حکم

> ### ✅ تأیید به‌عنوان **Review Candidate**
> ### ⛔ **Production sign-off رد می‌شود**

با disposition خودِ RC («REVIEW CANDIDATE ONLY — production sign-off blocked») موافقم. اما **فهرست blockerها ناقص بود** و سه مورد کشف‌نشده به آن افزوده شده است (RES-1 تا RES-3). هر سه در همین بازبینی **اصلاح شدند** و اصلاح‌ها به‌صورت patch جداگانه تحویل شده‌اند (بخش ۶).

| سنجه | نتیجه |
|---|---|
| یافته‌های تحت داوری (۴۰ Astra + ۱۳ Opus) | ۵۳ |
| بسته‌شده و مستقل راستی‌آزمایی‌شده | **۳۳** |
| باز/جزئی و **صادقانه افشا‌شده** | ۱۹ |
| داوری نادرست | **۰** |
| یافته جدیدِ کشف‌نشده در RC (این بازبینی) | **۳** (RES-1 HIGH، RES-2 MED-HIGH، RES-3 MED) |
| ریسک استقرار تازه‌ی ثبت‌نشده | ۲ (RES-4، RES-5) + ۱ مورد اطلاعاتی (RES-6) |
| بازاجرای تست‌ها توسط من | **1048 موفق / 0 ناموفق، exit 0** — ادعای RC دقیق است |
| بازاجرا پس از اصلاح‌های من | **1048 موفق / 0 ناموفق، exit 0** — بدون رگرسیون |

**ارزیابی کیفی:** این بهترین شکل ممکن از پاسخ به یک ممیزی است — دیف تولیدی حدوداً ۲۸۰ خط، بدون بازنویسی، بدون مهاجرت stack، با افشای صریح اینکه یک دیتابیس واقعاً خراب شده و **ترمیم نشده تا گیت سبز شود**. جدول `adjudication.json` با آنچه من مستقل اندازه گرفتم مطابقت دارد؛ هیچ موردی را بیش از واقعیت «IMPLEMENTED» نزده‌اند.

---

## 1. روش و محیط راستی‌آزمایی

هیچ ادعایی از روی متن HANDOFF یا FINDINGS_REGISTER پذیرفته نشد. روش:

1. **دیف کامل** `review/validation/changes.patch` خوانده شد (۳۴ فایل، ۴۹۲+ / ۹۹−؛ از این مقدار ۱۶۳ خط فایل تست جدید و ۴۶ خط ماژول `snapshots.py` است، یعنی کد تولیدی مؤثر ≈ ۲۸۰ خط).
2. **probeهای بازبینی قبلی من** بدون تغییر منطق روی RC اجرا شدند تا «همان counterexample» سنجیده شود.
3. **probeهای تازه** برای معماری جدید نوشته شدند، چون مکانیزم انتشار عوض شده و probe قدیمی دیگر جای درستی را اندازه نمی‌گیرد (بخش ۴).
4. **کل مجموعه تست** در محیط اعلام‌شده خودشان بازاجرا شد.
5. **تلاش برای بازتولید RC03** با فشار همزمانی انجام شد.

محیط: Python 3.12، pandas 2.2.3، NumPy 2.3.5، Streamlit 1.49.1، pytest 9.1.1، openpyxl 3.1.5، SQLite 3.x — منطبق بر `TEST_AND_INVARIANTS.md`.

اسکریپت‌های probe در `gsi-phase0-review/rc1/` و probeهای دور اول در `gsi-phase0-review/probes/` قرار دارند.

---

## 2. بازاجرای مستقل تست‌ها

```
جمع کل: 1048 تست موفق | 0 ناموفق
Runner exit code: 0
```

**ادعای headline دقیق است.** ۷۳ مجموعه، هر کدام در subprocess با DWH یکبارمصرف.

نکته صحت‌سنجی که باید ثبت شود: عدد ۱۰۴۸ ترکیب «check»های legacy و test caseهای pytest است، نه ۱۰۴۸ تابع مجزا؛ خودشان هم همین را در `TEST_AND_INVARIANTS.md` نوشته‌اند. سبزبودن این عدد **تأیید داده تولیدی نیست** و نباید باشد.

---

## 3. داوری بسته‌شدن ۵۳ یافته

ستون «روش» یعنی من چطور راستی‌آزمایی کردم:
**P** = probe اجرایی مستقل · **C** = خواندن کد/دیف · **S** = پوشش تست بازاجراشده · **A** = پذیرش داوری DEFER با شاهد کافی

### 3.1 بسته‌شده — با probe اجرایی تأیید شد

| ID | ادعای RC | حکم من | شاهد عددی (قبل ← بعد) | روش |
|---|---|---|---|---|
| **F001** | IMPLEMENTED | **✅ بسته** | PR اجرای مسدود برای چت‌بات: قابل‌مشاهده ← `blocked_pr_visible: false`؛ pointer روی R1 | P `rc_isolation` |
| **F002** | IMPLEMENTED | **✅ بسته** | داده منتشرشده پس از اجرای مسدود: ۰ ردیف ← `published_pr_survived_blocked_run: 2` | P `rc_isolation` |
| **F004** | PARTIAL | **✅ بسته (ریشه)** | دو ORDER با متریال مشترک: ۱ پرونده با `ORDER_COUNT=2` ← **۲ پرونده** با `[1,1]` | P `p_status` |
| **F005** | IMPLEMENTED | **✅ بسته** | دو ردیف native یکسان: ۱ observation ← **۲** | P `p_status` |
| **F007** | IMPLEMENTED | **✅ بسته** | `100 USD + 100 EUR` → `200.0 EUR` ← **NaN** (امتناع از جمع) | P `p_status` |
| **F008** | IMPLEMENTED | **✅ بسته** | «تایید نشده» → `ALLOCATED` ← **`OPEN`** | P `p_status` |
| **F009** | PARTIAL | **✅ بسته** | همان `COMMIT_ROW` دوبار: `ROWS=2, INITIAL=200, BALANCE=100` ← **`1 / 100 / 50`** | P `p_status` |
| **F012** | IMPLEMENTED | **✅ بسته** | اکسل رسمی پیش از گیت ← فقط پس از `gate.passed`، در `output/runs/<run_id>/` با ۴ آرتیفکت | P `rc_gatecheck` |
| **F017** | IMPLEMENTED | **✅ بسته** | `po_item` ذخیره‌شده: `(pr=1000000001, item=00090, mat=PRMAT)` ← **`(1000000009, 00090, POMAT-B)`**؛ رابطه `PR 1000000001→PO` ← **`PR 1000000009→PO`** | P `p_sap` |
| **F018** | PARTIAL | **✅ بسته (هر دو وجه)** | چت‌بات «آخرین PR»: `SUPPLIER-OLD` (قلم «۲» لغوی) ← **`SUPPLIER-NEW`** (قلم ۱۰، بر اساس تاریخ)؛ انباشت workflow پس از ingest مجدد: `3→7` ← **`3→4`** | P `rc_isolation`, `p_sap` |
| **F020** | IMPLEMENTED | **✅ بسته** | کلید مرکب خالی / `NaN` / برخورد delimiter / کلید جزئی: هر چهار `matched=1` ← **همه `0`** | P `rc_merge` |
| **F025** | PARTIAL | **✅ بسته** | `ilappend/main` کاملاً بی‌کلید: همه چک‌ها pass ← **`USABLE_KEY_EVIDENCE` = BLOCK/fail**؛ PR تکراری با item خالی: pass ← **`GRAIN_UNIQUENESS` = BLOCK/fail** | P `rc_isolation`, `p_sap` |
| **N02** | IMPLEMENTED | **✅ بسته** | `REG_FILE` با ۲ REG و ۲ ORDER: **۴ زوج جعلی** ← ۴ ردیف تفکیک‌شده با `NULL`، بدون هیچ جفت‌سازی | P `p_dwh` |
| **N03** | PARTIAL | **✅ بسته** | «مورد تایید»→NEGATIVE ← **POSITIVE**؛ «تایید نشده»→POSITIVE ← **NEGATIVE**؛ «در گردش»→NEGATIVE ← **OBSERVED** | P `p_status` |
| **N06** | IMPLEMENTED | **✅ بسته** | قلم PR با دو PO: ستون PO یک سند دلخواه ← **`<NA>` + `SAP_PO_COUNT`** | P `p_sap` |
| **N09** | PARTIAL | **✅ بسته** | ingest مجدد فایل دست‌نخورده: `evidence_count 1→2` ← **ثابت روی `1`** | P `p_dwh` |
| **F006** | REJECT | **✅ رد من تأیید شد** | `any_relation_from_main_frame: false`، `cross_pair: false` — در هر دو نسخه | P `p_dwh` |

### 3.2 بسته‌شده — با شاهد کد

| ID | حکم من | شاهد |
|---|---|---|
| **F011** | ✅ بسته (سازوکار) | دو `raise ValueError` در `a50_ntsw` جای خود را به **قرنطینه ردیفی** دادند (`commitment_quarantine` + `DQ_REASON`)؛ `critical_sources` از `{abbasi,ntsw,ilappend}` به `{ntsw,ilappend}` اصلاح شد — منطبق بر نقش Tier-2 مستند `abbasi`. **باقیمانده:** `moghavemat` (Tier-1 و سازنده جمعیت) همچنان critical نیست. |
| **F016** | ✅ بسته (وجه ارز) | `PI_VALUE_SUM` با `sum(min_count=len(g))` و شرط تک‌ارزی → NaN به‌جای جمع چندارزی |
| **F022** | ✅ بسته | نگاشت غلط `SATA_DOC_RECEIVED → FIN_RECEIPT_DATE` حذف شد — **اما جایگزین آن تولیدکننده ندارد؛ نک. RES-3** |
| **F024** | ✅ بسته | مسیر سریع `mtime+size` حالا `status='ACTIVE'` می‌گذارد؛ sweep حذف فقط روی rootهای **اسکن‌شده موفق** (`scanned_roots`) اعمال می‌شود |
| **F026** | ✅ بسته | FX و credit به `order_to_reg`/`bl_to_reg` با قاعده «تک‌کاندید» برمی‌گردند و در غیر این‌صورت `UNRESOLVED_FINANCIAL_EVIDENCE` ثبت می‌کنند — ردیف دیگر بی‌صدا حذف نمی‌شود |
| **F027** | ✅ بسته | `native_ref` از شمارنده `NTSW_COMMIT_ROWS` به `f"{reg}:commitment-summary"` تغییر کرد |
| **F030** | ✅ بسته (fail-closed) | `find_col` روی برخورد هدر نرمال‌شده `AMBIGUOUS_NORMALIZED_HEADER` و روی تساوی امتیاز `AMBIGUOUS_HEADER_MAPPING` می‌دهد — **ریسک جانبی: RES-5** |
| **F033** | ✅ بسته | frameهای fallback حالا با `wh.frame(...,'standardized',...)` برای run جدید ثبت و با `source_origin_run` در `attrs` برچسب‌گذاری می‌شوند؛ `attrs` در `store.frame/read_frame` رفت‌وبرگشت می‌کند |
| **F034** | ✅ بسته | `except Exception: return []` → `raise RuntimeError("OPERATIONAL_SOURCE_UNAVAILABLE")`؛ `answer` آن را به `status="SOURCE_UNAVAILABLE"` تبدیل می‌کند |
| **F035** | ✅ بسته (جداسازی) | تفکیک سؤال عملیاتی از رویه‌ای — **رگرسیون جانبی: RES-6** |
| **F038** | ✅ بسته | `DocCheckAdapter` حالا `doc_rows` native را در کنار projection `main` برمی‌گرداند |
| **F039** | ⚠️ **بسته ناقص** | SWIFT دیگر `PAYMENT` نیست (درست) — ولی مرحله جدید ثبت نشد؛ **RES-1** |
| **F040** | ✅ بسته | `publish` با `BEGIN IMMEDIATE` و گارد «انتشار نباید به اجرای قدیمی‌تر برگردد»؛ `_ensure_schema` حالا وجود `wh_quality_check`/`wh_schema_baseline`/`wh_publish_event` را هم شرط می‌کند |
| **N07** | ✅ بسته | `if ps:` → `if True:` با توضیح؛ نبودِ خلاصه دیگر گیت BLOCK را حذف نمی‌کند |
| **N10** | ✅ بسته | baseline اسکیما به `wh_schema_candidate` (run-scoped) می‌رود و **فقط داخل `publish()`** ترفیع می‌یابد — اجرای مسدود دیگر baseline را دائمی نمی‌کند |
| **N11** | ✅ بسته | فایل موقت حالا در `tmp/<fid>/<نام اصلی>` نوشته می‌شود، پس `_SOURCE_FILE` نام کسب‌وکاری است نه هش؛ `_SOURCE_SHEET` در شاخه معمولی هم ست می‌شود (هر دو fallback مردهٔ قبلی زنده شدند) |
| **N12** | ✅ بسته | `kind="mergesort"` در هر دو نقطه تصمیم «آخرین وضعیت» |

### 3.3 باز یا جزئی — افشای صادقانه، من هم تأیید می‌کنم

| ID | وضعیت RC | تأیید من | نکته |
|---|---|---|---|
| **F003** | PARTIAL | ✅ درست | جدول‌های کاری هر اجرا بازساخته می‌شوند و تاریخچه در snapshot می‌ماند؛ ولی «حذف در برابر نبودِ رکورد» تا تعیین قرارداد full/delta باز است. probe: `omitted_pr_after_new_publish: 0` با `snapshot_runs_retained: 3` — یعنی نمای جاری افت می‌کند، تاریخچه نه. |
| **F010** | PARTIAL | ✅ درست | `SOURCE_COVERAGE_GAP` با شدت DEGRADED افزوده شد؛ مفقودبودن منبع هنوز BLOCK نیست |
| **F013** | PARTIAL | ✅ درست | lineage سطح‌فیلد (`*_SOURCE_SHEETS`) افزوده شد؛ سیاست `max` درست دست‌نخورده ماند چون تصمیم مالک داده است (B5) |
| **F014** | OPEN / DEFER | ✅ درست (A) | تناقض «additive درون‌شیت / non-additive بین‌شیت» بدون داده واقعی قابل حل نیست |
| **F015** | DOCUMENTED | ✅ درست | با ارزیابی خودم در بازبینی قبلی هم‌راستاست: این projection اعلام‌شده است، نه data loss پنهان |
| **F019 / N04** | PARTIAL | ✅ درست | `validate="many_to_one"` افزوده شد و یک WARN صریح برای projection ثبت می‌شود، **اما چون `dedupe_on_key` همچنان قبل از join اجرا می‌شود، گارد هنوز غیرقابل‌فعال‌شدن است**. probe: `many_to_one_rhs_values_kept: ["LC-1"]`، `row_explosion_raised: false` — بدون تغییر نسبت به 29.7.6. حذف حالا **مرئی** است، ولی همچنان حذف است. |
| **F021 / N05** | PARTIAL | ✅ درست | `fully_unreachable_targets: 10 → 8`؛ `SATA_DATE` و `DISCHARGE_DATE` به تولیدکننده واقعی (`SATA_TRACKING_DATE`, `BL_DISCHARGE_DATE`) وصل شدند — یعنی شاخه مردهٔ تفکیک «در راه/در گمرک» زنده شد؛ و ثابت جعلی `SEGMENT="تولیدی"` به `""` تبدیل شد. **باقیمانده: RES-4.** |
| **F023** | OPEN_RELEASE_BLOCKER | ✅ درست | `totals_by_currency` همچنان بدون فیلتر run/file روی `wh_measure` |
| **F028** | OPEN_RELEASE_BLOCKER | ✅ درست | `all_data_sheets` هنوز فقط بزرگ‌ترین شیت را برمی‌گزیند |
| **F029** | OPEN / DEFER | ✅ درست | با ارزیابی من یکی است: این ابهام کسب‌وکاری است نه یافته HIGH |
| **F031** | OPEN_RELEASE_BLOCKER | ✅ درست — **ولی ناقص؛ نک. RES-2** | |
| **F032** | OPEN / DEFER | ✅ درست | `_POLICY` همچنان در زمان import خوانده می‌شود و `SOURCE_PRIORITY` هاردکد است |
| **F036** | DOCUMENTED | ✅ درست | `historical_runtime` همچنان صفر مصرف‌کننده دارد |
| **F037** | OPEN_RELEASE_BLOCKER | ✅ درست | `host=0.0.0.0`، `CORS *`، بدون auth |
| **N01** | PARTIAL | ✅ درست | چک تازه `SOURCE_MAPPING_COVERAGE` (بر پایه `df.attrs['missing_mappings']`) تغییر نام هدر را **می‌بیند** — probe `p_drift2`: در 29.7.6 خروجی `SCHEMA_DRIFT passed=TRUE` با fingerprint یکسان بود، در RC `SOURCE_MAPPING_COVERAGE passed=FALSE`. **اما شدت WARN است و انتشار را متوقف نمی‌کند.** |
| **N08** | OPEN_RELEASE_BLOCKER | ✅ درست | مشتق‌شدن `PROCESS_CASE_ID` از هش کل اعضای component تغییر نکرده. اصلاح F004 احتمال بروز را کم می‌کند (probe: `case_id_stable_when_member_added: true` در این سناریو) ولی سازوکار همچنان membership-based است. افشای آن‌ها دقیق است. |
| **N13** | DOCUMENTED | ✅ درست | در `FINDINGS_REGISTER.md:1018` با استدلال ثبت شده: فیلتر ۸ رقمی قرارداد `keys.yaml` است، نه حذف شاهد؛ پوشش قرنطینه/UI باز است |

---

## 4. راستی‌آزمایی معماری انتشار جدید

این مهم‌ترین تغییر RC است و باید جداگانه سنجیده می‌شد، چون **probe قدیمی من دیگر جای درست را اندازه نمی‌گیرد**: جدول `dwh_fact_source_row` حالا یک جدول کاری است که هر اجرا بازساخته می‌شود، پس خواندن `WHERE last_seen_run=?` از آن دیگر معیار ایزولاسیون نیست.

`gsi/warehouse/snapshots.py` (۴۶ خط) سه کار می‌کند:

1. `capture(conn, run_id)` — هر جدول `dwh_*` را با ستون `snapshot_run` در `snap_dwh_*` کپی می‌کند، **تریگر BEFORE UPDATE/DELETE با `RAISE(ABORT)`** می‌گذارد، و capture دوباره‌ی یک run را رد می‌کند.
2. `bind_published(conn)` — در `Warehouse.read_db()` فراخوانی می‌شود و برای هر جدول `dwh_*` یک **TEMP VIEW هم‌نام** می‌سازد که فقط snapshot اجرای منتشرشده را برمی‌گرداند. viewهای وابسته (مثل `dwh_registration_hub`) هم بازتعریف می‌شوند تا به همان viewهای محلی اتصال برسند.
3. **مسیر legacy fail-closed:** اگر `wh_semantic_snapshot` وجود نداشته باشد، همه‌ی viewها `WHERE 0` می‌شوند و `_published_run` خطای `LEGACY_SEMANTIC_REBUILD_REQUIRED` می‌دهد.

**نتیجه probe مستقل من (`rc_isolation`):**

```
pointer_still_r1                    : true
blocked_pr_visible                  : false     ← در 29.7.6: true
published_pr_survived_blocked_run   : 2         ← در 29.7.6: شواهد ناپدید می‌شد
snapshot_immutable                  : true      (DELETE روی snap_* با خطای Immutable رد شد)
snapshot_runs_retained              : 3
```

**ارزیابی:** طراحی درست است و fail-closed بودنش را تأیید می‌کنم. دو نکته که باید در سند استقرار بیاید:

- **اثر مهاجرت واقعی است و افشا شده:** هر دیتابیس تولیدی موجود تا اجرای یک run تازه، برای چت‌بات و Cash Flow **خالی** خواهد بود. این انتخاب درست است (نشان‌ندادن بهتر از نشان‌دادن داده‌ای است که as-of آن اثبات نمی‌شود)، اما باید به‌عنوان یک گام عملیاتی برنامه‌ریزی شود، نه یک سورپرایز. `KNOWN_LIMITATIONS` بند ۶ آن را ثبت کرده.
- **`read_db` حالا با `BEGIN` یک تراکنش خواندن باز می‌کند** و تا `close()` آن را نگه می‌دارد. برای انسجام snapshot درست است؛ اثرش بر رقابت با writer در بار تولیدی اندازه‌گیری نشده.

---

## 5. یافته‌های جدید — کشف‌نشده در RC

### RES-1 — **HIGH — رگرسیون خودِ RC** — مرحله `SWIFT_SENT` ثبت نشده است

**دسته:** Process Continuity · Commitment/Settlement
**فایل:** `gsi/resolve/process_evidence.py:237` (emit) در برابر `STAGES` (خط ۴۳ به بعد) · `gsi/stages/s54_process_integrity.py:27` (`providers`)

اصلاح F039 درست بود: شاهد سوئیفت دیگر `PAYMENT` («پرداخت / وصول ذی‌نفع») emit نمی‌کند و به‌جای آن `SWIFT_SENT` می‌دهد. اما `SWIFT_SENT` به tuple `STAGES` اضافه نشد. چون `_STAGE_POS` از همان tuple ساخته می‌شود و `_components`/`_stage_matrix` با `STAGE_CODE.isin(_STAGE_POS)` فیلتر می‌کنند، این شاهد از کل مدل فرایند بیرون می‌افتد.

**بازتولید (`rc_residual.py` روی RC1 دست‌نخورده):**

```
SWIFT_SENT_in_STAGES            : false
SWIFT_SENT_label                : <no label>
observation_stage_codes         : ["SOURCE_OBSERVATION", "SWIFT_SENT"]
stage_matrix_codes_include_swift: false
case_status                     : ["NO_STAGE_EVIDENCE"]
case_current_focus              : ["PLANNING_PR"]
```

**یعنی: پرونده‌ای با شاهد واقعی سوئیفت، «هیچ شاهد مرحله‌ای ندارد» گزارش می‌شود**، در ماتریس مراحل هیچ ردیفی ندارد، برچسب فارسی و مالک دامنه ندارد. نسبت به 29.7.6 این یک **از دست رفتن سیگنال** است: قبلاً سیگنال وجود داشت ولی با برچسب غلط؛ حالا اصلاً وجود ندارد.

این یک بدهی مستند نیست، یک رگرسیون عملکردی است. **اصلاح شد — بخش ۶.**

---

### RES-2 — **MEDIUM-HIGH** — مقادیر «نامعلومِ» تازه، دوباره به صفر تبدیل می‌شوند

**دسته:** Cash Flow · Source Authority · (تعامل با F031)
**فایل:** `gsi/stages/s20_derive.py` — `DERIVED` خطوط ۴۴، ۴۵، ۱۱۶–۱۱۹ (`default=0, numeric=True`) در برابر مقادیر NaN تازهٔ `a50_ntsw._agg_allocation` و `moghavemat._aggregate`

RC به‌درستی از حدس‌زدن امتناع می‌کند: تعهد/تخصیص چندارزی و ردیف‌های قرنطینه‌شده حالا `NaN` می‌دهند به‌جای عدد غلط. اما `DeriveStage` همان NaN را با `default=0` و `num_safe` به **`0.0`** تبدیل می‌کند.

**بازتولید (`rc_residual.py` روی RC1 دست‌نخورده):**

```
ALLOCATED_AMOUNT_from_NaN : [0.0]
BALANCE_from_NaN          : [0.0]
CB_VALUE_from_NaN         : [0.0]
```

پیش از RC، پرونده‌ی دارای تعارض ارز عددِ غلطِ آشکار (`200 EUR`) نشان می‌داد. حالا **«تخصیص = ۰» و «مانده = ۰»** نشان می‌دهد — که در داشبورد/ایمیل مدیریتی مثل «تعهدی وجود ندارد» خوانده می‌شود. از نظر جهتِ خطا این از حالت قبل خطرناک‌تر است.

این در روحِ blocker افشا‌شده‌ی **F031** هست، اما تعامل آن تازه است و مستقیماً محصول اصلاح‌های همین RC؛ بنابراین نباید داخل F031 مدفون بماند. **اصلاح شد — بخش ۶.**

---

### RES-3 — **MEDIUM** — `FIN_RECEIPT_DATE` حالا هیچ تولیدکننده‌ای ندارد

**دسته:** Ambiguous Mapping · Orphan Evidence
**فایل:** `gsi/stages/s20_derive.py:47`

```python
"FIN_RECEIPT_DATE": (["FINANCIAL_RECEIPT_DATE_EVIDENCE"], "", False),
```

`grep` در کل پکیج: تنها ارجاع به `FINANCIAL_RECEIPT_DATE_EVIDENCE` همین خط است. هیچ adapterی آن را تولید نمی‌کند، پس این ستون **برای همیشه خالی** است.

مصرف‌کننده‌ها: `gsi/stages/s80_eventlog.py:83` («Financial Receipt Booked»، فاز RELEASE)، `gsi/engines/risk.py:61`، `gsi/engines/commitment.py:207` (`alarm2_buy_to_fin`).

حذف نگاشت غلط `SATA_DOC_RECEIVED` **درست** بود (F022). اما جایگزینی آن با یک نام بی‌تولیدکننده، یک KPI و یک آلارم را از «غلط» به «همیشه غایب» می‌برد بدون اینکه جایی اعلام شود. سیگنالی که می‌توانست این را نشان دهد (`ctx.extras["derive_missing"]`) **همچنان نوشته می‌شود و هیچ مصرف‌کننده‌ای ندارد** — همان نکته‌ای که در بازبینی قبلی زیر N05 ثبت کرده بودم و بسته نشده. **اصلاح شد — بخش ۶.**

---

### RES-4 — LOW-MEDIUM — زنجیره authority همچنان به ستونی اشاره می‌کند که reader حذفش می‌کند

`gsi/resolve/expert_roles.py:59` نقش خریدار را با `[("ORC_BUYER","oracle"), ("CRD_BUYER","credit")]` حل می‌کند، یعنی **اولین مرجع** ستونی است که `a40_oracle.EXCLUDED_HEADERS` و لیست `forbidden` در `dataio/reader.py` عمداً حذف می‌کنند. `ORC_BUYER` و `ORC_STATUS` هر دو در فهرست ۸ هدف بی‌تولیدکننده باقی مانده‌اند. این بخشی از N05 است که PARTIAL علامت خورده ولی در `KNOWN_LIMITATIONS` نیامده. **اصلاح نشد** (نیازمند تصمیم مالک داده درباره اینکه آیا ستون باید از exclusion خارج شود) — ولی حالا با چک تازه‌ی بخش ۶ در هر اجرا مرئی است.

### RES-5 — LOW-MEDIUM — مسیر تازه‌ی قطعی‌شدن منبع در `find_col`

`gsi/core/columns.py` حالا روی هدر مبهم `raise` می‌کند. fail-closed بودن **درست** است، اما رفتار تازه‌ای می‌سازد: یک فایل واقعی که دو هدر با نرمال‌سازی یکسان دارد، از این پس کل adapter را می‌شکند. برای منابع غیربحرانی degrade می‌شود؛ برای `ntsw`/`ilappend` **انتشار را BLOCK می‌کند**. پیش از استقرار باید روی هر ۱۷ workbook واقعی smoke-test شود. این ریسک در هیچ سندی ثبت نشده.

### RES-6 — INFO — جست‌وجوی اسناد برای سؤال‌های شناسه‌دار کنار گذاشته می‌شود

`gsi/knowledge_desk/query.py`: `doc_hits = [] if operational else search(...)`. هر سؤالی که یک عدد ۶ تا ۱۶ رقمی داشته باشد و واژه‌های رویه‌ای (`رویه/آیین نامه/دستورالعمل/policy/procedure/how to`) نداشته باشد، **فقط** خروجی DWH می‌گیرد. مثلاً «برای ثبت سفارش ۸۸۰۰۰۰۰۱ چه مدارکی لازم است؟» هیچ سند دانشی برنمی‌گرداند. کیفیت پاسخ نسبت به 29.7.6 افت می‌کند، هرچند صحت ادعا بهتر شده.

---

## 6. اصلاح‌های اعمال‌شده

تحویل: `gsi-phase0-review/rc1/opus_rc1_fixes.patch` — دیف در برابر RC1 دست‌نخورده. چهار فایل، تغییر حداقلی، بدون بازنویسی.

| # | فایل | تغییر |
|---|---|---|
| RES-1 | `gsi/resolve/process_evidence.py` | افزودن `("SWIFT_SENT", "ارسال سوئیفت", "TREASURY")` به `STAGES`، **میان `FUNDING` و `PAYMENT`** |
| RES-1 | `gsi/stages/s54_process_integrity.py` | افزودن `"SWIFT_SENT": ("credit",)` به `providers` تا نبودِ منبع credit به `NOT_MEASURED` برود نه `EVIDENCE_GAP` |
| RES-2 | `gsi/stages/s20_derive.py` | ثابت `UNKNOWN_SENSITIVE` و ساخت ستون همزاد `<TARGET>_IS_UNKNOWN` برای شش هدف مالی |
| RES-3 | `gsi/stages/s20_derive.py` | ثابت `DECLARED_UNMEASURED` و پرکردن `ctx.extras["derive_coverage"]` |
| RES-2/3 | `gsi/warehouse/bridge.py` | تبدیل سیگنالِ بی‌مصرف به دو چک: `DERIVED_SOURCE_COVERAGE` و `UNKNOWN_COERCED_TO_ZERO` (هر دو **DEGRADED**) |

**اصول رعایت‌شده:**
- قرارداد عددی legacy **عوض نشد** — `BALANCE`/`CB_VALUE`/… همچنان `float` با پیش‌فرض صفر برمی‌گردند، چون `engines/risk.py` و `engines/commitment.py` روی آن حساب می‌کنند. تکمیل کامل قرارداد unknown/zero همچنان **F031** و متعلق به مالک داده است.
- شدت چک‌های تازه **DEGRADED** است نه BLOCK، چون این‌ها پوشش داده‌اند نه نقض قرارداد؛ ضمناً گیت بدون تصمیم مالک محصول سخت‌تر نمی‌شود.
- `provides` مرحله به‌روز شد تا `validate_graph` قرارداد کامل را ببیند.

**اثبات اصلاح (`rc_fixverify.py`):**

```
SWIFT_SENT_registered            : true
SWIFT_SENT_label                 : "ارسال سوئیفت"
SWIFT_SENT_owner                 : "TREASURY"
SWIFT_before_PAYMENT             : true
swift_in_stage_matrix            : true          ← قبلاً false
swift_row_status                 : ["OBSERVED"]
case_status                      : ["EVIDENCE_GAP"]  ← قبلاً "NO_STAGE_EVIDENCE"
payment_still_absent             : true          ← قرارداد F039 حفظ شد

ALLOCATED_AMOUNT                 : [0.0, 0.0]
ALLOCATED_AMOUNT_IS_UNKNOWN      : [true, false]  ← صفرِ نامعلوم از صفرِ واقعی جدا شد
BALANCE                          : [0.0, 250.0]
BALANCE_IS_UNKNOWN               : [true, false]
declared_unmeasured              : ["FIN_RECEIPT_DATE"]
```

سطر اول ورودی `NaN` منبع است و سطر دوم صفرِ واقعی منبع؛ هر دو `0.0` می‌مانند اما دیگر یکسان نیستند.

**بازاجرای کامل تست‌ها پس از اصلاح: `جمع کل: 1048 تست موفق | 0 ناموفق`، exit code 0 — **هیچ رگرسیونی ایجاد نشد**. لاگ کامل: `rc1/rcfix_full_suite.log`.**

---

## 7. فهرست blocker نهایی

بندهای ۱ تا ۶ عیناً از `KNOWN_LIMITATIONS.md` خودشان‌اند و تأیید می‌شوند. بندهای ۷ تا ۹ افزوده‌ی این بازبینی‌اند.

| # | Blocker | وضعیت |
|---|---|---|
| 1 | **F023** — جمع‌های legacy رفع تعهد همه نسخه‌های آرشیو را جمع می‌کنند | باز — تأیید شد |
| 2 | **F028** — `all_data_sheets` فقط بزرگ‌ترین شیت را می‌خواند | باز — تأیید شد |
| 3 | **F031** — تناقض unknown/صفر در فیلدهای مالی legacy | باز — تأیید شد (**RES-2 آن را تشدید می‌کرد؛ اکنون قابل‌تفکیک شده ولی بسته نیست**) |
| 4 | **F037** — احراز هویت/ACL اندپوینت و استقرار تأیید نشده | باز — تأیید شد |
| 5 | **N08 / F004** — شناسه پرونده فرایندی پایدار نیست | باز — تأیید شد |
| 6 | **RC03** — خرابی ایندکس SQLite با علت ناشناخته | باز — **من هم نتوانستم بازتولید کنم؛ بخش ۸** |
| 7 | **RES-4** — `ORC_BUYER`/`ORC_STATUS` بی‌تولیدکننده‌اند ولی `expert_roles` اولین مرجع را روی `ORC_BUYER` می‌گذارد | **افزوده — باز** |
| 8 | **RES-5** — `find_col` مسیر تازه‌ی BLOCK برای منابع بحرانی می‌سازد؛ smoke-test روی ۱۷ فایل واقعی الزامی است | **افزوده — پیش از استقرار** |
| 9 | **F019/N04** — حذف many-to-one همچنان رخ می‌دهد و گارد BLOCK آن غیرقابل‌فعال‌شدن است | **افزوده — باز** (RC آن را PARTIAL زده ولی در فهرست blocker نیاورده) |

**مهاجرت (نه blocker، ولی گام اجباری استقرار):** هر دیتابیس تولیدی موجود تا اجرای یک run کامل تازه، برای چت‌بات و Cash Flow خالی خواهد بود. این fail-closed عمدی است و باید در برنامه استقرار زمان‌بندی شود.

---

## 8. RC03 — آنچه من هم نتوانستم بازتولید کنم

خرابی گزارش‌شده واقعی است و در جدول‌های هسته است:

```
wrong # of entries in index wh_frame_run
wrong # of entries in index sqlite_autoindex_wh_frame_row_1
row 117 / 1021..1025 missing from index
```

**تلاش مستقل من (`rc_concurrency.py`):** ۴ پروسه همزمان × ۶ اجرای کامل روی یک DWH مشترک، هر اجرا با `wh.frame(...)` و `build_business_dwh(...)`.

```
workers                 : ["worker0: ok","worker1: ok","worker2: ok","worker3: ok"]
journal_mode            : "delete"
integrity_check         : [["ok"]]
foreign_key_violations  : 0
```

**نتیجه: فرضیه «رقابت نویسنده‌های همزمان» رد شد.** این شاهد منفی است و دامنه جست‌وجو را باریک می‌کند.

دو مشاهده‌ی قابل‌آزمون برای ادامه تحقیق — **فرضیه، نه یافته:**

1. انبار اصلی روی `journal_mode=delete` است، در حالی‌که `historical_store` و `knowledge_desk/indexer` صریحاً WAL می‌گذارند. با journaling نوع delete، کشته‌شدن سخت پروسه در میانه‌ی یک تراکنش بزرگ `wh_frame_row` محتمل‌ترین سناریوی باقی‌مانده است. آزمون: `SIGKILL` در میانه یک `wh.frame()` بزرگ، سپس `integrity_check`.
2. `Warehouse.read_db()` حالا `BEGIN` می‌زند و تا `close()` تراکنش خواندن باز می‌ماند. برای انسجام snapshot لازم است، ولی تعاملش با writerهای بلندمدت در بار واقعی اندازه‌گیری نشده.

**تصمیم آن‌ها که این را blocker نگه دارند و دیتابیس خراب را ترمیم نکنند تا گیت سبز شود، درست بوده و باید همین‌طور بماند.**

---

## 9. توصیه پذیرش

**۱. اکنون:** RC1 را به‌عنوان review candidate بپذیرید، patch بخش ۶ را اعمال کنید و فهرست blocker بخش ۷ را جایگزین نسخه فعلی کنید.

**۲. پیش از هر استقرار (به ترتیب):**
- RES-5: smoke-test `find_col` روی هر ۱۷ workbook واقعی — ارزان و می‌تواند یک قطعی کامل را پیش‌گیری کند.
- RC03: آزمون ۱ بخش ۸ را اجرا کنید؛ تا روشن‌نشدن علت، استقرار متوقف بماند.
- گام مهاجرت: یک run کامل تازه روی کپی داده تولیدی، و تأیید اینکه چت‌بات/Cash Flow پس از آن پر می‌شوند.

**۳. پس از آن، و فقط با مالک داده:** B3 (رسید مالی در برابر دریافت اسناد)، B5 (دانه موجودی Oracle)، B6 (هویت PR هدر در برابر `po.Purchase Requisition`)، B9 (full/delta هر منبع)، B10 (ریشه پرونده فرایندی). این‌ها F003/F013/F014/F022/F029/N08 را باز نگه داشته‌اند و **با کد قابل حل نیستند**.

**۴. آنچه نباید انجام شود:** یک اجرای سبز synthetic نباید به امضای مالی یا عملیاتی تبدیل شود. خودشان این را نوشته‌اند و من تکرارش می‌کنم.

---

## 10. حدود اعتبار این بازبینی

- هیچ فایلی از RC1 اصلی تغییر نکرد؛ اصلاح‌ها روی یک کپی اعمال و به‌صورت patch تحویل شدند.
- probeها synthetic‌اند: **وجود یا رفع نقص روی ورودی مشخص** را اثبات می‌کنند، نه نرخ وقوع در داده تولیدی.
- آزمایش نشد: شبکه سازمانی، Outlook COM، مرورگر واقعی و دانلود رسانه، مهاجرت دیتابیس تولیدی، و reconciliation واقعی SAP/NTSW/Oracle/گمرک.
- سنجش کارایی انجام‌شده‌ی خودشان (۱٫۳۳s → ۳٫۰۹s و دوبرابرشدن حجم DB روی ۳۰۰ ردیف) را بازتولید نکردم؛ اما صادقانه به‌عنوان **هزینه** گزارش شده و همین درست است. اندازه‌گیری در مقیاس تولید هنوز لازم است.
- همه اعداد نقل‌شده خروجی مستقیم probeهای همراه‌اند و با اجرای دوباره قابل بازتولیدند.
