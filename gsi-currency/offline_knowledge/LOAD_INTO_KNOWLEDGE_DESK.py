from __future__ import annotations
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gsi.knowledge_desk.config import KnowledgeDeskConfig
from gsi.knowledge_desk.indexer import build_index,status
p=argparse.ArgumentParser();p.add_argument('--db',default=str(ROOT/'data/offline_knowledge.sqlite'));a=p.parse_args()
cfg=KnowledgeDeskConfig(knowledge_path=str(Path(__file__).resolve().parent),db_path=str(Path(a.db).resolve()),enabled=True)
print(build_index(cfg));print(status(cfg));print('DB:',cfg.db_path)
