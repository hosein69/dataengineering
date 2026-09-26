# Known limitations — GSI 29.7.8 RC2

Production sign-off remains withheld. The package is a complete review delivery, not a certification of corporate data.

- F023: legacy obligation totals can aggregate historical archive versions.
- F028: largest-sheet selection can omit secondary operational sheets from standardized processing.
- F031: unknown/default-zero semantics are not consistent in every legacy report. New companion flags and degraded checks expose selected cases; they do not fix all calculations.
- F037: deployment and application authorization are not certified.
- N08: component-derived process IDs are not durable case identifiers.
- RC03: earlier synthetic shared-DWH SQLite index corruption remains unexplained. Isolated passing suites and clean repeats do not establish root cause.
- RES-4: ORC_BUYER producer exclusion versus authority candidacy remains unresolved.
- RES-5: the 17 real workbooks needed for production smoke/reconciliation were not provided in this work session.
- F019/N04: early RHS deduplication can conceal join-cardinality evidence in legacy paths.
- RES-6: operational questions containing IDs can skip knowledge-document retrieval.
- Financial snapshot measurements can still use report as-of as observed_at. This is not verified source observation time.
- Source-profile heuristics confuse REG_FILE/REG and date headers; identical relationship columns can raise an AttributeError. The supplied tool is included unchanged and cannot establish canonical authority.
- Same-case licence status history is preserved and flagged, not resolved by assuming status priority. Equal-date conflicting allocation requests are quarantined; this policy does not settle all source lifecycle semantics.
- Full event deduplication, deletion/delta semantics, retention, real production concurrency, enterprise network/Outlook integration and migration remain unverified.
- Figma returned UNAUTHORIZED requiring reauthentication. No Figma design file was created or accepted.

See review/rc1_documents/KNOWN_LIMITATIONS.md for historical details. Its statement that no browser inspection was performed is superseded for the RC2 exported financial HTML and the explicitly recorded Streamlit check only.
