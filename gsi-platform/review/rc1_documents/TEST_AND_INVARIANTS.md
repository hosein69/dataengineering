# TEST_AND_INVARIANTS — 29.7.7 RC1

This file supersedes historical release-test claims. Original Phase 0 invariants are preserved under review/inputs. Tests use synthetic/sample data, not production business reconciliation.

## Reproduction

Install requirements.txt and requirements-dev.txt in an isolated Python environment. From the package root run `python run_all_tests.py`. Each of 73 suites runs in a subprocess with a disposable DWH; explicit multi-run tests share their own database. The runner uses pytest for pytest-style suites and standalone entrypoints for legacy suites. Counts combine legacy checks and test cases; they are not all distinct pytest functions.

Focused counterexamples: `python -m pytest -q tests/test_rc_integrity.py`.
Date boundary suite: `python tests/test_v26_20_2_engine_hardening.py`.
Environment: Python 3.12.14, SQLite 3.53.1, pandas 2.2.3, NumPy 2.3.5, Streamlit 1.49.1, pytest 9.1.1, openpyxl 3.1.5.

## Exact results and scope

- Earlier full execution: 1042 passing checks, zero failures (rc_final_full.log). Superseded; not the final acceptance result.
- Earlier shared-DWH verification: 859 passing checks, seven failed checks/runner errors across six suites; SQLite INTEGRITY_CHECK blocked publication (release_verification.log).
- Continuation initial full run: 1047 passing checks, one failure caused by a wall-clock expiry assertion (continuation_full.log). Corrected under RC04 without changing production dates.
- Focused continuation: 29 passed in 2.13 seconds (continuation_focused.log); these are included in the full runner and must not be added to its total.
- Expiry suite after RC04: 47 passing checks, zero failures (continuation_expiry.log), including before/after-date summary assertions.
- Three separate processes using one fresh shared DWH: 42 architecture checks passed each time; integrity_check = ok after each (repeated_architecture_results.json). Additional probe, not proof the earlier corruption is fixed.
- Python compileall completed without errors; runtime manifest verify returned no issues.
- Final full-run result: see final line below and continuation_final_full.log.

## Invariants and contract evidence

| Contract | Evidence / test | Limit |
|---|---|---|
| Blocked R2 cannot change published R1 | test_blocked_run_isolation | No production concurrency stress claim |
| Omitted current facts preserve historical snapshot | test_published_omission_preserves_history | Full/delta policy unresolved |
| Unpublished evidence is not operational truth | test_no_publication_no_public_evidence | Legacy archive consumers remain separate |
| Replays do not accumulate relation counts across runs | test_replay_relation_counts | Cross-frame derived multiplicity remains open |
| Shared dimensions do not merge independent cases | test_shared_dimensions_do_not_merge | Durable case IDs unresolved |
| Duplicate/orphan observations survive | test_duplicate_orphan_preservation | Not every finance path is fixed |
| Downstream evidence survives upstream gap | test_downstream_gap | No fabricated upstream completion |
| Balance is not settlement; SWIFT is not payment | test_balance_not_settlement, test_swift_not_payment | Legacy unknown/zero fields remain unresolved |
| Empty composite keys never match | test_null_and_delimiter_keys | Other cardinality findings may remain partial |
| PO-side identity and conflict preserved | test_po_own_identity | Real export reconciliation pending |
| Ambiguous hub avoids Cartesian pairings | test_no_hub_product | Singleton path is derived |
| Schema rejection does not promote baseline | test_blocked_schema_does_not_become_baseline | Mandatory raw-header coverage incomplete |
| No silent successful publish on core corruption | sqlite_incident.json and failed-run log | Root cause unresolved, RC03 blocker |

Other registered suites cover legacy/new SAP, cashflow, population, warehouse, process, chatbot, UI/AppTest, cache/read isolation and reliability. A passing suite is not a blanket certification of every requested scenario. Full production SAP/Oracle/NTSW/clearance contracts, browser media downloads, organization ACLs, and real financial reconciliation remain unverified.

## Final full-run result — 2026-09-23

جمع کل: 1048 تست موفق | 0 ناموفق

Runner exit code: 0. All 73 discovered suites completed. See continuation_final_full.log. This result does not close the documented release blockers.
