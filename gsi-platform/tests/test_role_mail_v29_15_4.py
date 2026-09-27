# -*- coding: utf-8 -*-
"""No Outlook send: verify exact HR routing and at-most-once dispatch guard."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pandas as pd

from gsi.integrations.role_mail import plan_messages, render_html, dispatch, outlook_message
from gsi.warehouse.store import Warehouse


def hr():
    return pd.DataFrame([
        ("101", "مریم کارشناس", "کارشناس خرید خارجی", "m@example.com", "فعال", "لیلا رئیس", "علی مدیر", "معاونت خرید"),
        ("102", "لیلا رئیس", "رئیس اداره", "h@example.com", "فعال", "", "علی مدیر", "معاونت خرید"),
        ("103", "علی مدیر", "مدیر خرید", "d@example.com", "فعال", "", "", "معاونت خرید"),
        ("104", "فرد غیرفعال", "کارشناس", "off@example.com", "غیرفعال", "", "", "معاونت خرید"),
    ], columns=["KEY_EMP", "HR_FULL_NAME", "HR_POST", "HR_EMAIL", "HR_STATUS", "HR_HEAD", "HR_MANAGER", "HR_VICE"])


def rows():
    return pd.DataFrame([{
        "CANONICAL_REG": "R1", "EXPERT_BUYER": "مریم کارشناس",
        "CANONICAL_EXPERT": "مریم کارشناس", "EXPERT_ROLE": "کارشناس خرید خارجی",
        "NEXT_ACTION_TITLE": "پیگیری سفارش <فوری>", "NEXT_ACTION_OWNER": "خرید",
        "NEXT_ACTION_PRIORITY": "فوری", "NEXT_ACTION_DUE_DATE": "1405/07/06",
    }])


class RoleMailTests(unittest.TestCase):
    def test_exact_owner_to_and_requested_cc(self):
        plans, skipped = plan_messages(rows(), hr(), run_id="published-1",
                                       cc_levels=("head", "manager"), role_keys=("EXPERT_BUYER",))
        self.assertEqual(skipped, {})
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].to, "m@example.com")
        self.assertEqual(plans[0].cc, ("h@example.com", "d@example.com"))
        self.assertEqual(len(plans[0].cases), 1)
        self.assertIn("&lt;فوری&gt;", render_html(plans[0]))

    def test_no_role_guess_or_inactive_recipient(self):
        df = rows()
        df.loc[0, "CANONICAL_EXPERT"] = "فرد غیرفعال"
        df.loc[0, "EXPERT_BUYER"] = "فرد غیرفعال"
        plans, skipped = plan_messages(df, hr(), run_id="published-1", cc_levels=())
        self.assertEqual(plans, [])
        self.assertEqual(skipped["OWNER_HR_UNRESOLVED"], 1)
        with self.assertRaises(ValueError):
            plan_messages(rows(), hr(), run_id="published-1", role_keys=("EXPERT_TRANSPORT",))

    def test_ambiguous_or_missing_cc_blocks_message(self):
        h = hr()
        h.loc[len(h)] = ("105", "لیلا رئیس", "رئیس اداره", "another@example.com", "فعال", "", "", "معاونت دیگر")
        plans, skipped = plan_messages(rows(), h, run_id="published-1", cc_levels=("head",))
        self.assertEqual(plans, [])
        self.assertEqual(skipped["CC_HEAD_UNRESOLVED"], 1)

    def test_blank_email_duplicate_name_still_blocks_owner(self):
        h = hr()
        h.loc[len(h)] = ("105", "مریم کارشناس", "کارشناس خرید خارجی", "", "فعال", "", "", "معاونت خرید")
        plans, skipped = plan_messages(rows(), h, run_id="published-1", cc_levels=())
        self.assertEqual(plans, [])
        self.assertEqual(skipped["OWNER_HR_UNRESOLVED"], 1)

    def test_wrong_action_owner_is_not_mailed(self):
        df = rows()
        df.loc[0, "NEXT_ACTION_OWNER"] = "ترخیص"
        plans, _ = plan_messages(df, hr(), run_id="published-1", cc_levels=())
        self.assertEqual(plans, [])
        df.loc[0, "NEXT_ACTION_OWNER"] = "مدیر خرید"
        plans, _ = plan_messages(df, hr(), run_id="published-1", cc_levels=())
        self.assertEqual(plans, [])

    def test_outlook_draft_addresses_are_exact_and_never_send(self):
        plans, _ = plan_messages(rows(), hr(), run_id="published-1", cc_levels=("head", "manager"))
        class Mail:
            def __init__(self):
                self.Recipients = type("Recipients", (), {"ResolveAll": lambda s: True})()
                self.saved = self.sent = False
            def Save(self): self.saved = True
            def Send(self): self.sent = True
        mail = Mail()
        class Outlook:
            def CreateItem(self, kind):
                self.kind = kind
                return mail
        outlook = Outlook()
        @contextmanager
        def session():
            yield type("Com", (), {"Dispatch": lambda s, name: outlook})()
        with patch("gsi.integrations.daily_email._outlook_session", session), patch.dict(os.environ, {"GSI_EMAIL_SENDER": ""}):
            result = outlook_message(plans[0], ref_date="1405/07/06")
        self.assertEqual(outlook.kind, 0)
        self.assertEqual(mail.To, "m@example.com")
        self.assertEqual(mail.CC, "h@example.com; d@example.com")
        self.assertTrue(mail.saved)
        self.assertFalse(mail.sent)
        self.assertFalse(result["sent"])

    def test_duplicate_material_rows_make_one_case(self):
        df = pd.concat([rows(), rows()], ignore_index=True)
        plans, _ = plan_messages(df, hr(), run_id="published-1", cc_levels=())
        self.assertEqual(len(plans[0].cases), 1)

    def test_send_cannot_repeat_for_same_run(self):
        with tempfile.TemporaryDirectory() as directory:
            old = os.environ.get("GSI_DWH_PATH")
            os.environ["GSI_DWH_PATH"] = str(Path(directory) / "w.sqlite")
            try:
                Warehouse()
                plans, _ = plan_messages(rows(), hr(), run_id="published-1", cc_levels=())
                with patch("gsi.integrations.role_mail.outlook_message", return_value={"sent": True}) as send:
                    dispatch(plans, send=True)
                    with self.assertRaises(sqlite3.IntegrityError):
                        dispatch(plans, send=True)
                    self.assertEqual(send.call_count, 1)
            finally:
                if old is None:
                    os.environ.pop("GSI_DWH_PATH", None)
                else:
                    os.environ["GSI_DWH_PATH"] = old


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RoleMailTests))
    print(f"نتیجه: {result.testsRun - len(result.failures) - len(result.errors)} موفق | "
          f"{len(result.failures) + len(result.errors)} ناموفق")
    raise SystemExit(0 if result.wasSuccessful() else 1)
