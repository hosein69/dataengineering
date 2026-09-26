# FINDINGS_REGISTER — 29.7.7 RC1

تاریخ: 2026-09-22. وضعیت داوری از وضعیت بسته‌شدن جداست. ACCEPT به‌تنهایی به معنی حل‌شدن نیست. این RC برای Review است؛ موارد OPEN_RELEASE_BLOCKER مانع تأیید Production هستند.

مرجع: کد ZIP اصلی + چهار سند Phase 0 + OPUS_REVIEW؛ شواهد اجرایی جدید در review/validation.

| ID | Verdict | Closure | Finding |
|---|---|---|---|
| F001 | ACCEPT | IMPLEMENTED | نشت اجرای مسدودشده به پاسخ چت‌بات |
| F002 | ACCEPT | IMPLEMENTED | ناپدیدشدن شواهد Cash Flow نسخه منتشرشده بعد از اجرای مسدود |
| F003 | ACCEPT_WITH_MODIFICATION | PARTIAL | حذف و current بودن Business Facts تعریف نشده |
| F004 | ACCEPT_WITH_MODIFICATION | PARTIAL | ادغام سفارش‌های مستقل در Process Case از طریق Material/Employee |
| F005 | ACCEPT | IMPLEMENTED | حذف duplicate observations و سپس مسدودشدن انتشار |
| F006 | REJECT | NO_CHANGE | تبدیل frame مشتق به شاهد مستقیم |
| F007 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | NTSW تخصیص با ارزهای متفاوت یک جمع می‌سازد |
| F008 | ACCEPT | IMPLEMENTED | تشخیص تخصیص از عبارت منفی |
| F009 | ACCEPT_WITH_MODIFICATION | PARTIAL | تعهد تکراری به جای snapshot به‌عنوان تعهد جدید جمع می‌شود |
| F010 | ACCEPT_WITH_MODIFICATION | PARTIAL | کمبود داده source از gate عبور می‌کند |
| F011 | ACCEPT_WITH_MODIFICATION | PARTIAL | وابستگی کل انتشار به خرابی یک دامنه |
| F012 | ACCEPT | IMPLEMENTED | فایل رسمی قبل از تأیید gate نوشته می‌شود |
| F013 | ACCEPT_WITH_MODIFICATION | PARTIAL | Oracle هم‌پوشان یک ردیف ترکیبی می‌سازد |
| F014 | DEFER_NEEDS_DATA | OPEN | فرض جمع‌پذیری تکرارهای درون شیت Oracle اثبات نشده |
| F015 | ACCEPT_WITH_MODIFICATION | DOCUMENTED | Flat report فقط نماینده اول PR/Material سفارش را می‌گیرد |
| F016 | ACCEPT_WITH_MODIFICATION | PARTIAL | مبالغ Commercial Expert بدون dedupe و currency grain جمع می‌شوند |
| F017 | ACCEPT | IMPLEMENTED | PO fact به PR/Material هدر متصل می‌شود نه فیلد اختصاصی PO |
| F018 | ACCEPT_WITH_MODIFICATION | PARTIAL | Workflow observation به‌عنوان event و latest PR نمایش داده می‌شود |
| F019 | ACCEPT_WITH_MODIFICATION | PARTIAL | safe_merge حقایق many-to-one را قبل از کنترل یکتایی حذف می‌کند |
| F020 | ACCEPT | IMPLEMENTED | کلید مرکب خالی به کلید قابل join تبدیل می‌شود |
| F021 | ACCEPT_WITH_MODIFICATION | PARTIAL | برخی تاریخ‌های domain هرگز از adapter صحیح تغذیه نمی‌شوند |
| F022 | ACCEPT | IMPLEMENTED | معانی تاریخ دریافت سند و رسید مالی مخلوط شده‌اند |
| F023 | ACCEPT | OPEN_RELEASE_BLOCKER | مسیر legacy رفع تعهد همه نسخه‌های فایل را جمع می‌کند |
| F024 | ACCEPT_WITH_MODIFICATION | PARTIAL | قطع مسیر KB حذف منطقی و عدم بازیابی می‌سازد |
| F025 | ACCEPT_WITH_MODIFICATION | PARTIAL | grains ناقص و nullable-key loophole در Quality Gate |
| F026 | ACCEPT_WITH_MODIFICATION | PARTIAL | ردیف‌های FX دارای ORDER ولی فاقد REG در Cash Flow حذف می‌شوند |
| F027 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | شناسه commitment در Cash Flow تعداد سطر است، نه شناسه تعهد |
| F028 | ACCEPT | OPEN_RELEASE_BLOCKER | read all_data_sheets در عمل فقط بزرگ‌ترین شیت را می‌خواند |
| F029 | DEFER_NEEDS_DATA | OPEN | جداسازی صریح Export Clearance از Import پیدا نشد |
| F030 | ACCEPT_WITH_MODIFICATION | PARTIAL | فازی بودن header mapping می‌تواند معنای کلید را تغییر دهد |
| F031 | ACCEPT | OPEN_RELEASE_BLOCKER | صفر و Unknown در legacy financial fields یکسان می‌شوند |
| F032 | DEFER_NEEDS_DATA | OPEN | دو سیستم Authority با تصمیم متفاوت در تعارض وجود دارد |
| F033 | ACCEPT_WITH_MODIFICATION | PARTIAL | fallback استاندارد در snapshot تازه دوباره ذخیره نمی‌شود |
| F034 | ACCEPT_WITH_MODIFICATION | PARTIAL | خطای operational retrieval به نبود شاهد تبدیل می‌شود |
| F035 | ACCEPT_WITH_MODIFICATION | PARTIAL | دریافت متن KB تضمین پاسخ مرتبط/معتبر نیست |
| F036 | ACCEPT_WITH_MODIFICATION | DOCUMENTED | historical warehouse مستقل به pipeline اصلی متصل نیست |
| F037 | DEFER_NEEDS_DATA | OPEN_RELEASE_BLOCKER | شواهد endpoint KB شامل کنترل دسترسی application نیست |
| F038 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | DocCheck history پیش از process inventory فشرده می‌شود |
| F039 | ACCEPT | IMPLEMENTED | SWIFT در Process Matrix به PAYMENT تعبیر می‌شود |
| F040 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | serialized latest snapshot و migration/locking کامل نیست |
| N01 | ACCEPT_WITH_MODIFICATION | PARTIAL | HIGH — SCHEMA_DRIFT تغییر هدر منبع را نمی‌بیند؛ فیلد کسب‌وکاری بی‌صدا خالی می‌شود |
| N02 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | HIGH — نمای `dwh_registration_hub` cross-product تولید می‌کند و در UI انبار نمایش داده می‌شود |
| N03 | ACCEPT_WITH_MODIFICATION | PARTIAL | HIGH — طبقه‌بند وضعیت فارسی در لایه process، وضعیت‌های رایج را وارونه می‌کند |
| N04 | ACCEPT_WITH_MODIFICATION | PARTIAL | HIGH — گارد انفجار سطر مرده است؛ یک چک BLOCK هرگز نمی‌تواند فعال شود |
| N05 | ACCEPT_WITH_MODIFICATION | PARTIAL | HIGH — ستون‌های مشتقِ بی‌تولیدکننده، یک ثابت جعلی و یک شاخه مرده در گزارش رسمی می‌سازند |
| N06 | ACCEPT_WITH_MODIFICATION | IMPLEMENTED | HIGH — PR Item با چند PO Item: فقط یک PO در fact قلم PR باقی می‌ماند |
| N07 | ACCEPT | IMPLEMENTED | HIGH — گیت PROCESS_ROW_PRESERVATION خودغیرفعال‌شونده است |
| N08 | ACCEPT | OPEN_RELEASE_BLOCKER | MEDIUM — شناسه پرونده فرایندی پایدار نیست |
| N09 | ACCEPT_WITH_MODIFICATION | PARTIAL | MEDIUM — `evidence_count` تعداد (ردیف × اجرا) است، نه تعداد شواهد |
| N10 | ACCEPT | IMPLEMENTED | MEDIUM — اجرای مسدودشده، `wh_schema_baseline` را دائمی تغییر می‌دهد |
| N11 | ACCEPT_WITH_MODIFICATION | PARTIAL | MEDIUM — `_SOURCE_FILE` نام فایل اصلی را حمل نمی‌کند؛ دو fallback مستند مرده‌اند |
| N12 | ACCEPT_WITH_MODIFICATION | PARTIAL | MEDIUM — تعیین «آخرین وضعیت» درخواست تخصیص قطعی نیست |
| N13 | ACCEPT_WITH_MODIFICATION | DOCUMENTED | MEDIUM — REG غیر ۸‌رقمی بی‌صدا از جمعیت اصلی حذف می‌شود |

