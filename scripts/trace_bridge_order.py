#!/usr/bin/env python3
"""Look up bridge orders, with Relay support as the first-class executor."""

from __future__ import annotations

import argparse
from typing import Any

from common import add_common_output_args, command_error, format_time, http_json, print_or_write, shorten


def summarize_changes(tx: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in tx.get("stateChanges") or []:
        change = item.get("change") or {}
        data = change.get("data") or {}
        out.append(
            {
                "address": item.get("address"),
                "kind": change.get("kind"),
                "token": data.get("tokenAddress"),
                "balance_diff": change.get("balanceDiff"),
            }
        )
    return out


def relay_lookup(tx_hash: str | None, address: str | None, limit: int) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if tx_hash:
        params["hash"] = tx_hash
    elif address:
        params["user"] = address
    else:
        raise ValueError("Relay lookup requires --tx or --address")
    data = http_json("https://api.relay.link/requests/v2", params=params)
    orders = []
    for req in data.get("requests") or []:
        req_data = req.get("data") or {}
        in_txs = []
        out_txs = []
        for tx in req_data.get("inTxs") or []:
            in_txs.append(
                {
                    "hash": tx.get("hash"),
                    "chain_id": tx.get("chainId"),
                    "timestamp": tx.get("timestamp"),
                    "time": format_time(tx.get("timestamp")),
                    "status": tx.get("status"),
                    "type": tx.get("type"),
                    "state_changes": summarize_changes(tx),
                }
            )
        for tx in req_data.get("outTxs") or []:
            out_txs.append(
                {
                    "hash": tx.get("hash"),
                    "chain_id": tx.get("chainId"),
                    "timestamp": tx.get("timestamp"),
                    "time": format_time(tx.get("timestamp")),
                    "status": tx.get("status"),
                    "type": tx.get("type"),
                    "state_changes": summarize_changes(tx),
                }
            )
        orders.append(
            {
                "id": req.get("id"),
                "status": req.get("status"),
                "user": req.get("user"),
                "recipient": req.get("recipient"),
                "created_at": req.get("createdAt"),
                "updated_at": req.get("updatedAt"),
                "currency": req_data.get("currency"),
                "price": req_data.get("price"),
                "in_txs": in_txs,
                "out_txs": out_txs,
            }
        )
    return {"ok": True, "bridge": "relay", "query": params, "orders": orders}


def gaszip_lookup(tx_hash: str) -> dict[str, Any]:
    data = http_json(f"https://backend.gas.zip/v2/search/{tx_hash}")
    return {"ok": True, "bridge": "gaszip", "query": {"hash": tx_hash}, "raw": data}


def build_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Bridge Order Lookup: {result.get('bridge')}", ""]
    orders = result.get("orders") or []
    if not orders and "raw" in result:
        lines.append("Raw bridge API result was returned. See JSON output for details.")
        return "\n".join(lines) + "\n"
    if not orders:
        lines.append("No matching bridge orders found.")
        return "\n".join(lines) + "\n"
    for order in orders:
        lines.append(f"## Order `{order.get('id')}`")
        lines.append("")
        lines.append(f"- Status: `{order.get('status')}`")
        lines.append(f"- User: `{order.get('user')}`")
        lines.append(f"- Recipient: `{order.get('recipient')}`")
        lines.append(f"- Created: `{order.get('created_at')}`")
        for name in ("in_txs", "out_txs"):
            lines.append(f"- {name}:")
            for tx in order.get(name) or []:
                lines.append(f"  - `{shorten(str(tx.get('hash')))} ` chain `{tx.get('chain_id')}` status `{tx.get('status')}` time `{tx.get('time')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Look up bridge orders.")
    parser.add_argument("--bridge", choices=["relay", "gaszip"], default="relay")
    parser.add_argument("--tx", help="Origin or destination tx hash/signature")
    parser.add_argument("--address", help="User/sender/recipient address")
    parser.add_argument("--limit", type=int, default=20)
    add_common_output_args(parser)
    args = parser.parse_args()

    if args.bridge == "relay":
        result = relay_lookup(args.tx, args.address, args.limit)
    else:
        if not args.tx:
            raise ValueError("Gas.zip lookup currently requires --tx")
        result = gaszip_lookup(args.tx)
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)

