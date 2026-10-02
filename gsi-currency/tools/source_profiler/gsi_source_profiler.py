#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse, hashlib, json, os, re, sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
try:
    import yaml
except ImportError:
    yaml = None

KEY_PATTERNS = {
    "PR": [r"\bpurchase requisition\b", r"\bpr\b", r"درخواست خرید", r"شماره درخواست"],
    "PR_ITEM": [r"item of requisition", r"pr item", r"آیتم درخواست"],
    "PO": [r"purchasing document", r"purchase order", r"\bpo\b", r"سفارش خرید"],
    "PO_ITEM": [r"purchase order item", r"po\.item", r"\bpo item\b"],
    "ORDER": [r"\border\b", r"شماره سفارش(?! خرید)", r"سفارش خارجی"],
    "REG": [r"\breg\b", r"ثبت سفارش", r"registration", r"شماره ثبت"],
    "REG_FILE": [r"reg[_ ]?file", r"شماره پرونده", r"پرونده"],
    "BL": [r"\bbl\b", r"bill of lading", r"بارنامه"],
    "COTTAGE": [r"cottage", r"کوتاژ", r"اظهارنامه"],
    "MATERIAL": [r"\bmaterial\b", r"material code", r"کد کالا", r"کد قطعه"],
    "SUPPLIER": [r"supplier", r"vendor", r"فروشنده", r"تامین کننده", r"تأمین کننده"],
    "WORKFLOW": [r"workflow", r"work flow", r"work_flow", r"گردش کار"],
}
STATUS_PATTERNS = [r"status", r"state", r"release", r"deletion", r"completed", r"blocked", r"مرحله", r"وضعیت", r"تایید", r"تأیید", r"حذف", r"ابطال", r"ترخیص"]
DATE_PATTERNS = [r"date", r"زمان", r"تاریخ", r"changed on", r"created on", r"release"]
AMOUNT_PATTERNS = [r"amount", r"value", r"price", r"مبلغ", r"ارزش", r"بها", r"مانده", r"balance"]
CURRENCY_PATTERNS = [r"currency", r"ارز", r"currency code"]
QUANTITY_PATTERNS = [r"quantity", r"\bqty\b", r"مقدار", r"تعداد"]
TEXT_NULLS = {"", "nan", "none", "null", "nat", "<na>", "n/a", "-"}

def norm_text(v: Any) -> str:
    if v is None: return ""
    return re.sub(r"\s+", " ", str(v).strip())

def norm_col(v: Any) -> str: return norm_text(v).lower()

def is_blank(v: Any) -> bool:
    if v is None: return True
    try:
        if pd.isna(v): return True
    except Exception: pass
    return norm_text(v).lower() in TEXT_NULLS

def matches_any(name: str, patterns: Iterable[str]) -> bool:
    n = norm_col(name)
    return any(re.search(p, n, flags=re.I) for p in patterns)

def classify_column(name: str) -> set[str]:
    roles = set()
    for role, pats in KEY_PATTERNS.items():
        if matches_any(name, pats): roles.add(role)
    if matches_any(name, STATUS_PATTERNS): roles.add("STATUS")
    if matches_any(name, DATE_PATTERNS): roles.add("DATE")
    if matches_any(name, AMOUNT_PATTERNS): roles.add("AMOUNT")
    if matches_any(name, CURRENCY_PATTERNS): roles.add("CURRENCY")
    if matches_any(name, QUANTITY_PATTERNS): roles.add("QUANTITY")
    return roles

@dataclass
class SourceSpec:
    name: str
    path: str
    sheets: Any = "all"
    domain: str = ""
    authority: str = ""
    required: bool = False
    notes: str = ""

def load_config(path: Path) -> list[SourceSpec]:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SourceSpec(**x) for x in data.get("sources", [])]

def safe_slug(s: str) -> str:
    return (re.sub(r"[^\w\-.]+", "_", s, flags=re.UNICODE).strip("_") or "unnamed")[:120]

def read_table(path: Path, sheet: Optional[str] = None) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet, dtype=object)
    if ext == ".csv":
        last = None
        for enc in ("utf-8-sig", "utf-8", "cp1256", "latin1"):
            try: return pd.read_csv(path, dtype=object, encoding=enc, low_memory=False)
            except Exception as e: last = e
        raise last
    if ext in {".parquet", ".pq"}: return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")

