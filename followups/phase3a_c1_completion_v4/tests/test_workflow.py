"""The expanded worklist is distinct from unchanged admission resources."""
import copy
import unittest

from buddha2.artifacts import ContractError
from followups.phase3a_c1_completion_v4 import accounting, workflow
from followups.phase3a_v1 import accounting as old_accounting


class WorklistTests(unittest.TestCase):
    def setUp(self):
        self.study = {"tasks": workflow.frozen_tasks(), "execution_tag": "r3-worklist-unit"}

    def test_complete_extended_inventory_preserves_all_generation_and_assessment_slots(self):
        old, old_assessments = workflow.parent._plan_slots(self.study)
        slots, assessments = workflow._plan_slots(self.study)
        self.assertEqual(len(old), 775)
        self.assertEqual(len(slots), 967)
        self.assertEqual(assessments, old_assessments)
        self.assertTrue(all(slots[name] == meta for name, meta in old.items()))
        added = {name: meta for name, meta in slots.items() if name not in old}
        self.assertEqual(len(added), 192)
        self.assertTrue(all(meta["role"] == "editor" and 9 <= meta["turn"] <= 16 for meta in added.values()))
        self.assertEqual(accounting.POLICY["cell_http"], old_accounting.POLICY["cell_http"])
        self.assertEqual(accounting.POLICY["cell_http"], 96)
        self.assertEqual(4 * 96 + 4 * 73 + 99, 775)

    def test_old_inventory_is_insufficient_for_the_new_profile(self):
        old, _ = workflow.parent._plan_slots(self.study)
        with self.assertRaises(ContractError):
            accounting._slot_scope(old)

    def test_frozen_validator_does_not_silently_accept_the_new_inventory(self):
        slots, _ = workflow._plan_slots(self.study)
        with self.assertRaises(ContractError):
            old_accounting._slot_scope(slots)

    def test_extra_round_or_mismatched_turn_cannot_hide_in_extended_inventory(self):
        slots, _ = workflow._plan_slots(self.study)
        name = "p3a-01.adaptive.editor.inv1.a1.t16"
        bad = copy.deepcopy(slots)
        bad[name]["turn"] = 8
        with self.assertRaises(ContractError):
            accounting._slot_scope(bad)
        bad = copy.deepcopy(slots)
        bad[name[:-2] + "17"] = {**bad.pop(name), "turn": 17}
        with self.assertRaises(ContractError):
            accounting._slot_scope(bad)


if __name__ == "__main__":
    unittest.main()
