"""Send a request to the qrenderdoc bridge extension via temp-file IPC."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import uuid


def _write_json_atomic(path: Path, payload: dict) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temp_path, path)


def main() -> int:
    if hasattr(os.sys.stdout, "reconfigure"):
        os.sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(os.sys.stderr, "reconfigure"):
        os.sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Send a request to the qrenderdoc bridge extension")
    parser.add_argument("method")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--params-file")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    if args.params_file:
        params = json.loads(Path(args.params_file).read_text(encoding="utf-8-sig"))
        params = params.get("params", params)
    else:
        params = json.loads(args.params)

    ipc = Path(tempfile.gettempdir()) / "renderdoc_mcp_bridge"
    req_dir = ipc / "requests"
    resp_dir = ipc / "responses"

    if not ipc.exists():
        raise SystemExit("Bridge IPC directory not found. Is qrenderdoc running with the extension loaded?")

    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    request_id = str(uuid.uuid4())
    req = req_dir / f"{request_id}.json"
    resp = resp_dir / f"{request_id}.json"
    _write_json_atomic(
        req,
        {
            "id": request_id,
            "method": args.method,
            "params": params,
        },
    )

    start = time.time()
    while time.time() - start < args.timeout:
        if resp.exists():
            data = json.loads(resp.read_text(encoding="utf-8"))
            print(json.dumps(data, ensure_ascii=False, indent=2))
            try:
                resp.unlink()
            except FileNotFoundError:
                pass
            return 0
        time.sleep(0.1)

    raise SystemExit("Timed out waiting for bridge response")


if __name__ == "__main__":
    raise SystemExit(main())
