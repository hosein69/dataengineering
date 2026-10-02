# -*- coding: utf-8 -*-
"""End-to-end process evidence projection; never deletes source observations."""
from __future__ import annotations

import pandas as pd

from .base import Stage, PipelineContext, ColumnSpec, GROUP_DETAIL, register
from ..resolve.process_evidence import build_process_inventory, attach_process_state, source_observation_inventory
from ..dataio.logging_setup import log
from ..config.sources import get_source


@register
class ProcessIntegrityStage(Stage):
    name = "process_integrity"
    title = "یکپارچگی زنجیره فرایند و حفظ شواهد"
    order = 54
    tolerant = True
    requires = []
    provides = [
        "PROCESS_CASE_ID", "PROCESS_CASE_COUNT", "PROCESS_STATUS",
        "PROCESS_CURRENT_STAGE", "PROCESS_CURRENT_OWNER", "PROCESS_GAPS",
        "PROCESS_LAST_EVIDENCE_DATE", "PROCESS_EVIDENCE_COUNT",
    ]

    def run(self, df: pd.DataFrame, ctx: PipelineContext) -> pd.DataFrame:
        providers = {
            "PLANNING_PR": ("sap",),
            "EXPERT_INTAKE": ("moghavemat",), "ORDER_CREATED": ("moghavemat",),
            "REGISTRATION": ("ntsw",), "ALLOCATION_REQUEST": ("ntsw",),
            "ALLOCATION": ("ntsw",), "COMMITMENT": ("ntsw",), "SETTLEMENT": ("ntsw",),
            "FX_PURCHASE": ("fx_transaction",), "FUNDING": ("credit",), "SWIFT_SENT": ("credit",),
            "PAYMENT": ("fx_transaction", "credit"), "SHIPMENT": ("abbasi", "sata"),
            "CUSTOMS": ("cotage", "clearance"), "CLEARANCE": ("cotage", "clearance"),
            "BANK_DOCS": ("doccheck", "credit"),
        }
        unmeasured = set()
        for stage, srcs in providers.items():
            measurable = False
            for src in srcs:
                frames = (ctx.sources or {}).get(src) or {}
                has_data = any(isinstance(x, pd.DataFrame) and not x.empty for x in frames.values())
                try:
                    incomplete = str(get_source(src).opt("diagnostic_status", "")).strip().lower() == "known_incomplete"
                except Exception:
                    incomplete = False
                if has_data and not incomplete:
                    measurable = True
                    break
            if not measurable:
                unmeasured.add(stage)
        obs, cases, matrix = build_process_inventory(ctx.sources, unmeasured_stages=unmeasured)
        ctx.extras["process_unmeasured_stages"] = sorted(unmeasured)
        ctx.extras["process_evidence"] = obs
        ctx.extras["process_cases"] = cases
        ctx.extras["process_stage_matrix"] = matrix
        orphans = obs[obs.get("EVIDENCE_STATE", pd.Series(index=obs.index, dtype=str)).eq("ORPHAN_NO_BUSINESS_KEY")].copy() if not obs.empty else pd.DataFrame()
        ctx.extras["process_orphan_evidence"] = orphans
        inventory = source_observation_inventory(ctx.sources or {})
        generic = obs.loc[obs.get("STAGE_CODE", pd.Series(index=obs.index, dtype=str)).eq("SOURCE_OBSERVATION")].copy() if not obs.empty else pd.DataFrame()
        preserved_refs = set(generic.get("SOURCE_ROW_REF", pd.Series(dtype=str)).astype(str)) if not generic.empty else set()
        expected_refs = set(inventory.get("unique_refs", set()))
        missing_refs = sorted(expected_refs - preserved_refs)
        unexpected_refs = sorted(preserved_refs - expected_refs)
        generic_rows = int(len(preserved_refs))
        expected_source_rows = int(len(expected_refs))
        ctx.extras["process_evidence_summary"] = {
            "expected_native_rows": expected_source_rows,
            "preserved_source_observations": generic_rows,
            "candidate_frame_rows": int(inventory.get("candidate_frame_rows", expected_source_rows)),
            "physical_ref_dedup_rows": int(inventory.get("duplicate_ref_rows", 0)),
            "physical_ref_collision_count": int(inventory.get("duplicate_ref_count", 0)),
            "expected_by_source": dict(inventory.get("by_source_unique", {})),
            "missing_source_ref_count": int(len(missing_refs)),
            "unexpected_source_ref_count": int(len(unexpected_refs)),
            "missing_source_ref_sample": missing_refs[:12],
            "unexpected_source_ref_sample": unexpected_refs[:12],
            "orphan_no_business_key": int(len(orphans)),
            "process_cases": int(len(cases)),
            "stage_rows": int(len(matrix)),
            "row_preservation_ok": bool(not missing_refs and not unexpected_refs),
        }
        out = attach_process_state(df, obs, cases)
        log.info(f"🧭 [process-integrity] {len(cases)} پرونده فرایندی | {len(obs)} شاهد | "
                 f"{int((matrix.get('STATUS', pd.Series(dtype=str))=='EVIDENCE_GAP').sum()) if not matrix.empty else 0} شکاف صریح | "
                 f"{len(orphans)} شاهد بدون کلید (حفظ‌شده برای اتصال بعدی)")
        return out

    def columns(self):
        return [
            ColumnSpec("PROCESS_STATUS", "وضعیت زنجیره فرایند", 22, GROUP_DETAIL, order=65),
            ColumnSpec("PROCESS_CURRENT_STAGE", "تمرکز جاری فرایند", 22, GROUP_DETAIL, order=66),
            ColumnSpec("PROCESS_CURRENT_OWNER", "حوزه مسئول جاری", 18, GROUP_DETAIL, order=67),
            ColumnSpec("PROCESS_GAPS", "شکاف‌های شواهد فرایند", 36, GROUP_DETAIL, wrap=True, order=68),
            ColumnSpec("PROCESS_EVIDENCE_COUNT", "تعداد شواهد فرایند", 14, GROUP_DETAIL, order=69),
        ]
