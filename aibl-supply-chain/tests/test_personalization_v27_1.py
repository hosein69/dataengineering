# -*- coding: utf-8 -*-
import base64
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gsi.personalization.identity import resolve_employee_code, IdentityError
from gsi.personalization.store import (
    EncryptedUserStore, ProfileConfigurationError, ProfileIntegrityError,
    generate_master_key,
)
from gsi.personalization.service import PersonalWorkspace


def key_bytes():
    return base64.urlsafe_b64decode(generate_master_key())


class PersonalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "shared"
        self.key = key_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, emp="123456"):
        return EncryptedUserStore(self.root, self.key, emp)

    def test_employee_folder_is_canonical_eight_digits(self):
        s = self.store("201069-A")
        self.assertEqual(s.employee_code, "00201069")
        self.assertEqual(s.paths.folder.name, "00201069")

    def test_profile_persists_between_store_instances(self):
        s = self.store()
        s.set("preferences", "calendar", "jalali")
        s.set("preferences", "compact_mode", True)
        s2 = self.store()
        self.assertEqual(s2.get("preferences", "calendar"), "jalali")
        self.assertTrue(s2.get("preferences", "compact_mode"))

    def test_encrypted_file_does_not_expose_plaintext(self):
        s = self.store()
        secret = "VERY-SENSITIVE-PREFERENCE-XYZ"
        s.set("preferences", "note", secret)
        blob = s.paths.profile.read_bytes()
        self.assertNotIn(secret.encode("utf-8"), blob)
        self.assertNotIn(b"SQLite format 3", blob)

    def test_snapshot_is_separate_from_profile(self):
        s = self.store()
        s.set("preferences", "audience", "expert")
        s.replace_snapshot({"case_count": 12, "queue": ["R1", "R2"]}, source_run_id="run-1")
        self.assertEqual(s.get("preferences", "audience"), "expert")
        self.assertEqual(s.current_snapshot()["case_count"], 12)
        self.assertTrue(s.paths.profile.exists())
        self.assertTrue(s.paths.snapshot.exists())
        self.assertNotEqual(s.paths.profile.read_bytes(), s.paths.snapshot.read_bytes())

    def test_snapshot_replace_drops_stale_keys(self):
        s = self.store()
        s.replace_snapshot({"old": 1, "keep": 2})
        s.replace_snapshot({"keep": 3})
        self.assertEqual(s.current_snapshot(), {"keep": 3})

    def test_wrong_key_fails_closed(self):
        s = self.store()
        s.set("preferences", "calendar", "jalali")
        wrong = EncryptedUserStore(self.root, key_bytes(), s.employee_code)
        with self.assertRaises(ProfileIntegrityError):
            wrong.get("preferences", "calendar")

    def test_tamper_is_detected(self):
        s = self.store()
        s.set("preferences", "calendar", "jalali")
        data = bytearray(s.paths.profile.read_bytes())
        data[-1] ^= 0x01
        s.paths.profile.write_bytes(bytes(data))
        with self.assertRaises(ProfileIntegrityError):
            s.get("preferences", "calendar")

    def test_user_isolation_uses_distinct_crypto_context(self):
        a = EncryptedUserStore(self.root, self.key, "1001")
        b = EncryptedUserStore(self.root, self.key, "1002")
        a.set("preferences", "x", "A")
        b.set("preferences", "x", "B")
        self.assertEqual(a.get("preferences", "x"), "A")
        self.assertEqual(b.get("preferences", "x"), "B")
        self.assertNotEqual(a.paths.folder, b.paths.folder)

    def test_integrity_check(self):
        s = self.store()
        s.set("preferences", "x", 1)
        self.assertEqual(s.integrity_check(), "ok")

    def test_audit_does_not_store_value(self):
        s = self.store()
        s.set("preferences", "token_like", "DO-NOT-AUDIT-VALUE", audit_event="changed")
        audit = s.audit()
        self.assertEqual(audit[0]["event"], "changed")
        self.assertNotIn("DO-NOT-AUDIT-VALUE", str(audit))

    def test_per_user_key_can_open_only_its_user_store(self):
        from gsi.personalization.store import derive_user_key
        master = self.key
        central_a = EncryptedUserStore(self.root, master, "1001")
        central_a.set("preferences", "x", "A")
        user_a_key = derive_user_key(master, "1001")
        client_a = EncryptedUserStore(self.root, user_a_key, "1001", key_is_user=True)
        self.assertEqual(client_a.get("preferences", "x"), "A")
        user_b_key = derive_user_key(master, "1002")
        wrong_for_a = EncryptedUserStore(self.root, user_b_key, "1001", key_is_user=True)
        with self.assertRaises(ProfileIntegrityError):
            wrong_for_a.get("preferences", "x")

    def test_from_env_prefers_user_key_without_master(self):
        from gsi.personalization.store import derive_user_key, generate_master_key
        master = self.key
        central = EncryptedUserStore(self.root, master, "1001")
        central.set("preferences", "calendar", "jalali")
        user_key_text = base64.urlsafe_b64encode(derive_user_key(master, "1001")).decode("ascii")
        names = ["GSI_PROFILE_ROOT","GSI_PROFILE_MASTER_KEY","GSI_PROFILE_KEY_FILE","GSI_PROFILE_USER_KEY","GSI_PROFILE_USER_KEY_FILE"]
        old = {n: os.environ.get(n) for n in names}
        try:
            os.environ["GSI_PROFILE_ROOT"] = str(self.root)
            os.environ.pop("GSI_PROFILE_MASTER_KEY", None); os.environ.pop("GSI_PROFILE_KEY_FILE", None)
            os.environ["GSI_PROFILE_USER_KEY"] = user_key_text
            client = EncryptedUserStore.from_env("1001")
            self.assertEqual(client.get("preferences", "calendar"), "jalali")
        finally:
            for n,v in old.items():
                if v is None: os.environ.pop(n, None)
                else: os.environ[n] = v

    def test_master_key_file_must_not_be_inside_profile_root(self):
        self.root.mkdir(parents=True, exist_ok=True)
        kf = self.root / "key.txt"
        kf.write_text(generate_master_key(), encoding="utf-8")
        old_root, old_key, old_kf = os.environ.get("GSI_PROFILE_ROOT"), os.environ.get("GSI_PROFILE_MASTER_KEY"), os.environ.get("GSI_PROFILE_KEY_FILE")
        try:
            os.environ["GSI_PROFILE_ROOT"] = str(self.root)
            os.environ.pop("GSI_PROFILE_MASTER_KEY", None)
            os.environ["GSI_PROFILE_KEY_FILE"] = str(kf)
            with self.assertRaises(ProfileConfigurationError):
                EncryptedUserStore.from_env("123456")
        finally:
            for name, val in [("GSI_PROFILE_ROOT", old_root), ("GSI_PROFILE_MASTER_KEY", old_key), ("GSI_PROFILE_KEY_FILE", old_kf)]:
                if val is None: os.environ.pop(name, None)
                else: os.environ[name] = val

    def test_identity_resolution_never_uses_ip(self):
        old = os.environ.get("GSI_EMP_CODE")
        try:
            os.environ["GSI_EMP_CODE"] = "201069-A"
            self.assertEqual(resolve_employee_code(), "00201069")
        finally:
            if old is None: os.environ.pop("GSI_EMP_CODE", None)
            else: os.environ["GSI_EMP_CODE"] = old

    def test_identity_fails_closed_when_missing(self):
        old_emp, old_file = os.environ.get("GSI_EMP_CODE"), os.environ.get("GSI_IDENTITY_FILE")
        try:
            os.environ.pop("GSI_EMP_CODE", None); os.environ.pop("GSI_IDENTITY_FILE", None)
            with self.assertRaises(IdentityError):
                resolve_employee_code()
        finally:
            if old_emp is not None: os.environ["GSI_EMP_CODE"] = old_emp
            if old_file is not None: os.environ["GSI_IDENTITY_FILE"] = old_file

    def test_workspace_defaults_and_saved_preferences(self):
        s = self.store()
        ws = PersonalWorkspace(s.employee_code, s)
        self.assertEqual(ws.preferences()["audience"], "expert")
        ws.save_preferences({"audience": "manager", "compact_mode": True, "not_allowed": "x"})
        p = ws.preferences()
        self.assertEqual(p["audience"], "manager")
        self.assertTrue(p["compact_mode"])
        self.assertNotIn("not_allowed", p)

    def test_local_config_restores_root_identity_and_user_key_without_env(self):
        from gsi.personalization.store import derive_user_key
        master = self.key
        central = EncryptedUserStore(self.root, master, "1001")
        central.set("preferences", "calendar", "jalali")
        home = Path(self.tmp.name) / "local_home"
        gsi_home = home / ".gsi"
        gsi_home.mkdir(parents=True, exist_ok=True)
        (gsi_home / "personal_config.json").write_text(
            '{"profile_root": ' + repr(str(self.root)).replace("'", '"') + ', "employee_code": "00001001"}',
            encoding="utf-8"
        )
        (gsi_home / "identity.json").write_text('{"employee_code":"1001"}', encoding="utf-8")
        user_key = derive_user_key(master, "1001")
        (gsi_home / "profile.key").write_text(base64.urlsafe_b64encode(user_key).decode("ascii"), encoding="utf-8")
        names = ["GSI_PROFILE_ROOT","GSI_PROFILE_MASTER_KEY","GSI_PROFILE_KEY_FILE","GSI_PROFILE_USER_KEY","GSI_PROFILE_USER_KEY_FILE","GSI_EMP_CODE","GSI_IDENTITY_FILE","GSI_HOME"]
        old = {n: os.environ.get(n) for n in names}
        try:
            for n in names[:-1]: os.environ.pop(n, None)
            os.environ["GSI_HOME"] = str(gsi_home)
            self.assertEqual(resolve_employee_code(), "00001001")
            client = EncryptedUserStore.from_env("1001")
            self.assertEqual(client.get("preferences", "calendar"), "jalali")
        finally:
            for n,v in old.items():
                if v is None: os.environ.pop(n, None)
                else: os.environ[n] = v

    def test_central_publish_fails_closed_without_master_even_if_user_key_exists(self):
        from gsi.personalization.store import derive_user_key
        names = ["GSI_PROFILE_ROOT","GSI_PROFILE_MASTER_KEY","GSI_PROFILE_KEY_FILE","GSI_PROFILE_USER_KEY","GSI_PROFILE_USER_KEY_FILE"]
        old = {n: os.environ.get(n) for n in names}
        try:
            os.environ["GSI_PROFILE_ROOT"] = str(self.root)
            os.environ.pop("GSI_PROFILE_MASTER_KEY", None)
            os.environ.pop("GSI_PROFILE_KEY_FILE", None)
            os.environ["GSI_PROFILE_USER_KEY"] = base64.urlsafe_b64encode(derive_user_key(self.key, "1001")).decode("ascii")
            with self.assertRaises(ProfileConfigurationError):
                EncryptedUserStore.from_master_env("1001")
        finally:
            for n,v in old.items():
                if v is None: os.environ.pop(n, None)
                else: os.environ[n] = v

    def test_windows_installer_uses_local_launcher_and_recommends_key_file(self):
        src = (ROOT / "tools" / "windows" / "install_gsi_personal_protocol.py").read_text(encoding="utf-8")
        self.assertIn("gsi_personal_launcher.py", src)
        self.assertIn("--user-key-file", src)
        self.assertIn('"%1"', src)
        self.assertNotIn("http://", src.lower())
        self.assertNotIn("https://", src.lower())


