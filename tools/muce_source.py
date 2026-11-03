"""Convert only the pinned MuCE train Parquet using an existing host PyArrow reader.

This setup utility does not install a reader, fetch data, select pairs, or call models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def confined(path: Path, root: Path) -> Path:
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
            raise ValueError("linked setup paths are not supported")
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("setup reads and writes must stay inside the new project")
    return resolved


def publish(path: Path, raw: bytes) -> None:
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"refuse replacement of different setup evidence: {path.name}")
        return
    with path.open("xb") as stream:
        stream.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    expected = Path(r"C:\Users\arvik\code\research\Buddha2")
    if project != expected.resolve() or Path.cwd().resolve() != project:
        raise ValueError("run this setup helper only from the new Windows project root")
    source, output = confined(args.source, project), confined(args.output, project)
    sys.path.insert(0, str(project / "src"))
    from buddha2.muce import (
        SOURCE,
        SOURCE_JSONL_SHA256,
        SOURCE_PARQUET_SHA256,
        SOURCE_ROWS,
        SOURCE_SCHEMA,
    )

    try:
        import pyarrow
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ValueError("existing setup PyArrow 24.0.0 reader is required; no automatic installation") from exc
    if pyarrow.__version__ != "24.0.0":
        raise ValueError("reader version differs from the recorded setup reader PyArrow 24.0.0")
    if source.stat().st_size > 2_000_000 or sha256(source.read_bytes()) != SOURCE_PARQUET_SHA256:
        raise ValueError("source is not the frozen MuCE full_agreement/train Parquet")
    schema = pq.read_schema(source)
    fields = {name: str(dtype) for name, dtype in zip(schema.names, schema.types)}
    if fields != SOURCE_SCHEMA:
        raise ValueError("source schema differs from the pinned train schema")
    rows = pq.read_table(source).to_pylist()
    if len(rows) != SOURCE_ROWS:
        raise ValueError("source row count differs from the pinned train count")
    for row in rows:
        for name, field_type in SOURCE_SCHEMA.items():
            value = row[name]
            if name == "FullPrompt" and value is None:
                continue
            if (field_type == "string" and not isinstance(value, str)) or (field_type == "double" and type(value) is not float):
                raise ValueError("source field type was not preserved")
    records = [canonical(row) for row in rows]
    textual = [canonical({key: value for key, value in row.items() if key != "facsco_grm_scaled"}) for row in rows]
    if len(set(records)) != len(rows) or len(set(textual)) != len(rows):
        raise ValueError("duplicate or conflicting full source identity")
    blob = b"".join(record + b"\n" for record in records)
    if sha256(blob) != SOURCE_JSONL_SHA256 or [json.loads(line) for line in blob.splitlines()] != rows:
        raise ValueError("conversion differs from the frozen canonical source or original records")
    output.mkdir(parents=True, exist_ok=True)
    name = "muce-full_agreement-train.canonical.jsonl"
    publish(output / name, blob)
    metadata = {
        "schema_version": 1, "status": "conversion_only_no_selection", **SOURCE,
        "source_url": f"https://huggingface.co/datasets/{SOURCE['dataset']}/resolve/{SOURCE['revision']}/full_agreement/train-00000-of-00001.parquet",
        "source_sha256": SOURCE_PARQUET_SHA256, "source_rows": len(rows),
        "source_bytes": source.stat().st_size, "source_schema": fields,
        "converted_name": name, "converted_sha256": sha256(blob), "converted_rows": len(rows), "converted_bytes": len(blob),
        "method": "PyArrow read_table.to_pylist; all original fields and row order; UTF-8 canonical sorted compact JSON per row plus LF; no normalization, filtering, rescaling, pairing or selection.",
        "environment": {"python": sys.version.split()[0], "pyarrow": pyarrow.__version__, "platform": platform.platform(), "additional_installs": 0},
        "identity": {"original_ID_preserved": True, "source_ordinal": "Zero-based JSONL ordinal equals original Parquet row ordinal.", "unique_canonical_full_rows": len(set(records)), "unique_textual_source_rows_excluding_score": len(set(textual)), "same_textual_source_identity_conflicting_score_count": 0},
        "converter_name": Path(__file__).name, "converter_sha256": sha256(Path(__file__).read_bytes()),
        "roundtrip_all_original_records_equal": True, "opened_data_splits": ["train"], "model_requests": 0, "selected_pairs": 0,
    }
    publish(output / "conversion.json", json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n")
    print(json.dumps({"source_rows": len(rows), "converted_sha256": sha256(blob), "model_requests": 0, "selected_pairs": 0}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Source preparation refused: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
