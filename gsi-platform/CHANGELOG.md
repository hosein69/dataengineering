# Customizable HTML + Cash Flow release — 2026-09-26

- Added an offline HTML layout customizer to production report export: drag-and-drop block ordering, accessible move up/down controls, full/half/third/quarter sizing, hide/restore, reset, local persistence, and portable “download customized HTML” with the chosen layout embedded into the file itself.
- Customization is presentation-only: source rows, filters, KPI calculations, process semantics, evidence, DWH and publication state are never mutated.
- Analytical chart cards and individual Process Mining panels now receive stable customization keys so they can be independently reordered, resized or removed.
- Fixed a real Cash Flow HTML wiring defect: Money Flow Control Tower runtime existed but no rendered target was present. `cashflow` is now a first-class Composer block and is included in default Expert/Manager/Executive/Analyst layouts.
- Added `gsi/studio_core/html_customizer.py`, reproducible customizable sample generation, and regression tests for portable layout seed, Cash Flow rendering, chart/process stable keys and runtime call path.

Validation for this pass: targeted HTML/composer regression 18/18 PASS; JavaScript syntax compilation PASS; Python compile PASS. Package/GSI manifests are rebuilt after this entry.

---

# Final clean release — 2026-09-26

- Release packaging rebuilt from scratch: runtime warehouse/cache, demo scratch output, pycache and stale package-hash manifest are excluded deterministically by `tools/build_clean_release.py`.
- Excel font contract restored to `IRANSans Light`; HTML keeps the existing IRANSansWeb-first stack.
- Process Explorer UX hardened without changing process semantics: persistent active-node state, compact evidence-quality chips, keyboard zoom/reset/Escape, correct disabled zoom controls, and existing GSI design tokens only.
- Five production-path HTML samples plus an index are shipped under `samples/release_html/`; they were generated from the real synthetic Pipeline/report path.
- Validation on extracted candidate bytes: independent audit 173/173, extended audit 77/77, targeted release regression 85/85, compile PASS, clean-package manifest 1005/1005.

---

# Current build: GSI 29.8.2 RC4-OPT2 H1 — process-diagram re-skin (fixes UI regression)

`gsi/studio_core/process_diagrams.py` — a new offline process-flow module
(interactive SVG process-map with click-to-focus, edge highlighting, zoom,
and an SVG-export toolbar; plus a Variant Explorer) delivered in a separate
package outside this pass — shipped its own private, hardcoded design system
instead of GSI's tokens: literal hex colors, literal pixel spacing/radii, and
a hardcoded `Tahoma, Arial, sans-serif` font in every SVG `<text>` element.
It carried **zero** `box-shadow` and **zero** `transition`/animation anywhere
in its stylesheet. Wired into `html_export.py`'s `_process_flow_html` /
`_variants_html`, this is what a report actually rendered — a flat,
un-animated, un-shadowed panel bolted onto the rest of the paper/teal/navy
report, which is what read as "UI/UX got worse."

Fixed by re-skinning `process_diagrams.py` in place: every hex/px literal in
its `STYLE` block and inline SVG attributes now reads a GSI design token
(`var(--teal)`, `var(--navy)`, `var(--sunken)`, `var(--border)`, `var(--r-*)`,
`var(--sp-*)`, `var(--e-raised)`/`var(--e-overlay)` for elevation,
`var(--dur-short)`/`var(--ease-standard)` for motion, `var(--font)` for
IRANSans). Process nodes get the same soft drop-shadow treatment as every
other chart mark in `charts_js.py`; buttons/selects/cards get the same hover
lift and calm transition already used across the rest of the report. Edge
colors (forward/return/repeat) now draw from the product's own validated
categorical ramp (`--navy`, `--series-5`, `--teal`) instead of a private blue/
purple/teal triad.

