# Process Intelligence — UX/UI & Figma Design Review

**Scope of this review:** the process-mining surface of the platform — the module that turns a case/activity/timestamp event log into a directly-follows graph, conformance check, and case/variant drill-down. In the codebase this spans two generations that currently coexist:

- **Legacy tab** (`aibl-supply-chain/app/process_view.py`, `aibl/stages/s85_conformance.py`) — the seven-view "Process" tab: Summary, Bottleneck transitions, Cycle-time distribution, **Variant explorer**, Conformance, Root-cause, Case timeline.
- **New engine + kit** (`gsi/process_intelligence/`, `process-mining-ui-kit/pm_ui/`) — a rebuilt, design-token-driven flow-graph renderer with a live Figma-synced design system, currently exposed as three views: *Status & Action*, *Process Path*, *Handoff Between Units*.

That split — not a generic "DFG vs. BPMN" question — is the real state of the product, and it drives every recommendation below.

**One correction up front:** the request template this review responds to asked for the package's tech stack, users, and current visualizations to be filled in. Those fields were left as placeholders, and the attached package turned out to be this event-log/import-clearance process engine rather than a generic PM4Py/BPMN tool. Everything below is grounded in what the code actually does, not the template's assumptions — flag if a different package was intended.

---

## Phase 1 — Evaluation of the Current State & Standards Check

### 1.1 What the process model actually is, and why BPMN/Petri nets are the wrong bar

The discovered model is a **directly-follows graph (DFG)**: nodes are observed activities, edges are `A→B` transitions weighted by unique-case count and occurrence count, with median/P90 hours per edge (`gsi/process_intelligence/core.py:220-236`). This is the correct family of model for *discovered* (not hand-drawn) process behavior — the same choice Disco, Celonis Process Explorer, and ProM's Heuristics/Fuzzy Miner make. BPMN 2.0 and Petri nets encode **prescriptive, deterministic control flow** (explicit gateways, formal firing rules); forcing a mined, probabilistic DFG into that notation manufactures a precision the data doesn't have — routes that occur twice look identical to routes that occur two thousand times once you round them into a gateway diagram. **Keep the DFG. Do not chase BPMN compliance for the discovered model itself** — that would be a regression, not a standard upgrade.

The correct standards target is the **IEEE Task Force on Process Mining Manifesto** (2011) and the process-mining literature's own visual conventions (Disco/Celonis-style frequency & performance views), not BPMN. Scored against the Manifesto's guiding principles:

| Guiding principle | Current state |
|---|---|
| GP1 — event logs should be treated as first-class citizens | Strong. Strict event contract (`_CASE_KEY`, `ACTIVITY_FA`, `EVENTTIME`), rejects ambiguous simultaneous events unless `_SORTING` disambiguates them, validates ISO-8601, caps at 200k events (`core.py:163-198`). |
| GP2 — log/model quality should be checked before conclusions are drawn | Partial. Input validation is excellent; but there is no headline **fitness/conformance %** surfaced next to the graph — conformance lives in a separate table, not as a trust signal on the model itself (see 1.3). |
| GP3 — concept drift should be handled | Not addressed; out of scope for this review unless the team wants it. |
| GP4 — events should be related to model elements to allow for reasoning | Strong. Evidence rows carry `source_row` back to the exact input line (`core.py:114-115, 247-250`); nothing is asserted without a pointer back to its source. |
| GP5 — models should treat concurrency, not just sequence | The DFG doesn't distinguish "always A then B" from "A and B happen in either order across cases" — a real gap if the process has parallel branches (e.g., documents prepared while FX is allocated). Worth a note in the model, not necessarily a fix now. |
| GP8 — simplified models don't have to be more accurate | The 60-activity hard cap (`core.py:196-198`, raises `ValueError`) violates this in spirit: it fails closed instead of *simplifying with the user's consent*. This is the single highest-leverage fix — see 2.3. |

### 1.2 Visual language of the DFG itself

`process-mining-ui-kit/pm_ui/charts/process_flow.py` is a genuinely well-built hand-rolled SVG renderer (no D3/cytoscape dependency, by design, so it survives an air-gapped Outlook email):

