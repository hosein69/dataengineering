# -*- coding: utf-8 -*-
import pandas as pd
from gsi.resolve.process_evidence import source_observation_inventory, _observations


def _src():
    # Two standardized projections of the same physical rows.  Row-preservation
    # must count physical lineage once, not DataFrame exposure twice.
    base = pd.DataFrame({
        "_SOURCE_FILE_ID": ["book-a", "book-a"],
        "_SOURCE_SHEET": ["Sheet1", "Sheet1"],
        "_SOURCE_ROW": [2, 3],
        "KEY_REG": ["R1", "R2"],
        "VALUE": [10, 20],
    })
    projection = base.copy()
    projection["SEMANTIC_LABEL"] = ["x", "y"]
    return {"ntsw": {"native": base, "semantic": projection}}


def test_expected_rows_use_unique_physical_identity_not_projection_count():
    inv = source_observation_inventory(_src())
    assert inv["candidate_frame_rows"] == 4
    assert inv["expected_unique_rows"] == 2
    assert inv["duplicate_ref_rows"] == 2


def test_produced_source_observations_preserve_same_unique_refs():
    inv = source_observation_inventory(_src())
    obs = _observations(_src())
    generic = obs.loc[obs["STAGE_CODE"].eq("SOURCE_OBSERVATION")]
    refs = set(generic["SOURCE_ROW_REF"].astype(str))
    assert refs == set(inv["unique_refs"])
