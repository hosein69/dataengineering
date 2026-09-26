# Handoff for Opus — GSI 29.7.7 RC1

**Disposition: REVIEW CANDIDATE ONLY — production sign-off blocked.**

## Inputs and current version
Baseline is the supplied 560-member GSI_V29_7_6_SAP_SEMANTIC_DWH_SMART_CHATBOT.zip. Phase 0's four documents and OPUS_REVIEW are preserved under review/inputs. Runtime VERSION is 29.7.7 with rc1 release channel. No Greenfield rewrite or stack migration.

## Review first
1. FINDINGS_REGISTER.md: independent verdict and closure for all 40 Phase 0 findings, 13 Opus findings and RC01–RC04.
2. TEST_AND_INVARIANTS.md: exact outcomes, failed attempts and coverage limits.
3. review/validation/changes.patch and changed_files.json: code diff against supplied ZIP and file hashes.
4. KNOWN_LIMITATIONS.md: unresolved semantics and validation gaps.

## Architecture changes
Published readers bind to immutable typed per-run semantic snapshots through connection-local views. Working tables rebuild for each run. Raw evidence remains archived. Schema baseline promotion moves with publication. Reports are generated only after checks, under run-addressed paths. Shared Material/Employee dimensions no longer create process identity. PO-side PR/item/material identity is retained; ambiguous REG/ORDER memberships avoid cross-products. Downstream observations survive missing upstream evidence. No account, conversion, payment, settlement or upstream stage was fabricated.

## Adjudication
F006's specific derived-frame allegation is rejected using actual canonical columns; this does not dismiss broader derived-evidence concerns. F014/F029/F032/F037 require source/deployment evidence. Other findings have ACCEPT or ACCEPT_WITH_MODIFICATION verdicts, with implemented/partial/open closure recorded individually. An accepted finding is not automatically resolved.

## Release blockers
- F023: legacy obligation totals still aggregate historical archive versions.
- F028: all_data_sheets still chooses the largest operational sheet; additional sheets may be raw-only.
- F031: legacy financial Unknown/default-zero semantics remain inconsistent.
- F037: application/deployment access-control guarantees are not certified.
- N08: process IDs depend on component membership and are not durable identifiers.
- RC03: a prior synthetic shared-DWH database has genuine index-integrity errors. Three clean repeat processes on a fresh shared DB do not establish root cause. Gate remains unchanged; failed DB was not repaired to obtain a pass.

## Tests
Final full run: 1048 passing checks, zero failures across 73 suites, exit code 0. See TEST_AND_INVARIANTS.md and continuation_final_full.log. Focused tests: 29 passed. Date-boundary suite: 47 checks passed. Shared-database probe: 42 checks per process, three processes, integrity ok after each. Counts overlap with the main runner. Earlier failed logs remain included. No production-data or browser visual acceptance claim.

## Performance
One synthetic 300-row workload measured 1.334 s baseline versus 3.094 s RC for parsing/adapter/process/DWH/query primitives, and database size 11,046,912 versus 22,036,480 bytes. Published query uses the snapshot run + PR index. This is a cost increase, not a speed improvement. It excludes full Streamlit/network end-to-end behavior and does not justify Polars. Production-scale retention, concurrency and memory measurements remain necessary.

## UI/UX changes
Warehouse CSV filenames use frame identity; prepared backup bytes persist across reruns with a namespaced state key. Download click avoids unnecessary rerun. Streamlit minimum aligns with width API use. Semantic views show published as-of context; operational backend failure is distinguished from no evidence. See UI_UX_TECHNICAL_NOTES.md. No full navigation redesign; real browser media-link stability remains unverified.

## Open design questions
What are authoritative full/delta and effective-date contracts per source? Which rows represent event identity versus snapshot observation? What is the approved Oracle inventory grain and Clearance sheet/direction contract? How should stable case aliases survive changing components? Which source wins each conflicting field? What are retention and ACL policies? How should legacy totals migrate to published native commitment membership without guessing current archive versions?

## Suggested Figma exploration
Process Cockpit case detail and evidence gaps; Warehouse Relation Explorer ambiguity; Cash Flow event versus measurement display; Chatbot source/as-of/conflict drawer; PR→ORDER→REG→Shipment→Clearance breadcrumbs preserving case context. Keep source coverage distinct from process failure and show currency separately from amount.

## Acceptance recommendation
Review the implemented minimum changes and run the included tests. Keep deployment blocked until the listed blockers and relevant source contracts are resolved. Do not turn a green synthetic regression run into financial or operational sign-off.

## Changed files

- `ARCHITECTURE_BASELINE.md`
- `CHANGELOG.md`
- `DECISION_LOG.md`
- `FINDINGS_REGISTER.md`
- `HANDOFF_FOR_OPUS.md`
- `IMPLEMENTATION_REPORT.md`
- `KNOWN_LIMITATIONS.md`
- `README.md`
- `TARGET_ARCHITECTURE.md`
- `TEST_AND_INVARIANTS.md`
- `UI_UX_TECHNICAL_NOTES.md`
- `app/warehouse_view.py`
- `gsi/MANIFEST.json`
- `gsi/adapters/a40_oracle.py`
- `gsi/adapters/a50_ntsw.py`
- `gsi/adapters/a60_finance.py`
- `gsi/adapters/base.py`
- `gsi/adapters/moghavemat.py`
- `gsi/cashflow/dwh.py`
- `gsi/core/columns.py`
- `gsi/dataio/merge.py`
- `gsi/dataio/reader.py`
- `gsi/factsheet.py`
- `gsi/knowledge_desk/indexer.py`
- `gsi/knowledge_desk/operational.py`
- `gsi/knowledge_desk/query.py`
- `gsi/pipeline.py`
- `gsi/resolve/process_evidence.py`
- `gsi/stages/s20_derive.py`
- `gsi/warehouse/bridge.py`
- `gsi/warehouse/business_dwh.py`
- `gsi/warehouse/reliability.py`
- `gsi/warehouse/snapshots.py`
- `gsi/warehouse/store.py`
- `requirements.txt`
- `run_all_tests.py`
- `tests/conftest.py`
- `tests/test_material_runtime_visible_v29_6_4.py`
- `tests/test_material_supply_html_v29_6_5.py`
- `tests/test_rc_integrity.py`
- `tests/test_sap_semantic_dwh_v29_7_6.py`
- `tests/test_v26_20_2_engine_hardening.py`
- `tests/test_v29_4_2_diagnose_business_semantics.py`
- `tests/test_v29_4_3_relation_health_contract.py`
- `tests/test_v29_reliability_gate.py`
- `tests/test_validation.py`
