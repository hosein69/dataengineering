from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
KB=ROOT/'offline_knowledge'

def test_knowledge_manifest_is_complete_and_immutable():
    m=json.loads((KB/'knowledge_manifest.json').read_text(encoding='utf-8'))
    assert m['files']
    for rel,expected in m['files'].items():
        p=KB/rel
        assert p.is_file(), rel
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected, rel

def test_oracle_ids_unique_and_have_basis():
    x=json.loads((KB/'06_TEST_ORACLE_RULES.json').read_text(encoding='utf-8'))
    ids=[r['id'] for r in x['principles']]
    assert len(ids)==len(set(ids))
    for r in x['principles']:
        assert r['domain'] and r['severity'] in {'LOW','MEDIUM','HIGH','CRITICAL'}
        assert r['statement'] and r['basis']

def test_regulatory_oracles_have_external_provenance():
    src=json.loads((KB/'05_EXTERNAL_SOURCE_REGISTER.json').read_text(encoding='utf-8'))
    ids={s['id']:s for s in src['sources']}
    rules=json.loads((KB/'06_TEST_ORACLE_RULES.json').read_text(encoding='utf-8'))['principles']
    for r in rules:
        if r['domain']=='regulatory':
            refs=[b for b in r['basis'] if b.startswith('SRC-')]
            assert refs, r
            for ref in refs:
                assert ref in ids and ids[ref]['url'].startswith('https://')

def test_no_external_source_claimed_fully_observed_when_access_was_incomplete():
    src=json.loads((KB/'05_EXTERNAL_SOURCE_REGISTER.json').read_text(encoding='utf-8'))['sources']
    by={s['id']:s for s in src}
    assert by['SRC-NTSW']['observed']=='ACCESS_INCOMPLETE'
    assert by['SRC-EPL']['observed']=='ACCESS_INCOMPLETE'

def test_business_contract_document_contains_four_distinct_entities():
    t=(KB/'01_BUSINESS_KEY_CONTRACT_FA.md').read_text(encoding='utf-8')
    for token in ('`REG`','`ORDER`','`REG_FILE`','`BL`'):
        assert token in t
    assert 'موجودیتی مستقل از `REG`' in t
