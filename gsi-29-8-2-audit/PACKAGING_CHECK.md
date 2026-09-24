# Packaging check — GSI 29.8.2 RC4-OPT2 H1 (`FINAL_PRODUCT_20260924`)

927 files, 21 MB, 314 Python modules. Everything below was executed against the
extracted package, not read off a manifest.

## What is correct

| Check | Result |
|---|---|
| `PACKAGE_SHA256_FINAL.json` | **926/926 files verified** — every hash and byte count matches, nothing missing, and the only unlisted file on disk is the manifest itself (correct — it cannot hash itself) |
| Build artifacts | **Clean** — zero `__pycache__`, `.pyc`, `.pytest_cache`, stray `.sqlite` or writer-lock files |
| `python -m compileall gsi app tools tests` | **PASS** |
| Secret scan | **Clean** — no key-shaped strings; `ANYTHINGLLM_API_KEY` is read from the environment and the integration doc states it must never enter HTML |
| Dependency manifest | `requirements.txt` covers every third-party import reached by the runtime |

## P1 — 1.9 MB of real business rows ship inside the product, and 97% of the published chatbot is built from them — **Critical**

`offline_knowledge/raw/evidence.txt` (1,921,044 bytes) is in the distributable,
and a near-identical copy sits at `review/roadmap/evidence.txt`. This is the
evidence file holding real sample rows: customer names, registration codes,
order numbers, supplier names, bank branches, proforma values, FX rates and
named personnel columns.

It is not inert. Measured, not inferred, by running the shipped loader:

```
$ python offline_knowledge/LOAD_INTO_KNOWLEDGE_DESK.py
{'scanned': 14, 'indexed': 14, 'chunks': 988}

total searchable chunks:                 988
chunks originating from evidence.txt:    958   (97.0% of the knowledge base)
query for a real customer name:          returns hits, all from evidence.txt
```

The chain is complete and entirely inside the package:
`offline_knowledge/raw/evidence.txt` → `LOAD_INTO_KNOWLEDGE_DESK.py` (points
`knowledge_path` at `offline_knowledge/`) → `indexer.py:88` `rglob("*")` with
`.txt` in `SUPPORTED` → `kb_chunks` → `static_export.py:58` selects `c.body` and
inlines it as JSON into `chatbot.html` → published to a shared folder.

So building the offline chatbot as documented writes 958 chunks of real
business data into a single HTML file intended for a network share. Two further
points make this easy to miss: `static_export.py:151` raises
`BLOCKED_EMPTY_KNOWLEDGE` when nothing real is indexed, so `evidence.txt` is
currently the only thing keeping the build from failing — the risky file is
load-bearing; and nothing in the build output says one file dominates.

**Fix, in order:** remove `evidence.txt` from `offline_knowledge/raw/` and from
`knowledge_manifest.json` before shipping (deliver it separately if a reviewer
needs it); decide deliberately what the shared-folder chatbot is allowed to
contain; and take hunk 4 of `proposed.diff`, which makes `build_index` return
`largest_source` and `largest_source_share` so this is visible at build time:

```
{'scanned': 14, 'indexed': 14, 'chunks': 988,
 'largest_source': 'evidence.txt', 'largest_source_share': 0.97}
```

## P2 — the runtime release channel is a version behind the package — **Medium**

`gsi/factsheet.py:40` declares `RELEASE_CHANNEL = "rc4-opt1"` while the zip,
`README.md`, `CHANGELOG.md` and `PACKAGE_INFO_V29_8_2.json` all say
**RC4-OPT2** (and the zip and `PACKAGE_INFO.json` add H1 / the final rewrite).
`VERSION = "29.8.2"` is correct; only the channel string is stale. This is the
same defect class RC3 itself caught and fixed once ("zip named RC2 but runtime
still 29.7.7 rc1"), so it has regressed. Hunk 2 of `proposed.diff` sets it to
`"rc4-opt2-h1"`.

Three SHA manifests also ship side by side — `PACKAGE_SHA256_FINAL.json`
(current, verified), `PACKAGE_SHA256.json` (18 files stale) and
`RELEASE_SHA256.json` (56 files stale). The current one is unambiguous only if
you already know which it is; consider naming the historical two accordingly.

## P3 — the shipped test suite contradicts the shipped runtime contract — **High**

`python run_all_tests.py` on this package: **1175 passed, 1 failed.**

The failure is `tests/test_fullstack_v29_6_10.py::test_real_dashboard_runs_through_html_download`.
It patches `gsi.pipeline.Pipeline.run` and expects the dashboard to render an
HTML download button. The 29.8.2 dashboard no longer takes that path:
`app/dashboard.py:267-271` now shows an error and calls `st.stop()` when no
published snapshot exists, instead of falling back to a pipeline run. That is a
deliberate contract — `PACKAGE_INFO.json` declares
`"ui_default_mode": "published_snapshot_only"` and `"refresh_mode": "explicit_only"` —
and it is a defensible design. The test was simply never updated with it.

This went unnoticed because the release gate excused it:
`FINAL_PRODUCT_GATE_20260924.json` records
`"streamlit_apptests": "3 ENVIRONMENT-BLOCKED; not counted as PASS"`, and
`PACKAGE_INFO.json` explains "streamlit.testing unavailable in build runtime".
`streamlit.testing.v1` imports fine here, so the tests ran — and one of them
fails. **A test recorded as environment-blocked is not a test that would have
passed.** Any gate that carries this exclusion should be re-run on a runtime
where Streamlit is installed before the exclusion is renewed.

Hunk 3 of `proposed.diff` replaces the stale test with one that drives the
snapshot path the page actually takes, and adds the missing negative test
asserting the other half of the contract — that no ETL starts on page load.
Both pass (verified below).

## Verification of the proposed diff

Applied to a scratch copy of the package, not to the delivered zip:

| Hunk | Check | Result |
|---|---|---|
| 1 — `anythingllm.py` | `tests/test_anythingllm_learning_v29.py` | PASS |
| 2 — `factsheet.py` | `tests/test_doc_claims.py` (version/contract claims) | PASS |
| 3 — `test_fullstack_v29_6_10.py` | the replaced test + the new negative test | PASS (was 1 FAIL) |
| 4 — `indexer.py` | 15 knowledge-desk / offline / index tests | PASS |
| all four | `python run_all_tests.py` | **1177 passed, 0 failed** (was 1175 / 1) |

## Not checked here

Real corporate data. Every number above comes from the package's own bundled
artifacts and from generated data carrying the real production headers; the
631,576-row workbooks were not available in this environment. The package's own
`production_certification_reason` says the same thing, and that remains the
right position.
