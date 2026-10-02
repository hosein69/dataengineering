import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
from gsi.adapters.a40_oracle import OracleAdapter


def test_oracle_merges_two_sheets_preferring_full_data():
    a = pd.DataFrame({
        'شماره فني':['100','200'], 'موجودي انبار ايران خودرو':[10,20],
        'موجودي انبار ساپکو':[1,2], 'نياز روزانه قطعات':[5,10],
        'شرح جنس':['A',''], 'گروه قطعه':['X','Y']})
    b = pd.DataFrame({
        'شماره فني':['100','200'], 'موجودي انبار ايران خودرو':[10,99],
        'موجودي انبار ساپکو':[1,9], 'نياز روزانه قطعات':[5,10],
        'شرح جنس':['A2','B'], 'گروه قطعه':['X2','Y']})
    out = OracleAdapter().transform({'موجودی':a,'مصرف':b})['main']
    r = out.set_index('KEY_MATERIAL')
    assert r.loc['100','ORC_STOCK_IKCO'] == 10
    assert r.loc['200','ORC_STOCK_IKCO'] == 99
    assert r.loc['200','ORC_MATERIAL_DESC'] == 'B'
    assert 'ORC_SOURCE_SHEET' in out.columns

def _run_direct():
    ok = fail = 0
    for fn in [test_oracle_merges_two_sheets_preferring_full_data]:
        try:
            fn()
            ok += 1
            print(f"✅ {fn.__name__}")
        except Exception as ex:
            fail += 1
            print(f"❌ {fn.__name__} → {type(ex).__name__}: {ex}")
    print(f"نتیجه: {ok} موفق | {fail} ناموفق")
    return 1 if fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(_run_direct())
