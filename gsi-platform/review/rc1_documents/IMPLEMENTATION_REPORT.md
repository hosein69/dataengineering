# IMPLEMENTATION_REPORT — 29.7.7 RC1

Incremental review candidate from the supplied 29.7.6 archive. All 40 Phase 0 and 13 Opus findings have separate verdict and closure. Two evidenced RC findings address UI lifecycle/dependency floor and stale test isolation. Original inputs are preserved under review/inputs.

The delivered work is substantive but **does not close the whole requested architecture/financial contract**. F023, F028, F031, F037 and N08 remain release blockers; several accepted-with-modification findings are partial. Do not treat successful tests as permission to deploy unresolved finance or access-control semantics.

Implemented: published semantic snapshots and immutable captures; historical run membership; physical representation multiplicity; PO-side lineage/conflict; ambiguous hub without Cartesian products; process dimension separation, downstream preservation and independent state columns; status polarity; no balance-only settlement or SWIFT-only payment; currency-safe summaries and NTSW quarantine; knowledge outage restoration and source-unavailable responses; schema candidate promotion; run-addressed artifact generation; small warehouse download fixes. No rewrite, Polars, automatic FX conversion, account creation, upstream-stage completion or UI redesign.

## Exact changes

The list includes every modified original code/config/test file and two new runtime/test files. `gsi/MANIFEST.json` is regenerated from runtime source. Original release logs remain historical; only review/validation logs describe this run.

### `app/warehouse_view.py`

- Finding links: F001, RC01.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/stages/s20_derive.py`

- Finding links: F021, F022, F031, N05.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/MANIFEST.json`

- Finding links: Release packaging / approved cross-cutting snapshot integration.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/core/columns.py`

- Finding links: F030.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/pipeline.py`

- Finding links: F012, F033.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/dataio/reader.py`

- Finding links: N11.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/dataio/merge.py`

- Finding links: F019, F020, N04.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/adapters/a40_oracle.py`

- Finding links: F013, F014.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/adapters/a60_finance.py`

- Finding links: F038, N06.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/adapters/moghavemat.py`

- Finding links: F015, F016.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/adapters/a50_ntsw.py`

- Finding links: F007, F008, F009, F011, N12.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/adapters/base.py`

- Finding links: N01.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/knowledge_desk/query.py`

- Finding links: F034, F035.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/knowledge_desk/indexer.py`

- Finding links: F024.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/knowledge_desk/operational.py`

- Finding links: F001, F018, F034.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/warehouse/bridge.py`

- Finding links: F012, F036, N07.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/warehouse/store.py`

- Finding links: F001, F033, F040, N10.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/warehouse/business_dwh.py`

- Finding links: F002, F003, F005, F017, F018, N02, N09.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/warehouse/reliability.py`

- Finding links: F010, F011, F025, N01, N10.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/factsheet.py`

- Finding links: Release packaging / approved cross-cutting snapshot integration.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/resolve/process_evidence.py`

- Finding links: F004, F005, F039, N03.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/cashflow/dwh.py`

- Finding links: F002, F026, F027, F032, F039.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_sap_semantic_dwh_v29_7_6.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_v29_4_3_relation_health_contract.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_v29_reliability_gate.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_material_supply_html_v29_6_5.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/conftest.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_material_runtime_visible_v29_6_4.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_validation.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_v29_4_2_diagnose_business_semantics.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `requirements.txt`

- Finding links: RC01.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `gsi/warehouse/snapshots.py`

- Finding links: F001, F003.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: New immutable snapshot boundary and published-reader binding.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Consumer API, data grain, missing-value or publication behavior may change; inspect corresponding diff and contract tests.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

### `tests/test_rc_integrity.py`

- Finding links: RC02.
- BEFORE: exact original bytes in uploaded 29.7.6; file-level before/after in review/validation/changes.patch.
- CHANGE: See linked adjudications and exact unified diff; no unlisted file replacement.
- AFTER: RC implementation in this file; limitations are not removed from the Findings Register.
- REGRESSION RISK: Test isolation/fixture intent drift; assertions preserved and scenario inputs made explicit.
- TEST: complete registered runner plus focused tests named in FINDINGS_REGISTER.md; no blanket claim of production-data validation.

## Test fixture changes
Unpublished-build assertions now use administrative db(), preserving the new published-reader contract. Schema test explicitly publishes its baseline. Known-incomplete SAP tests explicitly set that condition. Build assertions use current VERSION. Audit-file test follows run-addressed output. Each pytest gets an isolated operational DWH to avoid prior-suite data answering an empty-KB test. Missing Streamlit is resolved in an isolated QA environment with Streamlit 1.49.1, not by skipping UI tests.

## Reproduction
From extracted gsi_2977_rc1, install requirements.txt and requirements-dev.txt in an isolated Python environment, set GSI_DWH_PATH to a disposable local path, then run `python run_all_tests.py`. Use `python -m pytest -q tests/test_rc_integrity.py` for focused counterexamples. No organization network source is expected in synthetic tests. Do not point regression tests at an operator's real database.


## 2026-09-23 continuation — run_all_tests.py (RC02)
- BEFORE: standalone scripts inherited one GSI_DWH_PATH; pytest fixtures did not apply to them.
- CHANGE: a TemporaryDirectory supplies one DWH path per subprocess suite.
- AFTER: suites cannot read previous independent suites' operational results; explicit multi-run tests retain one database.
- REGRESSION RISK: suite isolation can hide unintended cross-suite dependencies; a separate three-process shared-database architecture probe covers repeated runs, while RC03 remains unresolved.
- TEST: see TEST_AND_INVARIANTS.md and original logs in review/validation.

The earlier shared-DWH verification failure remains in the evidence bundle. No production SQLite schema, gate, or persistence code was changed during this continuation. RC03 is an additional production blocker.

## RC04 — expiry test fixture
BEFORE: near-expiry summary assertion read the wall clock. CHANGE: inject existing dated RuleBooks into the summary call. AFTER: assert both before-expiry warning and after-expiry status. REGRESSION RISK: test patch scope only; actual expiry rules unchanged. TEST: continuation_expiry.log.
