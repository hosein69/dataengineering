# OPUS_REVIEW — بازبینی مستقل تحلیل Astra

**هدف:** یافتن Blind Spotهای تحلیل Phase 0.
**ورودی:** `GSI_V29_7_6_SAP_SEMANTIC_DWH_SMART_CHATBOT.zip` (بدون تغییر) + `ARCHITECTURE_BASELINE.md` + `FINDINGS_REGISTER.md` + `DECISION_LOG.md` + `TEST_AND_INVARIANTS.md`.
**روش:** ابتدا کد مستقل خوانده شد، سپس ادعاهای Astra با probe اجرایی راستی‌آزمایی شد. هیچ فایل اصلی پکیج تغییر نکرده است.
**تاریخ:** 2026-09-22

---

## 0. خلاصه مدیریتی

| سنجه | نتیجه |
|---|---|
| یافته‌های Astra | 40 |
| CONFIRMED | 36 |
| PARTIALLY_CONFIRMED | 2 (F014, F015) |
| REJECTED | 1 (F006) |
| INSUFFICIENT_EVIDENCE | 1 (F029) |
| یافته جدید با شاهد مستقیم | 13 (N01–N13) |
| Probe مستقل اجراشده | 7 مجموعه (OP-01 … OP-07)، همه بازتولیدشده |

**ارزیابی کلی تحلیل Astra:** از نظر فنی قابل‌اتکاست. سه یافته CRITICAL هر سه بازتولید شدند و مکانیزم‌شان دقیقاً همان است که ثبت شده. تفکیک raw/native/canonical، تشخیص نبود publication isolation، و پرهیز از ادعای مالی جعلی، درست و حرفه‌ای است.

**اما چهار نقطه‌کور روشی وجود دارد:**

1. **تحلیل ایستا بدون راستی‌آزمایی ستون واقعی.** F006 صرفاً از روی نام frame استنتاج شده و **غلط است**: فریم `moghavemat/main` اصلاً ستون canonical `KEY_PR`/`KEY_MATERIAL` ندارد، پس هیچ رابطه‌ای تولید نمی‌کند (OP-02). Astra این را اجرا نکرده بود.
2. **ریسکی که در جدول Risk coverage ذکر شده ولی Finding ID نگرفته.** `dwh_registration_hub` در جدول ریسک آمده اما هیچ‌جا ثبت نشده، درحالی‌که cross-product واقعی تولید می‌کند و در UI انبار نمایش داده می‌شود (N02).
3. **یافته‌های نمونه‌ای به‌جای ممیزی کامل.** F021 دو ستون تاریخ را نام می‌برد؛ ممیزی مکانیکی producer/consumer نشان می‌دهد **۱۰ از ۱۰۴** فیلد مشتق هیچ تولیدکننده‌ای ندارند و یکی از آن‌ها یک ثابت جعلی به کل گزارش تزریق می‌کند (N05، OP-06).
4. **گیت‌هایی که Astra آن‌ها را «کنترل موجود» فرض کرده ولی مرده‌اند.** جدول «کنترل‌های موجود» صحت `safe_merge row count`، `SCHEMA_DRIFT` و `PROCESS_ROW_PRESERVATION` را مفروض گرفته؛ هر سه در شرایط واقعی غیرقابل‌فعال‌شدن یا خودغیرفعال‌شونده‌اند (N01، N04، N07).

> **هشدار روش‌شناختی:** هیچ یافته‌ای در این سند صرفاً به دلیل ترجیح معماری Critical نشده است. جایی که شدت Astra با شاهد نمی‌خواند، صریح نوشته شده و **پایین** آمده است (F015، F029).

---

## 1. Confirmed Findings

### 1.1 تأییدشده و بازتولیدشده (probe اجرایی)

| ID | Astra | Verdict | شاهد مستقل |
|---|---|---|---|
| F001 | CRITICAL | **CONFIRMED** | OP-05 |
| F002 | CRITICAL | **CONFIRMED** | OP-02 |
| F004 | CRITICAL | **CONFIRMED** | OP-04 |
| F005 | HIGH | **CONFIRMED** | OP-04 |
| F007 | HIGH | **CONFIRMED** | OP-04 |
| F008 | HIGH | **CONFIRMED** | OP-04 |
| F009 | HIGH | **CONFIRMED** (اثر مشروط به داده) | OP-04 |
| F017 | HIGH | **CONFIRMED + تشدید‌شده** | OP-03 |
| F018 | HIGH | **CONFIRMED + تشدید‌شده** | OP-03، OP-05 |
| F019 | HIGH | **CONFIRMED + تشدید‌شده** | OP-01 |
| F020 | MEDIUM | **CONFIRMED؛ شدت باید HIGH شود** | OP-01 |
| F021 | HIGH | **CONFIRMED + دامنه‌ی بسیار وسیع‌تر** | OP-06 |
| F025 | HIGH | **CONFIRMED + تشدید‌شده** | OP-03 |

**F001 — نشت اجرای مسدودشده به چت‌بات.** بازتولید کامل: pointer روی R1 ماند، اما PR ساخته‌شده در اجرای مسدود (`1000000777`) برای چت‌بات **قابل مشاهده** بود و پاسخ با برچسب `As-of published DWH run: R1` برگشت. علت دقیقاً همان است که Astra گفته: `_published_run()` فقط برچسب متن است و هیچ‌یک از کوئری‌های `dwh_fact_*` / `dwh_relation` / `dwh_entity` شرط `last_seen_run` ندارند. **افزوده:** همین نقص در `app/warehouse_view.py:75-80` نیز هست — کل نمای انبار (dims/relations/unresolved/hub/OMPI) بدون فیلتر run خوانده می‌شود.

**F002 — ناپدیدشدن شواهد Cash Flow.** بازتولید عددی: پس از publish اجرای R1 و سپس اجرای مسدود R2 روی همان داده، تعداد ردیف‌های `dwh_fact_source_row` با `last_seen_run = R1` **صفر** شد و همان ردیف به R2 منتقل شد. چون `cashflow/dwh.py:_published_source_frames` دقیقاً `WHERE last_seen_run = <published rid>` می‌زند، شواهد نسخه سالم منتشرشده حذف می‌شود.

**F004 — ادغام پرونده‌ها از طریق MATERIAL.** دو ORDER مستقل با متریال مشترک → `1` پرونده با `ORDER_COUNT=2`. **نکته‌ای که Astra نگفته:** `attach_process_state` برای ردیف‌هایی که به چند component می‌خورند برچسب `AMBIGUOUS_LINK` می‌گذارد؛ اما وقتی union-find دو پرونده را **یکی** کرده، فقط یک component وجود دارد و این محافظ هرگز فعال نمی‌شود. یعنی نقص، دقیقاً همان گاردی را که برای ابهام طراحی شده خنثی می‌کند.

**F005 — حذف observationهای تکراری.** دو ردیف native با محتوای یکسان → `1` ردیف `SOURCE_OBSERVATION`. چون `s54` انتظار `generic_rows == expected_source_rows` دارد، `row_preservation_ok=False` و گیت `PROCESS_ROW_PRESERVATION` با شدت BLOCK کل انتشار را متوقف می‌کند. ریشه: `_row_ref` هش محتواست و `idx` فقط برای ردیف کاملاً خالی استفاده می‌شود.

**F007/F008/F009 — NTSW.** هر سه بازتولید شدند:
- `100 USD + 100 EUR` → `NTSW_ALLOCATED_AMOUNT = 200.0` با `NTSW_REQ_CURRENCY = EUR`.
- وضعیت «تایید نشده» → `ALLOCATED` (زیررشته «تایید»).
- همان `COMMIT_ROW=7` دوبار → `INITIAL_COMMIT=200`, `BALANCE=100`.

**شاهد تقویتی که Astra استفاده نکرده:** خود کد می‌داند این قواعد لازم‌اند و فقط در یک مسیر اعمالشان کرده — `_agg_commitment` یک گارد صریح چندارزی دارد (`raise ValueError`)، اما `_agg_allocation` ندارد؛ `_allocation_request_ledger` روی `REQ_ROW` دِدوپ می‌کند، اما `_agg_commitment` روی `COMMIT_ROW` دِدوپ نمی‌کند هرچند آن را map کرده است. این عدم‌تقارن درون‌فایلی، قوی‌ترین شاهد است.

