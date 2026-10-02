# -*- coding: utf-8 -*-
"""محیط کاری «چرخه ارز و رفع تعهد» — از پرونده ثبت سفارش تا رفع تعهد.

این صفحه هیچ عددی را دوباره حساب نمی‌کند و خودش هم نشانه‌گذاری نمی‌سازد:

* داده از :mod:`gsi.report.fx_insight` می‌آید (خروجی‌های منتشرشده s56/s59 و مارت)؛
* کارت‌ها، مسیر کلیک‌پذیر مراحل، جریان پول و تابلوی بحرانی از
  :mod:`gsi.report.fx_html` می‌آیند؛ **همان تکه‌هایی** که گزارش HTML ارسالی
  برای کاربران می‌سازد. پس Studio و HTML یک تصویر نشان می‌دهند؛
* سه خروجی Excel از :mod:`gsi.report.fx_excel` و فقط هنگام کلیک ساخته می‌شوند
  (:mod:`app.lazy_download`؛ روی Streamlit قدیمی‌تر از 1.52 با دکمه «آماده‌سازی»).

جدول‌های تعاملی Streamlit (مرتب‌سازی و جستجو) زیر هر بخش در یک بازشو می‌مانند.
نبودِ یک جدول (Snapshot قدیمی‌تر از این نسخه) با پیام صریح نشان داده می‌شود،
نه با جدول خالی که «صفر» خوانده شود.
"""
from __future__ import annotations

import functools
import html
from typing import Any, Optional

import pandas as pd
import streamlit as st

from app import lazy_download as LD
from gsi.design import icons as I
from gsi.design import tokens as T
from gsi.report import critical_board as CB
from gsi.report import fx_excel as XL
from gsi.report import fx_html as H
from gsi.report import fx_insight as X

#: سازگاری با کد قدیمی‌تر که این نام‌ها را از این ماژول می‌خواند
LIFECYCLE = list(X.LIFECYCLE)
STATUS_TONE = X.STATUS_TONE
LINK_TONE = X.LINK_TONE
XLSX = H.XLSX_MIME

CSS = """<style>
.fxl-head{background:var(--raised);border-radius:24px;padding:18px 22px;margin:4px 0 16px;
  box-shadow:%(raised)s;display:flex;gap:16px;align-items:center}
.fxl-head .mi-tile{width:54px;height:54px;border-radius:18px}
.fxl-head .k{font-size:11px;font-weight:800;color:var(--brand);letter-spacing:.3px}
.fxl-head h2{font-size:24px!important;margin:4px 0!important;color:var(--text)!important}
.fxl-head p{font-size:12px;color:var(--text-2);margin:0}
.fxl-note{font-size:12px;color:var(--text-2)}
.fxl-path{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:16px;align-items:center}
.fxl-path>div{min-width:0}
@media (max-width:900px){.fxl-path{grid-template-columns:1fr}}
%(minimal)s
</style>""" % {"minimal": I.minimal_css().replace("%", "%%"), "raised": T.ELEVATION["raised"]}


def _lang() -> str:
    try:
        from app.col_lang import current
        return current()
    except Exception:
        return "fa"


def _html(fragment: str) -> None:
    """تکه HTML مشترک؛ ظرف ``div`` اول می‌آید تا پاک‌سازی DOMPurify چیزی را حذف نکند."""
    ltr = ' dir="ltr"' if _lang() == "en" else ""
    st.html(f'<div class="gx gx-host"{ltr}>{fragment}</div>')


def _missing(name: str) -> None:
    st.info(f"جدول «{name}» در Snapshot منتشرشده نیست. یک‌بار «اجرای مجدد خط لوله» را بزنید تا "
            "مرحله پیوند بارنامه/ثبت سفارش (نسخه جدید) اجرا و منتشر شود.")


def _signature(df: Optional[pd.DataFrame], extras: Any, ref_date: str) -> tuple:
    names = ("fx_lifecycle", "bl_registration_link", "registration_value_recon", "fx_money_ledger",
             "fx_money_reconciliation", "allocation_queue", "fx_control_summary", "fx_financial_decisions",
             "expert_material_positions")
    sizes = []
    for k in names:
        try:
            v = extras.get(k)
        except Exception:
            v = None
        sizes.append(len(v) if isinstance(v, pd.DataFrame) else -1)
    try:
        run_id = extras.get("warehouse_run_id")
    except Exception:
        run_id = None
    return (ref_date, run_id, 0 if df is None else len(df), 0 if df is None else df.shape[1], tuple(sizes))


