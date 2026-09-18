# -*- coding: utf-8 -*-
"""GSI Executive Daily Email Pack — Outlook integration."""
from __future__ import annotations
import html, os, re
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import pandas as pd
from ..config.settings import SETTINGS
from ..dataio.logging_setup import log

# ── پالت ایمیل — از سیستم طراحی GSI ──────────────────────────────────────
# سه مقدار قبلی کف WCAG را رد می‌کردند و روی کارت سفید عملاً ناخوانا بودند:
#     ORANGE #F39C12 → ۱٫۹    YELLOW #F1C40F → ۱٫۷    GREEN #27AE60 → ۲٫۸
# حالا هر رنگِ **متن** از پله ink سنجیده‌شده می‌آید و رنگِ **سطح** از fill.
from ..design import tokens as _T

THEME, NAVY = _T.BRAND_TEAL, _T.BRAND_NAVY
GOLD = _T.BRAND_GOLD
RED = _T.STATUS["critical"].ink
ORANGE = _T.STATUS["serious"].ink
YELLOW = _T.STATUS["warning"].ink
GREEN = _T.STATUS["good"].ink
GREY = _T.STATUS["neutral"].ink
BG, BORDER, TEXT = _T.SURFACE_PAGE, _T.BORDER, _T.TEXT
TEXT2, TEXT3 = _T.TEXT_SECONDARY, _T.TEXT_MUTED
# ── فهرست گیرندگان: پیکربندی محرمانه، هرگز داخل سورس ──────────────────────
# نشانی‌های واقعی کارکنان داده شخصی‌اند و در مخزن نگه‌داری نمی‌شوند.
# ترتیب حل:
#   ۱) متغیر محیطی GSI_EMAIL_TO  (جدا با «,» یا «;»)
#   ۲) فایلی که GSI_RECIPIENTS_FILE به آن اشاره می‌کند
#   ۳) recipients.yaml کنار پیکربندی (GSI_HOME یا پوشه جاری)
#   ۴) **سورس HR** — ستون Email همان فایل پرسنلی (GSI_EMAIL_FROM_HR=1)
#
# گزینه ۴ بهترین حالت است: فهرست هرگز در مخزن یا فایل جانبی کپی نمی‌شود،
# همیشه با آخرین وضعیت پرسنلی هم‌گام است، و کسی که غیرفعال شده خودکار
# از فهرست بیرون می‌رود.
# اگر هیچ‌کدام نبود، فهرست خالی است: ساخت گزارش کار می‌کند ولی ارسال
# با خطای صریح متوقف می‌شود — به‌جای آنکه بی‌صدا به فهرستی قدیمی برود.
RECIPIENTS_ENV = "GSI_EMAIL_TO"
RECIPIENTS_FILE_ENV = "GSI_RECIPIENTS_FILE"
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
HR_ENABLE_ENV = "GSI_EMAIL_FROM_HR"
HR_POSTS_ENV = "GSI_EMAIL_HR_POSTS"          # شرح پست، جدا با «,»
HR_MANAGEMENTS_ENV = "GSI_EMAIL_HR_MANAGEMENTS"
HR_OFFICES_ENV = "GSI_EMAIL_HR_OFFICES"
HR_MAX_ENV = "GSI_EMAIL_HR_MAX"

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
    home = os.environ.get("GSI_HOME") or os.path.join(os.path.expanduser("~"), ".gsi")
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
            "html":folder/f"{d:%Y-%m-%d}_GSI_Executive_Email.html"}

