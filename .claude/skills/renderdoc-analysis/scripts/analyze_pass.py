from __future__ import annotations

import argparse
import json
from pathlib import Path

from pass_analysis import analyze_pass, load_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a pass from observe-layer packet files.")
    parser.add_argument("--pass-packet", required=True)
    parser.add_argument("--pipeline-state")
    parser.add_argument("--shader")
    parser.add_argument("--shader-disasm")
    parser.add_argument("--texture-usage", action="append", default=[])
    parser.add_argument("--consumer-shader-evidence", action="append", default=[])
    parser.add_argument("--visual-validation")
    parser.add_argument("--out")
    args = parser.parse_args()

    texture_usages = [load_json(path) or {} for path in args.texture_usage]
    consumer_shader_evidence = [load_json(path) or {} for path in args.consumer_shader_evidence]
    result = analyze_pass(
        load_json(args.pass_packet) or {},
        load_json(args.pipeline_state),
        load_json(args.shader),
        load_json(args.shader_disasm),
        texture_usages,
        consumer_shader_evidence,
        load_json(args.visual_validation),
    )

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
