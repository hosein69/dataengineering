import os, subprocess, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from gsi.studio_core.runtime_data import bottleneck_view,resistance_diagnostic

class RuntimeFixTests(unittest.TestCase):
 def test_new_median(self):
  b,m=bottleneck_view(pd.DataFrame({'از فعالیت':['A','B'],'به فعالیت':['B','C'],'میانه روز':[2,7]}))
  self.assertEqual(m,'میانه روز');self.assertEqual(b[m].tolist(),[7,2])
 def test_legacy_mean(self):
  b,m=bottleneck_view(pd.DataFrame({'از فعالیت':['A'],'به فعالیت':['B'],'میانگین روز':[3]}))
  self.assertEqual(m,'میانگین روز');self.assertEqual(len(b),1)
 def test_missing_metric(self):
  b,m=bottleneck_view(pd.DataFrame({'از فعالیت':['A']}));self.assertTrue(b.empty);self.assertIsNone(m)
 def test_invalid_not_zero(self):
  b,m=bottleneck_view(pd.DataFrame({'از فعالیت':['A']*4,'به فعالیت':['B']*4,'میانه روز':['x',float('inf'),-2,0]}))
  self.assertEqual(b[m].tolist(),[0])
 def test_resistance_reasons(self):
  msg=resistance_diagnostic(pd.DataFrame({'مقاومت (روز)':[None,None],'کد طبقه بحرانی':['UNKNOWN','NO_CONSUMPTION']}))
  self.assertIn('بدون مصرف',msg);self.assertIn('نامعلوم',msg)
 def test_empty_filter(self):
  self.assertIn('فیلتر',resistance_diagnostic(pd.DataFrame()))
 def test_config_without_crypto(self):
  code='''
import importlib.abc, sys, tempfile
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='cryptography' or fullname.startswith('cryptography.'):
   raise ModuleNotFoundError('blocked cryptography',name=fullname)
sys.meta_path.insert(0,Deny())
from gsi.control_center.core import CenterStore, defaults, require_encryption
with tempfile.TemporaryDirectory() as d:
 s=CenterStore(d);s.save(defaults(),0);assert s.load()['revision']==1
try:require_encryption()
except RuntimeError as e:assert '-m pip install' in str(e)
else:raise AssertionError('encryption bypassed')
'''
  p=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeFixTests))
 print(f'نتیجه: {r.testsRun-len(r.failures)-len(r.errors)} موفق | {len(r.failures)+len(r.errors)} شکست');sys.exit(not r.wasSuccessful())
