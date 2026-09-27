import copy, io, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from gsi.control_center.core import *
from gsi.personalization.store import EncryptedUserStore, generate_master_key

class CenterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  # The warehouse defaults to a machine-level file. Without pinning it here the
  # suite reads a completed run left by an earlier suite, so render_report never
  # reaches the personal-snapshot branch these tests exercise.
  self._env=patch.dict(os.environ,{'GSI_DWH_PATH':str(self.root/'warehouse.sqlite')});self._env.start()
  self.store=CenterStore(self.root/'center');self.cfg=defaults()
  self.source={'id':'contacts','kind':'contacts','sheet':0,'mapping':{'employee_code':'code','name':'name','email':'email'}}
  self.blob=b'code,name,email\n00000123,A,a@example.invalid\n'
 def tearDown(self):self._env.stop();self.tmp.cleanup()
 def populated(self):
  c,_=preview_import(self.cfg,self.source,self.blob,'people.csv');c['memberships']=[dict(employee_code='00000123',cluster_id='purchase_1',level='manager',active=True)];return c
 def test_defaults_revision_conflict(self):
  self.assertEqual(len(validate(self.cfg)['clusters']),7);self.store.save(self.cfg,0)
  with self.assertRaises(ValueError):self.store.save(self.cfg,0)
  self.assertEqual(self.store.load()['revision'],1)
 def test_unknown_columns_not_in_config(self):
  blob=b'code,name,email,extra\n00000123,A,a@example.invalid,secret\n';c,s=preview_import(self.cfg,self.source,blob,'x.csv')
  self.assertEqual(c['people'][0]['employee_code'],'00000123');self.assertNotIn('extra',c['people'][0]);self.assertEqual(s['added'],1)
 def test_drift_preserves_config(self):
  c=self.store.save(self.cfg,0);before=json.dumps(self.store.load(),sort_keys=True)
  with self.assertRaises(ValueError):commit_import(self.store,c,self.source,b'wrong,name,email\n123,A,a@example.invalid','x.csv')
  self.assertEqual(before,json.dumps(self.store.load(),sort_keys=True))
 def test_duplicate_identity(self):
  with self.assertRaises(ValueError):preview_import(self.cfg,self.source,self.blob+b'123,B,b@example.invalid\n','x.csv')
 def test_duplicate_header(self):
  with self.assertRaises(ValueError):read_source(b'code,code\n1,2','x.csv')
 def test_partial_invalid_file(self):
  with self.assertRaises(ValueError):preview_import(self.cfg,self.source,self.blob+b'124,B,invalid\n','x.csv')
  self.assertEqual(self.cfg['people'],[])
 def test_raw_archive_and_idempotency(self):
  c,s=commit_import(self.store,self.cfg,self.source,self.blob,'x.csv');c2,s2=commit_import(self.store,c,self.source,self.blob,'x.csv')
  self.assertEqual(len(c2['people']),1);self.assertEqual(s2['added'],0)
  from gsi.warehouse.store import Warehouse
  with Warehouse().db() as db: archived=db.execute('SELECT content FROM wh_file WHERE id=?',(s2['sha256'],)).fetchone()[0]
  self.assertEqual(archived,self.blob)
 def test_missing_rows_preserved(self):
  c=self.populated();c['people'].append(dict(employee_code='00000124',name='B',email='b@example.invalid',active=True))
  updated,_=preview_import(c,self.source,self.blob,'x.csv');self.assertEqual(len(updated['people']),2)
 def test_xlsx_codes(self):
  b=io.BytesIO();pd.DataFrame([{'code':'00000123','name':'A','email':'a@example.invalid'}]).to_excel(b,index=False)
  c,_=preview_import(self.cfg,self.source,b.getvalue(),'x.xlsx');self.assertEqual(c['people'][0]['employee_code'],'00000123')
 def test_cluster_import_keeps_template(self):
  self.cfg['clusters'][0]['header']='خاص';spec={'kind':'clusters','mapping':{'cluster_id':'id','name':'title'}}
  c,_=preview_import(self.cfg,spec,b'id,title\npurchase_1,Changed\nnew_one,New','x.csv')
  self.assertEqual(c['clusters'][0]['header'],'خاص');self.assertEqual(len(c['clusters']),8)
 def test_membership_integrity(self):
  c=self.populated();c['memberships'][0]['cluster_id']='unknown'
  with self.assertRaises(ValueError):validate(c)
 def test_inactive_member(self):
  c=self.populated();c['memberships'][0]['active']=False
  with self.assertRaises(ValueError):report_context(c,'00000123','purchase_1','daily')
 def test_template_rejects_attribute_access(self):
  c=self.populated();c['clusters'][0]['body']='{name.__class__}'
  with self.assertRaises(ValueError):validate(c)
 def test_personal_store_unchanged_on_export(self):
  with patch.dict(os.environ,{'GSI_PROFILE_ROOT':str(self.root/'share'),'GSI_PROFILE_MASTER_KEY':generate_master_key()}):
   store=EncryptedUserStore.from_master_env('00000123');store.set('preferences','calendar','jalali')
   store.replace_snapshot({'records':[{'KEY_REG':'REG-1','NEXT_ACTION_TITLE':'<script>x</script>','FX_EVIDENCE_COVERAGE':99}], 'ref_date':'2026-09-19','row_count':1})
   a=store.paths.profile.read_bytes();b=store.paths.snapshot.read_bytes();bundle=render_report(self.populated(),'00000123','purchase_1')
   self.assertIn('&lt;script&gt;',bundle['html']);self.assertNotIn('<script>',bundle['html']);self.assertNotIn('FX_EVIDENCE_COVERAGE',bundle['html'])
   path=save_report(bundle);self.assertTrue(path.exists());self.assertIn('00000123',str(path))
   self.assertEqual(a,store.paths.profile.read_bytes());self.assertEqual(b,store.paths.snapshot.read_bytes())
 def test_snapshot_required(self):
  (self.root/'share').mkdir()
  with patch.dict(os.environ,{'GSI_PROFILE_ROOT':str(self.root/'share'),'GSI_PROFILE_MASTER_KEY':generate_master_key()}):
   with self.assertRaises(ValueError):render_report(self.populated(),'00000123','purchase_1')
 def test_draft_never_sends(self):
  from contextlib import contextmanager
  win=MagicMock();mail=win.Dispatch.return_value.CreateItem.return_value
  @contextmanager
  def session():yield win
  with patch('gsi.integrations.daily_email._outlook_session',session),patch.dict(os.environ,{'GSI_EMAIL_SENDER':''}):
   result=outlook_draft(dict(subject='S',email='a@example.invalid',html='<p>Hi</p>'))
  mail.Save.assert_called_once();mail.Display.assert_called_once();mail.Send.assert_not_called();self.assertFalse(result['sent'])
 def test_restore_revision(self):
  first=self.store.save(self.cfg,0);second=copy.deepcopy(first);second['clusters'][0]['name']='Changed';self.store.save(second,1)
  restored=self.store.save(first,2);self.assertEqual(restored['revision'],3);self.assertEqual(restored['clusters'][0]['name'],self.cfg['clusters'][0]['name'])

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CenterTests))
 print(f'نتیجه: {result.testsRun-len(result.failures)-len(result.errors)} موفق | {len(result.failures)+len(result.errors)} شکست');sys.exit(not result.wasSuccessful())