**F017 — انتساب PO به PR/Material هدر.** بازتولید با سناریوی «PR Item با چند PO Item» و PR متعارض:

| po_key | po_item | pr_key ذخیره‌شده | pr_item ذخیره‌شده | po.Purchase Requisition واقعی | material ذخیره‌شده | po.Material واقعی |
|---|---|---|---|---|---|---|
| 4500000001 | 10 | 1000000001 | 00010 | 1000000001 | PRMAT | POMAT-A |
| 4500000002 | 20 | **1000000001** | **00090** | **1000000009** | **PRMAT** | **POMAT-B** |

**تشدید نسبت به Astra:** `business_dwh.py` برای `pr_item` **ستون اختصاصی PO** (`SAP_PO_PR_ITEM`) را ترجیح می‌دهد ولی برای `pr_key` **ستون هدر** را می‌گیرد. نتیجه، یک ارجاع ترکیبی `(1000000001, 00090)` است که **در هیچ ردیف منبعی وجود ندارد** — این «انتساب اشتباه» نیست، «ساخت شناسه غیرموجود» است. همین آلودگی در `dwh_relation` هم می‌نشیند: `PR 1000000001 → PO 4500000002` و `PO 4500000002 → MATERIAL PRMAT`، بدون هیچ رکورد `dwh_unresolved_relation`.

**F018 — Workflow observation به‌عنوان event.** دو تأیید جدا:
- *چت‌بات:* برای PRی با اقلام `2` و `10` که قلم `10` تازه‌تر است (Changed On 2026-06-01)، `_pr_semantic` با `ORDER BY pr_item` و `pr_rows[-1]` مقدار قلم `"2"` را «آخرین» گرفت و `SUPPLIER-OLD` / `2026-01-01` را گزارش کرد. علت ریشه‌ای که Astra نگفته: `_clean_item` صفرهای ابتدایی را حذف می‌کند (`00010`→`10`)، یعنی همان normalization، تنها خاصیتی را که مرتب‌سازی لغوی SAP را درست می‌کرد از بین برده است.
- *انباشت نامحدود:* `dwh_fact_sap_workflow` از `3` به `7` ردیف رسید وقتی همان export با یک ردیف اضافه در ابتدا دوباره ingest شد. چون `SAP_SOURCE_ROW` موقعیتی است و جزو `workflow_key` است، جابه‌جایی ردیف‌ها کلیدهای تازه می‌سازد و **هیچ مکانیزمی ردیف قدیمی را بازنشسته نمی‌کند**. `workflow_events` در پاسخ چت‌بات = `len(wf_rows)`، پس هر ingest مجدد شمارش رویداد را متورم می‌کند.

**F019/F020 — merge.** بازتولید:
- سه ردیف LC روی یک BL → فقط `LC-1` باقی ماند.
- کلید مرکب `("","")` → `"|"` و match شد.
- **فراتر از Astra:** کلید تک‌ستونی `NaN` هم match می‌کند، چون `astype(str)` مقدار را به رشته `"nan"` تبدیل می‌کند و فیلتر خالی `str.strip() != ""` آن را نمی‌گیرد.
- **فراتر از Astra:** برخورد delimiter بازتولید شد: `("A|B","")` با `("A","B|")` منطبق می‌شود.

به همین دلیل شدت F020 باید از MEDIUM به **HIGH** برود: مسئله فقط ردیف بدون کلید نیست؛ هر ردیف با کلید `NaN` قابل‌اتصال به ردیف نامرتبط است.

**F025 — حفره nullable-key.** بازتولید و به‌مراتب بدتر از آنچه ثبت شده:

| سناریو | REQUIRED_COLUMNS | NULL_OR_BLANK_KEY | GRAIN_UNIQUENESS | نتیجه |
|---|---|---|---|---|
| دو ردیف `sap/pr_items` با PR یکسان و item خالی | pass | اجرا نشد | **pass** | گیت رد نمی‌کند |
| فریم `ilappend/main` که **همه** کلیدهایش خالی است | pass | اجرا نشد | **pass** | گیت رد نمی‌کند |

وقتی `nullable_key=True` باشد، بلوک `if not c.nullable_key:` هر سه چک `NULL_OR_BLANK_KEY` / `PARTIAL_KEY_EVIDENCE` / `USABLE_KEY_EVIDENCE` را رد می‌کند، و `dup_base = df.loc[complete_mask]` خالی می‌ماند پس یکتایی هم بی‌معنا می‌شود. `ilappend` در `critical_sources` است — یعنی منبعی که خرابی‌اش باید کل انتشار را متوقف کند، می‌تواند کاملاً بی‌کلید و «سالم» از گیت رد شود.

**F021 — مسیر تولیدکننده/مصرف‌کننده.** ممیزی مکانیکی (OP-06) روی کل `DERIVED`:

```
derived_targets: 104
fully_unreachable_targets: 10
```

`SATA_DATE`, `DISCHARGE_DATE`, `ARRIVAL_DATE`, `PARTIAL_CLEAR_DATE`, `CLEAR_AMOUNT`, `BL_DATE`, `SEGMENT`, `BARAT_DUE`, `MATERIAL_STATUS`, `BUYER` — هیچ adapterی ستون کاندیدشان را تولید نمی‌کند. برای `ORC_STATUS` و `ORC_BUYER` علت قطعی است: در `a40_oracle.EXCLUDED_HEADERS` و در `dataio/reader.py` لیست `forbidden` هنگام خواندن **حذف می‌شوند**. پیامدهای این مورد در N05 آمده است.

### 1.2 تأییدشده با شاهد کد (بدون نیاز به probe)

