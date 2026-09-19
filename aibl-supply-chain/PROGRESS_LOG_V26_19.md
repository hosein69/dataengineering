# GSI / AIBL V26.19 — Progress Log

**Workstream:** Legacy Knowledge Transfer → Systemic Knowledge Model  
**Release:** `26.19.0`  
**Status timestamp:** 2026-09-17 19:19 +03:30  
**Current state:** **Stage 6 of 6 — Completed / Release validated**

## Completed stages

- [x] **1. Baseline & source intake** — V26.18 copied as controlled baseline; old OF/BL/ETS/Rates/ZMM58/NTSW/Append/notebook/PDF received as *legacy knowledge only*, not current-law/current-data truth.
- [x] **2. Knowledge extraction & canonical mapping** — historical rules, operational practice, data mappings, root causes, evidence requirements and technical anti-patterns separated.
- [x] **3. Knowledge-to-code implementation** — `LegacyKnowledgeItem`, catalog, provenance/confidence/effective-period model, V26.19 Rule Pack and runtime stage implemented.
- [x] **4. Control Tower integration** — Root Cause/Evidence/Provenance signals wired to Money Flow Control Tower and FX report without changing legacy knowledge into an enforceable current rule.
- [x] **5. Regression & governance validation** — 19 registered test suites, 502 successful checks / 0 failures; RuleBook validator, manifest and Doctor passed structurally.
- [x] **6. Release finalization** — package version raised to `26.19.0`, README/Release Notes/docs updated, manifest regenerated and final archive prepared.

## System-design decisions transferred to code

1. **Legacy knowledge is evidence, not law.** `can_auto_enforce()` is fail-closed: legacy classes cannot silently become binding rules.
2. **Payment is independent from BL.** A payment without BL is represented as `UNALLOCATED_PAYMENT_CANDIDATE`, never a fabricated BL.
3. **Allocation is a relationship.** Historical FIFO is preserved only as a legacy candidate algorithm; explicit/authorized Allocation Edge has priority.
4. **Rate semantics are separated.** Historical normalization rate, FX purchase rate, supplier-settlement rate, cross-rate, accounting rate and fees are distinct concepts. A static legacy rate cannot produce real P&L.
5. **Cross-currency P&L requires evidence.** Missing amount/rate/cross-rate evidence creates an Evidence Gap instead of an invented loss/profit number.
6. **Historical A/B/C clocks remain non-binding.** They are retained for comparison/root-cause context with provenance and historical status.
7. **Root-cause knowledge is suggestion, not verdict.** Blockers from historical experience generate candidates and evidence requests, not automatic fraud/legal findings.
8. **Desktop/file-path anti-patterns are documented, not copied.** Fixed UNC/column/COM automation knowledge is kept as migration knowledge rather than business truth.

## Main V26.19 artifacts

- `aibl/knowledge/legacy.py`
- `aibl/rules/legacy_knowledge.yaml`
- `aibl/stages/s57_legacy_knowledge.py`
- `tests/test_legacy_knowledge_v26_19.py`
- `docs/LEGACY_KNOWLEDGE_TRANSFER_V26_19_FA.md`
- `docs/RELEASE_VALIDATION_V26_19_FA.md`
- `RELEASE_NOTES_V26_19_LEGACY_KNOWLEDGE_TRANSFER.md`

## Validation snapshot

- **Version:** `26.19.0`
- **Process stages:** 14, including `legacy_knowledge_transfer` between money-flow control and narration.
- **Rule packs:** 11.
- **Legacy knowledge items:** 22.
- **RuleBook structural errors:** 0.
- **Current rules requiring official re-verification:** 19 (kept separate from the non-binding legacy pack).
- **Manifest:** 102 tracked core files; fingerprints validated by Doctor.
- **Doctor:** 0 errors / 8 warnings.
- **Warnings:** optional `jdatetime`, 19 current-rule verification items, and six internal IKCO network shares unavailable from this environment. None are hidden as code success.
- **Tests:** 502 passed / 0 failed across 19 registered suites. Because the external tool harness has a wall-time limit, the complete regression was executed in recorded groups; all suites passed.

## Release principle

Old documents and workbooks are deliberately retained as **provenanced organizational knowledge**. Their values, deadlines, rates and formulas are not promoted to current binding logic unless independently verified through the current RuleBook governance process.
