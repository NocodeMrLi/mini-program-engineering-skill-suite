"""Recovery never admits a generated failure, altered input, or hidden dispatch."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
P=Path(__file__).resolve().parents[1]/'scripts/artifact_nondegradation_gate.py'
S=importlib.util.spec_from_file_location('recovery_gate',P);g=importlib.util.module_from_spec(S);S.loader.exec_module(g)
class RecoveryEvidence(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.i=0
 def bind(self,value):
  self.i+=1;raw=value if isinstance(value,bytes)else json.dumps(value).encode();name=f'evidence-{self.i}';(self.root/name).write_bytes(raw);return {'path':name,'sha256':g.sha256_bytes(raw)}
 def trial(self,recovery=True):
  run_prefix=str(self.i);stages=[];roles=['actor','peer','repair','recovery']if recovery else['actor','peer']
  for role in roles:
   failed=role=='repair';count=2 if role=='actor'else 1;prompt=b'same repair'if role in('repair','recovery')else role.encode()
   response=b''if failed else json.dumps({'response':'final model report','sessionId':run_prefix+'-'+role}).encode()
   denial={'type':'response.failed','response':{'error':{'code':'rate_limit_exceeded'},'output':[],'model':'GLM-5.3','status':'failed','usage':None,'id':run_prefix}}
   sse=('data: '+json.dumps(denial)+'\n\ndata: '+json.dumps({'type':'error','code':'rate_limit_exceeded'})+'\n\ndata: [DONE]\n').encode()
   ledger=[{'event':'upstream-dispatch','ordinal':i,'model':'GLM-5.3'}for i in range(1,count+1)]
   if failed:ledger.append({'event':'upstream-completed','response_sha256':g.sha256_bytes(sse),'ordinal':1})
   raw=b'\n'.join(json.dumps(row).encode()for row in ledger)
   audit={'id':run_prefix+'-'+role,'sessionId':run_prefix+'-'+role,'engine':'test-engine','execution_mode':'actor'if role=='actor'else'closed','fresh_context':True,'mcp_server_names':['audit_probe']if role=='actor'else[],'actual_upstream_calls':count,'maximum_provider_calls':5 if role=='actor'else 1,'automatic_retries':0,'provider_request_ledger_sha256':g.sha256_bytes(raw),'prompt_sha256':g.sha256_bytes(prompt),'model':'GLM-5.3','global_provider_config_unchanged':True,'temporary_credentials_removed':True,'elapsed_seconds':1.0,'status':'failed'if failed else'completed','provider_config_sha256':'a'*64,'adapter_sha256':'b'*64 if role=='actor'else'c'*64,'tool_execution_events':0,'observed_tool_names':[],'enabled_plugin_count':0,'mcp_server_connections':0,'observed_models':['GLM-5.3'],'response_sha256':g.sha256_bytes(response)}
   row={'role':role,'audit':self.bind(audit),'prompt':self.bind(prompt),'ledger':self.bind(raw),'stdout':self.bind(response)}
   if failed:row.update(refusal_sse=self.bind(sse),execution_events=self.bind([{'event':'bootstrap.app.startup.plugins.completed','context':{'enabledPluginCount':0}}]))
   stages.append(row)
  artifact=self.bind(b'final model report\n');return {'controls':{'retry_budget':1,'retry_count':int(recovery),'model':'GLM-5.3','call_budget':8,'time_budget_seconds':2700},'transport_stages':stages,'actual_provider_calls':len(roles)+1,'elapsed_seconds':float(len(roles)),'artifact_path':artifact['path'],'artifact_sha256':artifact['sha256']}
 def check(self,r):return g.validate_transport_recovery(self.root,r,g.TRANSPORT_RECOVERY_POLICY)
 def change_audit(self,r,index,key,value):
  a=json.loads(g.bound_bytes(self.root,r['transport_stages'][index]['audit']));a[key]=value;r['transport_stages'][index]['audit']=self.bind(a)
 def test_equal_opportunity_with_true_zero_and_one_recoveries(self):
  self.assertEqual(self.check(self.trial()),[]);self.assertEqual(self.check(self.trial(False)),[])
 def test_recovery_count_cannot_hide_retry(self):
  r=self.trial();r['controls']['retry_count']=0;self.assertTrue(self.check(r))
 def test_changed_recovery_prompt_is_rejected(self):
  r=self.trial();r['transport_stages'][-1]['prompt']=self.bind(b'different');self.change_audit(r,-1,'prompt_sha256',g.sha256_bytes(b'different'));self.assertTrue(self.check(r))
 def test_timeout_or_generated_result_is_not_quota_refusal(self):
  for event in ({'type':'response.failed','response':{'error':{'code':'timeout'},'output':[],'model':'GLM-5.3','status':'failed','usage':None}},{'type':'response.failed','response':{'error':{'code':'rate_limit_exceeded'},'output':[{'text':'partial'}],'model':'GLM-5.3'}}):
   r=self.trial();row=r['transport_stages'][-2];raw=('data: '+json.dumps(event)+'\ndata: '+json.dumps({'type':'error','code':'rate_limit_exceeded'})+'\n').encode();row['refusal_sse']=self.bind(raw)
   ledger=[{'event':'upstream-dispatch','ordinal':1,'model':'GLM-5.3'},{'event':'upstream-completed','response_sha256':g.sha256_bytes(raw)}];blob=b'\n'.join(json.dumps(x).encode()for x in ledger);row['ledger']=self.bind(blob);self.change_audit(r,-2,'provider_request_ledger_sha256',g.sha256_bytes(blob));self.assertTrue(self.check(r))
 def test_changed_configuration_or_tools_block(self):
  for key,value in [('provider_config_sha256','different'),('tool_execution_events',1),('observed_models',['DeepSeek'])]:
   r=self.trial();self.change_audit(r,-1,key,value);self.assertTrue(self.check(r))
 def test_total_dispatch_and_failed_elapsed_must_be_counted(self):
  for key,value in [('actual_provider_calls',4),('elapsed_seconds',3.0)]:
   r=self.trial();r[key]=value;self.assertTrue(self.check(r))
 def test_record_cannot_exceed_common_budget(self):
  r=self.trial();r['controls']['call_budget']=4;self.assertTrue(self.check(r));r=self.trial();r['controls']['time_budget_seconds']=3;self.assertTrue(self.check(r))
 def test_hand_edited_final_report_cannot_pass(self):
  r=self.trial();a=self.bind(b'hand edited report\n');r.update(artifact_path=a['path'],artifact_sha256=a['sha256']);self.assertTrue(self.check(r))
 def test_missing_receipts_bad_policy_and_second_recovery_block(self):
  r=self.trial();r['transport_stages'].append(deepcopy(r['transport_stages'][-1]));self.assertTrue(self.check(r));r=self.trial();del r['transport_stages'][0]['ledger'];self.assertTrue(self.check(r));self.assertTrue(g.validate_transport_recovery(self.root,self.trial(),{}))
 def test_no_space_sse_generated_event_is_not_skipped(self):
  r=self.trial();row=r['transport_stages'][-2];raw=g.bound_bytes(self.root,row['refusal_sse']);raw=b'data:{"type":"response.output_text.delta","delta":"partial"}\n\n'+raw;row['refusal_sse']=self.bind(raw)
  ledger=[{'event':'upstream-dispatch','ordinal':1,'model':'GLM-5.3'},{'event':'upstream-completed','response_sha256':g.sha256_bytes(raw)}];blob=b'\n'.join(json.dumps(x).encode()for x in ledger);row['ledger']=self.bind(blob);self.change_audit(r,-2,'provider_request_ledger_sha256',g.sha256_bytes(blob));self.assertTrue(self.check(r))
 def test_failed_stage_tool_execution_blocks_recovery(self):
  r=self.trial();r['transport_stages'][-2]['execution_events']=self.bind([{'event':'bootstrap.app.startup.plugins.completed','context':{'enabledPluginCount':0}},{'event':'tool.call.started','context':{}}]);self.assertTrue(self.check(r))
 def test_boolean_retry_count_is_not_integer(self):
  r=self.trial();r['controls']['retry_count']=True;self.assertTrue(self.check(r))
 def paired_bundle(self):
  from test_validated_skill_upgrade import make_bundle,write_json
  path=make_bundle(self.root);bundle=json.loads(path.read_text());bundle.update(model='GLM-5.3',transport_recovery_policy=g.TRANSPORT_RECOVERY_POLICY)
  for case in bundle['cases']:
   judgment=json.loads((self.root/case['judgment_path']).read_text())
   for index,reference in enumerate(case['runs']):
    p=self.root/reference['record_path'];r=json.loads(p.read_text());trial=self.trial(index==0);r.update({k:v for k,v in trial.items()if k!='controls'});r['controls'].update(trial['controls']);reference['record_sha256']=write_json(p,r);judgment['run_artifacts'][r['arm']][r['run_id']]=r['artifact_sha256']
   case['judgment_sha256']=write_json(self.root/case['judgment_path'],judgment)
  write_json(path,bundle);return path,bundle
 def test_opt_in_pass_and_default_retry_difference_stays_fail(self):
  from test_validated_skill_upgrade import write_json
  p,b=self.paired_bundle();self.assertEqual(g.validate_bundle(p)['verdict'],'PASS')
  del b['transport_recovery_policy'];write_json(p,b);self.assertIn('case:case-1:controls-not-equivalent',g.validate_bundle(p)['problems'])
 def test_cross_run_receipt_reuse_and_control_change_block(self):
  from test_validated_skill_upgrade import write_json
  p,b=self.paired_bundle();a,bref=b['cases'][0]['runs'][:2];first=json.loads((self.root/a['record_path']).read_text());rp=self.root/bref['record_path'];r=json.loads(rp.read_text());r['transport_stages'][0]=first['transport_stages'][0];r['controls']['permissions_sha256']='9'*64;bref['record_sha256']=write_json(rp,r);write_json(p,b);issues=g.validate_bundle(p)['problems'];self.assertTrue(any('transport-session-reused'in x for x in issues));self.assertTrue(any('controls-not-equivalent'in x for x in issues))
 def test_malformed_receipts_fail_closed_without_private_path(self):
  for raw in (b'null',b'{"event":"upstream-dispatch","ordinal":1,"model":"GLM-5.3"}\nnull'):
   r=self.trial();r['transport_stages'][0]['ledger']=self.bind(raw);self.change_audit(r,0,'provider_request_ledger_sha256',g.sha256_bytes(raw));self.assertTrue(self.check(r))
  for events in ([None],[{'event':'bootstrap.app.startup.plugins.completed','context':None}]):
   r=self.trial();r['transport_stages'][-2]['execution_events']=self.bind(events);self.assertTrue(self.check(r))
  r=self.trial();self.change_audit(r,0,'elapsed_seconds',10**400);self.assertTrue(self.check(r))
  r=self.trial();(self.root/r['transport_stages'][0]['audit']['path']).unlink();issues=self.check(r);self.assertTrue(issues);self.assertNotIn(str(self.root),' '.join(issues))
 def test_unused_null_refusal_reference_does_not_crash_bundle(self):
  from test_validated_skill_upgrade import write_json
  p,b=self.paired_bundle();ref=b['cases'][0]['runs'][0];rp=self.root/ref['record_path'];r=json.loads(rp.read_text());r['transport_stages'][0]['refusal_sse']=None;ref['record_sha256']=write_json(rp,r);write_json(p,b);self.assertEqual(g.validate_bundle(p)['verdict'],'PASS')
 def test_actual_config_change_for_whole_run_blocks(self):
  from test_validated_skill_upgrade import write_json
  p,b=self.paired_bundle();ref=b['cases'][0]['runs'][1];rp=self.root/ref['record_path'];r=json.loads(rp.read_text())
  for index in range(len(r['transport_stages'])):self.change_audit(r,index,'provider_config_sha256','d'*64)
  ref['record_sha256']=write_json(rp,r);write_json(p,b);self.assertTrue(any('actual-transport-profile-not-equivalent'in x for x in g.validate_bundle(p)['problems']))
 def test_actual_engine_session_reuse_blocks_even_with_new_audit_id(self):
  from test_validated_skill_upgrade import write_json
  p,b=self.paired_bundle();first=json.loads((self.root/b['cases'][0]['runs'][0]['record_path']).read_text());old=json.loads(g.bound_bytes(self.root,first['transport_stages'][1]['audit']));ref=b['cases'][0]['runs'][1];rp=self.root/ref['record_path'];r=json.loads(rp.read_text());row=r['transport_stages'][1];response=json.loads(g.bound_bytes(self.root,row['stdout']));response['sessionId']=old['sessionId'];blob=json.dumps(response).encode();row['stdout']=self.bind(blob);self.change_audit(r,1,'sessionId',old['sessionId']);self.change_audit(r,1,'response_sha256',g.sha256_bytes(blob));ref['record_sha256']=write_json(rp,r);write_json(p,b);self.assertTrue(any('actual-engine-session-reused'in x for x in g.validate_bundle(p)['problems']))
 def test_all_completed_stage_stdout_bound_and_tool_event_families_denied(self):
  r=self.trial();r['transport_stages'][0]['stdout']=self.bind(b'{}');self.assertTrue(self.check(r))
  for event in ('tool.execution.started','tool.invoke.completed','mcp.tool.started'):
   r=self.trial();r['transport_stages'][-2]['execution_events']=self.bind([{'event':'bootstrap.app.startup.plugins.completed','context':{'enabledPluginCount':0}},{'event':event,'context':{}}]);self.assertTrue(self.check(r))
 def test_missing_or_null_shared_profiles_block(self):
  r=self.trial()
  for index in range(len(r['transport_stages'])):
   for key in ('provider_config_sha256','adapter_sha256','engine','execution_mode'):self.change_audit(r,index,key,None)
  self.assertTrue(self.check(r))
 def test_all_runs_missing_engine_mode_or_actor_adapter_are_invalid(self):
  from test_validated_skill_upgrade import write_json
  for fields in (('engine','execution_mode'),('adapter_sha256',)):
   p,b=self.paired_bundle()
   for case in b['cases']:
    for ref in case['runs']:
     rp=self.root/ref['record_path'];r=json.loads(rp.read_text())
     for stage in r['transport_stages']:
      if fields==('adapter_sha256',)and stage['role']!='actor':continue
      audit=json.loads(g.bound_bytes(self.root,stage['audit']))
      for field in fields:del audit[field]
      stage['audit']=self.bind(audit)
     ref['record_sha256']=write_json(rp,r)
   write_json(p,b);self.assertEqual(g.validate_bundle(p)['verdict'],'FAIL');self.assertTrue(any('actual-transport-profile-invalid'in x for x in g.validate_bundle(p)['problems']))
 def test_tampered_hash_or_unsafe_reference_block(self):
  r=self.trial();r['transport_stages'][0]['audit']['sha256']='0'*64;self.assertTrue(self.check(r));r=self.trial();r['transport_stages'][0]['audit']['path']='../outside';self.assertTrue(self.check(r))
if __name__=='__main__':unittest.main()
