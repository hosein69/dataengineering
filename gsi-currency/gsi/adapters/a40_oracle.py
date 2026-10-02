"""Oracle: union every sheet that carries a part key; archive every sheet.

The Oracle workbook can contain two useful sheets.  They are coverage/fallback
sources, never additive sources.  Materials that exist in only one sheet are kept.
If the same material exists in both sheets, exactly one row is selected from the
more complete sheet; values are never summed or filled across sheets.  This avoids
double-counting stock/demand and avoids creating synthetic hybrid rows.  Missing
stays missing, never zero.

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
                dup_keys=kept.loc[kept[KEY_MATERIAL].duplicated(False),KEY_MATERIAL].astype(str).tolist()
                wh.issue('ORACLE_DUPLICATE_MATERIAL',{
                    'sheet':name,
                    'keys':list(dict.fromkeys(dup_keys)),
                    'policy':'exact duplicate rows are removed; inventory quantities are summed by material; daily need is max; descriptive fields use first non-empty value'
                })
                kept=self._collapse_material_grain(kept,name,wh)
            parts.append((name,kept))
        union=pd.concat([k for _,k in parts],ignore_index=True) if parts else pd.DataFrame()
        overlap=[]
        if not union.empty and union[KEY_MATERIAL].duplicated().any():
            # A material may exist in both Oracle sheets.  The sheets are NOT
            # additive and must never be blended field-by-field.  Select one
            # complete source row for the material and keep the other only as
            # evidence.  This prevents stock/demand from being doubled or a
            # synthetic hybrid row from being created.
            business_fields=[c for c in union.columns
                             if c not in (KEY_MATERIAL,'ORC_SOURCE_SHEET',
                                          '_SOURCE_ROW','_SOURCE_FILE_ID')]
            essential_cols=[self.p(f) for f in self.ESSENTIAL]
            merged=[]
            for key,grp in union.groupby(KEY_MATERIAL,sort=False):
                if len(grp)==1:
                    merged.append(grp.iloc[0]);continue
                candidates=[]
                for idx,row in grp.iterrows():
                    ess=sum(pd.notna(row.get(c)) and str(row.get(c)).strip()!=''
                            for c in essential_cols)
                    filled=sum(pd.notna(row.get(c)) and str(row.get(c)).strip()!=''
                               for c in business_fields)
                    candidates.append((ess,filled,idx,row))
                candidates.sort(key=lambda x:(-x[0],-x[1],x[2]))
                chosen=candidates[0][3].copy()

                # Oracle workbook policy (approved on real data): Sheet1 and
                # SAPCO_IK are alternative observations of the same part, not
                # additive ledgers.  Never SUM the same stock field across sheets.
                # For stock and demand choose the greatest valid observation; this
                # also implements DAILY_NEED = max(«نیاز روزانه قطعات»,
                # «میانگین نیاز روزانه (عدد)») while a single non-empty value wins
                # automatically when the other sheet is blank.
                for field in (self.p('STOCK_IKCO'), self.p('STOCK_SAPCO'),
                              self.p('DAILY_NEED'), self.p('CARS_ON_FLOOR')):
                    if field in grp.columns:
                        vals=pd.to_numeric(grp[field],errors='coerce')
                        if vals.notna().any():
                            chosen[field]=vals.max()
                            chosen[field + '_SOURCE_SHEETS'] = ' | '.join(sorted(set(grp.loc[vals.eq(vals.max()), 'ORC_SOURCE_SHEET'].astype(str))))
                # Foreign share is a ratio, not additive. Keep the greatest
                # populated observation so the value stays conservative and
                # report-selectable in Studio.
                fs=self.p('FOREIGN_SHARE')
                if fs in grp.columns:
                    vals=pd.to_numeric(grp[fs],errors='coerce')
                    if vals.notna().any():
                        chosen[fs]=vals.max()
                        chosen[fs + '_SOURCE_SHEETS'] = ' | '.join(sorted(set(grp.loc[vals.eq(vals.max()), 'ORC_SOURCE_SHEET'].astype(str))))

                # Preserve explicit evidence of the two Oracle demand headers.
                for _,r in grp.iterrows():
                    sh=str(r.get('ORC_SOURCE_SHEET','')).strip()
                    if sh.lower() in ('sheet1','sheet 1','1'):
                        chosen['ORC_DAILY_NEED_SHEET1']=r.get(self.p('DAILY_NEED'))
                    if 'sapco' in sh.lower() and 'ik' in sh.lower():
                        chosen['ORC_DAILY_NEED_SAPCO_IK']=r.get(self.p('DAILY_NEED'))
                overlap.append({
                    'material':key,
                    'sheets':grp['ORC_SOURCE_SHEET'].astype(str).tolist(),
                    'chosen_sheet':str(chosen.get('ORC_SOURCE_SHEET','')),
                    'policy':'no_cross_sheet_sum; stock/daily_need=max_valid_observation'
                })
                merged.append(chosen)
            union=pd.DataFrame(merged).reset_index(drop=True)
            wh.issue('ORACLE_SHEET_OVERLAP',{'resolved':overlap})
        wh.audit('oracle_union',{
            'sheets':[{'sheet':n,'rows':int(len(k))} for n,k in parts],
            'union_rows':int(len(union)),
            'overlapping_materials':len(overlap),
            'method':'union disjoint materials; overlap uses non-additive field resolution',
            'policy':'never SUM across Oracle sheets; STOCK_IKCO/STOCK_SAPCO/DAILY_NEED choose max valid observation; DAILY_NEED compares Sheet1 vs SAPCO_IK; empty stays empty (never zero)'})
        return {'main':union}

    def _collapse_material_grain(self, frame: pd.DataFrame, sheet: str, wh: Warehouse) -> pd.DataFrame:
        """Resolve repeated part numbers inside one Oracle sheet without inventing data.

        Production Oracle can carry more than one row for a part because stock is
        split across inventory buckets/locations while daily demand is repeated on
        those rows.  Treating that as a fatal duplicate loses the whole source.

        Policy (same business grain used by the earlier validated AIBL adapter):
          * exact duplicate standardized rows are removed first;
          * STOCK_IKCO / STOCK_SAPCO / CARS_ON_FLOOR are additive and are summed;
          * DAILY_NEED is non-additive and uses max (it is repeated per stock row);
          * FOREIGN_SHARE and descriptive fields use first non-empty value;
          * conflicting non-additive values are audited, never silently summed.
        """
        if frame.empty or not frame[KEY_MATERIAL].duplicated().any():
            return frame

        # Remove byte-for-byte logical duplicates before any additive aggregation.
        # Provenance columns are excluded from the equality key because duplicated
        # business rows may have different Excel row numbers.
        provenance={'_SOURCE_ROW','_SOURCE_FILE_ID','ORC_SOURCE_SHEET'}
        logical=[c for c in frame.columns if c not in provenance]
        before=len(frame)
        work=frame.drop_duplicates(subset=logical,keep='first').copy()
        exact_removed=before-len(work)

        additive={self.p('STOCK_IKCO'),self.p('STOCK_SAPCO'),self.p('CARS_ON_FLOOR')}
        daily=self.p('DAILY_NEED')
        nonadditive=[c for c in work.columns if c not in additive|{daily,KEY_MATERIAL,'_SOURCE_ROW','_SOURCE_FILE_ID','ORC_SOURCE_SHEET'}]

        conflicts=[]
        rows=[]
        for material,grp in work.groupby(KEY_MATERIAL,sort=False,dropna=False):
            if len(grp)==1:
                rows.append(grp.iloc[0].copy())
                continue
            row=grp.iloc[0].copy()
            for c in additive:
                if c in grp.columns:
                    vals=pd.to_numeric(grp[c],errors='coerce')
                    row[c]=vals.sum(min_count=1)
            if daily in grp.columns:
                vals=pd.to_numeric(grp[daily],errors='coerce')
                row[daily]=vals.max() if vals.notna().any() else pd.NA
            for c in nonadditive:
                if c not in grp.columns:
                    continue
                vals=grp[c].dropna()
                vals=vals[vals.astype(str).str.strip().ne('')]
                if len(vals):
                    row[c]=vals.iloc[0]
                    unique=list(dict.fromkeys(vals.astype(str).tolist()))
                    if len(unique)>1:
                        conflicts.append({'material':str(material),'field':c,'values':unique[:10]})
            if '_SOURCE_ROW' in grp.columns:
                row['_SOURCE_ROW']=' | '.join(dict.fromkeys(grp['_SOURCE_ROW'].astype(str).tolist()))
            if '_SOURCE_FILE_ID' in grp.columns:
                row['_SOURCE_FILE_ID']=' | '.join(dict.fromkeys(grp['_SOURCE_FILE_ID'].astype(str).tolist()))
            rows.append(row)

        out=pd.DataFrame(rows).reset_index(drop=True)
        wh.audit('oracle_material_grain_resolution',{
            'sheet':sheet,
            'input_rows':before,
            'exact_duplicates_removed':exact_removed,
            'output_materials':int(len(out)),
            'duplicate_materials_resolved':int((work.groupby(KEY_MATERIAL).size()>1).sum()),
            'nonadditive_conflicts':conflicts[:100],
            'policy':'stock/cars=sum; daily_need=max; descriptive=first_nonempty; exact logical duplicates removed first'
        })
        return out
