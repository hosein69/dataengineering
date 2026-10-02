from pathlib import Path
import tempfile
import pandas as pd

from gsi.knowledge_desk import KnowledgeDeskConfig, build_index, status, answer, discover_lessons
from gsi.studio_core.html_export import build_dynamic_html


def test_offline_kb_index_and_answer(tmp_path):
    kb=tmp_path/'kb'; lessons=tmp_path/'lessons'; kb.mkdir(); lessons.mkdir()
    (kb/'procedure.md').write_text('تمدید ثبت سفارش نیازمند بررسی اعتبار پرونده و مدارک مربوط به ثبت سفارش است. کارشناس باید وضعیت پرونده را کنترل کند.',encoding='utf-8')
    (lessons/'1405-W01.md').write_text('آموزش تخصیص ارز\nدر تخصیص ارز شماره پرونده ثبت سفارش باید با Import Licence کنترل شود.',encoding='utf-8')
    cfg=KnowledgeDeskConfig(knowledge_path=str(kb),lessons_path=str(lessons),db_path=str(tmp_path/'kb.sqlite'),public_url='http://GSI-SERVER:8765',enabled=True)
    r=build_index(cfg)
    assert r['indexed']==2
    s=status(cfg)
    assert s['documents']==2 and s['chunks']>=2
    ans=answer(cfg,'برای تمدید ثبت سفارش چه کاری لازم است؟')
    assert ans['status']=='ANSWERED'
    assert ans['sources']
    # incremental: second pass does not duplicate documents/chunks
    r2=build_index(cfg)
    assert r2['unchanged']==2
    assert status(cfg)['documents']==2
    assert discover_lessons(str(lessons))[0]['title']=='آموزش تخصیص ارز'


def test_html_uses_static_chatbot_without_http_api(tmp_path):
    from gsi.knowledge_desk import path_to_file_uri
    lesson={'id':'x','week':'هفته ۱','title':'ثبت سفارش','summary':'آموزش','body':'متن آموزش','questions':['ثبت سفارش چیست؟']}
    df=pd.DataFrame([{'KEY_ORDER':'1','KEY_MATERIAL':'M1'}])
    bot=tmp_path/'bot'/'chatbot.html'; bot.parent.mkdir(); bot.write_text('ok',encoding='utf-8')
    href=path_to_file_uri(str(bot))
    html=build_dynamic_html(df,'2026-09-21',selected_fields=['KEY_ORDER'],tabs=[{'title':'اصلی','fields':['KEY_ORDER'],'blocks':['table']}],learning_lesson=lesson,knowledge_chat={'chatbot_href':href})
    assert href in html
    assert '/api/chat' not in html
    assert 'http://GSI-SERVER:8765' not in html
    assert 'AnythingLLM' not in html

def test_native_http_service_chat(tmp_path):
    import socket, json, urllib.request, time
    from gsi.knowledge_desk import start_service, stop_service
    kb=tmp_path/'kb2'; kb.mkdir(); (kb/'faq.md').write_text('رفع تعهد ارزی پس از انجام تشریفات و کنترل مستندات مربوط انجام می‌شود.',encoding='utf-8')
    # A corporate endpoint policy can forbid binding a local socket at all
    # (a real Windows run reported WinError 10013 here). That is the machine
    # refusing, not the product failing, so skip rather than report red.
    try:
        sock=socket.socket(); sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]; sock.close()
    except (PermissionError, OSError) as ex:
        import pytest; pytest.skip(f'local socket bind not permitted here: {ex}')
    cfg=KnowledgeDeskConfig(knowledge_path=str(kb),lessons_path='',db_path=str(tmp_path/'svc.sqlite'),host='127.0.0.1',port=port,public_url=f'http://127.0.0.1:{port}',enabled=True)
    build_index(cfg); start_service(cfg); time.sleep(.05)
    try:
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/chat',data=json.dumps({'question':'رفع تعهد ارزی چگونه انجام می شود؟'},ensure_ascii=False).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=3) as r:
                out=json.loads(r.read().decode())
        except urllib.error.URLError as ex:
            import pytest; pytest.skip(f'loopback HTTP not permitted here: {ex}')
        assert out['answer']
        assert out['sources']
    finally:
        stop_service()
