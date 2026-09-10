# -*- coding: utf-8 -*-
"""Launcher for AIBL Studio modular platform."""
from __future__ import annotations
import argparse, os, socket, subprocess, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
def free_port(start=8501,tries=40):
    for p in range(start,start+tries):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',p))!=0:return p
    return start
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=0);a=ap.parse_args();
    try: import streamlit
    except ImportError: print('Streamlit نصب نیست');return 1
    p=a.port or free_port()
    # تم صریح — مستقل از اینکه فایل پیکربندی سر جایش باشد یا نه.
    sys.path.insert(0,ROOT)
    from app.theme import theme_env
    env=dict(os.environ,PYTHONPATH=ROOT,PYTHONUTF8='1',**theme_env())
    print(f'AIBL Studio: http://localhost:{p} (app/studio.py)')
    return subprocess.call([sys.executable,'-m','streamlit','run',os.path.join(HERE,'studio.py'),'--server.port',str(p),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env)
if __name__=='__main__':sys.exit(main())
