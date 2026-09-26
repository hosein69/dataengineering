# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# Handoff for Opus — GSI 29.7.8 RC2

Disposition: finalized review package; production sign-off withheld.

Inputs: RC1 29.7.7 package, OPUS_FINAL_REVIEW.md, exact opus_rc1_fixes.patch and the supplied GSI source profiler tool/config. Real corporate workbooks and generated profiler evidence were not supplied.

RES-1, RES-2, RES-3 patch applied after clean dry run. Numeric unknown flags additionally recognize invalid and nonfinite inputs. New financial presentation and safe published-source handling; source/status changes described in DEFENSIBLE_CHANGES_FA.md. Ten new focused tests added.

Final full regression: 1058 passing, zero failures. The earlier RC2 run was 1057 passing/1 failing because the new unknown flag used a helper returning NaN rather than None; corrected to decimal_text, then all suites rerun successfully. Both logs preserved. Counts include overlapping checks across legacy runners, not necessarily unique pytest functions.

Review SOURCE_CONTRACT_AUDIT_FA.md, CONFIRMATIONS_AND_LIMITS_FA.md and KNOWN_LIMITATIONS.md. Source-profiler heuristics are not canonical contracts. The 17 production workbooks remain a required validation gap. No claim that all reporting or all deduplication is solved.

Figma whoami returned UNAUTHORIZED/reauthentication required; no Figma file was created. Browser-checked financial HTML is synthetic QA. Streamlit evidence, where included, is an empty published-source scenario. No live corporate data acceptance.

Changes from RC1, SHA-256 file inventory, final/failed logs and source audit are in review/rc2_validation. RC1 detailed adjudication is preserved under review/rc1_documents and review/validation.
