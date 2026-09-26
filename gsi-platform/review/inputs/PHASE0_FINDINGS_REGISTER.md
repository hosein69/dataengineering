# FINDINGS_REGISTER — GSI V29.7.6 / Phase 0

تاریخ بررسی: 2026-09-22. هیچ اصلاحی اعمال نشده است. Severity بر اساس پیامد بالقوه کسب‌وکاری است، نه فراوانی اثبات‌شده در محیط تولید. HIGH confidence یعنی رفتار کد روشن است؛ صحت فرض کسب‌وکاری فقط با داده/مالک منبع تأیید می‌شود.

**40 یافته:** CRITICAL=3, HIGH=25, MEDIUM=12.

| ID | Severity | Finding | Verification |
|---|---|---|---|
| F001 | CRITICAL | نشت اجرای مسدودشده به پاسخ چت‌بات | P01 |
| F002 | CRITICAL | ناپدیدشدن شواهد Cash Flow نسخه منتشرشده بعد از اجرای مسدود | P01 |
| F003 | HIGH | حذف و current بودن Business Facts تعریف نشده | STATIC |
| F004 | CRITICAL | ادغام سفارش‌های مستقل در Process Case از طریق Material/Employee | P02 |
| F005 | HIGH | حذف duplicate observations و سپس مسدودشدن انتشار | P03 |
| F006 | HIGH | تبدیل frame مشتق به شاهد مستقیم | STATIC |
| F007 | HIGH | NTSW تخصیص با ارزهای متفاوت یک جمع می‌سازد | P04 |
| F008 | HIGH | تشخیص تخصیص از عبارت منفی | P04 |
| F009 | HIGH | تعهد تکراری به جای snapshot به‌عنوان تعهد جدید جمع می‌شود | P05 |
| F010 | HIGH | کمبود داده source از gate عبور می‌کند | STATIC |
| F011 | HIGH | وابستگی کل انتشار به خرابی یک دامنه | STATIC |
| F012 | HIGH | فایل رسمی قبل از تأیید gate نوشته می‌شود | STATIC |
| F013 | HIGH | Oracle هم‌پوشان یک ردیف ترکیبی می‌سازد | STATIC |
| F014 | HIGH | فرض جمع‌پذیری تکرارهای درون شیت Oracle اثبات نشده | STATIC |
| F015 | HIGH | Flat report فقط نماینده اول PR/Material سفارش را می‌گیرد | STATIC |
| F016 | HIGH | مبالغ Commercial Expert بدون dedupe و currency grain جمع می‌شوند | STATIC |
| F017 | HIGH | PO fact به PR/Material هدر متصل می‌شود نه فیلد اختصاصی PO | P06 |
| F018 | HIGH | Workflow observation به‌عنوان event و latest PR نمایش داده می‌شود | STATIC |
| F019 | HIGH | safe_merge حقایق many-to-one را قبل از کنترل یکتایی حذف می‌کند | STATIC |
| F020 | MEDIUM | کلید مرکب خالی به کلید قابل join تبدیل می‌شود | P07 |
| F021 | HIGH | برخی تاریخ‌های domain هرگز از adapter صحیح تغذیه نمی‌شوند | STATIC |
| F022 | HIGH | معانی تاریخ دریافت سند و رسید مالی مخلوط شده‌اند | STATIC |
| F023 | HIGH | مسیر legacy رفع تعهد همه نسخه‌های فایل را جمع می‌کند | P08 |
| F024 | HIGH | قطع مسیر KB حذف منطقی و عدم بازیابی می‌سازد | P09 |
| F025 | HIGH | grains ناقص و nullable-key loophole در Quality Gate | P10 |
| F026 | HIGH | ردیف‌های FX دارای ORDER ولی فاقد REG در Cash Flow حذف می‌شوند | STATIC |
| F027 | HIGH | شناسه commitment در Cash Flow تعداد سطر است، نه شناسه تعهد | P11 |
| F028 | MEDIUM | read all_data_sheets در عمل فقط بزرگ‌ترین شیت را می‌خواند | STATIC |
| F029 | HIGH | جداسازی صریح Export Clearance از Import پیدا نشد | STATIC |
| F030 | MEDIUM | فازی بودن header mapping می‌تواند معنای کلید را تغییر دهد | STATIC |
| F031 | HIGH | صفر و Unknown در legacy financial fields یکسان می‌شوند | STATIC |
| F032 | MEDIUM | دو سیستم Authority با تصمیم متفاوت در تعارض وجود دارد | STATIC |
| F033 | MEDIUM | fallback استاندارد در snapshot تازه دوباره ذخیره نمی‌شود | STATIC |
| F034 | MEDIUM | خطای operational retrieval به نبود شاهد تبدیل می‌شود | STATIC |
| F035 | MEDIUM | دریافت متن KB تضمین پاسخ مرتبط/معتبر نیست | STATIC |
| F036 | MEDIUM | historical warehouse مستقل به pipeline اصلی متصل نیست | STATIC |
| F037 | MEDIUM | شواهد endpoint KB شامل کنترل دسترسی application نیست | STATIC |
| F038 | MEDIUM | DocCheck history پیش از process inventory فشرده می‌شود | STATIC |
| F039 | MEDIUM | SWIFT در Process Matrix به PAYMENT تعبیر می‌شود | STATIC |
| F040 | MEDIUM | serialized latest snapshot و migration/locking کامل نیست | STATIC |

## F001 — نشت اجرای مسدودشده به پاسخ چت‌بات

