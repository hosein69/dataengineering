# Round 5: every FX lifecycle section is its own report-builder element — 2026-09-28

- The standalone FX lifecycle report (e-mail attachment, Studio button) keeps its fixed seven tabs.
  For a custom order, build the report in the report builder from the `fx_*` elements.
- FX elements do not react to the filters above an HTML tab, as it was for the combined block.
- The report's row scope (departments, experts) applies to FX elements. Allowed fields restrict only
  the tab tables: FX elements, like the combined block and the money control tower, read amounts and
  B/Ls from the row-scoped FX tables. Leave the money elements out of tabs for an audience that must
  not see amounts.
- The report builder renders the FX elements in Persian, like the combined block. Each element has an
  English version (`composer_part(..., lang="en")`, tested), but Studio does not build English
  report-builder pages yet.
- Per-stage and per-registration Excel links exist only in the standalone report. The «دانلود Excel»
  element carries the three report-wide workbooks and embeds none above 400 registrations.
- Validated on synthetic data only; acceptance on the organisation's real files is still pending.

# Round 4: review fixes — 2026-09-28

- A registration whose currency is unknown has an unknown shipped value, even when all its B/Ls share
  one currency; the registration currency is never inferred from its B/Ls.
- A B/L with a SATA value but no SATA currency does not borrow the customs declared currency; it stays
  «ارز نامعلوم» and out of the total.
- Snapshot schema drift: a column added between runs is added to the `snap_*` table (older runs read
  NULL). A column dropped or renamed stays in the snapshot table; new rows get NULL and old values are
  not moved to the new name.
- CSV downloads (Studio view, analytics pivot, warehouse table, event log) are raw data. Opening a CSV
  in Excel can still evaluate text that starts with «=»; share the Excel files instead.
- English FX report, critical board and FX workbooks now translate the program's own text (money-event
  names, financial-decision texts, stage evidence, next and suggested actions, critical reasons). The
  round-3 note that English workbooks carry no Persian held only for the small test data. Values from
  source files stay as in the source: bank and NTSW status text, order status, goods descriptions,
  names and customs locations.
- The other reviewer's fixed copy was not received; its tests have not been run against this package.
- Validated on synthetic data only; acceptance on the organisation's real files is still pending.

# Round 3: one insight across Studio, sent HTML, e-mail and Excel; Ravi and IRANSans fonts — 2026-09-28

- Fonts: Ravi first, IRANSans fills the gaps. The owner supplied the licensed files in `assets/fonts`.
  - Ravi Regular was supplied only as FaNum (Persian digits in the Latin digit slots), so Latin digits
    in regular-weight text come from IRANSans. SemiBold and Bold use Ravi's own Latin digits.
  - Ravi ExtraBlack ships but is not embedded: the design's weight-800 headings would pick it.
  - The e-mail body and Excel cannot carry fonts and name `IRANSans Light`, which must be installed on
    the viewing machine.
  - Sent HTML embeds the fonts (about 260 KB per file). Set `GSI_EMBED_FONTS=0` if the licence does not
    cover embedding. Installed system fonts are never embedded.
- Outlook runs no CSS interaction, so the e-mail body carries only the inline stage and money tables.
  The clickable report is an attachment and opens in a browser.
- Embedded Excel grows with the number of registrations.
  - The standalone report embeds per-registration workbooks for the 80 registrations with the most
    days in stage (`max_reg_workbooks`).
  - The report-builder block embeds no workbooks above 400 registrations (`max_embedded_regs`).
  - Stage panels list 60 registrations in the standalone report and 40 in the builder block. The
    rest are in the stage workbook. Counts and amounts always cover all registrations.
- The sent HTML has no search box; use the browser's Ctrl+F or the Excel files.
- English mode translates labels, stages, statuses and levels. Data values (goods descriptions,
  expert names, free text) stay as in the source. English pages (HTML report, critical board, Studio
  FX view) and English workbooks are left-to-right; the Studio menu, page title and tab titles stay
  Persian in English mode because the language switch covers columns and report content only.
- CSS-only interaction (stage rail, details, tabs, critical filter) was tested in Chromium only.

# FX lifecycle + minimal teal UI (on 29.15.13) — 2026-09-28

- The registration-file step (پرونده ثبت سفارش) has no date in any source; it is evidenced by the file number only.
- A BL linked to more than one registration has no per-registration share in any source; its value is not
  attributed to either registration and the shipped total is marked as a lower bound.
- Shipped value is summed only for BLs in the registration's currency; no FX conversion is applied.
- Validated on the project's synthetic data only; acceptance on the organisation's real files is pending.
- `samples/` HTML files were generated with the previous palette and were not regenerated.
- Column language (فارسی / English) changes column titles only; cell values, KPI captions, tab names
  and chart labels stay Persian. English titles of technical keys are built from a token dictionary
  and Persian titles of keys without a catalogue label are rule-built (`gsi/i18n/key_fa.py`); both
  read correctly for the tested columns but a new source column may need a token added.
