# DECISION_LOG — 29.7.7 RC1

| Decision | Status | Reason / consequence |
|---|---|---|
| Preserve modular stack | ACCEPT | No production bottleneck evidence justifies Polars or rewrite |
| Typed snapshots with connection-local published views | ACCEPT | Minimum cross-consumer isolation while retaining existing table contracts; extra storage/read setup cost |
| Rebuild current projection each run | ACCEPT_WITH_MODIFICATION | Stops old facts and count accumulation; absence does not mean deletion; delta sources need explicit policy |
| Do not certify pre-RC mutable state as old published history | ACCEPT | Historical payload may already have been overwritten; source replay required |
| Run-addressed artifacts after checks | ACCEPT | No old official-file overwrite; unreferenced failed-run files may remain |
| Schema candidate promotion during pointer transaction | ACCEPT | Failed runs cannot establish future baseline |
| CORE process summary gate | ACCEPT | Tolerant producer failure must not silently disable integrity |
| Remove Material/Employee case identity | ACCEPT | Shared dimension is not process-case identity; stable aliases deferred |
| Unknown mixed-currency summary, native ledger unchanged | ACCEPT | Avoid changing one-to-one compatibility join to one-to-many |
| Quarantine ambiguous commitment snapshots | ACCEPT | No last-row business truth chosen without effective version |
| Keep Oracle max with field provenance | ACCEPT_WITH_MODIFICATION | Tests/code document policy; source bucket semantics not proven |
| Reject specific F006 main-derived example | REJECT | Canonical keys required by alleged relationship are absent; broader derived-frame concern remains separate |
| Do not broaden REG pattern from speculation | DEFER_NEEDS_DATA | keys.yaml currently defines 8-digit registration; real exceptional keys needed |
| Fix stale test fixtures, not production config to satisfy them | ACCEPT | Tests explicitly establish known-incomplete scenario and isolated DWH |
| Numeric runtime VERSION=29.7.7; RELEASE_CHANNEL=rc1 | ACCEPT | Existing consumers parse numeric version components |

The original Phase 0 decisions remain in review/inputs, as historical review inputs. No approval, policy, relationship, currency conversion or financial date was invented. An accepted defect can remain open; closure is explicit in the Findings Register. This package is a review candidate, not production sign-off.

2026-09-23: ACCEPT isolated DWH per standalone suite (RC02). ACCEPT continued publication blocking for unresolved SQLite corruption (RC03). Three clean repeated architecture runs do not establish root cause. Production sign-off remains blocked.
