"""Send a request to the qrenderdoc bridge extension via temp-file IPC."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import uuid


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a request to the qrenderdoc bridge extension")
    parser.add_argument("method")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--params-file")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    if args.params_file:
        params = json.loads(Path(args.params_file).read_text(encoding="utf-8"))
        params = params.get("params", params)
    else:
        params = json.loads(args.params)

    ipc = Path(tempfile.gettempdir()) / "renderdoc_mcp_bridge"
    req = ipc / "request.json"
    resp = ipc / "response.json"
    lock = ipc / "lock"

    if not ipc.exists():
        raise SystemExit("Bridge IPC directory not found. Is qrenderdoc running with the extension loaded?")

    if resp.exists():
        resp.unlink()

    lock.write_text("lock", encoding="utf-8")
    req.write_text(
        json.dumps(
            {
                "id": str(uuid.uuid4()),
                "method": args.method,
                "params": params,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lock.unlink()

    start = time.time()
    while time.time() - start < args.timeout:
        if resp.exists():
            data = json.loads(resp.read_text(encoding="utf-8"))
            print(json.dumps(data, ensure_ascii=False, indent=2))
            resp.unlink()
            return 0
        time.sleep(0.1)

    raise SystemExit("Timed out waiting for bridge response")


if __name__ == "__main__":
    raise SystemExit(main())