- **ID:** F001
- **Severity:** CRITICAL
- **Evidence:** پس از انتشار R1 و ساخت R2 مسدود، pointer روی R1 ماند اما پاسخ وضعیت NEW_BLOCKED را با run_id=R1 برگرداند. کوئری Fact و Relation شرط run ندارد.
- **File / Function:** `gsi/knowledge_desk/operational.py:78` — `_pr_semantic`
- **Root Cause:** Business facts پیش از gate به‌صورت mutable upsert می‌شوند؛ run_id فقط در متن پاسخ تزریق می‌شود.
- **Business Impact:** نمایش داده تأییدنشده با ادعای Published و as-of غلط.
- **Potential Fix — پیشنهاد، اجرا نشده:** نسخه‌بندی facts/relations با run membership و خواندن از snapshot مشخص؛ یا staging و promotion اتمیک. صرف افزودن last_seen_run=R1 کافی نیست، چون R2 آن را overwrite کرده است.
- **Regression Surface:** Business DWH, operational/static chatbot, warehouse UI, publish rollback
- **Confidence:** HIGH — reproduced
- **Verification:** P01

## F002 — ناپدیدشدن شواهد Cash Flow نسخه منتشرشده بعد از اجرای مسدود

- **ID:** F002
- **Severity:** CRITICAL
- **Evidence:** source_row با PK=(source,frame,row_hash) در اجرای جدید last_seen_run را تغییر می‌دهد؛ reader فقط last_seen_run=published را می‌خواند. در P01 از دو frame قبلی فقط یک frame باقی ماند؛ commitment بدون تغییر ناپدید شد.
- **File / Function:** `gsi/cashflow/dwh.py:93` — `_published_source_frames`
- **Root Cause:** last_seen برای membership تاریخی استفاده شده است.
- **Business Impact:** Cash Flow نسخه سالم قبلی ناقص می‌شود حتی وقتی gate درست pointer را حفظ کرده است.
- **Potential Fix — پیشنهاد، اجرا نشده:** bridge_run_source_row مستقل و immutable؛ خواندن frameهای استاندارد همان run نیز گزینه قابل بررسی است.
- **Regression Surface:** Fallback, Cash Flow, blocked/failed run, repeat ingestion
- **Confidence:** HIGH — reproduced
- **Verification:** P01

## F003 — حذف و current بودن Business Facts تعریف نشده

- **ID:** F003
- **Severity:** HIGH
- **Evidence:** facts و dimensions و relations upsert می‌شوند؛ نبود رکورد در export بعدی نه expire می‌شود نه tombstone دارد؛ reader چت‌بات همه را می‌خواند.
- **File / Function:** `gsi/warehouse/business_dwh.py:299` — `build`
- **Root Cause:** current-state tables با تاریخچه first/last seen مخلوط‌اند؛ absence policy وجود ندارد.
- **Business Impact:** اقلام حذف‌شده/منقضی و روابط قدیمی به‌عنوان وضعیت جاری باقی می‌مانند.
- **Potential Fix — پیشنهاد، اجرا نشده:** سیاست full-snapshot در برابر delta برای هر source؛ run-scoped current views و inactive/deleted evidence.
- **Regression Surface:** SAP deletion, Oracle stock, allocation requests, all dimensions
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F004 — ادغام سفارش‌های مستقل در Process Case از طریق Material/Employee

- **ID:** F004
- **Severity:** CRITICAL
- **Evidence:** همه ENTITY_COLS از جمله MATERIAL و EMP با union-find به component واحد وصل می‌شوند. دو ORDER با M1 مشترک در P02 یک case با ORDER_COUNT=2 شدند.
- **File / Function:** `gsi/resolve/process_evidence.py:273` — `_components`
- **Root Cause:** اشتراک dimension با هویت پرونده کسب‌وکاری یکسان گرفته شده است.
- **Business Impact:** مراحل سفارش دیگر شکاف این سفارش را پُر می‌کنند؛ owner، bottleneck و تکمیل فرایند آلوده می‌شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** Case identity مستقل؛ allowlist روابط case-forming با cardinality؛ Material/Employee فقط attribute/bridge.
- **Regression Surface:** Process cases, stage matrix, actions, UI, case IDs
- **Confidence:** HIGH — reproduced
- **Verification:** P02

## F005 — حذف duplicate observations و سپس مسدودشدن انتشار

- **ID:** F005
- **Severity:** HIGH
- **Evidence:** _row_ref hash محتواست و idx برای ردیف غیرخالی در شناسه دخیل نیست؛ drop_duplicates OBSERVATION_ID دو ردیف یکسان را یکی می‌کند. P03: expected=2, preserved=1.
- **File / Function:** `gsi/resolve/process_evidence.py:145` — `_observations`
- **Root Cause:** هویت observation با hash محتوای business یکی شده؛ row-preservation تعداد input را انتظار دارد.
- **Business Impact:** ورودی تکراری مشروع gate کل گزارش/DWH را مسدود می‌کند؛ multiplicity شواهد از دست می‌رود.
- **Potential Fix — پیشنهاد، اجرا نشده:** observation_id بر اساس file/sheet/physical-row/run؛ duplicate-business-content را جدا علامت بزنید.
- **Regression Surface:** Process row gate, all adapters, duplicate semantics
- **Confidence:** HIGH — reproduced
- **Verification:** P03

## F006 — تبدیل frame مشتق به شاهد مستقیم

- **ID:** F006
- **Severity:** HIGH
- **Evidence:** تنها SAP semantic frames از relation extraction مستثنا هستند؛ برای moghavemat/main، inventory و OMPI و lines و دیگر frames زوج کلیدها DIRECT_COOBSERVED می‌شوند. main تجمیعی است و first_validهای مستقل دارد.
- **File / Function:** `gsi/warehouse/business_dwh.py:299` — `build`
- **Root Cause:** source frame الزاماً physical/native row نیست؛ whitelist عمومی زوج‌ها provenance معنایی را اثبات نمی‌کند.
- **Business Impact:** رابطه synthetic با عنوان مستقیم در DWH/چت‌بات؛ evidence_count از چند representation و run زیاد می‌شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** Relation extraction فقط از native observation با row reference؛ derived relation با rule/path جدا.
- **Regression Surface:** Entity relations, OMPI, chatbot, registration hub
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F007 — NTSW تخصیص با ارزهای متفاوت یک جمع می‌سازد

