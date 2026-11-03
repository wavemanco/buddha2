"""Build an isolated Inspect core image after reviewing exact wheel licenses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404
import zipfile
from pathlib import Path

from .paths import checked_path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "python:3.12-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0"
INSPECT_WHEEL = "f11c2afed84026507d902bbcc68e7a8ee95e8070786ba2914c880761e97a220f"
IMAGE = "buddha2-inspect-i1:0.3.286"


def save(path: Path, data: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def command(args: list[str], output: Path) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # nosec B603
    save(output, {"args": args, "exit_code": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(f"command failed; see {output}")


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reuse-reviewed", help="retained complete wheel download from a failed pre-install setup")
    args = parser.parse_args()
    expected = ROOT / "runs" / "inspect-visibility-i1"
    out = checked_path(args.output, expected, missing=True)
    if out.exists():
        raise ValueError("setup requires a new root under runs/inspect-visibility-i1")
    # The only setup bind is this fresh empty directory; no project or credentials mount.
    out.mkdir(parents=True)
    mount = ["--mount", f"type=bind,source={out},target=/setup"]
    common = ["docker", "run", "--rm", "--cap-drop", "ALL", "--security-opt",
              "no-new-privileges", *mount, "--workdir", "/setup", BASE, "python", "-m", "pip"]
    if args.reuse_reviewed:
        old = checked_path(args.reuse_reviewed, expected)
        manifest = json.loads((old / "wheel-manifest.json").read_bytes())
        for entry in manifest:
            wheel = checked_path(old / "wheels" / entry["filename"], expected)
            if hashlib.sha256(wheel.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("retained reviewed wheel changed")
        shutil.copyfile(old / "resolution.json", out / "resolution.json")
        shutil.copytree(old / "wheels", out / "wheels")
        save(out / "retained-wheel-reuse.json", {"from": str(old), "all_hashes_verified": True})
    else:
        command(common + ["install", "--dry-run", "--ignore-installed", "--only-binary=:all:",
                          "--report", "/setup/resolution.json", "inspect-ai==0.3.286"], out / "resolve-command.json")
    report = json.loads((out / "resolution.json").read_bytes())
    expected_wheels = {
        item["metadata"]["name"].lower().replace("_", "-"):
        item["download_info"]["archive_info"]["hashes"]["sha256"]
        for item in report["install"]
    }
    decisions = []
    pins = []
    for item in report["install"]:
        meta = item["metadata"]
        name, version = meta["name"], meta["version"]
        declared = str(meta.get("license_expression") or meta.get("license") or "")
        classifiers = [v for v in meta.get("classifier", []) if v.startswith("License ::")]
        text = declared + " " + " ".join(classifiers)
        # MPL certifi is covered by the recorded unmodified local-use decision in DECISIONS.
        normalized = name.lower().replace("_", "-")
        covered_mpl = normalized == "certifi" and ("MPL" in text or "Mozilla" in text)
        copyleft = bool(re.search(r"(?i)(?<![A-Z])(AGPL|LGPL|GPL|MPL|Mozilla|GNU)(?![A-Z])", text))
        permissive = bool(re.search(r"(?i)MIT|BSD|Apache|ISC|Python|PSF|Unlicense|public domain|Zlib|Artistic", text))
        acp_review = normalized == "agent-client-protocol" and version == "0.12.1"
        accepted = covered_mpl or acp_review or (permissive and not copyleft)
        decisions.append({"name": name, "version": version, "declared_license": declared,
                          "classifiers": classifiers, "accepted_before_install": accepted,
                          "decision": "existing unmodified local-use MPL certifi decision" if covered_mpl else "explicit Apache-2.0 upstream LICENSE review https://github.com/agentclientprotocol/python-sdk/blob/main/LICENSE; exact wheel notice required" if acp_review else "permissive declared license" if accepted else "manual review required"})
        pins.append(f"{name}=={version}")
    save(out / "license-review.json", {"packages": decisions, "all_accepted": all(d["accepted_before_install"] for d in decisions)})
    if not all(d["accepted_before_install"] for d in decisions):
        raise RuntimeError("additional or unclassified license; inspect license-review before enabling")
    (out / "pins.txt").write_text("\n".join(sorted(pins)) + "\n", encoding="utf-8")
    if not args.reuse_reviewed:
        command(common + ["download", "--only-binary=:all:", "--no-deps", "--dest", "/setup/wheels", "-r", "/setup/pins.txt"], out / "download-command.json")
    wheels = []
    locks = []
    for path in sorted((out / "wheels").iterdir()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with zipfile.ZipFile(path) as archive:
            metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = archive.read(metadata_name).decode("utf-8")
            name_match = re.search(r"(?m)^Name: (.+)$", metadata)
            version_match = re.search(r"(?m)^Version: (.+)$", metadata)
            if name_match is None or version_match is None:
                raise ValueError("wheel lacks required name/version metadata")
            name, version = name_match.group(1).strip(), version_match.group(1).strip()
            notices = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()
                       if ".dist-info/" in n and re.search(r"(?i)licen[sc]e|notice|copying", n)}
            if name.lower().replace("_", "-") == "agent-client-protocol":
                exact_notices = [archive.read(n).decode("utf-8") for n in notices]
                if not any("Apache License" in notice and "Version 2.0" in notice for notice in exact_notices):
                    raise ValueError("ACP exact wheel does not confirm reviewed Apache-2.0 license")
        if name.lower().replace("_", "-") == "inspect-ai" and digest != INSPECT_WHEEL:
            raise ValueError("Inspect wheel differs from independently verified PyPI digest")
        if expected_wheels.get(name.lower().replace("_", "-")) != digest:
            raise ValueError("wheel differs from resolver's package-registry hash")
        locks.append(f"{name}=={version} --hash=sha256:{digest}")
        wheels.append({"filename": path.name, "sha256": digest, "name": name, "version": version, "retained_notice_hashes": notices})
    save(out / "wheel-manifest.json", wheels)
    if len(wheels) != len(expected_wheels):
        raise ValueError("wheel closure does not match exact resolved package count")
    (out / "requirements.lock").write_text("\n".join(sorted(locks)) + "\n", encoding="utf-8")
    command(["docker", "build", "--platform", "linux/amd64", "-t", IMAGE, "-f", str(HERE / "Dockerfile"), str(out)], out / "build-command.json")
    command(["docker", "image", "inspect", IMAGE], out / "image-inspect.json")
    command(["docker", "run", "--rm", "--network", "none", "--read-only", IMAGE, "cat", "/installed.txt"], out / "installed.json")
    print(out)


if __name__ == "__main__":
    main()
