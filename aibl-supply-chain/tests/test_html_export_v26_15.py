# -*- coding: utf-8 -*-
import pandas as pd
from aibl.studio_core.html_export import build_dynamic_html

def test_dynamic_html_has_story_process_and_excel():
    df=pd.DataFrame({
        "KEY_MATERIAL":["M1","M2"],"CANONICAL_ORDER":["O1","O2"],
        "بحرانی (کوتاه)":["بحرانی","ایمن"],"مقاومت (روز)":[4,50],
        "روزهای رسوب":[12,2],"ORG_DEPT":["A","B"]
    })
    extras={
      "bottlenecks":pd.DataFrame({"از فعالیت":["ثبت سفارش"],"به فعالیت":["تخصیص ارز"],"میانگین روز":[14],"تعداد پرونده":[2]}),
      "variants":pd.DataFrame({"VARIANT":["A → B"],"تعداد پرونده":[2],"سهم (٪)":[100],"میانگین throughput":[20]}),
      "conformance_root_causes":pd.DataFrame({"بُعد":["گمرک"],"اثر تفاضلی (واحد درصد)":[12.5]})
    }
    h=build_dynamic_html(df,"2026-09-15",selected_fields=list(df.columns),
                         charts=["criticality","low_resistance","stock_vs_total"],
                         process_extras=extras,max_rows=100)
    assert "روایت این برش" in h
    assert "downloadFilteredXlsx" in h
    assert "PROC.bottlenecks" in h
    assert "واریانت‌های پرتکرار" in h
    assert "AIBL_filtered_" in h
    assert "IRANSans" in h

if __name__ == "__main__":
    test_dynamic_html_has_story_process_and_excel()
    print("نتیجه: 1 موفق | 0 ناموفق")
