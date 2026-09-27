"""No production writes: temporary SQLite, inline OOXML and synthetic report records."""
import io,json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
_tmp=tempfile.TemporaryDirectory();os.environ['GSI_DWH_PATH']=str(Path(_tmp.name)/'warehouse.sqlite')
import pandas as pd
from gsi.warehouse.store import Warehouse,RUN
from gsi.warehouse.excel import capture,frame
from gsi.warehouse.numeric import decimal_text
from gsi.control_center.core import defaults,CenterStore,preview_import,render_records,report_context,validate

def fixture(path):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="r1" state="hidden"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>id</t></is></c></row><row r="2" hidden="1"><c r="A2"><v>00123</v></c><c r="B2" t="e"><f>#REF!/#REF!</f><v>#REF!</v></c></row></sheetData></worksheet>')

class Tests(unittest.TestCase):
 def setUp(self):self.wh=Warehouse()
 def test_frame_roundtrip(self):
    df=pd.DataFrame({'id':['0012','x'],'n':[None,0],'time':[pd.Timestamp('2026-01-01'),pd.NaT],'flag':[True,False]})
    pd.testing.assert_frame_equal(df,self.wh.read_frame(self.wh.frame(df,'test','roundtrip')))
 def test_nonfinite_roundtrip(self):
    df=pd.DataFrame({'x':[float('inf'),float('-inf'),float('nan')]})
    pd.testing.assert_frame_equal(df,self.wh.read_frame(self.wh.frame(df,'test','nonfinite')))
 def test_empty_frame(self):
    df=pd.DataFrame(columns=['x']);pd.testing.assert_frame_equal(df,self.wh.read_frame(self.wh.frame(df,'test','empty')))
 def test_failed_run_not_published(self):
    with self.wh.run({}) as good:pass
    self.wh.publish(good)
    with self.assertRaises(ValueError):
      with self.wh.run({}) as bad:raise ValueError('test')
    with self.assertRaises(ValueError):self.wh.publish(bad)
    with self.wh.db() as c:self.assertEqual(c.execute("SELECT run_id FROM wh_current WHERE slot='report'").fetchone()[0],good)
 def test_blob_idempotent(self):
    a=self.wh.blob(b'abc','a','test');b=self.wh.blob(b'abc','b','test');self.assertEqual(a,b)
    with self.wh.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM wh_file WHERE id=?',(a,)).fetchone()[0],1)
 def test_hidden_formula_preserved(self):
    p=Path(_tmp.name)/'hidden.xlsx';fixture(p);fid,content,s=capture(p,'test')
    self.assertTrue(s['Data'][1]['hidden']);self.assertEqual(s['Data'][1]['cells'][0]['value'],'00123')
    self.assertEqual(s['Data'][1]['cells'][1]['formula'],'#REF!/#REF!')
    with self.wh.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM wh_raw_row WHERE file_id=?',(fid,)).fetchone()[0],2)
 def test_capture_rerun(self):
    p=Path(_tmp.name)/'repeat.xlsx';fixture(p);a=capture(p,'test')[0];capture(p,'test')
    with self.wh.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM wh_raw_row WHERE file_id=?',(a,)).fetchone()[0],2)
 def test_no_network_db(self):
    with self.assertRaises(ValueError):Warehouse('//server/share/db.sqlite')
 def test_wrong_database(self):
    import sqlite3
    p=Path(_tmp.name)/'unrelated.sqlite'
    with sqlite3.connect(p) as c:c.execute('CREATE TABLE business(x)')
    with self.assertRaises(ValueError):Warehouse(p)
 def test_backup(self):
    p=self.wh.backup(Path(_tmp.name)/'backup.sqlite')
    import sqlite3
    with sqlite3.connect(p) as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
 def test_decimal(self):
    self.assertEqual(decimal_text('۱٬۲۳۴٫۵۰'),'1234.50');self.assertIsNone(decimal_text('1,23'));self.assertIsNone(decimal_text('#REF!'))
 def test_contacts_and_membership(self):
    cfg=defaults();spec={'id':'contacts','kind':'contacts','mapping':{'employee_code':'کد','first_name':'نام','last_name':'فامیل','email':'ایمیل','management':'مدیریت','department':'اداره','position':'سمت'},'default_cluster_id':'purchase_1'}
    cfg['sources']=[spec]
    blob='کد,نام,فامیل,ایمیل,مدیریت,اداره,سمت\n10213984,آزمایشی,نمونه,test@example.com,خرید,قطعات,مدیر\n'.encode()
    result,summary=preview_import(cfg,spec,blob,'contacts.csv')
    self.assertEqual(result['people'][0]['name'],'آزمایشی نمونه');self.assertEqual(result['memberships'][0]['level'],'manager');self.assertEqual(summary['assigned'],1)
 def test_contact_invalid_atomic(self):
    cfg=defaults();spec={'kind':'contacts','mapping':{'employee_code':'id','name':'name','email':'email'}}
    with self.assertRaises(ValueError):preview_import(cfg,spec,b'id,name,email\n10213984,A,bad\n','a.csv')
    self.assertEqual(cfg['people'],[])
 def test_config_revision_audit_transaction(self):
    store=CenterStore(Path(_tmp.name)/'center');cfg=store.load();new=store.save(cfg,cfg['revision'])
    with self.assertRaises(ValueError):store.save(cfg,cfg['revision'])
    self.assertEqual(store.load()['revision'],new['revision']);self.assertFalse((store.root/'history').exists())
 def test_html_custom_fields_role_widgets(self):
    cfg=defaults();p={'employee_code':'10213984','name':'آزمایشی نمونه','email':'test@example.com','management':'مدیریت نمونه','department':'اداره نمونه','position':'مدیر','active':True,'custom_پروژه':'نمونه <script>'}
    cfg['people']=[p];cfg['memberships']=[{'employee_code':p['employee_code'],'cluster_id':'purchase_1','level':'manager','active':True}]
    cfg['sources']=[{'id':'people','kind':'contacts','mapping':{'employee_code':'id','email':'mail','name':'full','custom_پروژه':'پروژه'}}]
    cfg['clusters'][0]['header']='{management} — {department} — {name} — {custom_پروژه}'
    validate(cfg);person,cluster,member=report_context(cfg,p['employee_code'],'purchase_1','daily')
    h=render_records(cfg,person,cluster,member,'daily',{'ref_date':'2026-09-19','records':[{'KEY_REG':'123','NEXT_ACTION_TITLE':'پیگیری','NEXT_ACTION_DUE_DATE':'2026-09-18','مانع فعلی':'پاسخ بانک'}]})['html']
    self.assertIn('مدیریت نمونه',h);self.assertIn('موارد پیشنهادی برای مرور مدیر',h);self.assertIn('عقب‌افتاده',h);self.assertNotIn('<script>',h)
 def test_scope_does_not_expand_for_manager(self):
    from gsi.control_center.scope import warehouse_context
    with self.wh.run({'reference_date':'2026-09-19'}) as rid:
       self.wh.frame(pd.DataFrame({'KEY_EMP':['10213984','10213985'],'KEY_REG':['a','b']}),'mart','main')
    self.wh.publish(rid)
    result=warehouse_context('10213984',{'cluster_id':'purchase_1','level':'manager'})
    self.assertEqual(len(result['records']),1);self.assertEqual(result['records'][0]['KEY_REG'],'a')
 def test_explicit_scope(self):
    from gsi.control_center.scope import warehouse_context
    with self.wh.run({'reference_date':'2026-09-19'}) as rid:
       self.wh.frame(pd.DataFrame({'KEY_EMP':['10213984','10213985'],'KEY_REG':['a','b']}),'mart','main')
    self.wh.publish(rid)
    result=warehouse_context('10213984',{'cluster_id':'purchase_1','level':'manager','scope_employee_codes':'10213985'})
    self.assertEqual(len(result['records']),2)
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 print(f'نتیجه: {r.testsRun-len(r.failures)-len(r.errors)} موفق | {len(r.failures)+len(r.errors)} ناموفق')
 sys.exit(not r.wasSuccessful())
