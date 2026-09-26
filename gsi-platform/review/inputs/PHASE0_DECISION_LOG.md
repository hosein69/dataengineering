# DECISION_LOG — Phase 0

این سند تصمیم‌های **شناخت و ثبت baseline** و تصمیم‌های باز برای مرحله بعد را جدا می‌کند. پیشنهاد در این فایل مجوز پیاده‌سازی نیست. هیچ بازنویسی، patch تولیدی، migration، تغییر config، تغییر publication یا ارسال ایمیل انجام نشده است.

## تصمیم‌های این ممیزی

| ID | Decision | Status | Evidence / Rationale | Consequence |
|---|---|---|---|---|
| D001 | ZIP پیوست تنها baseline اجرایی است؛ release notes نسخه‌های قبلی normative نیستند | ACCEPTED FOR AUDIT | hash در ARCHITECTURE_BASELINE؛ 521 عضو فایل | شماره خطوط نسبت به همین ZIP |
| D002 | code behavior بر comment/docstring مقدم است | ACCEPTED FOR AUDIT | Oracle max vs single-row claim؛ all_data_sheets largest-sheet | تعارض مستندات جدا ثبت شده |
| D003 | raw cell / standardized frame / resolved value / derived relation یکسان نیستند | ACCEPTED FOR AUDIT | adapters aggregate/dedupe؛ Business DWH همه frames را می‌گیرد | ادعای native در نام یک table کافی نیست |
| D004 | Source-observed فقط co-observation در native row با semantic keys درست است | ACCEPTED FOR AUDIT | F006/F017 | exact join نیز می‌تواند derived باشد |
| D005 | severity بر پیامد بالقوه و confidence بر سطح evidence تعیین شود | ACCEPTED FOR AUDIT | synthetic probes و static traces جدا | هیچ برآورد مالی واقعی جعل نشود |
| D006 | probes و generated test outputs بیرون فایل‌های اصلی نگه داشته شوند | EXECUTED | evidence harness؛ مقایسه bytes original archive | صفر تغییر original member |
| D007 | production files/DB/network در دسترس فرض نشوند | ACCEPTED FOR AUDIT | 4 bundled XLSX خروجی QA/نمونه‌اند | data semantics ناشناخته صریح بماند |
| D008 | prior test logs فقط historical evidence؛ موفقیت فعلی باید rerun باشد | EXECUTED | run_all_tests log مستقل؛ pytest unavailable | 41 blocked suite معادل 41 code defect نیست |

## تصمیم‌های معماری موجود — استخراج‌شده، نه تأیید جدید

| ID | Existing choice | Evidence | Assessment |
|---|---|---|---|
| E001 | Excel-first ingestion, newest file by mtime | reader.find_files/read_source | reproducibility به blob archive متکی است؛ newest لزوماً business latest نیست |
| E002 | primary population=Expert ∪ NTSW؛ Abbasi enrichment | resolve/population.py | intentional scope؛ orphan خارج population باید در evidence قابل کشف باشد |
| E003 | tier1 Expert/NTSW؛ tier2 Abbasi/SATA | config/authority.py, sources.yaml | field semantics باید مقدم بر ranking باشد |
| E004 | flat merges preserve left row count با dedupe RHS | dataio/merge.py | data-loss در RHS را کنترل نمی‌کند |
| E005 | SAP split PR item / PO item / workflow / compatibility main | SapAdapter | separation درست، lineage و workflow identity ناقص |
| E006 | Business DWH current upsert + hash source rows | business_dwh.py | as-of publication isolation ندارد |
| E007 | report/dwh publish pointers با هم | store.publish | atomic pointer ≠ atomic dataset/files |
| E008 | optional failures degrade، critical fail gate | reliability.py | critical list با source population policy سازگار نیست |
| E009 | Process case=connected component تمام keys | process_evidence._components | shared dimension collapse بازتولید شد |
| E010 | Cash Flow Decimal + explicit evidence/links/rates | cashflow/engine.py | upstream identity/amount semantics همچنان باید درست باشند |
| E011 | offline extractive KB و optional AnythingLLM | knowledge_desk/query.py; learning/anythingllm.py | دو مسیر با risk model متفاوت |
| E012 | separate historical warehouse schema | historical_store/runtime | lifecycle core فعلی به آن متصل نیست |

## تصمیم‌های لازم برای Phase بعد — OPEN / NOT IMPLEMENTED

### O001 — Snapshot publication ownership

**مسئله:** F001/F002/F003/F012/F040. باید هر consumer از یک run واقعی و immutable بخواند. گزینه A: append-only run membership برای facts/evidence + current view؛ گزینه B: staging database/tables و atomic promotion. انتخاب نهایی: **UNKNOWN / NEEDS EVIDENCE** درباره حجم، retention، concurrent readers و زمان refresh. معیار پذیرش: blocked/failed run هیچ داده/فایل قابل انتشار قبلی را تغییر ندهد. افزودن WHERE last_seen_run کافی نیست.

### O002 — Transaction / observation / snapshot identity

