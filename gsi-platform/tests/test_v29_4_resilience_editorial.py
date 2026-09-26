import pandas as pd

from gsi.warehouse.store import Warehouse
from gsi.warehouse.reliability import source_runtime_checks, blocking
from gsi.design import tokens as T
from gsi.design.css import stylesheet


def test_last_published_standardized_frame_can_be_used_as_explicit_stale_fallback(tmp_path):
    wh = Warehouse(tmp_path / "warehouse.sqlite")
    with wh.run({"reference_date": "2026-09-21"}) as rid:
        wh.frame(pd.DataFrame({"KEY_BL": ["BL1"], "x": [1]}), "standardized", "sata/main")
    wh.publish(rid)
    frames, meta = wh.published_frames("sata")
    assert list(frames) == ["main"]
    assert frames["main"].iloc[0]["KEY_BL"] == "BL1"
    assert meta["run_id"] == rid


def test_noncritical_branch_failure_degrades_but_does_not_block_publish_gate():
    class P:
        source_failures = {"sata": {"error": "offline"}}
        source_fallbacks = {}
        merge_failures = []
    checks = source_runtime_checks(P())
    assert checks[0].severity == "DEGRADED"
    assert blocking(checks) == []


def test_registration_spine_failure_blocks_publication_without_hiding_diagnostics():
    class P:
        source_failures = {"ntsw": {"error": "import licence missing"}}
        source_fallbacks = {}
        merge_failures = []
    checks = source_runtime_checks(P())
    assert checks[0].code == "SOURCE_LOAD_FAILED"
    assert blocking(checks)


def test_editorial_tokens_are_restrained_and_css_exposes_paper_language():
    assert T.SURFACE_RAISED == "#ffffff"
    assert T.BRAND_TEAL == "#0a7c86"
    assert T.SURFACE_PAPER.startswith("#")
    css = stylesheet()
    assert "--paper:" in css
    assert ".editorial-lead" in css
    assert ".annotation" in css