class PersonalPublisherTests(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        self.pd = pd
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "shared"
        self.key_text = generate_master_key()
        self.old = {k: os.environ.get(k) for k in ["GSI_PROFILE_ROOT", "GSI_PROFILE_MASTER_KEY", "GSI_EMP_CODE"]}
        os.environ["GSI_PROFILE_ROOT"] = str(self.root)
        os.environ["GSI_PROFILE_MASTER_KEY"] = self.key_text

    def tearDown(self):
        for k,v in self.old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self.tmp.cleanup()

    def test_publish_scopes_each_user(self):
        from gsi.personalization.publisher import publish_employee_snapshots, load_personal_frame
        df = self.pd.DataFrame([
            {"KEY_EMP":"1001","KEY_REG":"R-A","مرحله جاری":"تخصیص"},
            {"KEY_EMP":"1002","KEY_REG":"R-B","مرحله جاری":"حمل"},
            {"KEY_EMP":"1001","KEY_REG":"R-C","مرحله جاری":"ترخیص"},
        ])
        out = publish_employee_snapshots(df, source_run_id="t1")
        self.assertEqual(out["users"], 2)
        a = load_personal_frame("1001")
        b = load_personal_frame("1002")
        self.assertEqual(set(a["KEY_REG"]), {"R-A","R-C"})
        self.assertEqual(set(b["KEY_REG"]), {"R-B"})
        self.assertNotIn("R-B", set(a["KEY_REG"]))

    def test_personal_html_has_local_live_protocol_not_http_api(self):
        from gsi.personalization.publisher import publish_employee_snapshots
        from gsi.personalization.personal_html import build_personal_html
        df = self.pd.DataFrame([{"KEY_EMP":"1001","KEY_REG":"R-A"}])
        publish_employee_snapshots(df)
        html = build_personal_html("1001")
        self.assertIn('href="gsi://personal"', html)
        self.assertNotIn('fetch("http', html.lower())
        self.assertNotIn('axios', html.lower())

    def test_launcher_renders_from_shared_store_to_local_cache(self):
        from gsi.personalization.publisher import publish_employee_snapshots
        from gsi.personalization.launcher import render_live
        df = self.pd.DataFrame([{"KEY_EMP":"1001","KEY_REG":"R-LIVE"}])
        publish_employee_snapshots(df)
        old_emp = os.environ.get("GSI_EMP_CODE")
        try:
            os.environ["GSI_EMP_CODE"] = "1001"
            out = Path(self.tmp.name) / "local" / "live.html"
            path = render_live(output=out)
            self.assertTrue(path.is_file())
            self.assertIn("R-LIVE", path.read_text(encoding="utf-8"))
            self.assertFalse(str(path).startswith(str(self.root)))
        finally:
            if old_emp is None: os.environ.pop("GSI_EMP_CODE", None)
            else: os.environ["GSI_EMP_CODE"] = old_emp

    def test_personal_html_reads_shared_store_and_keeps_preferences(self):
        from gsi.personalization.publisher import publish_employee_snapshots
        from gsi.personalization.service import PersonalWorkspace
        from gsi.personalization.personal_html import build_personal_html
        df = self.pd.DataFrame([{"KEY_EMP":"1001","KEY_REG":"R-A","مرحله جاری":"تخصیص","مانع فعلی":"پیگیری"}])
        publish_employee_snapshots(df)
        ws = PersonalWorkspace.from_env("1001")
        ws.save_preferences({"calendar":"gregorian", "compact_mode":True})
        html = build_personal_html("1001")
        self.assertIn("R-A", html)
        self.assertIn("gregorian", html)
        self.assertIn("Shared Folder", html)

    def test_shared_files_are_only_encrypted_store_files(self):
        from gsi.personalization.publisher import publish_employee_snapshots
        df = self.pd.DataFrame([{"KEY_EMP":"1001","KEY_REG":"R-A"}])
        publish_employee_snapshots(df)
        user = self.root / "00001001"
        self.assertEqual(sorted(p.name for p in user.iterdir()), ["snapshot", "state"])
        self.assertEqual(sorted(p.name for p in (user / "snapshot").iterdir()), ["current.gsi"])
        self.assertEqual(list((user / "state").iterdir()), [])
        self.assertNotIn(b"R-A", (user / "snapshot" / "current.gsi").read_bytes())


class V27_1_RegressionTests(unittest.TestCase):
    """رگرسیون باگ‌هایی که در ممیزی مویرگی V27.1 پیدا و رفع شدند."""

    def setUp(self):
        import pandas as pd
        self.pd = pd
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "shared"
        self.keep = {k: os.environ.get(k) for k in
                     ["GSI_PROFILE_ROOT", "GSI_PROFILE_MASTER_KEY", "GSI_PROFILE_KEY_FILE",
                      "GSI_PROFILE_USER_KEY", "GSI_PROFILE_USER_KEY_FILE", "GSI_EMP_CODE"]}
        for k in self.keep:
            os.environ.pop(k, None)
        os.environ["GSI_PROFILE_ROOT"] = str(self.root)
        os.environ["GSI_PROFILE_MASTER_KEY"] = generate_master_key()
        os.environ["GSI_EMP_CODE"] = "1001"

    def tearDown(self):
        for k, v in self.keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_numpy_bool_stays_boolean(self):
        """np.bool_ نباید به رشته «True»/«False» تبدیل شود؛ «False» رشته‌ای truthy است."""
        import numpy as np
        from gsi.personalization.publisher import _jsonable
        self.assertIs(_jsonable(np.bool_(True)), True)
        self.assertIs(_jsonable(np.bool_(False)), False)
        self.assertIs(_jsonable(True), True)

    def _publish(self, rows=300):
        from gsi.personalization.publisher import publish_employee_snapshots
        df = self.pd.DataFrame([
            {"KEY_EMP": "1001", "KEY_REG": f"R{i}", "مانع فعلی": "منتظر تأیید",
             "مرحله جاری": "تأیید فنی"} for i in range(rows)
        ])
        publish_employee_snapshots(df)

    def test_audience_caps_reach_the_personal_html(self):
        """تغییر مخاطب باید واقعاً تعداد سطر و یافته را عوض کند، نه فقط ذخیره شود."""
        from gsi.personalization.service import PersonalWorkspace
        from gsi.personalization.personal_html import build_personal_html
        from gsi import audience as AUD
        self._publish(300)
        ws = PersonalWorkspace.from_env("1001")
        seen = {}
        for key in ("expert", "manager", "executive", "analyst"):
            ws.save_preferences({"audience": key})
            prefs = ws.preferences()
            profile = AUD.get(key)
            self.assertEqual(prefs["table_rows"], profile.table_rows)
            self.assertEqual(prefs["max_findings"], profile.max_findings)
            html = build_personal_html("1001")
            cases = html.split("پرونده‌های من")[1].count("<tr>") - 1
            self.assertEqual(cases, min(profile.table_rows, 300))
            seen[key] = html
        self.assertNotEqual(seen["executive"], seen["analyst"],
                            "خروجی مدیر ارشد و تحلیل‌گر نباید یکسان باشد")

    def test_namespace_and_get_share_one_error_contract(self):
        """هر دو باید ProfileIntegrityError بدهند، نه یکی JSONDecodeError خام."""
        store = EncryptedUserStore.from_master_env("1001")
        store.set("preferences", "ok", 1)
        with store._db("profile", write=True) as con:
            con.execute("INSERT OR REPLACE INTO kv VALUES('preferences','bad','{not json','t')")
        with self.assertRaises(ProfileIntegrityError):
            store.get("preferences", "bad")
        with self.assertRaises(ProfileIntegrityError):
            store.namespace("preferences")

    def test_broken_user_key_is_not_reported_as_master_key(self):
        """پیام خطا باید همان فایلی را نام ببرد که خراب است."""
        bad = Path(self.tmp.name) / "bad.key"
        bad.write_text("not-base64!!", encoding="utf-8")
        os.environ["GSI_PROFILE_USER_KEY_FILE"] = str(bad)
        with self.assertRaises(ProfileConfigurationError) as ctx:
            EncryptedUserStore.from_env("1001")
        self.assertIn("User Key", str(ctx.exception))
        self.assertNotIn("GSI_PROFILE_MASTER_KEY", str(ctx.exception))

    def test_vanished_share_gives_an_actionable_error(self):
        """قطع شدن درایو شبکه نباید FileNotFoundError خام روی فایل .lock بدهد."""
        import shutil
        from gsi.personalization.store import ProfileStoreError
        store = EncryptedUserStore.from_master_env("1001")
        store.set("preferences", "a", 1)
        shutil.rmtree(self.root / "00001001")
        try:
            store.set("preferences", "b", 2)
        except ProfileStoreError as ex:
            self.assertIn("پوشه مشترک", str(ex))
        except FileNotFoundError:
            self.fail("خطای خام FileNotFoundError به کاربر رسید")

    def test_atomic_write_retries_before_giving_up(self):
        """روی ویندوز/SMB، os.replace وقتی خواننده‌ای فایل را باز دارد خطا می‌دهد."""
        import inspect
        from gsi.personalization import store as PS
        src = inspect.getsource(PS.EncryptedUserStore._atomic_write)
        self.assertIn("PermissionError", src)
        self.assertGreaterEqual(PS._REPLACE_ATTEMPTS, 3)

    def test_doctor_checks_the_shared_store(self):
        """تنها ابزار تشخیص این استقرار باید پوشه مشترک را هم بررسی کند."""
        from gsi import doctor
        self.assertTrue(hasattr(doctor, "check_personal_store"))
        import inspect
        self.assertIn("check_personal_store()", inspect.getsource(doctor.main))

    def test_handoff_points_at_the_real_figma_file(self):
        from gsi.design import handoff
        self.assertIn("0splRPuGQgIo33XFkwa0rz", handoff.FIGMA_FILE)
        self.assertNotIn("v3FIHcKem4vqZoZwcDWdZ2", handoff.FIGMA_FILE)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = result.testsRun - len(result.failures) - len(result.errors)
    fail = len(result.failures) + len(result.errors)
    print(f"نتیجه: {ok} موفق | {fail} ناموفق")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
