#!/usr/bin/env python3
"""Compute Solana mint launch top participants from indexed token transfers."""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from typing import Any

from common import (
    add_common_output_args,
    amount_from_raw,
    command_error,
    format_time,
    label_hits,
    load_label_map,
    parse_time,
    pick,
    print_or_write,
    shorten,
    solscan_json,
    unwrap_items,
    unwrap_object,
)


def token_meta(mint: str) -> dict[str, Any]:
    for path, params in (
        ("token/meta", {"address": mint}),
        ("token/meta", {"token": mint}),
    ):
        try:
            return unwrap_object(solscan_json(path, params=params))
        except Exception:
            continue
    return {}


def infer_creation_time(mint: str) -> int | None:
    meta = token_meta(mint)
    for key in ("created_time", "first_mint_time", "createdTime", "firstMintTime", "creation_time", "block_time", "time"):
        value = meta.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def fetch_token_transfers(mint: str, start: int, end: int, max_pages: int, page_size: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # Solscan Pro has used both token/transfer and token/transfer?address=<mint>
    # forms across docs/versions; keep the path centralized so failures are explicit.
    for page in range(1, max_pages + 1):
        params = {
            "address": mint,
            "page": page,
            "page_size": page_size,
            "from_time": start,
            "to_time": end,
            "sort_by": "block_time",
            "sort_order": "asc",
            "exclude_amount_zero": "true",
        }
        response = solscan_json("token/transfer", params=params)
        items = unwrap_items(response)
        if not items:
            break
        out.extend(items)
        if len(items) < page_size:
            break
    return out


def normalize_transfer(item: dict[str, Any], mint: str) -> dict[str, Any]:
    ts = pick(item, "block_time", "blockTime", "time")
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        ts_int = None
    decimals = pick(item, "token_decimals", "decimals", "decimal", default=0)
    raw_amount = pick(item, "amount", "value", "change_amount", default=0)
    amount = amount_from_raw(raw_amount, decimals)
    # If Solscan already returns UI amount, prefer it when raw/decimals looks absent.
    ui_amount = pick(item, "ui_amount", "uiAmount", "amount_ui", "amountUi")
    if ui_amount is not None:
        try:
            amount = float(ui_amount)
        except (TypeError, ValueError):
            pass
    from_owner = pick(item, "from_owner", "fromOwner", "source_owner", "owner_from")
    to_owner = pick(item, "to_owner", "toOwner", "destination_owner", "owner_to")
    from_addr = from_owner or pick(item, "from_address", "from", "src", "source")
    to_addr = to_owner or pick(item, "to_address", "to", "dst", "destination")
    return {
        "signature": pick(item, "trans_id", "tx_hash", "signature", "hash"),
        "block_time": ts_int,
        "time": format_time(ts_int) if ts_int else None,
        "from": from_addr,
        "to": to_addr,
        "from_raw": pick(item, "from_address", "from", "src", "source"),
        "to_raw": pick(item, "to_address", "to", "dst", "destination"),
        "mint": pick(item, "token_address", "mint", "token", default=mint),
        "amount": amount,
        "raw_amount": raw_amount,
        "decimals": decimals,
        "raw": item,
    }


def rank_participants(transfers: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"in": 0.0, "out": 0.0, "gross": 0.0, "txs": 0, "first_time": None, "last_time": None, "first_signature": None})
    for tx in transfers:
        amount = float(tx.get("amount") or 0)
        ts = tx.get("block_time")
        for side, sign in (("from", -1), ("to", 1)):
            address = tx.get(side)
            if not address:
                continue
            item = stats[address]
            if sign > 0:
                item["in"] += amount
                item["gross"] += amount
            else:
                item["out"] += amount
            item["txs"] += 1
            if ts is not None and (item["first_time"] is None or ts < item["first_time"]):
                item["first_time"] = ts
                item["first_signature"] = tx.get("signature")
            if ts is not None and (item["last_time"] is None or ts > item["last_time"]):
                item["last_time"] = ts
    ranked = []
    for address, item in stats.items():
        net = item["in"] - item["out"]
        rank_value = item["gross"] if metric == "top_gross_buy_volume" else net
        if rank_value <= 0:
            continue
        ranked.append(
            {
                "address": address,
                "rank_value": rank_value,
                "token_in": item["in"],
                "token_out": item["out"],
                "token_net": net,
                "tx_count": item["txs"],
                "first_time": item["first_time"],
                "first_time_text": format_time(item["first_time"]),
                "last_time": item["last_time"],
                "last_time_text": format_time(item["last_time"]),
                "first_signature": item["first_signature"],
            }
        )
    ranked.sort(key=lambda x: x["rank_value"], reverse=True)
    return ranked


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# Solana Mint Top Participants", ""]
    lines.append(f"- Mint: `{result['mint']}`")
    lines.append(f"- Window: `{result['window']['from_time']}` to `{result['window']['to_time']}`")
    lines.append(f"- Metric: `{result['metric']}`")
    lines.append(f"- Transfers indexed: {result['summary']['transfer_count']}")
    lines.append(f"- Participants ranked: {result['summary']['participant_count']}")
    lines.append("")
    lines.append("| Rank | Wallet | Rank Value | In | Out | First Seen | Label Hits |")
    lines.append("|---:|---|---:|---:|---:|---|---:|")
    for idx, row in enumerate(result["top"], start=1):
        hits = len(result["label_hits"].get(row["address"], []))
        lines.append(f"| {idx} | `{shorten(row['address'])}` | {row['rank_value']:.6f} | {row['token_in']:.6f} | {row['token_out']:.6f} | {row.get('first_time_text')} | {hits} |")
    if result["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute top Solana mint participants during a launch window.")
    parser.add_argument("--mint", required=True)
    parser.add_argument("--from-time", help="Window start. If omitted, infer mint creation time from Solscan token metadata.")
    parser.add_argument("--to-time", help="Window end. If omitted, use --hours-after-create from start.")
    parser.add_argument("--hours-after-create", type=float, default=3.0)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--metric", choices=["top_net_buyers", "top_gross_buy_volume"], default="top_net_buyers")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    add_common_output_args(parser)
    args = parser.parse_args()

    warnings: list[str] = []
    if not os.getenv("SOLSCAN_API_KEY"):
        raise RuntimeError("Missing SOLSCAN_API_KEY. Mint participant analysis requires Solscan Pro indexed token transfers.")
    start = parse_time(args.from_time, args.timezone) if args.from_time else infer_creation_time(args.mint)
    if start is None:
        raise RuntimeError("Could not infer mint creation time. Provide --from-time or a mint creation tx/window.")
    end = parse_time(args.to_time, args.timezone) if args.to_time else int(start + args.hours_after_create * 3600)

    raw_transfers = fetch_token_transfers(args.mint, start, end, args.max_pages, args.page_size)
    transfers = [normalize_transfer(item, args.mint) for item in raw_transfers]
    if len(raw_transfers) >= args.max_pages * args.page_size:
        warnings.append("Transfer results reached max page limit; increase --max-pages for full coverage.")
    ranked = rank_participants(transfers, args.metric)
    top = ranked[: args.top]
    labels = label_hits([row["address"] for row in top], load_label_map(args.label_file, args.label_sheets))
    result = {
        "ok": True,
        "tool": "trace_solana_mint_participants",
        "mint": args.mint,
        "metric": args.metric,
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "summary": {"transfer_count": len(transfers), "participant_count": len(ranked), "top_count": len(top)},
        "top": top,
        "label_hits": labels,
        "warnings": warnings,
        "transfers_sample": transfers[:50],
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