## F001 — نشت اجرای مسدودشده به پاسخ چت‌بات

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: پس از انتشار R1 و ساخت R2 مسدود، pointer روی R1 ماند اما پاسخ وضعیت NEW_BLOCKED را با run_id=R1 برگرداند. کوئری Fact و Relation شرط run ندارد.
- Root Cause: Business facts پیش از gate به‌صورت mutable upsert می‌شوند؛ run_id فقط در متن پاسخ تزریق می‌شود.
- Business Impact: نمایش داده تأییدنشده با ادعای Published و as-of غلط.
- Minimum Safe Change / Correct interpretation: Published readers use connection-pinned typed run snapshots; blocked R2 cannot change R1. Legacy mutable state is not certified as a historical snapshot.
- Affected Modules: warehouse/snapshots.py; warehouse/store.py; knowledge_desk/operational.py; app/warehouse_view.py
- Regression Surface: Business DWH, operational/static chatbot, warehouse UI, publish rollback
- Test Required / Verification: test_blocked_run_isolation
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F002 — ناپدیدشدن شواهد Cash Flow نسخه منتشرشده بعد از اجرای مسدود

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: source_row با PK=(source,frame,row_hash) در اجرای جدید last_seen_run را تغییر می‌دهد؛ reader فقط last_seen_run=published را می‌خواند. در P01 از دو frame قبلی فقط یک frame باقی ماند؛ commitment بدون تغییر ناپدید شد.
- Root Cause: last_seen برای membership تاریخی استفاده شده است.
- Business Impact: Cash Flow نسخه سالم قبلی ناقص می‌شود حتی وقتی gate درست pointer را حفظ کرده است.
- Minimum Safe Change / Correct interpretation: Source representations retain run membership and physical multiplicity in typed snapshots; cashflow reads published run.
- Affected Modules: warehouse/business_dwh.py; cashflow/dwh.py
- Regression Surface: Fallback, Cash Flow, blocked/failed run, repeat ingestion
- Test Required / Verification: test_blocked_run_isolation
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F003 — حذف و current بودن Business Facts تعریف نشده

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: facts و dimensions و relations upsert می‌شوند؛ نبود رکورد در export بعدی نه expire می‌شود نه tombstone دارد؛ reader چت‌بات همه را می‌خواند.
- Root Cause: current-state tables با تاریخچه first/last seen مخلوط‌اند؛ absence policy وجود ندارد.
- Business Impact: اقلام حذف‌شده/منقضی و روابط قدیمی به‌عنوان وضعیت جاری باقی می‌مانند.
- Minimum Safe Change / Correct interpretation: Current projection is rebuilt per run; prior snapshots retained. Omission is NOT a deletion event. Full-export versus delta semantics still require per-source contracts.
- Affected Modules: warehouse/business_dwh.py; warehouse/snapshots.py
- Regression Surface: SAP deletion, Oracle stock, allocation requests, all dimensions
- Test Required / Verification: test_published_omission_preserves_history
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F004 — ادغام سفارش‌های مستقل در Process Case از طریق Material/Employee

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: همه ENTITY_COLS از جمله MATERIAL و EMP با union-find به component واحد وصل می‌شوند. دو ORDER با M1 مشترک در P02 یک case با ORDER_COUNT=2 شدند.
- Root Cause: اشتراک dimension با هویت پرونده کسب‌وکاری یکسان گرفته شده است.
- Business Impact: مراحل سفارش دیگر شکاف این سفارش را پُر می‌کنند؛ owner، bottleneck و تکمیل فرایند آلوده می‌شود.
- Minimum Safe Change / Correct interpretation: Material/Employee do not form components; material does not override a concrete case attachment. Shared PR/REG and persistent case identities still require object-centric cardinality policy.
- Affected Modules: resolve/process_evidence.py
- Regression Surface: Process cases, stage matrix, actions, UI, case IDs
- Test Required / Verification: test_shared_dimensions_do_not_merge
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F005 — حذف duplicate observations و سپس مسدودشدن انتشار

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: _row_ref hash محتواست و idx برای ردیف غیرخالی در شناسه دخیل نیست؛ drop_duplicates OBSERVATION_ID دو ردیف یکسان را یکی می‌کند. P03: expected=2, preserved=1.
- Root Cause: هویت observation با hash محتوای business یکی شده؛ row-preservation تعداد input را انتظار دارد.
- Business Impact: ورودی تکراری مشروع gate کل گزارش/DWH را مسدود می‌کند؛ multiplicity شواهد از دست می‌رود.
- Minimum Safe Change / Correct interpretation: Content hash plus ordinal preserves duplicate physical representations. This is run/frame ordinal lineage, not a fabricated physical Excel row number.
- Affected Modules: resolve/process_evidence.py; warehouse/business_dwh.py
- Regression Surface: Process row gate, all adapters, duplicate semantics
- Test Required / Verification: test_duplicate_orphan_preservation
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F006 — تبدیل frame مشتق به شاهد مستقیم

