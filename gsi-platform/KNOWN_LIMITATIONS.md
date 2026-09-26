# Current release: GSI 29.13.0 — 2026-09-26

**Closed in this release** (details: `GSI_REVIEW_REPORT_V29_9_0_FA.md`): numeric-parsing magnitude errors,
Jalali invalid-date rollover and leap-year formula, invisible characters in join keys, currency
mis-identification, several Unknown→Zero paths in the FX/money-flow layers (F031 family on those
surfaces), Python 3.11 dashboard crash, quadratic cash-flow engine, Streamlit telemetry/LAN exposure.

**Still open — read before deployment**
- **Production certification is not claimed.** Real corporate workbooks (UNC/SMB shares) were not
  available; header mapping and final reconciliation must be run on the organisation's own snapshot
  (`REFRESH_GSI_DATA.cmd` → `VERIFY`), and Windows/Outlook acceptance is still pending.
- Two time-bound emergency rules expired on 2026-09-22; RuleBook stays fail-closed until an official
  successor/non-extension decision is recorded (`python -m gsi doctor` lists them).
- Performance numbers in this package are synthetic (scaled realistic-header workbooks). Real network,
  Excel and SQLite timings must be measured on the target machine.
- Streamlit apps write the chosen reference date into the process environment (`GSI_TODAY`); the apps are
  bound to localhost for a single operator — several simultaneous users on one server are not supported.
- Legacy numeric contract `num_safe` still maps *empty* to `0.0` for backward compatibility; decision
  surfaces use the strict parser. F031 is therefore closed on reviewed surfaces, not declared closed
  code-wide.
- Currency list covers the currencies seen in Iranian trade; an unlisted currency is kept as its full
  source text (never merged), but it must be added to `gsi/rules/currencies.yaml` to get an ISO code.
- Inherited open findings below (F023, F028, F037, N08, RC03, RES-4/5/6, F019/N04) are unchanged.

---

# Current delivery: GSI 29.8.2 Final Production Rewrite — 2026-09-24

این تحویل، مسیر runtime واقعی 2026-09-24 را مبنا قرار می‌دهد. خطای production مشاهده‌شدهٔ
`F031` در مرحله `s20_derive` برای شش فیلد حساس مالی بسته شده است: نبود شاهد عددی
به‌صورت Missing/NaN باقی می‌ماند و صفر فقط با شاهد عددی صفر تولید می‌شود. پرچم‌های
`*_IS_UNKNOWN` همچنان برای lineage/coverage حفظ شده‌اند. تست اختصاصی این قرارداد داخل
`tests/test_final_runtime_rewrite_20260924.py` است.

Quality Gate فیزیکی SAP نیز اصلاح شده است: grain درست `sap/raw_rows` برابر
`SAP_SOURCE_SHEET + SAP_SOURCE_ROW` است، نه `SAP_SOURCE_ROW` به‌تنهایی. بنابراین
شروع مجدد شماره ردیف در شیت‌های `pr/pack/po/inbound/GR` duplicate مصنوعی نمی‌سازد.

اجرای روزمره Streamlit دیگر ETL را خودکار شروع نمی‌کند. `START_GSI.cmd` آخرین Snapshot
منتشرشده را می‌خواند؛ `REFRESH_GSI_DATA.cmd` تنها مسیر صریح rebuild است و
`EXPORT_GSI_EXCEL.cmd` Excel را از Snapshot منتشرشده می‌سازد، بدون خواندن دوبارهٔ
workbookهای عملیاتی.

**مرز تأیید:** کد/پکیج این تحویل با gateهای داخل بسته و ممیزی‌های frozen/extended
تأیید شده است. benchmarkهای performance داخل بسته synthetic هستند؛ زمان واقعی شبکه،
Excel و SQLite روی Windows سازمان فقط با اجرای `REFRESH_GSI_DATA.cmd` روی همان ماشین
قابل اندازه‌گیری است. این مرز، نقص کد باقی‌مانده نیست و به‌صورت صریح از ادعای عدد
performance تولیدی جلوگیری می‌کند.

---

# Current release: GSI 29.8.2 RC4-OPT2