- **Layered (Sugiyama-style) layout** with explicit DFS back-edge detection so loops/rework don't blow up the longest-path layering — correct and non-trivial to get right (`process_flow.py:50-113`).
- **RTL-correct**: layer 0 (process start) is anchored on the *right* edge of the canvas, flow runs right-to-left, matching Persian reading order (`process_flow.py:128-129`) — most "Persian-ized" dashboards just mirror an LTR template and get this wrong.
- **Frequency encoding**: edge stroke-width scales with case count (`process_flow.py:181`) — correct DFG convention.
- **Gap**: there is no **performance (duration) view**. Edge/node color today is binary — `critical` boolean → red, everything else → one teal (`process_flow.py:182-183`). The token file already defines a 6-step sequential teal ramp (`gsi/design/tokens.py:57-59`, `SEQUENTIAL`) explicitly reserved for "continuous quantity, never category" — it is simply not wired into the flow chart yet. This is the standard Disco/Celonis "Frequency ⇄ Performance" toggle, and the palette to build it already exists and is unused.
- **Deviation is color-only.** A critical edge is red and thicker; there's no second (non-color) channel such as a dash pattern. For a system that already documents WCAG contrast ratios per token to four significant figures, relying on hue alone to mark "this transition is a problem" is the one accessibility gap in an otherwise disciplined system.

### 1.3 Conformance checking — correctly scoped, under-surfaced

`gsi/stages/s85_conformance.py` implements **precedence-rule conformance** against a "happy path" + ordering constraints from the RuleBook (skipped steps, out-of-order steps, explicit "insufficient evidence" fallback rather than a forced verdict — `s85_conformance.py:74-207`). This is the right level of rigor for this domain: it is not claiming formal alignment-based conformance (à la Petri-net token replay), and it says so implicitly by falling back to "insufficient evidence" instead of guessing. Good.

What's missing is **visibility, not rigor**: conformance today is a table a user has to navigate to, not a number attached to the graph they're already looking at. A discovered model with 40% of cases deviating and one with 2% deviating currently look identical on the Process Path canvas.

### 1.4 The fragmentation finding (the most important thing in this review)

The legacy `process_view.py` tab already has a **Variant Explorer** (variants ranked by % share and mean cycle length), a **cycle-time distribution histogram** (median + P75/P90), and a **differential root-cause table** (deviation rate vs. baseline per dimension) — see `RELEASE_NOTES_V26_4_0_PROCESS.md:37-46`. None of these three exist in the newer `gsi/process_intelligence` + `process-mining-ui-kit` stack: the registered block types are only `kpi_row, insight_row, process_flow, intensity_chart, evidence_table, heatmap, system_flow, kanban` (`pm_ui/layout/presets.py:19-36`) — no `variant_explorer`, no `cycle_time_histogram`, no `root_cause` block.

In other words: **the new, Figma-perfect, WCAG-documented design system currently powers the shallower of the two process views.** The analytically deepest views — the ones that let an analyst actually explain *why* a case is late, not just *that* it is — are still running on the old `theme.py` (`BANDS/SEQUENTIAL/SERIES/STATUS`), not the new token file. If the rebuild continues without porting these three views, the product will ship a beautiful UI with materially less analytical depth than the tab it replaces — which is exactly the failure mode this review was commissioned to prevent. **This is the top priority finding.**

### 1.5 What's already excellent (keep, don't relitigate)

- **Design-token discipline.** `gsi/design/tokens.py` documents the exact WCAG contrast ratio next to every color, separates *categorical* (8 hues) from *sequential* (6-step teal) palettes and comments that they must never be swapped, and ties every token to a named node in a live Figma file (`T9Ps72EYpriHdov9fmNFQu`, frame `3:2`). This is a materially higher bar than most enterprise dashboards clear.
- **"Never fabricate absence" philosophy.** Missing `from_team`/`to_team` renders as "not observed," an incomplete handoff row raises rather than guesses, `BALANCE_IS_UNKNOWN` is never silently treated as zero. This is precisely the right instinct for enterprise-grade precision and should be the explicit design principle carried into every new component (see Phase 2).
- **One computation, three renderers.** KPIs/nodes/edges are computed once and fed to Streamlit (build), HTML (Outlook, table-only, no Flexbox/Grid/JS because Word's renderer can't do it), and Excel — so the numbers a manager reads in an email can never drift from what an analyst sees live (`FIGMA_HANDOFF_FA.md:50-67`, `core.py:274-331`).
- **Audience-tiered layout** (`executive/manager/analyst`) already exists as data, not hardcoded UI (`pm_ui/layout/presets.py`) — this is exactly the mechanism to use for progressive disclosure in Phase 2, not a new concept to invent.