| ID | Verdict | شاهد کلیدی |
|---|---|---|
| F003 | **CONFIRMED** | `business_dwh.build` فقط upsert با `last_seen_run`؛ هیچ tombstone/expire؛ خواننده‌ها همه را می‌خوانند |
| F010 | **CONFIRMED** | `adapters/base.load` برای منبع غیرالزامی `return {}` بدون exception؛ `source_runtime_checks` فقط `source_failures` (exceptionها) را می‌بیند؛ `validate_sources` فقط frameهای موجود را می‌پیماید |
| F011 | **CONFIRMED + تشدید‌شده** | زیر |
| F012 | **CONFIRMED** | `bridge.run_pipeline`: `pipeline._run_warehouse(build_report)` (نوشتن اکسل روزانه + extracts + audit) **قبل از** `validate_sources`/`build_business_dwh`/`evaluate` |
| F013 | **CONFIRMED** | `a40_oracle.transform` پس از انتخاب `chosen`، فیلدهای STOCK/DAILY_NEED/CARS/FOREIGN_SHARE را با `max` بین شیت‌ها بازنویسی می‌کند، درحالی‌که docstring فایل می‌گوید «values are never summed or filled across sheets… avoids creating synthetic hybrid rows» |
| F016 | **CONFIRMED** (بخش ارز) | `moghavemat._aggregate`: `PI_VALUE_SUM = float(g[PI_LINE_VALUE].sum())` و `CURRENCY = first_valid(...)` — هیچ گارد چندارزی، برخلاف `_agg_commitment` |
| F022 | **CONFIRMED** | `a20_sata`: `DOC_RECEIVED ← «دریافت اسناد»` → `s20_derive: FIN_RECEIPT_DATE ← SATA_DOC_RECEIVED` → `s80_eventlog:83` برچسب **"Financial Receipt Booked"/«ثبت رسید مالی»** در فاز RELEASE، و مصرف در `engines/risk.py:61` و `engines/commitment.py:207` |
| F023 | **CONFIRMED** | `fx_obligation.totals_by_currency`: `SELECT … FROM wh_measure WHERE measure IN (…)` — بدون هیچ فیلتر file/run/published |
| F024 | **CONFIRMED** | `indexer.build_index`: root ناموجود → `continue` با `seen` خالی → sweep همه را `DELETED` می‌کند؛ و مسیر سریع `mtime_ns+size` برابر → `continue` **بدون** `status='ACTIVE'`، پس بازگرداندن فایل دست‌نخورده احیا نمی‌کند |
| F026 | **CONFIRMED + تشدید‌شده** | `cashflow/dwh.py` حلقه FX فقط `_source_reg()` می‌گیرد؛ `order_to_reg` ساخته و برای `moghavemat` استفاده می‌شود ولی برای FX/credit نه. `_event` با `case_id` خالی **بی‌صدا** `""` برمی‌گرداند — هیچ رکورد unresolved ثبت نمی‌شود |
| F027 | **CONFIRMED** | `ref = _first(r.get("NTSW_COMMIT_ROWS"), …)` — `COMMIT_ROWS` شمارنده است؛ `source_event_id = "1:COMMITMENT"` برای هر REG تک‌تعهدی؛ `engine.py:133-141` روی `(source, source_event_id)` تعارض cross-case می‌سازد |
| F028 | **CONFIRMED** | `reader._read_targets`: در شاخه `all_data_sheets` فقط `best` (بیشترین `len`) هر فایل اضافه می‌شود |
| F030 | **CONFIRMED؛ شدت کم‌برآورد** | `core/columns.find_col` فاز ۲: `nc in col_norm or col_norm in nc` و score = `rank*10 + extra`؛ در تساوی، **ترتیب ستون در اکسل** برنده را تعیین می‌کند |
| F031 | **CONFIRMED + دوطرفه** | `DERIVED`: `"BALANCE": (["NTSW_BALANCE"], 0, True)` و `"CB_VALUE": ([...], 0, True)`؛ `DeriveStage.run` بدون شرط default را اعمال می‌کند. جهت معکوس در N10 |
| F032 | **CONFIRMED + تشدید‌شده** | `cashflow/dwh.SOURCE_PRIORITY` هاردکد؛ `config/authority._POLICY = _load_policy()` در **سطح ماژول** اجرا می‌شود، پس reload پیکربندی روی آن اثر ندارد |
| F033 | **CONFIRMED + تشدید‌شده** | fallback در `pipeline.load_sources` فقط وقتی رخ می‌دهد که `load()` **raise** کرده باشد؛ اما `wh.frame(data,'standardized',…)` فقط در مسیر موفق `load()` اجرا می‌شود. یعنی اجرای degraded هیچ frame استانداردی برای run جدید ثبت نمی‌کند و اگر منتشر شود، **fallback دفعه بعد چیزی پیدا نمی‌کند**. fallback عملاً فقط یک‌بار کار می‌کند |
| F034 | **CONFIRMED** | `operational_search`/`operational_chunks`: `except Exception: return []`؛ `_ID_RE = (?<!\d)(\d{6,16})(?!\d)` فقط عددی |
| F035 | **CONFIRMED** | `query.search`: `" OR ".join(...)` روی FTS و `OR` روی LIKE؛ هیچ آستانه relevance؛ `status="ANSWERED_OPERATIONAL" if op_hits else …` — یعنی هر عدد ۶ تا ۱۶ رقمی در سؤال، پاسخ را «عملیاتی و پاسخ‌داده‌شده» می‌کند حتی اگر سؤال درباره رویه باشد |
| F036 | **CONFIRMED** | `grep -rn "historical_runtime\|WarehouseRun"` خارج از خود ماژول: **صفر مصرف‌کننده** |
| F037 | **CONFIRMED** | `service.py`: `Access-Control-Allow-Origin: *`، بدون auth، `do_GET` برای هر مسیر UI می‌دهد؛ `config.host = "0.0.0.0"`؛ `operational_chunks` همه PRهای `dwh_dim_pr` را بدون scope کاربر export می‌کند |
| F038 | **CONFIRMED** | `DocCheckAdapter.transform` → `dedupe_on_key(out, KEY_ORDER, keep_by=SUBMIT_DATE)` و `return {"main": out}` — هیچ frame native سند |
| F039 | **CONFIRMED + دامنه بیشتر** | `process_evidence`: شاخه `credit` با `CRD_SWIFT_DATE` رویداد `PAYMENT` («پرداخت / وصول ذی‌نفع») emit می‌کند؛ **همچنین** شاخه `fx_transaction` تاریخ `FX_SWIFT_DATE` را به‌عنوان تاریخ `PAYMENT` می‌پذیرد |
| F040 | **CONFIRMED** | `wh.publish(rid,…)` در `bridge.py` **بیرون از** `with wh.run(...)` است، پس بیرون از WriterLock؛ و `_ensure_schema` با `if 'wh_meta' in existing and version==1: return` از اجرای `SCHEMA` صرف‌نظر می‌کند، پس DB قدیمیِ `user_version=1` جدول‌های بعداً اضافه‌شده را نمی‌گیرد |

**تشدید F011 — محتمل‌ترین مسیر قطعی انتشار که Astra کم‌وزن دیده:**
`NtswAdapter.transform` دو `raise ValueError` بی‌قید دارد: یکی برای چندارزی‌بودن تعهد، و یکی برای `isna()` روی `INITIAL_COMMIT`/`BALANCE`. چون `std()` هر ستون یافت‌نشده را با `""` پر می‌کند و `number("")` مقدار `NaN` می‌دهد، **یک سلول خالی در «مانده تعهد» یا یک تغییر نام هدر در فایل NTSW** کل منبع NTSW را raise می‌کند. NTSW در `critical_sources` است ⇒ `SOURCE_LOAD_FAILED` با شدت BLOCK ⇒ **انتشار تمام دامنه‌ها (گزارش + DWH) متوقف می‌شود**.
تناقض سیاستی که Astra اشاره کرده اما شاهدش را کامل نیاورده: در `sources.yaml` نقش `abbasi` صراحتاً «enrichment لجستیکی درجه‌دوم؛ **سازنده جمعیت نیست**» تعریف شده، ولی `abbasi` جزو `critical_sources` است؛ در مقابل `moghavemat` که Tier-1 و سازنده جمعیت است، **critical نیست**. یعنی لیست بحرانی دقیقاً وارونه سیاست مستند است.

---

## 2. Rejected Findings

### F006 — «تبدیل frame مشتق به شاهد مستقیم» → **REJECTED**

**ادعای Astra:** «تنها SAP semantic frames از relation extraction مستثنا هستند؛ برای moghavemat/main … زوج کلیدها DIRECT_COOBSERVED می‌شوند. main تجمیعی است و first_validهای مستقل دارد.»

**بازتولید (OP-02):** فریم‌های واقعی adapter به `business_dwh.build` داده شد.

```
any_relation_from_main_frame : false
cross_pair_PR1_to_M_SECOND   : false
relations_after_run1         : همه با frame = "lines"
```

**چرا ادعا غلط است:** `_source_business_keys` فقط ستون‌های canonical در `ENTITY_COLS` را می‌خواند (`KEY_ORDER`, `KEY_MATERIAL`, `KEY_PR`, …). `moghavemat._aggregate` خروجی‌اش را با نام‌های **پیشونددار** می‌سازد — `MOGH_MATERIAL` و `MOGH_KEY_PR` — و تنها کلید canonical آن `KEY_ORDER` است. پس `main` هیچ زوجی ندارد و هیچ رابطه‌ای تولید نمی‌کند. فرضیه «دو first_valid مستقل به رابطه DIRECT تبدیل می‌شود» در این کد **اتفاق نمی‌افتد**.

سایر frameهای نام‌برده‌شده در F006 هم در گرین خودشان co-observation واقعی دارند:
- `moghavemat/lines` — ردیف native سطح قلم؛ ORDER/MATERIAL/PR واقعاً هم‌ردیف‌اند.
- `moghavemat/inventory` — تجمیع روی خودِ `(ORDER, MATERIAL)`؛ زوج، کلید گروه است.
- `moghavemat/order_material_pr_item` — تجمیع روی خودِ چهار کلید.
- `ntsw/allocation` و `ntsw/commitment` — فقط `KEY_REG` دارند، پس زوجی نمی‌سازند.

**آنچه واقعاً درست است و باید جای F006 بنشیند:** دو نقص مستقل که Astra آن‌ها را به F006 نچسبانده — انتساب غلط PR/Material در `sap/raw_rows` (**F017**) و cross-product در `dwh_registration_hub` (**N02**).

**یک مشاهده‌ی فرعی F006 که درست است** (`evidence_count` متورم می‌شود) مستقل بازتولید شد و به‌عنوان **N09** ثبت شده است.

---

## 3. Insufficient Evidence

### F029 — «جداسازی صریح Export Clearance از Import پیدا نشد» → **INSUFFICIENT_EVIDENCE**