برای هر source تعیین شود export full snapshot است یا delta؛ natural event ID چیست؛ آیا reorder file بی‌معناست؛ absence حذف است یا پوشش ناقص. SAP workflow history، NTSW commitment و FX IDs بدون این تصمیم قابل اصلاح قطعی نیستند. گزینه پیشنهادی: native observation immutable همراه file/sheet/row + business record key + effective time، بدون جعل event از snapshot.

### O003 — Process Case identity

Material و employee relation نباید به‌خودی‌خود پرونده‌ها را یکی کند. case root مناسب (PR-item، ORDER-item، shipment، REG مالی یا multi-object process) با مالک فرایند تعیین شود. تا آن زمان component فعلی فقط graph component است، نه پرونده کسب‌وکاری قطعی. lifecycle و stable case IDs باید مستقل از تغییر membership تعریف شود.

### O004 — Canonical relation policy

برای ORDER↔REG، BL↔ORDER، PO↔PR، REG_FILE↔REG حداقل cardinality، scope، temporal validity و source authority تعریف شود. direct native evidence جدا از transitive path بماند. `dwh_registration_hub` cross-product را relation اثبات‌شده ننامید. singleton mapping به معنی صحت semantic نیست.

### O005 — Finance grain / unknown / currency

NTSW request/commitment و commercial lines باید با natural identity، currency، UOM و date/version قرارداد داشته باشند. Unknown نباید صفر شود. تبدیل فقط با explicit approved rate؛ غیرفعال/رد/ابطال از allocated مستقل. F007/F008/F009/F016/F023/F027/F031 ورودی این تصمیم‌اند.

### O006 — SAP domain reconciliation

تساوی `Purchase Requisition` با `po.Purchase Requisition` و `Material` با `po.Material` باید بررسی شود، نه فرض. PR deletion و PO deletion scope مستقل دارند. missing PR item می‌تواند PR-only evidence باشد ولی نباید business PR-item مصنوعی یا duplicate-free fact نامیده شود. workflow event time با Changed On snapshot date یکی فرض نشود.

### O007 — Oracle / Commercial inventory semantics

آیا ردیف‌های یک material locations مستقل‌اند یا observations تکراری؟ آیا max cross-sheet تأییدشده است و date یکسان دارد؟ mapping MPN↔material code باید crosswalk واقعی داشته باشد. سیاست latest inventory به ترتیب فایل نیازمند source-order contract است. تا آن زمان F013/F014/F015 محدودیت تصمیم موجودند.

### O008 — Domain failure and publication scope

کاربر/مالک محصول باید atomic global snapshot یا per-domain snapshots را انتخاب کند. اگر global atomic لازم است، این coupling intentional و شفاف باشد؛ اگر availability مستقل لازم است، gate و consumer versioning باید domain-aware باشند. هیچ gate حساس صرفاً برای عبور تست ضعیف نشود.

### O009 — Knowledge authority and access

KB outage از deletion جدا، restore صحیح، version/effective dates و user scope تعریف شود. Operational query باید retrieval error را از not found جدا کند. AnythingLLM workspace/model/grounding configs و شبکه/ACL هنوز UNKNOWN / NEEDS EVIDENCE هستند؛ وجود prompt توصیه‌ای تضمین منع hallucination نیست.

### O010 — One consumer contract for process and financial UI

سه مدل stage و چند financial path هم‌زمان‌اند. نام‌های terminal، SWIFT، receipt، payment، customs باید mapping صریح داشته باشند. deprecation/migration هر مسیر نیازمند فهرست کاربران/خروجی‌هاست؛ در Phase 0 حذف هیچ مسیر مجاز نیست.

## شواهد موردنیاز، بدون درخواست دسترسی زودهنگام

| Evidence | Why | Owner / source to resolve |
|---|---|---|
| دو یا سه export متوالی از هر منبع با row ID | snapshot/history/deletion/replay | مالک هر source |
| نمونه SAP با split PO و PR-item و deletion | PO lineage و workflow events | SAP functional owner |
| native commitment ID + allocation state codes | تکرار تعهد و تشخیص allocated | NTSW export owner |
| کلید مکان/انبار Oracle و تاریخ شیت‌ها | sum/max stock validity | inventory owner |
| تعریف دریافت اسناد/رسید مالی/وصول ذی‌نفع | جلوگیری از terminal/payment جعلی | Credit / Finance |
| روابط مستند ORDER/REG_FILE/REG/BL با چندمقداری | جلوگیری از fan-out و synthetic relation | Commercial / Logistics |
| نمونه DB واقعی ارتقایافته و publication logs | migration و isolation | operator / deployment owner |
| source outage policy و freshness SLA | stale fallback و domain gating | governance owner |

## ترتیب پیشنهادی رسیدگی، بدون اجرا

1. Publication isolation و current membership؛ هم‌زمان regression برای R1→blocked R2.
2. Process identity و monetary grain/state/ID defects.
3. Native evidence contracts، source availability و SAP/Oracle semantics.
4. KB lifecycle و grounding، consumer consistency و history migration.

این ترتیب بر محدودکردن اثر خطا مقدم بر بهبود UI است؛ برنامه implementation تنها پس از تصمیم مستقل مرحله بعد تهیه می‌شود.
