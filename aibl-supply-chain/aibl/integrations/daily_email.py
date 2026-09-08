# -*- coding: utf-8 -*-
"""AIBL Executive Daily Email Pack — Outlook integration."""
from __future__ import annotations
import html, os, re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import pandas as pd
from ..config.settings import SETTINGS
from ..dataio.logging_setup import log

THEME, NAVY = "#0F6E6E", "#102D4D"
RED, ORANGE, YELLOW, GREEN, GREY = "#C0392B", "#F39C12", "#F1C40F", "#27AE60", "#95A5A6"
BG, BORDER, TEXT = "#F2F5F5", "#D8E4E1", "#243447"
# ── فهرست گیرندگان: پیکربندی محرمانه، هرگز داخل سورس ──────────────────────
# نشانی‌های واقعی کارکنان داده شخصی‌اند و در مخزن نگه‌داری نمی‌شوند.
# ترتیب حل:
#   ۱) متغیر محیطی AIBL_EMAIL_TO  (جدا با «,» یا «;»)
#   ۲) فایلی که AIBL_RECIPIENTS_FILE به آن اشاره می‌کند
#   ۳) recipients.yaml کنار پیکربندی (AIBL_HOME یا پوشه جاری)
#   ۴) **سورس HR** — ستون Email همان فایل پرسنلی (AIBL_EMAIL_FROM_HR=1)
#
# گزینه ۴ بهترین حالت است: فهرست هرگز در مخزن یا فایل جانبی کپی نمی‌شود،
# همیشه با آخرین وضعیت پرسنلی هم‌گام است، و کسی که غیرفعال شده خودکار
# از فهرست بیرون می‌رود.
# اگر هیچ‌کدام نبود، فهرست خالی است: ساخت گزارش کار می‌کند ولی ارسال
# با خطای صریح متوقف می‌شود — به‌جای آنکه بی‌صدا به فهرستی قدیمی برود.
RECIPIENTS_ENV = "AIBL_EMAIL_TO"
RECIPIENTS_FILE_ENV = "AIBL_RECIPIENTS_FILE"
RECIPIENTS_BASENAME = "recipients.yaml"


class NoRecipients(RuntimeError):
    """هیچ گیرنده‌ای پیکربندی نشده است."""


def _split(raw: str) -> list:
    return [x.strip() for x in re.split(r"[,;\s]+", raw or "") if x.strip() and "@" in x]


