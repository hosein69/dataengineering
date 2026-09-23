# -*- coding: utf-8 -*-
"""Verify RES-1..3 fixes."""
import sys, json, os
import pandas as pd
sys.path.insert(0, os.environ["PKG"])
from gsi.resolve.process_evidence import _STAGE_POS, _STAGE_FA, _STAGE_OWNER, build_process_inventory
from gsi.stages.s20_derive import DeriveStage, UNKNOWN_SENSITIVE, DECLARED_UNMEASURED
res = {}
# RES-1
res["SWIFT_SENT_registered"] = "SWIFT_SENT" in _STAGE_POS
res["SWIFT_SENT_label"] = _STAGE_FA.get("SWIFT_SENT")
res["SWIFT_SENT_owner"] = _STAGE_OWNER.get("SWIFT_SENT")
res["SWIFT_before_PAYMENT"] = _STAGE_POS.get("SWIFT_SENT", 99) < _STAGE_POS.get("PAYMENT", 0)
credit = pd.DataFrame([{ "KEY_REG":"88000001","KEY_ORDER":"ORD-A","CRD_SWIFT_DATE":"1405/03/01",
                         "CRD_STATUS":"ارسال شد","CRD_FUND_DATE":"","CRD_RIAL_AMOUNT":""}])
obs, cases, matrix = build_process_inventory({"credit": {"main": credit}})
res["swift_in_stage_matrix"] = ("SWIFT_SENT" in set(matrix["STAGE_CODE"])) if not matrix.empty else False
res["case_status"] = cases["PROCESS_STATUS"].tolist() if not cases.empty else []
res["case_focus"] = cases["CURRENT_FOCUS_STAGE"].tolist() if not cases.empty else []
res["swift_row_status"] = matrix.loc[matrix["STAGE_CODE"].eq("SWIFT_SENT"),"STATUS"].tolist() if not matrix.empty else []
res["payment_still_absent"] = "PAYMENT" not in set(obs["STAGE_CODE"])

# RES-2 / RES-3
class Ctx: extras = {}
df = pd.DataFrame([
    {"NTSW_ALLOCATED_AMOUNT": float("nan"), "NTSW_BALANCE": float("nan"), "MOGH_PI_VALUE_SUM": float("nan")},
    {"NTSW_ALLOCATED_AMOUNT": 0.0,          "NTSW_BALANCE": 250.0,        "MOGH_PI_VALUE_SUM": 10.0},
])
out = DeriveStage().run(df, Ctx())
res["ALLOCATED_AMOUNT"] = out["ALLOCATED_AMOUNT"].tolist()
res["ALLOCATED_AMOUNT_IS_UNKNOWN"] = out["ALLOCATED_AMOUNT_IS_UNKNOWN"].tolist()
res["BALANCE"] = out["BALANCE"].tolist()
res["BALANCE_IS_UNKNOWN"] = out["BALANCE_IS_UNKNOWN"].tolist()
res["CB_VALUE_IS_UNKNOWN"] = out["CB_VALUE_IS_UNKNOWN"].tolist()
cov = Ctx.extras.get("derive_coverage", {})
res["unknown_defaulted_to_zero"] = cov.get("unknown_defaulted_to_zero")
res["declared_unmeasured"] = cov.get("declared_unmeasured")
res["FIN_RECEIPT_DATE_declared"] = list(DECLARED_UNMEASURED)
res["unreachable_sample"] = (cov.get("unreachable_targets") or [])[:6]
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
