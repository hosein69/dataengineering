# گزارش نهایی اصلاح و اعتبارسنجی GSI — 2026-09-24

## 1) مبنای این اصلاح
این Release مستقیماً از feedback واقعی محیط Windows کاربر با شناسه `GSI_FEEDBACK_20260924_142807` ساخته شده است؛ نه از حدس، تست قدیمی یا بازنویسی Greenfield.

نتیجهٔ baseline در محیط کاربر:
- Frozen independent semantic audit: **130 PASS / 43 FAIL** از 173.
- Extended diagnostic: **44 PASS / 33 FAIL** از 77.
- هر 17 خانوادهٔ IA01..IA17 بازتولید شد.
- Manifest و knowledge bundle خود پکیج سالم بودند.
- بخشی از failure/errorهای تست داخلی ناشی از Windows Temp/SQLite locking، corporate proxy روی localhost و classification اشتباه pytest exit=5 بود؛ این موارد از failureهای business/algorithm جدا شدند.

## 2) قراردادهای هویتی غیرقابل اختلاط
این Release قرارداد زیر را حفظ و سخت‌گیرانه‌تر enforce می‌کند:
- `REG` = ثبت سفارش = شماره ثبت سفارش = کد ثبت سفارش.
- `REG_FILE` = شماره پرونده / شماره پرونده ثبت سفارش و **مستقل از REG**.
- `ORDER` = سفارش / شماره سفارش / Order No. / Our Reference.
- `BL` = بارنامه / شماره بارنامه / BL No.
- زنجیرهٔ مجاز cross-source: `ORDER ↔ REG_FILE ↔ REG ↔ BL` بر پایهٔ شاهد واقعی؛ نه inference ساختگی.
- `PO No.` معادل ORDER تجاری نیست مگر قرارداد منبع صریحاً آن را اثبات کند.
- Material برای NTSW-only gate الزامی نیست.

## 3) اصلاح 17 خانوادهٔ finding مستقل

| Finding | مشکل baseline | اصلاح نهایی |
|---|---|---|
| IA01 | planned purchase وارد actual/rate می‌شد | planned/forecast/draft از purchase واقعی و rate authority حذف شد؛ status ناموجود برای سازگاری قدیمی به‌تنهایی حذف نمی‌شود. |
| IA02 | Infinity وارد معادل مالی/coverage می‌شد | تمام مسیرهای عددی حساس به finite-number guard مجهز شدند؛ ±Inf/NaN evidence مالی معتبر نیست. |
| IA03 | نرخ تخصیص تأییدنشده مصرف می‌شد | allocation rate فقط از state واجد authority استفاده می‌شود؛ state صریحاً غیرمعتبر fail-closed است. |
| IA04 | نرخ متعارض به ترتیب ردیف وابسته بود | تعارض نرخ در latest-date به `CONFLICT` تبدیل می‌شود و انتخاب arbitrary حذف شد؛ permutation-invariant. |
| IA05 | پوشش ناقص Credit پنهان بود | پوشش EUR/IRR جداگانه و status PARTIAL صریح شد. |
| IA06 | ردیف بدون REG وارد summary می‌شد | ردیف فاقد REG از total/equivalent حذف و به `missing_key_rows` گزارش می‌شود. |
| IA07 | joint coverage با `min()` تخمین زده می‌شد | coverage مشترک از intersection واقعی caseهای دارای هر دو معادل محاسبه می‌شود. |
| IA08 | Unknown به Zero تبدیل می‌شد | ماندهٔ نامعلوم nullable/NaN می‌ماند و با `BALANCE_IS_UNKNOWN` قابل‌ردیابی است؛ صفر فقط صفر واقعی است. |
| IA09 | native currency در grain ثبت سفارش از بین می‌رفت | اختلاف native currency در یک REG conflict محسوب می‌شود؛ grain مالی بدون واحد حذف شد. |
| IA10 | near-miss header هویت تجاری می‌ساخت | resolver برای REG/ORDER/MATERIAL محافظه‌کار شد؛ پرونده/ارزش/کارمزد/حالت/PO No./descriptorهای Material هویت نمی‌سازند. |
| IA11 | ارز event به جای ارز Credit می‌نشست | headerهای `نوع ارز5/6` فقط به event متناظر map می‌شوند و LC/native currency مستقل می‌ماند. |
| IA12 | composite ناقص معتبر می‌شد | تمام اجزای composite اجباری‌اند؛ None/NaN/blank کل identity را نامعتبر می‌کند. |
| IA13 | lineage فیزیکی Credit قطع می‌شد | `_SOURCE_ROW`, `_SOURCE_FILE_ID`, `_SOURCE_SHEET` در CreditAdapter حفظ می‌شوند. |
| IA14 | PR فیلد PO/Package می‌ساخت | در PR-native تمام standardized fieldهای PO/PACK بدون authority واقعی blank می‌مانند. |
| IA15 | dedupe رویداد هم‌مبلغ/هم‌تاریخ با ارز متفاوت را حذف می‌کرد | `CURRENCY` وارد کلید dedupe رویداد شد. |
| IA16 | linked_amount ارزهای مختلف را خام جمع می‌کرد | linked amount در bucketهای currency-bearing نگه‌داری می‌شود؛ عدد بی‌واحد چندارزی ساخته نمی‌شود. |
| IA17 | Gap صرفاً از fixed chain استنتاج می‌شد | بدون applicability contract صریح، مرحلهٔ فاقد evidence به `NOT_YET_EVIDENCED` می‌رود و GAP الزام‌آور ساخته نمی‌شود. |

