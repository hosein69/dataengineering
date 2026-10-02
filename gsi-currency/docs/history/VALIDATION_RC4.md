# GSI 29.8.0 RC4 validation

Full runner (`python run_all_tests.py`): **1136 passed, 0 failed.**
RC3 baseline, reproduced independently on the same machine before any change:
**1089 passed, 0 failed.** The 47 added tests all lock a defect that was
measured on real output, not a preference.

New suites:

| file | tests | what it locks |
|---|---|---|
| `tests/test_opus_rc4_output_integrity.py` | 15 | HTML keeps every row; declares every column it left out; discloses the `fx_ledger` cap; drops the false Excel claim; OF is neither rejected wholesale nor fanned out; empty sections and sheets state their reason; the financial report uses the package font stack; the content manifest does not import data-quality vocabulary into an operational view |
| `tests/test_opus_rc4_warehouse_reset.py` | 7 | reset refuses without `--yes`; refuses a non-GSI database; backs up first; clears runs, frames, frame cache and writer lock; the warehouse works again immediately; the CLI reports what it removed |
| `tests/test_opus_rc4_dashboard_startup.py` | 7 | the dashboard reads the published snapshot before rerunning the pipeline; the explicit button still forces a fresh run; caches are bounded; no eager `dict(extras)`; lazy scoping is still enforced |
| `tests/test_opus_rc4_process_views.py` | 18 | cumulative flow counts a case once per stage and never decreases; throughput counts only closed cases; aging lists only open cases; percentiles are withheld below three observations; rework and handoff read the real columns; every metric degrades to an empty frame; every view states the limit of its claim; the new Kanban lanes separate blocked from ready |

One existing test was deliberately rewritten:
`test_cashflow_v29_7.py::test_of_missing_payment_ids_never_becomes_cash`.
Its old assertion (`events` must be empty) rejected 100% of the real OF
workbook. It now asserts the invariant its own name states: an OF row may be
source evidence but must never produce a bank account, an account movement or a
balance, and `ACCOUNT_DETAIL_GAP` must be recorded.

Measured on real artifacts rather than asserted:

| claim | evidence |
|---|---|
| HTML keeps every row, 18 of 561 columns | full pipeline run, `REPORT_META` |
| OF produced 0 accepted events in RC3 | `samples/cashflow/attached_OF_review/` shipped in RC3 |
| OF produces 67 accepted events in RC4 | `samples/cashflow/attached_OF_review_rc4/` |
| registration value was 5×–8× inflated | same workbook, `summary` vs distinct `CB Value` |
| 8 of 19 cash-flow tabs empty on a healthy run | synthetic end-to-end run against the published DWH |
| reset then rebuild leaves `integrity_check: ok` | 2 runs / 126 frames → 0 → 1 run / 63 frames |
| published snapshot read is 0.005 s vs 3.54 s | `time.perf_counter` around `last_report` and `Pipeline().run` |

No production-data certification. Every number above comes from the OF workbook
attached inside the RC3 package or from generated data carrying the real
production headers. The 631,576-row corporate workbooks were not available here.