- Verdict: **REJECT**
- Closure: **NO_CHANGE**
- Evidence: تنها SAP semantic frames از relation extraction مستثنا هستند؛ برای moghavemat/main، inventory و OMPI و lines و دیگر frames زوج کلیدها DIRECT_COOBSERVED می‌شوند. main تجمیعی است و first_validهای مستقل دارد.
- Root Cause: source frame الزاماً physical/native row نیست؛ whitelist عمومی زوج‌ها provenance معنایی را اثبات نمی‌کند.
- Business Impact: رابطه synthetic با عنوان مستقیم در DWH/چت‌بات؛ evidence_count از چند representation و run زیاد می‌شود.
- Minimum Safe Change / Correct interpretation: The cited moghavemat/main example lacks canonical PR/Material columns. That concrete alleged direct relation is not produced. This does not certify every derived frame; representation counting remains a separate limitation.
- Affected Modules: warehouse/business_dwh.py:_source_business_keys; adapters/moghavemat.py:_aggregate
- Regression Surface: Entity relations, OMPI, chatbot, registration hub
- Test Required / Verification: Existing moghavemat relation tests; static key-map review
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F007 — NTSW تخصیص با ارزهای متفاوت یک جمع می‌سازد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence: groupby فقط REG است؛ amountها جمع و REQ_CURRENCY از آخرین ردیف گرفته می‌شود. P04: 100 USD + 100 EUR → 200 EUR.
- Root Cause: currency بخشی از grain تجمیع نیست و guard چندارزی commitment در allocation تکرار نشده است.
- Business Impact: اشتباه مبلغ تخصیص/صف و همه خلاصه‌های downstream.
- Minimum Safe Change / Correct interpretation: Keep REG compatibility grain; mixed/unknown-currency summary amounts become NaN while request ledger retains individual currencies. Do not add a REG×currency frame to existing one-to-one joins.
- Affected Modules: adapters/a50_ntsw.py
- Regression Surface: Allocation, queue, FX, cashflow fallback, report totals
- Test Required / Verification: test_mixed_currency_allocation_unknown_and_native_intact
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F008 — تشخیص تخصیص از عبارت منفی

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: state ابتدا substring مثبت تایید یا تاریخ تخصیص را بررسی می‌کند. P04: «تایید نشده» بدون تاریخ، ALLOCATED شد.
- Root Cause: واژه‌نامه substring بدون نفی و precedence زمانی وضعیت ابطال.
- Business Impact: درخواست تأییدنشد‌ه/لغوشده می‌تواند تخصیص واقعی شمرده شود.
- Minimum Safe Change / Correct interpretation: Rejection and negation take precedence over positive substrings and allocation dates.
- Affected Modules: adapters/a50_ntsw.py
- Regression Surface: Allocation states, process stage, cashflow events
- Test Required / Verification: test_mixed_currency_allocation_unknown_and_native_intact
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F009 — تعهد تکراری به جای snapshot به‌عنوان تعهد جدید جمع می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: COMMIT_ROW خوانده می‌شود اما در dedupe/grain به کار نمی‌رود. P05: دو نسخه همان commitment با balance=50 → balance=100.
- Root Cause: فرض هر ردیف یک تعهد مستقل بدون natural-key contract.
- Business Impact: تورم مانده و تعهد اولیه. تکرار واقعی در داده تولیدی: UNKNOWN / NEEDS EVIDENCE.
- Minimum Safe Change / Correct interpretation: Preserve commitment_rows; identical native IDs deduplicate in accepted projection; differing monetary snapshots quarantine. Latest-state contract remains unresolved; direct private _agg_commitment helper still assumes validated input for conflicting IDs.
- Affected Modules: adapters/a50_ntsw.py
- Regression Surface: Commitment engine, deadlines, source summary, DWH
- Test Required / Verification: Existing NTSW tests; native branch inspection
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F010 — کمبود داده source از gate عبور می‌کند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: برای source اختیاری با فایل/شیت مفقود return {}؛ Pipeline.source_failures فقط exceptionها را می‌گیرد؛ validate_sources فقط frames موجود را اعتبارسنجی می‌کند. moghavemat و ntsw required=false هستند.
- Root Cause: مفقودبودن با عدم applicability/empty valid result تفکیک نمی‌شود و expected-frame contract نیست.
- Business Impact: با وجود یکی از منابع primary، حذف منبع primary دیگر ممکن است به گزارش تازه اما ناقص منجر شود.
- Minimum Safe Change / Correct interpretation: Absent loaded sources emit SOURCE_COVERAGE_GAP. This is coverage, never failure proof. Mandatory source/frame inventory and disabled-source distinction remain incomplete.
- Affected Modules: warehouse/reliability.py
- Regression Surface: Missing source/sheet, primary population, fallback, publication
- Test Required / Verification: Existing reliability and source continuity tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F011 — وابستگی کل انتشار به خرابی یک دامنه

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: critical_sources={abbasi,ntsw,ilappend}؛ BLOCK در هر قرارداد report و dwh را با هم متوقف می‌کند؛ moghavemat critical نیست. exception تعهد چندارزی کل transform NTSW از جمله Import Licence و Allocation را از دسترس خارج می‌کند.
- Root Cause: primary population policy جدید با critical_sources قدیمی هماهنگ نیست؛ isolation در load است نه domain publication.
- Business Impact: خرابی مالی/لجستیکی می‌تواند تازه‌سازی همه دامنه‌ها را متوقف کند.
- Minimum Safe Change / Correct interpretation: Abbasi enrichment failures degrade, not block; NTSW commitment rows quarantine without erasing licence/allocation. Core NTSW/IL source exceptions still block global publication. No per-domain publication protocol added.
- Affected Modules: adapters/a50_ntsw.py; warehouse/reliability.py
- Regression Surface: NTSW transform, HR contract, Abbasi fallback, slots, UI
- Test Required / Verification: Existing failure isolation and process tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F012 — فایل رسمی قبل از تأیید gate نوشته می‌شود

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: _run_warehouse(build_report) قبل از validate_sources/build_business_dwh/evaluate اجرا می‌شود؛ build_report فایل daily_report_path را save می‌کند و extracts/audit نیز نوشته می‌شوند.
- Root Cause: promotion فایل‌های خروجی داخل پروتکل publish نیست.
- Business Impact: یک XLSX متعلق به اجرای ردشده می‌تواند در مسیر رسمی روز قرار بگیرد؛ pointer سالم کافی نیست.
- Minimum Safe Change / Correct interpretation: Run calculations without file publication; after passing checks write run-addressed reports/extracts/audit. Pointer advances only on completed build. Failed generation may leave unreferenced run files, never overwrites earlier official files.
- Affected Modules: warehouse/bridge.py; pipeline.py
- Regression Surface: Excel reports, daily email input, extracts, report path
- Test Required / Verification: test_missing_process_summary_blocks_before_files; test_validation
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F013 — Oracle هم‌پوشان یک ردیف ترکیبی می‌سازد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: ابتدای فایل و commentها از انتخاب یک row کامل می‌گویند، ولی loop هم‌پوشانی stock/need/cars/share را field-wise max می‌گیرد و chosen_sheet یک شیت باقی می‌ماند.
- Root Cause: سیاست non-additive max با روایت single-row provenance ناسازگار است.
- Business Impact: موجودی/نیاز ممکن است متعلق به هیچ snapshot واقعی نباشد و lineage تک‌شیتی گمراه‌کننده شود.
- Minimum Safe Change / Correct interpretation: Existing cross-sheet max policy is explicit in code and tests. Preserve it pending business approval, add per-field SOURCE_SHEETS lineage. This remains a derived composite, not a native Oracle row.
- Affected Modules: adapters/a40_oracle.py
- Regression Surface: Oracle union, resistance, criticality, material view
- Test Required / Verification: Existing Oracle multisheet and union tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F014 — فرض جمع‌پذیری تکرارهای درون شیت Oracle اثبات نشده

- Verdict: **DEFER_NEEDS_DATA**
- Closure: **OPEN**
- Evidence: پس از حذف exact logical duplicates، stock و cars بر اساس material جمع می‌شوند؛ location/bucket در COLUMN_MAP و کلید نیست.
- Root Cause: تمایز duplicate snapshot از stock-location row بدون هویت bucket انجام می‌شود.
- Business Impact: Double counting در نسخه‌های تکراری یا undercount دو bucket با مقادیر یکسان.
- Minimum Safe Change / Correct interpretation: Need physical inventory bucket IDs, UOM, effective dates and duplicate semantics before changing within-sheet sum. No stock aggregation rewrite.
- Affected Modules: adapters/a40_oracle.py
- Regression Surface: Oracle inventory totals, daily need, supply position
- Test Required / Verification: Synthetic tests do not prove actual bucket additivity
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F015 — Flat report فقط نماینده اول PR/Material سفارش را می‌گیرد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **DOCUMENTED**
- Evidence: MOGH_MATERIAL و MOGH_KEY_PR هر کدام first_valid؛ PRS_ALL/MATERIALS_ALL و OMPI حفظ شده‌اند اما Pipeline از main برای ساخت key و join SAP/Oracle استفاده می‌کند.
- Root Cause: order-level projection ورودی تحلیل item-level است.
- Business Impact: تحلیل اقلام دیگر در flat criticality/legacy UI ناقص؛ independent first_validها می‌توانند ترکیب غیرهم‌ردیف بسازند.
- Minimum Safe Change / Correct interpretation: Flat report remains representative compatibility grain; normalized PO facts and OMPI bridge retain multiplicity. Do not claim flat rows are additive procurement facts. No full UI redesign.
- Affected Modules: adapters/moghavemat.py; report consumers
- Regression Surface: Flat joins, supply_position, Oracle, SAP, inventory filters
- Test Required / Verification: Existing multi-PR/OMPI tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F016 — مبالغ Commercial Expert بدون dedupe و currency grain جمع می‌شوند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: PI_LINE_VALUE، QTY_IN_ORDER و QTY_IN_PART مستقیماً sum؛ currency first_valid؛ DATA_TYPE و revision در گروه‌بندی نیستند.
- Root Cause: سطر export چندنوعی به‌عنوان line additive فرض شده است.
- Business Impact: PI/quantity با repeated workflow/partial rows متورم یا چندارزی می‌شود؛ Cash Flow نیز PI_VALUE_SUM را مصرف می‌کند.
- Minimum Safe Change / Correct interpretation: Mixed/unknown-currency commercial PI summary becomes unknown; native line-level amounts remain. Duplicate-line business identity requires source contract.
- Affected Modules: adapters/moghavemat.py
- Regression Surface: Commercial main, cashflow registration value, quantity KPIs
- Test Required / Verification: Existing commercial/supply tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F017 — PO fact به PR/Material هدر متصل می‌شود نه فیلد اختصاصی PO

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: P06: KEY_PR=1000000001 و KEY_MATERIAL=PRMAT در po_items، درحالی‌که SAP_PO_PR=1000000002 و SAP_PO_MATERIAL=POMAT است. business_dwh نیز generic keys را ذخیره می‌کند.
- Root Cause: po_items از raw_rows با generic PR/material بدون conflict resolution ساخته شده است.
- Business Impact: PO به PR/Material غلط نسبت داده می‌شود اگر export آن‌ها را متفاوت نشان دهد.
- Minimum Safe Change / Correct interpretation: Use PO-side PR/item/material when supplied; header PR relation remains separate. Conflicting header/PO PR is recorded as SAP_HEADER_PO_PR_CONFLICT.
- Affected Modules: warehouse/business_dwh.py
- Regression Surface: SAP facts, relations, chatbot PR search, planning
- Test Required / Verification: test_po_own_identity
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F018 — Workflow observation به‌عنوان event و latest PR نمایش داده می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: workflow_key شامل payload و SAP_SOURCE_ROW است؛ reorder یا تغییر صفات یک workflow رکورد تازه می‌سازد. chatbot len(wf_rows) را workflow_events می‌نامد؛ latest_pr از آخرین pr_item مرتب‌شده رشته‌ای انتخاب می‌شود نه تازه‌ترین تاریخ.
- Root Cause: هویت export-row با هویت event یکی شده؛ وضعیت PR چندقلمی قرارداد aggregation ندارد.
- Business Impact: event/rework count و آخرین وضعیت نادرست؛ history ظاهری می‌تواند تغییر ترتیب فایل باشد.
- Minimum Safe Change / Correct interpretation: Workflow displayed as observations; snapshots prevent cross-run count inflation; latest PR chosen by evidence date. Same-time item conflicts and workflow event IDs remain unresolved; workflow_events key retained for compatibility.
- Affected Modules: knowledge_desk/operational.py; warehouse/business_dwh.py
- Regression Surface: SAP workflow, chatbot, Process planning, snapshots
- Test Required / Verification: Existing SAP tests; snapshot replay tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F019 — safe_merge حقایق many-to-one را قبل از کنترل یکتایی حذف می‌کند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: dedupe_on_key پیش از join روی کلید راست drop_duplicates می‌کند؛ SATA/clearance روی BL، credit/FX/IL روی REG. row-count gate فقط سمت چپ را حفظ می‌کند.
- Root Cause: عدم تکثیر ردیف به‌جای حفظ grain تجاری هدف کنترل است.
- Business Impact: چند LC/خرید ارز/کوتاژ/REG مرتبط با BL به یک نماینده محدود می‌شود؛ خطای fan-out با data loss جایگزین می‌شود.
- Minimum Safe Change / Correct interpretation: Retain compatibility representative projection, add explicit RHS multiplicity warning and pandas many_to_one validation. All RHS frames remain in DWH. Not a proof of financial additivity; arbitrary equal-date representative still an open design issue.
- Affected Modules: dataio/merge.py
- Regression Surface: Flat enrichment, logistics, finance, customs
- Test Required / Verification: Existing merge/regression tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F020 — کلید مرکب خالی به کلید قابل join تبدیل می‌شود

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: P07: A="", B="" به "|" تبدیل و دو طرف match شدند. شرط blank در dedupe فقط کل رشته را بررسی می‌کند.
- Root Cause: اعتبار اجزای مرکب قبل از concatenation کنترل نمی‌شود.
- Business Impact: اتصال رکوردهای بدون کلید یا partial key به داده نامربوط.
- Minimum Safe Change / Correct interpretation: JSON tuple encoding prevents delimiter collisions; null/blank components never match; null scalar RHS keys excluded.
- Affected Modules: dataio/merge.py
- Regression Surface: ORDER_MATERIAL, BL_ORDER, custom config
- Test Required / Verification: test_null_and_delimiter_keys
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F021 — برخی تاریخ‌های domain هرگز از adapter صحیح تغذیه نمی‌شوند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: DERIVED: DISCHARGE_DATE از CL_DISCHARGE_DATE و SATA_DATE از SATA_DATE؛ adapterهای فعلی BL_DISCHARGE_DATE و SATA_TRACKING_DATE تولید می‌کنند.
- Root Cause: نام‌های canonical با adapter contract همگام نیستند.
- Business Impact: تخلیه موجود نادیده گرفته می‌شود؛ open shipped به transit می‌رود و eventlog تاریخ‌های واقعی را از دست می‌دهد.
- Minimum Safe Change / Correct interpretation: Fix proven BL_DISCHARGE_DATE and SATA_TRACKING_DATE paths. Other unreachable dates/amounts remain unknown pending true producers, not guessed aliases.
- Affected Modules: stages/s20_derive.py
- Regression Surface: Inventory location, lead times, legacy eventlog, process comparisons
- Test Required / Verification: Existing derive/validation tests; producer-consumer inventory
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F022 — معانی تاریخ دریافت سند و رسید مالی مخلوط شده‌اند

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: FIN_RECEIPT_DATE از SATA_DOC_RECEIVED است که adapter آن را «دریافت اسناد» می‌خواند؛ s80 آن را Financial Receipt Booked و terminal activity می‌داند.
- Root Cause: تاریخ دو رویداد متفاوت semantic equivalent فرض شده است.
- Business Impact: پرونده ممکن است صرفاً با دریافت اسناد بسته تلقی شود.
- Minimum Safe Change / Correct interpretation: Document receipt no longer supplies financial receipt date. Absent dedicated financial-receipt evidence stays empty.
- Affected Modules: stages/s20_derive.py
- Regression Surface: Eventlog terminal, conformance, KPI completion
- Test Required / Verification: Existing event-log and validation tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F023 — مسیر legacy رفع تعهد همه نسخه‌های فایل را جمع می‌کند

