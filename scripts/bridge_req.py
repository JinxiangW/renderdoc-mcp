"""Send a request to the qrenderdoc bridge extension."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_src_on_path() -> None:
    src = _repo_root() / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    _configure_stdio()
    _ensure_src_on_path()

    from renderdoc_mcp.integration import LiveBridgeClient, LiveBridgeError

    parser = argparse.ArgumentParser(description="Send a request to the qrenderdoc bridge extension")
    parser.add_argument("method")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--params-file")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--window-id",
        default=os.environ.get("RENDERDOC_MCP_WINDOW_ID") or os.environ.get("RENDERDOC_MCP_BRIDGE_ID"),
        help="Target qrenderdoc bridge window_id. Defaults to RENDERDOC_MCP_WINDOW_ID.",
    )
    args = parser.parse_args()

    if args.params_file:
        params = json.loads(Path(args.params_file).read_text(encoding="utf-8-sig"))
        params = params.get("params", params)
    else:
        params = json.loads(args.params)

    request_id = str(uuid.uuid4())
    client = LiveBridgeClient(timeout=args.timeout)

    try:
        if args.method == "list_live_windows":
            result = client.list_windows()
        else:
            result = client.call(args.method, params, window_id=args.window_id)
        payload = {"id": request_id, "result": result}
        exit_code = 0
    except LiveBridgeError as exc:
        payload = {
            "id": request_id,
            "error": {
                "code": "bridge_error",
                "message": str(exc),
            },
        }
        exit_code = 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
