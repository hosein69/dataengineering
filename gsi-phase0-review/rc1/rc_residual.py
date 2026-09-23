# -*- coding: utf-8 -*-
"""RC residual checks: SWIFT_SENT stage registration, NaN->0 downstream, FIN_RECEIPT_DATE."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.resolve.process_evidence import STAGES, _STAGE_POS, _STAGE_FA, build_process_inventory
from gsi.stages.s20_derive import DeriveStage, DERIVED
res = {}
res["SWIFT_SENT_in_STAGES"] = "SWIFT_SENT" in _STAGE_POS
res["SWIFT_SENT_label"] = _STAGE_FA.get("SWIFT_SENT", "<no label>")

credit = pd.DataFrame([{ "KEY_REG":"88000001","KEY_ORDER":"ORD-A","CRD_SWIFT_DATE":"1405/03/01",
                         "CRD_STATUS":"ارسال شد","CRD_FUND_DATE":"","CRD_RIAL_AMOUNT":""}])
obs, cases, matrix = build_process_inventory({"credit": {"main": credit}})
res["observation_stage_codes"] = sorted(set(obs["STAGE_CODE"]))
res["stage_matrix_codes_include_swift"] = ("SWIFT_SENT" in set(matrix["STAGE_CODE"])) if not matrix.empty else False
res["case_current_focus"] = cases["CURRENT_FOCUS_STAGE"].tolist() if not cases.empty else []
res["case_status"] = cases["PROCESS_STATUS"].tolist() if not cases.empty else []

# NaN -> 0 through DeriveStage for the multi-currency allocation / PI value
class Ctx:
    extras = {}
df = pd.DataFrame([{ "NTSW_ALLOCATED_AMOUNT": float("nan"), "NTSW_BALANCE": float("nan"),
                     "MOGH_PI_VALUE_SUM": float("nan"), "KEY_ORDER":"O1"}])
out = DeriveStage().run(df, Ctx())
res["ALLOCATED_AMOUNT_from_NaN"] = out["ALLOCATED_AMOUNT"].tolist()
res["BALANCE_from_NaN"] = out["BALANCE"].tolist()
res["CB_VALUE_from_NaN"] = out["CB_VALUE"].tolist()
res["FIN_RECEIPT_DATE_values"] = out["FIN_RECEIPT_DATE"].tolist()
res["FIN_RECEIPT_DATE_candidates"] = DERIVED["FIN_RECEIPT_DATE"][0]
res["derive_missing_recorded"] = len(Ctx.extras.get("derive_missing", []))
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
