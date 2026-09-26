from pathlib import Path
import json
import pytest

from gsi.knowledge_desk import KnowledgeDeskConfig, build_index, publish_static, validate_paths
from gsi.knowledge_desk.lessons import discover_lessons


def cfg(tmp_path, knowledge, lessons, publish):
    return KnowledgeDeskConfig(
        knowledge_path=str(knowledge),
        lessons_path=str(lessons),
        publish_path=str(publish),
        db_path=str(tmp_path/'kb.sqlite'),
        enabled=True,
    )


def test_generated_chatbot_is_never_lesson(tmp_path):
    lessons=tmp_path/'lessons'; lessons.mkdir()
    (lessons/'chatbot.html').write_text('<style>body{color:red}</style><h1>GSI bot</h1>', encoding='utf-8')
    (lessons/'weekly_lessons.json').write_text('{}', encoding='utf-8')
    (lessons/'1405-W01.md').write_text('# تخصیص ارز\nاین یک آموزش واقعی است.', encoding='utf-8')
    got=discover_lessons(str(lessons))
    assert len(got)==1
    assert got[0]['id']=='1405-W01.md'
    assert 'body{color:red}' not in got[0]['body']


def test_exact_publish_source_overlap_blocked(tmp_path):
    src=tmp_path/'same'; src.mkdir()
    c=cfg(tmp_path, src, tmp_path/'lessons', src)
    v=validate_paths(c)
    assert not v['ok']
    assert any(x['code']=='PUBLISH_EQUALS_SOURCE' for x in v['issues'])


def test_empty_knowledge_does_not_publish_false_success(tmp_path):
    k=tmp_path/'knowledge'; k.mkdir()
    l=tmp_path/'lessons'; l.mkdir()
    out=tmp_path/'out'
    c=cfg(tmp_path,k,l,out)
    build_index(c)
    with pytest.raises(RuntimeError, match='BLOCKED_EMPTY_KNOWLEDGE'):
        publish_static(c)
    assert not (out/'chatbot.html').exists()


def test_publish_child_of_knowledge_is_safe_and_not_reindexed(tmp_path):
    k=tmp_path/'knowledge'; k.mkdir()
    l=tmp_path/'lessons'; l.mkdir()
    (k/'faq.md').write_text('# FAQ\nپاسخ معتبر بازرگانی برای ثبت سفارش.',encoding='utf-8')
    (l/'week.md').write_text('# آموزش هفته\nنکات ثبت سفارش.',encoding='utf-8')
    out=k/'_GSI_CHATBOT'
    c=cfg(tmp_path,k,l,out)
    s1=build_index(c); p1=publish_static(c)
    assert p1['documents']>=2 and p1['chunks']>0
    s2=build_index(c)
    idx=json.loads((out/'knowledge_index.json').read_text(encoding='utf-8'))
    assert all('chatbot.html' not in x['source'] for x in idx['chunks'])
    assert all('knowledge_index.json' not in x['source'] for x in idx['chunks'])