def workbook_sheets(path: Path) -> list[Optional[str]]:
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return list(pd.ExcelFile(path).sheet_names)
    return [None]

def selected_sheets(spec: SourceSpec, path: Path) -> list[Optional[str]]:
    available = workbook_sheets(path)
    if spec.sheets in (None, "all", ["all"]): return available
    wanted = spec.sheets if isinstance(spec.sheets, list) else [spec.sheets]
    return [x for x in available if x in wanted]

def semantic_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    out = {}
    for c in df.columns:
        for role in classify_column(str(c)):
            out.setdefault(role, []).append(str(c))
    return out

def series_stats(s: pd.Series) -> dict[str, Any]:
    n = len(s)
    non_null = s[~s.map(is_blank)]
    nunique = int(non_null.astype(str).nunique()) if len(non_null) else 0
    return {"rows": int(n), "non_null": int(len(non_null)), "nulls": int(n-len(non_null)),
            "null_pct": round((n-len(non_null))/n*100,2) if n else 0,
            "unique": nunique, "unique_pct_of_non_null": round(nunique/len(non_null)*100,2) if len(non_null) else 0,
            "examples": [norm_text(x) for x in non_null.head(5).tolist()]}

def candidate_key_score(s: pd.Series) -> float:
    st = series_stats(s)
    if not st["non_null"]: return 0.0
    uniq = st["unique_pct_of_non_null"] / 100
    cov = st["non_null"] / max(st["rows"],1)
    return round(0.65*uniq + 0.35*cov, 4)

def status_profile(df, cols, topn=20):
    out = {}
    for c in cols:
        s = df[c].map(norm_text)
        s = s[~s.str.lower().isin(TEXT_NULLS)]
        out[c] = [{"value": str(k), "count": int(v)} for k,v in s.value_counts().head(topn).items()]
    return out

def row_information_score(row, sem):
    score = 0.0
    for role in ["PR","PR_ITEM","PO","PO_ITEM","ORDER","REG","REG_FILE","BL","COTTAGE","MATERIAL","SUPPLIER","WORKFLOW"]:
        if any(not is_blank(row.get(c)) for c in sem.get(role,[])): score += 3.0
    for c in sem.get("STATUS",[]):
        if not is_blank(row.get(c)): score += 2.0
    for role,w in [("DATE",1.2),("AMOUNT",1.5),("CURRENCY",1.3),("QUANTITY",1.0)]:
        for c in sem.get(role,[]):
            if not is_blank(row.get(c)): score += w
    score += min(sum(not is_blank(v) for v in row.tolist()),30)*0.03
    return score

