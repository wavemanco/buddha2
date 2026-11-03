import copy,hashlib,inspect,json,tempfile
from pathlib import Path
from unittest.mock import patch
from followups.phase3a_v1 import accounting,editor,strategy
from followups.phase3a_v1.mocks import SDKMock
from buddha2.artifacts import ContractError
OUT=Path('/export');TOOLS=json.loads((strategy.ROOT/'followups/phase3a_v1/editor-tools.json').read_text())
original=accounting._editor_request
original_code=inspect.getsource(original)
old="""            elif kind == "tool_use":
                _require(set(block) == {"type", "id", "name", "input"} | cache_keys and block["name"] in names
"""
new="""            elif kind == "tool_use":
                caller_keys = {"caller"} if "caller" in block else set()
                _require(not caller_keys or block["caller"] == {"type": "direct"},
                         "only direct client-tool caller metadata is supported")
                _require(set(block) == {"type", "id", "name", "input"} | cache_keys | caller_keys and block["name"] in names
"""
assert original_code.count(old)==1
candidate_code=original_code.replace(old,new)
namespace=dict(accounting.__dict__);exec(compile(candidate_code,'candidate-accounting-function.py','exec'),namespace)
candidate=namespace['_editor_request']
with (OUT/'candidate-accounting-function.py').open('x',encoding='utf-8') as f:f.write(candidate_code)
class CallerMock(SDKMock):
 def _handle(self,request,*,http_module):
  response=super()._handle(request,http_module=http_module)
  if self._selected[0]!='editor':return response
  body=json.loads(response.content)
  for block in body['content']:
   if block['type']=='tool_use':block['caller']={'type':'direct'}
  self.records[-1]['response']=copy.deepcopy(body)
  return http_module.Response(200,json=body,headers={'request-id':self.records[-1]['request_id']})
def run_case(name,validator,expected):
 requests=[];rejected=[];holds=[]
 with CallerMock() as mock,tempfile.TemporaryDirectory() as temp,patch.object(accounting,'_editor_request',validator):
  root=Path(temp);strategy.materialize_seed(root/'input/harness')
  def dispatch(slot,role,request):
   requests.append(copy.deepcopy(request));before=copy.deepcopy(request)
   try:accounting.validate_request(role,request,editor_tools=TOOLS)
   except ContractError as ex:
    rejected.append({'message':str(ex),'request':copy.deepcopy(request)});raise
   assert request==before,'validator mutated the effective wire request'
   mock.transport.select(role,slot);response=mock.transport.create(role,request)
   return {'status':'response','response':response,'slot_id':slot}
  prop=editor.AccountedProposer(pilot='p3a-01',study_sha256='b'*64,dispatch=dispatch,audit_dir=root/'audit',fixture=True,halt=lambda *a,**k:holds.append({'args':a,'kwargs':k}))
  error=None;reply=None
  try:reply=prop.call('Edit the declared strategy and report completion.',root/'input','inv1.a1',harvest='context/harness',max_attempts=1)
  except Exception as ex:error=type(ex).__name__
  forwarded=[b for row in mock.records[1:] for m in row['request']['messages'] for b in (m['content'] if isinstance(m['content'],list) else []) if isinstance(b,dict) and b.get('type')=='tool_use']
  seen=[b for request in requests[1:] for m in request['messages'] for b in (m['content'] if isinstance(m['content'],list) else []) if isinstance(b,dict) and b.get('type')=='tool_use']
  if expected=='reject':
   assert error and len(mock.records)==1 and rejected and rejected[0]['message']=='invalid client tool call'
   assert any(b.get('caller')=={'type':'direct'} for b in seen)
  else:
   assert error is None and not holds and reply is not None and mock.http_calls==3
   assert forwarded and all(b.get('caller')=={'type':'direct'} for b in forwarded)
   assert prop.phase3a_evidence()['sessions']['inv1.a1']['status']=='valid'
  result={'case':name,'expected':expected,'passed':True,'SDK_mock_HTTP':mock.http_calls,'real_provider_calls':0,'error_type':error,'holds':holds,'rejected':rejected,'requests':requests,'wire':mock.records,'direct_caller_seen_in_next_request':any(b.get('caller')=={'type':'direct'} for b in seen),'forwarded_direct_caller_preserved':bool(forwarded) and all(b.get('caller')=={'type':'direct'} for b in forwarded)}
  with (OUT/(name+'.json')).open('x',encoding='utf-8') as f:f.write(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
  return result
old_result=run_case('frozen-v3-rejection',original,'reject')
fixed_result=run_case('candidate-direct-caller',candidate,'accept')
second=copy.deepcopy(fixed_result['requests'][1]);checks=[]
for value in (None,{}, {'type':'code_execution_20260120','tool_id':'srvtoolu_bad'}, {'type':'direct','extra':True}):
 modified=copy.deepcopy(second);tool=next(b for m in modified['messages'] for b in (m['content'] if isinstance(m['content'],list) else []) if isinstance(b,dict) and b.get('type')=='tool_use');tool['caller']=value
 try:candidate('editor',modified,TOOLS)
 except ContractError:checks.append(True)
 else:raise AssertionError('Unsupported caller accepted')
missing=copy.deepcopy(second)
for m in missing['messages']:
 for b in m['content'] if isinstance(m['content'],list) else []:
  if isinstance(b,dict) and b.get('type')=='tool_use':b.pop('caller',None)
candidate('editor',missing,TOOLS)
proof={'kind':'phase3a-direct-caller-offline-regression-v1','passed':True,'fixture':True,'real_provider_calls':0,'real_credentials_read':False,'old_runtime_source_unchanged':True,'frozen_guard_reproduced':True,'candidate_actual_OpenCode_three_turn_path_passed':True,'effective_request_not_mutated':True,'caller_metadata_preserved_on_wire':True,'unsupported_callers_rejected':len(checks),'absent_caller_still_supported':True,'original_function_sha256':hashlib.sha256(original_code.encode()).hexdigest(),'candidate_function_sha256':hashlib.sha256(candidate_code.encode()).hexdigest(),'case_results':{'frozen-v3':{'HTTP':old_result['SDK_mock_HTTP'],'error':old_result['error_type']},'candidate':{'HTTP':fixed_result['SDK_mock_HTTP'],'error':fixed_result['error_type']}}}
with (OUT/'proof.json').open('x',encoding='utf-8') as f:f.write(json.dumps(proof,sort_keys=True,indent=2)+'\n')
print(json.dumps(proof))
