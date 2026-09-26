# ARCHITECTURE_BASELINE — 29.7.7 RC1

2026-09-22 · Incremental patch of 29.7.6. Not Greenfield. No stack migration.

## Runtime ownership
Excel/archived bytes → adapters → standardized representations → population/stages → working Business DWH → validation → run-addressed files → publication pointers. pandas, SQLite, Streamlit and existing domain modules remain.

Raw wh_file/wh_sheet/wh_raw_row remain the immutable source archive. Serialized wh_frame snapshots now also preserve DataFrame attrs, including source_origin_run and mapping diagnostics. A standardized row is not automatically a physical source row or a financial event.

Business working tables retain their existing schemas and PK/FK constraints. At build completion they are copied to typed snap_dwh_* tables, identified by snapshot_run and protected from UPDATE/DELETE. wh_semantic_snapshot records completed captures. The entire working projection is rebuilt, avoiding stale current facts and accumulated relation counts. All captures occur in the business-build transaction.

Warehouse.read_db opens a read transaction and binds connection-local views to one published run before setting query_only. Chatbot, Cashflow and warehouse UI use this API; Warehouse.db remains explicitly administrative/working access. Snapshot indexes cover run + major business keys. No new DWH engine, SCD Type 2 business-event model, or streaming/incremental claim is made.

Legacy mutable databases cannot prove the old published payload after prior overwrites. The code does not manufacture an old snapshot from their current tables. Rebuild from archived run frames before certifying old as-of data. First successful RC build starts certified semantic snapshots. Existing raw bytes are unchanged.

## Publication
Schema baseline candidates are per run; only successful publication promotes them. Missing process summary blocks publication. Core checks run before generation of Excel/extract/audit files. Artifacts live under OUTPUT_DIR/runs/<run_id>; a failed run cannot overwrite a prior official daily file. Pointer move requires completed run, passing checks and non-regressing started time, under BEGIN IMMEDIATE. Filesystem generation and SQLite are not a distributed transaction: a failed generation/publish may leave unreferenced run files. Retention/cleanup is not automated.

## SAP grain
| Representation | Grain | Interpretation |
|---|---|---|
| Raw archive | file hash × sheet × physical row | Original evidence, including duplicates |
| sap/raw_rows | standardized row ordinal | All exported standardized rows |
| PR fact | PR × PR Item (item may be absent) | Snapshot; multi-PO columns suppressed, SAP_PO_COUNT shown |
| PO fact | PO × PO Item | PO-side PR/item/material; conflicts recorded |
| Workflow fact | source workflow observation within run | Not certified business event history |
| Supplier / Plant / Package | source payload fields | No fabricated dimension relationships; dedicated conformed dimensions not added |
| Legacy main | representative PR | Compatibility only; not an additive PO fact |

PR/PO deletion flags remain separate payload evidence. Omission from a new snapshot is absence in that snapshot, not proof of cancelled/deleted procurement. Full/delta source contracts remain open.

## Process
Reference sequence is a control vocabulary, never an evidence generator. Material/Employee cannot form case components; downstream observations stay present with upstream gaps. SWIFT_SENT is distinct from Payment. Remaining balance is not Settlement. Matrix retains legacy display STATUS plus separate EVIDENCE_STATE, COVERAGE_STATE, COMPLETION_STATE, EXECUTION_STATE and RELATION_STATE. Positive approval is not automatically completed. Shared PR/REG components and hash-based PC identifiers remain limitations.

## Finance and failure boundaries
Allocation request ledger retains currency amounts. Mixed-currency compatibility totals become unknown. Invalid/conflicting NTSW commitment rows quarantine independently of licence/allocation. No account, FX rate, payment date or settlement is inferred. Legacy balance/default-zero and unscoped historical obligation totals are unresolved release blockers.

CORE: publication/SQLite consistency, final partition, process evidence presence and existing required grain checks. TOLERANT: enrichment/source branches; raw/quarantine/diagnostics retained. OPTIONAL: absent evidence reports a coverage gap. The implementation still publishes one global run; it does not implement independent domain pointers.

## Semantic chatbot
Operational identifiers route to the published semantic DWH; explicit policy questions route to KB. Operational backend errors return SOURCE_UNAVAILABLE, not absence. Numeric and explicitly labelled alphanumeric identifiers are supported. PR answers expose item payload evidence, source, business key, evidence date, run, evidence state and source-observed confidence. Workflow is labelled observation. This is not yet a complete PR-to-payment-to-clearance answer: normalized per-stage evidence retrieval, conflict rendering, KB effective authority and external LLM governance remain open.

## Preserved boundaries
Source authority rankings, Oracle approved max policy, historical warehouse and external access control are not silently rewritten. Oracle max columns now expose contributing sheet names. Flat reports are compatibility projections; normalized ledgers are the grain reference. Existing UI layouts remain.

See FINDINGS_REGISTER.md for exact closure, DECISION_LOG.md for tradeoffs, and TEST_AND_INVARIANTS.md for execution evidence.
