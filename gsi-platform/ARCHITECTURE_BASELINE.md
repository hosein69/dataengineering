# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# Architecture — GSI 29.7.8 RC2

RC1 published-run/snapshot architecture remains. Financial views now read the published DWH by default, with scope resolved against the same loaded frames. Source errors are distinct from no publication. Optional user-ledger reports remain separate. See review/rc1_documents/ARCHITECTURE_BASELINE.md for baseline architecture and KNOWN_LIMITATIONS.md for unresolved issues.
