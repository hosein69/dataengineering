import argparse
import json
from pathlib import Path
from .store import Warehouse
from .service import ingest_file
p=argparse.ArgumentParser(description='GSI SQLite warehouse')
s=p.add_subparsers(dest='command',required=True)
i=s.add_parser('ingest');i.add_argument('source',choices=['oracle','ntsw','fx_transaction','headers_map']);i.add_argument('file')
b=s.add_parser('backup');b.add_argument('destination')
s.add_parser('check')
r=s.add_parser('reset',help='پاک‌کردن کامل انبار داده و ساخت دوباره از صفر')
r.add_argument('--yes',action='store_true',help='تأیید صریح حذف؛ بدون آن چیزی پاک نمی‌شود')
r.add_argument('--backup-to',help='مسیر نسخه پشتیبان؛ پیش‌فرض کنار همان فایل با مهر زمان')
r.add_argument('--no-backup',action='store_true',help='بدون پشتیبان — فقط وقتی پشتیبان جداگانه دارید')
a=p.parse_args()
if a.command=='ingest':print(ingest_file(a.file,a.source))
elif a.command=='backup':print(Warehouse().backup(a.destination))
elif a.command=='reset':
    wh=Warehouse(initialize=False)
    if not a.yes:
        print(f'انبار داده: {wh.path}')
        print('این دستور همه اجراها، فریم‌ها، snapshotها و خروجی‌های منتشرشده را پاک می‌کند.')
        print('برای اجرا: python -m gsi.warehouse reset --yes')
        raise SystemExit(2)
    out=wh.reset(confirm=True,backup_to=a.backup_to,keep_backup=not a.no_backup)
    print(json.dumps(out,ensure_ascii=False,indent=2))
    print('انبار داده خالی و آمادهٔ ساخت دوباره است. اجرای بعدی خط لوله آن را پر می‌کند.')
else:
 with Warehouse().db() as c:
  print('integrity_check:',c.execute('PRAGMA integrity_check').fetchone()[0])
  print('foreign_key_check:',c.execute('PRAGMA foreign_key_check').fetchall())
  print('runs:',c.execute('SELECT status,count(*) FROM wh_run GROUP BY status').fetchall())
