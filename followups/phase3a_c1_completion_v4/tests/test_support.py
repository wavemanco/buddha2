"""R3 authority, closed-R2 identity and private-path-first validation."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v4 import support as s


class SupportTests(unittest.TestCase):
    def test_accepted_closed_r2_manifest_and_external_acceptance_are_exact(self):
        value = s._parent_manifest()
        self.assertEqual(value['source_sha256'], s.PARENT_SHA)
        self.assertEqual(value['archive_sha256'], s.PARENT_ARCHIVE_SHA)
        self.assertEqual(value['member_count'], 2484)

    def test_current_r3_authority_binds_history_worklist_and_actual_definition(self):
        value = s.validate_authority()
        self.assertEqual(value['potential_request_slots'], 967)
        self.assertEqual(value['new_max_attempts'], 775)
        self.assertEqual(value['historical_attempts'], 904)
        for field, changed in [('potential_request_slots', 775), ('new_max_attempts', 967),
                               ('historical_known_micro_usd', 12231444), ('historical_attempts', 885),
                               ('new_cap_micro_usd', True), ('historical_liability_release_authorized', True),
                               ('accepted_proposal_sha256', '0' * 64),
                               ('accepted_proposal_path', 'specifications/archive/other.md')]:
            trial = copy.deepcopy(value)
            trial[field] = changed
            with self.subTest(field=field), patch.object(s, 'read', return_value=trial):
                with self.assertRaises(ContractError):
                    s.validate_authority()

    def test_private_names_rejected_before_metadata_and_foreign_output_rejected(self):
        for name in s.c1.PRIVATE:
            target = s.BASE / 'private-check' / name
            with self.subTest(name=name), patch.object(Path, 'is_symlink', side_effect=AssertionError('metadata')):
                with self.assertRaises(ContractError):
                    s.read(target)
                with self.assertRaises(ContractError):
                    s.path(target)
        with self.assertRaises(ContractError):
            s.path(s.ROOT / 'foreign-output.json')

    def test_json_duplicate_and_nonfinite_inputs_rejected_and_valid_seal_preserved(self):
        s.BASE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='support-check-', dir=s.BASE) as directory:
            target = Path(directory) / 'record.json'
            for text in ['{"x":1,"x":2}', '{"x":NaN}', '[1,2]']:
                target.write_text(text, encoding='utf-8')
                with self.assertRaises(ContractError):
                    s.read(target)
            value = s.seal({'scope': 'R3-only'})
            self.assertEqual(s.checked(value), value)
            with self.assertRaises(ContractError):
                s.checked(value | {'scope': 'changed'})