def _require_matplotlib():
    """پیام روشن به‌جای ModuleNotFoundError خام.

    نمودارهای ایمیل با matplotlib کشیده می‌شوند و تا نسخه ۲۶٫۲٫۲ این
    وابستگی در requirements.txt نبود؛ «python -m gsi email» روی نصب تازه
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

def available_email_charts() -> Dict[str, str]:
    """نمودارهای ایمیل دقیقاً با فهرست نمودارهای شیت Charts هم‌نام‌اند."""
    from ..studio_core.designs import EMAIL_CHARTS
    return dict(EMAIL_CHARTS)



@contextmanager
def _outlook_session():
    """دسترسی به Outlook با COM مقداردهی‌شده روی **همان نخ جاری**.

    خطای واقعی تولید::

        (-2147221008, 'CoInitialize has not been called.', None, None)

    Streamlit هر تعامل کاربر را روی یک نخ ScriptRunner تازه اجرا می‌کند و
    ``win32com`` فقط روی نخی کار می‌کند که پیش‌تر ``CoInitialize`` روی آن صدا
    شده باشد. دکمه «باز کردن پیش‌نویس ایمیل در Outlook» در Process View دقیقاً
    از همین مسیر فراخوانی می‌شود، پس بدون این مدیر زمینه روی ویندوز می‌افتد.

    COM در **هر مسیر خروج** — شامل مسیر خطا — آزاد می‌شود؛ نبودِ
    ``CoUninitialize`` در مسیر خطا همان چیزی است که در اجرای طولانی Studio به
    نشت اشاره COM و خطاهای بعدیِ به‌ظاهر بی‌ربط منجر می‌شود.
    """
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError as ex:
        raise RuntimeError(
            "برای Outlook روی ویندوز باید pywin32 و Classic Outlook نصب باشد:\n"
            "    python -m pip install pywin32") from ex
    pythoncom.CoInitialize()
    try:
        yield win32
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception as ex:
            log.debug("CoUninitialize نادیده گرفته شد: %s", ex)


def make_email_charts(df: pd.DataFrame, assets: Path,
                      selected: Optional[Iterable[str]] = None,
                      extras: Optional[Dict[str, Any]] = None) -> list[Path]:
    """ساخت نمودارهای قابل انتخاب ایمیل.

    اگر selected خالی باشد سه نمودار مدیریتی پیش‌فرض ساخته می‌شود؛ اگر کلید
    داده شود، فقط همان نمودارها ساخته می‌شوند. منطق اعداد از همان فیلدهای
    گزارش رسمی استفاده می‌کند تا انتخاب نمودار صرفاً presentation باشد.
    """
    _require_matplotlib()
    import matplotlib.pyplot as plt
    _font_setup()
    from ..studio_core.designs import EMAIL_CHARTS

    wanted = list(selected) if selected else ["criticality", "low_resistance", "stock_vs_total"]
    wanted = [x for x in wanted if x in EMAIL_CHARTS]
    out = []
    assets.mkdir(parents=True, exist_ok=True)

    def save(fig, key, idx):
        path = assets / f"{idx:02d}_{key}.png"
        return _save_chart(fig, path)

    if "criticality" in wanted and "کد طبقه بحرانی" in df.columns:
        order=["STOCKOUT","CRITICAL","BECOMING_CRITICAL","WATCH","SAFE","NO_CONSUMPTION","UNKNOWN"]
        labels={"STOCKOUT":"توقف خط","CRITICAL":"بحرانی","BECOMING_CRITICAL":"در آستانه",
                "WATCH":"تحت نظر","SAFE":"ایمن","NO_CONSUMPTION":"بدون مصرف","UNKNOWN":"نامشخص"}
        colors={"STOCKOUT":RED,"CRITICAL":RED,"BECOMING_CRITICAL":ORANGE,"WATCH":YELLOW,"SAFE":GREEN,
                "NO_CONSUMPTION":GREY,"UNKNOWN":GREY}
        codes=df["کد طبقه بحرانی"].astype(str)
        vals=[int((codes==x).sum()) for x in order if (codes==x).any()]
        labs=[labels[x] for x in order if (codes==x).any()]
        if labs:
            fig,ax=plt.subplots(figsize=(8.8,3.7))
            bars=ax.bar(labs,vals,color=[colors[x] for x in order if (codes==x).any()],edgecolor="white")
            ax.set_title(EMAIL_CHARTS["criticality"],fontsize=13,fontweight="bold"); ax.set_ylabel("تعداد متریال")
            for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v,f"{v:,}",ha="center",va="bottom",fontsize=9)
            fig.tight_layout(); out.append(save(fig,"criticality",len(out)+1))

    if "low_resistance" in wanted and {"KEY_MATERIAL","مقاومت (روز)"}.issubset(df.columns):
        x=df[["KEY_MATERIAL","مقاومت (روز)"]].copy()
        x["مقاومت (روز)"]=pd.to_numeric(x["مقاومت (روز)"],errors="coerce")
        x=x.dropna().drop_duplicates("KEY_MATERIAL").sort_values("مقاومت (روز)").head(10)
        if not x.empty:
            fig,ax=plt.subplots(figsize=(8.8,4.5))
            bars=ax.barh(x["KEY_MATERIAL"].astype(str),x["مقاومت (روز)"],color=RED,edgecolor="white")
            ax.set_title(EMAIL_CHARTS["low_resistance"],fontsize=13,fontweight="bold"); ax.set_xlabel("مقاومت (روز)")
            ax.axvline(10,linestyle="--",linewidth=1.2,color=RED)
            for b,v in zip(bars,x["مقاومت (روز)"]): ax.text(v,b.get_y()+b.get_height()/2,f" {v:.1f}",va="center",fontsize=8)
            fig.tight_layout(); out.append(save(fig,"low_resistance",len(out)+1))

    if "stock_vs_total" in wanted and {"KEY_MATERIAL","مقاومت انبار (روز)","مقاومت (روز)"}.issubset(df.columns):
        x=df[["KEY_MATERIAL","مقاومت انبار (روز)","مقاومت (روز)"]].copy()
        for c in x.columns[1:]: x[c]=pd.to_numeric(x[c],errors="coerce")
        x=x.dropna().drop_duplicates("KEY_MATERIAL").sort_values("مقاومت (روز)").head(10)
        if not x.empty:
            fig,ax=plt.subplots(figsize=(9,4.5)); pos=range(len(x)); w=.38
            ax.bar([i-w/2 for i in pos],x["مقاومت انبار (روز)"],width=w,label="مقاومت انبار")
            ax.bar([i+w/2 for i in pos],x["مقاومت (روز)"],width=w,label="مقاومت کل")
            ax.set_xticks(list(pos)); ax.set_xticklabels(x["KEY_MATERIAL"].astype(str),rotation=45,ha="right")
            ax.set_title(EMAIL_CHARTS["stock_vs_total"],fontsize=13,fontweight="bold"); ax.set_ylabel("روز"); ax.legend(frameon=False)
            fig.tight_layout(); out.append(save(fig,"stock_vs_total",len(out)+1))

    if "commitment" in wanted and {"مانده تعهد","روزهای تأخیر"}.issubset(df.columns):
        bal=pd.to_numeric(df["مانده تعهد"],errors="coerce").fillna(0)
        overdue=pd.to_numeric(df["روزهای تأخیر"],errors="coerce").fillna(0)
        labs=["معوق","در مهلت","تسویه‌شده"]; masks=[overdue>0,(overdue<=0)&(bal>0),bal<=0]
        vals=[float(bal[m].sum()) for m in masks]
        fig,ax=plt.subplots(figsize=(8.8,3.7)); bars=ax.bar(labs,vals,color=[RED,ORANGE,GREEN],edgecolor="white")
        ax.set_title(EMAIL_CHARTS["commitment"],fontsize=13,fontweight="bold"); ax.set_ylabel("مانده تعهد")
        for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v,f"{v:,.0f}",ha="center",va="bottom",fontsize=9)
        fig.tight_layout(); out.append(save(fig,"commitment",len(out)+1))

    if "bottlenecks" in wanted:
        x=None
        if extras: x=extras.get("bottlenecks")
        if x is None or getattr(x,"empty",True):
            if "STAGE_FA" in df.columns: x=df["STAGE_FA"].fillna("").astype(str).value_counts().head(10).sort_values()
        if x is not None and not getattr(x,"empty",True):
            if isinstance(x,pd.DataFrame):
                num=x.select_dtypes(include="number").columns
                if len(num): vals=x[num[0]].head(10); labs=x.index.astype(str)[:len(vals)]
                else: vals=x.iloc[:,0].value_counts().head(10).sort_values(); labs=vals.index.astype(str)
            else: vals=x; labs=x.index.astype(str)
            fig,ax=plt.subplots(figsize=(8.8,4)); ax.barh(list(labs),list(vals),color=ORANGE)
            ax.set_title(EMAIL_CHARTS["bottlenecks"],fontsize=13,fontweight="bold"); fig.tight_layout()
            out.append(save(fig,"bottlenecks",len(out)+1))

    if "risk_mix" in wanted and "طبقه ریسک" in df.columns:
        vc=df["طبقه ریسک"].fillna("").astype(str).replace("", "نامشخص").value_counts()
        fig,ax=plt.subplots(figsize=(8.8,3.7)); ax.bar(vc.index.astype(str),vc.values,color=ORANGE,edgecolor="white")
        ax.set_title(EMAIL_CHARTS["risk_mix"],fontsize=13,fontweight="bold"); ax.set_ylabel("پرونده")
        fig.tight_layout(); out.append(save(fig,"risk_mix",len(out)+1))

    if "org_workload" in wanted and "ORG_DEPT" in df.columns:
        vc=df["ORG_DEPT"].fillna("").astype(str).replace("", "نامشخص").value_counts().head(12).sort_values()
        fig,ax=plt.subplots(figsize=(8.8,4)); ax.barh(vc.index.astype(str),vc.values,color=THEME,edgecolor="white")
        ax.set_title(EMAIL_CHARTS["org_workload"],fontsize=13,fontweight="bold"); ax.set_xlabel("پرونده")
        fig.tight_layout(); out.append(save(fig,"org_workload",len(out)+1))
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

def _health_banner(folder)->str:
    """اگر داده امروز ناقص بود، خواننده باید **قبل از اعداد** بداند.

    بدون این بنر، «۰ سفارش خارج از Commercial Expert Data» و «فایل
    بارگذاری نشد» در ایمیل یک شکل دارند.
    """
    from .. import health as _h
    data=_h.load(str(folder))
    if not data: return ""
    verdict=data.get("verdict",""); blocking=data.get("blocking") or []
    if verdict==_h.OK and not blocking: return ""
    c=data.get("counts",{})
    bits=[f"وضعیت داده امروز: <b>{html.escape(str(verdict))}</b>"]
    if blocking: bits.append("سورس الزامیِ ناموجود: "+html.escape("، ".join(blocking)))
    bits.append(f"سورس سالم/ناقص/خراب: {c.get('سورس سالم',0)} / "
                f"{c.get('سورس ناقص',0)} / {c.get('سورس خراب/ردشده',0)}")
    return (f'<div style="background:{ORANGE}1a;border-right:4px solid {ORANGE};'
            f'padding:10px 14px;border-radius:8px;margin:0 0 14px;font-size:13px;'
            f'color:{TEXT}">⚠️ ' + " — ".join(bits) +
            ' <div style="font-size:12px;margin-top:4px">جزئیات در شیت «۱۷. سلامت '
            'سیستم» گزارش رسمی است. KPIهای وابسته به سورس‌های ناقص را با احتیاط '
            'بخوانید.</div></div>')

#: حداکثر کارت KPI در یک ردیف جدول ایمیل.
#: تا پیش از این همه کارت‌ها در یک ``<tr>`` با ``width:20%`` می‌رفتند؛ با شش
#: KPI مجموع عرض ۱۲۰٪ می‌شد و Outlook کارت آخر را می‌فشرد تا برچسب بلندی
#: مثل «سفارش خارج از Commercial Expert Data» از کارت بیرون بزند.
KPI_PER_ROW = 3


def _kpi_cards(kpis:Iterable[dict[str,Any]])->str:
    """کارت‌های سنجه — شبکه‌ای، با رنگ سنجیده‌شده.

    رنگ نوار بالای کارت هم از همان پله ``ink`` می‌آید: یک نوار ۴ پیکسلی
    حامل معناست (کدام KPI هشدار است) و طبق WCAG 1.4.11 باید کف ۳:۱ را
    بگذراند — ``#F39C12`` نمی‌گذراند.
    """
    items = list(kpis)
    if len(items) > KPI_PER_ROW:
        rows = [items[i:i + KPI_PER_ROW] for i in range(0, len(items), KPI_PER_ROW)]
        return "".join(_kpi_cards(r) for r in rows)
    width = f"{100 // max(len(items), 1)}%"
    colors = {"red": RED, "amber": ORANGE, "green": GREEN}
    cards = []
    for k in items:
        c = colors.get(k.get("tone"), _T.TEAL_INK)
        cards.append(
            f'<td style="width:{width};padding:7px;vertical-align:top">'
            f'<div style="background:#fff;border:1px solid {BORDER};'
            f'border-top:3px solid {c};border-radius:12px;padding:13px;text-align:center">'
            f'<div style="font-size:12px;color:{TEXT2}">{html.escape(str(k["label"]))}</div>'
            f'<div style="font-size:25px;font-weight:800;color:{c};margin:4px 0">'
            f'{html.escape(str(k["value"]))}</div>'
            f'<div style="font-size:10px;color:{TEXT3}">{html.escape(str(k.get("note","")))}</div>'
            f'</div></td>')
    return "<tr>" + "".join(cards) + "</tr>"

def build_email_html(day:date,df:pd.DataFrame,charts:list[Path],excel:Path)->str:
    img="".join(f'<tr><td style="padding:8px 0"><img src="cid:chart_{i}" width="100%" style="display:block;border:1px solid {BORDER};border-radius:10px" alt="Executive chart"></td></tr>' for i,_ in enumerate(charts,1))
    rows=[]
    if "BL_CRITICAL" in df.columns:
        g=df[df["BL_CRITICAL"].astype(bool)].drop_duplicates("CANONICAL_BL").head(6) if "CANONICAL_BL" in df.columns else df.iloc[0:0]
        for _,r in g.iterrows(): rows.append((r.get("CANONICAL_BL","—"),r.get("BL_CRITICAL_MATERIALS","—"),r.get("BL_CRITICAL_REASON","—")))
    table="".join(f'<tr><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(a))}</td><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(b))}</td><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(c))}</td></tr>' for a,b,c in rows)
    cause=(f'<div style="margin:18px 0 8px;font-size:16px;font-weight:800;color:{NAVY}">نمونه بارنامه‌های بحرانی و علت</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px"><tr style="background:{THEME};color:#fff"><th style="padding:8px">بارنامه</th><th style="padding:8px">متریال</th><th style="padding:8px">علت</th></tr>{table}</table>') if table else ""
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"></head><body style="margin:0;background:{BG};font-family:'IRANSans Light','IRANSans',Tahoma,Arial,sans-serif;color:{TEXT}"><table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:18px 8px"><table width="820" cellpadding="0" cellspacing="0" style="max-width:820px;width:100%;background:#fff;border:1px solid {BORDER};border-radius:16px;overflow:hidden"><tr><td style="padding:22px 28px;background:{NAVY}"><div style="color:#fff;font-size:24px;font-weight:800">GSI · Executive Daily Insight</div><div style="color:#d9f1ed;font-size:13px;margin-top:5px">Global Sourcing Intelligence · Data • Process • Decision · {day:%Y-%m-%d}</div></td></tr><tr><td style="padding:20px 24px">{_health_banner(excel.parent)}<table width="100%" cellpadding="0" cellspacing="0">{_kpi_cards(executive_kpis(df))}</table><div style="margin:20px 0 12px;font-size:18px;font-weight:800;color:{NAVY}">سه نگاه برای تصمیم امروز</div><table width="100%" cellpadding="0" cellspacing="0">{img}</table><div style="margin:18px 0 10px;font-size:17px;font-weight:800;color:{NAVY}">چرا فایل Excel را باز کنیم؟</div><div style="background:#f5faf8;border:1px solid {BORDER};border-radius:10px;padding:14px;line-height:1.9;font-size:13px">در ایمیل فقط <b>سیگنال مدیریتی</b> را می‌بینید؛ جزئیات تصمیم در Excel است: متریال‌های بحرانی، علت بحرانی شدن هر بارنامه/سفارش، مقاومت، موجودی، تعهد ارزی، گلوگاه فرآیند و ردیابی پرونده. <b>یک متریال بحرانی، کل پرونده را بحرانی می‌کند؛ علت آن در فایل تا سطح متریال قابل مشاهده است.</b></div>{cause}<div style="margin-top:20px;text-align:center"><span style="display:inline-block;background:{THEME};color:#fff;border-radius:9px;padding:11px 18px;font-weight:800">📎 {html.escape(excel.name)}</span></div></td></tr><tr><td style="padding:14px 24px;background:#f7f9f9;color:#6b7b88;font-size:11px">این پیام توسط GSI تولید شده است · داده‌ها از Pipeline همان روز استخراج شده‌اند.</td></tr></table></td></tr></table></body></html>'''

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
    raw_charts = os.environ.get("GSI_EMAIL_CHARTS", "").strip()
    selected_charts = [x.strip() for x in raw_charts.split(",") if x.strip()] if raw_charts else None
    charts=make_email_charts(res.main,paths["assets"],selected=selected_charts,extras=res.extras)
    body=build_email_html(d,res.main,charts,excel); paths["html"].write_text(body,encoding="utf-8")
    to=_recipients()
    result={"excel":excel,"html":paths["html"],"charts":charts,"recipients":to,"sent":False}
    if not(send or display): return result
    if not to:
        # بی‌صدا به فهرست قدیمی نمی‌رویم — فهرست گیرندگان پیکربندی محرمانه است.
        raise NoRecipients(
            "هیچ گیرنده‌ای پیکربندی نشده است. یکی از این‌ها را تنظیم کنید:\n"
            f"    {RECIPIENTS_ENV}=\"a@example.invalid;b@example.invalid\"\n"
            f"    {RECIPIENTS_FILE_ENV}=/path/to/{RECIPIENTS_BASENAME}\n"
            f"    یا فایل {RECIPIENTS_BASENAME} را در GSI_HOME بگذارید،\n"
            f"    یا {HR_ENABLE_ENV}=1 تا از ستون Email سورس HR خوانده شود.\n"
            "نمونه: recipients.example.yaml")
    with _outlook_session() as win32:
        outlook=win32.Dispatch("Outlook.Application")
        mail=outlook.CreateItem(0)
        mail.BodyFormat=2  # olFormatHTML
        mail.Subject=f"GSI Executive Daily Insight — {d:%Y-%m-%d}"
        mail.To="; ".join(to)
        sender=os.environ.get("GSI_EMAIL_SENDER","").strip().lower()
        if sender:
            matched=False
            try:
                for account in outlook.Session.Accounts:
                    if str(getattr(account,"SmtpAddress","")).strip().lower()==sender:
                        mail.SendUsingAccount=account
                        matched=True
                        break
            except Exception as ex:
                log.warning("انتخاب حساب فرستنده ناموفق بود: %s", ex)
            if not matched:
                raise RuntimeError(f"حساب Outlook با نشانی فرستنده «{sender}» پیدا نشد.")
        for i,ch in enumerate(charts,1): _add_inline(mail,ch,f"chart_{i}")
        if Path(excel).exists(): mail.Attachments.Add(str(excel.resolve()))
        mail.HTMLBody=body
        mail.Save()  # قبل از Display/Send تا بدنه و CIDها پایدار شوند
        if send:
            mail.Send()
            result["sent"]=True
        elif display:
            mail.Display()
        return result

def create_studio_email(*, day: Optional[date], df: pd.DataFrame, excel: Path, selected_charts=None, send: bool=False, display: bool=True, subject: Optional[str]=None) -> Dict[str,Any]:
    """ارسال/نمایش گزارش فیلترشده Studio در Classic Outlook."""
    d=day or date.today(); to=_recipients()
    if not to: raise NoRecipients("گیرنده‌ای پیدا نشد. GSI_EMAIL_TO یا recipients.yaml یا GSI_EMAIL_FROM_HR را تنظیم کنید.")
    assets=Path(excel).parent/"studio_email_assets";assets.mkdir(parents=True,exist_ok=True)
    charts=make_email_charts(df,assets,selected=selected_charts,extras={});body=build_email_html(d,df,charts,Path(excel))
    with _outlook_session() as win32:
        outlook=win32.Dispatch("Outlook.Application")
        mail=outlook.CreateItem(0)
        mail.BodyFormat=2
        mail.Subject=subject or f"GSI Studio — گزارش فیلترشده — {d:%Y-%m-%d}"
        mail.To="; ".join(to)
        sender=os.environ.get("GSI_EMAIL_SENDER","").strip().lower()
        if sender:
            matched=False
            try:
                for account in outlook.Session.Accounts:
                    if str(getattr(account,"SmtpAddress","")).strip().lower()==sender:
                        mail.SendUsingAccount=account
                        matched=True
                        break
            except Exception as ex:
                raise RuntimeError(f"انتخاب حساب فرستنده Outlook ناموفق بود: {ex}") from ex
            if not matched:
                raise RuntimeError(f"حساب Outlook با نشانی فرستنده «{sender}» پیدا نشد.")
        for i,ch in enumerate(charts,1): _add_inline(mail,ch,f"chart_{i}")
        if Path(excel).exists(): mail.Attachments.Add(str(Path(excel).resolve()))
        mail.HTMLBody=body
        mail.Save()
        if send: mail.Send()
        elif display: mail.Display()
        return {"sent":bool(send),"recipients":len(to),"charts":len(charts)}

def _s_action(v: Any) -> str:
    return "" if v is None else str(v).strip()


def build_case_action_html(action: Dict[str, Any]) -> str:
    """HTML مینیمال و قابل ممیزی برای پیشنهاد یک پرونده."""
    def e(k: str, default: str = "—") -> str:
        v = action.get(k, default)
        txt = default if v is None or str(v).strip() == "" else str(v)
        return html.escape(txt).replace("\n", "<br>")
    priority = e("PRIORITY")
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"></head>
<body style="margin:0;background:{BG};font-family:'IRANSans Light','IRANSans',Tahoma,Arial,sans-serif;color:{TEXT}">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:18px 8px">
<table width="760" cellpadding="0" cellspacing="0" style="max-width:760px;width:100%;background:#fff;border:1px solid {BORDER};border-radius:16px;overflow:hidden">
<tr><td style="padding:22px 28px;background:{NAVY}"><div style="color:#fff;font-size:23px;font-weight:800">GSI · Case Action</div>
<div style="color:#d9f1ed;font-size:12px;margin-top:5px">Data • Process • Decision · پیشنهاد نیازمند بازبینی انسانی</div></td></tr>
<tr><td style="padding:22px 26px;line-height:1.9;font-size:13px">
<table width="100%" cellpadding="7" cellspacing="0" style="border-collapse:collapse;background:#fbfcfc;border:1px solid {BORDER}">
<tr><td><b>پرونده / REG</b></td><td>{e('KEY_REG')}</td><td><b>اولویت</b></td><td>{priority}</td></tr>
<tr><td><b>اقدام پیشنهادی</b></td><td colspan="3">{e('TITLE')}</td></tr>
<tr><td><b>مالک پیشنهادی</b></td><td>{e('OWNER_ROLE')}</td><td><b>موعد داخلی</b></td><td>{e('DUE_DATE')}</td></tr>
<tr><td><b>علت</b></td><td colspan="3">{e('RATIONALE')}</td></tr>
<tr><td><b>شکاف شواهد</b></td><td colspan="3">{e('EVIDENCE_GAPS')}</td></tr>
<tr><td><b>مبنای پیشنهاد</b></td><td colspan="3">{e('RULE_BASIS')}</td></tr>
<tr><td><b>شناسه اقدام</b></td><td colspan="3">{e('ACTION_ID')}</td></tr>
</table>
<div style="margin-top:18px;padding:12px 14px;border:1px solid #e9c98b;background:#fff8e8;border-radius:10px">
این پیام یک <b>پیشنهاد تحلیلی GSI</b> است. Investigation Signal به‌تنهایی حکم تقلب، تخلف حقوقی یا الزام قانونی نیست؛ پیش از ارسال نهایی، مسئول پرونده باید متن و شواهد را بازبینی کند.
</div></td></tr>
<tr><td style="padding:13px 24px;background:#f7f9f9;color:#6b7b88;font-size:11px">GSI | Global Sourcing Intelligence · Data • Process • Decision</td></tr>
</table></td></tr></table></body></html>'''


def create_case_action_email(action: Dict[str, Any], *, to: Optional[Iterable[str] | str] = None,
                             send: bool = False, display: bool = True) -> Dict[str, Any]:
    """Draft Outlook برای یک Case Action؛ پیش‌فرض هرگز ارسال مستقیم نیست."""
    if isinstance(to, str):
        recipients = _split(to)
    elif to is not None:
        recipients = [str(x).strip() for x in to if str(x).strip() and "@" in str(x)]
    else:
        recipients = _recipients()
    if not recipients:
        raise NoRecipients("برای Draft پرونده گیرنده وارد کنید یا GSI_EMAIL_TO/recipients.yaml را تنظیم کنید.")
    body = build_case_action_html(action)
    subject = _s_action(action.get("EMAIL_SUBJECT")) or f"GSI | اقدام پیشنهادی پرونده {_s_action(action.get('KEY_REG'))}"
    with _outlook_session() as win32:
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.BodyFormat = 2
        mail.Subject = subject
        mail.To = "; ".join(recipients)
        sender = os.environ.get("GSI_EMAIL_SENDER", "").strip().lower()
        if sender:
            matched = False
            for account in outlook.Session.Accounts:
                if str(getattr(account, "SmtpAddress", "")).strip().lower() == sender:
                    mail.SendUsingAccount = account
                    matched = True
                    break
            if not matched:
                raise RuntimeError(f"حساب Outlook با نشانی فرستنده «{sender}» پیدا نشد.")
        mail.HTMLBody = body
        mail.Save()
        if send:
            mail.Send()
        elif display:
            mail.Display()
        return {"sent": bool(send), "drafted": not send, "recipients": len(recipients),
                "action_id": action.get("ACTION_ID", ""), "subject": subject}

def main(argv=None)->int:
    import argparse
    ap=argparse.ArgumentParser(description="GSI Executive Daily Insight email"); ap.add_argument("--send",action="store_true"); ap.add_argument("--no-display",action="store_true")
    a=ap.parse_args(argv); r=create_daily_email(send=a.send,display=not a.no_display)
    print(f"Excel: {r['excel']}"); print(f"HTML: {r['html']}"); print(f"Charts: {len(r['charts'])}"); print(f"Recipients: {len(r['recipients'])}"); print(f"Sent: {r['sent']}"); return 0
if __name__=="__main__": raise SystemExit(main())

# ── V27.1 Personal Store Email ─────────────────────────────────────────────
def build_personal_store_email_html(employee_code: str) -> str:
    """Render per-user HTML only from encrypted profile/current.gsi shared-folder state."""
    from ..personalization.personal_html import build_personal_html
    return build_personal_html(employee_code, title="GSI · گزارش شخصی")


def create_personal_store_email(employee_code: str, *, to: Iterable[str] | str,
                                send: bool = False, display: bool = True,
                                subject: Optional[str] = None) -> Dict[str, Any]:
    """Create an Outlook draft from the user's encrypted shared-folder snapshot.

    No operational source is queried here. The body is generated from
    ``GSI_PROFILE_ROOT/<EMP>/profile.gsi`` and ``current.gsi`` only.
    """
    recipients = _split(to) if isinstance(to, str) else [str(x).strip() for x in to if "@" in str(x)]
    if not recipients:
        raise NoRecipients("برای گزارش شخصی گیرنده معتبر لازم است.")
    body = build_personal_store_email_html(employee_code)
    with _outlook_session() as win32:
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.BodyFormat = 2
        mail.Subject = subject or f"GSI | گزارش شخصی {employee_code}"
        mail.To = "; ".join(recipients)
        mail.HTMLBody = body
        mail.Save()
        if send:
            mail.Send()
        elif display:
            mail.Display()
    return {"sent": bool(send), "drafted": not send, "recipients": len(recipients),
            "employee_code": employee_code, "subject": subject or f"GSI | گزارش شخصی {employee_code}"}
