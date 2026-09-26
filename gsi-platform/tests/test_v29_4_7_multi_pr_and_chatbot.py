from pathlib import Path
import pandas as pd

from gsi.adapters.moghavemat import MoghavematAdapter
from gsi.studio_core.html_export import build_dynamic_html
from gsi.knowledge_desk.config import KnowledgeDeskConfig
from gsi.knowledge_desk.indexer import build_index
from gsi.knowledge_desk.static_export import publish_static


def _sample_mogh():
    rows = [
        [124, "843115", "6100002273", "", 9654003280, "رينگ ضدقفل مغناطيسي", ""],
        [168, "843115", "6100002723", 20, 9654003280, "هدف چرخشي ترمز ضدقفل", "ABS RADIAL TARGET"],
        [169, "843120", "6100002854", 20, 9654003280, "هدف چرخشي ترمز ضدقفل", "ABS RADIAL TARGET"],
        [170, "843120", "6100002854", 20, 9654003280, "هدف چرخشي ترمز ضدقفل", "ABS RADIAL TARGET"],
    ]
    return pd.DataFrame(rows, columns=[
        "Row No.", "Order No.\n(Our Reference)", "PR No.", "PR Item", "Material",
        "Material Description", "Material Short Text",
    ])


def test_multi_pr_is_preserved_at_relation_grain():
    out = MoghavematAdapter().transform({"Expert Data": _sample_mogh()})
    main = out["main"].set_index("KEY_ORDER")
    assert int(main.loc["843115", "MOGH_PR_COUNT"]) == 2
    assert main.loc["843115", "MOGH_MULTI_PR"] in (True, 1)
    assert "6100002273" in main.loc["843115", "MOGH_PRS_ALL"]
    assert "6100002723" in main.loc["843115", "MOGH_PRS_ALL"]

    rel = out["order_material_pr_item"]
    a = rel[(rel.KEY_ORDER == "843115") & (rel.KEY_PR == "6100002723")].iloc[0]
    assert a["MOGH_PR_ITEM"] == "20"
    assert int(a["MOGH_EVIDENCE_COUNT"]) == 1
    b = rel[(rel.KEY_ORDER == "843120") & (rel.KEY_PR == "6100002854")].iloc[0]
    assert int(b["MOGH_EVIDENCE_COUNT"]) == 2
    assert b["MOGH_SOURCE_ROWS"] == "169,170"


def test_report_html_renders_chatbot_without_optional_content():
    html = build_dynamic_html(
        pd.DataFrame([{"KEY_MATERIAL": "9654003280"}]),
        "2026-09-21",
        selected_fields=["KEY_MATERIAL"],
        learning_lesson=None,
        knowledge_chat={"chatbot_href": "file:///X:/GSI/chatbot.html"},
    )
    assert "💬 چت‌بات" in html
    assert "file:///X:/GSI/chatbot.html" in html
    assert "سؤال بازرگانی خود را بنویسید" in html
    assert "آموزش هفتگی" not in html


def test_static_chatbot_does_not_use_weekly_wording(tmp_path: Path):
    knowledge = tmp_path / "knowledge"
    publish = knowledge / "_GSI_CHATBOT"
    knowledge.mkdir()
    (knowledge / "faq.txt").write_text(
        "سؤال: ثبت سفارش چیست؟\nپاسخ: ثبت سفارش یکی از مراحل فرآیند بازرگانی خارجی است و باید بر اساس مدارک معتبر پیگیری شود.",
        encoding="utf-8",
    )
    cfg = KnowledgeDeskConfig(
        knowledge_path=str(knowledge), lessons_path="", publish_path=str(publish),
        db_path=str(tmp_path / "kb.sqlite"), enabled=True,
    )
    build_index(cfg)
    result = publish_static(cfg)
    text = Path(result["entrypoint"]).read_text(encoding="utf-8")
    assert "آموزش این هفته" not in text
    assert "آموزش هفتگی" not in text
    assert (publish / "chatbot_content.json").exists()