آنچه قابل‌اثبات است: `pattern: "*Clearance*"`، `multi_file: true`، و نبود فیلد جهت در `ClearanceAdapter.COLUMN_MAP` — همگی تأیید می‌شوند.
آنچه قابل‌اثبات **نیست**: اینکه فایل ExportClearanceی وجود دارد، اینکه کلیدهایش با import مشترک است، و اینکه KPI واردات آلوده می‌شود. خود Astra نوشته «وجود چنین فایل در محیط فعلی UNKNOWN / NEEDS EVIDENCE» — اما همان مورد را **HIGH** ثبت کرده است. این با معیار خودش (`D005: severity بر پیامد بالقوه و confidence بر سطح evidence`) نمی‌خواند.

**پیشنهاد:** از فهرست یافته‌ها خارج و به بخش Business Rule Ambiguities منتقل شود، با یک تست fixture «export-only» به‌عنوان شرط پذیرش.

---

## 4. Partially Confirmed

### F014 — جمع‌پذیری تکرار درون شیت Oracle → **PARTIALLY_CONFIRMED**

رفتار تأیید می‌شود: `_collapse_material_grain` پس از حذف تکرارهای دقیق، `STOCK_IKCO`/`STOCK_SAPCO`/`CARS_ON_FLOOR` را **جمع** و `DAILY_NEED` را **max** می‌کند؛ هیچ کلید location/bucket در `COLUMN_MAP` نیست. اما اینکه این در داده واقعی double-count می‌سازد یا نه، بدون فایل واقعی قابل اثبات نیست.

**شاهد قوی‌تری که Astra نیاورده:** خودِ قرارداد دانه، درون‌متناقض است — همان فیلد `STOCK_IKCO` **درون یک شیت additive** (`sum`) و **بین دو شیت non-additive** (`max`) تعریف شده. این تناقض بدون داده تولید هم قابل طرح با مالک داده است.

### F015 — «Flat report فقط نماینده اول را می‌گیرد» → **PARTIALLY_CONFIRMED؛ شدت بیش‌برآورد**

مکانیزم تأیید می‌شود (`MOGH_MATERIAL` و `MOGH_KEY_PR` هر دو `first_valid`). اما توصیف Astra («بی‌صدا»، HIGH) با کد نمی‌خواند:
- `log.warning` صریح برای سفارش‌های چندمتریاله و چند-PR صادر می‌شود؛
- `health.current().find(... WARN ...)` ثبت می‌شود؛
- `MATERIALS_ALL`, `PARTS_ALL`, `MULTI_MATERIAL`, `PRS_ALL`, `PR_COUNT`, `MULTI_PR` نگه داشته می‌شوند؛
- frame مستقل `order_material_pr_item` با `EVIDENCE_COUNT` و `SOURCE_ROWS` وجود دارد؛
- کامنت کد خودش این را «نقطه کور واقعیِ داده» اعلام کرده است.

این یک **projection اعلام‌شده** است، نه data loss پنهان. ریسک باقی‌مانده «مصرف‌کننده‌ای که projection را کل سفارش بخواند» است — که یک Architecture Concern است، نه یافته HIGH. **پیشنهاد شدت: MEDIUM.**

---

## 5. New Findings

همه با شاهد مستقیم از code / schema / data contract / test / source structure. هیچ‌کدام به دلیل ترجیح معماری Critical نشده‌اند.

### N01 — HIGH — SCHEMA_DRIFT تغییر هدر منبع را نمی‌بیند؛ فیلد کسب‌وکاری بی‌صدا خالی می‌شود

**دسته:** SAP schema evolution · Source Authority · Silent Data Loss
**شاهد:** `warehouse/reliability.py:schema_drift_checks` + `adapters/base.py:std` · probe OP-07

`schema_drift_checks` روی `pipeline.sources` یعنی frameهای **استانداردشده** اجرا می‌شود، نه روی شیت خام. `std()` هر ستون یافت‌نشده را با `""` می‌سازد، پس مجموعه ستون‌های frame استاندارد **ثابت** است.

بازتولید: هدر `Name of Supplier` در export به `Supplier Name (new)` تغییر نام داد.

```
cols_identical            : true
fingerprint_identical     : true
supplier value            : "ACME"  →  ""
SCHEMA_DRIFT              : severity=WARN, passed=TRUE, added=[], removed=[], dtype_changed={}
```

یعنی داده کسب‌وکاری کاملاً از بین رفت و **هیچ چکی fail نشد**:
- `REQUIRED_COLUMNS` (BLOCK) هرگز fail نمی‌کند، چون ستون استانداردشده همیشه ساخته می‌شود؛
- `SCHEMA_DRIFT` fingerprint یکسان می‌بیند؛
- تنها ردپا یک `log.warning` در `std()` است که به هیچ `Check` تبدیل نمی‌شود.

این مستقیماً با docstring خودِ تابع در تضاد است: «This makes upstream Excel/header changes visible until explicitly reviewed.»

> در پروژه‌ای که ورودی‌اش ۱۷ فایل اکسل دستی است، این محتمل‌ترین مسیر «گزارش تازه ولی غلط» است.

### N02 — HIGH — نمای `dwh_registration_hub` cross-product تولید می‌کند و در UI انبار نمایش داده می‌شود

**دسته:** Fan-out · Ambiguous Relation · DWH Referential Integrity
**شاهد:** `business_dwh.py` (تعریف VIEW) · `app/warehouse_view.py:78` · probe OP-02

VIEW دو `LEFT JOIN` مستقل روی `dwh_relation` می‌زند و حاصل‌ضرب دکارتی REG×ORDER هر REG_FILE را برمی‌گرداند. بازتولید با یک REG_FILE، دو REG و دو ORDER (که هیچ‌کدام در یک ردیف native با هم دیده نشده‌اند):

```
900000001 | 88000001 | ORD-A
900000001 | 88000001 | ORD-B
900000001 | 88000002 | ORD-A
900000001 | 88000002 | ORD-B
```

چهار «رابطه» از صفر شاهد مستقیم. این جدول در `app/warehouse_view.py` مستقیماً به کاربر نشان داده می‌شود و در `SYSTEM_RELIABILITY_V29_FA.md` به‌عنوان دارایی انبار معرفی شده است.

**انصاف فنی:** مسیر Cash Flow از این نما استفاده نمی‌کند؛ `cashflow/dwh._candidate_maps` هاب را خودش بازمی‌سازد و در تعارض هم‌اولویت، `DWH_EQUAL_PRIORITY_KEY_CONFLICT` ثبت می‌کند و resolve نمی‌کند. یعنی محافظ در Cash Flow هست و در VIEW نیست.

**چرا Blind Spot است:** Astra این را فقط در سطر «Fan-out» جدول Risk coverage آورده و هیچ Finding ID، شدت یا fix برایش ثبت نکرده. تست موجود `tests/test_v29_business_dwh.py:17` هم فقط حالت ۱:۱:۱ را می‌آزماید و N:M را اصلاً لمس نمی‌کند.

### N03 — HIGH — طبقه‌بند وضعیت فارسی در لایه process، وضعیت‌های رایج را وارونه می‌کند

**دسته:** Process Continuity · Chatbot Unsupported Conclusions
**شاهد:** `resolve/process_evidence.py:_state_from_text` · probe OP-04

```
"مورد تایید"     → NEGATIVE_OBSERVED      ← «رد» زیررشته «مورد» است
"تایید نشده"     → POSITIVE_OBSERVED      ← نفی دیده نمی‌شود
"تأیید نشده"     → POSITIVE_OBSERVED
"در گردش"        → NEGATIVE_OBSERVED      ← «رد» زیررشته «گردش» است
"مورد بررسی"     → NEGATIVE_OBSERVED
"بازگشت داده شد" → OBSERVED
```

این خروجی مستقیماً `EVIDENCE_STATE` هر observation را می‌سازد و از آنجا `PROCESS_STATUS = "NEGATIVE_EVIDENCE_PRESENT"` و ستون `STATUS` در `_stage_matrix`. یعنی یک سفارش سالم با وضعیت «مورد تایید» در ماتریس فرایند «شاهد منفی» می‌شود.