**Scope decision — only `flow_map` and `variants` were re-wired to the new
module.** Its `handoff_html` and `timeline_html` were left unwired after
re-skinning them broke two existing invariant tests:
`test_opus_rc4_process_views.py::test_no_view_presents_an_observation_as_a_target`
(the handoff panel must literally say "زمان انتظار است نه زمان کار" — the new
module's rephrased caption didn't contain that exact clause) and
`test_report_composer_tab_isolation_v284.py::test_timeline_has_local_escape_runtime`
(the original Case Timeline defines its own local JS escape function by design,
documented in its own comment, because its inline `<script>` runs before the
shared runtime is parsed — the new module's `<template>`-based renderer
doesn't need one, but the test still asserts on the old implementation
detail). Both functions were removed from `process_diagrams.py` as dead code
rather than shipped unused. `handoff_html`/`_timeline_html` in
`process_views_html.py`/`html_export.py` are unchanged from before this pass.

**Follow-up: CSS minification.** `gsi/design/css.py::stylesheet()` now runs
its assembled output through a new `_minify_css()` — strips `/* */` comments
and collapses whitespace around `{ } : ; ,`, with quoted `content:"..."`
values protected from the collapse so nothing inside them can be corrupted
even if a future rule adds a multi-word value there. No selector, property,
or value changes — verified pixel-identical in the browser (Kanban shadows,
chip tints, due-date pill colors all unchanged) and by the full suite: same
576 passed / 4 pre-existing failures, `tests/test_design_system.py` 93/93.
Caught and fixed one real thing on this pass: the SVG drop-shadow added
above used a literal `#0B1F33` hex, which the design system's own
"no manual hex" hygiene check correctly flagged — changed to
`rgb(11,31,51)`, matching the decimal-notation convention `charts_js.py`
already uses for the exact same shadow tint.

Measured on a real manager report with both `flow_map` and `variants`
active: stylesheet 31,795 → 28,715 bytes (−9.7%). Checked whether the same
was worth doing for the embedded JS (chart runtime + report interactivity,
~65KB) and the surrounding HTML — both were already hand-authored dense
(≈2% whitespace, ~0% comments measured directly), so a whitespace/comment
pass there would save only a few hundred bytes for real risk of corrupting
a template literal or regex; skipped as not worth it. The dominant lever for
transfer size is gzip, which is free and 100% lossless: this same report is
~227KB on disk and ~53KB gzipped — already the size a browser actually
downloads whenever the file is served through anything that gzips (virtually
every real web server does this by default). No further change made here
since this file's own bytes are what "shipped in the zip" means.

Verified: full suite before and after this specific change — 576 passed, same
4 pre-existing environment-only failures both times, zero new failures.

