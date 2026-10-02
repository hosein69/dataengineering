# -*- coding: utf-8 -*-
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html

def test_dynamic_html_has_story_process_and_excel():
    df=pd.DataFrame({
        "KEY_MATERIAL":["M1","M2"],"CANONICAL_ORDER":["O1","O2"],
        "بحرانی (کوتاه)":["بحرانی","ایمن"],"مقاومت (روز)":[4,50],
        "روزهای رسوب":[12,2],"ORG_DEPT":["A","B"]
    })
    extras={
      "bottlenecks":pd.DataFrame({"از فعالیت":["ثبت سفارش"],"به فعالیت":["تخصیص ارز"],
                                  "میانه روز":[14],"صدک ۹۰ روز":[21],"بیشینه روز":[30],"تعداد پرونده":[2]}),
      "stage_queue":pd.DataFrame({"مرحله جاری":["تخصیص ارز"],"تعداد پرونده":[3],
                                  "میانه انتظار (روز)":[19],"بیشترین انتظار (روز)":[40]}),
      "variants":pd.DataFrame({"VARIANT":["A → B"],"تعداد پرونده":[2],"سهم (٪)":[100],
                               "پرونده بسته":[1],"میانه چرخه":[20]}),
      "conformance_root_causes":pd.DataFrame({"بُعد":["گمرک"],"اثر تفاضلی (واحد درصد)":[12.5]})
    }
    h=build_dynamic_html(df,"2026-09-15",selected_fields=list(df.columns),
                         charts=["criticality","low_resistance","stock_vs_total"],
                         process_extras=extras,max_rows=100)
    # ناحیه‌ها را می‌سنجیم، نه یک عنوان را: عنوان‌ها عمداً عوض می‌شوند،
    # ولی این نواحی قرارداد صفحه‌اند و باید باشند.
    assert 'id="story"' in h and 'id="story_scr"' in h
    assert 'id="process_variants"' in h and 'id="process_roots"' in h
    assert "downloadFilteredXlsx" in h
    assert "PROC.bottlenecks" in h and "PROC.stage_queue" in h
    assert "GSI_filtered_" in h
    assert "IRANSans" in h
    # صف جاری باید در صفحه رندر شود — همان چیزی که جدول گذار نشان نمی‌داد.
    assert "صف جاری" in h
    # هیچ ادعای علّی از روی همبستگی در **متن دیده‌شده** نمانده باشد.
    # کامنت‌های JS که تاریخچه را توضیح می‌دهند استثنا هستند، وگرنه تست،
    # توضیح را با ادعا اشتباه می‌گیرد.
    import re as _re
    visible = _re.sub(r"/\*.*?\*/", "", h, flags=_re.S)
    assert "علت ریشه‌ای انحراف" not in visible
    assert "عوامل همراه با انحراف" in visible
    assert "همبستگی نشان می‌دهد، نه علت" in visible


def test_inline_json_cannot_break_script_context():
    payload = "</script><script>window.__gsi_pwned=1</script>"
    df = pd.DataFrame({"KEY_MATERIAL": ["M1"], "ORG_DEPT": ["A"]})
    extras = {"bottlenecks": pd.DataFrame({"از فعالیت": [payload],
                                              "به فعالیت": ["B"],
                                              "میانه روز": [1]})}
    h = build_dynamic_html(
        df, "2026-09-19", selected_fields=list(df.columns),
        labels={"KEY_MATERIAL": payload}, process_extras=extras,
    )
    # Any literal closing script sequence originating in data would terminate
    # the host script in the HTML parser before JS gets a chance to parse JSON.
    assert payload not in h
    assert "<\\/script><script>window.__gsi_pwned=1<\\/script>" in h

def _run_direct():
    ok = fail = 0
    for fn in [test_dynamic_html_has_story_process_and_excel, test_inline_json_cannot_break_script_context]:
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