- **ID:** F007
- **Severity:** HIGH
- **Evidence:** groupby فقط REG است؛ amountها جمع و REQ_CURRENCY از آخرین ردیف گرفته می‌شود. P04: 100 USD + 100 EUR → 200 EUR.
- **File / Function:** `gsi/adapters/a50_ntsw.py:246` — `_agg_allocation`
- **Root Cause:** currency بخشی از grain تجمیع نیست و guard چندارزی commitment در allocation تکرار نشده است.
- **Business Impact:** اشتباه مبلغ تخصیص/صف و همه خلاصه‌های downstream.
- **Potential Fix — پیشنهاد، اجرا نشده:** REG×currency summary و request ledger مرجع؛ منع جمع بدون تبدیل مستند.
- **Regression Surface:** Allocation, queue, FX, cashflow fallback, report totals
- **Confidence:** HIGH — reproduced
- **Verification:** P04

## F008 — تشخیص تخصیص از عبارت منفی

- **ID:** F008
- **Severity:** HIGH
- **Evidence:** state ابتدا substring مثبت تایید یا تاریخ تخصیص را بررسی می‌کند. P04: «تایید نشده» بدون تاریخ، ALLOCATED شد.
- **File / Function:** `gsi/adapters/a50_ntsw.py:192` — `_allocation_request_ledger`
- **Root Cause:** واژه‌نامه substring بدون نفی و precedence زمانی وضعیت ابطال.
- **Business Impact:** درخواست تأییدنشد‌ه/لغوشده می‌تواند تخصیص واقعی شمرده شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** status codes رسمی یا classifier نفی‌آگاه، latest state و cancellation evidence جدا.
- **Regression Surface:** Allocation states, process stage, cashflow events
- **Confidence:** HIGH — reproduced
- **Verification:** P04

## F009 — تعهد تکراری به جای snapshot به‌عنوان تعهد جدید جمع می‌شود

- **ID:** F009
- **Severity:** HIGH
- **Evidence:** COMMIT_ROW خوانده می‌شود اما در dedupe/grain به کار نمی‌رود. P05: دو نسخه همان commitment با balance=50 → balance=100.
- **File / Function:** `gsi/adapters/a50_ntsw.py:163` — `_agg_commitment`
- **Root Cause:** فرض هر ردیف یک تعهد مستقل بدون natural-key contract.
- **Business Impact:** تورم مانده و تعهد اولیه. تکرار واقعی در داده تولیدی: UNKNOWN / NEEDS EVIDENCE.
- **Potential Fix — پیشنهاد، اجرا نشده:** REG×commitment ID×currency؛ نگهداری history و current selection مستند.
- **Regression Surface:** Commitment engine, deadlines, source summary, DWH
- **Confidence:** HIGH — reproduced conditional defect
- **Verification:** P05

## F010 — کمبود داده source از gate عبور می‌کند

- **ID:** F010
- **Severity:** HIGH
- **Evidence:** برای source اختیاری با فایل/شیت مفقود return {}؛ Pipeline.source_failures فقط exceptionها را می‌گیرد؛ validate_sources فقط frames موجود را اعتبارسنجی می‌کند. moghavemat و ntsw required=false هستند.
- **File / Function:** `gsi/adapters/base.py:60` — `load`
- **Root Cause:** مفقودبودن با عدم applicability/empty valid result تفکیک نمی‌شود و expected-frame contract نیست.
- **Business Impact:** با وجود یکی از منابع primary، حذف منبع primary دیگر ممکن است به گزارش تازه اما ناقص منجر شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** source outcome صریح و expected contracts، completeness threshold و per-domain freshness.
- **Regression Surface:** Missing source/sheet, primary population, fallback, publication
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F011 — وابستگی کل انتشار به خرابی یک دامنه

- **ID:** F011
- **Severity:** HIGH
- **Evidence:** critical_sources={abbasi,ntsw,ilappend}؛ BLOCK در هر قرارداد report و dwh را با هم متوقف می‌کند؛ moghavemat critical نیست. exception تعهد چندارزی کل transform NTSW از جمله Import Licence و Allocation را از دسترس خارج می‌کند.
- **File / Function:** `gsi/warehouse/reliability.py:274` — `source_runtime_checks`
- **Root Cause:** primary population policy جدید با critical_sources قدیمی هماهنگ نیست؛ isolation در load است نه domain publication.
- **Business Impact:** خرابی مالی/لجستیکی می‌تواند تازه‌سازی همه دامنه‌ها را متوقف کند.
- **Potential Fix — پیشنهاد، اجرا نشده:** تصمیم صریح درباره atomic global snapshot یا domain snapshots؛ failure scope و قراردادها هم‌راستا شوند.
- **Regression Surface:** NTSW transform, HR contract, Abbasi fallback, slots, UI
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F012 — فایل رسمی قبل از تأیید gate نوشته می‌شود

- **ID:** F012
- **Severity:** HIGH
- **Evidence:** _run_warehouse(build_report) قبل از validate_sources/build_business_dwh/evaluate اجرا می‌شود؛ build_report فایل daily_report_path را save می‌کند و extracts/audit نیز نوشته می‌شوند.
- **File / Function:** `gsi/warehouse/bridge.py:9` — `run_pipeline`
- **Root Cause:** promotion فایل‌های خروجی داخل پروتکل publish نیست.
- **Business Impact:** یک XLSX متعلق به اجرای ردشده می‌تواند در مسیر رسمی روز قرار بگیرد؛ pointer سالم کافی نیست.
- **Potential Fix — پیشنهاد، اجرا نشده:** خروجی در run-specific staging و promote atomic پس از قبولی؛ manifest مشترک فایل/DB.
- **Regression Surface:** Excel reports, daily email input, extracts, report path
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F013 — Oracle هم‌پوشان یک ردیف ترکیبی می‌سازد

