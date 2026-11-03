import hashlib,json,stat
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
ROOT=Path('/workspace'); RELEASE=Path('/results/phase3a-v1/release-v3'); RETAINED=Path('/retained-release'); INPUT=Path('/retained-run'); OUT=Path('/export');REPORT=Path('/results/phase3a-v1/live-stop-report-v1')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
def cp(src,dst):
 assert stat.S_ISREG(src.lstat().st_mode) and not src.is_symlink()
 data=src.read_bytes();dst.parent.mkdir(parents=True,exist_ok=True)
 with dst.open('xb') as f:f.write(data)
 assert sha(src)==sha(dst)
 return hashlib.sha256(data).hexdigest()
study=read(RETAINED/'study.json');run=Path('/results/phase3a-v1')/study['study_sha256']/'live';inputs={};excluded=[]
for name in ('study.json','live-grant.json'):inputs['release/'+name]=cp(RETAINED/name,RELEASE/name)
for directory in ('seed','source'):
 for p in sorted((RETAINED/directory).rglob('*')):
  assert not p.is_symlink()
  if p.is_file():
   name=p.relative_to(RETAINED).as_posix();inputs['release/'+name]=cp(p,RELEASE/name)
for p in sorted(INPUT.rglob('*')):
 assert not p.is_symlink()
 if not p.is_file():continue
 name=p.relative_to(INPUT).as_posix()
 if p.name in ('.writer.lock','credential-binding.json'):
  excluded.append(name);continue
 inputs['run/'+name]=cp(p,run/name)
assert all(sha(ROOT/name)==sha(RELEASE/'source'/name)==v for name,v in study['source']['files'].items())
from followups.phase3a_v1 import workflow
attempts=[]
def forbidden(*args,**kwargs):
 attempts.append('blocked');raise AssertionError('No SDK/client/network allowed in saved-evidence report')
with ExitStack() as stack:
 for name in ('anthropic.Anthropic','anthropic.AsyncAnthropic','openai.OpenAI','openai.AsyncOpenAI','socket.create_connection'):stack.enter_context(patch(name,side_effect=forbidden))
 for d in ('report','replay'):
  summary=workflow.report(RELEASE/'study.json',RELEASE/'live-grant.json',REPORT/d,False)
  assert summary['attempts']==summary['provider_calls']==86 and summary['spent_micro_usd']==1293437
  assert summary['reserved_micro_usd']==0 and summary['primary_scored']==0 and summary['complete_primary'] is False
assert not attempts
names=('rows.json','coverage.json','analysis.json','summary.json','accounting.json','protocol.json','PHASE3A_REPORT.md')
assert all((REPORT/'report'/n).read_bytes()==(REPORT/'replay'/n).read_bytes() for n in names)
for d in ('report','replay'):
 for n in names:cp(REPORT/d/n,OUT/d/n)
assert all(sha(INPUT/name[4:])==v for name,v in inputs.items() if name.startswith('run/'))
assert all(sha(ROOT/name)==v for name,v in study['source']['files'].items())
put(OUT/'raw-inputs.json',{'kind':'phase3a-live-stop-input-inventory-v1','study_sha256':study['study_sha256'],'source_sha256':study['source_sha256'],'files':inputs,'excluded':excluded,'canonical_run':str(run),'original_inputs_preserved':True})
put(OUT/'replay-proof.json',{'kind':'phase3a-live-stop-report-replay-v1','passed':True,**{k:study[k] for k in ('study_sha256','source_sha256','policy_sha256','runtime_sha256','launcher_sha256')},'fixture':False,'live_provider_calls_in_saved_data':86,'reporting_provider_calls':0,'SDK_or_network_attempts':0,'real_credentials_read':False,'original_inputs_preserved':True,'same_absolute_results_paths':True,'input_files':len(inputs),'report_files_byte_equal':7,'output_sha256':{d+'/'+n:sha(OUT/d/n) for d in ('report','replay') for n in names}})
print(json.dumps({'passed':True,'inputs':len(inputs),'report_files_byte_equal':7,'saved_known_calls':86,'reporting_calls':0}))
