"""Oracle: union every sheet that carries a part key; archive every sheet.

The two production sheets are disjoint partitions of the part universe, not two
renderings of the same rows: on the real file they share **zero** part numbers.
Choosing one sheet therefore discarded every part that lived only in the other —
measured at 3 of 4 parts on the real input. Sheets are unioned instead, and where
one part does appear in more than one sheet the value is resolved per field from
the sheet that actually carries it. Nothing is invented: a field empty everywhere
stays empty, never zero.

User-excluded columns never enter standardized Oracle data or business rules;
they are listed in ``EXCLUDED_HEADERS`` so the rule survives a future alias.
"""
from __future__ import annotations
__contract__ = 1
import pandas as pd
from .base import KEY_MATERIAL,SourceAdapter,register
from ..warehouse.excel import header_normal
from ..warehouse.store import Warehouse
from ..core.text import clean_part_no
from ..warehouse.numeric import number

@register
class OracleAdapter(SourceAdapter):
    key,prefix='oracle','ORC'
    COLUMN_MAP={
      'PART_NO':['شماره فنی'], 'MATERIAL_CODE':['کد جنس'],
      'MATERIAL_DESC':['شرح جنس','شرح قطعه'], 'SUPPLY_GROUP':['گروه تامین'],
      'BUILD_GROUP':['گروه ساخت'],'PLANNING_GROUP':['گروه برنامه ریزی'],
      'PART_GROUP':['گروه قطعه'],'PART_CLASS':['رده بندی قطعه','EI / NEI'],
      'FOREIGN_SHARE':['درصد سهم خرید خارجی','درصد خرید خارجی'],
      'ALTERNATIVE':['کد آلترناتیو','آلترناتیو1'],
      'STOCK_IKCO':['موجودی انبار ایران خودرو'], 'STOCK_SAPCO':['موجودی انبار ساپکو'],
      'CARS_ON_FLOOR':['تعداد خودرو کف'],
      'DAILY_NEED':['نیاز روزانه قطعات','میانگین نیاز روزانه (عدد)','نیاز روزانه']}
    # Operator-excluded source headers. Listed explicitly rather than relied on
    # being absent from COLUMN_MAP, so adding an alias cannot silently readmit one.
    EXCLUDED_HEADERS={'وضعیت','قطعه بحرانی','شماره نامه','تاریخ ثبت','توضیحات',
                      'شماره پرسنلی','کارشناس خرید خارجی','ریسک پذیری','column18'}
    ESSENTIAL=['STOCK_IKCO','STOCK_SAPCO','DAILY_NEED']
    NUMERIC=ESSENTIAL+['CARS_ON_FLOOR','FOREIGN_SHARE']
    def transform(self,sheets):
        ranked=[]
        for name,df in sheets.items():
            lookup={header_normal(c):c for c in df.columns
                    if header_normal(c).lower() not in self.EXCLUDED_HEADERS}
            part=lookup.get('شماره فنی')
            if part is None:continue
            out=pd.DataFrame(index=df.index)
            for target,aliases in self.COLUMN_MAP.items():
                col=next((lookup[header_normal(a)] for a in aliases if header_normal(a) in lookup),None)
                out[self.p(target)]=df[col] if col else None
            out[KEY_MATERIAL]=df[part].map(clean_part_no)
            for f in self.NUMERIC:out[self.p(f)]=out[self.p(f)].map(number)
            valid=out[KEY_MATERIAL].fillna('').ne('')
            essential=out.loc[valid,[self.p(f) for f in self.ESSENTIAL]]
            score=float(essential.notna().mean().mean()) if valid.any() else 0.0
            complete=int(essential.notna().all(axis=1).sum())
            for c in ('_SOURCE_ROW','_SOURCE_FILE_ID'):out[c]=df[c] if c in df else df.index if c=='_SOURCE_ROW' else ''
            out['ORC_SOURCE_SHEET']=name
            ranked.append((score,complete,int(valid.sum()),name,out,valid))
        if not ranked:return {}
        # Highest essential completeness first: that sheet wins a field-level tie.
        ranked.sort(key=lambda r:(-r[0],-r[1],-r[2],r[3]))
        wh=Warehouse()
        parts=[]
        for score,complete,nvalid,name,out,valid in ranked:
            if (~valid).any():
                wh.issue('ORACLE_MISSING_KEY',{'sheet':name,'rows':out.index[~valid].tolist()})
            kept=out.loc[valid].copy()
            if kept[KEY_MATERIAL].duplicated().any():
                wh.issue('ORACLE_DUPLICATE_MATERIAL',{'sheet':name,'keys':kept.loc[kept[KEY_MATERIAL].duplicated(False),KEY_MATERIAL].tolist()})
                raise ValueError('اوراکل دارای شماره فنی تکراری است؛ بدون تعیین سطح موجودی تجمیع نمی‌شود.')
            parts.append((name,kept))
        union=pd.concat([k for _,k in parts],ignore_index=True) if parts else pd.DataFrame()
        overlap=[]
        if not union.empty and union[KEY_MATERIAL].duplicated().any():
            # One part present in several sheets: resolve per field, best sheet first.
            fields=[c for c in union.columns if c not in (KEY_MATERIAL,'ORC_SOURCE_SHEET')]
            merged=[]
            for key,grp in union.groupby(KEY_MATERIAL,sort=False):
                if len(grp)==1:
                    merged.append(grp.iloc[0]);continue
                overlap.append({'material':key,'sheets':grp['ORC_SOURCE_SHEET'].tolist()})
                row=grp.iloc[0].copy()
                for f in fields:
                    if pd.isna(row.get(f)) or str(row.get(f)).strip()=='':
                        filled=grp[f].dropna()
                        filled=filled[filled.astype(str).str.strip().ne('')]
                        if len(filled):row[f]=filled.iloc[0]
                row['ORC_SOURCE_SHEET']=' + '.join(dict.fromkeys(grp['ORC_SOURCE_SHEET']))
                merged.append(row)
            union=pd.DataFrame(merged).reset_index(drop=True)
            wh.issue('ORACLE_SHEET_OVERLAP',{'resolved':overlap})
        wh.audit('oracle_union',{
            'sheets':[{'sheet':n,'rows':int(len(k))} for n,k in parts],
            'union_rows':int(len(union)),
            'overlapping_materials':len(overlap),
            'method':'union all sheets on part key; per-field fill from the sheet that carries a value; tie broken by essential_nonnull_ratio',
            'policy':'no sheet discarded; empty stays empty (never zero); all sheets retained raw'})
        return {'main':union}