- **ID:** F013
- **Severity:** HIGH
- **Evidence:** ابتدای فایل و commentها از انتخاب یک row کامل می‌گویند، ولی loop هم‌پوشانی stock/need/cars/share را field-wise max می‌گیرد و chosen_sheet یک شیت باقی می‌ماند.
- **File / Function:** `gsi/adapters/a40_oracle.py:41` — `transform`
- **Root Cause:** سیاست non-additive max با روایت single-row provenance ناسازگار است.
- **Business Impact:** موجودی/نیاز ممکن است متعلق به هیچ snapshot واقعی نباشد و lineage تک‌شیتی گمراه‌کننده شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** تصمیم مالک داده درباره max یا chosen-row؛ اگر max معتبر است lineage در سطح field و تاریخ.
- **Regression Surface:** Oracle union, resistance, criticality, material view
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F014 — فرض جمع‌پذیری تکرارهای درون شیت Oracle اثبات نشده

- **ID:** F014
- **Severity:** HIGH
- **Evidence:** پس از حذف exact logical duplicates، stock و cars بر اساس material جمع می‌شوند؛ location/bucket در COLUMN_MAP و کلید نیست.
- **File / Function:** `gsi/adapters/a40_oracle.py:150` — `_collapse_material_grain`
- **Root Cause:** تمایز duplicate snapshot از stock-location row بدون هویت bucket انجام می‌شود.
- **Business Impact:** Double counting در نسخه‌های تکراری یا undercount دو bucket با مقادیر یکسان.
- **Potential Fix — پیشنهاد، اجرا نشده:** قرارداد native grain واقعی و کلید location/snapshot؛ بدون شاهد، quarantine یا conflict.
- **Regression Surface:** Oracle inventory totals, daily need, supply position
- **Confidence:** MEDIUM — code confirmed; business validity UNKNOWN / NEEDS EVIDENCE
- **Verification:** STATIC

## F015 — Flat report فقط نماینده اول PR/Material سفارش را می‌گیرد

- **ID:** F015
- **Severity:** HIGH
- **Evidence:** MOGH_MATERIAL و MOGH_KEY_PR هر کدام first_valid؛ PRS_ALL/MATERIALS_ALL و OMPI حفظ شده‌اند اما Pipeline از main برای ساخت key و join SAP/Oracle استفاده می‌کند.
- **File / Function:** `gsi/adapters/moghavemat.py:373` — `_aggregate`
- **Root Cause:** order-level projection ورودی تحلیل item-level است.
- **Business Impact:** تحلیل اقلام دیگر در flat criticality/legacy UI ناقص؛ independent first_validها می‌توانند ترکیب غیرهم‌ردیف بسازند.
- **Potential Fix — پیشنهاد، اجرا نشده:** consumers item-level از facts/OMPI؛ flat فقط خلاصه صریح؛ ممنوعیت تفسیر نماینده به‌عنوان کل سفارش.
- **Regression Surface:** Flat joins, supply_position, Oracle, SAP, inventory filters
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F016 — مبالغ Commercial Expert بدون dedupe و currency grain جمع می‌شوند

- **ID:** F016
- **Severity:** HIGH
- **Evidence:** PI_LINE_VALUE، QTY_IN_ORDER و QTY_IN_PART مستقیماً sum؛ currency first_valid؛ DATA_TYPE و revision در گروه‌بندی نیستند.
- **File / Function:** `gsi/adapters/moghavemat.py:373` — `_aggregate`
- **Root Cause:** سطر export چندنوعی به‌عنوان line additive فرض شده است.
- **Business Impact:** PI/quantity با repeated workflow/partial rows متورم یا چندارزی می‌شود؛ Cash Flow نیز PI_VALUE_SUM را مصرف می‌کند.
- **Potential Fix — پیشنهاد، اجرا نشده:** natural line ID، version/data-type semantics و currency/UOM grain؛ جمع فقط additive contract.
- **Regression Surface:** Commercial main, cashflow registration value, quantity KPIs
- **Confidence:** MEDIUM — implementation definite; real duplication UNKNOWN / NEEDS EVIDENCE
- **Verification:** STATIC

## F017 — PO fact به PR/Material هدر متصل می‌شود نه فیلد اختصاصی PO

- **ID:** F017
- **Severity:** HIGH
- **Evidence:** P06: KEY_PR=1000000001 و KEY_MATERIAL=PRMAT در po_items، درحالی‌که SAP_PO_PR=1000000002 و SAP_PO_MATERIAL=POMAT است. business_dwh نیز generic keys را ذخیره می‌کند.
- **File / Function:** `gsi/adapters/a60_finance.py:46` — `transform`
- **Root Cause:** po_items از raw_rows با generic PR/material بدون conflict resolution ساخته شده است.
- **Business Impact:** PO به PR/Material غلط نسبت داده می‌شود اگر export آن‌ها را متفاوت نشان دهد.
- **Potential Fix — پیشنهاد، اجرا نشده:** PO-specific lineage با مقایسه و quarantine تضاد؛ عدم فرض برابری دو ستون.
- **Regression Surface:** SAP facts, relations, chatbot PR search, planning
- **Confidence:** HIGH — reproduced
- **Verification:** P06

## F018 — Workflow observation به‌عنوان event و latest PR نمایش داده می‌شود

- **ID:** F018
- **Severity:** HIGH
- **Evidence:** workflow_key شامل payload و SAP_SOURCE_ROW است؛ reorder یا تغییر صفات یک workflow رکورد تازه می‌سازد. chatbot len(wf_rows) را workflow_events می‌نامد؛ latest_pr از آخرین pr_item مرتب‌شده رشته‌ای انتخاب می‌شود نه تازه‌ترین تاریخ.
- **File / Function:** `gsi/knowledge_desk/operational.py:78` — `_pr_semantic`
- **Root Cause:** هویت export-row با هویت event یکی شده؛ وضعیت PR چندقلمی قرارداد aggregation ندارد.
- **Business Impact:** event/rework count و آخرین وضعیت نادرست؛ history ظاهری می‌تواند تغییر ترتیب فایل باشد.
- **Potential Fix — پیشنهاد، اجرا نشده:** observation/event مدل جدا، stable source event identity، per-item status و latest بر اساس timestamp مستند.
- **Regression Surface:** SAP workflow, chatbot, Process planning, snapshots
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F019 — safe_merge حقایق many-to-one را قبل از کنترل یکتایی حذف می‌کند