- Line icons are inline SVG / CSS masks; they do not depend on an icon font. Tested in Chromium only.
- Calculation accuracy is assessed qualitatively in `docs/ACCURACY_ASSESSMENT_FA.md`; no measured
  accuracy percentage exists until the 30-registration acceptance on real files is run.

# Current release: GSI 29.15.13 — 2026-09-27

- The decision brief reads s58's action queue, which has financial / commitment rules only. Supply
  stoppages (s40 «اقدام پیشنهادی مقاومت») are advice without owner or due date; the brief shows
  them as outside the queue and asks for an owner, it does not create the action. A supply rule in
  s58 needs the owner's SLA (review F4).
- Owners are roles («رفع تعهد/بانک عامل»), not people; the role → person map exists for e-mail
  (`role_mail`) and is not shown in the HTML.
- Which output the manager actually reads (HTML, Excel, e-mail) is unknown; if it is Excel, the
  brief belongs on sheet 1 (same `compute_decision_brief`) — not yet done.
- Filter labels in the HTML still show technical keys (`KEY_MATERIAL`, …).
- The HTML supply tab is off by default (`GSI_HTML_SUPPLY_TAB=1` to show it).
- `doctor` still reports the two expired emergency rules (FX overlay 1405_05_14, customs
  `emergency_sata_waiver_1405`); their successors are a regulatory decision.

# GSI 29.15.12 — 2026-09-27

- The expert file is read on its exact 35 headers only. A renamed header is reported missing, not
  guessed; add the new spelling to `EXPERT_HEADERS` deliberately.
- Part states come only from Order Status. Only the four states and a few English equivalents are
  recognised (`status_lexicon.yaml → part_states`); any other text is «وضعیت نامشخص» until added.
- Quantity ordered but not yet in any part (Quantity In Order − Σ Quantity In Part) is in no state
  and is not shown as «نزد سازنده» — an open owner decision.
- Order-less expert lines keep their part states in the mart and the ledger; the warehouse supply
  fact table is keyed by order and records them only as partial evidence.

# GSI 29.15.11 — 2026-09-27

- Every Commercial Expert Order×Material is a row of the mart and of every calculation
  (`MOGH_ITEM_ROLE` = FIRST / ADDITIONAL / NO_ORDER). This supersedes the 29.15.8 and 29.15.10 notes
  below that the mart stays at order grain and expert-only materials are not calculated.
- Which BL carries an order's second material is not recorded in any source, so `ADDITIONAL` rows
  carry no BL and no BL-derived state; their row-level demurrage days read 0 like any row without a
  discharge date, and case-level averages skip them. A per-line BL column in the expert file would
  let them carry their own.
- Order-level columns (PI value, REG, commitment, dates) are repeated on every material row of the
  order. They must be aggregated with the grain helpers (`safe_agg`, `case_rows`), never summed
  row-wise; every built-in report does so, an ad-hoc export sum would not.
- Row counts labelled «پرونده» in sheets 11, 12 and 16 count supply rows (BL × material), so a
  multi-material order contributes one per material; order/BL counts there stay distinct counts.
- `python -m gsi.doctor` reports two regulatory rules that expired on 2026-09-22 (the 1405-05-14 emergency
  deadline overlay in fx_governance and the 1405 emergency SATA waiver in customs). Their successors are
  regulatory facts to be supplied by the owner; nothing was invented. Same in 29.15.10.
- Acceptance on the organisation's real Commercial Expert file is still pending (not available here).

# GSI 29.15.10 — 2026-09-27

- Every Commercial Expert Order×Material is a row of the main material view (HTML, Excel sheet 14,
  Studio); rows that exist only in the expert file are labelled and are **not** counted in KPIs,
  sums or the mart. Whether they should enter calculations is an open owner decision.
- Expert-only rows never carry an operational position/stage/BL event («نامشخص»); Oracle stock and
  need are shown only for the exact same material code.
- The flat order mart and Excel sheet 2 are still at order grain (one representative material);
  the complete lists are in `MOGH_MATERIALS_ALL` / `MOGH_MATERIAL_DESCS_ALL` there.
- Acceptance on the organisation's real Commercial Expert file is still pending (not available here).

# GSI 29.15.8 — 2026-09-27

- The shipping tab is computed on the current published and filtered main mart;
  it does not reconstruct omitted BLs or certify transport performance.
  Booking, hub events, switch B/L audit, free time, actual charges and ETA
  revision logs are absent. DO_DATE is receipt date, not request/issue/payment.
  A dossier with conflicting dates suppresses that interval and exposes the gap.

- Transition durations are observations, not proof of a bottleneck or an SLA
  breach. No cross-domain bottleneck percentage or ranking is certified.
  Settlement due status is case specific in the FX stage timeline; missing or
  unverified deadlines require review under that subsystem's rules.

- The feedback workbook compares a reconstructed old flat-material visibility
  proxy against the new material ledger on the same published run. It is not a
  byte-for-byte historical old-version run. Reviewer sufficiency is subjective;
  observed success cohorts are descriptive and cannot establish causal uplift
  without prospective comparable/randomized assignment and verified outcomes.