Astra فقط نسخه‌ی NTSW این باگ را ثبت کرده (F008). الگوی «تطبیق زیررشته بدون نفی و بدون مرز واژه» دست‌کم در **چهار** نقطه تکرار شده است:
`a50_ntsw.state`، `process_evidence._state_from_text`، `_agg_commitment` (توکن `"باز"` که زیررشته «بازگشت»/«بازنگری» است)، و قاعده SETTLEMENT (`"رفع" in rel and "نشده" not in rel` که «عدم رفع تعهد» را رفع‌شده می‌گیرد).

### N04 — HIGH — گارد انفجار سطر مرده است؛ یک چک BLOCK هرگز نمی‌تواند فعال شود

**دسته:** Fan-out · Silent Data Loss
**شاهد:** `dataio/merge.py:safe_merge` · `warehouse/reliability.py:source_runtime_checks` · probe OP-01

`safe_merge` پیش از join همیشه `r = dedupe_on_key(r, key, …)` می‌زند، پس سمت راست تضمیناً روی کلید یکتاست و `n_after != n_before` **هرگز** رخ نمی‌دهد.

```
many_to_one_rhs_rows_in            : 3
many_to_one_rhs_values_kept        : ["LC-1"]
row_explosion_raised_on_duplicate_rhs : false
```

نتیجه‌ها:
- `RowExplosionError` کد مرده است؛
- `pipeline.merge_failures` از این مسیر هرگز پر نمی‌شود؛
- پس `Check(..., "JOIN_CARDINALITY_VIOLATION", BLOCK, ...)` یک گیت BLOCK است که **در عمل غیرقابل‌فعال‌شدن** است؛
- و آنچه docstring ماژول «ادغام left-join تضمین‌شده بدون تکثیر سطر» می‌نامد، در واقع «حذف بی‌صدای ردیف‌های سمت راست» است.

Astra در جدول «کنترل‌های موجود» نوشته `safe_merge row count` ثابت‌ماندن تعداد سطر چپ را **اثبات می‌کند** — این درست است ولی گمراه‌کننده: چیزی اثبات نمی‌شود چون شکست ساختاراً ممکن نیست.

### N05 — HIGH — ستون‌های مشتقِ بی‌تولیدکننده، یک ثابت جعلی و یک شاخه مرده در گزارش رسمی می‌سازند

**دسته:** Ambiguous Mapping · Orphan Evidence
**شاهد:** `stages/s20_derive.py` · `adapters/a40_oracle.py:EXCLUDED_HEADERS` · `dataio/reader.py` (`forbidden`) · `resolve/expert_roles.py:59` · probe OP-06
(ریشه مشترک با F021؛ اما سه پیامد زیر در هیچ یافته‌ای ثبت نشده‌اند.)

1. **ثابت جعلی:** `"SEGMENT": (["BL_SEGMENT"], "تولیدی", False)`. چون `BL_SEGMENT` هیچ تولیدکننده‌ای ندارد و `DeriveStage.run` بدون شرط default را می‌نشاند، **هر ردیف گزارش** مقدار «تولیدی» می‌گیرد. این یک مقدار پیش‌فرض نیست؛ یک ادعای کسب‌وکاری است که به‌صورت داده ارائه می‌شود.
2. **شاخه مرده در تفکیک موجودی:** `DISCHARGE_DATE` همیشه خالی است ⇒ در `_inventory_pipeline` متغیر `discharged` همیشه `False` ⇒ `assign_customs` هرگز فعال نمی‌شود و `IS_IN_CUSTOMS` فقط از عدد کارشناسی می‌آید، درحالی‌که `IS_IN_TRANSIT` برای هر ردیف ترخیص‌نشده `True` می‌شود. یعنی تفکیک «در راه / در گمرک» مبتنی بر رویداد، **ساختاراً غیرفعال** است.
3. **زنجیره authority به ستون حذف‌شده اشاره می‌کند:** `expert_roles.py:59` نقش خریدار را با `[("ORC_BUYER","oracle"), ("CRD_BUYER","credit")]` حل می‌کند — یعنی اولین مرجع، ستونی است که reader **عمداً حذف می‌کند**. همچنین `pipeline.preflight` و `doctor.py` مقدار `"ORC_STATUS"` را در `base_cols` می‌گذارند، پس اعتبارسنج گراف مرحله‌ها فرض می‌کند این ستون موجود است و شکاف را پنهان می‌کند.
4. **سیگنالی که دور ریخته می‌شود:** `DeriveStage.run` فهرست کاندیداهای یافت‌نشده را در `ctx.extras["derive_missing"]` می‌گذارد؛ `grep` نشان می‌دهد **هیچ مصرف‌کننده‌ای** ندارد و به هیچ `Check` تبدیل نمی‌شود.

### N06 — HIGH — PR Item با چند PO Item: فقط یک PO در fact قلم PR باقی می‌ماند

**دسته:** SAP PR/PO Grain · Silent Data Loss
**شاهد:** `adapters/a60_finance.py:SapAdapter.transform` · probe OP-03

سناریوی خراب‌کننده: `PR 1000000001 / item 10` بین دو سند خرید تقسیم شده (PO…01 qty 60 و PO…02 qty 40).

```
pr_item_10_row_count : 1
pr_item_10_kept_po   : ["20"]     ← فقط قلم PO دوم
```

`pr_items = pr.groupby([KEY_PR,"SAP_PR_ITEM"]).tail(1)` است؛ چون `__SORT` هر دو ردیف برابر است (هر دو `Changed On` یکسان PR دارند)، برنده صرفاً «آخرین ردیف فایل» است. هر ستون `SAP_PO_*`، `SAP_QTY_ORDERED` و `SAP_HEADER_PURCHASE_ORDER` روی fact قلم PR، نماینده **یکی از N** سند خرید است، بدون هیچ پرچم multiplicity (برخلاف `MULTI_PR`/`MULTI_MATERIAL` که Commercial Expert دارد).

این با F017 یکی نیست: F017 درباره انتساب غلط در `po_items` است؛ این درباره از دست رفتن کثرت در `pr_items` است.

### N07 — HIGH — گیت PROCESS_ROW_PRESERVATION خودغیرفعال‌شونده است

**دسته:** Failure Isolation · Snapshot Publication
**شاهد:** `stages/s54_process_integrity.py` (`tolerant = True`) · `warehouse/bridge.py:28` (`if ps:`) · probe OP-05

```
gate_when_stage_ran    : [("PROCESS_ROW_PRESERVATION", False)]   ← BLOCK فعال
gate_when_stage_raised : []                                      ← هیچ چکی
```

`s54` با `tolerant=True` تعریف شده، پس هر exception داخل `build_process_inventory` باعث می‌شود `run_stages` مرحله را قرنطینه کند و `ctx.extras["process_evidence_summary"]` هرگز ست نشود. `bridge.py` هم با `if ps:` وقتی خلاصه نباشد چک را **اضافه نمی‌کند**.

یعنی همان خرابی‌ای که گیت باید جلویش را بگیرد (فروپاشی مدل شواهد فرایند)، خودِ گیت را حذف می‌کند و run با `quality_gate_passed=True` منتشر می‌شود. این وارونگی fail-closed است و در `FINDINGS_REGISTER` نیامده.

### N08 — MEDIUM — شناسه پرونده فرایندی پایدار نیست

**دسته:** History Preservation · Process Continuity
**شاهد:** `resolve/process_evidence.py:_components` · probe OP-04

`case_id = "PC-" + sha1("|".join(sorted(nodes)))[:14]` — یعنی شناسه، تابع **کل اعضای component** است.

```
اجرای الف (ORD-A, ORD-B روی M1)          : PC-148AAC992DA6B2
اجرای ب  (ORD-A, ORD-B, ORD-C روی M1)    : PC-F5548CE40949AD
case_id_stable_when_member_added         : false
```

هر ورود یک شاهد جدید (که با N04/F004 بسیار محتمل است) شناسه پرونده را کاملاً عوض می‌کند. هر مصرف‌کننده‌ای که `PROCESS_CASE_ID` را ذخیره یا لینک کند — action queue، پیوست در ردیف flat، مقایسه بین دو روز — بی‌صدا ارجاعش را از دست می‌دهد. `DECISION_LOG` این را به‌عنوان نیازمندی O003 ذکر کرده ولی به‌عنوان نقص فعلی ثبت نکرده است.

### N09 — MEDIUM — `evidence_count` تعداد (ردیف × اجرا) است، نه تعداد شواهد

