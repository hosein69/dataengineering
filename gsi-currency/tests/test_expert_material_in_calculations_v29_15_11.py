# -*- coding: utf-8 -*-
"""Every expert-file material is in the mart and in the calculations — GSI 29.15.11.

Owner's words (1405-07-05): «معیار فایل کارشناسان هست و نباید حذف یا از
محاسبات خارج شود؛ اگر اشتباه بود باید علت‌یابی شود».

Until 29.15.10 the mart held one row per order (its first material); the
second material of an order and a row without an order number were only shown
beside the calculations. Now each Order×Material is a mart row:

* ``FIRST``      — the order's first material; carries the order's BLs.
* ``ADDITIONAL`` — every further material; order-level values are repeated,
  its BL is left empty on purpose (which BL carries it is not recorded).
* ``NO_ORDER``   — an expert line without an order number; its own case.

The grain contract that keeps the numbers honest: material-level measures
count every material; order/REG/BL-level facts (commitment, demurrage, process
conformance, BL count) are counted once per case — a three-material order is
not three commitments.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.report.dashboard import SHEET_COMMIT, SHEET_SCORECARD, ExcelDashboardBuilder
from gsi.resolve.population import build_primary_population
from gsi.resolve.process_evidence import build_process_inventory
from gsi.studio_core.grain import case_rows, safe_agg


def _expert():
    raw = pd.DataFrame([
        {"Row No.": 1, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "رينگ ضدقفل مغناطيسي", "Quantity In Order": 10,
         "PI Line Value": 100, "Currency": "EUR"},
        {"Row No.": 2, "Order No. (Our Reference)": "823107D", "Material": "9654003280",
         "Material Description": "هدف چرخشي ترمز ضدقفل", "Quantity In Order": 10,
         "PI Line Value": 0, "Currency": "EUR"},
        {"Row No.": 3, "Order No. (Our Reference)": "823107D", "Material": "B-2",
         "Material Description": "قطعه دوم سفارش", "Quantity In Order": 4,
         "PI Line Value": 50, "Currency": "EUR"},
        {"Row No.": 4, "Order No. (Our Reference)": "", "Material": "IK88888888",
         "Material Description": "بست لوله"},
    ])
    return MoghavematAdapter().transform({"Expert Data": raw})


def _population():
    abbasi = pd.DataFrame([{"KEY_ORDER": "823107D", "KEY_BL": "HDM1501WESL0968"},
                           {"KEY_ORDER": "823107D", "KEY_BL": "HDM1534WNHS2798"}])
    base, _, meta = build_primary_population({"moghavemat": _expert(),
                                              "abbasi": {"main": abbasi}})
    return base, meta


def test_every_order_material_is_a_row_with_its_own_identity():
    main = _expert()["main"]
    assert list(main["MOGH_ITEM_ROLE"]) == ["FIRST", "ADDITIONAL", "NO_ORDER"]
    first, second, orphan = (main.iloc[i] for i in range(3))
    # each material keeps its own descriptions — B-2's text never lands on 9654003280
    assert first["MOGH_MATERIAL_DESC_COUNT"] == 2
    assert "قطعه دوم سفارش" not in first["MOGH_MATERIAL_DESCS_ALL"]
    assert second["MOGH_MATERIAL_DESCS_ALL"] == "قطعه دوم سفارش"
    # order-level values are the order's, repeated — never split or invented
    assert first["KEY_ORDER"] == second["KEY_ORDER"] == "823107D"
    assert first["MOGH_PI_VALUE_SUM"] == second["MOGH_PI_VALUE_SUM"] == 150
    # the order-less line is its own case, reported as incomplete
    assert orphan["KEY_ORDER"] == ""
    assert "شماره درخواست خرید" in orphan["MOGH_ITEM_RECORD_GAPS"]


def test_population_keeps_every_material_and_invents_no_bl():
    base, meta = _population()
    roles = base["MOGH_ITEM_ROLE"].tolist()
    assert roles.count("FIRST") == 2          # the first material on each of the order's two BLs
    assert roles.count("ADDITIONAL") == 1 and roles.count("NO_ORDER") == 1
    extra = base[base["MOGH_ITEM_ROLE"].eq("ADDITIONAL")].iloc[0]
    assert extra["KEY_BL"] == ""              # which BL carries B-2 is not recorded
    orphan = base[base["MOGH_ITEM_ROLE"].eq("NO_ORDER")].iloc[0]
    assert orphan["PRIMARY_POPULATION_KEY"] == "MATERIAL:IK88888888"
    assert meta["unique_primary_orders"] == 1


def test_order_level_money_is_not_multiplied_by_materials():
    base, _ = _population()
    # 3 rows carry order 823107D; the order's PI is 150, not 450
    assert base["MOGH_PI_VALUE_SUM"].sum() > 150
    assert safe_agg(base, "MOGH_PI_VALUE_SUM", "sum") == 150


def test_case_rows_drop_only_material_repeats():
    base, _ = _population()
    cases = case_rows(base)
    assert set(cases["MOGH_ITEM_ROLE"]) == {"FIRST", "NO_ORDER"}
    assert len(cases) == len(base) - 1
    legacy = base.drop(columns=["MOGH_ITEM_ROLE"])
    assert len(case_rows(legacy)) == len(legacy)


def test_bl_grain_average_ignores_material_rows_without_bl():
    df = pd.DataFrame({"KEY_BL": ["BL1", "", ""], "MOGH_ITEM_ROLE": ["FIRST", "ADDITIONAL", "NO_ORDER"],
                       "روزهای رسوب": [90.0, 0.0, 0.0]})
    # ADDITIONAL has no BL by design; the order-less case is an independent entity
    assert safe_agg(df, "روزهای رسوب", "mean") == 45.0


def _kpi_frame():
    return pd.DataFrame({
        "KEY_REG": ["R1", "R1", ""],
        "MOGH_ITEM_ROLE": ["FIRST", "ADDITIONAL", "NO_ORDER"],
        "مانده تعهد": [1000.0, 1000.0, None],
        "جریمه برآوردی": [10.0, 10.0, None],
        "وضعیت کلی هشدار": ["قرمز", "قرمز", "سبز"],
        "روزهای رسوب": [120.0, 0.0, 0.0],
        "درصد قطعیت": [80.0, 60.0, 20.0],
        "انحراف فرآیند": ["فعالیت جاافتاده", "فعالیت جاافتاده", "شاهد کافی نداریم"],
        "امتیاز انطباق (٪)": [50.0, 50.0, None],
    })


def test_case_level_kpis_count_each_case_once():
    from gsi.stages.s50_commitment import CommitmentStage
    from gsi.stages.s60_narrate import NarrateStage
    from gsi.stages.s85_conformance import ConformanceStage
    df = _kpi_frame()
    ctx = SimpleNamespace(rb=SimpleNamespace(status_label=lambda _: "قرمز"),
                          extras={})
    commit = CommitmentStage().kpis(df, ctx)
    assert commit["تعهدات با هشدار قرمز"][0] == 1        # one commitment, not two
    assert commit["جمع مانده تعهد"][0] == 1000.0
    narr = NarrateStage().kpis(df, ctx)
    assert narr["میانگین روزهای رسوب"][0] == 60.0        # (120 + 0) / 2 cases
    assert narr["میانگین قطعیت داده (٪)"][0] == 53.3      # a row measure — every material
    conf = ConformanceStage().kpis(df, ctx)
    assert conf["پرونده‌های منحرف از مسیر استاندارد"][0] == 1
    assert conf["پرونده بدون شاهد کافی"][0] == 1


def _mart_for_sheets():
    return pd.DataFrame({
        "ORG_VICE": ["م"] * 4, "ORG_DEPT": ["د"] * 4, "ORG_MANAGER": ["x"] * 4, "ORG_HEAD": ["y"] * 4,
        "CANONICAL_EXPERT": ["م.محمدی", "م.محمدی", "مریم احمدی", "علی رضایی"],
        "KEY_EMP": ["1", "1", "2", "3"],
        "CANONICAL_BL": ["BL1", "", "", ""],
        "CANONICAL_REG": ["R1", "R1", "", ""],
        "KEY_REG": ["R1", "R1", "", ""],
        "MOGH_ITEM_ROLE": ["FIRST", "ADDITIONAL", "NO_ORDER", "FIRST"],
        "BL_CRITICAL": [True, False, False, False],
        "روزهای رسوب": [159.0, 0.0, 0.0, 0.0],
        "امتیاز ریسک": [60.0, 50.0, 27.5, 20.0],
        "مانده تعهد": [100.0, 100.0, None, None],
        "NTSW_CURRENCY": ["CNY", "CNY", "", ""],
        "وضعیت کلی هشدار": ["قرمز", "قرمز", "سبز", "سبز"],
    })


def test_scorecard_keeps_every_bl_less_case_and_counts_only_real_bls(tmp_path):
    b = ExcelDashboardBuilder(str(tmp_path / "s.xlsx"))
    b.build_scorecard(_mart_for_sheets())
    ws = b.wb[SHEET_SCORECARD]
    rows = {ws.cell(r, 5).value: [ws.cell(r, c).value for c in range(1, 14)]
            for r in range(2, ws.max_row + 1) if ws.cell(r, 5).value}
    # two BL-less cases of two experts were collapsed into one arbitrary row before
    assert {"م.محمدی", "مریم احمدی", "علی رضایی"} <= set(rows)
    mohammadi = rows["م.محمدی"]
    assert mohammadi[6] == 1                 # one real BL; the material row adds none
    assert mohammadi[8] == 159.0             # its demurrage is the BL's, not diluted by a 0
    assert rows["مریم احمدی"][6] == 0        # a case without BL has no BL


def test_commitment_register_lists_a_commitment_once(tmp_path):
    b = ExcelDashboardBuilder(str(tmp_path / "c.xlsx"))
    b.build_commitment(_mart_for_sheets())
    ws = b.wb[SHEET_COMMIT]
    regs = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
    assert regs.count("R1") == 1


def test_process_evidence_does_not_repeat_order_stages_for_material_rows():
    t = _expert()
    obs, _, _ = build_process_inventory({"moghavemat": {"main": t["main"]}})
    per_row = obs.groupby("SOURCE_ROW_REF")["STAGE_CODE"].apply(set)
    refs = sorted(per_row.index, key=lambda r: int(r.split(":")[1]))
    first, extra = per_row[refs[0]], per_row[refs[1]]
    assert "SOURCE_OBSERVATION" in extra          # the row is preserved and traceable
    assert extra == {"SOURCE_OBSERVATION"}        # ...but the order's stages are counted once
    assert len(first) > 1


def test_trust_bl_key_missing_is_not_inflated_by_material_rows():
    from gsi.trust.contracts import BL, KEYLESS_BY_DESIGN
    col, vals = KEYLESS_BY_DESIGN[BL]
    assert col == "MOGH_ITEM_ROLE" and "ADDITIONAL" in vals and "NO_ORDER" not in vals


def test_cashflow_emits_an_orders_pi_once_however_many_materials(tmp_path):
    """The financial workspace reads the expert main frame directly; a
    three-material order is one PI registration, not three (and no
    «duplicate removed» notice is manufactured for it)."""
    from gsi.cashflow.dwh import bundle_from_dwh
    from gsi.cashflow.engine import build_cashflow
    from gsi.warehouse.business_dwh import build as build_business_dwh
    from gsi.warehouse.store import Warehouse
    main = pd.DataFrame([{"KEY_ORDER": "O1", "MOGH_PI_VALUE_SUM": 120, "MOGH_CURRENCY": "EUR",
                          "MOGH_PO_SENT_DATE": "2026-07-01", "MOGH_ITEM_ROLE": role,
                          "MOGH_MATERIAL": f"M{i}"}
                         for i, role in enumerate(["FIRST", "ADDITIONAL", "ADDITIONAL"])])
    sources = {
        "moghavemat": {"main": main},
        "ntsw": {"import_license": pd.DataFrame([{"KEY_REG": "11111111", "KEY_REG_FILE": "900000001"}])},
        "ilappend": {"main": pd.DataFrame([{"KEY_ORDER": "O1", "KEY_REG_FILE": "900000001",
                                            "IL_KEY_REG": ""}])},
    }
    wh = Warehouse(tmp_path / "warehouse.sqlite")
    with wh.run({"reference_date": "2026-09-22", "version": "test"}) as rid:
        build_business_dwh(wh, sources, rid)
    wh.publish(rid, slots=("dwh", "report"))
    bundle = bundle_from_dwh("2026-09-22", wh)
    reg = bundle["events"][bundle["events"]["kind"].eq("REGISTRATION")]
    assert len(reg) == 1 and float(reg.iloc[0]["amount"]) == 120.0
    result = build_cashflow(bundle["events"], measurements=bundle["measurements"], as_of="2026-09-22")
    assert "DUPLICATE_REMOVED" not in set(result["issues"]["code"])
