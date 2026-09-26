# Current release: GSI 29.7.9 RC3

Superseding scope: SOURCE_ROADMAP_FA.md and UPDATED_CODE_AND_REPO_REVIEW_FA.md. New evidence supplies 41 profiles and 1089 sampled rows, not full workbooks. F023 is partially mitigated (totals scoped; legacy chain/coverage still archive-wide). F028 clearance largest-sheet selection is replaced with contracted-header selection. No new UI or external AI dependency. Current validation: review/roadmap/final_full_regression.log. Historical RC2 assertions below retain their original scope/date.

---

# Financial UI/UX — 29.7.8 RC2

Shared Streamlit renderer covers standalone, dashboard and studio financial workspace. Header identifies published source/run and date; optional imports sit in a collapsed section. Four tabs separate flow, settlement/reconciliation, provenance and quality. Case/currency filters precede details; unknown amounts use a dash; no cross-currency grand total. Scope changes invalidate cached results; source failures clear old results.

Offline HTML includes embedded styles/JS and Excel bytes, keyboard RTL tab navigation, Persian digit search, status badges, mobile navigation and scrollable detail tables. User content is escaped. Download names carry run/date. Synthetic previews and browser checks are included.

Figma connection was attempted and returned UNAUTHORIZED requiring reauthentication. No Figma design acceptance, file or link exists. Styling was implemented in application code. Only financial views were redesigned; other product pages retain their existing design.
