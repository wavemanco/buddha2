"""The operator command cannot overwrite old paths or export private bindings."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from followups.phase3a_compat_c1_v1 import verify


class VerifyTests(unittest.TestCase):
    def test_host_output_rejects_existing_foreign_parent_and_link_paths(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(verify, "ROOT", Path(temporary)):
            root = Path(temporary) / "runs/phase3a-compat-c1-v1"
            self.assertEqual(verify.host_output("runs/phase3a-compat-c1-v1/fresh"), root / "fresh")
            for value in ("../foreign", "old-evidence", str(root), str(root / "a/../b")):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    verify.host_output(value)
            (root / "existing").mkdir(parents=True)
            with self.assertRaises(ValueError):
                verify.host_output(str(root / "existing"))

    def test_export_omits_private_names_before_read_and_retains_public_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "trace.json").write_text('{"fixture":true}')
            (source / "credential-binding.json").write_text("must not inspect")
            (source / ".writer.lock").write_text("must not inspect")
            original = verify.shutil.copyfile
            def copy(src, dst):
                self.assertNotIn(src.name, {"credential-binding.json", ".writer.lock"})
                return original(src, dst)
            with patch.object(verify.shutil, "copyfile", copy):
                verify.export_demo(source, root / "export")
            self.assertEqual([p.name for p in (root / "export").iterdir()], ["trace.json"])


if __name__ == "__main__":
    unittest.main()
