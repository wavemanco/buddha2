"""One-off H1 v4 proof: rerun changed checks; bind unchanged v3 component evidence."""

import ast
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from followups.phase3a_history_compat_h1 import runtime, verify

OUT = Path(__file__).resolve().parent
V3 = ROOT / "runs/phase3a-history-compat-h1/verification-v3"
OLD = ROOT / "evidence/phase3a-history-compat-h1/unaccepted-v3/source"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_files():
    result, excluded, pending = {}, [], [V3]
    while pending:
        directory = pending.pop()
        for name in sorted(os.listdir(directory)):
            path = directory / name
            relative = path.relative_to(V3).as_posix()
            if name.casefold() in runtime.PRIVATE:
                excluded.append(relative)
                continue
            if "real-provider" in name.casefold() and any(k in name.casefold() for k in ("stdout", "stderr")):
                raise ValueError("real-provider stream is outside this synthetic evidence proof")
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("retained synthetic evidence contains a link")
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                result[relative] = sha(path)
            else:
                raise ValueError("retained synthetic evidence contains an unexpected type")
    return {"files": result, "excluded_private_names_before_metadata": excluded}


def main():
    assert sha(V3 / "summary.json") == "f7b24da3daeeb0da645e94483035447d658f8a747a5c4d0204919f5fe275aca8"
    old_map = json.loads((V3 / "source-before.json").read_text(encoding="utf-8"))
    assert len(old_map) == 10 and digest(old_map) == "9657015c38d4b6101bef2b1ece6ca39d9a30ebf70a7cd2fb9b4c14f624c166d6"
    assert old_map == json.loads((V3 / "source-after.json").read_text(encoding="utf-8"))
    assert all(sha(OLD / name) == value for name, value in old_map.items())
    before = verify.source()
    verify.save(OUT / "source-before.json", before)
    changed = sorted(name for name in old_map if before[name] != old_map[name])
    assert changed == ["followups/phase3a_history_compat_h1/tests.py", "followups/phase3a_history_compat_h1/verify.py"]
    assert before.keys() == old_map.keys()
    module = "followups/phase3a_history_compat_h1/verify.py"
    old_ast = ast.parse((OLD / module).read_text(encoding="utf-8"))
    new_ast = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    for tree in (old_ast, new_ast):
        tree.body = [node for node in tree.body if not (isinstance(node, ast.FunctionDef) and node.name == "preserved_r3")]
    assert ast.dump(old_ast) == ast.dump(new_ast)
    test_module = "followups/phase3a_history_compat_h1/tests.py"
    old_tests = ast.parse((OLD / test_module).read_text(encoding="utf-8"))
    new_tests = ast.parse((ROOT / test_module).read_text(encoding="utf-8"))
    old_history = next(node for node in old_tests.body if isinstance(node, ast.ClassDef) and node.name == "HistoryTests")
    new_history = next(node for node in new_tests.body if isinstance(node, ast.ClassDef) and node.name == "HistoryTests")
    assert ast.dump(old_history) == ast.dump(new_history)
    preservation_tests = next(node for node in new_tests.body if isinstance(node, ast.ClassDef) and node.name == "PreservationTests")
    assert len([node for node in preservation_tests.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]) == 2
    verify.save(OUT / "component-equality.json", {
        "unchanged_component_sources": {name: value for name, value in before.items() if name not in changed},
        "changed_sources": changed,
        "verify_ast_outside_preserved_r3_identical": True,
        "all_existing_history_test_asts_identical": True,
        "new_preservation_test_methods": 2,
        "v3_exact_source_snapshot_sha256": digest(old_map),
    })
    retained_before = evidence_files()
    verify.save(OUT / "reused-v3-evidence.json", retained_before)
    original_summary = json.loads((V3 / "summary.json").read_text(encoding="utf-8"))
    assert original_summary["H1_engineering_checks_passed"] and not original_summary["H1_complete"]
    checked_image = verify.command(["docker", "image", "inspect", "--format", "{{json .RootFS.Layers}}|{{.Id}}", IMAGE])
    verify.save(OUT / "fixed-image.json", checked_image)
    assert checked_image["exit_code"] == 0
    layers, image_id = checked_image["stdout"].strip().split("|")
    assert image_id == IMAGE
    assert json.loads(layers) == original_summary["runtime"]["fixed"]["layers"]
    verify.save(OUT / "r3-preservation-before.json", verify.preserved_r3())
    checks = {
        "ruff": ["-m", "ruff", "check", "--no-cache", "--config", "/workspace/pyproject.toml", "followups/phase3a_history_compat_h1"],
        "mypy": ["-m", "mypy", "--cache-dir", verify.MYPY_CACHE, "followups/phase3a_history_compat_h1"],
        "bandit": ["-m", "bandit", "-q", "-r", "followups/phase3a_history_compat_h1", "-x", "followups/phase3a_history_compat_h1/tests.py"],
        "unit": ["-m", "followups.phase3a_history_compat_h1.tests"],
    }
    for label, arguments in checks.items():
        result = verify.command(verify.docker(IMAGE) + arguments)
        verify.save(OUT / (label + ".json"), result)
        assert result["exit_code"] == 0, label
    verify.save(OUT / "r3-preservation-after.json", verify.preserved_r3())
    after = verify.source()
    verify.save(OUT / "source-after.json", after)
    assert before == after
    assert retained_before == evidence_files()
    verify.save(OUT / "summary.json", {
        "kind": "PRESERVATION AMENDMENT",
        "fixture": True,
        "provider_calls": 0,
        "api_spend": 0,
        "runtime_image": IMAGE,
        "proof_script_sha256": sha(Path(__file__)),
        "source_sha256": digest(before),
        "v3_summary_sha256": retained_before["files"]["summary.json"],
        "reused_evidence_manifest_sha256": sha(OUT / "reused-v3-evidence.json"),
        "reused": ["unchanged immutable derived image and baseline layers", "393039-entry private-first whole-runtime comparison", "actual installed SDK conversion/order/incomplete-stream probes", "all five native changed/KEEP/negative cases"],
        "rerun": ["Ruff", "Mypy", "Bandit", "all 8 unit methods including preservation tripwires", "authenticated 294-file R3 preservation before/after", "10-source before/after and exact v3 component/AST equality", "all retained v3 evidence hashes before/after"],
        "v3_source_preserved_and_v3_results_unmodified": True,
        "H1_engineering_checks_passed": True,
        "H1_complete": False,
        "independent_acceptance_required": True,
        "scientific_complete": False,
        "real_provider_signature_validation_tested": False,
        "paid_launcher_readiness_claimed": False,
    })
    print(json.dumps({"summary_sha256": sha(OUT / "summary.json"), "source_sha256": digest(before), "retained_v3_files": len(retained_before["files"])}))


if __name__ == "__main__":
    main()