def _from_file(path: Path) -> list:
    """هر خط یک نشانی، یا YAML با کلید ``recipients``. «#» توضیح است."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict) and data.get("recipients"):
            return [str(x).strip() for x in data["recipients"] if "@" in str(x)]
        if isinstance(data, list):
            return [str(x).strip() for x in data if "@" in str(x)]
    except Exception:
        pass
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().lstrip("- ").strip()
        if "@" in line:
            out.append(line)
    return out


# ── انتخاب گیرنده از سورس HR ──────────────────────────────────────────────
HR_ENABLE_ENV = "AIBL_EMAIL_FROM_HR"
HR_POSTS_ENV = "AIBL_EMAIL_HR_POSTS"          # شرح پست، جدا با «,»
HR_MANAGEMENTS_ENV = "AIBL_EMAIL_HR_MANAGEMENTS"
HR_OFFICES_ENV = "AIBL_EMAIL_HR_OFFICES"
HR_MAX_ENV = "AIBL_EMAIL_HR_MAX"

#: پیش‌فرض: فقط سطوح مدیریتی. گزارش روزانه مدیریتی است و ارسال آن به کل
#: پرسنل نه مفید است نه محتاطانه.
DEFAULT_HR_POSTS = ("مدیر", "رئیس", "معاون")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _csv_env(name: str, default=()) -> tuple:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple(default)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def hr_recipients(hr_frame: Optional["pd.DataFrame"] = None) -> list:
    """گیرندگان را از ستون Email سورس HR برمی‌دارد.

    فیلترها، به ترتیب:
      • فقط پرسنل **فعال** (کسی که غیرفعال شده خودکار حذف می‌شود)
      • نشانی معتبر از نظر شکل
      • انطباق با شرح پست / مدیریت / اداره، اگر تعیین شده باشد

    نشانی‌ها هرگز لاگ یا ذخیره نمی‌شوند؛ فقط **تعداد** گزارش می‌گردد.
    """
    df = hr_frame
    if df is None:
        try:
            from ..adapters import discover, REGISTRY
            discover()
            cls = REGISTRY.get("hr")
            if cls is None:
                return []
            df = (cls().load() or {}).get("main")
        except Exception as ex:
            log.warning(f"⚠️ سورس HR برای گیرندگان ایمیل خوانده نشد: {ex}")
            return []
    if df is None or getattr(df, "empty", True):
        return []

    def col(suffix: str):
        name = f"HR_{suffix}"
        return df[name] if name in df.columns else None

    email = col("EMAIL")
    if email is None:
        log.warning("⚠️ ستون Email در سورس HR نیست؛ گیرنده‌ای استخراج نشد.")
        return []
    mail = email.fillna("").astype(str).str.strip()

    keep = mail.map(lambda x: bool(_EMAIL_RE.match(x)))

    status = col("STATUS")
    if status is not None:
        st = status.fillna("").astype(str)
        keep &= st.str.contains("فعال", na=False) & ~st.str.contains("غیرفعال", na=False)

    for env, suffix in ((HR_POSTS_ENV, "POST"), (HR_MANAGEMENTS_ENV, "DEPT"),
                        (HR_OFFICES_ENV, "OFFICE")):
        wanted = _csv_env(env, DEFAULT_HR_POSTS if env == HR_POSTS_ENV else ())
        if not wanted:
            continue
        c = col(suffix)
        if c is None:
            continue
        text = c.fillna("").astype(str)
        keep &= text.apply(lambda v: any(w in v for w in wanted))

    out = sorted({m.lower() for m in mail[keep] if m})
    cap = os.environ.get(HR_MAX_ENV, "").strip()
    if cap.isdigit():
        out = out[:int(cap)]
    log.info(f"👥 {len(out)} گیرنده از سورس HR انتخاب شد "
             f"(از {len(df)} پرسنل؛ نشانی‌ها لاگ نمی‌شوند).")
    return out


def recipients_path() -> Optional[Path]:
    explicit = os.environ.get(RECIPIENTS_FILE_ENV, "").strip()
    if explicit:
        return Path(explicit)
    home = os.environ.get("AIBL_HOME") or os.path.join(os.path.expanduser("~"), ".aibl")
    for cand in (Path(home) / RECIPIENTS_BASENAME, Path.cwd() / RECIPIENTS_BASENAME):
        if cand.exists():
            return cand
    return None


def _recipients() -> list:
    raw = os.environ.get(RECIPIENTS_ENV, "")
    if raw.strip():
        return _split(raw)
    path = recipients_path()
    if path:
        found = _from_file(path)
        if found:
            return found
    # سورس HR — تازه‌ترین و کم‌خطاترین منبع، چون کپی جانبی نمی‌سازد.
    if os.environ.get(HR_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return hr_recipients()
    return []


def daily_paths(day: Optional[date]=None) -> Dict[str,Path]:
    d=day or SETTINGS.today
    folder=Path(SETTINGS.daily_report_root)/d.strftime("%Y-%m-%d")
    folder.mkdir(parents=True,exist_ok=True)
    assets=folder/"email_assets"; assets.mkdir(parents=True,exist_ok=True)
    return {"folder":folder,"excel":Path(SETTINGS.daily_report_path(d)),"assets":assets,
            "html":folder/f"{d:%Y-%m-%d}_AIBL_Executive_Email.html"}

def _require_matplotlib():
    """پیام روشن به‌جای ModuleNotFoundError خام.

    نمودارهای ایمیل با matplotlib کشیده می‌شوند و تا نسخه ۲۶٫۲٫۲ این
    وابستگی در requirements.txt نبود؛ «python -m aibl email» روی نصب تازه
    با traceback خام می‌افتاد.
    """
    try:
        import matplotlib  # noqa: F401
    except ImportError as ex:
        raise ImportError(
            "بسته ایمیل مدیریتی به matplotlib نیاز دارد:\n"
            "    python -m pip install matplotlib") from ex


def _font_setup():
    _require_matplotlib()
    import matplotlib.pyplot as plt
    try:
        from matplotlib import font_manager
        font_manager.findfont("IRANSans Light", fallback_to_default=False)
        plt.rcParams["font.family"] = "IRANSans Light"
    except Exception:
        plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["axes.unicode_minus"] = False

def _save_chart(fig,path:Path)->Path:
    fig.savefig(path,dpi=150,bbox_inches="tight",facecolor="white")
    import matplotlib.pyplot as plt; plt.close(fig); return path

def make_email_charts(df:pd.DataFrame,assets:Path)->list[Path]:
    _require_matplotlib()
    import matplotlib.pyplot as plt
    _font_setup(); out=[]
    band_order=["STOCKOUT","CRITICAL","BECOMING_CRITICAL","WATCH","SAFE","NO_CONSUMPTION","UNKNOWN"]
    band_labels={"STOCKOUT":"Stop Line","CRITICAL":"Critical","BECOMING_CRITICAL":"Becoming Critical",
                 "WATCH":"Watch","SAFE":"Safe","NO_CONSUMPTION":"Inactive","UNKNOWN":"No Data"}
    band_colors={"STOCKOUT":RED,"CRITICAL":RED,"BECOMING_CRITICAL":ORANGE,"WATCH":YELLOW,
                 "SAFE":GREEN,"NO_CONSUMPTION":GREY,"UNKNOWN":GREY}
    if "کد طبقه بحرانی" in df.columns:
        codes=df["کد طبقه بحرانی"].astype(str)
        labels=[x for x in band_order if x in set(codes)]
        vals=[]
        for code in labels:
            sub=df[codes==code]
            vals.append(int(sub["KEY_MATERIAL"].replace("",pd.NA).nunique()) if "KEY_MATERIAL" in sub else len(sub))
        if labels:
            fig,ax=plt.subplots(figsize=(8.8,3.7))
            bars=ax.bar([band_labels[x] for x in labels], vals, color=[band_colors[x] for x in labels], edgecolor="white", linewidth=0.8)
            ax.set_title("Material Criticality Mix", fontsize=13, fontweight="bold", pad=10)
            ax.set_ylabel("Unique Materials", fontsize=10); ax.grid(axis="y",alpha=.15); ax.tick_params(axis="x",labelsize=9)
            for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v,f"{v:,}",ha="center",va="bottom",fontsize=9)
            fig.tight_layout(); out.append(_save_chart(fig,assets/"01_material_criticality.png"))

    vals=[]; labels=[]
    for col,label,key,color in (("BL_CRITICAL","Critical BLs","CANONICAL_BL",RED),("ORDER_CRITICAL","Critical Orders","CANONICAL_ORDER",ORANGE)):
        if col in df.columns:
            vals.append(int(df.loc[df[col].astype(bool),key].replace("",pd.NA).nunique()) if key in df else int(df[col].sum())); labels.append(label)
    if vals:
        fig,ax=plt.subplots(figsize=(8.8,3.7))
        bars=ax.bar(labels,vals,color=[RED,ORANGE][:len(vals)],edgecolor="white",linewidth=0.8)
        ax.set_title("Critical Cases",fontsize=13,fontweight="bold",pad=10); ax.set_ylabel("Unique Cases",fontsize=10); ax.grid(axis="y",alpha=.15)
        for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,max(v,0),f"{v:,}",ha="center",va="bottom",fontsize=10)
        fig.tight_layout(); out.append(_save_chart(fig,assets/"02_group_criticality.png"))

    if {"KEY_MATERIAL","مقاومت (روز)"}.issubset(df.columns):
        cols=["KEY_MATERIAL","مقاومت (روز)"] + (["کد طبقه بحرانی"] if "کد طبقه بحرانی" in df.columns else [])
        x=df[cols].copy(); x["مقاومت (روز)"]=pd.to_numeric(x["مقاومت (روز)"],errors="coerce")
        x=x.dropna().drop_duplicates("KEY_MATERIAL").sort_values("مقاومت (روز)").head(10).sort_values("مقاومت (روز)")
        if not x.empty:
            fig,ax=plt.subplots(figsize=(8.8,4.5))
            row_colors=[band_colors.get(str(code),GREY) for code in x.get("کد طبقه بحرانی",pd.Series(["UNKNOWN"]*len(x),index=x.index))]
            bars=ax.barh(x["KEY_MATERIAL"].astype(str),x["مقاومت (روز)"],color=row_colors,edgecolor="white",linewidth=0.6)
            ax.axvline(10,linestyle="--",linewidth=1.2,color=RED,label="Critical threshold: 10 days")
            ax.set_title("10 Lowest-Resistance Materials",fontsize=13,fontweight="bold",pad=10); ax.set_xlabel("Resistance (days)",fontsize=10); ax.grid(axis="x",alpha=.15); ax.legend(frameon=False,fontsize=8); ax.tick_params(axis="y",labelsize=8)
            for b,v in zip(bars,x["مقاومت (روز)"]): ax.text(v,b.get_y()+b.get_height()/2,f" {v:.1f}",va="center",fontsize=8)
            fig.tight_layout(); out.append(_save_chart(fig,assets/"03_low_resistance.png"))
    return out

def executive_kpis(df:pd.DataFrame)->list[dict[str,Any]]:
    def unique(mask,key): return int(df.loc[mask,key].replace("",pd.NA).nunique()) if key in df.columns else 0
    crit_mat=int(df.loc[df["کد طبقه بحرانی"].isin(["STOCKOUT","CRITICAL"]),"KEY_MATERIAL"].replace("",pd.NA).nunique()) if {"کد طبقه بحرانی","KEY_MATERIAL"}.issubset(df.columns) else 0
    crit_bl=unique(df["BL_CRITICAL"].astype(bool),"CANONICAL_BL") if "BL_CRITICAL" in df.columns else 0
    crit_ord=unique(df["ORDER_CRITICAL"].astype(bool),"CANONICAL_ORDER") if "ORDER_CRITICAL" in df.columns else 0
    low=pd.to_numeric(df.get("مقاومت (روز)"),errors="coerce").min()
    overdue=int((pd.to_numeric(df["روزهای تأخیر"],errors="coerce").fillna(0)>0).sum()) if "روزهای تأخیر" in df.columns else 0
    cov_measured = ("COMMERCIAL_COVERAGE_STATE" in df.columns
                    and (df["COMMERCIAL_COVERAGE_STATE"] == "measured").any())
    missing_commercial = unique(df["ORDER_MISSING_COMMERCIAL_EXPERT"].astype(bool), "CANONICAL_ORDER") if "ORDER_MISSING_COMMERCIAL_EXPERT" in df.columns else 0
    return [{"label":"متریال بحرانی","value":crit_mat,"tone":"red","note":"توقف خط + بحرانی"},{"label":"بارنامه بحرانی","value":crit_bl,"tone":"red","note":"علت تا متریال مشخص است"},{"label":"سفارش بحرانی","value":crit_ord,"tone":"amber","note":"علت تا متریال مشخص است"},{"label":"کمترین مقاومت","value":"—" if pd.isna(low) else f"{low:.1f} روز","tone":"red" if pd.notna(low) and low<10 else "green","note":"بحرانی‌ترین وضعیت"},{"label":"تعهدات معوق","value":overdue,"tone":"amber" if overdue else "green","note":"نیازمند پیگیری"},{"label":"سفارش خارج از Commercial Expert Data","value":missing_commercial if cov_measured else "سنجیده نشد","tone":("red" if missing_commercial else "green") if cov_measured else "amber","note":"بدون انتساب کارشناس خرید" if cov_measured else "سورس خرید بارگذاری نشد"}]

def _kpi_cards(kpis:Iterable[dict[str,Any]])->str:
    colors={"red":RED,"amber":ORANGE,"green":GREEN}; cards=[]
    for k in kpis:
        c=colors.get(k.get("tone"),THEME)
        cards.append(f'<td style="width:20%;padding:7px"><div style="background:#fff;border:1px solid {BORDER};border-top:4px solid {c};border-radius:12px;padding:13px;text-align:center"><div style="font-size:12px;color:#607181">{html.escape(str(k["label"]))}</div><div style="font-size:25px;font-weight:800;color:{c};margin:4px 0">{html.escape(str(k["value"]))}</div><div style="font-size:10px;color:#607181">{html.escape(str(k.get("note","")))}</div></div></td>')
    return "<tr>"+"".join(cards)+"</tr>"

def build_email_html(day:date,df:pd.DataFrame,charts:list[Path],excel:Path)->str:
    img="".join(f'<tr><td style="padding:8px 0"><img src="cid:chart_{i}" width="100%" style="display:block;border:1px solid {BORDER};border-radius:10px" alt="Executive chart"></td></tr>' for i,_ in enumerate(charts,1))
    rows=[]
    if "BL_CRITICAL" in df.columns:
        g=df[df["BL_CRITICAL"].astype(bool)].drop_duplicates("CANONICAL_BL").head(6) if "CANONICAL_BL" in df.columns else df.iloc[0:0]
        for _,r in g.iterrows(): rows.append((r.get("CANONICAL_BL","—"),r.get("BL_CRITICAL_MATERIALS","—"),r.get("BL_CRITICAL_REASON","—")))
    table="".join(f'<tr><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(a))}</td><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(b))}</td><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(c))}</td></tr>' for a,b,c in rows)
    cause=(f'<div style="margin:18px 0 8px;font-size:16px;font-weight:800;color:{NAVY}">نمونه بارنامه‌های بحرانی و علت</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px"><tr style="background:{THEME};color:#fff"><th style="padding:8px">بارنامه</th><th style="padding:8px">متریال</th><th style="padding:8px">علت</th></tr>{table}</table>') if table else ""
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"></head><body style="margin:0;background:{BG};font-family:'IRANSans Light','IRANSans',Tahoma,Arial,sans-serif;color:{TEXT}"><table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:18px 8px"><table width="820" cellpadding="0" cellspacing="0" style="max-width:820px;width:100%;background:#fff;border:1px solid {BORDER};border-radius:16px;overflow:hidden"><tr><td style="padding:22px 28px;background:{NAVY}"><div style="color:#fff;font-size:24px;font-weight:800">AIBL · Executive Daily Insight</div><div style="color:#d9f1ed;font-size:13px;margin-top:5px">مغز شناختی لجستیک ایران خودرو · {day:%Y-%m-%d}</div></td></tr><tr><td style="padding:20px 24px"><table width="100%" cellpadding="0" cellspacing="0">{_kpi_cards(executive_kpis(df))}</table><div style="margin:20px 0 12px;font-size:18px;font-weight:800;color:{NAVY}">سه نگاه برای تصمیم امروز</div><table width="100%" cellpadding="0" cellspacing="0">{img}</table><div style="margin:18px 0 10px;font-size:17px;font-weight:800;color:{NAVY}">چرا فایل Excel را باز کنیم؟</div><div style="background:#f5faf8;border:1px solid {BORDER};border-radius:10px;padding:14px;line-height:1.9;font-size:13px">در ایمیل فقط <b>سیگنال مدیریتی</b> را می‌بینید؛ جزئیات تصمیم در Excel است: متریال‌های بحرانی، علت بحرانی شدن هر بارنامه/سفارش، مقاومت، موجودی، تعهد ارزی، گلوگاه فرآیند و ردیابی پرونده. <b>یک متریال بحرانی، کل پرونده را بحرانی می‌کند؛ علت آن در فایل تا سطح متریال قابل مشاهده است.</b></div>{cause}<div style="margin-top:20px;text-align:center"><span style="display:inline-block;background:{THEME};color:#fff;border-radius:9px;padding:11px 18px;font-weight:800">📎 {html.escape(excel.name)}</span></div></td></tr><tr><td style="padding:14px 24px;background:#f7f9f9;color:#6b7b88;font-size:11px">این پیام توسط AIBL تولید شده است · داده‌ها از Pipeline همان روز استخراج شده‌اند.</td></tr></table></td></tr></table></body></html>'''

def _add_inline(mail,path:Path,cid:str)->None:
    att=mail.Attachments.Add(str(path.resolve()),1,0,path.name); acc=att.PropertyAccessor
    acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F",cid)
    try: acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3716001F","inline")
    except Exception: pass

def create_daily_email(*,day:Optional[date]=None,send:bool=False,display:bool=True)->Dict[str,Any]:
    from ..pipeline import Pipeline
    d=day or SETTINGS.today; res=Pipeline(today=d).run(build_report=True); paths=daily_paths(d)
    excel=Path(res.dashboard_path); official=paths["excel"]
    if excel.resolve()!=official.resolve():
        try:
            if official.exists(): official.unlink()
            excel.replace(official); excel=official
        except Exception: pass
    charts=make_email_charts(res.main,paths["assets"]); body=build_email_html(d,res.main,charts,excel); paths["html"].write_text(body,encoding="utf-8")
    to=_recipients()
    result={"excel":excel,"html":paths["html"],"charts":charts,"recipients":to,"sent":False}
    if not(send or display): return result
    if not to:
        # بی‌صدا به فهرست قدیمی نمی‌رویم — فهرست گیرندگان پیکربندی محرمانه است.
        raise NoRecipients(
            "هیچ گیرنده‌ای پیکربندی نشده است. یکی از این‌ها را تنظیم کنید:\n"
            f"    {RECIPIENTS_ENV}=\"a@example.invalid;b@example.invalid\"\n"
            f"    {RECIPIENTS_FILE_ENV}=/path/to/{RECIPIENTS_BASENAME}\n"
            f"    یا فایل {RECIPIENTS_BASENAME} را در AIBL_HOME بگذارید،\n"
            f"    یا {HR_ENABLE_ENV}=1 تا از ستون Email سورس HR خوانده شود.\n"
            "نمونه: recipients.example.yaml")
    try: import win32com.client as win32
    except ImportError as ex: raise RuntimeError("برای Outlook باید pywin32 و Classic Outlook نصب باشد.") from ex
    outlook=win32.Dispatch("Outlook.Application"); mail=outlook.CreateItem(0); mail.BodyFormat=2
    mail.Subject=f"AIBL Executive Daily Insight — {d:%Y-%m-%d}"; mail.To="; ".join(to)
    # حساب فرستنده هم پیکربندی است، نه ثابتِ داخل کد؛ خالی یعنی حساب پیش‌فرض Outlook.
    sender=os.environ.get("AIBL_EMAIL_SENDER","").strip().lower()
    if sender:
        try:
            for account in outlook.Session.Accounts:
                if getattr(account,"SmtpAddress","").lower()==sender: mail._oleobj_.Invoke(*(64209,0,8,0,account)); break
        except Exception: pass
    for i,ch in enumerate(charts,1): _add_inline(mail,ch,f"chart_{i}")
    mail.Attachments.Add(str(excel.resolve())); mail.HTMLBody=body; mail.Save()
    if send: mail.Send(); result["sent"]=True
    elif display: mail.Display()
    return result

def main(argv=None)->int:
    import argparse
    ap=argparse.ArgumentParser(description="AIBL Executive Daily Insight email"); ap.add_argument("--send",action="store_true"); ap.add_argument("--no-display",action="store_true")
    a=ap.parse_args(argv); r=create_daily_email(send=a.send,display=not a.no_display)
    print(f"Excel: {r['excel']}"); print(f"HTML: {r['html']}"); print(f"Charts: {len(r['charts'])}"); print(f"Recipients: {len(r['recipients'])}"); print(f"Sent: {r['sent']}"); return 0
if __name__=="__main__": raise SystemExit(main())
