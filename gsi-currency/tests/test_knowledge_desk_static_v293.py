from pathlib import Path
import json
import pandas as pd

from gsi.knowledge_desk import KnowledgeDeskConfig, build_index, publish_static, path_to_file_uri
from gsi.studio_core.html_export import build_dynamic_html


def test_static_bundle_zero_server_and_source_privacy(tmp_path):
    kb=tmp_path/'secret_share'; lessons=tmp_path/'lessons'; out=tmp_path/'published'
    kb.mkdir(); lessons.mkdir()
    (kb/'procedure.md').write_text('تمدید ثبت سفارش نیازمند بررسی اعتبار پرونده و مدارک مربوط است.',encoding='utf-8')
    (lessons/'week1.md').write_text('آموزش تخصیص ارز\nشماره پرونده ثبت سفارش باید با Import Licence کنترل شود.',encoding='utf-8')
    cfg=KnowledgeDeskConfig(knowledge_path=str(kb),lessons_path=str(lessons),db_path=str(tmp_path/'kb.sqlite'),publish_path=str(out),enabled=True)
    build_index(cfg)
    pub=publish_static(cfg)
    entry=Path(pub['entrypoint'])
    assert entry.exists()
    assert (out/'knowledge_index.json').exists()
    assert (out/'weekly_lessons.json').exists()
    assert (out/'manifest.json').exists()
    h=entry.read_text(encoding='utf-8')
    assert 'بدون سرور' in h
    assert '/api/chat' not in h
    assert 'http://GSI-SERVER' not in h
    assert str(kb) not in h
    idx=json.loads((out/'knowledge_index.json').read_text(encoding='utf-8'))
    assert idx['chunks']
    assert all(str(kb) not in x.get('source','') for x in idx['chunks'])


def test_report_opens_static_chatbot_with_question(tmp_path):
    chat=tmp_path/'GSI_BOT'/'chatbot.html'; chat.parent.mkdir(); chat.write_text('ok',encoding='utf-8')
    href=path_to_file_uri(str(chat))
    lesson={'id':'x','week':'هفته ۱','title':'ثبت سفارش','summary':'آموزش','body':'متن آموزش','questions':['ثبت سفارش چیست؟']}
    df=pd.DataFrame([{'KEY_ORDER':'1'}])
    h=build_dynamic_html(df,'2026-09-21',selected_fields=['KEY_ORDER'],tabs=[{'title':'اصلی','fields':['KEY_ORDER'],'blocks':['table']}],learning_lesson=lesson,knowledge_chat={'chatbot_href':href})
    assert href.replace('&','&amp;') in h or href in h
    assert '/api/chat' not in h
    assert 'askGsiKnowledge' in h
    assert 'دستیار کاملاً آفلاین' in h


def test_unc_path_to_file_uri():
    uri=path_to_file_uri(r'\\SERVER\Commercial\GSI_BOT\chatbot.html')
    assert uri.startswith('file://SERVER/Commercial/GSI_BOT/chatbot.html')
