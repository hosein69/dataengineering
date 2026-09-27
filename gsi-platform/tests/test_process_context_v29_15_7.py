"""Long FX timelines must never acquire a global bottleneck verdict."""
import unittest

import pandas as pd

from gsi.report.transition_context import annotate_transitions
from gsi.stages.s80_eventlog import EventLogStage
from gsi.studio_core.runtime_data import bottleneck_view
from app.process_cockpit import _bottleneck_stage, _stage_html


class ProcessContextTests(unittest.TestCase):
    def test_settlement_vs_transport_and_cross_domain(self):
        rows = pd.DataFrame({
            "از فعالیت": ["رفع تعهد", "شاهد حرکت محموله", "ترخیص کامل"],
            "به فعالیت": ["رفع تعهد انجام‌شده", "ورود محموله", "رفع تعهد"],
            "میانه روز": [300, 12, 60], "تعداد پرونده": [5, 10, 3],
        })
        measured = annotate_transitions(rows)
        self.assertEqual(measured["حوزه فرایندی"].tolist(),
                         ["رفع تعهد", "حمل", "گذار میان‌حوزه‌ای"])
        self.assertEqual(measured["میانه روز"].tolist(), [300, 12, 60])
        self.assertTrue(measured["وضعیت گلوگاه"].eq("سنجش‌نشده").all())
        label, note = _bottleneck_stage({"bottlenecks": measured})
        self.assertEqual(label, "—")
        self.assertIn("توصیفی", note)
        self.assertNotIn("is-warning", _stage_html(pd.Series(dtype=int), {"bottlenecks": measured}))

    def test_actual_eventlog_transitions_have_no_global_rank(self):
        events = pd.DataFrame([
            {"_CASE_KEY": "A", "ACTIVITY_FA": "ایجاد تعهد ارزی", "EVENTTIME": pd.Timestamp("2026-01-01")},
            {"_CASE_KEY": "A", "ACTIVITY_FA": "تخصیص ارز", "EVENTTIME": pd.Timestamp("2026-04-01")},
            {"_CASE_KEY": "B", "ACTIVITY_FA": "شاهد حرکت محموله", "EVENTTIME": pd.Timestamp("2026-01-01")},
            {"_CASE_KEY": "B", "ACTIVITY_FA": "ورود محموله", "EVENTTIME": pd.Timestamp("2026-01-10")},
        ])
        out = EventLogStage._bottlenecks(events, pd.DataFrame())
        self.assertEqual(set(out["حوزه فرایندی"]), {"ارز و تعهد", "حمل"})
        self.assertTrue(out["وضعیت گلوگاه"].eq("سنجش‌نشده").all())
        shown, metric = bottleneck_view(out)
        self.assertEqual(metric, "میانه روز")
        self.assertEqual(set(shown["حوزه فرایندی"]), {"ارز و تعهد", "حمل"})


if __name__ == "__main__":
    unittest.main()
