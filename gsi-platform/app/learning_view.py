# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import streamlit as st

from gsi.knowledge_desk import (
    KnowledgeDeskConfig, answer, build_index, discover_lessons,
    load_config, save_config, status, publish_static, path_to_file_uri, validate_paths,
)


def _browse_folder(label: str, key: str, initial: str = "", allow_create: bool = False) -> str:
    """Server-side folder browser for local/UNC shared folders."""
    if key not in st.session_state:
        st.session_state[key] = initial or ""
    st.markdown(f"**{label}**")
    path = st.text_input("مسیر", value=st.session_state[key], key=f"{key}_text",
                         placeholder=r"مثلاً \\SERVER\Share\GSI_Knowledge")
    if path != st.session_state[key]:
        st.session_state[key] = path
    p = Path(path) if path else None
    c1,c2 = st.columns([1,3])
    if c1.button("⬆ پوشه بالاتر", key=f"{key}_up", disabled=not (p and p.parent != p)):
        st.session_state[key] = str(p.parent); st.rerun()
    if p and p.exists() and p.is_dir():
        try:
            dirs = sorted([x.name for x in p.iterdir() if x.is_dir() and not x.name.startswith(".")], key=str.lower)
        except Exception:
            dirs=[]
        chosen = c2.selectbox("زیرپوشه", ["—"] + dirs, key=f"{key}_child")
        if chosen != "—" and st.button(f"ورود به {chosen}", key=f"{key}_open"):
            st.session_state[key] = str(p / chosen); st.rerun()
        st.caption("✅ این مسیر از دید برنامه قابل دسترسی است.")
    elif path:
        if allow_create:
            st.info("این فولدر هنوز وجود ندارد؛ هنگام ساخت چت‌بات ایجاد می‌شود (به شرط دسترسی نوشتن روی پوشه والد).")
        else:
            st.error("این مسیر از دید برنامه قابل دسترسی نیست.")
    return st.session_state[key]


