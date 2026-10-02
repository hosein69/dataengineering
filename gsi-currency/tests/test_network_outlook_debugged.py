"""Failure-injection regression tests; no live SMB or Outlook connection."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os, time, tempfile, unittest
from unittest.mock import patch
import pandas as pd
from gsi.personalization.store import (EncryptedUserStore, _FileLock, ProfileStoreError,
    ProfileConfigurationError, ProfileIntegrityError, _decode_master_key, _read_key_text,
    generate_master_key, derive_user_key)
from gsi.personalization.publisher import frame_payload, publish_employee_snapshots
from gsi.personalization.service import PersonalWorkspace

class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'share'
        self.key = _decode_master_key(generate_master_key())
        self.store = EncryptedUserStore(self.root, self.key, '1001')
    def tearDown(self): self.tmp.cleanup()
    def test_old_lock_is_not_stolen(self):
        p = self.root/'old.lock'; p.write_text('active')
        os.utime(p, (time.time()-10000,)*2)
        with self.assertRaises(ProfileStoreError):
            with _FileLock(p, timeout=.01): pass
        self.assertEqual(p.read_text(), 'active')
    def test_lock_owner_change_is_preserved(self):
        p=self.root/'lock'
        with _FileLock(p): p.write_text('another-owner')
        self.assertTrue(p.exists())
    def test_failed_replace_preserves_previous(self):
        self.store.set('p','value','before')
        with patch('gsi.personalization.store.os.replace', side_effect=PermissionError):
            with self.assertRaises(PermissionError): self.store.set('p','value','after')
        self.assertEqual(self.store.get('p','value'),'before')
        self.assertEqual(list(self.store.paths.state_dir.glob('*.tmp')),[])
    def test_transient_sharing_violation_retries(self):
        real=os.replace; calls=[]
        def replace(a,b):
            calls.append(1)
            if len(calls)==1: raise PermissionError()
            real(a,b)
        with patch('gsi.personalization.store.os.replace', side_effect=replace): self.store.set('p','x',1)
        self.assertEqual(self.store.get('p','x'),1)
    def test_client_cannot_publish(self):
        c=EncryptedUserStore(self.root,derive_user_key(self.key,'1001'),'1001',key_is_user=True)
        with self.assertRaises(ProfileStoreError): c.replace_snapshot({'records':[]})
        with self.assertRaises(ProfileStoreError): c.set('current','records',[],kind='snapshot')
    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError): self.store.set('p','x',1,kind='typo')
    def test_future_schema_rejected(self):
        con=self.store._new_db(self.store.employee_code,'profile')
        con.execute("UPDATE meta SET value='999' WHERE key='schema_version'"); con.commit()
        self.store.paths.profile.write_bytes(self.store._encrypt(con.serialize(),'profile')); con.close()
        with self.assertRaises(ProfileIntegrityError): self.store.get('p','x')
    def test_network_disappearance_is_not_empty(self):
        import shutil
        shutil.rmtree(self.root)
        with self.assertRaises(ProfileStoreError): self.store.current_snapshot()
    def test_utf16_key_file(self):
        p=Path(self.tmp.name)/'key'; key=generate_master_key(); p.write_text(key,encoding='utf-16')
        self.assertEqual(_decode_master_key(_read_key_text(p)),_decode_master_key(key))
    def test_base64_junk_rejected(self):
        with self.assertRaises(ProfileConfigurationError): _decode_master_key('!'+generate_master_key())
    def test_nonfinite_json_cleaned(self):
        d=frame_payload(pd.DataFrame([{'KEY_EMP':'1001','مانده تعهد':float('inf')}]))
        self.assertIsNone(d['records'][0]['مانده تعهد'])
    def test_unknown_columns_never_leak(self):
        d=frame_payload(pd.DataFrame([{'secret':'hidden'}]))
        self.assertNotIn('secret',str(d))
    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError): frame_payload(pd.DataFrame(),max_rows=-1)
    def test_action_fields_preserved(self):
        d=frame_payload(pd.DataFrame([{'KEY_EMP':'1001','NEXT_ACTION_TITLE':'Call supplier'}]))
        self.assertEqual(d['records'][0]['NEXT_ACTION_TITLE'],'Call supplier')
    def test_explicit_empty_scope_clears_previous(self):
        self.store.replace_snapshot({'records':[{'KEY_REG':'old'}]})
        with patch.object(EncryptedUserStore,'from_master_env',return_value=self.store):
            publish_employee_snapshots(pd.DataFrame(columns=['KEY_EMP','KEY_REG']),employee_codes=['1001'])
        self.assertEqual(self.store.current_snapshot()['records'],[])
    def test_bad_preferences_rejected(self):
        ws=PersonalWorkspace('1001',self.store)
        with self.assertRaises(ValueError): ws.save_preferences({'audience':'unknown'})
        self.store.set('preferences','audience','unknown')
        self.assertEqual(ws.preferences()['audience'],'expert')
    def test_preferences_do_not_share_mutable_defaults(self):
        ws=PersonalWorkspace('1001',self.store); p=ws.preferences(); p['email_widgets'].clear()
        self.assertTrue(ws.preferences()['email_widgets'])
    def test_snapshot_context_consistent(self):
        self.store.replace_snapshot({'value':1},source_run_id='run1')
        data,meta=self.store.snapshot_context()
        self.assertEqual((data['value'],meta['source_run_id']),(1,'run1'))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NetworkTests))
    failures=len(result.errors)+len(result.failures)
    print(f'نتیجه: {result.testsRun-failures} موفق | {failures} ناموفق')
    sys.exit(bool(failures))
