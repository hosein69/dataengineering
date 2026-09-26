# UI_UX_TECHNICAL_NOTES — 29.7.7 RC1

No visual redesign. Existing page/navigation structure retained.

| Area | Before | Change / after | Validation / remaining |
|---|---|---|---|
| Streamlit API | Existing code used width while dependency allowed 1.35 | Minimum 1.49; existing use_container_width audit has no occurrences | Streamlit 1.49.1 QA; official API reference below |
| CSV download | Constant warehouse_table.csv; rerun | Frame-ID filename, namespaced key, on_click=ignore | AST logic test; actual media-server click not browser-tested |
| Backup download | Only rendered inside one-shot preparation button | Store prepared bytes under warehouse_backup_bytes, render on later reruns, ignore click rerun | Prepared backup remains that prepared version; generate again for newer DB |
| Warehouse semantic view | Working mutable DWH exposed as current | Published read transaction; visible As-of run | Legacy unbuilt semantic state requires rebuild |
| Hub | N×M REG/ORDER rows looked like relations | Separate ambiguous memberships with null opposite key | Singleton is still a derived path, not native co-observation |
| Chatbot | Workflow rows labelled events; lexical item ordering | Observation wording, evidence-date PR selection, structured item provenance | Full source/conflict/current-stage visual rendering still incomplete |
| Error distinction | DB exception became no evidence | SOURCE_UNAVAILABLE status for operational backend errors | Technical diagnostics retained in server errors; all clients not visually tested |
| Empty states | Existing no-evidence caveat | Retained; no upstream completion inferred | UI-wide wording audit/consistent badges remains partial |

Official API checked: https://docs.streamlit.io/1.49.0/develop/api-reference/widgets/st.download_button — width and on_click="ignore". This reference was used for API compatibility, not as validation of server media stability.

Not delivered: full PR→ORDER→REG→Cashflow→Shipment→Clearance context-preserving navigation, global stale-filter redesign, all debug-column defaults, all badge semantics, or visual Figma design. These remain explicit review opportunities, not hidden implementation claims.

Figma exploration candidates: Process Cockpit case detail and evidence gaps; Warehouse Relation Explorer ambiguity display; Cash Flow event/measurement comparison; Chatbot source/as-of/conflict drawer; material/order navigation breadcrumbs. Use consistent source/coverage vocabulary and preserve explicit currency columns. No Figma account access was needed for this technical cleanup.
