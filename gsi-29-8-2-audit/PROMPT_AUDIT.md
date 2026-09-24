# Prompt audit — GSI 29.8.2 RC4-OPT2 H1 (`FINAL_PRODUCT_20260924`)

Run via `/claude-api prompt-audit`. Two deliverables: this report, and
`proposed.diff` (4 files, 127 lines) which is proposed, not applied.

## Stated assumptions (Step 0)

**Scope.** The whole package: 927 files, 314 Python modules. The prompt surface
is whatever the Step 1 inventory found — no narrower scope was named.

**Target model: none is declared anywhere in this package, and that is the
single most important fact about this audit.** There is no Anthropic SDK, no
OpenAI SDK, no model ID, no `thinking` config, no sampling parameters, no
`tools` array, no beta header, no prefill, and no provider client of any kind.
The one LLM integration is an AnythingLLM sidecar, where the model is chosen by
the operator inside AnythingLLM — not by this code. Non-Anthropic provider
markers found: **none**. Consequently every "obsolete for the target model"
judgement in the standard pattern tables is unavailable here, and this audit
only reports patterns that are model-independent or provable from the code
itself. Nothing below proposes moving anything to any SDK.

## Inventory (Step 1)

| # | Surface | Location | Reaches a model? |
|---|---|---|---|
| 1 | Runtime prompt, assembled in code | `gsi/learning/anythingllm.py:70-87` | Yes, in principle — but see F1 |
| 2 | Offline review prompt, human-pasted | `tools/source_profiler/MODEL_REVIEW_PROMPT.md` (29 lines) | Yes, outside the app |
| 3 | Lesson text injected as context by (1) | `config/weekly_lessons.json`, `gsi/learning/weekly.py:14-24` | Only via (1) |
| 4 | Offline knowledge corpus | `offline_knowledge/**` (14 files) | Only if an operator uploads it to a workspace |
| 5 | Request-building code | — | **None exists** |
| 6 | Tool definitions | — | **None exists** |
| 7 | `SKILL.md` / `CLAUDE.md` / rule files | — | **None exists** |

## Provenance (Step 2)

No git history is shipped inside the zip, so blame-based dating is unavailable
and only idiom-dating applies. The signal greps from the audit guide were run
over surfaces 1–3 and returned **nothing** for: pressure language
(`MUST|NEVER|ALWAYS|CRITICAL|IMPORTANT`, `!!`, `try to|if possible|ideally`),
API-replaceable scaffolds (`think step by step`, `<scratchpad>`,
`stop_sequences`, `budget_tokens`, `temperature`, "output only valid JSON"),
fossils (retired model names, `no longer`, `instead of`, `reminder:`,
anti-formatting rules), and numeric output caps or update cadences. The only
`Do not` / numbered-list hits are in surface 2 and are domain-contract rules and
a deliverables list, which the keep list protects.

**The prompt text in this package is clean.** Per the guide, a clean surface is
a valid outcome and an empty diff beats a manufactured one — so no finding
below is a text-level cruft finding. All three are structural: instructions that
nothing enforces, and one that nothing can even reach.

## Findings (Step 5)

### F1 — the only runtime prompt in the package is unreachable — **High**

| | |
|---|---|
| **Location** | `gsi/learning/anythingllm.py:44-96`; doc at `ANYTHINGLLM_INTEGRATION_FA.md:19-25` |
| **Evidence** | `grep -rn "AnythingLLMClient" --include='*.py'` returns exactly two hits, both in `gsi/learning/__init__.py` (the import and `__all__`). The class is never instantiated. The only test touches `AnythingLLMConfig.from_env()`. `app/learning_view.py:109` answers with the local deterministic engine: `r = answer(cfg, q)`. |
| **Pattern** | Group 1d — unenforced instruction; Group 4 — dead call site |
| **Why it matters** | `ANYTHINGLLM_INTEGRATION_FA.md` documents a live Streamlit feature — "پرسش از همان آموزش با context محدودشده به محتوای درس" and "نمایش source citations بازگشتی AnythingLLM" — that the shipped `app/learning_view.py` does not implement. The doc over-claims against the code. This is model-independent and provable by grep. |
| **Action** | `rewrite` the integration doc to describe what ships, **or** wire `ask()` into `learning_view.py`. The diff takes neither unilaterally: F2's hunk makes the client honest first, and the decision on which way to close F1 is the owner's. |

### F2 — the grounding claim is prose only; nothing enforces or checks it — **Medium**

| | |
|---|---|
| **Location** | `gsi/learning/anythingllm.py:79-87` |
| **Evidence** | `"به سؤال زیر فقط بر اساس آموزش هفتگی و دانش موجود در Workspace پاسخ بده."` sent with `mode: str = "chat"` (the default, never overridden anywhere in the package — `grep -rn "mode=" gsi/learning app/learning_view.py` returns nothing), and `answer_text()` reads the text with no reference to whether any source was returned. |
| **Pattern** | Group 1d — unenforced instruction ("enforce in code what can be enforced in code"); Group 4 — request config |
| **Why it matters** | For an evidence-led product whose entire architecture refuses to assert what it cannot source, the one place it talks to a model relies on a sentence rather than a parameter. A prompt is a request; the mode and the citation check are the enforcement. **I could not verify AnythingLLM's `chat` vs `query` semantics from this environment — `docs.anythingllm.com` is blocked by the egress proxy — so the diff does not change the default.** It documents the contract and adds `has_sources()` so a caller can verify grounding instead of trusting it. Confirm the mode semantics against your AnythingLLM version before switching the default to `"query"`. |
| **Action** | `rewrite` — hunk 1 of `proposed.diff` |

### F3 — `MODEL_REVIEW_PROMPT.md` is clean; no edit proposed — **(no finding)**

All 29 lines survive the deletion rule. The seven numbered rules are
domain contract — "Missing evidence is not proof a process step did not occur",
"A co-observed relation is not automatically a causal/authoritative join", "Do
not assume a whole Excel export has one grain" — which is context only the
author knows (keep list #1) and prohibitions against failures that demonstrably
reproduce in this domain (keep list #5). The `DIRECTLY SUPPORTED / HEURISTIC /
NEEDS BUSINESS CONFIRMATION` label set is format-pinning on a format-sensitive
output (keep list #7). The "Read first / Then inspect" lines are file-map
context, not method choreography. The eight-item "Deliver" list is the
requirement, not a procedure. **Reported so the clean result is on the record.**

### F4 — no token or cost accounting on the one model call — **Low (flag)**

`ask()` returns the raw response dict and nothing records usage, latency or
cost. This is the Group 4 "no token accounting" item: without it, no future
audit of this surface can be measured. Not worth a diff while F1 stands (the
call site does not exist), but it is the first thing to add if the client is
wired up.

## Proposed diff (Step 6)

`proposed.diff` — one finding per hunk, take them selectively:

1. **F2** `gsi/learning/anythingllm.py` — document what `mode` actually
   constrains; add `has_sources()` so grounding is checkable rather than
   assumed.
2. **P2** `gsi/factsheet.py` — `RELEASE_CHANNEL` `"rc4-opt1"` → `"rc4-opt2-h1"` (packaging, below).
3. **P3** `tests/test_fullstack_v29_6_10.py` — replace the AppTest that still
   asserts the pre-29.8.2 contract, and add the negative test for the new one (packaging, below).
4. **P1** `gsi/knowledge_desk/indexer.py` — report index composition so one file
   dominating the knowledge base is visible before publication (packaging, below).

Nothing in the diff is applied to the package. Verification of each hunk is
recorded in `PACKAGING_CHECK.md`.