- **ID:** F019
- **Severity:** HIGH
- **Evidence:** dedupe_on_key پیش از join روی کلید راست drop_duplicates می‌کند؛ SATA/clearance روی BL، credit/FX/IL روی REG. row-count gate فقط سمت چپ را حفظ می‌کند.
- **File / Function:** `gsi/dataio/merge.py:65` — `safe_merge`
- **Root Cause:** عدم تکثیر ردیف به‌جای حفظ grain تجاری هدف کنترل است.
- **Business Impact:** چند LC/خرید ارز/کوتاژ/REG مرتبط با BL به یک نماینده محدود می‌شود؛ خطای fan-out با data loss جایگزین می‌شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** projectionهای نام‌دار latest/summary و separate native facts؛ cardinality diagnostics قبل از کاهش.
- **Regression Surface:** Flat enrichment, logistics, finance, customs
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F020 — کلید مرکب خالی به کلید قابل join تبدیل می‌شود

- **ID:** F020
- **Severity:** MEDIUM
- **Evidence:** P07: A="", B="" به "|" تبدیل و دو طرف match شدند. شرط blank در dedupe فقط کل رشته را بررسی می‌کند.
- **File / Function:** `gsi/dataio/merge.py:65` — `safe_merge`
- **Root Cause:** اعتبار اجزای مرکب قبل از concatenation کنترل نمی‌شود.
- **Business Impact:** اتصال رکوردهای بدون کلید یا partial key به داده نامربوط.
- **Potential Fix — پیشنهاد، اجرا نشده:** tuple keys و validity mask روی تک‌تک اجزا؛ escaping delimiter.
- **Regression Surface:** ORDER_MATERIAL, BL_ORDER, custom config
- **Confidence:** HIGH — reproduced
- **Verification:** P07

## F021 — برخی تاریخ‌های domain هرگز از adapter صحیح تغذیه نمی‌شوند

- **ID:** F021
- **Severity:** HIGH
- **Evidence:** DERIVED: DISCHARGE_DATE از CL_DISCHARGE_DATE و SATA_DATE از SATA_DATE؛ adapterهای فعلی BL_DISCHARGE_DATE و SATA_TRACKING_DATE تولید می‌کنند.
- **File / Function:** `gsi/stages/s20_derive.py:158` — `DeriveStage`
- **Root Cause:** نام‌های canonical با adapter contract همگام نیستند.
- **Business Impact:** تخلیه موجود نادیده گرفته می‌شود؛ open shipped به transit می‌رود و eventlog تاریخ‌های واقعی را از دست می‌دهد.
- **Potential Fix — پیشنهاد، اجرا نشده:** mapping audit از producer به consumer با assertion ستون‌های واقعی و meaning؛ نه صرف alias مشابه.
- **Regression Surface:** Inventory location, lead times, legacy eventlog, process comparisons
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F022 — معانی تاریخ دریافت سند و رسید مالی مخلوط شده‌اند

- **ID:** F022
- **Severity:** HIGH
- **Evidence:** FIN_RECEIPT_DATE از SATA_DOC_RECEIVED است که adapter آن را «دریافت اسناد» می‌خواند؛ s80 آن را Financial Receipt Booked و terminal activity می‌داند.
- **File / Function:** `gsi/stages/s20_derive.py:158` — `DeriveStage`
- **Root Cause:** تاریخ دو رویداد متفاوت semantic equivalent فرض شده است.
- **Business Impact:** پرونده ممکن است صرفاً با دریافت اسناد بسته تلقی شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** تعریف دقیق از مالک SATA و ستون رسید مالی مستقل؛ تا آن زمان UNKNOWN.
- **Regression Surface:** Eventlog terminal, conformance, KPI completion
- **Confidence:** HIGH — mapping confirmed; business equivalence UNKNOWN / NEEDS EVIDENCE
- **Verification:** STATIC

## F023 — مسیر legacy رفع تعهد همه نسخه‌های فایل را جمع می‌کند

- **ID:** F023
- **Severity:** HIGH
- **Evidence:** کوئری wh_measure فاقد file/run/published filter است. P08: دو فایل با balance=50 به total=100 رسیدند. chain نیز آخرین پیمایش را روی مبلغ همان ارز overwrite می‌کند بدون ORDER BY.
- **File / Function:** `gsi/warehouse/fx_obligation.py:165` — `totals_by_currency`
- **Root Cause:** raw archive همه نسخه‌هاست ولی reader آن را current ledger فرض می‌کند.
- **Business Impact:** Double counting تاریخچه و انتخاب غیرقطعی مانده؛ از Cash Flow جدید مستقل است.
- **Potential Fix — پیشنهاد، اجرا نشده:** select published source-file membership، native obligation key و per-currency aggregation.
- **Regression Surface:** Warehouse obligation UI/CLI consumers, historical file ingestion
- **Confidence:** HIGH — reproduced
- **Verification:** P08

## F024 — قطع مسیر KB حذف منطقی و عدم بازیابی می‌سازد

