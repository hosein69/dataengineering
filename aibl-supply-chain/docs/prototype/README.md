# Process Explorer prototype — Python/Streamlit implementation

This is a **real, runnable fork of `process-mining-ui-kit`** (the package reviewed in
`../PROCESS_MINING_UX_FIGMA_REVIEW.md`), implementing the Phase 2/3 recommendations as actual
Python/Streamlit code — not a static mockup. Every file under `process-mining-ui-kit/` keeps the
original module paths and conventions (`pm_ui.tokens`, `pm_ui.blocks`, etc.) so the diff can be
reviewed and merged directly into the real package.

## Run it

```bash
cd process-mining-ui-kit
pip install -r requirements.txt
streamlit run app.py
```

## What's new here, and why

| Requirement | File(s) | What it does |
|---|---|---|
| Frequency ⇄ Performance modes, deviation dashing, graded simplification | `pm_ui/charts/process_flow.py` | `render_process_flowgraph(..., mode=, abstraction=, highlight_edges=)`. Replaces the old hard `ValueError` at 60 activities with a 0–100 slider (default 100 = full precision) that always reports "shown N of M" — nothing is hidden without saying so. |
| Restored Variant Explorer | `pm_ui/charts/variant_explorer.py` | The variant list the legacy `aibl` tab had; picking a variant highlights its exact path on the flow graph via `highlight_edges`. |
| Conformance visible next to the map, not a separate tab | `pm_ui/components.py` (`render_conformance_tile`, `render_root_cause_bars`) | Fitness % tile + differential root-cause bars, wired as new block types (`conformance`, `root_cause`) in `pm_ui/blocks.py` and `pm_ui/layout/presets.py`. |
| **Drag-and-drop** layout reordering | `pm_ui/layout/dragdrop.py` + `pm_ui/layout/dragdrop_frontend/index.html` | A hand-rolled, zero-dependency Streamlit custom component (raw `postMessage` protocol) — no npm/pip package, so it still works fully offline. See the note below; it replaces the `streamlit-sortables` dependency `requirements.txt` used to suggest. |
| **Item removal** | `pm_ui/layout/engine.py` (`remove_block`, `add_block`) | ✕ button per block in the sidebar; removed blocks can be added back from a dropdown — nothing is destroyed, just unrendered. |
| **Output customization** | `app.py` sidebar | Drag-to-reorder, ▲/▼ (keyboard/no-mouse fallback), ✕ remove, ➕ add — all persist through the existing `save_layout`/`load_layout` JSON mechanism. |
| **Outlook HTML size limit** | `pm_ui/export/html_report.py` (`MAX_OUTLOOK_BYTES`, `HtmlExportResult`) | `build_report_html(...)` now measures its own output and, if it exceeds 100 KB, trims the kanban summary then the route table (in that order), naming what it trimmed — never a mid-tag truncation. `app.py`'s sidebar shows a ✅/⚠ byte count live. |

## A real bug found and fixed along the way

Streamlit's custom-component protocol has an **undocumented requirement**: every `postMessage`
sent from a component's iframe must include `isStreamlitMessage: true` at the top level, or
Streamlit's `ComponentRegistry.onMessageEvent` silently drops it — no console warning, no error,
nothing. Without this flag the component renders (parent→child still works) but can never send a
value back (child→parent silently fails). This is why the drag-and-drop component in
`dragdrop_frontend/index.html` sends every message through one `post()` helper that always sets
that flag. Verified with a headless Chromium harness (Playwright) end-to-end, including a
loop-guard fix: Streamlit persists a component's last submitted value across reruns, so
`app.py` only applies a reorder when it actually differs from the current layout — otherwise
`if new_order:` alone would `st.rerun()` forever.

## What's unchanged

`pm_ui/tokens.py`, `pm_ui/theme.py`, `pm_ui/persian.py`, and every existing chart/component not
listed above are byte-identical to the original — this is an additive patch, not a rewrite.
