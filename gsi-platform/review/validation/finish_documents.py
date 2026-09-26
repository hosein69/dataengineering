from pathlib import Path
import json,zipfile,hashlib,difflib,shutil
root=Path('/workspace/scratch/58b6b78e0919');src=root/'src'
with (src/'FINDINGS_REGISTER.md').open('a') as f:f.write('''

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
''')
with (src/'DECISION_LOG.md').open('a') as f:f.write('\n2026-09-23: ACCEPT isolated DWH per standalone suite (RC02). ACCEPT continued publication blocking for unresolved SQLite corruption (RC03). Three clean repeated architecture runs do not establish root cause. Production sign-off remains blocked.\n')
with (src/'KNOWN_LIMITATIONS.md').open('a') as f:f.write('\n## Continuation blocker RC03\nA previously used synthetic regression database has failed SQLite index integrity. Three fresh shared-database architecture runs are clean, but cause remains unknown. Suite isolation is not a corruption fix. Do not promote this RC to production until investigated.\n')
with (src/'IMPLEMENTATION_REPORT.md').open('a') as f:f.write('''

## 2026-09-23 continuation — run_all_tests.py (RC02)
- BEFORE: standalone scripts inherited one GSI_DWH_PATH; pytest fixtures did not apply to them.
- CHANGE: a TemporaryDirectory supplies one DWH path per subprocess suite.
- AFTER: suites cannot read previous independent suites' operational results; explicit multi-run tests retain one database.
- REGRESSION RISK: suite isolation can hide unintended cross-suite dependencies; a separate three-process shared-database architecture probe covers repeated runs, while RC03 remains unresolved.
- TEST: see TEST_AND_INVARIANTS.md and original logs in review/validation.

The earlier shared-DWH verification failure remains in the evidence bundle. No production SQLite schema, gate, or persistence code was changed during this continuation. RC03 is an additional production blocker.
''')
(src/'CHANGELOG.md').write_text('''# 29.7.7 RC1 — review candidate

Baseline: supplied GSI 29.7.6 ZIP. Incremental changes only.

- Bind semantic reads to immutable per-run published snapshots; preserve old run evidence after blocked runs.
- Preserve duplicate/orphan observations; separate process identity from shared Material/Employee dimensions.
- Correct PO-side PR/material lineage and ambiguous registration-hub joins; avoid null-key matching.
- Remove balance-only settlement, SWIFT-only payment and document-receipt financial completion inference.
- Quarantine conflicting NTSW commitment rows; preserve independent allocation/licence processing.
- Promote schema baselines only on publication; generate reports under run-specific paths after gates.
- Improve operational backend error reporting and knowledge-source outage handling.
- Stabilize warehouse downloads, clarify published as-of state and require compatible Streamlit APIs.
- Correct legacy test fixtures; isolate standalone suite databases.

Not production approved. F023, F028, F031, F037, N08 and RC03 remain blockers; additional partial findings are detailed in FINDINGS_REGISTER.md. The SQLite incident remains unresolved. No claim of improved performance or complete financial/source contracts.
''')