- Verdict: **ACCEPT**
- Closure: **OPEN_RELEASE_BLOCKER**
- Evidence: کوئری wh_measure فاقد file/run/published filter است. P08: دو فایل با balance=50 به total=100 رسیدند. chain نیز آخرین پیمایش را روی مبلغ همان ارز overwrite می‌کند بدون ORDER BY.
- Root Cause: raw archive همه نسخه‌هاست ولی reader آن را current ledger فرض می‌کند.
- Business Impact: Double counting تاریخچه و انتخاب غیرقطعی مانده؛ از Cash Flow جدید مستقل است.
- Minimum Safe Change / Correct interpretation: Legacy fx_obligation totals still read archived versions without published native commitment membership. Do not certify/use those totals as current finance. Requires version/file-selection reconciliation, not a guessed latest mtime.
- Affected Modules: warehouse/fx_obligation.py:totals_by_currency
- Regression Surface: Warehouse obligation UI/CLI consumers, historical file ingestion
- Test Required / Verification: Baseline P08; code query reviewed; no new fix claimed
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F024 — قطع مسیر KB حذف منطقی و عدم بازیابی می‌سازد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: P09: یک سند فعال؛ root unavailable → deleted=1؛ بازگرداندن فایل با همان mtime/size → unchanged=1 و active=0.
- Root Cause: seen برای root ناموفق خالی است؛ sweep همه اسناد را DELETED می‌کند؛ unchanged branch status را ACTIVE نمی‌کند.
- Business Impact: مستندات معتبر از پاسخ‌ها ناپدید می‌شوند و بازگشت شبکه کافی نیست.
- Minimum Safe Change / Correct interpretation: Sweep only available roots; reactivation on unchanged restore. Partial permission failure within an existing tree is not fully modeled as an incomplete scan.
- Affected Modules: knowledge_desk/indexer.py
- Regression Surface: KB indexing, network outages, static export, questions
- Test Required / Verification: test_kb_outage_then_restoration
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F025 — grains ناقص و nullable-key loophole در Quality Gate

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: برای frame فاقد قرارداد INFO/True؛ nullable SAP PR item ردیف‌ها را از complete_mask بیرون می‌برد و uniqueness فقط روی completeهاست. P10: duplicate PR+blank item از GRAIN_UNIQUENESS عبور کرد.
- Root Cause: nullable بودن جزء کلید با عدم نیاز به uniqueness یکی شده است.
- Business Impact: قبولی gate اثبات native grain بسیاری از منابع و fallback item نیست.
- Minimum Safe Change / Correct interpretation: Nullable keys retain usable-leading-key and uniqueness checks. Entire source/frame contract catalog and null normalization parity still need extension.
- Affected Modules: warehouse/reliability.py
- Regression Surface: SAP PR fallback, HR, FX, credit, logistics, process inputs
- Test Required / Verification: test_nullable_uniqueness; existing reliability suite
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F026 — ردیف‌های FX دارای ORDER ولی فاقد REG در Cash Flow حذف می‌شوند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: FX adapter رکورد دارای ORDER را معتبر نگه می‌دارد؛ bundle در loop FX فقط _source_reg می‌گیرد و از order_to_reg استفاده نمی‌کند؛ _event با case_id خالی return می‌کند.
- Root Cause: mapping ساخته‌شده برای commercial/scope در رویداد مالی استفاده نمی‌شود.
- Business Impact: خرید ارز سالم دارای ارتباط قابل حل در native data هست ولی وارد event ledger نمی‌شود.
- Minimum Safe Change / Correct interpretation: ORDER/BL candidate resolution for finance; unresolved rows recorded in diagnostics while native source rows survive. No guessed account/case. Orphans are not yet a dedicated financial quarantine fact.
- Affected Modules: cashflow/dwh.py
- Regression Surface: Cash Flow purchase/payment, scope reconciliation, orphan totals
- Test Required / Verification: Existing Cashflow DWH tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F027 — شناسه commitment در Cash Flow تعداد سطر است، نه شناسه تعهد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence: native_ref از NTSW_COMMIT_ROWS ساخته می‌شود؛ دو REG با COMMIT_ROWS=1 هر دو source_event_id="1:COMMITMENT" دارند. engine replay detector source+source_event_id را cross-case چک می‌کند. P11 هر دو event را با CONFLICTING_SOURCE_EVENT_ID قرنطینه کرد.
- Root Cause: count به‌جای stable source identity استفاده شده است.
- Business Impact: تعهد پرونده‌های مستقل به‌صورت CONFLICTING_SOURCE_EVENT_ID قرنطینه می‌شود.
- Minimum Safe Change / Correct interpretation: REG-scoped commitment-summary ID replaces count-as-ID. Explicitly a summary representation, not a newly discovered native transaction ID.
- Affected Modules: cashflow/dwh.py
- Regression Surface: Cash Flow accepted ledger, commitment summary, multi-REG runs
- Test Required / Verification: Existing multi-REG cashflow tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F028 — read all_data_sheets در عمل فقط بزرگ‌ترین شیت را می‌خواند

