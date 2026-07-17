#!/usr/bin/env python3
"""Trace first-layer EVM wallet activity with Etherscan or Blockscout."""

from __future__ import annotations

import argparse
import os
from typing import Any

from common import add_common_output_args, command_error, format_time, http_json, parse_time, print_or_write, shorten
from evm_networks import chain_name, robinhood_blockscout_api


def resolve_provider(provider: str, chain_id: int) -> str | None:
    if provider == "auto":
        if robinhood_blockscout_api(chain_id):
            return "robinhood_blockscout"
        if os.getenv("ETHERSCAN_API_KEY"):
            return "etherscan"
        if os.getenv("BLOCKSCOUT_API_KEY"):
            return "blockscout"
        return None
    if provider == "robinhood_blockscout" and not robinhood_blockscout_api(chain_id):
        raise RuntimeError(f"Robinhood Blockscout is not configured for chain {chain_id}")
    return provider


def provider_api_key(provider: str) -> str | None:
    if provider == "etherscan":
        return os.getenv("ETHERSCAN_API_KEY")
    if provider == "blockscout":
        return os.getenv("BLOCKSCOUT_API_KEY")
    if provider == "robinhood_blockscout":
        return ""
    return None


def fetch_account_action(provider: str, chain_id: int, action: str, address: str, api_key: str | None, limit: int) -> list[dict[str, Any]]:
    if provider == "robinhood_blockscout":
        url = robinhood_blockscout_api(chain_id)
        if not url:
            raise RuntimeError(f"Robinhood Blockscout is not configured for chain {chain_id}")
        rows: list[dict[str, Any]] = []
        page_size = min(max(limit, 1), 100)
        page = 1
        while len(rows) < limit:
            data = http_json(
                url,
                params={
                    "module": "account",
                    "action": action,
                    "address": address,
                    "page": page,
                    "offset": min(page_size, limit - len(rows)),
                    "sort": "asc",
                },
            )
            result = data.get("result")
            if not isinstance(result, list):
                if data.get("status") == "0" and "No transactions" in str(data.get("message")):
                    break
                raise RuntimeError(f"{provider} {action} failed: {data}")
            for row in result:
                if isinstance(row, dict) and not row.get("hash") and row.get("transactionHash"):
                    row["hash"] = row["transactionHash"]
            rows.extend(row for row in result if isinstance(row, dict))
            if len(result) < min(page_size, limit - (len(rows) - len(result))):
                break
            page += 1
        return rows[:limit]
    if provider == "etherscan":
        url = "https://api.etherscan.io/v2/api"
        params = {
            "chainid": chain_id,
            "module": "account",
            "action": action,
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "asc",
            "apikey": api_key,
        }
    elif provider == "blockscout":
        url = "https://api.blockscout.com/v2/api"
        params = {
            "chain_id": chain_id,
            "module": "account",
            "action": action,
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "asc",
            "apikey": api_key,
        }
    else:
        raise RuntimeError(f"Unknown EVM provider: {provider}")
    data = http_json(url, params=params)
    result = data.get("result")
    if isinstance(result, list):
        for row in result:
            if isinstance(row, dict) and not row.get("hash") and row.get("transactionHash"):
                row["hash"] = row["transactionHash"]
        return result
    if data.get("status") == "0" and "No transactions" in str(data.get("message")):
        return []
    raise RuntimeError(f"{provider} {action} failed: {data}")


def in_window(item: dict[str, Any], start: int | None, end: int | None) -> bool:
    ts_raw = item.get("timeStamp") or item.get("timestamp")
    try:
        ts = int(ts_raw)
    except (TypeError, ValueError):
        return True
    return (start is None or ts >= start) and (end is None or ts < end)


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# EVM Wallet First-Layer Trace", ""]
    lines.append(f"- Address: `{result['address']}`")
    lines.append(f"- Chain ID: `{result['chain_id']}`")
    lines.append(f"- Chain: `{result['chain']}`")
    lines.append(f"- Provider: `{result['provider']}`")
    lines.append(f"- Window: `{result['window'].get('from_time')}` to `{result['window'].get('to_time')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    s = result["summary"]
    lines.append(f"- Normal tx: {s['normal_tx_count']}")
    lines.append(f"- ERC20 transfers: {s['erc20_tx_count']}")
    lines.append(f"- Internal tx: {s['internal_tx_count']}")
    lines.append(f"- Outgoing events: {s['outgoing_count']}")
    if result["outgoing"]:
        lines.append("")
        lines.append("## First outgoing events")
        lines.append("")
        for item in result["outgoing"][:10]:
            lines.append(f"- `{item['type']}` `{shorten(item.get('hash'))}` -> `{item.get('to')}` token `{item.get('token_symbol') or 'native'}` value `{item.get('value')}` time `{item.get('time')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace first-layer EVM wallet activity.")
    parser.add_argument("--address", required=True)
    parser.add_argument("--chain-id", type=int, default=1)
    parser.add_argument("--from-time")
    parser.add_argument("--to-time")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--provider", choices=["auto", "etherscan", "blockscout", "robinhood_blockscout"], default="auto")
    parser.add_argument("--limit", type=int, default=100)
    add_common_output_args(parser)
    args = parser.parse_args()

    provider = resolve_provider(args.provider, args.chain_id)
    if provider is None:
        raise RuntimeError("Missing EVM provider API key; set ETHERSCAN_API_KEY or BLOCKSCOUT_API_KEY")
    api_key = provider_api_key(provider)
    if provider != "robinhood_blockscout" and not api_key:
        raise RuntimeError(f"Missing {provider.upper()} API key in environment")
    start = parse_time(args.from_time, args.timezone)
    end = parse_time(args.to_time, args.timezone)
    actions = {
        "normal": "txlist",
        "erc20": "tokentx",
        "internal": "txlistinternal",
    }
    records = {name: [x for x in fetch_account_action(provider, args.chain_id, action, args.address, api_key, args.limit) if in_window(x, start, end)] for name, action in actions.items()}
    address_l = args.address.lower()
    outgoing = []
    for kind, items in records.items():
        for item in items:
            if str(item.get("from", "")).lower() == address_l:
                outgoing.append(
                    {
                        "type": kind,
                        "hash": item.get("hash"),
                        "from": item.get("from"),
                        "to": item.get("to"),
                        "value": item.get("value"),
                        "token_symbol": item.get("tokenSymbol"),
                        "token_contract": item.get("contractAddress"),
                        "timestamp": item.get("timeStamp"),
                        "time": format_time(int(item.get("timeStamp"))) if str(item.get("timeStamp", "")).isdigit() else None,
                    }
                )
    result = {
        "ok": True,
        "tool": "trace_evm_wallet",
        "provider": provider,
        "address": args.address,
        "chain_id": args.chain_id,
        "chain": chain_name(args.chain_id),
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "summary": {
            "normal_tx_count": len(records["normal"]),
            "erc20_tx_count": len(records["erc20"]),
            "internal_tx_count": len(records["internal"]),
            "outgoing_count": len(outgoing),
            "status": "first_layer_outgoing_detected" if outgoing else "terminal_no_outgoing_detected",
        },
        "outgoing": outgoing,
        "records": records,
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)