**Follow-up: de-duplicated the module's stylesheet.** `flow_html` and
`variants_html` each returned `STYLE + <section>...`, so a report using both
`flow_map` and `variants` embedded the same 4.8KB `<style>` block twice.
`_process_suite_html` now injects `process_diagrams.STYLE` once per page —
the same convention already used for `process_views_html`'s `CHART_CSS`
(Kanban) — and the two render functions return only their markup. Confirmed
on a real regenerated manager report: 232,249 → 227,425 bytes, a drop of
exactly 4,824 bytes (the STYLE block's size). Suite re-run after this change:
same 576 passed / 4 pre-existing failures.

---

# GSI 29.8.2 RC4-OPT2 H1 — chart & Kanban visual design pass

Presentation-only pass across `gsi/design/{tokens,css,charts_js}.py` and the
Kanban card block in `gsi/studio_core/html_export.py`. No data pipeline, no
chart data-shaping (`chartFor`, `processStats`, `renderProcess`), no business
logic changed — verified by running the full suite before and after (576
passed, same 4 pre-existing environment-only failures both times) and the
`tests/test_design_system.py` 93-check regression (93/93 both times).

**Categorical palette re-stepped, not replaced.** The eight-hue set in
`gsi/design/tokens.py::CATEGORICAL` kept its brand hues but four of eight
were below the OKLCH chroma floor (read as gray, did no identity work) and
one adjacent pair was below the colorblind-separation floor. Re-stepped with
`dataviz` skill's `validate_palette.js` until all eight cleared every check
in both light and dark mode.

**Donut, bar, scatter, Pareto and trend marks gained real depth and a real
tooltip.** Previously every mark was a flat single-color fill with the
browser's native `<title>` tooltip — indistinguishable from a default
Excel/Chart.js chart. Marks now carry a subtle `drop-shadow` and a
brightness-on-hover state; donut slices get a 2° gap (skipped for slices
under 2.5% share, so they don't vanish) instead of touching arcs; the trend
line is a cubic-bezier curve instead of straight segments. A small shared
tooltip helper (`gsi/design/charts_js.py::tipShow/tipMove/tipHide`) replaces
the native title box with a positioned, styled one; the `<title>` element is
kept alongside it for screen readers and print, where no JS runs.

**Kanban cards got an owner avatar and a toned due-date pill.** Previously
`👤 owner name` and `◷ date · N days` were plain gray text — the same
information a table cell would show, just indented. The owner's initials
now render in a small gradient circle, and the due date is a colored pill
(critical wash if overdue, warning wash if due within 7 days, good wash
otherwise) reusing the same status tokens the rest of the product already
uses — no new color introduced.

**Scope note:** this only reaches charts and the Kanban board built through
`gsi/design/charts_js.py`'s shared primitives (`barChart`, `donutChart`,
`scatterChart`, `paretoChart`, `trendChart`, `groupedChart`) — which
includes the process-mining bottleneck/queue bars in `renderProcess`, since
they call the same `barChart`. It does not add new chart *forms* (e.g. a
Sankey process-flow diagram, a heatmap matrix); the existing seven-form
catalog was restyled, not extended.

---

# Current build: GSI 29.8.2 RC4-OPT2 H1 — daily-email snapshot orchestration fix

One defect, measured against this exact package rather than argued from the
review that flagged it: `gsi/integrations/daily_email.py::create_daily_email`
unconditionally called `Pipeline(today=d).run(build_report=True)` on every
invocation — a full ETL re-run — independent of whatever `python -m gsi
refresh` had already published. `RUNBOOK_FINAL_20260925_FA.md` states Refresh
must only happen via an explicit action (`REFRESH_GSI_DATA.cmd` or `python -m
gsi refresh`); a scheduled `python -m gsi email` task silently violated that
every time it ran, and could collide with a concurrent publisher
(`NETWORK_OUTLOOK_RELEASE_FA.md`: concurrent central publishes are not
supported).

`create_daily_email` now follows the same load_published → load_pipeline
split `app/dashboard.py` already used: by default it reads the last
published snapshot for the requested day (near-zero cost, no warehouse
pressure); it only builds a fresh run when the caller explicitly passes
`refresh=True` (CLI: `python -m gsi email --refresh`), and with no snapshot
and no `--refresh` it raises `NoPublishedSnapshot` with the exact remediation
command instead of silently doing the heavy work. If a concurrent publisher
holds the writer lock during an explicit refresh (`WarehouseBusyError`), the
result falls back to the last published snapshot marked `stale_snapshot`
instead of raising or stacking a second run.

Six new tests in `tests/test_daily_email_snapshot_orchestration.py` cover: a
published snapshot is used without constructing `Pipeline`; no snapshot +
`refresh=False` raises without running `Pipeline`; no snapshot + `refresh=True`
runs `Pipeline` exactly once; a `WarehouseBusyError` during an explicit
refresh falls back to the last snapshot without retrying; and both CLI paths
(`--refresh` wiring, exit code 3 on `NoPublishedSnapshot`). Full runner on
this build: 576 passed (unchanged failures: the 4 pre-existing
Streamlit/AppTest and IRANSansWeb-font-dependent failures already present in
this environment before this change — see `DAILY_EMAIL_SNAPSHOT_ORCHESTRATION.patch`).

---

# Current build: GSI 29.8.2 RC4-OPT2 H1 — audit remediation 2

Two Windows defects that the `GSI_FEEDBACK_20260924_142807` run surfaced, on top
of remediation 1. Channel `rc4-opt2-h1-audit2`.

**`Warehouse.reset()` failed on Windows with `PermissionError: [WinError 32]`.**
Windows refuses to delete a file another handle still holds; on Linux the same
unlink succeeds silently, which is why no Linux run caught it. Deletion now
retries with a short backoff after `gc.collect()` — CPython closes an
unreferenced sqlite connection in its finalizer — and when the file still
cannot be removed, reset no longer fails: the contract is that the warehouse is
empty, not that the inode is gone, so the contents are dropped through SQL and
the report carries `emptied_in_place: true`. A file that survived is listed
under `undeleted`; no deletion is silent either way. A new test drives that
path by simulating `PermissionError(32)` and checks the warehouse comes back
empty, `integrity_check: ok`, and immediately usable.

**The loopback knowledge-service test failed where a corporate policy forbids
binding a local socket** (`WinError 10013`). A machine refusing to open a port
is not the product failing, so the test now skips with the reason instead of
reporting red.

Full runner: **1178 passed, 0 failed.**

Not fixed here, because they are not mine and guessing without a Windows
machine to verify would be worse than saying so: the same WinError 32 pattern
in `test_control_center_v27_2` and `test_fx_obligation_v28_1`,
`test_import_hygiene` (doctor does not exit 1 on Python 3.13 for the flat-module
case), `test_dashboard`, and `test_personalization_v27_1`. See
`review/feedback_triage/TRIAGE.md`.

---

# Current build: GSI 29.8.2 RC4-OPT2 H1 — audit remediation 1

Four changes on top of the 29.8.2 RC4-OPT2 H1 final package, each one a defect
that was measured on that package rather than argued. Runtime channel is
`rc4-opt2-h1-audit1` so this build is distinguishable from the one it came from.

**The release channel string was a version behind.** `gsi/factsheet.py` declared
`rc4-opt1` while the zip, README, CHANGELOG and `PACKAGE_INFO_V29_8_2.json` all
said RC4-OPT2. `VERSION` was correct; only the channel was stale.

**One shipped test still asserted the pre-29.8.2 dashboard contract.** It patched
`Pipeline.run` and expected the page to render, but the 29.8.2 runtime is
`ui_default_mode: published_snapshot_only` / `refresh_mode: explicit_only` — with
no published snapshot the page stops instead of starting an ETL. The test now
drives the snapshot path the page actually takes, and a second test asserts the
other half of the contract: no ETL on page load. The release gate had excused
these as `streamlit_apptests: ENVIRONMENT-BLOCKED`, which is not the same as
passing — they run and fail wherever `streamlit.testing` is installed.

**The knowledge index gave no sign when one file dominated it.** `build_index`
now returns `largest_source` and `largest_source_share`. On the shipped
`offline_knowledge/` folder that reads `evidence.txt` at 0.97 — 958 of 988
searchable chunks — which `static_export` would inline into `chatbot.html`.
Nothing is blocked or deleted; the composition is simply no longer silent.

**The AnythingLLM grounding claim was prose nothing enforced.** The prompt asks
the model to answer only from the lesson and the workspace while the request
sends the default `mode`, and no caller checked whether a source came back.
`ask()` now documents what `mode` actually constrains, and `has_sources()` lets
a caller verify grounding instead of trusting it. The default is unchanged:
AnythingLLM's `chat`/`query` semantics were not verifiable from the audit
environment and must be confirmed against your own version first.

Full runner on this build: **1177 passed, 0 failed** (the package it came from:
1175 passed, 1 failed). `gsi/MANIFEST.json` and `PACKAGE_SHA256_FINAL.json` are
regenerated; `python -m gsi.doctor` reports every fingerprint matching.

Still open and deliberately not changed here: `offline_knowledge/raw/evidence.txt`
is still in the package. Removing it is a business decision, and
`static_export.py` raises `BLOCKED_EMPTY_KNOWLEDGE` when nothing real is indexed,
so the chatbot build will fail until real knowledge documents replace it.

---

# Current release: GSI 29.8.2 RC4-OPT2

Scope: source-authority FX equivalents and currency-safe financial outputs, built
on 29.8.1 RC4-OPT1.

**Source equivalents are now first-class facts.** FX purchase rows preserve and
aggregate source-reported EUR/IRR equivalents with explicit coverage. Credit
rows expose source-reported EUR/IRR equivalents with LC-level snapshot dedupe;
conflicting values are withheld and flagged instead of guessed.

**NTSW commitment equivalent is explicit reference valuation.** Release
Commitment remains the authority for the native balance. EUR/IRR equivalents are
computed only from evidence belonging to the same REG and same currency. No
cross-case/global FX rate is used. The exact basis is stored beside every
reference equivalent.

**Mixed currency remains mixed.** Native EUR/USD/CNY amounts are never summed
into a naked total. A weighted purchase rate is numeric only for single-currency
cases; multi-currency cases receive a per-currency rate display rather than a
misleading zero or blended rate.

**Compatibility preserved.** Existing decision/export contracts remain in their
legacy positions; equivalent columns/cards are additive. The 29.8.1 warehouse
performance hardening remains intact.

Validation: `VALIDATION_V29_8_2_FX_EQUIVALENT_FA.md`.

---

# Current release: GSI 29.8.0 RC4

Scope: output integrity and usability, measured against the RC3 package and the
real OF workbook shipped inside it. Read `RC4_OUTPUT_INTEGRITY_FA.md` first.

**Exported HTML now declares its own scope.** The payload always carried every
row, but only the columns the tabs referenced (18 of 561 on a real run) and it
said so nowhere. Every artifact now carries a printable content manifest —
rows, columns, and the full list of excluded column names — plus a record of
any section that hit a display cap. The footer no longer claims the Excel
button carries columns it drops.

**Cash flow reads the real OF workbook.** `inputs.legacy_of()` emitted a status
the engine can never accept, so 61 of 63 events were rejected as
`UNVERIFIED_EVIDENCE` and the report was empty. OF rows are source facts with
their own document reference. Event identity now comes from content instead of
row number, which removes a 5×–8× fan-out on the case-grain columns of that flat
report (CB1 registration value: 303,686.30 → 60,737.26).

**Empty means "no evidence in the source", and says which.** Empty report
sections state their own reason and sit behind the sections that have data;
empty Excel sheets carry the reason instead of bare headers. The financial
report uses the package font stack.

**The warehouse can be wiped and rebuilt:** `python -m gsi.warehouse reset --yes`
(automatic backup, full wipe including frame cache and writer lock, schema
recreate). Nothing is deleted without `--yes`, and a database that is not a GSI
warehouse is never touched.

**The dashboard opens on the published snapshot** instead of rerunning the whole
pipeline, matching what Studio already did. Scope filtering of process extras
stays lazy while still being enforced.

**Seven new Kanban/Scrum process views** (cumulative flow, throughput, aging WIP,
cycle-time percentiles, rework, handoff, stage evidence coverage) and two new
Kanban lane modes (work mix, blocked vs ready). Percentiles are observed
behaviour, never targets.

Validation: see VALIDATION_RC4.md (full runner result recorded there). No production-data certification.

---

# GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# Changes — GSI 29.7.8 RC2

Applied RES-1/2/3; added unknown numeric validation, safe financial source/scope handling, NTSW identifier/status conflict controls, shared financial UI and offline report redesign. Included supplied source-profiler tool unchanged. Runtime version 29.7.8, channel rc2. See DEFENSIBLE_CHANGES_FA.md.