## 4) سخت‌سازی Windows / Offline runner
علاوه بر semantic fixes، feedback واقعی محیط کاربر سه failure ثانویه مهم نشان داد:

1. **SQLite file locking در Windows**: connectionهای read/reset که context manager آنها را close نمی‌کرد با `contextlib.closing` بسته شدند.
2. **GSI_HOME در Windows**: اگر کاربر آن را صریح تنظیم کند، identity/personalization اکنون همان مسیر را محترم می‌شمارد؛ `LOCALAPPDATA` فقط fallback است.
3. **Corporate proxy و localhost**: runner برای `127.0.0.1, localhost, ::1` متغیرهای `NO_PROXY/no_proxy` را enforce می‌کند تا تست native Knowledge Desk به proxy سازمانی نرود.
4. هر test file از `--basetemp` مجزا استفاده می‌کند؛ آلودگی Temp/SQLite بین فایل‌ها کم می‌شود.
5. pytest exit code `5` (no tests collected) به `NO_TESTS` طبقه‌بندی می‌شود، نه product failure.
6. source probe فقط فایل‌های data معتبر و در صورت تعریف قرارداد، workbook دارای sheet مورد انتظار را می‌پذیرد؛ فایل Python/Doc دیگر نمی‌تواند به‌اشتباه NTSW تشخیص داده شود.
7. یک ایمیل واقعی نامرتبط در raw knowledge snapshot به `[REDACTED_EMAIL]` تبدیل شد؛ semantic evidence تغییری نکرد و email hygiene دوباره سبز شد.

## 5) تغییرات production code
ده فایل production نسبت به Offline Diagnostic baseline اصلاح شدند:
- `gsi/finance/equivalents.py`
- `gsi/report/financial_summary.py`
- `gsi/engines/commitment.py`
- `gsi/adapters/base.py`
- `gsi/config/keys.py`
- `gsi/adapters/a60_finance.py`
- `gsi/stages/s55_fx_traceability.py`
- `gsi/cashflow/engine.py`
- `gsi/warehouse/store.py`
- `gsi/personalization/identity.py`

