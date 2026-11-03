"""Exercise the real retained-candidate packet guard without a completed gate."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[3]
SPEC = importlib.util.spec_from_file_location("r3_public_packet", ROOT / "evidence/phase3a-c1-completion-v4/package_public.py")
assert SPEC is not None and SPEC.loader is not None
packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packet)


class PacketTests(unittest.TestCase):
    def test_both_real_records_and_all_snapshots_are_verified_and_included(self):
        added: list[Path] = []
        records = packet.retained_candidates(added.append)
        self.assertEqual(set(records), {"v1", "v2"})
        self.assertEqual({version: len(record["snapshot_sha256"]) for version, record in records.items()},
                         {"v1": 1994, "v2": 1972})
        expected = {packet.EVIDENCE / f"unaccepted-candidate-{version}/candidate-rejection.json" for version in records}
        expected.update(ROOT.joinpath(*packet.relative(name).parts)
                        for record in records.values() for name in record["snapshot_sha256"])
        self.assertEqual(set(added), expected)

    def test_either_bad_record_or_missing_or_changed_snapshot_rejects(self):
        original = packet.file_hash
        for version in ("v1", "v2"):
            record_path = packet.EVIDENCE / f"unaccepted-candidate-{version}/candidate-rejection.json"
            record = packet.read(record_path)
            snapshot = ROOT.joinpath(*packet.relative(next(iter(record["snapshot_sha256"]))).parts)
            for case, target, error in (("record", record_path, ValueError),
                                        ("missing", snapshot, FileNotFoundError),
                                        ("changed", snapshot, ValueError)):
                def fault(path):
                    if path == target:
                        if case == "missing":
                            raise FileNotFoundError("synthetic missing retained snapshot")
                        return "0" * 64
                    return original(path)
                with self.subTest(version=version, case=case), patch.object(packet, "file_hash", side_effect=fault):
                    with self.assertRaises(error):
                        packet.retained_candidates(lambda _: None)
