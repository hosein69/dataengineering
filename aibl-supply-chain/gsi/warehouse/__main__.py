import argparse
from pathlib import Path
from .store import Warehouse
from .service import ingest_file
p=argparse.ArgumentParser(description='GSI SQLite warehouse')
s=p.add_subparsers(dest='command',required=True)
i=s.add_parser('ingest');i.add_argument('source',choices=['oracle','ntsw','fx_transaction','headers_map']);i.add_argument('file')
b=s.add_parser('backup');b.add_argument('destination')
s.add_parser('check')
a=p.parse_args()
if a.command=='ingest':print(ingest_file(a.file,a.source))
elif a.command=='backup':print(Warehouse().backup(a.destination))
else:
 with Warehouse().db() as c:
  print('integrity_check:',c.execute('PRAGMA integrity_check').fetchone()[0])
  print('foreign_key_check:',c.execute('PRAGMA foreign_key_check').fetchall())
  print('runs:',c.execute('SELECT status,count(*) FROM wh_run GROUP BY status').fetchall())
