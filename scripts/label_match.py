#!/usr/bin/env python3
"""Match wallet addresses against a local label sheet/file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import add_common_output_args, command_error, extract_addresses, label_hits, load_label_map, print_or_write


def build_markdown(result: dict) -> str:
    lines = ["# Label Match", ""]
    lines.append(f"Input addresses: {len(result['addresses'])}")
    lines.append(f"Matched addresses: {len(result['matches'])}")
    lines.append("")
    if result["matches"]:
        lines.append("| Address | Hits |")
        lines.append("|---|---:|")
        for address, hits in result["matches"].items():
            lines.append(f"| `{address}` | {len(hits)} |")
    else:
        lines.append("No label hits found.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Match addresses against xlsx/csv/json/txt label files.")
    parser.add_argument("addresses", nargs="*", help="Addresses to match")
    parser.add_argument("--addresses-file", help="File containing addresses or JSON/text with addresses")
    parser.add_argument("--label-file", required=True, help="Label file (.xlsx, .csv, .json, .txt)")
    parser.add_argument("--label-sheets", help="Comma-separated xlsx sheet names to read")
    add_common_output_args(parser)
    args = parser.parse_args()

    addresses = list(args.addresses)
    if args.addresses_file:
        text = Path(args.addresses_file).read_text(encoding="utf-8", errors="ignore")
        addresses.extend(extract_addresses(text))
    normalized = []
    seen = set()
    for address in addresses:
        key = address.lower() if address.startswith("0x") else address
        if key not in seen:
            seen.add(key)
            normalized.append(key if address.startswith("0x") else address)

    labels = load_label_map(args.label_file, args.label_sheets)
    matches = label_hits(normalized, labels)
    result = {
        "ok": True,
        "tool": "label_match",
        "addresses": normalized,
        "label_file": args.label_file,
        "label_sheets": args.label_sheets,
        "matches": matches,
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)