---

## Phase 2 — UX Architecture & Precision Interactions

Map the requested pipeline (Event Log → Variant Analysis → Discovery → Conformance → Enhancement) onto what already exists rather than a generic dashboard IA:

```
Published Snapshot / ad-hoc log  →  Scope & Reference Time (shared header, already exists)
        │
        ├─ VIEW 1  Status & Action        (exists)
        ├─ VIEW 2  Process Path           (exists — Discovery; needs Variant + Conformance folded in)
        └─ VIEW 3  Handoff Between Units  (exists)
```

### 2.1 Restore Variant Analysis as a first-class step, not a lost tab

Add a `variant_explorer` block (new registration in `pm_ui/blocks.py`, same `@register("variant_explorer")` mechanism the kit already documents for extension). Behavior:

- List distinct **trace signatures** (full activity sequence per case), ranked by % of cases, with mean cycle time per variant — this is exactly what the legacy tab computed; it needs a new renderer on the new token system, not new logic.
- Clicking a variant **highlights its exact path** on the Process Path canvas (edges not on the path drop to the existing dimmed-opacity treatment already used for hover, `process_flow.py:265-266` `.edge{transition:opacity}` — reuse, don't reinvent) and **filters** the KPI ribbon and evidence table to that variant's cases.
- Selecting the single most common variant = "happy path" is one click, not a mental exercise — this becomes the visual anchor for conformance overlay (2.4).

### 2.2 Filter sidebar — the one structural gap

There is currently no persistent filter panel component in the new kit (confirmed absent from `pm_ui/blocks.py`/`pm_ui/layout/presets.py`). Add one, scoped by audience tier like everything else in the layout system:

| Control | Applies to | Audience |
|---|---|---|
| Scope & Reference Time (already computed upstream) | all 3 views | all |
| Team / resource multi-select (`owner_team`, `from_team`/`to_team`) | Process Path, Handoff | manager, analyst |
| Evidence-quality filter (`evidence_quality` field already in the data model) | Status & Action | manager, analyst |
| Activity-path abstraction slider (2.3) | Process Path | analyst (manager sees a fixed sane default, not the control) |

Every filter that narrows what's shown must render a persistent chip stating what was excluded and why (`"۱۲ فعالیت با فراوانی زیر آستانه پنهان شد — نمایش کامل"` with a one-click "show everything" reset) — this is the same "never hide silently" instinct already applied to missing data; apply it to *filtered* data too, since a user must never mistake "filtered out" for "does not exist."

### 2.3 Replace the hard 60-activity cliff with a graded abstraction control

Today, exceeding 60 activities raises `ValueError("Graph limit is 60 activities; narrow the input scope")` (`core.py:198`) — the user hits a wall with no path forward inside the tool. Replace with a **Disco/Celonis-style simplification slider**: user controls "% of activities shown" / "% of paths shown" by frequency, computed client-side over the already-materialized full graph (no re-computation, no data loss — this is view-layer filtering, not re-mining). Two non-negotiables to preserve the product's own precision ethic:

1. The slider default is **100% (full graph)**, never a pre-simplified view — precision is opt-out, not opt-in.
2. A fixed status line always reads "Showing N of M activities, N of M paths" so the abstraction level is never ambiguous.

### 2.4 Conformance and deviation, made visible where the eye already is

- Add a **fitness/conformance %** tile to the existing `kpi_row` block — it's the single most important trust signal for a discovered model (Manifesto GP2) and currently requires navigating away from the graph to find.
- On the Process Path canvas, render deviating edges with a **second, non-color channel** in addition to the existing red: a dashed stroke (reuse `STATUS['critical']` color, add `stroke-dasharray`) so the signal survives grayscale printing and color-vision deficiency, consistent with the rigor already applied to every other token's contrast ratio.
- Keep root-cause as a differential table (deviation rate vs. baseline per dimension, as the legacy tab already computes) but restyle it on the new tokens and surface it as a drill-down *from* the conformance KPI tile, not a separate unrelated tab.

### 2.5 Drill-down ladder (consistent across all three views)

`Graph node/edge → Variant → Case list → Case timeline (already exists) → Evidence row with source_row (already exists)`. This ladder already exists end-to-end in pieces; the fix is making the path between each rung a literal click target (node click opens variant explorer pre-filtered to that node; variant row click opens case list; case row click opens the timeline) rather than requiring the user to reorient across independent widgets each time.

### 2.6 Cognitive load — reuse the tiering system that already exists, don't invent a new one

The `executive/manager/analyst` `visible_for` mechanism already solves "don't overwhelm the CEO." Extend the *same* field to the new filter sidebar and the variant explorer's depth (executive: read-only KPI + one insight sentence; manager: graph + variant list + conformance %; analyst: everything, including the abstraction slider and root-cause differential). This means zero new architecture for progressive disclosure — just new `visible_for` entries on new block types.

---

## Phase 3 — Figma Design System & Component Guidelines

**Governance rule, stated explicitly because it's easy to violate under deadline pressure:** the live file `T9Ps72EYpriHdov9fmNFQu` ("GSI Foundations", frame `3:2`) is the *only* source of truth. `gsi/design/tokens.py` and `pm_ui/tokens.py` are consumers, never independent decision points (this is already stated in `design/FIGMA_HANDOFF_FA.md:5` — carry it forward, don't relitigate it per-component). Any new component below is designed **inside that file**, as new frames/pages, not a new file.