معادل‌های خرید ارز و Credit که مستقیماً در Source گزارش شده‌اند در این نسخه
حفظ و در خروجی‌ها استفاده می‌شوند. با این حال `FX_NTSW_BALANCE_EUR_EQ` و
`FX_NTSW_BALANCE_RIAL_EQ` **معادل گزارش‌شده توسط NTSW نیستند**؛ چون در قرارداد
فعلی Release Commitment چنین ستون مستقیمی وجود ندارد. این دو فیلد reference
valuation هستند و Basis آن‌ها کنار عدد ذخیره می‌شود.

برای مانده NTSW نرخ از پرونده دیگر یا ارز دیگر استفاده نمی‌شود. اگر برای همان
REG+Currency شاهد کافی نباشد Equivalent خالی می‌ماند. نرخ Allocation فقط fallback
IRR همان پرونده/ارز است. Source-reported EUR/IRR Credit نیز با شماره LC dedupe
می‌شود؛ conflict در یک LC باعث withheld شدن همان Equivalent می‌شود، نه انتخاب
دلخواه یک مقدار.

Coverage خرید ارز row-based است، نه amount-weighted بین ارزهای متفاوت؛ چون ساختن
یک denominator از native amountهای EUR/USD/CNY خودش نیازمند تبدیل ارز است.

اعتبارسنجی production روی workbookهای واقعی شبکه/UNC سازمانی در این محیط انجام
نشده است. بنابراین صحت mapping هدرها و reconciliation نهایی باید روی Snapshot
واقعی سازمان نیز اجرا شود. این محدودیت مانع از پاس شدن regressionهای کد نیست،
اما مانع از ادعای production certification است.

---

# Current release: GSI 29.8.1 RC4-OPT1

این نسخه F031 را در **سطوح تصمیم‌ساز بررسی‌شده** محدود می‌کند: Studio KPI،
Excel commitment/scorecard/charts، Excel سفارشی، نمودار ایمیل، insight و
history دیگر unknown balance را صفر فرض نمی‌کنند و جمع بین ارزهای متفاوت
تولید نمی‌کنند. قرارداد عددی legacy در هسته `CommitmentEngine` هنوز برای
backward compatibility باقی است و با `BALANCE_IS_UNKNOWN` همراه می‌شود؛
بنابراین F031 در کل کدبیس «کاملاً بسته» اعلام نمی‌شود.

اعتبارسنجی production روی workbookهای واقعی شبکه سازمانی در این محیط انجام
نشده است. Streamlit نیز در محیط ممیزی نصب نبود، بنابراین دو تست browser/app
که به `streamlit.testing` نیاز دارند اجرا نشدند. جزئیات در
`VALIDATION_V29_8_1_OPT.md` ثبت شده است.

---


# Known limitations — GSI 29.7.8 RC2

Production sign-off remains withheld. The package is a complete review delivery, not a certification of corporate data.

- F023: legacy obligation totals can aggregate historical archive versions.
- F028: largest-sheet selection can omit secondary operational sheets from standardized processing.
- F031: unknown/default-zero semantics are not consistent in every legacy report. New companion flags and degraded checks expose selected cases; they do not fix all calculations.
- F037: deployment and application authorization are not certified.
- N08: component-derived process IDs are not durable case identifiers.
- RC03: earlier synthetic shared-DWH SQLite index corruption remains unexplained. Isolated passing suites and clean repeats do not establish root cause.
- RES-4: ORC_BUYER producer exclusion versus authority candidacy remains unresolved.
- RES-5: the 17 real workbooks needed for production smoke/reconciliation were not provided in this work session.
- F019/N04: early RHS deduplication can conceal join-cardinality evidence in legacy paths.
- RES-6: operational questions containing IDs can skip knowledge-document retrieval.
- Financial snapshot measurements can still use report as-of as observed_at. This is not verified source observation time.
- Source-profile heuristics confuse REG_FILE/REG and date headers; identical relationship columns can raise an AttributeError. The supplied tool is included unchanged and cannot establish canonical authority.
- Same-case licence status history is preserved and flagged, not resolved by assuming status priority. Equal-date conflicting allocation requests are quarantined; this policy does not settle all source lifecycle semantics.
- Full event deduplication, deletion/delta semantics, retention, real production concurrency, enterprise network/Outlook integration and migration remain unverified.
- Figma returned UNAUTHORIZED requiring reauthentication. No Figma design file was created or accepted.

See review/rc1_documents/KNOWN_LIMITATIONS.md for historical details. Its statement that no browser inspection was performed is superseded for the RC2 exported financial HTML and the explicitly recorded Streamlit check only.
