# -*- coding: utf-8 -*-
"""Static Outlook-safe/personal HTML renderer from encrypted shared-folder data.

The renderer itself never queries network APIs. It reads the current encrypted
snapshot + persistent profile directly from GSI_PROFILE_ROOT.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, Iterable

from .service import PersonalWorkspace


def _e(v: Any) -> str:
    return html.escape("—" if v is None or str(v).strip() == "" else str(v))


def _records(context: Dict[str, Any]) -> list[dict]:
    current = context.get("current") or {}
    recs = current.get("records", []) if isinstance(current, dict) else []
    return [x for x in recs if isinstance(x, dict)]


def build_personal_html(employee_code: str, *, title: str = "GSI · فضای شخصی") -> str:
    ws = PersonalWorkspace.from_env(employee_code)
    ctx = ws.context()
    prefs = ctx["preferences"]
    current = ctx.get("current") or {}
    records = _records(ctx)
    meta = ctx.get("snapshot_meta") or {}
    refreshed = meta.get("refreshed_at") or current.get("ref_date") or "—"

    max_findings = max(1, int(prefs.get("max_findings", 5) or 5))
    table_rows = max(1, int(prefs.get("table_rows", 80) or 80))

    action_rows = []
    for r in records:
        act = r.get("FX_ACTION_TITLE") or r.get("مانع فعلی")
        if not act:
            continue
        action_rows.append(
            f"<tr><td>{_e(r.get('KEY_REG'))}</td><td>{_e(r.get('مرحله جاری') or r.get('FX_CURRENT_STAGE'))}</td>"
            f"<td>{_e(act)}</td><td>{_e(r.get('FX_ACTION_DUE_DATE'))}</td></tr>"
        )
        if len(action_rows) >= max_findings:
            break

    case_rows = []
    for r in records[:table_rows]:
        case_rows.append(
            f"<tr><td>{_e(r.get('KEY_REG'))}</td><td>{_e(r.get('CANONICAL_ORDER'))}</td>"
            f"<td>{_e(r.get('CANONICAL_BL'))}</td><td>{_e(r.get('مرحله جاری') or r.get('FX_CURRENT_STAGE'))}</td>"
            f"<td>{_e(r.get('بحرانی (کوتاه)'))}</td><td>{_e(r.get('مقاومت (روز)'))}</td></tr>"
        )

    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>
<style>body{{margin:0;background:#f6f8f9;color:#0b1f33;font-family:Tahoma,Arial,sans-serif}}.w{{max-width:980px;margin:24px auto;padding:0 12px}}.h{{background:#0b1f33;color:#fff;padding:22px;border-radius:16px}}.h small{{color:#c5d2db}}.card{{background:#fff;border:1px solid #dbe3e7;border-radius:14px;padding:16px;margin-top:14px}}.meta{{color:#5a6b79;font-size:12px}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:9px;border-bottom:1px solid #edf1f3;text-align:right}}th{{background:#eef2f4}}.pill{{display:inline-block;background:#e7f1f2;color:#076670;padding:6px 10px;border-radius:999px;font-size:11px}}.live{{display:inline-block;background:#0a7c86;color:#fff!important;text-decoration:none;padding:10px 14px;border-radius:10px;font-weight:bold;margin-right:8px}}.warn{{background:#faf3e4;color:#7a5a15;padding:10px 12px;border-radius:10px}}@media(max-width:650px){{.w{{margin:10px auto}}table{{min-width:720px}}.scroll{{overflow:auto}}}}</style></head>
<body><div class="w"><div class="h"><b style="font-size:22px">{_e(title)}</b><br><small>EMP {_e(employee_code)} · Data • Process • Decision</small></div>
<div class="card"><span class="pill">داده از Shared Folder رمزگذاری‌شده</span><a class="live" href="gsi://personal">مشاهده وضعیت زنده</a><p class="meta">آخرین Snapshot: {_e(refreshed)} · ردیف: {_e(current.get('row_count', len(records)))} · Calendar: {_e(prefs.get('calendar'))}</p>
<div class="warn">این فایل Snapshot داده‌ای است که هنگام ساخت HTML از <b>current.gsi</b> خوانده شده. بدنه ایمیل Outlook JavaScript فعال اجرا نمی‌کند؛ دکمه «مشاهده وضعیت زنده» Helper محلی GSI را باز می‌کند تا همین لحظه profile.gsi + current.gsi را دوباره از Shared Folder بخواند. اگر Policy سازمانی custom protocol را مسدود کند، GSI Personal Workspace را از Shortcut محلی باز کنید.</div></div>
<div class="card"><h3>اقدامات من</h3><div class="scroll"><table><tr><th>REG</th><th>مرحله</th><th>اقدام</th><th>موعد</th></tr>{''.join(action_rows) or '<tr><td colspan="4">اقدام بازی در Snapshot نیست.</td></tr>'}</table></div></div>
<div class="card"><h3>پرونده‌های من</h3><div class="scroll"><table><tr><th>REG</th><th>Order</th><th>BL</th><th>مرحله</th><th>وضعیت</th><th>مقاومت</th></tr>{''.join(case_rows) or '<tr><td colspan="6">داده‌ای منتشر نشده است.</td></tr>'}</table></div></div>
<div class="meta" style="padding:14px 4px">GSI Personal Workspace · profile.gsi + current.gsi · بدون API/IP برای Data Access</div></div></body></html>'''