- Verdict: **ACCEPT**
- Closure: **OPEN_RELEASE_BLOCKER**
- Evidence: شاخه all_data_sheets برای هر فایل فقط best با بیشترین len را به frames اضافه می‌کند؛ raw capture همه شیت‌ها را حفظ می‌کند.
- Root Cause: نام strategy با implementation متفاوت است.
- Business Impact: داده شیت عملیاتی دوم به standardized/process/DWH نمی‌رسد.
- Minimum Safe Change / Correct interpretation: all_data_sheets still selects largest sheet. Raw workbook bytes/sheets survive, but operational second-sheet coverage does not. Need approved sheet signatures/allowlist before changing mixed helper/data workbook ingestion.
- Affected Modules: dataio/reader.py:_read_targets
- Regression Surface: Clearance multi-file, mixed transport, sheet coverage
- Test Required / Verification: Code verified; no all-sheets fix claimed
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F029 — جداسازی صریح Export Clearance از Import پیدا نشد

- Verdict: **DEFER_NEEDS_DATA**
- Closure: **OPEN**
- Evidence: pattern *Clearance* و all_data_sheets؛ mapping فاقد direction/import-export و در population/process filter صریح export مشاهده نشد.
- Root Cause: transport با flow direction متفاوت است و قرارداد جهت وجود ندارد.
- Business Impact: در صورت وجود ExportClearance با کلید مشترک امکان آلودگی KPI واردات؛ وجود چنین فایل در محیط فعلی UNKNOWN / NEEDS EVIDENCE.
- Minimum Safe Change / Correct interpretation: Need real ExportClearance/import workbooks and direction keys. No evidence that supplied QA data demonstrates export/import contamination.
- Affected Modules: adapters/a30_customs.py; source patterns
- Regression Surface: Customs, clearance, process, import financial stages
- Test Required / Verification: Opus insufficient-evidence assessment accepted
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F030 — فازی بودن header mapping می‌تواند معنای کلید را تغییر دهد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: بعد از exact match، substring در هر دو جهت با shortest-score برنده می‌شود؛ std ستون ناموجود را blank می‌سازد. collision normalized header اولین را برمی‌گزیند.
- Root Cause: mapping ambiguity و missing-column error به شکل uniform contract گزارش نمی‌شود.
- Business Impact: اشتباه semantic بدون exception؛ نبود fuzzy business join به معنی exact header mapping نیست.
- Minimum Safe Change / Correct interpretation: Normalized-header collision and equal-scoring fuzzy tie raise explicit errors. Non-tied fuzzy fallback remains for backward compatibility; exact key/amount allowlists still open.
- Affected Modules: core/columns.py
- Regression Surface: All std adapters, SAP prefixed headers, changing Excel layout
- Test Required / Verification: Existing mapping and adapter tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F031 — صفر و Unknown در legacy financial fields یکسان می‌شوند

- Verdict: **ACCEPT**
- Closure: **OPEN_RELEASE_BLOCKER**
- Evidence: BALANCE/CB_VALUE/FX_PURCHASE_AMOUNT default=0 numeric؛ s55 و s56 نیز fillna(0) دارند؛ cashflow engine جدید None/Decimal را جدا می‌کند.
- Root Cause: سیاست missing در دامنه‌ها یکنواخت نیست.
- Business Impact: نبود منبع ممکن است صفر مانده/خرید یا risk score کم نمایش داده شود.
- Minimum Safe Change / Correct interpretation: Legacy BALANCE/CB_VALUE/default-zero and downstream fillna(0) remain. New Cashflow unknown semantics are stronger. No claim of global unknown/zero parity.
- Affected Modules: stages/s20_derive.py; stages/s55_fx_traceability.py; stages/s56_money_flow_control.py
- Regression Surface: Legacy dashboards, risk, commitment, FX vs cashflow consistency
- Test Required / Verification: Existing tests only; known unresolved financial invariant
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F032 — دو سیستم Authority با تصمیم متفاوت در تعارض وجود دارد

- Verdict: **DEFER_NEEDS_DATA**
- Closure: **OPEN**
- Evidence: SOURCE_PRIORITY hardcoded و hub=390 پایین‌تر از direct NTSW=400 است؛ registration_bridge direct/hub را هم‌اولویت در candidate conflict می‌گیرد؛ authority.py tiers از YAML در import cache می‌شود.
- Root Cause: policy موزع و قواعد tie-break مستقل.
- Business Impact: یک ORDER در flat unresolved ولی در Cash Flow resolved؛ تغییر config در یک consumer اثر نمی‌کند.
- Minimum Safe Change / Correct interpretation: Need authoritative per-field source policy/effective date and approval of tie semantics before unifying canonical versus cashflow ranking.
- Affected Modules: config/authority.py; cashflow/dwh.py
- Regression Surface: Canonical resolver, population, cashflow, config reload
- Test Required / Verification: Conflict-resolution implementations reviewed; no policy invented
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F033 — fallback استاندارد در snapshot تازه دوباره ذخیره نمی‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: در مسیر fallback self.sources=published_frames است ولی wh.frame standardized اجرا نمی‌شود؛ build DWH آن را با run جدید upsert می‌کند.
- Root Cause: freshness lineage بین source snapshot و publication run جدا مدل نشده است.
- Business Impact: پس از انتشار degraded run، fallback دفعه بعد ممکن است frame آن source را پیدا نکند؛ Cash Flow می‌تواند stale balance را observed_at روز گزارش بنامد.
- Minimum Safe Change / Correct interpretation: Repeated fallback frame is persisted with source_origin_run attrs; frame attrs survive cache and SQL reconstruction. Freshness SLA/measurement date propagation is not fully resolved.
- Affected Modules: pipeline.py; warehouse/store.py
- Regression Surface: Repeated optional-source failures, cashflow measurements, provenance
- Test Required / Verification: Existing fallback/frame roundtrip tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F034 — خطای operational retrieval به نبود شاهد تبدیل می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: except Exception:return []؛ query.answer ممکن است فقط doc hits را ANSWERED کند. ID regex فقط اعداد 6..16 رقمی می‌گیرد؛ alphanumeric ORDER/BL/material پشتیبانی معنایی کامل ندارد.
- Root Cause: absence evidence، unsupported ID و backend failure نتیجه یکسان دارند.
- Business Impact: پاسخ ناقص یا مستند عمومی به سؤال عملیاتی؛ علت واقعی پنهان می‌ماند.
- Minimum Safe Change / Correct interpretation: Backend errors produce SOURCE_UNAVAILABLE; explicit alphanumeric IDs supported. Static export fails on corrupt operational DB rather than silently dropping evidence. All client-specific error displays still need visual verification.
- Affected Modules: knowledge_desk/operational.py; knowledge_desk/query.py
- Regression Surface: Chatbot answer status, SQL locks/migrations, alphanumeric IDs
- Test Required / Verification: test_backend_error_not_absence
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F035 — دریافت متن KB تضمین پاسخ مرتبط/معتبر نیست

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence: search از OR tokens/BM25 یا LIKE استفاده می‌کند؛ هر hit می‌تواند ANSWERED شود؛ effective-date/authority/citation entailment gate ندارد. AnythingLLM مسیر جدا با mode=chat است و بدون lesson دستور grounding اضافی ندارد.
- Root Cause: retrieval relevance با answer sufficiency یکی گرفته شده است.
- Business Impact: Extractive chatbot هم می‌تواند متن نامرتبط/قدیمی را پاسخ قطعی جلوه دهد؛ external LLM کنترل‌شده در این پکیج اثبات نشده.
- Minimum Safe Change / Correct interpretation: Operational questions do not receive KB fallback as factual evidence; explicit policy intent routes to KB. KB relevance/effective-date/contradiction governance and external LLM grounding remain open.
- Affected Modules: knowledge_desk/query.py
- Regression Surface: Offline server, static chatbot, AnythingLLM, KB governance
- Test Required / Verification: Existing knowledge tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F036 — historical warehouse مستقل به pipeline اصلی متصل نیست

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **DOCUMENTED**
- Evidence: Pipeline.run فقط warehouse.bridge.run_pipeline را صدا می‌زند؛ historical_runtime wrapper در core pipeline فراخوانی نمی‌شود. historical_store مدل dw_run/fact_event دارد و store مدل wh_run مستقل.
- Root Cause: دو نسل persistence بدون مسیر migration/promotion مشترک.
- Business Impact: داشتن ماژول historical به معنی ثبت خودکار تاریخچه تمام runtime فعلی نیست.
- Minimum Safe Change / Correct interpretation: Historical warehouse is a separate legacy subsystem; no claim that current pipeline populates it. Migration not necessary for this scoped patch and not implemented.
- Affected Modules: warehouse/historical_runtime.py; warehouse/bridge.py
- Regression Surface: Historical UI, CLI, profile persistence, old snapshots
- Test Required / Verification: Call-site review
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F037 — شواهد endpoint KB شامل کنترل دسترسی application نیست

