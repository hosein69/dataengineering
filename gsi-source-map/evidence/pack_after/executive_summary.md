# Executive Summary — GSI Source Evidence Pack

Tool `2.0.0-reviewed` · generated 2026-09-23T08:20:23

> ✅ All configured sources profiled.

- Configured sources: **6**
- Profiled frames/sheets: **8**
- Total native rows scanned: **14**
- Same-role key conflicts found: **3**
- Cross-source key roles: **BL, MATERIAL, NATIVE_ROW_ID, ORDER, PR, PR_ITEM, REG**

## Source coverage

| Source | Status | Frames | Rows | Detail |
| --- | --- | --- | --- | --- |
| SAP | PROFILED | 1 | 3 |  |
| Commercial_Expert | PROFILED | 1 | 2 |  |
| NTSW | PROFILED | 3 | 6 |  |
| Oracle | PROFILED | 1 | 1 |  |
| FX_Transactions | PROFILED | 1 | 1 |  |
| Customs | PROFILED | 1 | 1 |  |

## Read order
1. model_context_pack.md
2. process_key_index.json
3. coverage_report.json
4. Relevant sample CSVs
5. Relevant schema JSONs

Heuristic grain and join findings are not business truth until confirmed by contracts or code. A shared role name never makes two identifiers the same business entity.
