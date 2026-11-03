"""Exercise the actual source-bound future gate without grants, keys or SDKs."""

import json
from pathlib import Path
from unittest.mock import patch

from buddha2.phase2_release import _live_readiness, load_release

path = Path('/results/phase2-release-r018/release/study.json')
with patch('buddha2.phase2_dispatch.DirectSDKTransport', side_effect=AssertionError('no SDK')) as client:
    study = load_release(path)
    _live_readiness(study, path)
    client.assert_not_called()
print(json.dumps({'status': 'pass', 'study_sha256': study['study_sha256'],
                  'actual_gate_validation': True, 'sdk_constructions': 0,
                  'provider_calls': 0, 'real_credentials_read': False, 'paid_grant_created': False}))
