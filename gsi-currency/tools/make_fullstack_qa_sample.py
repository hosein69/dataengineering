"""Build deterministic synthetic HTML for browser regression checks."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html

def create(target):
    df=pd.DataFrame([{'KEY_MATERIAL':f'MAT-{i:03d}','ORC_PART_NO':f'MAT-{i:03d}',
        'MOGH_MATERIAL':f'MAT-{i:03d}','ORC_MATERIAL_DESC':'قطعه آزمایشی',
        'MOGH_COMMERCIAL_NOTE':'پیگیری کارشناسی '+str(i),
        'ORC_STOCK_IKCO':60,'ORC_STOCK_SAPCO':40,'ORC_DAILY_NEED':20,
        'CANONICAL_ORDER':'999999999999999999','KEY_REG':str(12000000+i),
        'NTSW_BALANCE':100,'NTSW_CURRENCY':'EUR','NTSW_RELEASE_STATUS':'رفع تعهد نشده'} for i in range(175)])
    df.loc[0,'MOGH_COMMERCIAL_NOTE']='</script><script>window.UNSAFE=1</script>'
    h=build_dynamic_html(df,'2026-09-21',title='داده آزمایشی — تست فول‌استک',max_rows=5,
       selected_fields=['KEY_MATERIAL','CANONICAL_ORDER','NTSW_BALANCE'],
       tabs=[{'id':'financial','title':'مالی آزمایشی','fields':['KEY_MATERIAL','CANONICAL_ORDER','NTSW_BALANCE'],'blocks':['kpi','table']}])
    Path(target).write_text(h,encoding='utf-8')
if __name__=='__main__': create(sys.argv[1])