- Verdict: **DEFER_NEEDS_DATA**
- Closure: **OPEN_RELEASE_BLOCKER**
- Evidence: HTTP API فاقد احراز هویت و access scope، CORS=*؛ config پیش‌فرض host=0.0.0.0. static payload نیز PRهای DWH را بدون user scope صادر می‌کند.
- Root Cause: اعتماد به شبکه/فایل‌سرور بیرون از کد.
- Business Impact: در صورت دسترسی شبکه/پوشه، پرسش از اطلاعات عملیاتی خارج از دامنه مخاطب ممکن است.
- Minimum Safe Change / Correct interpretation: Endpoint defaults/CORS/application ACL boundary remain unchanged. Need deployment audience, identity provider and actual file/network ACL evidence before certifying access control.
- Affected Modules: knowledge_desk/service.py; knowledge_desk/config.py
- Regression Surface: Knowledge server, static snapshots, personal scope
- Test Required / Verification: Static exposure confirmed, deployed exploitability not claimed
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F038 — DocCheck history پیش از process inventory فشرده می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence: transform خروجی std را با dedupe_on_key(ORDER, SUBMIT_DATE) به یک main کاهش می‌دهد؛ frame native docs نگه نمی‌دارد. raw workbook در wh_file موجود است.
- Root Cause: adapter projection و native evidence یک frame شده‌اند.
- Business Impact: اسناد و وضعیت‌های قبلی در process ledger قابل مشاهده نیستند؛ row-preservation پس از حذف می‌سنجد.
- Minimum Safe Change / Correct interpretation: doc_rows preserves every standardized document row; main remains latest-order compatibility projection. Raw workbook lineage still lives in archive.
- Affected Modules: adapters/a60_finance.py
- Regression Surface: Bank docs, process evidence count, DWH source facts
- Test Required / Verification: Existing finance/process tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F039 — SWIFT در Process Matrix به PAYMENT تعبیر می‌شود

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence: credit با CRD_SWIFT_DATE بدون receipt evidence، PAYMENT با شرح «پرداخت / وصول ذی‌نفع» emit می‌کند؛ در s55 این دو عمداً جدا هستند.
- Root Cause: تعریف stage میان دو subsystem یکسان نیست.
- Business Impact: وجود سوئیفت می‌تواند شاهد وصول تلقی شود؛ مقایسه دو dashboard متناقض است.
- Minimum Safe Change / Correct interpretation: SWIFT_SENT stays a separate observation, never PAYMENT. FX payment date no longer falls back to SWIFT/buy date. Zero remaining balance never emits settlement.
- Affected Modules: resolve/process_evidence.py; cashflow/dwh.py
- Regression Surface: Process matrix, FX trace, cashflow, current stage
- Test Required / Verification: test_swift_not_payment; test_balance_not_settlement
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## F040 — serialized latest snapshot و migration/locking کامل نیست

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence: run_pipeline پس از خروج از with wh.run (آزادشدن writer lock) publish را می‌زند؛ publish ordering gate ندارد. _ensure_schema با wh_meta+user_version=1 از DDL بازمی‌گردد حتی اگر جدول‌های جدید نسخه‌های دیگر نباشند.
- Root Cause: writer lifecycle و schema revision کم‌دانه است.
- Business Impact: با interleaving ممکن است pointer عقب برود؛ DB قدیمی با version=1 لزوماً همه tables ندارد. وقوع در تولید UNKNOWN / NEEDS EVIDENCE.
- Minimum Safe Change / Correct interpretation: Schema fast path verifies required tables; publication uses BEGIN IMMEDIATE and monotonic started ordering. Global writer lifecycle unchanged; old run cannot roll pointer backward.
- Affected Modules: warehouse/store.py
- Regression Surface: Concurrent update, legacy DB upgrades, current slots
- Test Required / Verification: test_legacy_schema_upgrade; existing publish tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.


## N01 — HIGH — SCHEMA_DRIFT تغییر هدر منبع را نمی‌بیند؛ فیلد کسب‌وکاری بی‌صدا خالی می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `warehouse/reliability.py:schema_drift_checks` + `adapters/base.py:std` · probe OP-07
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: std retains source_headers/missing_mappings; schema gate emits mapping coverage warning. Full raw header baseline/required-alias classification still open.
- Affected Modules: adapters/base.py; warehouse/reliability.py
- Regression Surface: adapters/base.py; warehouse/reliability.py
- Test Required / Verification: Code and existing schema tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


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


</details>


## N02 — HIGH — نمای `dwh_registration_hub` cross-product تولید می‌کند و در UI انبار نمایش داده می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence:  `business_dwh.py` (تعریف VIEW) · `app/warehouse_view.py:78` · probe OP-02
- Root Cause: Independent joins multiply unrelated memberships.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Singleton hub pairs retained as derived traversal; ambiguous hubs return separate REG and ORDER memberships with null opposite keys, no product.
- Affected Modules: warehouse/business_dwh.py
- Regression Surface: warehouse/business_dwh.py
- Test Required / Verification: test_no_hub_product
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


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


</details>


## N03 — HIGH — طبقه‌بند وضعیت فارسی در لایه process، وضعیت‌های رایج را وارونه می‌کند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `resolve/process_evidence.py:_state_from_text` · probe OP-04
- Root Cause: Substring matching ignores word boundaries and negation.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Negation and word boundaries fix demonstrated Persian status inversions. Source-specific state-code dictionaries still required.
- Affected Modules: resolve/process_evidence.py
- Regression Surface: resolve/process_evidence.py
- Test Required / Verification: test_polarity
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


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


</details>


## N04 — HIGH — گارد انفجار سطر مرده است؛ یک چک BLOCK هرگز نمی‌تواند فعال شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `dataio/merge.py:safe_merge` · `warehouse/reliability.py:source_runtime_checks` · probe OP-01
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Duplicate RHS explicitly warns; pandas validates many_to_one. Legacy representative collapse remains declared, not an active fan-out gate on native facts.
- Affected Modules: dataio/merge.py
- Regression Surface: dataio/merge.py
- Test Required / Verification: See F019; no claim the old impossible branch is now a native cardinality gate
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


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


</details>


## N05 — HIGH — ستون‌های مشتقِ بی‌تولیدکننده، یک ثابت جعلی و یک شاخه مرده در گزارش رسمی می‌سازند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `stages/s20_derive.py` · `adapters/a40_oracle.py:EXCLUDED_HEADERS` · `dataio/reader.py` (`forbidden`) · `resolve/expert_roles.py:59` · probe OP-06
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Remove fabricated تولیدی segment default; restore proven discharge producer. Excluded Oracle buyer/status and other unmapped producers remain open.
- Affected Modules: stages/s20_derive.py
- Regression Surface: stages/s20_derive.py
- Test Required / Verification: Existing derive/validation tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Ambiguous Mapping · Orphan Evidence
**شاهد:** `stages/s20_derive.py` · `adapters/a40_oracle.py:EXCLUDED_HEADERS` · `dataio/reader.py` (`forbidden`) · `resolve/expert_roles.py:59` · probe OP-06
(ریشه مشترک با F021؛ اما سه پیامد زیر در هیچ یافته‌ای ثبت نشده‌اند.)