**دسته:** Double Count · Event vs Snapshot
**شاهد:** `business_dwh._upsert_relation` · probe OP-02

`ON CONFLICT … evidence_count = dwh_relation.evidence_count + 1` هیچ محدوده run ندارد. ingest مجدد فایل **دست‌نخورده** شمارنده را دوبرابر کرد (`1 → 2`). این عدد در `_relations()` به چت‌بات و در `app/warehouse_view.py:76` به UI داده می‌شود و طبیعتاً «چند شاهد مستقل داریم» خوانده می‌شود.

### N10 — MEDIUM — اجرای مسدودشده، `wh_schema_baseline` را دائمی تغییر می‌دهد

**دسته:** Snapshot Publication · Failure Isolation
**شاهد:** `warehouse/reliability.py:schema_drift_checks` · `warehouse/bridge.py`

`schema_drift_checks` **درون** `with wh.run(...)` و **پیش از** گیت اجرا می‌شود و برای هر frame تازه یک ردیف در `wh_schema_baseline` (با `PRIMARY KEY(contract)`، بدون ستون run) `INSERT` می‌کند. `wh.publish` که بعداً `QualityGateBlockedError` می‌دهد این نوشتن را برنمی‌گرداند (تراکنش جداست).

پیامد: نخستین اجرا — حتی اگر رد شود — baseline اسکیما را برای همیشه تثبیت می‌کند. اگر آن اجرا با فایل خراب بوده باشد، اجراهای درست بعدی به‌عنوان drift علامت می‌خورند. این نمونه‌ای از همان خانواده F001/F002/F012 است، اما روی جدولی که Astra اصلاً نام نبرده.

### N11 — MEDIUM — `_SOURCE_FILE` نام فایل اصلی را حمل نمی‌کند؛ دو fallback مستند مرده‌اند

**دسته:** Orphan Evidence · Ambiguous Mapping
**شاهد:** `dataio/reader.py:read_source` و `_read_targets` · `adapters/a30_customs.py:122` · `adapters/a10_abbasi.py:62`

`read_source` بایت‌های آرشیوشده را در فایل موقتی با نام `fid + ext` می‌نویسد، و `fid = hashlib.sha256(content).hexdigest()` است. سپس `_read_targets` می‌نویسد `df["_SOURCE_FILE"] = os.path.basename(f)` — یعنی مقدار این ستون یک هش ۶۴ کاراکتری است، نه `SeaClearance.xlsx`.

در نتیجه:
- در `ClearanceAdapter`، شاخه‌ای که مستند شده «نوع فایل خودش حامل حقیقت است» هرگز کار نمی‌کند (`rb.transport_mode("<sha256>.xlsx")`). شاخه `_SOURCE_SHEET` هنوز کار می‌کند، چون clearance از `all_data_sheets` استفاده می‌کند.
- در `AbbasiAdapter` **هر دو** fallback مرده‌اند: `_SOURCE_FILE` هش است، و `_SOURCE_SHEET` در شاخه معمولی `_read_targets` (خط ۱۹۸) اصلاً ست نمی‌شود — فقط در شاخه `all_data_sheets`.

این یک پسرفت جانبی از تغییر درستِ «خواندن از بایت آرشیوشده» است.

### N12 — MEDIUM — تعیین «آخرین وضعیت» درخواست تخصیص قطعی نیست

**دسته:** Event vs Snapshot · Late-arriving Data
**شاهد:** `adapters/a50_ntsw.py:_allocation_request_ledger` و `_agg_allocation`

`a.sort_values("_ord")` با `kind` پیش‌فرض (`quicksort`، ناپایدار) اجرا می‌شود و سپس `drop_duplicates(..., keep="last")` برنده را می‌گیرد؛ `_agg_allocation` هم `g.sort_values("_ord")` و `g.iloc[-1]`. وقتی دو snapshot از یک درخواست تاریخ‌های یکسان دارند (حالت رایج در snapshot روزانه)، برنده به ترتیب ورودی و اندازه آرایه بستگی دارد.

شاهد تقویتی از خود پکیج: `dataio/merge.py:dedupe_on_key` برای دقیقاً همین تصمیم `kind="mergesort"` را انتخاب کرده و دلیلش را کامنت کرده («در تساوی تاریخ … نتیجه dedupe بین دو اجرا عوض نمی‌شود»). یعنی استاندارد داخلی پروژه اینجا رعایت نشده.

### N13 — MEDIUM — REG غیر ۸‌رقمی بی‌صدا از جمعیت اصلی حذف می‌شود

**دسته:** Orphan Evidence · Source Authority
**شاهد:** `resolve/population.py:_clean_reg`

```python
def _clean_reg(v) -> str:
    s = clean_key(v)
    return s if len(s) == 8 and s.isdigit() else ""
```

هر REG که دقیقاً ۸ رقم عددی نباشد `""` می‌شود و ردیف در `_ntsw_reg_rows` با `if reg:` کنار گذاشته می‌شود — **بدون هیچ issue، audit یا `dwh_unresolved_relation`**. همان REG می‌تواند در `dwh_fact_ntsw_commitment` موجود باشد (که چنین فیلتری ندارد)، پس گزارش تخت و DWH در شمارش پرونده‌ها با هم اختلاف پیدا می‌کنند و علت اختلاف در هیچ خروجی دیده نمی‌شود.

---

## 6. سناریوهای خراب‌کننده و نتیجه واقعی

| # | سناریو | نتیجه مشاهده‌شده | یافته |
|---|---|---|---|
| S01 | PR Item با چند PO Item | fact قلم PR فقط یک PO را نگه می‌دارد؛ qty و سند خرید نماینده‌ی یکی از دو PO | N06 |
| S02 | `po.Purchase Requisition` متفاوت با PR هدر | `(pr_key, pr_item) = (1000000001, 00090)` ذخیره شد — ترکیبی که در هیچ ردیف منبع نیست؛ رابطه PR→PO غلط ساخته شد | F017 |
| S03 | ORDER با چند BL / چند LC روی یک BL | ۳ ردیف سمت راست → فقط `LC-1`؛ خطای cardinality ساختاراً غیرممکن | F019, N04 |
| S04 | REG با چند جریان ارزی (USD + EUR) | `ALLOCATED_AMOUNT = 200` با `CURRENCY = EUR` | F007 |
| S05 | Stage بعدی بدون Stage قبلی | درست کار می‌کند: `EVIDENCE_GAP` تولید می‌شود و شاهد بعدی پنهان نمی‌شود | — (رفتار صحیح) |
| S06 | Settlement بدون Link معتبر | Cash Flow engine درست عمل می‌کند (`INVALID_REVERSAL`, `OVER_REVERSAL`, الزام دو leg برای FX) | — (رفتار صحیح) |
| S07 | NTSW Balance بدون comparator | `COMMITMENT_BALANCE` به‌عنوان measurement با `observed_at = تاریخ گزارش` ثبت می‌شود، در حالی که snapshot منبع است؛ و `source_record_id` شمارنده است | F027 |
| S08 | Source Tier 2 متعارض با Tier 1 | سیاست درست پیاده شده (`_ensure_key(force=True)` پس از پل NTSW)، اما سیاست در زمان **import** خوانده می‌شود و reload اثر ندارد؛ Cash Flow نسخه هاردکد خودش را دارد | F032 |
| S09 | Partial Run (اجرای مسدود پس از یک publish سالم) | pointer درست ماند؛ اما چت‌بات داده اجرای مسدود را با برچسب as-of اجرای سالم برگرداند و شواهد Cash Flow نسخه منتشرشده صفر شد | F001, F002 |
| S10 | Duplicate Native Rows | دو ردیف یکسان → یک observation → `row_preservation_ok=False` → کل انتشار BLOCK | F005 |
| S11 | Cancelled/Reworked PR («تایید نشده»، «مورد تایید») | NTSW: «تایید نشده» → ALLOCATED. Process: «مورد تایید» → NEGATIVE، «تایید نشده» → POSITIVE | F008, N03 |
| S12 | SAP schema evolution (تغییر نام هدر) | fingerprint یکسان، `SCHEMA_DRIFT` **پاس**، مقدار `ACME → ""`، هیچ چک BLOCK فعال نشد | N01 |
| S13 | ingest مجدد همان فایل با یک ردیف اضافه در ابتدا | `dwh_fact_sap_workflow`: `3 → 7` ردیف؛ ردیف قدیمی بازنشسته نمی‌شود | F018 |
| S14 | ingest مجدد فایل کاملاً بدون تغییر | `evidence_count`: `1 → 2` | N09 |
| S15 | REG_FILE با ۲ REG و ۲ ORDER | نمای هاب ۴ زوج REG×ORDER تولید کرد | N02 |
| S16 | فریم `ilappend/main` با همه کلیدها خالی | همه چک‌ها پاس شدند | F025 |
| S17 | یک سلول خالی در «مانده تعهد» NTSW | `raise ValueError` → کل منبع NTSW از دست می‌رود → چون critical است، انتشار تمام دامنه‌ها BLOCK | F011 |
| S18 | ریشه KB موقتاً در دسترس نیست و بعد برمی‌گردد | همه اسناد `DELETED`؛ بازگرداندن فایل با mtime/size یکسان آن را `ACTIVE` نمی‌کند | F024 |
| S19 | ردیف FX با ORDER معتبر ولی بدون REG | رویداد Cash Flow ساخته نمی‌شود و هیچ رکورد unresolved ثبت نمی‌شود | F026 |
| S20 | exception در سازنده شواهد فرایند | گیت BLOCK حذف می‌شود و run پاس می‌شود | N07 |