- **ID:** F024
- **Severity:** HIGH
- **Evidence:** P09: یک سند فعال؛ root unavailable → deleted=1؛ بازگرداندن فایل با همان mtime/size → unchanged=1 و active=0.
- **File / Function:** `gsi/knowledge_desk/indexer.py:137` — `build_index`
- **Root Cause:** seen برای root ناموفق خالی است؛ sweep همه اسناد را DELETED می‌کند؛ unchanged branch status را ACTIVE نمی‌کند.
- **Business Impact:** مستندات معتبر از پاسخ‌ها ناپدید می‌شوند و بازگشت شبکه کافی نیست.
- **Potential Fix — پیشنهاد، اجرا نشده:** delete sweep فقط roots با scan موفق؛ restore state در fast path با تضمین chunks.
- **Regression Surface:** KB indexing, network outages, static export, questions
- **Confidence:** HIGH — reproduced
- **Verification:** P09

## F025 — grains ناقص و nullable-key loophole در Quality Gate

- **ID:** F025
- **Severity:** HIGH
- **Evidence:** برای frame فاقد قرارداد INFO/True؛ nullable SAP PR item ردیف‌ها را از complete_mask بیرون می‌برد و uniqueness فقط روی completeهاست. P10: duplicate PR+blank item از GRAIN_UNIQUENESS عبور کرد.
- **File / Function:** `gsi/warehouse/reliability.py:180` — `validate_frame`
- **Root Cause:** nullable بودن جزء کلید با عدم نیاز به uniqueness یکی شده است.
- **Business Impact:** قبولی gate اثبات native grain بسیاری از منابع و fallback item نیست.
- **Potential Fix — پیشنهاد، اجرا نشده:** قرارداد تمام frames و uniqueness null-aware؛ required PR مستقل از optional item.
- **Regression Surface:** SAP PR fallback, HR, FX, credit, logistics, process inputs
- **Confidence:** HIGH — reproduced
- **Verification:** P10

## F026 — ردیف‌های FX دارای ORDER ولی فاقد REG در Cash Flow حذف می‌شوند

- **ID:** F026
- **Severity:** HIGH
- **Evidence:** FX adapter رکورد دارای ORDER را معتبر نگه می‌دارد؛ bundle در loop FX فقط _source_reg می‌گیرد و از order_to_reg استفاده نمی‌کند؛ _event با case_id خالی return می‌کند.
- **File / Function:** `gsi/cashflow/dwh.py:225` — `bundle_from_dwh`
- **Root Cause:** mapping ساخته‌شده برای commercial/scope در رویداد مالی استفاده نمی‌شود.
- **Business Impact:** خرید ارز سالم دارای ارتباط قابل حل در native data هست ولی وارد event ledger نمی‌شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** resolve با direct/hub evidence و ثبت unresolved financial rows؛ حفظ ORDER/BL در events.
- **Regression Surface:** Cash Flow purchase/payment, scope reconciliation, orphan totals
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F027 — شناسه commitment در Cash Flow تعداد سطر است، نه شناسه تعهد

- **ID:** F027
- **Severity:** HIGH
- **Evidence:** native_ref از NTSW_COMMIT_ROWS ساخته می‌شود؛ دو REG با COMMIT_ROWS=1 هر دو source_event_id="1:COMMITMENT" دارند. engine replay detector source+source_event_id را cross-case چک می‌کند. P11 هر دو event را با CONFLICTING_SOURCE_EVENT_ID قرنطینه کرد.
- **File / Function:** `gsi/cashflow/dwh.py:225` — `bundle_from_dwh`
- **Root Cause:** count به‌جای stable source identity استفاده شده است.
- **Business Impact:** تعهد پرونده‌های مستقل به‌صورت CONFLICTING_SOURCE_EVENT_ID قرنطینه می‌شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** REG+native commitment identity یا صریحاً summary snapshot ID؛ عدم جعل event ID.
- **Regression Surface:** Cash Flow accepted ledger, commitment summary, multi-REG runs
- **Confidence:** HIGH — reproduced
- **Verification:** P11

## F028 — read all_data_sheets در عمل فقط بزرگ‌ترین شیت را می‌خواند

- **ID:** F028
- **Severity:** MEDIUM
- **Evidence:** شاخه all_data_sheets برای هر فایل فقط best با بیشترین len را به frames اضافه می‌کند؛ raw capture همه شیت‌ها را حفظ می‌کند.
- **File / Function:** `gsi/dataio/reader.py:151` — `_read_targets`
- **Root Cause:** نام strategy با implementation متفاوت است.
- **Business Impact:** داده شیت عملیاتی دوم به standardized/process/DWH نمی‌رسد.
- **Potential Fix — پیشنهاد، اجرا نشده:** همه شیت‌های مجاز همراه signature validation یا rename strategy با قرارداد تک‌شیت.
- **Regression Surface:** Clearance multi-file, mixed transport, sheet coverage
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F029 — جداسازی صریح Export Clearance از Import پیدا نشد

- **ID:** F029
- **Severity:** HIGH
- **Evidence:** pattern *Clearance* و all_data_sheets؛ mapping فاقد direction/import-export و در population/process filter صریح export مشاهده نشد.
- **File / Function:** `gsi/adapters/a30_customs.py:27` — `ClearanceAdapter`
- **Root Cause:** transport با flow direction متفاوت است و قرارداد جهت وجود ندارد.
- **Business Impact:** در صورت وجود ExportClearance با کلید مشترک امکان آلودگی KPI واردات؛ وجود چنین فایل در محیط فعلی UNKNOWN / NEEDS EVIDENCE.
- **Potential Fix — پیشنهاد، اجرا نشده:** direction field و exclusion/quarantine صریح با fixture export-only.
- **Regression Surface:** Customs, clearance, process, import financial stages
- **Confidence:** MEDIUM — conditional risk
- **Verification:** STATIC

## F030 — فازی بودن header mapping می‌تواند معنای کلید را تغییر دهد

