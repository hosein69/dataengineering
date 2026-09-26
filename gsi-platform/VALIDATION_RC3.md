# GSI 29.7.9 RC3 validation

Final full runner: 1089 passed, zero failures. Targeted roadmap + uploaded-patch tests: 31 passed. Original uploaded-patch suite independently: 12 passed unchanged. No production-data certification.

The first integration run had 1078 passing / 6 failures: source-fixture contact addresses, three README claim checks and two legacy obligation fixtures that had no selected run. Contact addresses were removed from the reusable fixture (the original input remains unchanged); documentation restored factual runtime counts; obligation precision/currency tests now explicitly select their fixture run. An intermediate full run passed 1088 before final downstream fixes. Final complete log is review/roadmap/final_full_regression.log.

Scope tests cover actual negative GR returns, ambiguous SAP reference preservation, native SAP sheets, source discovery, mixed FX schemas/currencies, planned purchase exclusion, funding amount unknown, actual credit SWIFT fields, licence/amendment status, clearance headers, missing-run isolation and PO↔BL persistence.

All 41 sheet profiles have dispositions in SOURCE_ROADMAP_FA.md. There are 1089 source samples representing profile statistics over 631576 rows; the complete workbooks were not available. Interface/styling files and requirements are byte-identical to the previous local RC2; no repository code was copied.