---

## 7. Missing Tests

تست‌های موجود پکیج (۸۰ فایل) در محیط این بازبینی با Python 3.12 اجرا شدند: **380 pass / 8 fail / 1 error**؛ شکست‌ها عمدتاً وابستگی محیطی و یک رشته نسخه کهنه (`Build 29.7.5` در برابر پکیج 29.7.6) بودند. اما بحرانی‌ترین رفتارها اصلاً تست ندارند.

`grep` روی `tests/` برای شناسه‌های کلیدی:

| شناسه رفتار | تست موجود |
|---|---|
| `last_seen_run` (ایزولاسیون انتشار) | **هیچ** |
| `RowExplosionError` | **هیچ** |
| `_state_from_text` | **هیچ** |
| `SAP_PO_PR` | **هیچ** |
| `dwh_registration_hub` | فقط حالت ۱:۱:۱ |
| `SCHEMA_DRIFT` | فقط افزودن/حذف ستونِ استانداردشده، نه تغییر هدر منبع |
| `GRAIN_UNIQUENESS` | بدون حالت `nullable_key=True` |

**تست‌هایی که باید نوشته شوند (به ترتیب ارزش):**

| # | تست | شکست موردانتظار امروز |
|---|---|---|
| T01 | publish R1 → build R2 مسدود → همه خواننده‌ها (چت‌بات، Cash Flow، `warehouse_view`) باید byte-stable بمانند | F001, F002 |
| T02 | تغییر نام یک هدر منبع → باید یک چک BLOCK فعال شود | N01 |
| T03 | ادغام با سمت راست غیریکتا → باید یا تکثیر آگاهانه باشد یا `JOIN_CARDINALITY_VIOLATION` بدهد | F019, N04 |
| T04 | کلید `NaN` و `("","")` و برخورد delimiter → نباید هیچ انطباقی بسازند | F020 |
| T05 | جدول پارامتری طبقه‌بند وضعیت فارسی (حداقل ۲۰ عبارت واقعی با نفی) | F008, N03 |
| T06 | REG_FILE با ۲ REG و ۲ ORDER → هاب نباید زوج اثبات‌نشده بسازد | N02 |
| T07 | فریم با `nullable_key=True` و همه کلیدها خالی → باید BLOCK شود | F025 |
| T08 | `po.Purchase Requisition` ≠ PR هدر → باید قرنطینه شود، نه ذخیره‌ی ترکیبی | F017 |
| T09 | exception عمدی در `s54` → گیت `PROCESS_ROW_PRESERVATION` نباید ناپدید شود | N07 |
| T10 | ingest مجدد فایل بدون تغییر → `evidence_count` و تعداد ردیف‌های workflow نباید تغییر کند | N09, F018 |
| T11 | ممیزی reachability: هر کاندیدای `DERIVED` باید تولیدکننده داشته باشد (تست ساختاری، نه داده‌ای) | F021, N05 |
| T12 | دو snapshot هم‌تاریخ از یک درخواست تخصیص → برنده باید قطعی و تکرارپذیر باشد | N12 |
| T13 | NTSW با یک سلول خالی → نباید انتشار دامنه‌های نامرتبط را متوقف کند | F011 |
| T14 | افزودن عضو به component فرایندی → `PROCESS_CASE_ID` پرونده‌های قبلی نباید عوض شود | N08 |

---

## 8. Architecture Concerns

این‌ها یافته نیستند؛ الگوهای ساختاری‌اند که یافته‌ها را تکثیر می‌کنند.

**A1 — گیت‌های تزئینی.** سه چک با شدت BLOCK وجود دارد که یا ساختاراً غیرقابل‌فعال‌شدن‌اند (`JOIN_CARDINALITY_VIOLATION`)، یا خودغیرفعال‌شونده‌اند (`PROCESS_ROW_PRESERVATION`)، یا چیزی را می‌سنجند که خودِ کد تضمین کرده (`REQUIRED_COLUMNS` روی ستون‌هایی که `std()` همیشه می‌سازد). یک گیت که نمی‌تواند fail شود، از نبودِ گیت بدتر است، چون اعتماد کاذب تولید می‌کند. **هر چک BLOCK باید یک تست داشته باشد که آن را عمداً fail می‌کند.**

**A2 — مرز انتشار سه‌بار شکسته شده.** فایل اکسل رسمی، جدول‌های `dwh_*` و `wh_schema_baseline` همگی **پیش از** گیت نوشته می‌شوند. «حفاظت از pointer» تنها یک‌سوم دارایی‌های منتشرشده را می‌پوشاند. این همان O001 در `DECISION_LOG` است و تا حل‌نشدنش، F001/F002/F012/N10 صرفاً نمودهای مختلف یک نقص‌اند.

**A3 — سیگنال تولید می‌شود ولی مصرف نمی‌شود.** `ctx.extras["derive_missing"]`، هشدار ستون یافت‌نشده در `std()`، `health.current().find(...)`، `ORACLE_SHEET_OVERLAP`، `DWH_EQUAL_PRIORITY_KEY_CONFLICT` — همه تولید می‌شوند و هیچ‌کدام به `Check` تبدیل نمی‌شوند. زیرساخت تشخیص موجود است؛ اتصالش به گیت نیست.

**A4 — هویت به‌جای شناسه، هش محتوا است.** `dwh_fact_source_row.row_hash`، `OBSERVATION_ID`، `PROCESS_CASE_ID` و `workflow_key` همگی از محتوا مشتق می‌شوند. نتیجه دوگانه است: دو ردیف یکسان یک هویت می‌گیرند (F005)، و تغییر کوچک محتوا هویت تازه می‌سازد (F018, N08). این ریشه مشترک شش یافته است.

**A5 — سه لایه persistence بدون مالک.** `wh_*` (mutable current)، `dwh_*` (mutable upsert) و `historical_store` (رویدادمحور، **بدون هیچ مصرف‌کننده**). وجود ماژول historical به‌معنی ثبت تاریخچه نیست (F036).

**A6 — تطبیق زیررشته در متن فارسی، به‌عنوان قاعده کسب‌وکاری.** `find_col` فاز ۲، طبقه‌بندهای وضعیت، و `_UNRESOLVED` همگی روی `x in s` کار می‌کنند. در فارسی که فاصله و نیم‌فاصله ناپایدار است، این تصمیم قابل‌دفاع بوده؛ اما بدون مرز واژه و بدون تشخیص نفی، به‌صورت نظام‌مند خطا تولید می‌کند (F008, F030, N03).

**A7 — پروژکشن و شاهد، هم‌نام‌اند.** `main` گاهی ردیف native است (clearance، fx) و گاهی تجمیع (moghavemat، sap، doccheck). مصرف‌کننده از روی نام نمی‌تواند تشخیص دهد. Astra این را در `D003` درست تشخیص داده است، ولی خودش هم در F006 قربانی همین ابهام شده و از نام frame به رفتار استنتاج کرده.

---

## 9. Business Rule Ambiguities

مواردی که **بدون مالک داده قابل تصمیم نیستند**. هیچ‌کدام نباید به‌عنوان نقص کد بسته شوند.