def _fx(df: pd.DataFrame, extras: Any, ref_date: str) -> X.FxData:
    """مدل مشترک یک‌بار در هر Snapshot ساخته می‌شود، نه در هر بازاجرای صفحه."""
    sig = _signature(df, extras, ref_date)
    cached = st.session_state.get("_gsi_fx_model")
    if cached and cached[0] == sig:
        return cached[1]
    fx = X.load(df, extras, ref_date)
    st.session_state["_gsi_fx_model"] = (sig, fx)
    return fx


def _dl(col, label: str, make, file_name: str, key: str, primary: bool = False, sig: tuple = (),
        mime: str = XLSX, icon: str = ":material/download:") -> None:
    """دانلود با ساخت فایل فقط هنگام نیاز، روی هر Streamlit از 1.49 به بالا.

    ``sig`` ورودی‌هایی است که محتوای فایل را عوض می‌کنند و در نام فایل نیستند؛ امضای
    Snapshot (شناسه اجرای منتشرشده) خودکار اضافه می‌شود.
    """
    snap = (st.session_state.get("_gsi_fx_model") or (None,))[0]
    LD.download(col, label, make, file_name=file_name, mime=mime, key=key, sig=(snap,) + tuple(sig),
                icon=icon, primary=primary)


# ═══════════════════════════════ نمای کلی ═══════════════════════════════
def _overview(fx: X.FxData, df: pd.DataFrame, ref_date: str, lang: str) -> None:
    _html(H.kpis(fx, lang))
    summ = X.stage_summary(fx)
    st.markdown(I.section_title("flow", "ثبت سفارش‌ها در هر مرحله"), unsafe_allow_html=True)
    st.caption("روی هر مرحله کلیک کنید: ثبت سفارش‌های همان مرحله باز می‌شود و هر کدام سفارش‌ها، متریال‌ها، "
               "بارنامه‌ها، جریان پول و تصمیم‌های مالی‌اش را نشان می‌دهد. همین نما در گزارش HTML ارسالی هست.")
    _html(H.stage_explorer(X.explorer(fx, max_regs=60), key="studio-overview", lang=lang,
                           selected=X.busiest_stage(summ), more_note="در Excel «پرونده‌ها به تفکیک مرحله»"))

    st.markdown(I.section_title("file", "خروجی Excel و HTML"), unsafe_allow_html=True)
    stages = [c for c, _ in X.STAGES if (fx.reg_table["STAGE_CODE"] == c).any()]
    c1, c2, c3 = st.columns([2, 2, 2])
    pick = c1.selectbox("مرحله برای Excel", ["همه مراحل"] + stages, key="fxl_xl_stage",
                        format_func=lambda c: c if c == "همه مراحل" else X.STAGE_FA.get(c, c))
    sel = None if pick == "همه مراحل" else [pick]
    _dl(c1, "Excel پرونده‌ها به تفکیک مرحله", functools.partial(XL.stage_workbook, fx, sel, lang),
        f"GSI_FX_STAGES_{pick if sel else 'ALL'}_{ref_date}.xlsx", "fxl_dl_stage", primary=True, sig=(lang,))
    regs = fx.reg_table["KEY_REG"].tolist()
    reg = c2.selectbox("ثبت سفارش برای ریز مالی", ["همه ثبت سفارش‌ها"] + regs, key="fxl_xl_reg")
    one = None if reg == "همه ثبت سفارش‌ها" else [reg]
    _dl(c2, "Excel ریز مالی ثبت سفارش", functools.partial(XL.registration_workbook, fx, one, lang),
        f"GSI_FX_FINANCE_{reg if one else 'ALL'}_{ref_date}.xlsx", "fxl_dl_reg", primary=True, sig=(lang,))
    c3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    _dl(c3, "گزارش HTML برای ارسال", functools.partial(_report_bytes, df, fx, ref_date, lang),
        f"GSI_FX_LIFECYCLE_{ref_date}.html", "fxl_dl_html", primary=True, sig=(lang,), mime="text/html",
        icon=":material/mail:")
    c3.caption("همین نماها با Excelهای جاسازی‌شده، بدون نیاز به Studio یا شبکه.")

    with st.expander("جدول تعاملی همه ثبت سفارش‌ها"):
        table = X.reg_display(fx.reg_table)
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            "پیشرفت (٪)": st.column_config.ProgressColumn("پیشرفت (٪)", min_value=0, max_value=100, format="%.0f٪"),
            "حمل‌شده (٪)": st.column_config.NumberColumn(format="%.1f٪"),
            "ارزش ثبت سفارش": st.column_config.NumberColumn(format="%,.2f"),
            "حمل‌شده": st.column_config.NumberColumn(format="%,.2f"),
            "مانده حمل‌نشده": st.column_config.NumberColumn(format="%,.2f")})

    st.markdown(I.section_title("link", "مسیر یک ثبت سفارش"), unsafe_allow_html=True)
    if not regs:
        return
    reg1 = st.selectbox("ثبت سفارش", regs, key="fxl_reg_pick")
    row = fx.reg_table[fx.reg_table["KEY_REG"].eq(reg1)].iloc[0]
    path = X.path(fx, reg1)
    st.markdown(
        f'<div class="mi-card"><div class="fxl-path"><div><div class="mi-title" style="margin-top:0">'
        f'{I.icon_tile("stamp", size=18)}<span>ثبت سفارش {html.escape(reg1)} · مرحله جاری: '
        f'{html.escape(X.s(row["STAGE"]))}</span></div>{I.stepper([(p["code"], p["label"], p["state"]) for p in path])}'
        f'<div class="fxl-note">نقطه با خط‌چین نارنجی = گام قبل از مرحله جاری که شاهد ندارد.</div></div>'
        f'<div>{I.ring(X.n(row["PROGRESS_PCT"]), 92, label="پیشرفت چرخه", uid="p" + H.uid(reg1))}</div>'
        f'<div>{I.ring(X.n(row["SHIPPED_PCT"]), 92, label="حمل‌شده از ثبت سفارش", uid="s" + H.uid(reg1))}</div>'
        f'</div></div>', unsafe_allow_html=True)
    _html(H.reg_details(X.reg_node(fx, reg1), lang, open_=True))
    _dl(st, f"Excel ریز مالی ثبت سفارش {reg1}", functools.partial(XL.registration_workbook, fx, [reg1], lang),
        f"GSI_FX_REG_{reg1}_{ref_date}.xlsx", "fxl_dl_one", sig=(lang,))
    detail = pd.DataFrame([{"مرحله": p["label"], "وضعیت": p["status"], "تاریخ/مهلت": p["date"],
                            "شاهد": p["evidence"]} for p in path])
    with st.expander("جزئیات مراحل این ثبت سفارش"):
        st.dataframe(detail, hide_index=True, width="stretch")


