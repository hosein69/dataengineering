# Prompt for reviewing the GSI Evidence Pack

You are reviewing a compact evidence pack generated from the real GSI source files.

## Before anything else

Open `executive_summary.md` and check the coverage banner. **If the pack is marked
INCOMPLETE, every conclusion you draw is scoped to the sources listed as PROFILED.**
A source that is missing from the pack tells you nothing about the business.

## Rules

1. Treat this as evidence, not a full dump.
2. Representative rows were chosen to expose keys, statuses, fan-out, duplicates, gaps and relations.
3. Missing evidence is not proof a process step did not occur.
4. A co-observed relation is not automatically a causal or authoritative join.
5. Do not assume one Excel export has one grain when several are evident. The `side`
   field (`header` / `po` / `pack`) says which grain a column belongs to.
6. Distinguish raw/native evidence, derived facts, events, snapshots, statuses,
   entities and bridges.
7. A shared role name across two sources is a join **candidate**. It does not make the
   two identifiers the same business entity. `secondary_role_columns` lists columns
   that matched a role but were deliberately kept out of the join map — do not
   promote them yourself.
8. `key_conflicts` means two columns claim one role and disagree on the same native
   row. Never merge them. Ask the source owner which one the business means.
9. A repeated composite key is a question, not a finding: a second business event, or
   the same record re-observed in a later snapshot?
10. `EXPORT_ROW_NO` is an export sequence number. It identifies a row inside one file
    and nothing else. Never join on it and never let it define a grain.
11. Status counts are grouped on a normalised form. `raw_variants` shows the different
    spellings that folded together — that is a data-entry observation worth reporting,
    not noise to discard.
12. Label every conclusion DIRECTLY SUPPORTED / HEURISTIC / NEEDS BUSINESS CONFIRMATION.

## Read order

1. `executive_summary.md` — coverage first
2. `model_context_pack.md`
3. `process_key_index.json`
4. `coverage_report.json`

Then inspect individual samples and schemas only where needed.

## Deliver

1. Source and grain matrix, with coverage stated per source
2. Candidate business keys, separating representative keys from secondary columns
3. Candidate cross-source joins, each labelled with its confidence level
4. Status and state inventory, including spelling variants found
5. Process graph
6. Fan-out and double-count risks, including every repeated composite key
7. Same-role key conflicts and what each one blocks
8. Missing business rules
9. Questions that must be answered before any architecture change
