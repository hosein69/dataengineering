# Known limitations — production sign-off withheld

1. F023: legacy fx_obligation totals aggregate historical archive without certified current membership. Do not use as current financial truth.
2. F028: all_data_sheets selects largest sheet; secondary operational sheets remain raw-only.
3. F031: legacy financial default-zero/fillna paths remain; unknown/zero parity is not complete.
4. N08/F004: component-based PC IDs are not stable durable identities; PR/REG shared-component semantics remain open.
5. F037: endpoint/application authorization, default host/CORS and deployment/file ACL scope are not certified.
6. Snapshot storage roughly doubles business data for a run; no retention, compact/incremental strategy or production-scale concurrency benchmark. Pre-RC published histories may already be irrecoverably overwritten; archived run-frame replay is needed. Rebuilding the same already-captured run is refused rather than overwriting history.
7. Supplier/Plant/Package remain payload-level attributes; full conformed dimensions and workflow event identity have not been added. Equal-date conflict selection and deletion/delta semantics require source contracts.
8. Raw archive is preserved, but standardized ordinal is not a physical Excel address. Derived representations may still add observation/relationship counts across frames. Exact per-event deduplication is not solved everywhere.
9. Full raw-header mandatory contracts, source coverage inventory, partial-scan KB outages and governance authority unification remain incomplete. Source-origin metadata does not yet fix every stale measurement date.
10. Operational chatbot is improved, but does not yet give a complete PR-to-settlement process dossier with every requested stage and conflict. KB entailment/effective policy and external LLM grounding remain open.
11. Browser visual inspection, real media-download clicks, enterprise network/Outlook COM, actual SAP/NTSW/customs reconciliation and production-scale migration were not executed. AppTest is useful runtime coverage, not a pixel/browser acceptance review.
12. Performance sample is synthetic and small. Additional CPU/storage cost is measured, not hidden. No financial business-value estimate or production throughput claim is made.

## Continuation blocker RC03
A previously used synthetic regression database has failed SQLite index integrity. Three fresh shared-database architecture runs are clean, but cause remains unknown. Suite isolation is not a corruption fix. Do not promote this RC to production until investigated.