یک expectation قدیمی در `tests/test_population_cashflow_v29_7_4.py` با قرارداد سخت‌گیرانه IA17 اصلاح شد: نبود evidence بدون applicability دیگر GAP قطعی نیست. این تغییر برای سبزکردن مصنوعی محصول نیست؛ تست قدیمی دقیقاً خلاف oracle مستقل IA17 انتظار داشت.

تغییرات diagnostic/knowledge نیز در `offline_validation/*` و `offline_knowledge/*` ثبت شده‌اند.

## 6) شواهد تست بعد از اصلاح

### Independent / knowledge-algorithm gates
- Frozen independent audit: **173/173 PASS**.
- Extended metamorphic/contract/knowledge suite: **77/77 PASS**.
- مجموع independent offline semantic tests: **250/250 PASS**.

### Regression نقاط تغییر
- Affected internal regression: **100/100 PASS**.
- Dashboard/email hygiene: **8/8 PASS**.
- Knowledge Desk local service with localhost proxy bypass: **3/3 PASS**.
- Import/deployment hygiene: **6/6 PASS**.
- Python compileall برای `gsi` و `offline_validation`: **PASS**.
- `gsi/MANIFEST.json`: بازسازی شد؛ **0 issue** در verify.

### Sweep همه فایل‌های تست داخلی
کل inventory: **90 test files/scripts**.
- **80 file suites PASS** در محیط ساخت.
- **8 فایل NO_TESTS**: فایل‌های legacy/script-style بدون test قابل collection؛ failure محسوب نشده‌اند.
- **2 فایل UI در محیط ساخت BLOCKED** چون package `streamlit` در این محیط نصب نیست: `test_cashflow_v29_7.py` و `test_fullstack_v29_6_10.py`. failureهای مشاهده‌شده فقط `ModuleNotFoundError: streamlit` بودند؛ در feedback Windows کاربر، همین دو فایل روی baseline به‌ترتیب **42/42** و **9/9** پاس شده بودند و محیط کاربر `streamlit 1.51.0` دارد. بنابراین این دو مورد را PASS نهاییِ build جدید ادعا نمی‌کنیم؛ runner داخل package برای اجرای آنها در محیط واقعی کاربر باقی مانده است.

## 7) Real NTSW re-probe
روی `NTSW-IKCO.xlsx` واقعی موجود، semantic probe پس از اصلاح **OK** است:
- Import License: 1000 rows.
- REG_FILE non-empty: 1000.
- REG non-empty: 840.
- ORDER non-empty: 0 (هیچ ORDER جعل نشد).
- direct REG_FILE↔REG pairs: 840.
- REG_FILE→multi-REG: 0.
- REG→multi-REG_FILE: 0.
- Allocation history: 3286؛ valid allocation rows: 2834؛ aggregate cases: 1418.
- Release Commitment rows: 4007؛ cases: 2390.

## 8) وضعیت Release
**Algorithm / knowledge / semantic remediation gate: PASS.**

این عبارت به‌طور مشخص یعنی 250/250 oracle مستقل و 100/100 regression مستقیمِ کدهای تغییرکرده پاس شده‌اند و real NTSW probe سالم است.

**Overall multi-source production certification همچنان `false` است**، نه به‌خاطر failure دانشی فعلی، بلکه چون فایل‌های واقعی bridge برای اثبات کامل `ORDER ↔ REG_FILE ↔ REG ↔ BL` (مانند IL Append / Abbasi / SATA یا معادل authoritative) در این تحویل موجود نیستند. GSI نباید این روابط را بسازد یا حدس بزند.

Material برای NTSW gate همچنان الزام نیست.

## 9) روش بازآزمایی در محیط کاربر
برای بازتولید نهایی، در پوشهٔ Extract شده اجرا شود:

`RUN_OFFLINE_DIAGNOSTIC.cmd`

اگر sourceها کنار package هستند، هیچ پارامتری لازم نیست. خروجی استاندارد در `offline_feedback/GSI_FEEDBACK_*.zip` تولید می‌شود.
