from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def build_report(texture_usage: dict, producer_pass: dict | None, consumer_pass: dict | None) -> str:
    data = texture_usage.get("data", {})
    producer = data.get("producer") or data.get("last_write")
    first_read = data.get("first_read")

    lines: list[str] = []
    lines.append(f"Resource: {data.get('rid', 'unknown')} {data.get('name', '')}".rstrip())
    lines.append(
        "Producer: {producer}".format(
            producer=producer.get("pass") if producer else "unknown",
        )
    )
    lines.append(
        "First consumer: {consumer}".format(
            consumer=first_read.get("pass") if first_read else "unknown",
        )
    )
    lines.append("")
    lines.append("Flow:")

    if producer:
        lines.append(
            "- write at eid={eid} usage={usage} pass={pass_name}".format(
                eid=producer.get("eid", "unknown"),
                usage=producer.get("usage", "unknown"),
                pass_name=producer.get("pass", "unknown"),
            )
        )
    if first_read:
        lines.append(
            "- first read at eid={eid} usage={usage} pass={pass_name}".format(
                eid=first_read.get("eid", "unknown"),
                usage=first_read.get("usage", "unknown"),
                pass_name=first_read.get("pass", "unknown"),
            )
        )

    for item in (data.get("items") or [])[:5]:
        lines.append(
            "- usage eid={eid} type={kind} usage={usage} name={name}".format(
                eid=item.get("eid", "unknown"),
                kind=item.get("type", "unknown"),
                usage=item.get("usage", "unknown"),
                name=item.get("name", ""),
            )
        )

    lines.append("")
    lines.append("Notes:")
    if producer_pass and producer_pass.get("data", {}).get("pass"):
        lines.append(
            "- producer pass packet available for `{}`".format(
                producer_pass["data"]["pass"].get("pass", "unknown")
            )
        )
    if consumer_pass and consumer_pass.get("data", {}).get("pass"):
        lines.append(
            "- consumer pass packet available for `{}`".format(
                consumer_pass["data"]["pass"].get("pass", "unknown")
            )
        )
    if not producer or not first_read:
        lines.append("- the observed chain is partial; inspect more packets before making stronger claims")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a markdown resource-flow report from observe packets.")
    parser.add_argument("--texture-usage", required=True)
    parser.add_argument("--producer-pass")
    parser.add_argument("--consumer-pass")
    parser.add_argument("--out")
    args = parser.parse_args()

    report = build_report(
        load_json(args.texture_usage) or {},
        load_json(args.producer_pass),
        load_json(args.consumer_pass),
    )

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
