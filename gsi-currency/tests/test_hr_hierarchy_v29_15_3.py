# -*- coding: utf-8 -*-
"""HR hierarchy must never widen access through fuzzy or inactive matches."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pandas as pd

from gsi.personalization.hr_scope import build_scopes, restrict_rows
from gsi.personalization.publisher import publish_employee_snapshots
from gsi.personalization.service import PersonalWorkspace


def roster():
    return pd.DataFrame([
        ("101", "مریم کارشناس", "کارشناس", "لیلا رئیس", "علی مدیر", "معاونت خرید", "فعال"),
        ("102", "لیلا رئیس", "رئیس اداره", "", "علی مدیر", "معاونت خرید", "فعال"),
        ("103", "علی مدیر", "مدیر خرید", "", "", "معاونت خرید", "فعال"),
        ("104", "زهرا معاون", "معاون خرید", "", "", "معاونت خرید", "فعال"),
        ("105", "فرد غیرفعال", "کارشناس", "لیلا رئیس", "علی مدیر", "معاونت خرید", "غیرفعال"),
        ("106", "کارشناس دیگر", "کارشناس", "لیلا رئیس", "علی مدیر", "معاونت فروش", "فعال"),
    ], columns=["KEY_EMP", "HR_FULL_NAME", "HR_POST", "HR_HEAD", "HR_MANAGER", "HR_VICE", "HR_STATUS"])


class HrHierarchyTests(unittest.TestCase):
    def test_four_levels_and_inactive_exclusion(self):
        s = build_scopes(roster())
        self.assertEqual(s["00000101"].level, "expert")
        self.assertEqual(s["00000102"].level, "head")
        self.assertEqual(s["00000103"].level, "manager")
        self.assertEqual(s["00000104"].level, "vice")
        self.assertEqual(s["00000102"].member_codes, frozenset({"00000101", "00000102", "00000106"}))
        self.assertEqual(s["00000103"].member_codes, frozenset({"00000101", "00000102", "00000103", "00000106"}))
        self.assertEqual(s["00000104"].member_codes, frozenset({"00000101", "00000102", "00000103", "00000104"}))
        self.assertNotIn("00000105", s)

    def test_ambiguous_name_does_not_grant_team(self):
        hr = roster()
        hr.loc[len(hr)] = ("107", "لیلا رئیس", "رئیس اداره", "", "", "معاونت دیگر", "فعال")
        s = build_scopes(hr)
        self.assertEqual(s["00000102"].member_codes, frozenset({"00000102"}))
        self.assertEqual(s["00000107"].member_codes, frozenset({"00000107"}))

    def test_two_vices_in_one_unit_do_not_both_receive_every_case(self):
        hr = roster()
        hr.loc[len(hr)] = ("108", "معاون دوم", "معاون خرید", "", "", "معاونت خرید", "فعال")
        s = build_scopes(hr)
        self.assertEqual(s["00000104"].member_codes, frozenset({"00000104"}))
        self.assertEqual(s["00000108"].member_codes, frozenset({"00000108"}))

    def test_publication_uses_team_scope_and_rejects_inactive_identity(self):
        df = pd.DataFrame({"KEY_EMP": ["101", "102", "103", "104", "105", "106"],
                           "KEY_REG": [f"R{i}" for i in range(6)]})
        saved = {}
        class Store:
            @classmethod
            def from_master_env(cls, emp):
                class User:
                    def replace_snapshot(self, payload, **kwargs):
                        saved[emp] = payload
                return User()
        with patch("gsi.personalization.publisher.EncryptedUserStore", Store):
            out = publish_employee_snapshots(df, hr_frame=roster(), employee_codes=["102", "104"])
            self.assertEqual(out["published"]["00000102"], 3)
            self.assertEqual(out["published"]["00000104"], 4)
            self.assertEqual({r["KEY_REG"] for r in saved["00000104"]["records"]}, {"R0", "R1", "R2", "R3"})
            with self.assertRaises(ValueError):
                publish_employee_snapshots(df, hr_frame=roster(), employee_codes=["105"])

    def test_missing_hr_or_key_fails_closed(self):
        with self.assertRaises(ValueError):
            build_scopes(pd.DataFrame())
        with self.assertRaises(ValueError):
            restrict_rows(pd.DataFrame({"KEY_REG": ["R1"]}), build_scopes(roster())["00000102"])

    def test_user_cannot_select_a_higher_hr_audience(self):
        class Store:
            def __init__(self):
                self.saved = {"audience": "executive"}
            def namespace(self, name):
                return dict(self.saved)
            def current_snapshot(self):
                return {"hr_scope": {"level": "expert"}}
            def merge(self, name, values, **kwargs):
                self.saved.update(values)
        store = Store()
        ws = PersonalWorkspace("00000101", store)
        self.assertEqual(ws.preferences()["audience"], "expert")
        self.assertEqual(ws.save_preferences({"audience": "executive"})["audience"], "expert")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(HrHierarchyTests))
    print(f"نتیجه: {result.testsRun - len(result.failures) - len(result.errors)} موفق | "
          f"{len(result.failures) + len(result.errors)} ناموفق")
    raise SystemExit(0 if result.wasSuccessful() else 1)