def select_representative_rows(df, sem, max_rows=18, seed=42):
    if df.empty: return df.copy()
    work = df.copy()
    work["__info_score__"] = work.apply(lambda r: row_information_score(r, sem), axis=1)
    chosen = []
    def add(i):
        if i not in chosen: chosen.append(i)
    for i in work.sort_values("__info_score__", ascending=False).head(max(4,max_rows//3)).index: add(i)
    used = 0
    for c in sem.get("STATUS",[]):
        vals = work[c].map(norm_text)
        for val in vals.value_counts().head(8).index.tolist():
            if not val or val.lower() in TEXT_NULLS: continue
            idxs = work.index[vals.eq(val)].tolist()
            if idxs:
                add(work.loc[idxs].sort_values("__info_score__", ascending=False).index[0]); used += 1
                if used >= max(3,max_rows//3): break
        if used >= max(3,max_rows//3): break
    for role in ["PR","ORDER","REG","MATERIAL"]:
        if not sem.get(role): continue
        c = sem[role][0]
        s = work[c].map(norm_text)
        valid = work[~s.str.lower().isin(TEXT_NULLS)].copy()
        if valid.empty: continue
        vc = valid[c].map(norm_text).value_counts()
        for key in vc[vc>1].head(4).index:
            sub = valid[valid[c].map(norm_text).eq(key)]
            for i in sub.sort_values("__info_score__", ascending=False).head(2).index: add(i)
    sem_cols = sorted({c for cols in sem.values() for c in cols if c in work.columns})
    if sem_cols:
        blanks = work[sem_cols].apply(lambda r: sum(is_blank(x) for x in r), axis=1)
        add(blanks.sort_values(ascending=False).index[0])
    remaining = [i for i in work.index if i not in chosen]
    need = max_rows-len(chosen)
    if need>0 and remaining:
        for i in work.loc[remaining].sample(n=min(need,len(remaining)), random_state=seed).index: add(i)
    chosen = chosen[:max_rows]
    out = df.loc[chosen].copy()
    out.insert(0,"__source_row_index__",[str(i) for i in chosen])
    return out

def infer_grain(sem, df):
    role_sets = [("PR_ITEM",["PR","PR_ITEM"]),("PO_ITEM",["PO","PO_ITEM"]),("ORDER_REG",["ORDER","REG"]),("ORDER_BL",["ORDER","BL"]),("REG",["REG"]),("ORDER",["ORDER"]),("PR",["PR"]),("MATERIAL",["MATERIAL"])]
    candidates=[]
    for label,roles in role_sets:
        if any(not sem.get(r) for r in roles): continue
        cols=[sem[r][0] for r in roles]
        x=df[cols].copy()
        for c in cols: x[c]=x[c].map(norm_text)
        for c in cols: x=x[~x[c].str.lower().isin(TEXT_NULLS)]
        if x.empty: continue
        uniq=x.drop_duplicates().shape[0]
        candidates.append({"label":label,"columns":cols,"non_null_rows":int(len(x)),"distinct_keys":int(uniq),"uniqueness_ratio":round(uniq/len(x),4)})
    candidates.sort(key=lambda x:(x["uniqueness_ratio"],x["non_null_rows"]), reverse=True)
    return {"best_candidate": candidates[0] if candidates else None, "candidates": candidates[:8], "note":"Heuristic only unless source contract explicitly defines grain."}

def relation_examples(df, sem, limit=12):
    pairs=[("PR","PO"),("PR","ORDER"),("PR","MATERIAL"),("ORDER","REG"),("ORDER","BL"),("REG","REG_FILE"),("REG","COTTAGE"),("BL","COTTAGE")]
    out=[]
    for a,b in pairs:
        if not sem.get(a) or not sem.get(b): continue
        ca,cb=sem[a][0],sem[b][0]
        x=df[[ca,cb]].copy(); x[ca]=x[ca].map(norm_text); x[cb]=x[cb].map(norm_text)
        x=x[~x[ca].str.lower().isin(TEXT_NULLS) & ~x[cb].str.lower().isin(TEXT_NULLS)].drop_duplicates()
        if x.empty: continue
        a2b=x.groupby(ca)[cb].nunique(); b2a=x.groupby(cb)[ca].nunique()
        out.append({"from_role":a,"to_role":b,"from_column":ca,"to_column":cb,"distinct_pairs":int(len(x)),"max_to_per_from":int(a2b.max()),"max_from_per_to":int(b2a.max()),"many_from_examples":[{"key":str(k),"linked_count":int(v)} for k,v in a2b[a2b>1].sort_values(ascending=False).head(5).items()],"examples":x.head(limit).to_dict("records"),"assertion":"co-observed in same native source row; not proof of causal/authoritative relation"})
    return out

def duplicate_profile(df, key_cols):
    findings=[]
    for c in key_cols:
        x=df[[c]].copy(); x[c]=x[c].map(norm_text); x=x[~x[c].str.lower().isin(TEXT_NULLS)]
        if x.empty: continue
        dup=x[c].duplicated(keep=False)
        if dup.any():
            counts=x.loc[dup,c].value_counts().head(10)
            findings.append({"columns":[c],"duplicate_rows":int(dup.sum()),"examples":[{"key":str(k),"count":int(v)} for k,v in counts.items()]})
    return findings

def profile_frame(spec,path,sheet,df,sample_rows,out):
    sem=semantic_columns(df)
    schema=[]
    for c in df.columns:
        st=series_stats(df[c]); schema.append({"column":str(c),"roles":sorted(classify_column(str(c))),"dtype":str(df[c].dtype),"candidate_key_score":candidate_key_score(df[c]),**st})
    key_cols=[]
    for role in ["PR","PR_ITEM","PO","PO_ITEM","ORDER","REG","REG_FILE","BL","COTTAGE","MATERIAL","SUPPLIER","WORKFLOW"]: key_cols.extend(sem.get(role,[]))
    key_cols=list(dict.fromkeys(key_cols))
    sample=select_representative_rows(df,sem,sample_rows)
    label=sheet if sheet is not None else "table"; stem=f"{safe_slug(spec.name)}__{safe_slug(label)}"
    (out/"samples").mkdir(parents=True,exist_ok=True); (out/"schemas").mkdir(parents=True,exist_ok=True)
    sp=out/"samples"/f"{stem}__sample.csv"; sample.to_csv(sp,index=False,encoding="utf-8-sig")
    sch={"source":spec.name,"sheet":label,"row_count":int(len(df)),"column_count":int(len(df.columns)),"columns":schema}
    shp=out/"schemas"/f"{stem}__schema.json"; shp.write_text(json.dumps(sch,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"source":spec.name,"path":str(path),"sheet":label,"domain":spec.domain,"authority":spec.authority,"required":spec.required,"notes":spec.notes,"row_count":int(len(df)),"column_count":int(len(df.columns)),"headers":[str(c) for c in df.columns],"semantic_columns":sem,"grain_inference":infer_grain(sem,df),"status_profile":status_profile(df,sem.get("STATUS",[])),"duplicate_profile":duplicate_profile(df,key_cols),"relation_examples":relation_examples(df,sem),"candidate_keys":sorted([{"column":x["column"],"score":x["candidate_key_score"],"roles":x["roles"]} for x in schema if x["candidate_key_score"]>=0.80],key=lambda x:x["score"],reverse=True)[:15],"sample_file":str(sp.relative_to(out)),"schema_file":str(shp.relative_to(out))}

def build_global_key_index(profiles):
    idx={}
    for p in profiles:
        for role,cols in p.get("semantic_columns",{}).items():
            if role in {"STATUS","DATE","AMOUNT","CURRENCY","QUANTITY"}: continue
            for c in cols: idx.setdefault(role,[]).append({"source":p["source"],"sheet":p["sheet"],"column":c,"authority":p.get("authority",""),"domain":p.get("domain","")})
    return {"roles":idx,"candidate_cross_source_join_roles":sorted([k for k,v in idx.items() if len(v)>=2]),"warning":"Shared role across sources is a join candidate only; not proof of authoritative comparability."}

def md_table(rows,cols):
    if not rows: return "_None detected._"
    esc=lambda x:str(x).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for r in rows: lines.append("| "+" | ".join(esc(r.get(c,"")) for c in cols)+" |")
    return "\n".join(lines)

def build_markdown(profiles,key_index,cfg):
    lines=["# GSI Model Context Evidence Pack","",f"Generated: {datetime.now().isoformat(timespec='seconds')}",f"Config: `{cfg}`","","## Interpretation rules","","- Samples maximize process/key/status coverage; they are not statistical samples.","- Grain and relation findings are heuristic unless confirmed by contracts/code.","- Co-observed keys are not automatically authoritative joins.","- Missing evidence must not be interpreted as proof that a process step did not occur.","- Preserve source authority and domain semantics.","","## Cross-source key map",""]
    rows=[]
    for role,refs in key_index.get("roles",{}).items(): rows.append({"Role":role,"Occurrences":len(refs),"Sources":", ".join(sorted({r['source'] for r in refs})),"Columns":"; ".join(f"{r['source']}/{r['sheet']}: {r['column']}" for r in refs[:8])})
    lines.append(md_table(rows,["Role","Occurrences","Sources","Columns"])); lines.append("")
    for p in profiles:
        lines += [f"---\n## Source: {p['source']} / Sheet: {p['sheet']}","",f"- Path: `{p['path']}`",f"- Domain: `{p.get('domain','')}`",f"- Authority: `{p.get('authority','')}`",f"- Rows: **{p['row_count']:,}**",f"- Columns: **{p['column_count']}**",f"- Sample: `{p['sample_file']}`",""]
        g=p.get("grain_inference",{}).get("best_candidate")
        if g: lines += ["### Grain candidate",f"`{g['label']}` using `{', '.join(g['columns'])}` — uniqueness ratio `{g['uniqueness_ratio']}`.",""]
        lines.append("### Semantic columns"); lines.append(md_table([{"Role":k,"Columns":", ".join(v)} for k,v in p.get("semantic_columns",{}).items()],["Role","Columns"])); lines.append("")
        lines.append("### Status values")
        sr=[]
        for c,vals in p.get("status_profile",{}).items():
            for x in vals[:10]: sr.append({"Column":c,"Value":x["value"],"Count":x["count"]})
        lines.append(md_table(sr,["Column","Value","Count"])); lines.append("")
        lines.append("### Co-observed relation candidates")
        rr=[{"From":f"{r['from_role']} ({r['from_column']})","To":f"{r['to_role']} ({r['to_column']})","Pairs":r['distinct_pairs'],"Max fanout":r['max_to_per_from']} for r in p.get("relation_examples",[])]
        lines.append(md_table(rr,["From","To","Pairs","Max fanout"])); lines.append("")
        if p.get("duplicate_profile"):
            lines.append("### Repeated-key signals")
            for d in p["duplicate_profile"][:8]: lines.append(f"- `{d['columns']}` → duplicate rows: **{d['duplicate_rows']}**; examples: `{json.dumps(d['examples'][:3],ensure_ascii=False)}`")
            lines.append("")
    return "\n".join(lines)

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",required=True); ap.add_argument("--output",default="gsi_evidence_pack"); ap.add_argument("--sample-rows",type=int,default=18); args=ap.parse_args()
    cfg=Path(args.config).resolve(); out=Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    specs=load_config(cfg); profiles=[]; errors=[]
    for spec in specs:
        path=Path(os.path.expandvars(os.path.expanduser(spec.path))).resolve()
        if not path.exists():
            errors.append(f"Missing source: {spec.name} -> {path}"); continue
        try:
            for sheet in selected_sheets(spec,path):
                try:
                    df=read_table(path,sheet).dropna(how="all")
                    profiles.append(profile_frame(spec,path,sheet,df,args.sample_rows,out))
                except Exception as e: errors.append(f"{spec.name}/{sheet}: {type(e).__name__}: {e}")
        except Exception as e: errors.append(f"{spec.name}: {type(e).__name__}: {e}")
    idx=build_global_key_index(profiles)
    (out/"source_catalog.json").write_text(json.dumps(profiles,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"process_key_index.json").write_text(json.dumps(idx,ensure_ascii=False,indent=2),encoding="utf-8")
    md=build_markdown(profiles,idx,cfg); (out/"model_context_pack.md").write_text(md,encoding="utf-8")
    summary="# Executive Summary — GSI Source Evidence Pack\n\n"+f"- Profiled frames/sheets: **{len(profiles)}**\n- Total native rows scanned: **{sum(p['row_count'] for p in profiles):,}**\n- Cross-source key roles: **{', '.join(idx.get('candidate_cross_source_join_roles',[])) or 'none detected'}**\n\n## Read order\n1. model_context_pack.md\n2. process_key_index.json\n3. Relevant sample CSVs\n4. Relevant schema JSONs\n\nHeuristic grain/join findings are not business truth until confirmed by contracts or code.\n"
    (out/"executive_summary.md").write_text(summary,encoding="utf-8")
    manifest={"generated_at":datetime.now().isoformat(timespec="seconds"),"config":str(cfg),"profiled_frames":len(profiles),"errors":errors,"files":{}}
    for p in sorted(out.rglob("*")):
        if p.is_file(): manifest["files"][str(p.relative_to(out))]={"bytes":p.stat().st_size,"sha256":sha256_file(p)}
    (out/"run_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Evidence pack written to: {out}"); print(f"Profiled frames: {len(profiles)}"); print(f"Errors: {len(errors)}")
    for e in errors: print("WARN:",e,file=sys.stderr)
    return 0
if __name__=="__main__": raise SystemExit(main())
