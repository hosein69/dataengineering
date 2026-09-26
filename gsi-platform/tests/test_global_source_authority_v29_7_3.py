# -*- coding: utf-8 -*-
import pandas as pd

from gsi.config.authority import (PRIMARY_SOURCES, SECONDARY_SOURCES,
                                  policy_dict, sort_columns,
                                  sort_source_candidates, source_tier)
from gsi.resolve.canonical import CanonicalEntityResolver
from gsi.stages.base import PipelineContext
from gsi.stages.s20_derive import DeriveStage


def test_policy_is_full_report_and_primary_sources_are_expert_ntsw():
    p = policy_dict()
    assert p['scope'] == 'full_report'
    assert tuple(p['tier_1']) == PRIMARY_SOURCES == ('moghavemat', 'ntsw')
    assert tuple(p['tier_2']) == SECONDARY_SOURCES == ('abbasi', 'sata')
    assert source_tier('moghavemat') == source_tier('ntsw') == 1
    assert source_tier('abbasi') == source_tier('sata') == 2


def test_canonical_conflict_uses_expert_over_abbasi_and_oracle():
    df = pd.DataFrame([{
        'KEY_BL': 'ABB-BL-1', 'MOGH_BL_NO': 'EXP-BL-1',
        'KEY_ORDER': '602164B', 'MOGH_ORDER_REF': '602999B',
        'ORC_MATERIAL_DESC': 'شرح اوراکل', 'MOGH_MATERIAL_DESC': 'شرح کارشناسان',
    }])
    r = CanonicalEntityResolver()
    bl = r.resolve(df, 'شماره بارنامه', [('KEY_BL','abbasi'),('MOGH_BL_NO','moghavemat')], is_key=True)
    desc = r.resolve(df, 'شرح کالا', [('ORC_MATERIAL_DESC','oracle'),('MOGH_MATERIAL_DESC','moghavemat')])
    assert bl.iloc[0] == 'EXP-BL-1'
    assert desc.iloc[0] == 'شرح کارشناسان'


def test_canonical_reg_uses_ntsw_over_sata():
    df = pd.DataFrame([{'KEY_BL':'BL000001','KEY_ORDER':'602164B',
                        'NTSW_KEY_REG':'11111111','SATA_KEY_REG':'22222222'}])
    out = CanonicalEntityResolver().resolve(
        df, 'ثبت سفارش', [('SATA_KEY_REG','sata'),('NTSW_KEY_REG','ntsw')], is_key=True)
    assert out.iloc[0] == '11111111'


def test_derived_global_sort_primary_then_secondary_then_fallback():
    # Deliberately pass old/wrong order: authority must reorder it.
    assert sort_columns(['SATA_FX_SOURCE','FX_FX_SOURCE','NTSW_FX_SOURCE']) == [
        'NTSW_FX_SOURCE','SATA_FX_SOURCE','FX_FX_SOURCE']
    assert sort_source_candidates([('a','oracle'),('b','abbasi'),('c','moghavemat')]) == [
        ('c','moghavemat'),('b','abbasi'),('a','oracle')]


def test_derive_stage_applies_policy_to_whole_report_fields():
    df = pd.DataFrame([{
        # Material description: expert must beat Oracle.
        'MOGH_MATERIAL_DESC':'شرح کارشناسان', 'ORC_MATERIAL_DESC':'شرح اوراکل',
        # FX source: NTSW must beat SATA.
        'NTSW_FX_SOURCE':'مرکز مبادله NTSW', 'SATA_FX_SOURCE':'منبع SATA',
        # Commitment value: NTSW must beat complementary FX value.
        'NTSW_INITIAL_COMMIT':120, 'FX_CB_VALUE':999,
        # Invoice value has no tier-1 candidate; SATA (tier 2) must beat clearance.
        'SATA_INVOICE_VALUE':50, 'CL_INVOICE_VALUE':70,
    }])
    ctx = PipelineContext(rb=None, today=None, resolver=CanonicalEntityResolver())
    out = DeriveStage().run(df, ctx)
    assert out.loc[0,'MATERIAL_DESC'] == 'شرح کارشناسان'
    assert out.loc[0,'FX_SOURCE'] == 'مرکز مبادله NTSW'
    assert float(out.loc[0,'CB_VALUE']) == 120.0
    assert float(out.loc[0,'INVOICE_VALUE']) == 50.0


