# -*- coding: utf-8 -*-
"""V26.18 regression: chart catalog, no silent HTML truncation, email composer and durable DW."""
from __future__ import annotations
import os, sqlite3, tempfile, json, re, zipfile
from pathlib import Path

import pandas as pd

from gsi.studio_core.chart_catalog import CHART_TITLES
from gsi.studio_core.html_export import build_dynamic_html
from gsi.integrations.daily_email import build_email_html
from gsi.warehouse.historical_store import Warehouse, warehouse_from_settings
from gsi.studio_core.excel_export import build_custom_excel


def sample(n=3000):
    return pd.DataFrame({
        "CASE_KEY":[f"C{i}" for i in range(n)],
        "KEY_MATERIAL":[f"M{i%80}" for i in range(n)],
        "CANONICAL_ORDER":[f"O{i%120}" for i in range(n)],
        "CANONICAL_BL":[f"B{i%60}" for i in range(n)],
        "ORG_DEPT":["خرید" if i%2 else "گمرک" for i in range(n)],
        "CANONICAL_EXPERT":[f"E{i%15}" for i in range(n)],
        "TRANSPORT_MODE":["دریایی" if i%3 else "هوایی" for i in range(n)],
        "ORDER_STAGE_FA":[["خرید","حمل","گمرک","ورود"][i%4] for i in range(n)],
        "بحرانی (کوتاه)":["بحرانی" if i%11==0 else "ایمن" for i in range(n)],
        "مقاومت (روز)":[float(i%50) for i in range(n)],
        "مقاومت انبار (روز)":[float(i%25) for i in range(n)],
        "روزهای رسوب":[float(i%90) for i in range(n)],
        "مانده تعهد":[float((i%40)*1000) for i in range(n)],
        "روزهای تأخیر":[float(i%70) for i in range(n)],
    })


def run():
    df=sample()
    html=build_dynamic_html(df,"2026-09-15",max_rows=3000,
        selected_fields=["KEY_MATERIAL","ORG_DEPT","بحرانی (کوتاه)","مقاومت (روز)"],
        charts=["criticality","stage_distribution","transport_mix","commitment","top_orders"],show_process=True,
        tabs=[{"id":"main","title":"اصلی","fields":["KEY_MATERIAL","ORG_DEPT"],
               "blocks":["table","charts","process"],"process_views":["flow_map"]}])
    assert '"payload_rows": 3000' in html, "3000 rows must stay in payload"
    start=html.index("const DATA=")+len("const DATA=")
    payload,_=json.JSONDecoder().raw_decode(html[start:])
    assert len(payload)==3000, "embedded payload must really contain all 3000 rows"
    assert "برای پایداری مرورگر، 900" not in html
    assert "PAGE_SIZE=100" in html and "COL_INDEX" in html, "pagination + compact payload required"
    # Copy changed in the process-explorer redesign; the contract is that an
    # empty event log renders an explicit reason, never a fabricated map.
    assert "نقشه مسیر مشاهده‌شده" in html and "Event Log کافی برای ساخت مسیر مشاهده‌شده موجود نیست" in html
    assert "توزیع مرحله فعلی" in html
    assert len(CHART_TITLES) >= 15, "shared chart catalog must provide real choice"
    from gsi.studio_core.chart_catalog import CHART_SPECS
    assert {x.kind for x in CHART_SPECS.values()} >= {"bar","donut","scatter","grouped"}
    for k in ("criticality","stage_distribution","transport_mix","commitment","top_orders"):
        assert CHART_TITLES[k] in html
    assert "پشتیبانی تولید خودرو" in html and "AUTOMOTIVE SUPPLY CHAIN" in html

    mail=build_email_html(pd.Timestamp("2026-09-15").date(),df.head(20),[],Path("2026-09-15_AIBL_Interactive_Report.html"),
        header_title="هدر اختصاصی مدیر",intro_text="متن اختصاصی ایمیل")
    assert "هدر اختصاصی مدیر" in mail and "متن اختصاصی ایمیل" in mail
    assert "IRANSans" in mail and "زنجیره تأمین" in mail

    td=Path(tempfile.mkdtemp(prefix="aibl2618_")); db=td/"warehouse.sqlite3"
    # Native Excel charts must carry Persian/RTL drawing metadata and IRANSans.
    xp=td/"fa_charts.xlsx"
    build_custom_excel(df.head(120),xp,["criticality","resistance","commitment","org","expert","table"],
                       "2026-09-15",email_charts=["low_resistance","org_workload","commitment"])
    with zipfile.ZipFile(xp) as z:
        charts=[z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("xl/charts/chart")]
    assert charts and all("IRANSans" in x and 'rtl="1"' in x and "fa-IR" in x for x in charts)
    assert any("کمترین مقاومت" in x or "بار کاری" in x or "مانده تعهد" in x for x in charts)

    wh=Warehouse(db); wh.save_profile("email_composer","مدیر",{"to":"a@example.com","cc":"b@example.com"})
    assert wh.load_profile("email_composer","مدیر")["cc"]=="b@example.com"
    # Force metadata back one schema version then re-open: migration must keep data/profile and create backup.
    with sqlite3.connect(db) as con:
        con.execute("UPDATE dw_meta SET value='1' WHERE key='schema_version'"); con.commit()
    wh2=Warehouse(db)
    assert wh2.load_profile("email_composer","مدیر")["to"]=="a@example.com"
    backups=list((td/"warehouse_backups").glob("*.sqlite3"))
    assert backups, "schema migration backup missing"
    # A package release change also gets a one-time backup even if schema stays unchanged.
    with sqlite3.connect(db) as con:
        con.execute("UPDATE dw_meta SET value='26.17.0' WHERE key='package_version'"); con.commit()
    before=len(list((td/"warehouse_backups").glob("*.sqlite3")))
    wh3=Warehouse(db)
    after=len(list((td/"warehouse_backups").glob("*.sqlite3")))
    assert after==before+1 and wh3.load_profile("email_composer","مدیر")["cc"]=="b@example.com"
    # Release directory may change, but the durable pointer must resolve the same DB.
    old_home=os.environ.get("AIBL_HOME")
    try:
        os.environ["AIBL_HOME"]=str(td/"stable_home")
        hp=Path(os.environ["AIBL_HOME"]); hp.mkdir(parents=True,exist_ok=True)
        (hp/"warehouse.path").write_text(str(db),encoding="utf-8")
        assert warehouse_from_settings().path == db.resolve()
    finally:
        if old_home is None: os.environ.pop("AIBL_HOME",None)
        else: os.environ["AIBL_HOME"]=old_home
    print("نتیجه: 21 موفق | 0 ناموفق")
    return 0

if __name__=="__main__": raise SystemExit(run())