def _report_bytes(df: pd.DataFrame, fx: X.FxData, ref_date: str, lang: str) -> bytes:
    # مارت کامل، نه ``fx.mart``: تابلوی بحرانی و Excel بحرانی موجودی، نیاز روزانه و ارزش
    # فاکتور را از ستون‌هایی می‌خوانند که مدل چرخه ارز نگه نمی‌دارد
    return H.build_report(df, None, ref_date, lang=lang, fx=fx).encode("utf-8")


# ═══════════════════════════════ صف تخصیص ═══════════════════════════════
def _queue(fx: X.FxData, lang: str) -> None:
    _html(H.queue_section(fx, lang))


# ═══════════════════════════ بارنامه ↔ ثبت سفارش ═══════════════════════════
def _bl_link(fx: X.FxData, lang: str) -> None:
    if fx.recon.empty:
        _missing("پیوند بارنامه/ثبت سفارش")
        return
    statuses = sorted(fx.recon["STATUS"].dropna().unique().tolist())
    pick = st.multiselect("وضعیت پیوند ثبت سفارش", statuses, default=[], key="fxl_link_status",
                          placeholder="همه وضعیت‌ها")
    view = fx if not pick else _with_recon(fx, fx.recon[fx.recon["STATUS"].isin(pick)])
    _html(H.bl_link_section(view, lang, limit=40))
    with st.expander("جدول کامل بارنامه × ثبت سفارش"):
        st.dataframe(X.bls_frame(fx), hide_index=True, width="stretch", column_config={
            "ارزش فاکتور": st.column_config.NumberColumn(format="%,.2f")})


def _with_recon(fx: X.FxData, recon: pd.DataFrame) -> X.FxData:
    """نمای فیلترشده بدون ساختن دوباره مدل: فقط جدول تطبیق عوض می‌شود."""
    import copy
    view = copy.copy(fx)
    view.recon = recon
    view.__dict__.pop("recon_by_reg", None)
    return view


