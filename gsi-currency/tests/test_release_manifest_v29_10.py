# -*- coding: utf-8 -*-
"""مانیفست پکیج باید با فایل‌های واقعی بخواند.

چرا این تست وجود دارد: `gsi/MANIFEST.json` از نسخه ۲۹٫۸٫۲ مانده بود و در
۲۹٫۹٫۰ بازتولید نشد. نتیجه این بود که `python -m gsi.doctor` روی یک نصب
کاملاً سالم، هفده فایل را «قدیمی یا دست‌کاری‌شده» اعلام می‌کرد.

این بدتر از نداشتن مانیفست است: تمام ارزش این مکانیزم در این است که
بگوید «فقط همین یک فایل را جایگزین کن». وقتی هفده هشدار کاذب می‌دهد،
پشتیبان یاد می‌گیرد کل بخش را نادیده بگیرد، و آن یک فایلی که واقعاً قدیمی
مانده هم با بقیه نادیده گرفته می‌شود.

بازتولید مانیفست: ``python -m gsi.manifest``
"""
from __future__ import annotations

import json
import os
import unittest

from gsi import manifest
from gsi.version import PACKAGE_VERSION


class ManifestMatchesTheFilesItDescribes(unittest.TestCase):

    def test_manifest_exists(self):
        self.assertTrue(os.path.exists(manifest.MANIFEST_PATH),
                        "gsi/MANIFEST.json وجود ندارد — «python -m gsi.manifest»")

    def test_manifest_version_is_this_release(self):
        with open(manifest.MANIFEST_PATH, encoding="utf-8") as f:
            stored = json.load(f).get("package_version")
        self.assertEqual(
            stored, PACKAGE_VERSION,
            "مانیفست برای نسخه دیگری ساخته شده؛ با «python -m gsi.manifest» بازتولید کنید.")

    def test_no_file_reports_as_changed_missing_or_extra(self):
        issues = manifest.verify()
        self.assertEqual(
            [], [i.message for i in issues],
            "doctor روی همین درخت کاری هشدار می‌دهد؛ "
            "با «python -m gsi.manifest» بازتولید کنید.")

    def test_the_trust_layer_is_covered_by_the_manifest(self):
        """لایه‌ای که در این نسخه اضافه شد هم باید اثر انگشت داشته باشد."""
        tracked = set(manifest.scan())
        for expected in ("trust/__init__.py", "trust/verdict.py", "trust/impact.py",
                         "trust/profiling.py", "trust/fitness.py",
                         "stages/s95_trust.py"):
            self.assertIn(expected, tracked)


if __name__ == "__main__":
    unittest.main()
