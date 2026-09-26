# 29.7.7 RC1 — review candidate

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