- **ID:** F030
- **Severity:** MEDIUM
- **Evidence:** بعد از exact match، substring در هر دو جهت با shortest-score برنده می‌شود؛ std ستون ناموجود را blank می‌سازد. collision normalized header اولین را برمی‌گزیند.
- **File / Function:** `gsi/core/columns.py:38` — `find_col`
- **Root Cause:** mapping ambiguity و missing-column error به شکل uniform contract گزارش نمی‌شود.
- **Business Impact:** اشتباه semantic بدون exception؛ نبود fuzzy business join به معنی exact header mapping نیست.
- **Potential Fix — پیشنهاد، اجرا نشده:** exact alias allowlist برای keys/measures و ambiguity evidence؛ منع auto-pick در tie.
- **Regression Surface:** All std adapters, SAP prefixed headers, changing Excel layout
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F031 — صفر و Unknown در legacy financial fields یکسان می‌شوند

- **ID:** F031
- **Severity:** HIGH
- **Evidence:** BALANCE/CB_VALUE/FX_PURCHASE_AMOUNT default=0 numeric؛ s55 و s56 نیز fillna(0) دارند؛ cashflow engine جدید None/Decimal را جدا می‌کند.
- **File / Function:** `gsi/stages/s20_derive.py:158` — `DeriveStage`
- **Root Cause:** سیاست missing در دامنه‌ها یکنواخت نیست.
- **Business Impact:** نبود منبع ممکن است صفر مانده/خرید یا risk score کم نمایش داده شود.
- **Potential Fix — پیشنهاد، اجرا نشده:** nullable amounts + coverage/availability flags؛ totals known/unknown جدا.
- **Regression Surface:** Legacy dashboards, risk, commitment, FX vs cashflow consistency
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F032 — دو سیستم Authority با تصمیم متفاوت در تعارض وجود دارد

- **ID:** F032
- **Severity:** MEDIUM
- **Evidence:** SOURCE_PRIORITY hardcoded و hub=390 پایین‌تر از direct NTSW=400 است؛ registration_bridge direct/hub را هم‌اولویت در candidate conflict می‌گیرد؛ authority.py tiers از YAML در import cache می‌شود.
- **File / Function:** `gsi/cashflow/dwh.py:126` — `_candidate_maps`
- **Root Cause:** policy موزع و قواعد tie-break مستقل.
- **Business Impact:** یک ORDER در flat unresolved ولی در Cash Flow resolved؛ تغییر config در یک consumer اثر نمی‌کند.
- **Potential Fix — پیشنهاد، اجرا نشده:** policy semantic مشترک و explicit derived-path confidence؛ test conflict parity.
- **Regression Surface:** Canonical resolver, population, cashflow, config reload
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F033 — fallback استاندارد در snapshot تازه دوباره ذخیره نمی‌شود

- **ID:** F033
- **Severity:** MEDIUM
- **Evidence:** در مسیر fallback self.sources=published_frames است ولی wh.frame standardized اجرا نمی‌شود؛ build DWH آن را با run جدید upsert می‌کند.
- **File / Function:** `gsi/pipeline.py:132` — `load_sources`
- **Root Cause:** freshness lineage بین source snapshot و publication run جدا مدل نشده است.
- **Business Impact:** پس از انتشار degraded run، fallback دفعه بعد ممکن است frame آن source را پیدا نکند؛ Cash Flow می‌تواند stale balance را observed_at روز گزارش بنامد.
- **Potential Fix — پیشنهاد، اجرا نشده:** run-source reference به origin snapshot و fetched_at/observed_at مستقل؛ bounded stale policy.
- **Regression Surface:** Repeated optional-source failures, cashflow measurements, provenance
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F034 — خطای operational retrieval به نبود شاهد تبدیل می‌شود

- **ID:** F034
- **Severity:** MEDIUM
- **Evidence:** except Exception:return []؛ query.answer ممکن است فقط doc hits را ANSWERED کند. ID regex فقط اعداد 6..16 رقمی می‌گیرد؛ alphanumeric ORDER/BL/material پشتیبانی معنایی کامل ندارد.
- **File / Function:** `gsi/knowledge_desk/operational.py:158` — `operational_search`
- **Root Cause:** absence evidence، unsupported ID و backend failure نتیجه یکسان دارند.
- **Business Impact:** پاسخ ناقص یا مستند عمومی به سؤال عملیاتی؛ علت واقعی پنهان می‌ماند.
- **Potential Fix — پیشنهاد، اجرا نشده:** typed retrieval outcome با error/unsupported/not_found؛ identifier parser مطابق entity contracts.
- **Regression Surface:** Chatbot answer status, SQL locks/migrations, alphanumeric IDs
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F035 — دریافت متن KB تضمین پاسخ مرتبط/معتبر نیست

- **ID:** F035
- **Severity:** MEDIUM
- **Evidence:** search از OR tokens/BM25 یا LIKE استفاده می‌کند؛ هر hit می‌تواند ANSWERED شود؛ effective-date/authority/citation entailment gate ندارد. AnythingLLM مسیر جدا با mode=chat است و بدون lesson دستور grounding اضافی ندارد.
- **File / Function:** `gsi/knowledge_desk/query.py:59` — `answer`
- **Root Cause:** retrieval relevance با answer sufficiency یکی گرفته شده است.
- **Business Impact:** Extractive chatbot هم می‌تواند متن نامرتبط/قدیمی را پاسخ قطعی جلوه دهد؛ external LLM کنترل‌شده در این پکیج اثبات نشده.
- **Potential Fix — پیشنهاد، اجرا نشده:** minimum relevance و explicit abstention؛ document authority/effective date؛ tests contradictory docs و external grounded mode.
- **Regression Surface:** Offline server, static chatbot, AnythingLLM, KB governance
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F036 — historical warehouse مستقل به pipeline اصلی متصل نیست

