"""Behavior checks for isolated report tables and the blocks-only document."""
import re
import unittest

import pandas as pd

from gsi.design.css import stylesheet
from gsi.studio_core.composer import normalize_tabs
from gsi.studio_core.html_export import build_dynamic_html


class ComposerTablesTest(unittest.TestCase):
    def test_two_tables_keep_columns_and_filter_outside_display_columns(self):
        source = pd.DataFrame({"KEY_MATERIAL": ["M1", "M2"],
                               "KEY_REG": ["R1", "R2"], "ORG_DEPT": ["A", "B"]})
        tab = {"id": "one", "title": "صرفاً داده", "fields": ["KEY_MATERIAL"],
               "blocks": ["table", "table__abc123"],
               "table_fields": {"table": ["KEY_MATERIAL"], "table__abc123": ["KEY_REG"]},
               "table_titles": {"table": "قطعات", "table__abc123": "ثبت سفارش‌ها"},
               "filter_fields": ["ORG_DEPT"]}
        self.assertEqual(normalize_tabs([tab], ["KEY_MATERIAL"], "expert")[0]["blocks"],
                         ["table", "table__abc123"])
        output = build_dynamic_html(source, "2026-09-29", tabs=[tab],
                                    selected_fields=["KEY_MATERIAL"], blocks_only=True,
                                    include_decision_brief=False, include_material_view=False)
        self.assertIn('id="tb_0"', output)
        self.assertIn('id="tb_0_table__abc123"', output)
        self.assertIn('data-f="ORG_DEPT"', output)
        self.assertIn('"tables": [{"key": "table", "fields": ["KEY_MATERIAL"]', output)
        self.assertIn('"key": "table__abc123", "fields": ["KEY_REG"]', output)
        self.assertIn('onclick="downloadFilteredXlsx(\'table__abc123\')"', output)
        self.assertNotIn('class="app-bar"', output)
        self.assertNotIn('class="toolbar split no-print"', output)
        self.assertNotIn('role="tablist"', output)
        self.assertNotIn('<footer', output)
        self.assertNotIn('دفتر کامل شواهد کارشناسان', output)

    def test_empty_block_selection_stays_empty_and_table_rules_are_visible(self):
        self.assertEqual(normalize_tabs([{"title": "خالی", "blocks": []}], ["KEY_REG"],
                                        "expert")[0]["blocks"], [])
        css = stylesheet()
        self.assertIn('.detail-table tbody td', css)
        self.assertIn('border-left:1px solid var(--border-strong)', css)


if __name__ == "__main__":
    unittest.main()