def run():
    st.markdown("## 💬 دستیار دانش بازرگانی GSI")
    st.caption("Shared Folder-only · بدون اینترنت · بدون سرور · بدون AnythingLLM. خروجی یک chatbot.html مستقل است.")

    cfg = load_config()
    try: s = status(cfg)
    except Exception: s = {"documents":0,"chunks":0,"quarantine":0,"questions":0,"last_indexed_at":"—"}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("اسناد فعال", f"{s.get('documents',0):,}")
    c2.metric("قطعات دانش", f"{s.get('chunks',0):,}")
    c3.metric("Quarantine", f"{s.get('quarantine',0):,}")
    c4.metric("حالت", "آفلاین / Zero-server")

    with st.container(border=True):
        st.markdown("### ۱ · مسیرهای منبع")
        kpath = _browse_folder("پایگاه دانش سازمانی", "kb_pick_knowledge", cfg.knowledge_path)
        lpath = _browse_folder("پوشه محتوای چت‌بات (اختیاری)", "kb_pick_lessons", cfg.lessons_path)

    with st.container(border=True):
        st.markdown("### ۲ · مسیر انتشار چت‌بات")
        default_publish = cfg.publish_path or (str(Path(kpath) / "_GSI_CHATBOT") if kpath else "")
        if "kb_pick_publish" not in st.session_state and default_publish:
            st.session_state["kb_pick_publish"] = default_publish
        publish = _browse_folder("فولدر مشترک خروجی", "kb_pick_publish", default_publish, allow_create=True)
        st.caption("فایل‌های chatbot.html، knowledge_index.json، chatbot_content.json و manifest.json در این مسیر ساخته می‌شوند. chatbot.html برای کار کردن به سرور نیاز ندارد.")

    with st.container(border=True):
        st.markdown("### ۳ · ایجاد / به‌روزرسانی")
        if st.button("🚀 ایجاد / به‌روزرسانی چت‌بات آفلاین", type="primary", width="stretch"):
            newcfg = KnowledgeDeskConfig(
                knowledge_path=kpath, lessons_path=lpath, db_path=cfg.db_path,
                publish_path=publish, enabled=True,
                title="دستیار دانش بازرگانی GSI",
                # legacy network-service fields intentionally left unused
                host=cfg.host, port=cfg.port, public_url="",
            )
            preflight = validate_paths(newcfg, require_publish=True)
            if not preflight["ok"]:
                st.error("ساخت متوقف شد: مسیرهای منبع/خروجی با هم تداخل نامعتبر دارند.")
                for issue in preflight["issues"]:
                    st.write(f"• {issue['code']}: {issue['detail']}")
            else:
                save_config(newcfg)
                try:
                    with st.spinner("در حال ایندکس فایل‌های جدید/تغییرکرده و ساخت بسته آفلاین…"):
                        idx = build_index(newcfg)
                        pub = publish_static(newcfg)
                    st.session_state["kb_last_build"] = {"index":idx,"publish":pub}
                    st.success(f"آماده شد · {pub['documents']} سند · {pub['chunks']} قطعه دانش · {pub['lessons']} محتوای تکمیلی")
                    st.info(f"فایل اصلی: {pub['entrypoint']}")
                except Exception as ex:
                    msg=str(ex)
                    if msg.startswith("BLOCKED_EMPTY_KNOWLEDGE"):
                        st.error("ساخت متوقف شد: هیچ سند واقعی قابل استفاده‌ای در مسیرهای انتخاب‌شده ایندکس نشد.")
                        st.caption("مسیر پایگاه دانش و محتوای چت‌بات را بررسی کنید؛ فایل خروجی chatbot خودش منبع دانش محسوب نمی‌شود.")
                    else:
                        st.error(f"ساخت ناموفق بود: {msg}")
        if st.session_state.get("kb_last_build"):
            st.json(st.session_state["kb_last_build"], expanded=False)

    cfg = load_config()
    entry = Path(cfg.chatbot_path) if cfg.chatbot_path else None
    with st.container(border=True):
        st.markdown("### ۴ · تست قبل از ارسال")
        q=st.text_area("سؤال بازرگانی", placeholder="مثلاً برای تمدید ثبت سفارش چه مدارکی لازم است؟", height=95)
        if st.button("پرسیدن در موتور Python", disabled=not q.strip()):
            try:
                r=answer(cfg,q)
                st.markdown(r["answer"])
                if r.get("sources"):
                    with st.expander("منابع"):
                        for x in r["sources"]: st.write(f"• {x['title']}")
            except Exception as ex: st.error(str(ex))
        if entry and entry.exists():
            st.success("chatbot.html ساخته شده و آماده قرار گرفتن روی Shared Folder است.")
            st.code(path_to_file_uri(str(entry)), language=None)
        else:
            st.info("پس از ساخت، فایل chatbot.html اینجا قابل تأیید خواهد بود.")

    with st.container(border=True):
        st.markdown("### ۵ · چت‌بات")
        lessons=discover_lessons(cfg.lessons_path)
        if not lessons:
            st.info("محتوای تکمیلی جداگانه‌ای تعریف نشده است؛ چت‌بات با پایگاه دانش اصلی کار می‌کند.")
        else:
            labels={x['id']:x['title'] for x in lessons}
            pick=st.selectbox("پیش‌نمایش محتوای چت‌بات", list(labels), format_func=lambda x:labels[x])
            lesson=next(x for x in lessons if x['id']==pick)
            st.markdown(f"#### {lesson['title']}")
            st.write(lesson['body'][:5000])

    st.caption("نکته: مرورگر باید اجازه باز کردن فایل شبکه را داشته باشد. اگر Policy سازمان file:// را مسدود کند، خود موتور آفلاین سالم است ولی لینک از ایمیل باید با مسیر مورد تأیید IT/DFS یا Drive Mapping سازمان ارائه شود.")