def test_secondary_only_fills_primary_blank():
    df = pd.DataFrame([{
        'MOGH_MATERIAL_DESC':'', 'ORC_MATERIAL_DESC':'شرح اوراکل',
        'NTSW_FX_SOURCE':'', 'SATA_FX_SOURCE':'منبع SATA',
    }])
    ctx = PipelineContext(rb=None, today=None, resolver=CanonicalEntityResolver())
    out = DeriveStage().run(df, ctx)
    assert out.loc[0,'MATERIAL_DESC'] == 'شرح اوراکل'
    assert out.loc[0,'FX_SOURCE'] == 'منبع SATA'


def test_order_format_cannot_override_higher_authority_expert():
    df = pd.DataFrame([{'KEY_BL':'BL000001', 'KEY_ORDER':'12345678',
                        'MOGH_ORDER_REF':'602164B'}])
    out = CanonicalEntityResolver().resolve(
        df, 'شماره سفارش', [('KEY_ORDER','abbasi'),('MOGH_ORDER_REF','moghavemat')], is_key=True)
    assert out.iloc[0] == '602164B'


def test_ntsw_reg_file_hub_builds_primary_order_reg_without_sata():
    from gsi.resolve.registration_bridge import build_ntsw_order_reg_bridge
    sources = {
        'ntsw': {'import_license': pd.DataFrame([{
            'KEY_REG_FILE':'900000001','KEY_REG':'11111111','NTSW_KEY_REG':'11111111','KEY_ORDER':''
        }])},
        'ilappend': {'main': pd.DataFrame([{
            'KEY_REG_FILE':'900000001','KEY_ORDER':'602164B','KEY_REG':'22222222'
        }])},
        'sata': {'main': pd.DataFrame([{'KEY_ORDER':'602164B','SATA_KEY_REG':'33333333'}])},
    }
    bridge, diag = build_ntsw_order_reg_bridge(sources)
    assert diag.empty
    assert len(bridge) == 1
    assert bridge.iloc[0]['KEY_ORDER'] == '602164B'
    assert bridge.iloc[0]['NTSW_KEY_REG'] == '11111111'
    assert bridge.iloc[0]['NTSW_REG_AUTHORITY_PATH'] == 'NTSW_REG_FILE_HUB'


def test_full_report_base_uses_ntsw_reg_over_conflicting_sata():
    from datetime import date
    from gsi.pipeline import Pipeline

    p = Pipeline(today=date(2026, 9, 22))
    p.sources = {
        'abbasi': {'main': pd.DataFrame([{'KEY_BL':'BL000001','KEY_ORDER':'602164B'}])},
        'sata': {'main': pd.DataFrame([{'KEY_BL':'BL000001','KEY_ORDER':'602164B',
                                       'SATA_KEY_REG':'22222222'}])},
        'moghavemat': {'main': pd.DataFrame([{'KEY_ORDER':'602164B','MOGH_ORDER_REF':'602164B',
                                              'MOGH_MATERIAL_DESC':'شرح کارشناسان'}])},
        'ntsw': {
            'import_license': pd.DataFrame([{'KEY_ORDER':'602164B','KEY_REG':'11111111',
                                             'NTSW_KEY_REG':'11111111','KEY_REG_FILE':'900000001'}]),
            'commitment': pd.DataFrame(),
            'allocation': pd.DataFrame(),
        },
        'ilappend': {'main': pd.DataFrame([{'KEY_ORDER':'602164B','KEY_REG_FILE':'900000001',
                                            'IL_KEY_REG':'33333333'}])},
    }
    p.ctx.sources = p.sources
    out = p.build_base()
    assert out.loc[0, 'NTSW_KEY_REG'] == '11111111'
    assert out.loc[0, 'SATA_KEY_REG'] == '22222222'
    assert out.loc[0, 'KEY_REG'] == '11111111'