- **ID:** F036
- **Severity:** MEDIUM
- **Evidence:** Pipeline.run فقط warehouse.bridge.run_pipeline را صدا می‌زند؛ historical_runtime wrapper در core pipeline فراخوانی نمی‌شود. historical_store مدل dw_run/fact_event دارد و store مدل wh_run مستقل.
- **File / Function:** `gsi/warehouse/historical_runtime.py:23` — `WarehouseRun`
- **Root Cause:** دو نسل persistence بدون مسیر migration/promotion مشترک.
- **Business Impact:** داشتن ماژول historical به معنی ثبت خودکار تاریخچه تمام runtime فعلی نیست.
- **Potential Fix — پیشنهاد، اجرا نشده:** مالکیت و lifecycle هر DB مستند؛ تصمیم migration جدا از Phase 0.
- **Regression Surface:** Historical UI, CLI, profile persistence, old snapshots
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F037 — شواهد endpoint KB شامل کنترل دسترسی application نیست

- **ID:** F037
- **Severity:** MEDIUM
- **Evidence:** HTTP API فاقد احراز هویت و access scope، CORS=*؛ config پیش‌فرض host=0.0.0.0. static payload نیز PRهای DWH را بدون user scope صادر می‌کند.
- **File / Function:** `gsi/knowledge_desk/service.py:20` — `_handler`
- **Root Cause:** اعتماد به شبکه/فایل‌سرور بیرون از کد.
- **Business Impact:** در صورت دسترسی شبکه/پوشه، پرسش از اطلاعات عملیاتی خارج از دامنه مخاطب ممکن است.
- **Potential Fix — پیشنهاد، اجرا نشده:** تعیین deployment boundary و authorization/source scope؛ وضعیت ACL واقعی UNKNOWN / NEEDS EVIDENCE.
- **Regression Surface:** Knowledge server, static snapshots, personal scope
- **Confidence:** MEDIUM — exposure conditional on deployment
- **Verification:** STATIC

## F038 — DocCheck history پیش از process inventory فشرده می‌شود

- **ID:** F038
- **Severity:** MEDIUM
- **Evidence:** transform خروجی std را با dedupe_on_key(ORDER, SUBMIT_DATE) به یک main کاهش می‌دهد؛ frame native docs نگه نمی‌دارد. raw workbook در wh_file موجود است.
- **File / Function:** `gsi/adapters/a60_finance.py:498` — `DocCheckAdapter`
- **Root Cause:** adapter projection و native evidence یک frame شده‌اند.
- **Business Impact:** اسناد و وضعیت‌های قبلی در process ledger قابل مشاهده نیستند؛ row-preservation پس از حذف می‌سنجد.
- **Potential Fix — پیشنهاد، اجرا نشده:** doc_rows native مستقل و main compatibility projection.
- **Regression Surface:** Bank docs, process evidence count, DWH source facts
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F039 — SWIFT در Process Matrix به PAYMENT تعبیر می‌شود

- **ID:** F039
- **Severity:** MEDIUM
- **Evidence:** credit با CRD_SWIFT_DATE بدون receipt evidence، PAYMENT با شرح «پرداخت / وصول ذی‌نفع» emit می‌کند؛ در s55 این دو عمداً جدا هستند.
- **File / Function:** `gsi/resolve/process_evidence.py:145` — `_observations`
- **Root Cause:** تعریف stage میان دو subsystem یکسان نیست.
- **Business Impact:** وجود سوئیفت می‌تواند شاهد وصول تلقی شود؛ مقایسه دو dashboard متناقض است.
- **Potential Fix — پیشنهاد، اجرا نشده:** SWIFT_SENT و BENEFICIARY_RECEIVED جدا؛ stage semantics و source status معتبر.
- **Regression Surface:** Process matrix, FX trace, cashflow, current stage
- **Confidence:** HIGH — code-confirmed
- **Verification:** STATIC

## F040 — serialized latest snapshot و migration/locking کامل نیست

- **ID:** F040
- **Severity:** MEDIUM
- **Evidence:** run_pipeline پس از خروج از with wh.run (آزادشدن writer lock) publish را می‌زند؛ publish ordering gate ندارد. _ensure_schema با wh_meta+user_version=1 از DDL بازمی‌گردد حتی اگر جدول‌های جدید نسخه‌های دیگر نباشند.
- **File / Function:** `gsi/warehouse/store.py:234` — `publish`
- **Root Cause:** writer lifecycle و schema revision کم‌دانه است.
- **Business Impact:** با interleaving ممکن است pointer عقب برود؛ DB قدیمی با version=1 لزوماً همه tables ندارد. وقوع در تولید UNKNOWN / NEEDS EVIDENCE.
- **Potential Fix — پیشنهاد، اجرا نشده:** publish زیر همان lock و monotonic run ordering؛ migrations صریح با نسخه schema.
- **Regression Surface:** Concurrent update, legacy DB upgrades, current slots
- **Confidence:** MEDIUM — static race/migration risk
- **Verification:** STATIC

## Risk coverage

| Requested risk | Findings |
|---|---|
| Silent Data Loss / Orphan Loss | F002, F005, F010, F019, F026, F028, F038 |
| Wrong Grain / Double Counting | F007, F009, F014–F019, F023 |
| Fan-out / Many-to-Many Explosion | F004, F006, F019; registration hub view produces REG×ORDER combinations |
| History Loss / Event-Snapshot Confusion | F003, F009, F018, F023, F033, F036, F038–F039 |
| Authority Violation / Silent Override | F013, F015, F017, F030, F032 |
| Ambiguous Mapping / Incorrect Fallback | F017, F020–F022, F026–F027, F030, F033 |
| Broken Publication | F001–F003, F010–F012, F024, F040 |
| Hidden Coupling / One Domain Blocking Another | F004, F011, F025, F032, F036 |
| Chatbot Hallucination / false factual attribution | F001, F006, F018, F024, F034–F035, F039 |

## محدودیت

مقادیر اثر مالی واقعی، فراوانی duplicate، قرارداد بانک/گمرک، ACL شبکه و صحت business identifiers در داده زنده: **UNKNOWN / NEEDS EVIDENCE**. هیچ فرضی درباره رابطه صرفاً از شباهت نام ستون قطعی نشده است. شواهد بازتولید synthetic هستند و جای reconciliation با source workbook واقعی را نمی‌گیرند.
