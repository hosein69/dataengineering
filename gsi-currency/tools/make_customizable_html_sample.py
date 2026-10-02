# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from gsi.studio_core.html_export import build_dynamic_html


def main(out: str = "samples/release_html/GSI_SAMPLE_CUSTOMIZABLE_CASHFLOW.html") -> Path:
    df = pd.DataFrame([
        {"KEY_MATERIAL":"MAT-001","CANONICAL_ORDER":"ORD-001","CANONICAL_BL":"BL-001","KEY_REG":"REG-001","CASE_KEY":"REG-001","CANONICAL_EXPERT":"احمدی","ORG_DEPT":"بازرگانی","TRANSPORT_MODE":"دریایی","بحرانی (کوتاه)":"بحرانی","کد طبقه بحرانی":"CRITICAL","مقاومت (روز)":4,"مقاومت انبار (روز)":2,"روزهای رسوب":55,"مانده تعهد":9.2e9,"روزهای تأخیر":45,"STAGE_FA":"تخصیص ارز"},
        {"KEY_MATERIAL":"MAT-002","CANONICAL_ORDER":"ORD-001","CANONICAL_BL":"BL-001","KEY_REG":"REG-002","CASE_KEY":"REG-002","CANONICAL_EXPERT":"رضایی","ORG_DEPT":"مالی","TRANSPORT_MODE":"هوایی","بحرانی (کوتاه)":"هشدار","کد طبقه بحرانی":"WARNING","مقاومت (روز)":11,"مقاومت انبار (روز)":6,"روزهای رسوب":34,"مانده تعهد":6.4e9,"روزهای تأخیر":30,"STAGE_FA":"تأمین وجه"},
        {"KEY_MATERIAL":"MAT-003","CANONICAL_ORDER":"ORD-002","CANONICAL_BL":"BL-002","KEY_REG":"REG-003","CASE_KEY":"REG-003","CANONICAL_EXPERT":"کاظمی","ORG_DEPT":"لجستیک","TRANSPORT_MODE":"زمینی","بحرانی (کوتاه)":"ایمن","کد طبقه بحرانی":"SAFE","مقاومت (روز)":28,"مقاومت انبار (روز)":15,"روزهای رسوب":18,"مانده تعهد":3.1e9,"روزهای تأخیر":14,"STAGE_FA":"سوئیفت"},
        {"KEY_MATERIAL":"MAT-004","CANONICAL_ORDER":"ORD-003","CANONICAL_BL":"BL-003","KEY_REG":"REG-004","CASE_KEY":"REG-004","CANONICAL_EXPERT":"احمدی","ORG_DEPT":"بازرگانی","TRANSPORT_MODE":"دریایی","بحرانی (کوتاه)":"هشدار","کد طبقه بحرانی":"WARNING","مقاومت (روز)":18,"مقاومت انبار (روز)":9,"روزهای رسوب":22,"مانده تعهد":4.9e9,"روزهای تأخیر":18,"STAGE_FA":"حمل"},
        {"KEY_MATERIAL":"MAT-005","CANONICAL_ORDER":"ORD-004","CANONICAL_BL":"BL-004","KEY_REG":"REG-005","CASE_KEY":"REG-005","CANONICAL_EXPERT":"رضایی","ORG_DEPT":"مالی","TRANSPORT_MODE":"هوایی","بحرانی (کوتاه)":"ایمن","کد طبقه بحرانی":"SAFE","مقاومت (روز)":42,"مقاومت انبار (روز)":24,"روزهای رسوب":9,"مانده تعهد":2.7e9,"روزهای تأخیر":5,"STAGE_FA":"گمرک"},
        {"KEY_MATERIAL":"MAT-006","CANONICAL_ORDER":"ORD-005","CANONICAL_BL":"BL-005","KEY_REG":"REG-006","CASE_KEY":"REG-006","CANONICAL_EXPERT":"کاظمی","ORG_DEPT":"لجستیک","TRANSPORT_MODE":"دریایی","بحرانی (کوتاه)":"ایمن","کد طبقه بحرانی":"SAFE","مقاومت (روز)":63,"مقاومت انبار (روز)":33,"روزهای رسوب":3,"مانده تعهد":1.2e9,"روزهای تأخیر":0,"STAGE_FA":"ترخیص"},
    ])
    acts=["ثبت سفارش","تخصیص ارز","تأمین وجه","سوئیفت","حمل"]
    ev=[]
    for i in range(1,7):
        for j,a in enumerate(acts[:3+(i%3)]):
            ev.append({"_CASE_KEY":f"REG-{i:03d}","CASE_KEY":f"REG-{i:03d}","ACTIVITY_FA":a,"EVENTTIME":f"2026-09-{1+j*4+i%2:02d}T09:00:00"})
    extras={
        "eventlog":pd.DataFrame(ev),
        "stage_queue":pd.DataFrame([{"مرحله جاری":"تخصیص ارز","تعداد پرونده":4,"میانه انتظار (روز)":18,"بیشترین انتظار (روز)":41},{"مرحله جاری":"تأمین وجه","تعداد پرونده":3,"میانه انتظار (روز)":12,"بیشترین انتظار (روز)":28}]),
        "bottlenecks":pd.DataFrame([{"از فعالیت":"ثبت سفارش","به فعالیت":"تخصیص ارز","میانه روز":8.5,"صدک ۹۰ روز":17,"تعداد پرونده":6},{"از فعالیت":"تخصیص ارز","به فعالیت":"تأمین وجه","میانه روز":6.0,"صدک ۹۰ روز":13,"تعداد پرونده":5}]),
        "variants":pd.DataFrame([{"VARIANT":"ثبت سفارش > تخصیص ارز > تأمین وجه > سوئیفت > حمل","تعداد پرونده":4,"سهم (٪)":66.7,"پرونده بسته":3,"میانه چرخه":31},{"VARIANT":"ثبت سفارش > تخصیص ارز > حمل","تعداد پرونده":2,"سهم (٪)":33.3,"پرونده بسته":1,"میانه چرخه":24}]),
        "case_actions":pd.DataFrame([{"CASE_KEY":"REG-001","STATUS":"نیازمند اقدام","NEXT_ACTION":"پیگیری تخصیص ارز","OWNER":"مالی","PRIORITY":"CRITICAL","DAYS_REMAINING":-3,"EVIDENCE_GAPS":"مجوز تکمیلی"},{"CASE_KEY":"REG-002","STATUS":"باز","NEXT_ACTION":"تکمیل تأمین وجه","OWNER":"خزانه","PRIORITY":"HIGH","DAYS_REMAINING":2}]),
        "fx_ledger":pd.DataFrame([{"KEY_REG":"REG-001","FX_NTSW_BALANCE":9.2e9,"FX_NTSW_CURRENCY":"IRR","FX_NTSW_BALANCE_EUR_EQ":130000,"FX_NTSW_BALANCE_RIAL_EQ":9.2e9,"FX_ANOMALY_COUNT":2},{"KEY_REG":"REG-002","FX_NTSW_BALANCE":6.4e9,"FX_NTSW_CURRENCY":"IRR","FX_NTSW_BALANCE_EUR_EQ":91000,"FX_NTSW_BALANCE_RIAL_EQ":6.4e9,"FX_ANOMALY_COUNT":0},{"KEY_REG":"REG-003","FX_NTSW_BALANCE":3.1e9,"FX_NTSW_CURRENCY":"IRR","FX_NTSW_BALANCE_EUR_EQ":44000,"FX_NTSW_BALANCE_RIAL_EQ":3.1e9,"FX_ANOMALY_COUNT":1}]),
        "fx_control_summary":pd.DataFrame([{"KEY_REG":"REG-001","FX_CURRENT_STAGE":"تخصیص ارز","FX_CONTROL_RISK_BAND":"CRITICAL","FX_CONTROL_RISK_SCORE":92,"FX_DEADLINE_STATUS":"OVERDUE","FX_DEADLINE_DATE":"2026-09-20","FX_DAYS_REMAINING":-6,"FX_UNAUTHORIZED_REALLOCATION_COUNT":1,"FX_CONVERSION_STATUS":"EVIDENCE_GAP","FX_CONVERSION_IMPACT_RIAL":480000000},{"KEY_REG":"REG-002","FX_CURRENT_STAGE":"تأمین وجه","FX_CONTROL_RISK_BAND":"HIGH","FX_CONTROL_RISK_SCORE":77,"FX_DEADLINE_STATUS":"DUE_SOON","FX_DEADLINE_DATE":"2026-09-29","FX_DAYS_REMAINING":3,"FX_UNAUTHORIZED_REALLOCATION_COUNT":0,"FX_CONVERSION_STATUS":"OK","FX_CONVERSION_IMPACT_RIAL":120000000},{"KEY_REG":"REG-003","FX_CURRENT_STAGE":"سوئیفت","FX_CONTROL_RISK_BAND":"MEDIUM","FX_CONTROL_RISK_SCORE":52,"FX_DEADLINE_STATUS":"OPEN","FX_DEADLINE_DATE":"2026-10-05","FX_DAYS_REMAINING":9,"FX_UNAUTHORIZED_REALLOCATION_COUNT":0,"FX_CONVERSION_STATUS":"EVIDENCE_GAP","FX_CONVERSION_IMPACT_RIAL":75000000}]),
    }
    h=build_dynamic_html(df,"2026-09-26",title="GSI — نمونه خروجی قابل شخصی‌سازی",
        tabs=[{"title":"نمای مدیریتی","fields":["KEY_MATERIAL","CANONICAL_ORDER","KEY_REG","ORG_DEPT","TRANSPORT_MODE","بحرانی (کوتاه)","مقاومت (روز)","مانده تعهد","روزهای تأخیر"]}],
        charts=["criticality","low_resistance","commitment","overdue_bucket","org_workload","transport_mix"],
        process_extras=extras,audience="manager",header_title="GSI — گزارش مدیریتی قابل شخصی‌سازی",
        header_subtitle="Drag & Drop · Resize · Hide/Restore · Cash Flow · Process Mining")
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(h,encoding="utf-8");return p

if __name__ == "__main__":
    p=main();print(p, p.stat().st_size)