### 3.1 New frames to add to the existing Foundations file

1. **Process Explorer / Canvas** — the DFG itself: node, edge, and canvas-chrome components (zoom control, minimap, legend).
2. **Variant Explorer panel** — ranked list component + "happy path" pinned row.
3. **Filter Sidebar** — the panel from 2.2, built from existing input/chip components already in Foundations.
4. **Conformance & Root Cause** — KPI tile variant + differential bar-chart component.

### 3.2 Component specs

**`Node` component**
- Auto-layout, fixed width/height per `process_flow.py` constants (158×58) so Figma and the rendered SVG stay pixel-comparable.
- Variant property `status`: the 7 existing values (`stockout, critical, serious, warning, good, neutral, unknown`) — reuse `STATUS_SCALE` verbatim (`gsi/design/tokens.py:81-89`), including its icon and label, so a Figma reviewer and the shipped product show identical states.
- Boolean variant properties: `selected`, `dimmed` (for the hover/variant-highlight interaction in 2.1).
- Text properties: `label`, `count`, `hint` — bound to real content, not placeholder Latin text, since Persian string length is the actual layout risk here.

**`Edge` component**
- Since Figma can't bind a continuous stroke width to a data value, define **5 discrete frequency steps** (matching the `1.6 + (count/max)*7.0` formula's practical range, `process_flow.py:181`) as component variants: `xs, sm, md, lg, xl`.
- Variant property `mode`: `frequency` (current teal) / `performance` (bound to the `SEQUENTIAL` 6-step ramp, `tokens.py:57-59`) — this is the toggle from 1.2/2.4, designed once, wired twice.
- Boolean property `deviating`: applies the dashed stroke treatment from 2.4, independent of color.

**`Filter Sidebar` component**
- Sections as auto-layout frames: Scope & Reference Time / Team & Resource / Evidence Quality / Path Abstraction.
- The abstraction slider is a component with a bound numeric property (0–100) and a live-updating "Showing N of M" label — the label is a required sub-component, not an annotation, so no engineer ships the slider without the disclosure text from 2.3.
- A persistent "Reset to full precision" ghost-button component, same treatment everywhere it appears (Filter Sidebar, and the "hidden activities" chip from 2.2).

**`Variant Row` component**
- Rank number, trace-signature sparkline (small multiples of activity abbreviations, matching the "long Persian labels truncate, full name on hover" rule already established in `aibl-supply-chain/app/process_view.py` docstring), % share (bar + number, never bar alone), mean cycle time, boolean `selected`.

**`Conformance Tile` component**
- Extends the existing `kpi_row` tile pattern (reuse `metric`/`metric-sm` type styles, `tokens.py:150-151`) with a percentage ring or bar, status-colored via `STATUS_SCALE`, click target opens Root Cause drill-down.

### 3.3 Color, typography, motion — largely defined; two additions

Everything below already exists in `gsi/design/tokens.py` and should simply be *cited* as the Figma variable set, not redefined:

- Surfaces: `#F6F8F9` / `#FFFFFF` / `#EEF2F4`; Brand: Navy `#0B1F33` (data & trust), Teal `#0A7C86` (process & flow), Gold `#C79A4A` (decision surface only, never text); 7-state status scale with ink/fill/wash roles; sequential ramp (6 steps, quantity only) vs. categorical set (8 hues, category only) — never interchange the two.
- Spacing (12-step, 4px grid), radius (0/6/10/14/20/pill — bigger container = rounder, table stays sharp), elevation (4 steps), type ramp (Display through caption/overline/metric), motion (140/220/400/600ms, transform/opacity only, `prefers-reduced-motion` respected).

**Two genuine additions needed**, not covered by the existing token set:

1. A **`deviation` pattern token** (dash pattern, not a color) — required by 2.4's accessibility gap; this is a new token category, not a new color.
2. A **`dimmed` opacity token** (e.g., 0.12, matching the existing hover-dim JS behavior in `process_flow.py:229-234`) formalized as a token instead of a magic number in inline `<script>`, so Figma's "dimmed" state and the shipped canvas's hover behavior can't drift apart.

### 3.4 Keep the Figma↔code sync test that already exists, extend it

The team already re-validates text nodes against the live file for font usage (27/27, 11/11, 203/203 checks noted in the Figma status report) and documents WCAG ratios per token. Extend that same discipline to a **token-diff check**: a script (mirroring `gsi_source_profiler.py`'s existing pattern of read-only verification) that pulls the Figma variable set via the Figma MCP/API and fails CI if `gsi/design/tokens.py` values drift from it. This turns "tokens.py must never be an independent source of truth" from a comment into an enforced contract.

---

## Phase 4 — User Journey Mapping

**Executive** (read-only, KPI-first — matches existing `visible_for: []`/`["executive", ...]` defaults)
1. Opens the published snapshot (no ETL wait — this already works: `python -m gsi.warehouse` publishes ahead of time).
2. Sees KPI ribbon + one `insight_row` sentence (e.g., "the process's largest bottleneck is customs clearance") — no filter sidebar, no abstraction slider; the tiering system hides them by design.
3. Optionally opens Process Path in a fixed, pre-simplified read view (not interactive filtering) to see the shape of the process, colored by status only.

**Process manager**
1. Opens Status & Action — sees case-level state, owner, evidence quality, next action; anything unobserved reads "not observed," never blank or zero.
2. Moves to Process Path — sees the DFG in **frequency mode** by default, conformance % tile visible in the KPI ribbon.
3. Spots a thick, dashed (deviating) edge into a bottleneck node → clicks the node → Variant Explorer opens pre-filtered to that node, ranked variants shown.
4. Picks the top deviating variant → canvas highlights that exact path, dims the rest → compares visually against the pinned happy-path row.
5. Drills to the case list for that variant → opens one case's timeline → confirms the actual delay is at a specific transition, not a hunch.
6. Exports the current scope as the Outlook HTML report — same numbers the manager just explored live, table-rendered for Word's engine, no drift.

**Analyst / operator**
1. Opens the Filter Sidebar (only tier that sees it) — narrows Scope & Reference Time, team/resource, evidence quality.
2. Switches Process Path to **performance mode** (sequential teal ramp by duration) to find slow-but-not-rare transitions the frequency view hides.
3. Uses the abstraction slider to declutter a >60-activity graph — sees "Showing 38 of 112 activities, 61 of 340 paths," never a hard error, always reversible with one click to 100%.
4. Selects a variant, drills to case timeline, inspects the evidence row (`source_row` pointing at the exact input line) — the same fail-closed evidentiary trail already used everywhere else in the product.
5. Notes a recurring rule-based pattern match (Pattern Observation) — explicitly labeled *observation only*, so the analyst — not the software — decides whether it becomes a flagged risk.
6. Exports the full Excel workbook for offline case-by-case review, RTL, same token palette, same numbers as the live view.

**The rule that ties all three journeys together, inherited from the product's own existing philosophy:** nothing is ever silently simplified, hidden, or fabricated — every abstraction is a labeled, reversible, user-chosen state, and every number on every surface (Streamlit, Outlook HTML, Excel) traces back to the same single computation. The UX work above is about *exposing* that rigor at every zoom level the three audiences actually use, not softening it for the sake of a cleaner canvas.
