"""Longer waiting cannot rewrite old budgets, source, output, or recovery eligibility."""
import importlib.util,json,os,sys,unittest,shutil
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
import test_transport_recovery as fixture
P=Path(os.environ.get('WAITING_GATE_UNDER_TEST',str(Path(__file__).resolve().parents[1]/'scripts/artifact_nondegradation_gate.py')))
S=importlib.util.spec_from_file_location('waiting_gate',P);g=importlib.util.module_from_spec(S);S.loader.exec_module(g)
class WaitingEvidence(unittest.TestCase):
 setUp=fixture.RecoveryEvidence.setUp
 bind=fixture.RecoveryEvidence.bind
 trial=fixture.RecoveryEvidence.trial
 change_audit=fixture.RecoveryEvidence.change_audit
 def lineage(self):
  prior=b"def call(fixture):\n maximum=5 if fixture else 1;deadline=900 if fixture else 600\n gateway=BudgetGateway(ledger,maximum,deadline)\n p.wait(timeout=deadline)\n record={'maximum_provider_calls':maximum,}\n"
  current=prior.replace(b'deadline=900 if fixture else 600',b'deadline=900 if fixture else 1200').replace(b"'maximum_provider_calls':maximum,",b"'maximum_provider_calls':maximum,'stage_deadline_seconds':deadline,")
  return {'prior_adapter':self.bind(prior),'current_adapter':self.bind(current)}
 def decorate(self,r):
  r.setdefault('case_id','case-fixture');r.setdefault('arm','baseline');r.setdefault('repetition',1);r.setdefault('run_id','case-fixture-baseline-'+str(self.i))
  r.setdefault('treatment',{'kind':'none'if r['arm']=='baseline'else'suite-prompt-context','skill_context_sha256':None if r['arm']=='baseline'else'c'*64})
  r['generation_session']=json.loads(g.bound_bytes(self.root,r['transport_stages'][0]['audit']))['id'];r['independent_review_session']=json.loads(g.bound_bytes(self.root,r['transport_stages'][1]['audit']))['id']
 def reservations(self,r):
  out={}
  for stage in r['transport_stages']:
   audit=json.loads(g.bound_bytes(self.root,stage['audit']));role=stage['role'];name=r['run_id']+'-'+('quota-recovery'if role=='recovery'else role)+'-attempt.json'
   raw=json.dumps({'session':audit['id'],'status':audit['status'],'audit_sha256':stage['audit']['sha256'],'actual_provider_calls':audit['actual_upstream_calls']}).encode();(self.root/name).write_bytes(raw);out[role]={'path':name,'sha256':g.sha256_bytes(raw)}
  return out
 def waiting(self,legacy=False,recovery=False):
  r=self.trial(recovery=='quota' or recovery is True)
  if recovery=='completed':
   stage=deepcopy(r['transport_stages'][-1]);stage['role']='repair';audit=json.loads(g.bound_bytes(self.root,stage['audit']));audit['id']+='-repair';audit['sessionId']+='-repair';output=json.loads(g.bound_bytes(self.root,stage['stdout']));output['sessionId']=audit['sessionId'];blob=json.dumps(output).encode();stage['stdout']=self.bind(blob);audit['response_sha256']=g.sha256_bytes(blob);stage['audit']=self.bind(audit);r['transport_stages'].append(stage);r['actual_provider_calls']+=1;r['elapsed_seconds']+=1
  lineage=self.lineage();digest=lineage['prior_adapter'if legacy else'current_adapter']['sha256']
  for i,row in enumerate(r['transport_stages']):
   self.change_audit(r,i,'adapter_sha256',digest)
   if not legacy:self.change_audit(r,i,'stage_deadline_seconds',900 if row['role']=='actor'else 1200)
  self.decorate(r)
  if legacy:
   reservations=self.reservations(r);r['prior_waiting_record']=self.bind(deepcopy(r));r['prior_waiting_attempts']=reservations
  r['controls']['time_budget_seconds']=4500
  return r,lineage
 def check(self,r,lineage):return g.validate_transport_recovery(self.root,r,g.WAITING_TRANSPORT_POLICY,lineage)
 def test_actual_extended_closed_wait_is_accepted(self):
  r,lineage=self.waiting();self.change_audit(r,1,'elapsed_seconds',900.0);r['elapsed_seconds']=901.0;self.assertEqual(self.check(r,lineage),[])
 def test_completed_stricter_stage_retains_original_budget(self):
  r,lineage=self.waiting(True);self.assertEqual(self.check(r,lineage),[]);original=json.loads(g.bound_bytes(self.root,r['prior_waiting_record']));self.assertEqual(original['controls']['time_budget_seconds'],2700)
 def test_only_outer_budget_without_actual_timeout_binding_blocks(self):
  r,lineage=self.waiting();self.change_audit(r,1,'stage_deadline_seconds',600);self.assertTrue(self.check(r,lineage))
 def test_current_adapter_requires_typed_exact_deadline(self):
  for value in (None,True,'1200',900,1800):
   r,lineage=self.waiting();self.change_audit(r,1,'stage_deadline_seconds',value);self.assertTrue(self.check(r,lineage))
 def test_deadline_plus_nonwaiting_change_blocks(self):
  r,lineage=self.waiting();raw=g.bound_bytes(self.root,lineage['current_adapter'])+b'new_prompt=True\n';lineage['current_adapter']=self.bind(raw);self.assertTrue(self.check(r,lineage))
 def test_process_wait_or_gateway_change_not_in_exact_transform_blocks(self):
  for added in (b'process.wait(timeout=600)\n',b'gateway_deadline=600\n'):
   r,lineage=self.waiting();lineage['current_adapter']=self.bind(g.bound_bytes(self.root,lineage['current_adapter'])+added);self.assertTrue(self.check(r,lineage))
 def broken_pair(self,old,new):
  r,lineage=self.waiting();raw=g.bound_bytes(self.root,lineage['prior_adapter']).replace(old,new)
  lineage['prior_adapter']=self.bind(raw);lineage['current_adapter']=self.bind(raw.replace(b'deadline=900 if fixture else 600',b'deadline=900 if fixture else 1200').replace(b"'maximum_provider_calls':maximum,",b"'maximum_provider_calls':maximum,'stage_deadline_seconds':deadline,"))
  for i in range(len(r['transport_stages'])):self.change_audit(r,i,'adapter_sha256',lineage['current_adapter']['sha256'])
  self.assertTrue(self.check(r,lineage))
 def test_both_sources_hardcode_short_process_wait_block(self):self.broken_pair(b'p.wait(timeout=deadline)',b'p.wait(timeout=600)')
 def test_both_sources_hardcode_short_gateway_wait_block(self):self.broken_pair(b'BudgetGateway(ledger,maximum,deadline)',b'BudgetGateway(ledger,maximum,600)')
 def test_later_deadline_overwrite_in_both_sources_blocks(self):self.broken_pair(b'gateway=BudgetGateway',b'deadline=600\n gateway=BudgetGateway')
 def test_prior_adapter_without_immutable_record_blocks(self):
  r,lineage=self.waiting(True);del r['prior_waiting_record'];self.assertTrue(self.check(r,lineage))
 def test_tampered_or_unsafe_ancestry_blocks(self):
  r,lineage=self.waiting(True);r['prior_waiting_record']['sha256']='0'*64;self.assertTrue(self.check(r,lineage));r,lineage=self.waiting(True);r['prior_waiting_record']['path']='../outside';self.assertTrue(self.check(r,lineage))
 def test_inherited_stage_cannot_be_replaced(self):
  r,lineage=self.waiting(True);self.change_audit(r,1,'id','different-actual-stage');self.assertTrue(self.check(r,lineage))
 def test_legacy_over_original_cap_is_not_grandfathered(self):
  r,lineage=self.waiting(True);self.change_audit(r,1,'elapsed_seconds',601.0);r['elapsed_seconds']=602.0;original=deepcopy(r);original.pop('prior_waiting_record');original['controls']['time_budget_seconds']=2700;r['prior_waiting_record']=self.bind(original);self.assertTrue(self.check(r,lineage))
 def test_subdirectory_ancestry_resolves_bytes_with_changed_relative_paths(self):
  r,lineage=self.waiting(True);directory=self.root/'original';directory.mkdir()
  for file in list(self.root.iterdir()):
   if file.is_file():shutil.copyfile(file,directory/file.name)
  r['prior_waiting_record']['path']='original/'+r['prior_waiting_record']['path']
  for stage in r['transport_stages']:
   for value in stage.values():
    if isinstance(value,dict):value['path']='original/'+value['path']
  self.assertEqual(self.check(r,lineage),[])
 def test_waiting_nested_parent_symlink_is_rejected(self):
  r,lineage=self.waiting(True);outside=self.root/'real';outside.mkdir();source=self.root/r['prior_waiting_record']['path'];shutil.copyfile(source,outside/source.name);(self.root/'alias').symlink_to(outside,target_is_directory=True);r['prior_waiting_record']['path']='alias/'+source.name;self.assertTrue(self.check(r,lineage))
 def test_waiting_nested_escape_or_empty_components_are_rejected(self):
  for name in ('../outside','original/../outside','original//file','/absolute/file'):
   r,lineage=self.waiting(True);r['prior_waiting_record']['path']=name;self.assertTrue(self.check(r,lineage))
 def test_successful_material_repair_cannot_be_replaced(self):
  r,lineage=self.waiting(True,'completed');self.assertEqual(self.check(r,lineage),[]);self.change_audit(r,-1,'adapter_sha256',lineage['current_adapter']['sha256']);self.change_audit(r,-1,'stage_deadline_seconds',1200);self.assertTrue(self.check(r,lineage))
 def test_completed_chain_cannot_be_shortened(self):
  r,lineage=self.waiting(True,'completed');r['transport_stages'].pop();r['actual_provider_calls']-=1;r['elapsed_seconds']-=1;self.assertTrue(self.check(r,lineage))
 def test_arm_context_or_generation_identity_cannot_be_relabelled(self):
  for key,value in [('arm','with-skill'),('case_id','another-case'),('repetition',2),('run_id','another-run'),('treatment',{'kind':'suite-prompt-context','skill_context_sha256':'c'*64}),('generation_session','another-session')]:
   r,lineage=self.waiting(True);r[key]=value;self.assertTrue(self.check(r,lineage))
 def test_consumed_failed_repair_slot_cannot_be_reopened(self):
  r,lineage=self.waiting(True);name=r['run_id']+'-repair-attempt.json';raw=json.dumps({'session':'timed-out','status':'failed'}).encode();(self.root/name).write_bytes(raw);r['prior_waiting_attempts']['repair']={'path':name,'sha256':g.sha256_bytes(raw)};self.assertTrue(self.check(r,lineage))
 def test_omitting_existing_reserved_slot_is_rejected(self):
  r,lineage=self.waiting(True);name=r['run_id']+'-repair-attempt.json';(self.root/name).write_text('{}');self.assertTrue(self.check(r,lineage))
 def test_actual_sibling_symlink_with_safe_declared_copy_blocks(self):
  r,lineage=self.waiting(True);file=self.root/r['prior_waiting_attempts']['actor']['path'];copy=self.root/'safe-copy';copy.write_bytes(file.read_bytes());r['prior_waiting_attempts']['actor']['path']=copy.name;file.unlink();file.symlink_to(copy);self.assertTrue(self.check(r,lineage))
 def test_extra_dangling_failed_slot_cannot_disappear(self):
  r,lineage=self.waiting(True);(self.root/(r['run_id']+'-repair-attempt.json')).symlink_to(self.root/'does-not-exist');self.assertTrue(self.check(r,lineage))
 def test_actual_sibling_directory_is_rejected(self):
  r,lineage=self.waiting(True);file=self.root/r['prior_waiting_attempts']['actor']['path'];file.unlink();file.mkdir();self.assertTrue(self.check(r,lineage))
 def test_unmodified_prior_final_artifact_is_required(self):
  r,lineage=self.waiting(True);blob=self.bind(b'new hand edited report\n');r['artifact_path']=blob['path'];r['artifact_sha256']=blob['sha256'];self.assertTrue(self.check(r,lineage))
 def test_legacy_semantic_context_change_blocks(self):
  r,lineage=self.waiting(True);r['controls']['permissions_sha256']='d'*64;self.assertTrue(self.check(r,lineage))
 def test_prior_recovery_slot_cannot_be_reset(self):
  r,lineage=self.waiting(True,True);r['controls']['retry_count']=0;self.assertTrue(self.check(r,lineage))
 def test_timeout_is_never_quota_recovery(self):
  r,lineage=self.waiting(recovery=True);self.change_audit(r,2,'error','engine-timeout');self.assertTrue(self.check(r,lineage))
 def test_extended_budget_does_not_remove_caps(self):
  r,lineage=self.waiting();self.change_audit(r,1,'elapsed_seconds',1201.0);r['elapsed_seconds']=1202.0;self.assertTrue(self.check(r,lineage));r,lineage=self.waiting();r['controls']['time_budget_seconds']=5000;self.assertTrue(self.check(r,lineage))
 def test_default_protocol_still_rejects_extended_wait(self):
  r,lineage=self.waiting();r['controls']['time_budget_seconds']=2700;self.change_audit(r,1,'elapsed_seconds',900.0);r['elapsed_seconds']=901.0;self.assertTrue(g.validate_transport_recovery(self.root,r,g.TRANSPORT_RECOVERY_POLICY))
 def test_default_protocol_does_not_accept_waiting_lineage(self):
  r=self.trial(False);self.assertTrue(g.validate_transport_recovery(self.root,r,g.TRANSPORT_RECOVERY_POLICY,self.lineage()))
 def test_equal_arms_with_mixed_bounded_adapter_lineage(self):
  from test_validated_skill_upgrade import write_json
  helper=fixture.RecoveryEvidence('test_equal_opportunity_with_true_zero_and_one_recoveries');helper.tmp=self.tmp;helper.root=self.root;helper.i=self.i
  path,bundle=helper.paired_bundle();self.i=helper.i;lineage=self.lineage();bundle['transport_recovery_policy']=g.WAITING_TRANSPORT_POLICY;bundle['waiting_adapter_lineage']=lineage
  for case in bundle['cases']:
   for index,ref in enumerate(case['runs']):
    file=self.root/ref['record_path'];r=json.loads(file.read_text());legacy=index%2==0
    for i,row in enumerate(r['transport_stages']):
     self.change_audit(r,i,'adapter_sha256',lineage['prior_adapter'if legacy else'current_adapter']['sha256'])
     if not legacy:self.change_audit(r,i,'stage_deadline_seconds',900 if row['role']=='actor'else 1200)
    self.decorate(r)
    if legacy:
     reservations=self.reservations(r);r['prior_waiting_record']=self.bind(deepcopy(r));r['prior_waiting_attempts']=reservations
    r['controls']['time_budget_seconds']=4500;ref['record_sha256']=write_json(file,r)
  write_json(path,bundle);self.assertEqual(g.validate_bundle(path)['verdict'],'PASS',g.validate_bundle(path)['problems'])
  ref=bundle['cases'][0]['runs'][1];file=self.root/ref['record_path'];r=json.loads(file.read_text())
  for i in range(len(r['transport_stages'])):self.change_audit(r,i,'provider_config_sha256','d'*64)
  ref['record_sha256']=write_json(file,r);write_json(path,bundle);self.assertTrue(any('actual-transport-profile-not-equivalent'in x for x in g.validate_bundle(path)['problems']))
if __name__=='__main__':unittest.main()