| # | ابهام | چرا کد نمی‌تواند تصمیم بگیرد | تصمیم‌گیرنده |
|---|---|---|---|
| B1 | `NTSW_FX_RATE_TYPE` و `NTSW_FX_RATE_NUMERIC` هر دو به ستون خام «نرخ ارز» map شده‌اند | یکی از این دو الزاماً غلط است؛ اگر ستون متنی باشد (نیمایی/آزاد) `num_safe` آن را `NaN` می‌کند، و اگر عددی باشد `RATE_TYPE` یک عدد است | مالک export NTSW |
| B2 | `FX_CURRENCY` در نبودِ «نوع ارز خریداری شده» به «نوع ارز» برمی‌گردد — همان ستونی که به `FX_PROFORMA_CURRENCY` هم بسته شده؛ و `FX_SWIFT_CURRENCY` به هدر تکراریِ موقعیتی `نوع ارز__2` (تولیدشده توسط `warehouse/excel.frame`) بسته است | با افزودن/جابه‌جایی یک ستون هم‌نام، ارز سوئیفت بی‌صدا به ستون دیگری می‌چسبد | مالک فایل خرید ارز |
| B3 | «دریافت اسناد» (SATA) = «رسید مالی»؟ | `s80` آن را terminal-ish تفسیر می‌کند؛ معادل‌بودن دو رویداد یک حکم کسب‌وکاری است (F022) | Credit / Finance |
| B4 | SWIFT = وصول ذی‌نفع؟ | `s55` این دو را جدا می‌کند و `process_evidence` یکی؛ هر دو در یک پکیج (F039) | Treasury |
| B5 | آیا ردیف‌های تکراری یک متریال در یک شیت Oracle، bucket مستقل‌اند یا snapshot تکراری؟ | قرارداد فعلی درون‌شیت additive و بین‌شیت non-additive است — نمی‌تواند هر دو درست باشد (F014) | مالک موجودی |
| B6 | آیا `Purchase Requisition` هدر و `po.Purchase Requisition` یک چیزند؟ | کد امروز فرض می‌کند بله و ترکیب می‌سازد؛ باید فرض نشود (F017) | SAP functional owner |
| B7 | آیا فایل ExportClearance وجود دارد و کلید مشترک دارد؟ | بدون نمونه فایل قابل تصمیم نیست — به همین دلیل F029 اینجاست نه در فهرست یافته‌ها | Logistics |
| B8 | آیا REG همیشه دقیقاً ۸ رقم است؟ | `_clean_reg` این را قانون سخت جمعیت کرده و تخلف را بی‌صدا حذف می‌کند (N13) | مالک NTSW |
| B9 | آیا export هر منبع full snapshot است یا delta؟ | تمام سیاست حذف/tombstone به این بستگی دارد (F003) — همان O002 | مالک هر منبع |
| B10 | ریشه پرونده فرایندی چیست؟ | تا تعیین‌نشدنش، `_components` فقط یک component گراف است، نه پرونده (F004, N08) — همان O003 | مالک فرایند |

---

## 10. Priority Recommendation

ترتیب بر اساس **مهار خطای قابل‌اثبات**، نه اهمیت معماری. هیچ موردی صرفاً به دلیل ترجیح طراحی بالا نیامده است.

### P0 — داده منتشرنشده نباید خوانده شود *(بدون نیاز به هیچ تصمیم کسب‌وکاری)*
`F001` · `F002` · `F012` · `N10`
تمام خواننده‌ها (`knowledge_desk/operational`، `cashflow/dwh`، `app/warehouse_view`) باید به یک snapshot مشخص مقید شوند و هر نوشتن پیش از گیت باید در staging برود. معیار پذیرش: **T01**.
اگر فقط یک کار انجام شود، همین است: امروز چت‌بات داده تأییدنشده را با برچسب «منتشرشده» برمی‌گرداند.

### P0 — گیت‌های مرده، اعتماد کاذب می‌دهند
`N01` · `N04` · `N07` · `F025`
این چهار مورد باعث می‌شوند «گیت پاس شد» چیزی را اثبات نکند. هزینه اصلاحشان کم و اثرشان روی اعتبار کل سیستم زیاد است. معیار پذیرش: **T02, T03, T07, T09**.

### P1 — نقص‌های عددی و هویتی با اثر مستقیم بر تصمیم
`F007` · `F008` · `F009` · `F016` · `F027` · `N03`
جمع ارزهای متفاوت، تشخیص تخصیص از عبارت منفی، و شناسه‌ای که شمارنده است — همه بدون نیاز به مالک داده قابل اصلاح‌اند، چون در هر تفسیر کسب‌وکاری غلط‌اند. معیار پذیرش: **T05, T12**.

### P1 — گرین SAP و روابط جعلی
`F017` · `N06` · `N02` · `F018`
تمرکز ویژه‌ی درخواست‌شده. در همه‌ی این موارد راه‌حل ایمن «قرنطینه به‌جای ترکیب» است و نیازی به تصمیم کسب‌وکاری ندارد: وقتی PR هدر با PR سند خرید نمی‌خواند، رکورد باید `dwh_unresolved_relation` شود، نه یک ارجاع ساختگی. معیار پذیرش: **T06, T08, T10**.

### P2 — از دست رفتن شاهد و ایزوله‌نبودن خرابی
`F019` · `F020` · `F026` · `F023` · `F033` · `F010` · `F011` · `F024` · `N11` · `N13`
همه یک الگو دارند: داده‌ای حذف یا از دسترس خارج می‌شود بدون اینکه رکورد «چه چیزی و چرا» بماند.

### P2 — ممیزی reachability
`F021` · `N05`
ارزان، مکانیکی و قابل‌تبدیل به تست ساختاری (**T11**). ثابت جعلی `SEGMENT="تولیدی"` باید فوراً حذف شود؛ یک مقدار پیش‌فرض نباید شبیه داده به‌نظر برسد.

### P3 — پس از تصمیم مالک داده
`F003` · `F004` · `F013` · `F014` · `F022` · `F029` · `F039` · `N08`
این‌ها به B3–B10 گره خورده‌اند. اصلاح کد پیش از تصمیم، فقط خطا را جابه‌جا می‌کند.
**یک استثنا:** حتی پیش از تعیین ریشه پرونده، حذف `MATERIAL` و `EMP` از کلیدهای case-forming در `_components` یک اصلاح ایمن است — چون هیچ تفسیر کسب‌وکاری‌ای نمی‌گوید «اشتراک متریال یعنی یک پرونده».

### P4 — بدهی ساختاری
`F030` · `F031` · `F032` · `F034` · `F035` · `F036` · `F037` · `F038` · `F040` · `N09` · `N12`
`F037` اگر استقرار روی شبکه‌ای باشد که کاربر غیرمجاز دارد، باید به P1 منتقل شود؛ وضعیت شبکه/ACL در این بازبینی **UNKNOWN / NEEDS EVIDENCE** باقی است.

---

## 11. حدود اعتبار این بازبینی

- هیچ فایل اصلی پکیج تغییر نکرد؛ probeها بیرون درخت source اجرا شدند و در `probes/` این پوشه قرار دارند.
- probeها synthetic‌اند. آن‌ها **وجود نقص روی ورودی مشخص** را اثبات می‌کنند، نه فراوانی وقوع در داده تولید. هر جا اثر به داده واقعی وابسته است (F009، F014، F016، F029) صریح نوشته شده.
- محیط اجرا Python 3.12 با pandas 3.0.6 بود. نکته‌ی مهم: `gsi/cashflow/report.py:86` از f-string تودرتوی PEP 701 استفاده می‌کند و **روی Python 3.11 اصلاً parse نمی‌شود**، درحالی‌که `requirements.txt` می‌گوید «پایتون ۳٫۱۱ یا بالاتر». این یک ناسازگاری اعلام‌شده/واقعی است که در Phase 0 دیده نشده (Astra با AST parse گزارش «۰ خطای نحوی» داده که با مفسر ۳٫۱۲+ درست است).
- شبکه سازمانی، Outlook COM، مرورگر Streamlit، و migration دیتابیس تولیدی آزمایش نشدند.
- همه عددهای نقل‌شده خروجی مستقیم probeهای همراه‌اند و با اجرای مجدد قابل بازتولیدند.