# ═══════════════════════════════ جریان پول ═══════════════════════════════
def _money(fx: X.FxData, ref_date: str, lang: str) -> None:
    if fx.money.empty:
        _missing("تطبیق صفر تا صد مبالغ")
        return
    _html(H.money_section(fx, lang))
    c1, c2 = st.columns([2, 3])
    _dl(c1, "Excel ریز مالی همه ثبت سفارش‌ها", functools.partial(XL.registration_workbook, fx, None, lang),
        f"GSI_FX_FINANCE_ALL_{ref_date}.xlsx", "fxl_dl_money_all", primary=True, sig=(lang,))
    lg = X.ledger(fx)
    if not lg.empty:
        with st.expander("رویدادهای مبلغی یک ثبت سفارش"):
            reg = st.selectbox("ثبت سفارش", sorted(lg["KEY_REG"].map(X.s).unique()), key="fxl_money_reg")
            ev = lg[lg["KEY_REG"].map(X.s).eq(reg)].drop(columns=["KEY_REG"])
            st.dataframe(ev.rename(columns={"EVENT_FA": "رویداد", "EVENT_DATE": "تاریخ", "AMOUNT": "مبلغ", "CURRENCY": "ارز",
                                            "SOURCE": "منبع", "REFERENCE": "مرجع", "STATUS": "وضعیت", "NOTE": "یادداشت"}),
                         hide_index=True, width="stretch",
                         column_config={"مبلغ": st.column_config.NumberColumn(format="%,.2f")})


# ═══════════════════════════════ ترخیص ═══════════════════════════════
def _clearance(fx: X.FxData, lang: str) -> None:
    _html(H.clearance_section(fx, lang))


# ═══════════════════════════════ بحرانی ═══════════════════════════════
def _critical(fx: X.FxData, df: pd.DataFrame, ref_date: str, lang: str) -> None:
    opts = list(CB.LEVELS.keys())[:5]
    levels = st.multiselect("سطوح بحرانی", opts, default=list(CB.DEFAULT_LEVELS),
                            format_func=CB.level_label, key="fxl_crit_levels")
    levels = tuple(levels) or CB.DEFAULT_LEVELS
    c1, c2 = st.columns(2)
    _dl(c1, "Excel اقلام بحرانی به تفکیک مرحله", functools.partial(XL.critical_workbook, fx, df, levels, None, lang),
        f"GSI_CRITICAL_BY_STAGE_{ref_date}.xlsx", "fxl_dl_crit", primary=True, sig=(levels, lang))
    page = functools.partial(lambda: CB.build_critical_html(df, ref_date, levels=levels, lang=lang).encode("utf-8"))
    _dl(c2, "قالب HTML متریال‌ها و بارنامه‌های بحرانی", page, f"GSI_CRITICAL_BOARD_{ref_date}.html",
        "fxl_dl_crit_html", sig=(levels, lang), mime="text/html")
    _html(H.critical_section(fx, df, lang, levels, key="studio-crit"))


# ═══════════════════════════════ ورودی ═══════════════════════════════
def run(df: pd.DataFrame, extras, ref_date: str) -> None:
    st.html(H.style_tag())
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="fxl-head">{I.icon_tile("exchange", size=26, active=True)}<div>'
                '<div class="k">خرید ارز · رفع تعهد · گزارش مالی</div><h2>چرخه ارز و رفع تعهد</h2><p>از پرونده ثبت سفارش تا رفع تعهد: صف تخصیص، خرید ارز، سوئیفت، پیوند مبلغی هر بارنامه با '
                'ثبت سفارشش، جریان پول، ترخیص و اقلام بحرانی. همین نماها در گزارش HTML ارسالی و سه خروجی Excel هستند.</p></div></div>',
                unsafe_allow_html=True)
    lang = _lang()
    fx = _fx(df, extras, ref_date)
    st.markdown("<style>" + I.nth_icons_css('.stTabs:not(.stTabs .stTabs) [role="tablist"] > [data-testid="stTab"]',
                                            ["gauge", "queue", "link", "coins", "customs", "alert"], 16)
                + "</style>", unsafe_allow_html=True)
    tabs = st.tabs(["نمای کلی چرخه", "صف تخصیص ارز", "بارنامه ↔ ثبت سفارش", "جریان پول (گزارش مالی)", "ترخیص",
                    "متریال و بارنامه بحرانی"])
    with tabs[0]:
        _overview(fx, df, ref_date, lang) if fx.available else _missing("چرخه ارز")
    with tabs[1]:
        _queue(fx, lang) if not fx.queue.empty or fx.available else _missing("صف تخصیص")
    with tabs[2]:
        _bl_link(fx, lang)
    with tabs[3]:
        _money(fx, ref_date, lang)
    with tabs[4]:
        _clearance(fx, lang)
    with tabs[5]:
        _critical(fx, df, ref_date, lang)
