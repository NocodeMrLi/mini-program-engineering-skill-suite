"""Phone scanning must keep real contacts while accepting cryptographic digests."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'scripts/scan_sensitive_content.py'
S=importlib.util.spec_from_file_location('scan_hash_context_module',P)
scan=importlib.util.module_from_spec(S)
import sys
sys.modules[S.name]=scan;S.loader.exec_module(scan)
class HashContextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.phone='1'+'3'+'0'*9
  self.digest='a'*25+self.phone+'b'*28
  assert len(self.digest)==64
 def findings(self,text,name='sample.txt'):
  p=self.root/name;p.write_text(text);return scan.scan_files_with_summary([p],self.root)
 def test_computed_readme_manifest_digest_is_not_a_phone(self):
  import hashlib
  digest=hashlib.sha256((P.parents[1]/'README.md').read_bytes()).hexdigest()
  r,summary=self.findings(json.dumps({'sha256':digest}),'package-manifest.json');self.assertFalse(r);self.assertEqual(summary.scanned_count,1)
 def test_full_hash_with_phone_fragment_keeps_coverage(self):
  r,summary=self.findings(json.dumps({'sha256':self.digest}));self.assertFalse(r);self.assertEqual(summary.text_file_count,1)
 def test_real_contact_same_line_or_short_hex_context_still_detected(self):
  for text in [json.dumps({'sha256':self.digest,'phone':self.phone}),'contact='+self.phone,'a'+self.phone+'b']:
   r,_=self.findings(text,'package-manifest.json');self.assertEqual([x.rule_id for x in r],['mainland-phone-number'])
 def test_hash_shape_never_hides_hardcoded_credentials(self):
  r,_=self.findings('api_key="'+self.digest+'"');self.assertIn('credential-assignment',[x.rule_id for x in r])
if __name__=='__main__':unittest.main()
