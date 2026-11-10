"""Clock construction uses the validator's exact arithmetic grouping."""
import math
import unittest

from buddha2.artifacts import ContractError, digest
from followups.phase3b_seq2_v1 import deadline


class ClockConstructionTests(unittest.TestCase):
    def test_fractional_start_constructs_an_exact_strict_clock(self):
        started = 189.39132855435614
        clock = deadline.clock_record(study_sha256="a" * 64, source_sha256="a" * 64,
            pilot="p3b-02", label="select.seq2", fixture=True,
            editor_profile_sha256="a" * 64, started=started)
        self.assertEqual(clock["grace_deadline_monotonic"], started + 900)
        self.assertEqual(deadline.validate_clock(clock), clock)
        tampered = {**clock, "grace_deadline_monotonic": math.nextafter(started + 900, math.inf)}
        tampered["sha256"] = digest({key: value for key, value in tampered.items() if key != "sha256"})
        with self.assertRaisesRegex(ContractError, "invalid conversation timing profile"):
            deadline.validate_clock(tampered)