1. **ثابت جعلی:** `"SEGMENT": (["BL_SEGMENT"], "تولیدی", False)`. چون `BL_SEGMENT` هیچ تولیدکننده‌ای ندارد و `DeriveStage.run` بدون شرط default را می‌نشاند، **هر ردیف گزارش** مقدار «تولیدی» می‌گیرد. این یک مقدار پیش‌فرض نیست؛ یک ادعای کسب‌وکاری است که به‌صورت داده ارائه می‌شود.
2. **شاخه مرده در تفکیک موجودی:** `DISCHARGE_DATE` همیشه خالی است ⇒ در `_inventory_pipeline` متغیر `discharged` همیشه `False` ⇒ `assign_customs` هرگز فعال نمی‌شود و `IS_IN_CUSTOMS` فقط از عدد کارشناسی می‌آید، درحالی‌که `IS_IN_TRANSIT` برای هر ردیف ترخیص‌نشده `True` می‌شود. یعنی تفکیک «در راه / در گمرک» مبتنی بر رویداد، **ساختاراً غیرفعال** است.
3. **زنجیره authority به ستون حذف‌شده اشاره می‌کند:** `expert_roles.py:59` نقش خریدار را با `[("ORC_BUYER","oracle"), ("CRD_BUYER","credit")]` حل می‌کند — یعنی اولین مرجع، ستونی است که reader **عمداً حذف می‌کند**. همچنین `pipeline.preflight` و `doctor.py` مقدار `"ORC_STATUS"` را در `base_cols` می‌گذارند، پس اعتبارسنج گراف مرحله‌ها فرض می‌کند این ستون موجود است و شکاف را پنهان می‌کند.
4. **سیگنالی که دور ریخته می‌شود:** `DeriveStage.run` فهرست کاندیداهای یافت‌نشده را در `ctx.extras["derive_missing"]` می‌گذارد؛ `grep` نشان می‌دهد **هیچ مصرف‌کننده‌ای** ندارد و به هیچ `Check` تبدیل نمی‌شود.


</details>


## N06 — HIGH — PR Item با چند PO Item: فقط یک PO در fact قلم PR باقی می‌ماند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **IMPLEMENTED**
- Evidence:  `adapters/a60_finance.py:SapAdapter.transform` · probe OP-03
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: PR item carries SAP_PO_COUNT; PO-specific representative columns become missing on multi-PO items; po_items/raw_rows retain all PO facts.
- Affected Modules: adapters/a60_finance.py
- Regression Surface: adapters/a60_finance.py
- Test Required / Verification: Existing SAP split-PO tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** SAP PR/PO Grain · Silent Data Loss
**شاهد:** `adapters/a60_finance.py:SapAdapter.transform` · probe OP-03

سناریوی خراب‌کننده: `PR 1000000001 / item 10` بین دو سند خرید تقسیم شده (PO…01 qty 60 و PO…02 qty 40).

```
pr_item_10_row_count : 1
pr_item_10_kept_po   : ["20"]     ← فقط قلم PO دوم
```

`pr_items = pr.groupby([KEY_PR,"SAP_PR_ITEM"]).tail(1)` است؛ چون `__SORT` هر دو ردیف برابر است (هر دو `Changed On` یکسان PR دارند)، برنده صرفاً «آخرین ردیف فایل» است. هر ستون `SAP_PO_*`، `SAP_QTY_ORDERED` و `SAP_HEADER_PURCHASE_ORDER` روی fact قلم PR، نماینده **یکی از N** سند خرید است، بدون هیچ پرچم multiplicity (برخلاف `MULTI_PR`/`MULTI_MATERIAL` که Commercial Expert دارد).

این با F017 یکی نیست: F017 درباره انتساب غلط در `po_items` است؛ این درباره از دست رفتن کثرت در `pr_items` است.


</details>


## N07 — HIGH — گیت PROCESS_ROW_PRESERVATION خودغیرفعال‌شونده است

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence:  `stages/s54_process_integrity.py` (`tolerant = True`) · `warehouse/bridge.py:28` (`if ps:`) · probe OP-05
- Root Cause: Conditional gate registration depends on successful producer.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Missing process summary is blocking instead of disabling the row-preservation gate; independent processing completes diagnostics first.
- Affected Modules: warehouse/bridge.py
- Regression Surface: warehouse/bridge.py
- Test Required / Verification: test_missing_process_summary_blocks_before_files
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Failure Isolation · Snapshot Publication
**شاهد:** `stages/s54_process_integrity.py` (`tolerant = True`) · `warehouse/bridge.py:28` (`if ps:`) · probe OP-05

```
gate_when_stage_ran    : [("PROCESS_ROW_PRESERVATION", False)]   ← BLOCK فعال
gate_when_stage_raised : []                                      ← هیچ چکی
```

`s54` با `tolerant=True` تعریف شده، پس هر exception داخل `build_process_inventory` باعث می‌شود `run_stages` مرحله را قرنطینه کند و `ctx.extras["process_evidence_summary"]` هرگز ست نشود. `bridge.py` هم با `if ps:` وقتی خلاصه نباشد چک را **اضافه نمی‌کند**.

یعنی همان خرابی‌ای که گیت باید جلویش را بگیرد (فروپاشی مدل شواهد فرایند)، خودِ گیت را حذف می‌کند و run با `quality_gate_passed=True` منتشر می‌شود. این وارونگی fail-closed است و در `FINDINGS_REGISTER` نیامده.


</details>


## N08 — MEDIUM — شناسه پرونده فرایندی پایدار نیست

- Verdict: **ACCEPT**
- Closure: **OPEN_RELEASE_BLOCKER**
- Evidence:  `resolve/process_evidence.py:_components` · probe OP-04
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: PC ID still hashes component membership. Material/Employee no longer merge components, but stable case aliases/identity migration are not implemented.
- Affected Modules: resolve/process_evidence.py:_components
- Regression Surface: resolve/process_evidence.py:_components
- Test Required / Verification: Static code verified; do not use PC ID as persistent external identity
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** History Preservation · Process Continuity
**شاهد:** `resolve/process_evidence.py:_components` · probe OP-04

`case_id = "PC-" + sha1("|".join(sorted(nodes)))[:14]` — یعنی شناسه، تابع **کل اعضای component** است.

```
اجرای الف (ORD-A, ORD-B روی M1)          : PC-148AAC992DA6B2
اجرای ب  (ORD-A, ORD-B, ORD-C روی M1)    : PC-F5548CE40949AD
case_id_stable_when_member_added         : false
```

هر ورود یک شاهد جدید (که با N04/F004 بسیار محتمل است) شناسه پرونده را کاملاً عوض می‌کند. هر مصرف‌کننده‌ای که `PROCESS_CASE_ID` را ذخیره یا لینک کند — action queue، پیوست در ردیف flat، مقایسه بین دو روز — بی‌صدا ارجاعش را از دست می‌دهد. `DECISION_LOG` این را به‌عنوان نیازمندی O003 ذکر کرده ولی به‌عنوان نقص فعلی ثبت نکرده است.


</details>


## N09 — MEDIUM — `evidence_count` تعداد (ردیف × اجرا) است، نه تعداد شواهد

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `business_dwh._upsert_relation` · probe OP-02
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Per-run rebuild stops accumulation across ingests. Duplicate derived representations across frames may still count separately; evidence_count is not a physical-event count.
- Affected Modules: warehouse/business_dwh.py
- Regression Surface: warehouse/business_dwh.py
- Test Required / Verification: test_replay_relation_counts
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Double Count · Event vs Snapshot
**شاهد:** `business_dwh._upsert_relation` · probe OP-02

`ON CONFLICT … evidence_count = dwh_relation.evidence_count + 1` هیچ محدوده run ندارد. ingest مجدد فایل **دست‌نخورده** شمارنده را دوبرابر کرد (`1 → 2`). این عدد در `_relations()` به چت‌بات و در `app/warehouse_view.py:76` به UI داده می‌شود و طبیعتاً «چند شاهد مستقل داریم» خوانده می‌شود.


</details>


## N10 — MEDIUM — اجرای مسدودشده، `wh_schema_baseline` را دائمی تغییر می‌دهد

- Verdict: **ACCEPT**
- Closure: **IMPLEMENTED**
- Evidence:  `warehouse/reliability.py:schema_drift_checks` · `warehouse/bridge.py`
- Root Cause: Mutable schema baseline is written before publication.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Run-scoped schema candidates promote only with successful pointer transaction.
- Affected Modules: warehouse/reliability.py; warehouse/store.py
- Regression Surface: warehouse/reliability.py; warehouse/store.py
- Test Required / Verification: test_blocked_schema_does_not_become_baseline
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Snapshot Publication · Failure Isolation
**شاهد:** `warehouse/reliability.py:schema_drift_checks` · `warehouse/bridge.py`

`schema_drift_checks` **درون** `with wh.run(...)` و **پیش از** گیت اجرا می‌شود و برای هر frame تازه یک ردیف در `wh_schema_baseline` (با `PRIMARY KEY(contract)`، بدون ستون run) `INSERT` می‌کند. `wh.publish` که بعداً `QualityGateBlockedError` می‌دهد این نوشتن را برنمی‌گرداند (تراکنش جداست).

پیامد: نخستین اجرا — حتی اگر رد شود — baseline اسکیما را برای همیشه تثبیت می‌کند. اگر آن اجرا با فایل خراب بوده باشد، اجراهای درست بعدی به‌عنوان drift علامت می‌خورند. این نمونه‌ای از همان خانواده F001/F002/F012 است، اما روی جدولی که Astra اصلاً نام نبرده.


</details>


