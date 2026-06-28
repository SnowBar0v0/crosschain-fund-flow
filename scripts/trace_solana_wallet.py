#!/usr/bin/env python3
"""Trace Solana wallet activity in a time window."""

from __future__ import annotations

import argparse
import os
from typing import Any

from common import (
    add_common_output_args,
    command_error,
    format_time,
    label_hits,
    load_label_map,
    parse_time,
    pick,
    print_or_write,
    shorten,
    solana_rpc,
    solscan_json,
    unwrap_items,
)


DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def solscan_pro_auto_enabled() -> bool:
    return os.getenv("CFF_ENABLE_SOLSCAN_PRO_AUTO") in ("1", "true", "TRUE", "yes", "YES")


def fetch_solscan_transfers(address: str, start: int | None, end: int | None, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page_size = 100
    max_pages = max(1, (limit + page_size - 1) // page_size)
    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "address": address,
            "page": page,
            "page_size": min(page_size, limit),
            "sort_by": "block_time",
            "sort_order": "asc",
            "exclude_amount_zero": "true",
        }
        if start is not None:
            params["from_time"] = start
        if end is not None:
            params["to_time"] = end
        response = solscan_json("account/transfer", params=params)
        items = unwrap_items(response)
        if not items:
            break
        out.extend(items)
        if len(items) < page_size or len(out) >= limit:
            break
    return out[:limit]


def fetch_rpc_activity(address: str, start: int | None, end: int | None, limit: int, rpc_url: str) -> list[dict[str, Any]]:
    signatures = solana_rpc("getSignaturesForAddress", [address, {"limit": limit}], rpc_url) or []
    selected = []
    for sig in signatures:
        ts = sig.get("blockTime")
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        if end is not None and ts >= end:
            continue
        selected.append(sig)
    selected.sort(key=lambda x: x.get("blockTime") or 0)
    out: list[dict[str, Any]] = []
    for sig in selected:
        tx = solana_rpc("getTransaction", [sig["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}], rpc_url)
        if not tx:
            continue
        meta = tx.get("meta") or {}
        account_keys = tx.get("transaction", {}).get("message", {}).get("accountKeys") or []
        sol_delta = 0
        try:
            for idx, key in enumerate(account_keys):
                pubkey = key.get("pubkey") if isinstance(key, dict) else key
                if pubkey == address:
                    sol_delta = (meta.get("postBalances", [])[idx] - meta.get("preBalances", [])[idx]) / 1_000_000_000
                    break
        except (IndexError, TypeError):
            sol_delta = 0
        token_deltas = []
        balances: dict[tuple[str | None, str | None, int | None], list[float]] = {}
        for b in meta.get("preTokenBalances") or []:
            key = (b.get("owner"), b.get("mint"), b.get("accountIndex"))
            balances.setdefault(key, [0.0, 0.0])[0] = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
        for b in meta.get("postTokenBalances") or []:
            key = (b.get("owner"), b.get("mint"), b.get("accountIndex"))
            balances.setdefault(key, [0.0, 0.0])[1] = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
        for (owner, mint, _idx), (pre, post) in balances.items():
            delta = post - pre
            if owner == address and abs(delta) > 1e-12:
                token_deltas.append({"owner": owner, "mint": mint, "delta": delta})
        out.append(
            {
                "source": "solana_rpc",
                "signature": sig["signature"],
                "block_time": sig.get("blockTime"),
                "time": format_time(sig.get("blockTime")),
                "err": sig.get("err"),
                "sol_delta": sol_delta,
                "token_deltas": token_deltas,
            }
        )
    return out


def normalize_solscan(items: list[dict[str, Any]], address: str) -> list[dict[str, Any]]:
    out = []
    for item in items:
        ts = pick(item, "block_time", "blockTime", "time")
        try:
            ts_int = int(ts)
        except (TypeError, ValueError):
            ts_int = None
        from_addr = pick(item, "from_address", "from", "src", "source")
        to_addr = pick(item, "to_address", "to", "dst", "destination")
        token = pick(item, "token_address", "token", "mint", "token1", "token2")
        amount = pick(item, "amount", "value", "change_amount", default="")
        direction = "out" if from_addr == address else "in" if to_addr == address else "related"
        out.append(
            {
                "source": "solscan",
                "signature": pick(item, "trans_id", "tx_hash", "signature", "hash"),
                "block_time": ts_int,
                "time": format_time(ts_int) if ts_int else pick(item, "time"),
                "from": from_addr,
                "to": to_addr,
                "direction": direction,
                "token": token,
                "amount": amount,
                "raw": item,
            }
        )
    return out


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# Solana Wallet Trace", ""]
    lines.append(f"- Address: `{result['address']}`")
    lines.append(f"- Source: `{result['source']}`")
    lines.append(f"- Window: `{result['window']['from_time']}` to `{result['window']['to_time']}`")
    lines.append(f"- Events: {len(result['events'])}")
    lines.append(f"- Outgoing events: {len(result['outgoing'])}")
    lines.append("")
    if result["outgoing"]:
        lines.append("## First outgoing events")
        lines.append("")
        for event in result["outgoing"][:10]:
            lines.append(f"- `{shorten(event.get('signature'))}` token `{event.get('token') or 'SOL/unknown'}` amount `{event.get('amount') or event.get('sol_delta')}` to `{event.get('to')}` time `{event.get('time')}`")
    if result.get("label_hits"):
        lines.append("")
        lines.append("## Label hits")
        for address, hits in result["label_hits"].items():
            lines.append(f"- `{address}`: {len(hits)} hit(s)")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace Solana wallet activity in a time window.")
    parser.add_argument("--address", required=True)
    parser.add_argument("--from-time")
    parser.add_argument("--to-time")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    parser.add_argument("--source", choices=["auto", "solscan", "rpc"], default="auto")
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    add_common_output_args(parser)
    args = parser.parse_args()
    start = parse_time(args.from_time, args.timezone)
    end = parse_time(args.to_time, args.timezone)

    used_source = args.source
    if args.source == "solscan" and os.getenv("SOLSCAN_API_KEY"):
        events = normalize_solscan(fetch_solscan_transfers(args.address, start, end, args.limit), args.address)
        used_source = "solscan"
    elif args.source == "solscan":
        raise RuntimeError("SOLSCAN_API_KEY is required for --source solscan")
    elif args.source == "auto" and solscan_pro_auto_enabled() and os.getenv("SOLSCAN_API_KEY"):
        try:
            events = normalize_solscan(fetch_solscan_transfers(args.address, start, end, args.limit), args.address)
            used_source = "solscan"
        except Exception:
            events = fetch_rpc_activity(args.address, start, end, args.limit, args.rpc_url)
            used_source = "solana_rpc"
    else:
        events = fetch_rpc_activity(args.address, start, end, args.limit, args.rpc_url)
        used_source = "solana_rpc"

    outgoing = []
    for event in events:
        if event.get("direction") == "out" or event.get("sol_delta", 0) < 0:
            outgoing.append(event)
    addresses = [args.address]
    for event in events:
        for key in ("from", "to"):
            if event.get(key):
                addresses.append(event[key])
    labels = label_hits(addresses, load_label_map(args.label_file, args.label_sheets))
    result = {
        "ok": True,
        "tool": "trace_solana_wallet",
        "address": args.address,
        "source": used_source,
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "summary": {"event_count": len(events), "outgoing_count": len(outgoing), "status": "first_layer_outgoing_detected" if outgoing else "terminal_no_outgoing_detected"},
        "events": events,
        "outgoing": outgoing,
        "label_hits": labels,
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
