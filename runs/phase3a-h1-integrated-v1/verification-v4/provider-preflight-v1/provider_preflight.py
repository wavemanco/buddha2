"""Keyless, artifact-only check of the accepted two-part packet and provider preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from contextlib import ExitStack
from pathlib import Path, PurePosixPath
from unittest.mock import patch

PREFIX = "phase3a-h1-integrated-v1"
ROOT = Path(r"C:\Users\arvik\code\research\Buddha2") if os.name == "nt" else Path("/workspace")
REL = "runs/" + PREFIX + "/verification-v4/provider-preflight-v1"
HERE = ROOT / REL
RELEASE = "runs/" + PREFIX + "/verification-v4/release/"
EVIDENCE = "evidence/" + PREFIX + "/"
RECEIPT_SHA = "31fdee4427f4e4609b82209d9d312201004fba019e32d13c68d27a235b47e32c"
IMAGE = "sha256:ce1d4ab2241ce9d141a5447c3da15fb44f62e521c3e2bbe49b74611ff36e3800"
BINDINGS = ("study_sha256", "source_sha256", "runtime_sha256", "policy_sha256", "launcher_sha256")
PRIVATE = {"credential-binding.json", ".writer.lock", ".env", "auth.json", "credentials.json"}
LAUNCHER_NAMES = {"914e776894424e8facaf3cb83892dcb1.inspection.json",
                  "b632ad38f5064312994ec4bb047ba76f.inspection.json",
                  "b632ad38f5064312994ec4bb047ba76f.result.json"}
COUNTS = {"sdk": 0, "socket": 0, "subprocess": 0}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def safe(relative: str) -> Path:
    name = PurePosixPath(relative)
    require(not name.is_absolute() and name.as_posix() == relative and ":" not in relative and "\\" not in relative
            and all(p not in {".", ".."} and p.casefold() not in PRIVATE
                    and "stdout" not in p.casefold() and "stderr" not in p.casefold() for p in name.parts),
            "private, stream or escaped preflight path")
    current = ROOT
    for part in name.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            break
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "linked preflight path")
    return ROOT / relative


def sha(relative: str) -> str:
    digest = hashlib.sha256()
    with safe(relative).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(relative: str) -> dict:
    value = json.loads(safe(relative).read_bytes())
    require(isinstance(value, dict), "preflight input must be an object")
    return value


def save(target: Path, value: dict) -> None:
    require(target.is_relative_to(HERE) or (os.name != "nt" and target.is_relative_to(Path("/results") / PREFIX)),
            "foreign preflight output")
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def bootstrap() -> None:
    paths = (ROOT / "src", ROOT / ".upstream/harness2", ROOT)
    sys.path[:0] = list(map(str, paths))
    sys.dont_write_bytecode = True
    require(Path(__file__) == HERE / "provider_preflight.py", "preflight helper moved")
    if os.name == "nt":
        require(Path.cwd() == ROOT, "wrong new-project working directory")
        os.environ["PYTHONPATH"] = os.pathsep.join(map(str, paths))
        os.environ["BUDDHA2_OUTPUT_ROOT"] = str(ROOT / "runs")


def bundle() -> dict:
    receipt_name = EVIDENCE + "packet-acceptance.json"
    require(sha(receipt_name) == RECEIPT_SHA, "external independent packet receipt changed")
    receipt = read(receipt_name)
    study = read(RELEASE + "study.json")
    require(receipt.get("passed") is True and receipt.get("bundle_complete") is True
            and receipt.get("bundle_kind") == "p3a-hi-main-plus-launcher-evidence-v1"
            and receipt.get("main_archive_independently_sufficient") is False
            and receipt.get("all_bundle_CRCs_SHA256_and_current_bytes_verified") is True
            and receipt.get("bundle_members_verified") == 8228 and receipt.get("canonical_source_files_verified") == 356
            and all(receipt.get(k) == study[k] for k in BINDINGS), "complete source-bound two-part acceptance required")
    expected = {
        EVIDENCE + "offline-kit-v1.zip": receipt["archive_sha256"],
        EVIDENCE + "offline-kit-v1.manifest.json": receipt["manifest_sha256"],
        EVIDENCE + "offline-kit-v1-launcher-evidence.zip": receipt["companion_archive_sha256"],
        EVIDENCE + "offline-kit-v1-launcher-evidence.manifest.json": receipt["companion_manifest_sha256"],
        "runs/" + PREFIX + "/verification-v4/retained-launcher-evidence/map.json": receipt["companion_map_sha256"],
        RELEASE + "offline-gate.json": receipt["offline_gate_file_sha256"],
    }
    require(receipt["archive"] == EVIDENCE + "offline-kit-v1.zip"
            and receipt["companion_archive"] == EVIDENCE + "offline-kit-v1-launcher-evidence.zip"
            and receipt["companion_manifest"] == EVIDENCE + "offline-kit-v1-launcher-evidence.manifest.json"
            and receipt["companion_map"] == "runs/" + PREFIX + "/verification-v4/retained-launcher-evidence/map.json",
            "receipt references foreign bundle paths")
    main = read(EVIDENCE + "offline-kit-v1.manifest.json")
    for name in (RELEASE + "study.json", RELEASE + "live-grant.json", EVIDENCE + "independent-acceptance.json"):
        expected[name] = main["member_sha256"][name]
    mapping = read(receipt["companion_map"])
    require(len(mapping["entries"]) == 3 and {Path(row["original"]).name for row in mapping["entries"]} == LAUNCHER_NAMES,
            "launcher supplemental map differs")
    for row in mapping["entries"]:
        name = Path(row["original"]).name
        require(row["original"] == "runs/" + PREFIX + "/launcher/" + name
                and row["copy"] == "runs/" + PREFIX + "/verification-v4/retained-launcher-evidence/" + name,
                "launcher map escaped explicit three public artifacts")
        expected[row["original"]] = expected[row["copy"]] = row["sha256"]
    require(all(sha(name) == expected_sha for name, expected_sha in expected.items()), "accepted bundle/public evidence changed")
    return {"packet_acceptance_sha256": RECEIPT_SHA, "files": expected,
            **{k: study[k] for k in BINDINGS}}


def activity(event: str, args: tuple) -> None:
    if event.startswith("socket.") and event in {"socket.__new__", "socket.connect", "socket.getaddrinfo"}:
        COUNTS["socket"] += 1
        raise RuntimeError("keyless preflight cannot use sockets")
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.exec", "os.spawn"}:
        COUNTS["subprocess"] += 1
        raise RuntimeError("keyless preflight cannot start subprocesses")


def deny_sdk(*args, **kwargs):
    COUNTS["sdk"] += 1
    raise RuntimeError("keyless preflight cannot construct provider clients")


def inside(output: Path) -> int:
    require(output == Path("/results") / PREFIX / "verification-v4/provider-preflight-v1/actual-v1",
            "foreign inside preflight output")
    sys.addaudithook(activity)
    with ExitStack() as blocks:
        for target in ("anthropic.Anthropic", "anthropic.AsyncAnthropic", "openai.OpenAI", "openai.AsyncOpenAI"):
            blocks.enter_context(patch(target, side_effect=deny_sdk))
        from followups.phase3a_h1_integrated_v1 import launch, support
        require({p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}, "actual network-none required")
        before, source = bundle(), support.source_identity()
        study = read(RELEASE + "study.json")
        require(source == study["source"] and len(source["files"]) == 356, "current source differs from accepted356")
        claim = Path("/results") / PREFIX / "live-study.json"
        claim_before = claim.read_bytes() if claim.exists() else None
        checked = launch.preflight(Path("/results") / PREFIX / "verification-v4/release/study.json",
            Path("/results") / PREFIX / "verification-v4/release/live-grant.json", "all", "provider")
        require(checked["mode"] == "provider" and checked["fixture"] is False
                and checked["credentials_read"] is False and checked["credential_access"] is False
                and checked["provider_requests"] == 0 and checked["provider_calls"] == 0
                and checked["accepted_packet"]["packet_acceptance_sha256"] == RECEIPT_SHA
                and all(checked[k] == before[k] for k in BINDINGS), "provider preflight changed authority or attempted activity")
        require(bundle() == before and support.source_identity() == source
                and (claim.read_bytes() if claim.exists() else None) == claim_before
                and not any(COUNTS.values()), "preflight mutated bundle/source/claim or attempted execution")
        save(output / "preflight.json", {"kind": "phase3a-hi-keyless-provider-preflight-v1", "passed": True,
            **before, "actual_image": IMAGE, "checked": checked, "activity_attempts": COUNTS,
            "provider_calls": 0, "credentials_read": False, "global_claim_published": False,
            "source_and_bundle_unchanged": True, "SDK_socket_subprocess_blocks_installed": True})
    return 0


def host() -> int:
    from followups.phase3a_h1_integrated_v1 import support, verify
    before, source = bundle(), support.source_identity()
    require(source == read(RELEASE + "study.json")["source"], "host current356 source mismatch")
    output = safe(REL + "/actual-v1")
    output.mkdir(exist_ok=False)
    args = verify.container_args(ROOT / ("runs/" + PREFIX + "/verification-v4"), mode="inside")
    args[args.index(IMAGE) + 1:] = ["-B", str(Path("/workspace") / REL / "provider_preflight.py"), "--inside"]
    created = verify.execute(args, timeout=60)
    owner = created["stdout"].strip()
    require(created["exit_code"] == 0 and re.fullmatch(r"[0-9a-f]{64}", owner) is not None,
            "keyless preflight has no exact owned Docker ID")
    try:
        save(output / "create.json", created)
        inspected = verify.execute(["docker", "inspect", owner], timeout=60)
        require(inspected["exit_code"] == 0, "owned preflight inspection failed")
        actual = json.loads(inspected["stdout"])[0]
        mounts = {(m["Source"], m["Destination"], m["RW"]) for m in actual["Mounts"]}
        environment = dict(v.split("=", 1) for v in actual["Config"]["Env"])
        require(actual["Image"] == IMAGE and actual["HostConfig"]["NetworkMode"] == "none"
                and actual["HostConfig"]["ReadonlyRootfs"] is True and mounts == {
                    (str(ROOT), "/workspace", False), (str(ROOT / "runs" / PREFIX), "/results/" + PREFIX, True)},
                "actual keyless preflight image/isolation differs")
        require(all(environment.get(k) == v for k, v in {
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "/workspace/src:/workspace/.upstream/harness2:/workspace",
            "BUDDHA2_OUTPUT_ROOT": "/results", "BUDDHA2_IMAGE_ID": IMAGE, "BUDDHA2_OFFLINE": "1",
            "PHASE3A_OPENCODE": "/opt/phase3a-opencode", "PHASE3A_BUN": "/usr/local/bin/bun"}.items())
            and not any(k.endswith("_API_KEY") for k in environment), "actual keyless runtime environment differs")
        save(output / "actual-container.json", {"image": actual["Image"], "network": "none", "mounts": actual["Mounts"],
             "read_only_rootfs": True, "container_id": owner, "environment_names": [v.split("=", 1)[0] for v in actual["Config"]["Env"]]})
        execution = verify.execute(["docker", "start", "--attach", owner], timeout=600)
        save(output / "execution.json", execution)
        require(execution["exit_code"] == 0, "actual keyless provider preflight failed")
        proof = json.loads((output / "preflight.json").read_bytes())
        require(proof.get("passed") is True and proof.get("packet_acceptance_sha256") == RECEIPT_SHA
                and not any(proof["activity_attempts"].values()), "no valid keyless preflight proof")
    finally:
        terminal = verify.execute(["docker", "inspect", "--format", "{{.State.Running}}", owner], timeout=30)
        save(output / "terminal.json", terminal)
        if terminal["exit_code"] != 0 or terminal["stdout"].strip() != "false":
            save(output / "stop.json", verify.execute(["docker", "stop", "--time", "10", owner], timeout=30))
        removed = verify.execute(["docker", "rm", owner], timeout=30)
        save(output / "remove.json", removed)
        require(removed["exit_code"] == 0, "owned preflight cleanup is unproved")
    require(bundle() == before and support.source_identity() == source, "source/bundle changed during actual preflight")
    save(output / "completion.json", {"kind": "phase3a-hi-keyless-preflight-completion-v1", "passed": True,
        **before, "provider_calls": 0, "credentials_read": False, "owned_cleanup_verified": True,
        "source_and_bundle_unchanged": True, "helper_sha256": sha(REL + "/provider_preflight.py")})
    print("Accepted full bundle and unchanged provider preflight passed without keys or calls; owned container removed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inside", action="store_true")
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--host", action="store_true")
    args = parser.parse_args()
    bootstrap()
    if args.inside:
        return inside(Path("/results") / PREFIX / "verification-v4/provider-preflight-v1/actual-v1")
    require(os.name == "nt", "host command requires the existing Windows/Docker installation")
    if args.check_only:
        from followups.phase3a_h1_integrated_v1 import support
        proof, source = bundle(), support.source_identity()
        require(source == read(RELEASE + "study.json")["source"], "host current356 source mismatch")
        save(HERE / "bundle-check-v1.json", {"passed": True, **proof, "source_files_verified": len(source["files"]),
            "helper_sha256": sha(REL + "/provider_preflight.py"), "provider_calls": 0, "container_started": False})
        return 0
    return host()


if __name__ == "__main__":
    raise SystemExit(main())
