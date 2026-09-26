# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# Validation — 29.7.8 RC2

- `python run_all_tests.py`: final 1058 passing checks, zero failed; final_full_regression.log.
- New targeted tests: 10 passed; final_contracts.log. Includes identifier separation, licence status conflicts, commitment status quarantine, allocation input-order invariance, exact duplicate collapse, newer-date selection, empty unresolved scope, corrupt DB handling, SWIFT registry and unknown values.
- Earlier complete run: 1057 pass / 1 fail; full_regression.log retained. Incorrect numeric helper corrected before final complete rerun.
- Exported HTML: desktop, case filter, settlement tab, embedded Excel download, RTL arrow navigation, Persian digit search, mobile 390px overflow check; BROWSER_RESULTS.json and screenshots. Synthetic data only.
- Streamlit: see STREAMLIT_BROWSER_RESULTS.json if present for actual run scope. No real source-data acceptance claim.
- Source audit: SOURCE_AUDIT.json and SOURCE_CONTRACT_AUDIT_FA.md. Actual corporate source workbooks supplied: false.

Evidence resides under review/rc2_validation. The test suite uses disposable DWH instances. It does not explain RC03, certify production concurrency, or resolve all legacy deduplication/accounting problems. Historical RC1 tests remain in review/validation and review/rc1_documents.