- The shareable JSON contains aggregate counts only; the local Excel review
  file contains order/material identifiers and must remain within the user's
  authorized environment. No percentage is invented when outcomes are absent.

- The main flat mart remains at order/BL grain and cannot carry every material
  as a separate main row without multiplying unrelated financial amounts.
  A separate expert ORDER×MATERIAL ledger is published and shown in Studio and
  the official Excel line sheet. Missing expert fields do not suppress its
  witnessed components; complete stock stays unknown until all five buckets
  are witnessed. Oracle stock repeated across different orders is not additive.
- Real Commercial Expert/Oracle workbook reconciliation and end-to-end Windows
  acceptance are pending. Description variants in an order containing several
  materials are shown at order level, never assigned to its first material.

- Role mail has no real-HR/Classic-Outlook acceptance in this environment. Only
  seven roles with explicit `EXPERT_*` owner columns are supported; transport
  needs its own proven source and role mapping. It sends actionable cases for
  the current owner only, never fabricates a task for every HR person.
- A missing, inactive or ambiguous HR owner/CC, or a stale HR snapshot, blocks
  the corresponding message. A partial batch cannot be sent. Sending requires
  Windows Classic Outlook, a configured mailbox and an explicit action; a
  scheduled command may be used after an operator validates it. Reserved but
  uncertain deliveries need manual reconciliation before any retry.

- HR scopes are exact and conservative: duplicated names/codes, inactive people,
  or multiple vice holders for one vice unit cannot expand a team view. Real HR
  roster reconciliation and SMB/Windows acceptance remain required. An absent
  leader link can omit a subordinate until HR fixes the source.
- The personal workspace now uses an HR-derived four-level presentation. The
  Streamlit visual pass could not be measured in this environment (Streamlit and
  a browser runtime were unavailable); a 9/10 usability score is a target,
  not a tested claim.

- Legacy FX obligation `chain()` and `coverage()` now use the published NTSW
  file set, with an explicit `run_id` for historical inspection. They return
  no archive-derived decision when nothing is published. Multiple distinct
  commitment balances inside one published run still require a separate
  business rule for selecting a current balance; do not interpret an arbitrary
  row of the chain as an approved aggregate.
- Eight further derived financial inputs retain missing evidence as missing,
  with `*_IS_UNKNOWN` flags. Consumers of these fields must be checked on real
  workbooks before operational sign-off. No official regulation was changed.
- The historical F023 and F028 bullet points further below describe findings
  from an earlier release. Current code scopes obligation totals by published
  file set and reads every contracted clearance sheet; real workbook acceptance
  remains outstanding.
- Validation in this environment: 3 new financial tests, 8 legacy obligation
  tests and 61 core validation checks passed. The full claimed suite could not
  be rerun here because `pytest` is unavailable.

**A/B-driven fixes** (29.14.0 ↔ 29.15.0 on identical inputs; `docs/AB_TEST_29_15_1_FA.md`). Still open:
- `EUR_VALUE`, `DUTY_AMOUNT` and `CREDIT_*` are still derived with a 0 default for unknown, the same
  pattern fixed for `INVOICE_VALUE`. No trust-layer decision reads them today; each is a one-word
  addition to `UNKNOWN_SENSITIVE` when one does.
- A systematic error affecting ≥5% of one group is not asked about case by case (it is a mode, not an
  outlier). Above 2% outliers per field it becomes one "two populations in one field" question, and a
  jump in the total is caught by the "too good" detector.
- The FX timeline shows SATA's own currency next to SATA's invoice amount; when SATA records no currency
  the event currency is blank (unknown), never borrowed from NTSW.

# GSI 29.15.0 — 2026-09-26

**Added in this release:** anomaly inquiry and human-approved healing (`gsi/trust/anomaly.py`,
`gsi/trust/inquiry.py`, stages 21 and 96). Limits worth knowing before relying on it:
- History-based detectors (volume drop, "too good", new category) need at least three earlier runs
  that were produced by 29.15.0 or later; before that only within-run checks (numeric outliers,
  spelling variants) can fire. Earlier snapshots carry no `observations` and are ignored, not guessed.
- Numeric outliers need at least 8 peers per group (currency); small groups are not judged.
- Repairs exist only for input columns present by stage 21 (INVOICE_VALUE grouped by INVOICE_CURRENCY, DAILY_NEED, STOCK_IKCO,
  STOCK_SAPCO and six category fields). Computed outputs such as «مانده تعهد» are asked about but
  never repaired; the question is routed to their inputs.
- An unexplained outlier does **not** yet change a decision's grade. Whether it should cap additive
  decisions at «جهت‌نما» is an open business decision, not a technical one.
- Answers are stored in the local warehouse (`wh_audit`). A warehouse reset without backup loses them.

# Previous release: GSI 29.14.0 — 2026-09-26

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
