# Findings register — 29.7.8 RC2

The full RC1 per-finding adjudication remains in review/rc1_documents/FINDINGS_REGISTER.md and is inherited unchanged except below.

| Finding | RC2 outcome |
|---|---|
| RES-1 | Implemented: SWIFT_SENT accepted in stage/provider registry; regression tested; not equated with payment. |
| RES-2 | Mitigated: six companion unknown flags plus DEGRADED check; invalid/nonfinite protected. F031 remains open globally. |
| RES-3 | Implemented: FIN_RECEIPT_DATE declared unmeasured; coverage diagnostics. No date fabricated. |
| FIN-01 | Implemented: published DWH default; unresolved scope stays empty; no intermediate fallback. |
| FIN-02 | Implemented: corrupt SQLite/payload surfaces source failure. |
| ID-01 | Implemented: registration headings excluded from ORDER matching. |
| STATUS-01 | Implemented within NTSW adapter: licence status conflicts preserved, commitment/status and tied request conflicts quarantined. Broader lifecycle semantics remain open. |
| UI-01 | Code/HTML redesign implemented and synthetic browser tested; Figma editing blocked by reauthentication. |
| RES-4/5/6 | Open; see KNOWN_LIMITATIONS.md. |

F023, F028, F031, F037, N08, RC03 and F019/N04 remain open. No clean test run closes an untested production-data finding.
