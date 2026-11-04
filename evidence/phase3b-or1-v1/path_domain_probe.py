"""Reuse the owned H1 driver to test the actual contained entry guard."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "evidence/phase3b-or1-v1/writer_domain_probe.py"
DRIVER_SHA = "8ba0023f611574fcd0f6facb626266681a4201a73cedb00890ebd7e5f042e6df"
PROBE = r'''
import importlib.util,json,hashlib
from pathlib import Path
from followups.phase3b_seq2_v1 import verify,workflow
from followups.phase3b_seq2_v1.support import recovery_config
config=recovery_config()
if config['candidate']!=2 or config['verification']!='verification-v6':raise ValueError('only preservedfailedv6 precheck')
source=Path('/workspace/evidence/phase3b-seq2-c2-v1/composed_acceptance.py')
spec=importlib.util.spec_from_file_location('or1_actual_path_module',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
allowed=workflow.BASE/config['verification']
if not allowed.is_dir():raise ValueError('preserved failedv6 missing')
sentinels=[allowed/name for name in ('operator-main.json','c2-main-execution.json','boundary-contract/result.json')]
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in sentinels}
if module.runtime_output(str(allowed))!=allowed:raise ValueError('actual containedvalidator rejected exactruntime')
rejections={}
for name,value in {'hostalias':'/workspace/runs/phase3b-seq2-v1/verification-v6',
 'BASE':str(workflow.BASE),'sibling':str(workflow.BASE/'verification-v7'),
 'traversal':str(workflow.BASE/'child/../verification-v6')}.items():
 try:module.runtime_output(value)
 except ValueError:rejections[name]=True
 else:raise ValueError('wrongdomain accepted:'+name)
try:verify.output_path(str(allowed),existing=True)
except ValueError:rejections['hostguard_unchanged']=True
else:raise ValueError('hostguard was weakened')
alias=workflow.BASE/'or1-path-domain-v1/symlink'
alias.symlink_to(allowed,target_is_directory=True)
try:
 try:module.runtime_output(str(alias))
 except ValueError as exc:
  if 'linked S2 input/output'not in str(exc):raise ValueError('symlink not rejected by linkguard')
  rejections['symlink']=True
 else:raise ValueError('symlink accepted')
finally:alias.unlink()
if before!={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in sentinels}:raise ValueError('failedv6inputs changed')
print(json.dumps({'passed':True,'exact_runtime_accepted':True,'rejections':rejections,
 'preserved_failedv6_sentinels_unchanged':True,'tested_function':'composed_acceptance.runtime_output',
 'workflow_run_calls':0,'model_calls':0,'provider_calls':0,'release_admissions':0}))
'''


def main() -> int:
    if hashlib.sha256(DRIVER.read_bytes()).hexdigest() != DRIVER_SHA:
        raise ValueError("reviewed owned component driver changed")
    spec = importlib.util.spec_from_file_location("or1_owned_domain_driver", DRIVER)
    if spec is None or spec.loader is None:
        raise ValueError("owned component driver cannot load")
    driver: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.OUT = ROOT / "runs/phase3b-seq2-v1/or1-path-domain-v1"
    driver.PROBE = PROBE
    return driver.main()


if __name__ == "__main__":
    raise SystemExit(main())
