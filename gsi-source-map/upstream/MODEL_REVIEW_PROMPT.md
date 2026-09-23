# Prompt for reviewing the GSI Evidence Pack

You are reviewing a compact evidence pack generated from the real GSI source files.

Rules:
1. Treat this as evidence, not a full dump.
2. Representative rows were chosen to expose keys, statuses, fan-out, duplicates, gaps and relations.
3. Missing evidence is not proof a process step did not occur.
4. A co-observed relation is not automatically a causal/authoritative join.
5. Do not assume a whole Excel export has one grain if multiple grains are evident.
6. Distinguish raw/native evidence, derived facts, events, snapshots, statuses, entities and bridges.
7. For every conclusion label it DIRECTLY SUPPORTED / HEURISTIC / NEEDS BUSINESS CONFIRMATION.

Read first:
- executive_summary.md
- model_context_pack.md
- process_key_index.json

Then inspect small samples/schema files only where needed.

Deliver:
1. Source & grain matrix
2. Candidate business keys
3. Candidate cross-source joins
4. Status/state inventory
5. Process graph
6. Fan-out / double-count risks
7. Missing business rules
8. Questions required before architecture changes
