"""Create a resumable, content-addressed RDC inventory without changing captures."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    previous = json.loads(args.output.read_text(encoding="utf-8-sig")) if args.output.exists() else {}
    cached = {entry["relative_path"]: entry for entry in previous.get("captures", [])}
    paths = sorted(root.rglob("*.rdc"), key=lambda path: path.relative_to(root).as_posix())
    records = []
    document = {"schema_version": 1, "root": str(root), "captures": records, "complete": False}
    for index, path in enumerate(paths, 1):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        old = cached.get(relative, {})
        record = {"relative_path": relative, "filename": path.name, "group": path.parent.name,
                  "path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                  "game_version": None, "version_evidence": [], "replay_status": "pending"}
        if old.get("sha256") and old.get("bytes") == stat.st_size and old.get("mtime_ns") == stat.st_mtime_ns:
            record.update(old)
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while block := stream.read(16 * 1024 * 1024):
                    digest.update(block)
            after = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError("Capture changed while hashing: " + str(path))
            record["sha256"] = digest.hexdigest()
        records.append(record)
        document["updated_at"] = datetime.now(timezone.utc).isoformat()
        document["count"] = len(records)
        document["total_bytes"] = sum(item["bytes"] for item in records)
        document["groups"] = dict(Counter(item["group"] for item in records))
        write_json(args.output, document)
        print("[{}/{}] {} {}".format(index, len(paths), relative, record["sha256"][:12]), flush=True)
    document["complete"] = True
    write_json(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
