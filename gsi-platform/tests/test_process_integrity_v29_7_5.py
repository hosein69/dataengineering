import pandas as pd

from gsi.adapters.a60_finance import SapAdapter
from gsi.adapters.base import KEY_PR, KEY_ORDER, KEY_REG, KEY_BL
from gsi.resolve.process_evidence import build_process_inventory, attach_process_state
from gsi.pipeline import Pipeline
from gsi.stages.base import Stage


def test_sap_preserves_workflow_history_and_latest_projection():
    raw = pd.DataFrame({
        'Purchase Requisition': ['1001','1001','1002'],
        'Changed On': ['2026-01-01','2026-01-05','2026-02-01'],
        'WorkFlow Status': ['Created','Approved','Created'],
        'Action': ['create','approve','create'],
    })
    out = SapAdapter().transform({'Data': raw})
    assert set(out) >= {'main','workflow_rows'}
    assert len(out['workflow_rows']) == 3
    assert len(out['main']) == 2
    row = out['main'][out['main'][KEY_PR].astype(str) == '1001'].iloc[0]
    assert row['SAP_WORKFLOW_STATUS'] == 'Approved'


def test_later_stage_never_hides_missing_predecessor():
    sources = {
        'moghavemat': {'main': pd.DataFrame([{KEY_ORDER:'O1'}])},
        'ntsw': {'import_license': pd.DataFrame([{KEY_ORDER:'O1','NTSW_KEY_REG':'12345678'}])},
        # Shipment is absent, but customs/clearance exists.  Later evidence must
        # survive and the missing predecessor must become an explicit gap.
        'cotage': {'main': pd.DataFrame([{KEY_BL:'BL1','COT_NO':'C1','COT_COTAGE_DATE':'2026-03-01','COT_FULL_CLEAR_DATE':'2026-03-03'}])},
        'sata': {'main': pd.DataFrame([{KEY_ORDER:'O1',KEY_BL:'BL1','SATA_KEY_REG':'12345678'}])},
    }
    obs, cases, matrix = build_process_inventory(sources)
    assert not obs.empty and not cases.empty and not matrix.empty
    cid = cases.iloc[0]['PROCESS_CASE_ID']
    m = matrix[matrix.PROCESS_CASE_ID == cid].set_index('STAGE_CODE')
    assert m.loc['CUSTOMS','STATUS'] in {'OBSERVED','POSITIVE_OBSERVED','NEGATIVE_OBSERVED'}
    assert m.loc['CLEARANCE','STATUS'] in {'OBSERVED','POSITIVE_OBSERVED','NEGATIVE_OBSERVED'}
    # Early planning/expert gaps remain visible instead of erasing later facts.
    assert (m.STATUS == 'EVIDENCE_GAP').any()


def test_sap_only_pr_is_kept_in_process_inventory_without_entering_flat_population_contract():
    sources = {'sap': {'workflow_rows': pd.DataFrame([{KEY_PR:'PR9','SAP_WORKFLOW_STATUS':'Created','SAP_CHANGED_ON':'2026-01-01'}])}}
    obs, cases, matrix = build_process_inventory(sources)
    assert len(cases) == 1
    assert 'PR9' in cases.iloc[0]['PR_KEYS']
    assert (matrix.STAGE_CODE == 'PLANNING_PR').any()


def test_attach_marks_ambiguous_instead_of_guessing():
    obs = pd.DataFrame([
        {'PROCESS_CASE_ID':'PC1','KEY_ORDER':'O1','KEY_PR':'','KEY_REG':'','KEY_REG_FILE':'','KEY_BL':'','KEY_MATERIAL':'','KEY_EMP':''},
        {'PROCESS_CASE_ID':'PC2','KEY_ORDER':'O1','KEY_PR':'','KEY_REG':'','KEY_REG_FILE':'','KEY_BL':'','KEY_MATERIAL':'','KEY_EMP':''},
    ])
    cases = pd.DataFrame([
        {'PROCESS_CASE_ID':'PC1','PROCESS_STATUS':'IN_PROGRESS','CURRENT_FOCUS_STAGE':'REGISTRATION','CURRENT_OWNER':'REGISTRATION','EVIDENCE_GAPS':'','LAST_EVIDENCE_DATE':'','EVIDENCE_COUNT':1},
        {'PROCESS_CASE_ID':'PC2','PROCESS_STATUS':'IN_PROGRESS','CURRENT_FOCUS_STAGE':'REGISTRATION','CURRENT_OWNER':'REGISTRATION','EVIDENCE_GAPS':'','LAST_EVIDENCE_DATE':'','EVIDENCE_COUNT':1},
    ])
    df = pd.DataFrame([{'CANONICAL_ORDER':'O1'}])
    out = attach_process_state(df, obs, cases)
    assert out.loc[0,'PROCESS_CASE_COUNT'] == 2
    assert out.loc[0,'PROCESS_STATUS'] == 'AMBIGUOUS_LINK'
    assert out.loc[0,'PROCESS_CASE_ID'] == ''


class _Boom(Stage):
    name='boom_v2975'; title='boom'; order=1; tolerant=True; requires=[]; provides=['BOOM_COL']
    def run(self, df, ctx):
        raise RuntimeError('isolated failure')

class _After(Stage):
    name='after_v2975'; title='after'; order=2; tolerant=False; requires=[]; provides=['AFTER_COL']
    def run(self, df, ctx):
        df=df.copy(); df['AFTER_COL']='ok'; return df


def test_tolerant_stage_exception_does_not_stop_independent_flow():
    p = Pipeline()
    p.stages = [_Boom(), _After()]
    df = pd.DataFrame([{'x':1},{'x':2}])
    out = p.run_stages(df)
    assert len(out) == 2
    assert out['AFTER_COL'].tolist() == ['ok','ok']
    assert 'BOOM_COL' in out.columns
    assert p.ctx.extras['stage_failures'][0]['stage'] == 'boom_v2975'


def test_keyless_source_row_is_preserved_as_orphan_evidence():
    sources = {'sap': {'workflow_rows': pd.DataFrame([{'SAP_WORKFLOW_STATUS':'Created'}])}}
    obs, cases, matrix = build_process_inventory(sources)
    generic = obs[obs.STAGE_CODE == 'SOURCE_OBSERVATION']
    assert len(generic) == 1
    assert generic.iloc[0]['EVIDENCE_STATE'] == 'ORPHAN_NO_BUSINESS_KEY'
    assert cases.empty