## N11 — MEDIUM — `_SOURCE_FILE` نام فایل اصلی را حمل نمی‌کند؛ دو fallback مستند مرده‌اند

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `dataio/reader.py:read_source` و `_read_targets` · `adapters/a30_customs.py:122` · `adapters/a10_abbasi.py:62`
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Archived parsing uses original filename inside content-hash directory; configured sheet lineage carried. First-sheet alias remains __first__, not claimed as actual sheet name.
- Affected Modules: dataio/reader.py
- Regression Surface: dataio/reader.py
- Test Required / Verification: Existing reader/transport tests
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Orphan Evidence · Ambiguous Mapping
**شاهد:** `dataio/reader.py:read_source` و `_read_targets` · `adapters/a30_customs.py:122` · `adapters/a10_abbasi.py:62`

`read_source` بایت‌های آرشیوشده را در فایل موقتی با نام `fid + ext` می‌نویسد، و `fid = hashlib.sha256(content).hexdigest()` است. سپس `_read_targets` می‌نویسد `df["_SOURCE_FILE"] = os.path.basename(f)` — یعنی مقدار این ستون یک هش ۶۴ کاراکتری است، نه `SeaClearance.xlsx`.

در نتیجه:
- در `ClearanceAdapter`، شاخه‌ای که مستند شده «نوع فایل خودش حامل حقیقت است» هرگز کار نمی‌کند (`rb.transport_mode("<sha256>.xlsx")`). شاخه `_SOURCE_SHEET` هنوز کار می‌کند، چون clearance از `all_data_sheets` استفاده می‌کند.
- در `AbbasiAdapter` **هر دو** fallback مرده‌اند: `_SOURCE_FILE` هش است، و `_SOURCE_SHEET` در شاخه معمولی `_read_targets` (خط ۱۹۸) اصلاً ست نمی‌شود — فقط در شاخه `all_data_sheets`.

این یک پسرفت جانبی از تغییر درستِ «خواندن از بایت آرشیوشده» است.


</details>


## N12 — MEDIUM — تعیین «آخرین وضعیت» درخواست تخصیص قطعی نیست

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **PARTIAL**
- Evidence:  `adapters/a50_ntsw.py:_allocation_request_ledger` و `_agg_allocation`
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Stable sort for identical input order. Equal-date conflicting request statuses still lack authoritative time/version tie policy; reordering may change representative.
- Affected Modules: adapters/a50_ntsw.py
- Regression Surface: adapters/a50_ntsw.py
- Test Required / Verification: Existing request ledger tests; no reorder-invariance claim
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Event vs Snapshot · Late-arriving Data
**شاهد:** `adapters/a50_ntsw.py:_allocation_request_ledger` و `_agg_allocation`

`a.sort_values("_ord")` با `kind` پیش‌فرض (`quicksort`، ناپایدار) اجرا می‌شود و سپس `drop_duplicates(..., keep="last")` برنده را می‌گیرد؛ `_agg_allocation` هم `g.sort_values("_ord")` و `g.iloc[-1]`. وقتی دو snapshot از یک درخواست تاریخ‌های یکسان دارند (حالت رایج در snapshot روزانه)، برنده به ترتیب ورودی و اندازه آرایه بستگی دارد.

شاهد تقویتی از خود پکیج: `dataio/merge.py:dedupe_on_key` برای دقیقاً همین تصمیم `kind="mergesort"` را انتخاب کرده و دلیلش را کامنت کرده («در تساوی تاریخ … نتیجه dedupe بین دو اجرا عوض نمی‌شود»). یعنی استاندارد داخلی پروژه اینجا رعایت نشده.


</details>


## N13 — MEDIUM — REG غیر ۸‌رقمی بی‌صدا از جمعیت اصلی حذف می‌شود

- Verdict: **ACCEPT_WITH_MODIFICATION**
- Closure: **DOCUMENTED**
- Evidence:  `resolve/population.py:_clean_reg`
- Root Cause: See original Opus evidence excerpt below; implementation behavior checked against the named module.
- Business Impact: Risk described in original Opus finding; no production loss/frequency estimate asserted.
- Minimum Safe Change / Correct interpretation: Eight-digit REG exclusion is current keys.yaml business contract, not evidence deletion from archive/DWH. Nonconforming operational registration quarantine/UI coverage remains open; do not broaden legal identifiers by guessing.
- Affected Modules: resolve/population.py; config/keys.yaml
- Regression Surface: resolve/population.py; config/keys.yaml
- Test Required / Verification: Source preservation/current-scope distinction reviewed
- Evidence scope: static trace plus named executed suites where indicated; fixture coverage does not establish production source semantics.

<details><summary>Original independent review evidence</summary>


**دسته:** Orphan Evidence · Source Authority
**شاهد:** `resolve/population.py:_clean_reg`

```python
def _clean_reg(v) -> str:
    s = clean_key(v)
    return s if len(s) == 8 and s.isdigit() else ""
```

هر REG که دقیقاً ۸ رقم عددی نباشد `""` می‌شود و ردیف در `_ntsw_reg_rows` با `if reg:` کنار گذاشته می‌شود — **بدون هیچ issue، audit یا `dwh_unresolved_relation`**. همان REG می‌تواند در `dwh_fact_ntsw_commitment` موجود باشد (که چنین فیلتری ندارد)، پس گزارش تخت و DWH در شمارش پرونده‌ها با هم اختلاف پیدا می‌کنند و علت اختلاف در هیچ خروجی دیده نمی‌شود.

---


</details>


## RC01 — ACCEPT: UI download lifecycle and dependency floor
Evidence: app/warehouse_view.py creates backup download only inside st.button branch; CSV name was always warehouse_table.csv. requirements.txt allowed Streamlit 1.35 while existing UI already uses width.
Root cause: transient button branch and unbounded minimum API version. Business impact: download disappears after rerun; installation can reject API arguments. Minimum change: persist prepared bytes under warehouse-specific state key, render button on later reruns, on_click=ignore, deterministic frame-ID CSV filename, minimum Streamlit 1.49. Regression surface: warehouse page; tests: test_download_rerun_contract and existing AppTest suites. Browser click/media-server continuity has not been visually verified.

## RC02 — ACCEPT: baseline tests depend on stale version/config and global DWH state
Evidence: baseline_full.log shows literal Build 29.7.5 against 29.7.6, known-incomplete SAP scenarios rely on current production config, and empty-KB test sees prior suite operational data. Minimum change: import VERSION, explicitly fixture known-incomplete scenario, isolate each pytest DWH, update audit-file test for run-addressed publication and unpublished build test to administrative db(). Assertions retain scenario intent.


## RC03 — ACCEPT: SQLite integrity incident remains unresolved
- Evidence: release_verification.log blocks publication with sqlite:INTEGRITY_CHECK; read-only recheck reports missing index entries in wh_frame_run and sqlite_autoindex_wh_frame_row_1 (review/validation/sqlite_incident.json).
- Root cause: UNKNOWN. Shared test state is a test-isolation defect, not an established explanation for index corruption.
- Business impact: publication unavailable; database cannot be certified healthy.
- Minimum safe change: retain publication gate unchanged; isolate standalone test suites as required by RC02. Preserve the failed log and integrity report. Do not repair/reindex the affected database or suppress the gate to obtain green tests.
- Affected modules: run_all_tests.py (harness only); wh_frame persistence requires further investigation.
- Regression surface: repeated writes and cross-process reuse of the same database.
- Test: three independent processes ran the architecture suite against one fresh shared database; 42 checks passed per process and integrity_check returned ok after each. This does not explain the earlier incident.
- Closure: OPEN_RELEASE_BLOCKER pending reproducible root-cause analysis and affected-environment validation.

### RC02 continuation
Standalone scripts bypass pytest conftest.py. run_all_tests.py now supplies a fresh temporary DWH per suite, preserving explicit same-database scenarios inside tests. No production gate was relaxed.

## RC04 — ACCEPT: wall-clock-dependent expiry assertion
- Evidence: continuation_full.log has 1047 passing checks and one failing assertion in test_v26_20_2_engine_hardening.py. On 2026-09-23, summary_rows correctly labels the rule expired; the test still expects near-expiry wording for a rule expiring 2026-09-22.
- Root cause: summary_rows uses today's RuleBook while the surrounding scenario uses explicit before/after dates.
- Business impact: false regression report after expiry; no evidenced production defect.
- Minimum safe change: patch get_rulebook only inside the test to its existing before/after fixtures; require both near-expiry and expired labels. Do not alter production rule dates.
- Affected module: tests/test_v26_20_2_engine_hardening.py.
- Regression surface: health-summary date semantics.
- Required test: unchanged standalone suite with stronger two-date assertion.
- Closure: IMPLEMENTED; exact execution result in TEST_AND_INVARIANTS.md.
