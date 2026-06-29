#!/usr/bin/env python3
"""Fetch token trading activity from the public OKX Web3 market endpoint."""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from typing import Any

from common import (
    ToolError,
    add_common_output_args,
    command_error,
    format_time,
    http_json,
    label_hits,
    load_label_map,
    parse_time,
    print_or_write,
    shorten,
)


OKX_TRADING_HISTORY_URL = "https://web3.oyuzh.com/priapi/v1/dx/market/v2/trading-history/filter-list"
OKX_TOKEN_REFERER = "https://web3.oyuzh.com/zh-hans/token/{chain_slug}/{token}"
DEFAULT_CHAIN_ID = 501
OKX_CHAIN_SLUGS = {
    1: "ethereum",
    10: "optimism",
    56: "bsc",
    137: "polygon",
    324: "zksync-era",
    501: "solana",
    8453: "base",
    42161: "arbitrum",
    43114: "avalanche",
    59144: "linea",
    81457: "blast",
}


def _coerce_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _side(value: Any) -> str:
    return "buy" if str(value) == "1" else "sell"


def okx_chain_slug(chain_id: int, chain_slug: str | None = None) -> str:
    if chain_slug:
        return chain_slug
    return OKX_CHAIN_SLUGS.get(int(chain_id), str(chain_id))


