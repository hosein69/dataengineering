# GSI V26.20 — Case Action Queue + Allocation Queue + Supply Position

**Release date:** 2026-09-17  
**Product identity:** GSI | Global Sourcing Intelligence — Data • Process • Decision

## Why this release exists
V26.20 closes three control gaps that could create misleading management conclusions:
1. allocation-history rows could overstate allocation or hide an open tranche;
2. missing inventory could appear as zero;
3. a detected problem had no governed, human-reviewed action/email workflow.

## Supply Position: expert truth + Oracle reconciliation
The authoritative operational buckets are:
- Supplier / نزد سازنده — Expert source
- In Transit / در راه — Expert source
- In Customs / گمرک — Expert source
- IKCO stock — Oracle
- SAPCO stock — Oracle

The system does not derive quantitative expert inventory from BL status or dates. Missing is unknown, not zero. Confirmed total and days-of-resistance are only produced when all required components are present. Otherwise the system emits a lower bound, coverage percentage and lineage/evidence gaps.

## Allocation Request Ledger
NTSW allocation is request-level. The ledger distinguishes allocated, open and rejected requests and deduplicates status/snapshot history. A REG can therefore be simultaneously partially allocated and still in queue. Queue rank is only displayed when the source export actually supplies it.

## Money-flow case lifecycle
The control tower separates:
`Order → Allocation Queue → Allocation → FX Purchase → Funding → SWIFT/Conversion → Shipment → Customs → Clearance → Bank Customs Document → Settlement`.

Physical clearance is not treated as proof that the bank has received/matched the customs document. Currency purchase is not treated as proof of supplier payment. Cross-currency P&L is not calculated without sufficient conversion evidence.

## Case Action Queue
Each actionable case can produce an internal recommendation with:
- priority and owner;
- due date / age;
- rationale;
- missing evidence;
- rule basis;
- draft email subject/body;
- `PENDING_REVIEW` status and mandatory human review.

The Outlook action opens a draft by default. Direct send is not the default. Unexplained reallocation is an investigation signal, never an automatic fraud finding.

## Regulatory source hierarchy
`Official/Binding → Official Operational → Verified Field Intelligence → Field Signal`.
Telegram/Bale signals cannot independently create a legal penalty or definitive compliance finding. Current emergency overlays and SATA exceptions are eligibility/evidence driven.

## GSI identity migration
- Python package and CLI: `gsi`.
- GSI environment variables are primary; old aliases are migration fallback only.
- Studio/HTML/email use Global Sourcing Intelligence branding.
- Visual semantics: Navy=Data, Teal=Process, Gold=Decision.

## Release validation
- Version: 26.20.0
- Rule packs: 12
- Pipeline stages: 16
- Test files/suites: 20
- Regression: **517 passed / 0 failed** (suite-by-suite execution)
- RuleBook structural errors: **0**
- Rules requiring official/current verification: **19**
- Manifest: **105 tracked files**
- Doctor: **0 errors / 8 warnings**

Warnings are environmental/governance warnings, not code failures: inaccessible corporate network shares from this runtime, optional `jdatetime`, and the deliberately fail-closed unverified rules.