def _tags(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    raw = row.get("tagList") or row.get("t") or []
    if not isinstance(raw, list):
        return out
    for tag in raw:
        if isinstance(tag, str):
            out.append(tag)
        elif isinstance(tag, list) and tag:
            out.append(str(tag[0]))
        elif isinstance(tag, dict):
            value = tag.get("k") or tag.get("name") or tag.get("label")
            if value:
                out.append(str(value))
    return out


def _changed_amount(row: dict[str, Any], token_address: str) -> float:
    for item in row.get("changedTokenInfo") or []:
        if not isinstance(item, dict):
            continue
        if item.get("tokenAddress") == token_address:
            return _coerce_float(item.get("amount"))
    return 0.0


def normalize_okx_trade(row: dict[str, Any], token_address: str, timezone: str = "Asia/Shanghai") -> dict[str, Any]:
    ts_ms = row.get("timestamp")
    try:
        ts = int(float(ts_ms) / 1000)
    except (TypeError, ValueError):
        ts = None
    side = _side(row.get("isBuy"))
    token_amount = _changed_amount(row, token_address)
    base_token = row.get("baseTokenAddress")
    base_amount = _changed_amount(row, base_token) if base_token else 0.0
    signed_token_delta = token_amount if side == "buy" else -token_amount
    signed_base_delta = -base_amount if side == "buy" else base_amount
    user_address = row.get("userAddress")
    return {
        "id": row.get("id"),
        "chain_id": row.get("chainId"),
        "token_address": token_address,
        "timestamp": ts,
        "timestamp_ms": ts_ms,
        "time": format_time(ts, timezone) if ts else None,
        "side": side,
        "user_address": user_address,
        "tx_hash": row.get("txHash"),
        "tx_hash_url": row.get("txHashUrl"),
        "explorer_url": row.get("explorerUrl"),
        "dex_name": row.get("dexName"),
        "price": _coerce_float(row.get("price")),
        "volume_usd": _coerce_float(row.get("volume")),
        "token_amount": token_amount,
        "base_token_address": base_token,
        "base_token_amount": base_amount,
        "signed_token_delta": signed_token_delta,
        "signed_base_delta": signed_base_delta,
        "tags": _tags(row),
        "tx_unique_key": row.get("txUniqueKey"),
        "source_id": row.get("sourceId"),
        "raw": row,
    }


def okx_request(payload: dict[str, Any], token_address: str, chain_slug: str) -> dict[str, Any]:
    response = http_json(
        OKX_TRADING_HISTORY_URL,
        method="POST",
        body=payload,
        headers={
            "accept": "application/json",
            "origin": "https://web3.oyuzh.com",
            "referer": OKX_TOKEN_REFERER.format(chain_slug=chain_slug, token=token_address),
            "user-agent": "Mozilla/5.0",
        },
    )
    if not isinstance(response, dict):
        raise ToolError("OKX trading history returned a non-object response.")
    if response.get("code") not in (0, "0", None):
        hint = ""
        trading_filter = payload.get("tradingHistoryFilter") or {}
        end_ms = trading_filter.get("endTime")
        if isinstance(end_ms, (int, float)) and end_ms > int(time.time() * 1000):
            hint = " endTime appears to be in the future for OKX; use a closed time window ending at or before now."
        raise ToolError(f"OKX trading history request failed: {response}.{hint}")
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def fetch_okx_trades(
    token_address: str,
    *,
    chain_id: int = DEFAULT_CHAIN_ID,
    chain_slug: str | None = None,
    start: int | None = None,
    end: int | None = None,
    page_size: int = 30,
    max_pages: int = 20,
    desc: bool = True,
    addresses: list[str] | None = None,
    timezone: str = "Asia/Shanghai",
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    all_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    data_id = ""
    has_more = "1"
    referer_slug = okx_chain_slug(chain_id, chain_slug)
    for page in range(max_pages):
        trading_filter: dict[str, Any] = {
            "chainId": chain_id,
            "tokenContractAddress": token_address,
        }
        if start is not None:
            trading_filter["startTime"] = int(start * 1000)
        if end is not None:
            trading_filter["endTime"] = int(end * 1000)
        if addresses:
            trading_filter["userAddressList"] = addresses
        payload = {
            "dataId": data_id,
            "desc": bool(desc),
            "orderBy": "timestamp",
            "limit": page_size,
            "tradingHistoryFilter": trading_filter,
        }
        data = okx_request(payload, token_address, referer_slug)
        rows = data.get("list") or []
        if not isinstance(rows, list):
            rows = []
        new_count = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("txUniqueKey") or raw.get("id") or raw.get("txHash") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            all_rows.append(normalize_okx_trade(raw, token_address, timezone))
            new_count += 1
        has_more = str(data.get("hasMore") or "0")
        if not rows or has_more != "1":
            break
        next_id = rows[-1].get("id") if isinstance(rows[-1], dict) else None
        if not next_id or str(next_id) == data_id or new_count == 0:
            warnings.append("OKX pagination stopped because the next cursor did not advance.")
            break
        data_id = str(next_id)
    if has_more == "1" and len(all_rows) >= max_pages * page_size:
        warnings.append("OKX trading history reached max page limit; increase --max-pages for broader coverage.")
    warnings.append("OKX trading activity is a public market-data index. Verify material transactions on the chain RPC or an explorer before treating them as final evidence.")
    return all_rows, {"has_more": has_more, "last_data_id": data_id, "page_size": page_size, "max_pages": max_pages}, warnings


def rank_okx_trade_participants(rows: list[dict[str, Any]], metric: str = "top_net_buyers") -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "token_in": 0.0,
            "token_out": 0.0,
            "buy_value": 0.0,
            "sell_value": 0.0,
            "tx_count": 0,
            "buy_count": 0,
            "sell_count": 0,
            "first_time": None,
            "last_time": None,
            "first_signature": None,
            "last_signature": None,
            "dex_names": set(),
            "tags": set(),
        }
    )
    for row in rows:
        address = row.get("user_address")
        if not address:
            continue
        item = stats[address]
        amount = float(row.get("token_amount") or 0.0)
        value = float(row.get("volume_usd") or 0.0)
        if row.get("side") == "buy":
            item["token_in"] += amount
            item["buy_value"] += value
            item["buy_count"] += 1
        else:
            item["token_out"] += amount
            item["sell_value"] += value
            item["sell_count"] += 1
        item["tx_count"] += 1
        ts = row.get("timestamp")
        if ts is not None and (item["first_time"] is None or ts < item["first_time"]):
            item["first_time"] = ts
            item["first_signature"] = row.get("tx_hash")
        if ts is not None and (item["last_time"] is None or ts > item["last_time"]):
            item["last_time"] = ts
            item["last_signature"] = row.get("tx_hash")
        if row.get("dex_name"):
            item["dex_names"].add(str(row.get("dex_name")))
        for tag in row.get("tags") or []:
            item["tags"].add(str(tag))
    ranked = []
    for address, item in stats.items():
        net = item["token_in"] - item["token_out"]
        if metric == "top_gross_buy_volume":
            rank_value = item["token_in"]
        elif metric == "top_flow_value":
            rank_value = item["buy_value"] + item["sell_value"]
        else:
            rank_value = net
        if rank_value <= 0:
            continue
        ranked.append(
            {
                "address": address,
                "rank_value": rank_value,
                "token_in": item["token_in"],
                "token_out": item["token_out"],
                "token_net": net,
                "buy_value": item["buy_value"],
                "sell_value": item["sell_value"],
                "tx_count": item["tx_count"],
                "buy_count": item["buy_count"],
                "sell_count": item["sell_count"],
                "first_time": item["first_time"],
                "first_time_text": format_time(item["first_time"]) if item["first_time"] else None,
                "last_time": item["last_time"],
                "last_time_text": format_time(item["last_time"]) if item["last_time"] else None,
                "first_signature": item["first_signature"],
                "last_signature": item["last_signature"],
                "dex_names": sorted(item["dex_names"]),
                "tags": sorted(item["tags"]),
            }
        )
    ranked.sort(key=lambda x: x["rank_value"], reverse=True)
    return ranked


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# OKX Token Trading Activity", ""]
    lines.append(f"- Token: `{result['token_address']}`")
    lines.append(f"- Chain ID: `{result['chain_id']}`")
    lines.append(f"- Window: `{result['window']['from_time']}` to `{result['window']['to_time']}`")
    lines.append(f"- Trades fetched: {result['summary']['trade_count']}")
    lines.append(f"- Participant wallets: {result['summary']['participant_count']}")
    lines.append("")
    lines.append("| Rank | Wallet | Net Token | Bought | Sold | Tx | Buy Value | Sell Value | Label Hits |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for idx, row in enumerate(result["participants"][:100], start=1):
        hits = len(result["label_hits"].get(row["address"], []))
        lines.append(
            f"| {idx} | `{shorten(row['address'])}` | {row['token_net']:.6f} | {row['token_in']:.6f} | {row['token_out']:.6f} | {row['tx_count']} | {row['buy_value']:.4f} | {row['sell_value']:.4f} | {hits} |"
        )
    if result["trades"]:
        lines.append("")
        lines.append("## Recent Trades")
        lines.append("| Time | Side | Wallet | Token Amount | Value USD | DEX | Tx | Tags |")
        lines.append("|---|---|---|---:|---:|---|---|---|")
        for row in result["trades"][:50]:
            tags = ",".join(row.get("tags") or [])
            tx = shorten(row.get("tx_hash"))
            lines.append(
                f"| {row.get('time')} | {row.get('side')} | `{shorten(row.get('user_address'))}` | {row.get('token_amount', 0):.6f} | {row.get('volume_usd', 0):.4f} | {row.get('dex_name') or ''} | `{tx}` | {tags} |"
            )
    if result["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OKX Web3 token trading activity.")
    parser.add_argument("--token", "--mint", dest="token", required=True, help="Token contract/mint address.")
    parser.add_argument("--chain-id", type=int, default=DEFAULT_CHAIN_ID)
    parser.add_argument("--chain-slug", help="Optional OKX URL chain slug for referer, e.g. solana, ethereum, base, bsc.")
    parser.add_argument("--from-time")
    parser.add_argument("--to-time")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--page-size", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--addresses", nargs="*", default=[])
    parser.add_argument("--metric", choices=["top_net_buyers", "top_gross_buy_volume", "top_flow_value"], default="top_net_buyers")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    add_common_output_args(parser)
    args = parser.parse_args()

    start = parse_time(args.from_time, args.timezone) if args.from_time else None
    end = parse_time(args.to_time, args.timezone) if args.to_time else None
    rows, paging, warnings = fetch_okx_trades(
        args.token,
        chain_id=args.chain_id,
        chain_slug=args.chain_slug,
        start=start,
        end=end,
        page_size=args.page_size,
        max_pages=args.max_pages,
        addresses=args.addresses,
        timezone=args.timezone,
    )
    participants = rank_okx_trade_participants(rows, args.metric)
    top = participants[: args.top]
    labels = load_label_map(args.label_file, args.label_sheets)
    result = {
        "ok": True,
        "tool": "fetch_okx_token_trades",
        "source": "okx_trading_history",
        "token_address": args.token,
        "chain_id": args.chain_id,
        "metric": args.metric,
        "window": {
            "from": start,
            "to": end,
            "from_time": format_time(start, args.timezone) if start else None,
            "to_time": format_time(end, args.timezone) if end else None,
        },
        "summary": {
            "trade_count": len(rows),
            "participant_count": len(participants),
            "top_count": len(top),
            "paging_has_more": paging.get("has_more"),
        },
        "participants": top,
        "all_participants_sample": participants[:100],
        "trades": rows[: min(len(rows), 500)],
        "label_hits": label_hits([row["address"] for row in top], labels),
        "paging": paging,
        "warnings": warnings,
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
