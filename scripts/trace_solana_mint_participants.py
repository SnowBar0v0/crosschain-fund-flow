#!/usr/bin/env python3
"""Compute Solana mint launch top participants from indexed transfers or holder snapshots."""

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
    http_json,
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

API_BASE = "https://web3.oyuzh.com/priapi/v1/dx/market/v2"
BINANCE_META_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/dex/market/token/meta/info"
BINANCE_DYN_URL = "https://web3.binance.com/bapi/defi/v4/public/wallet-direct/buw/wallet/market/token/dynamic/info"
SOL_CHAIN_ID = 501


def solscan_pro_auto_enabled() -> bool:
    return os.getenv("CFF_ENABLE_SOLSCAN_PRO_AUTO") in ("1", "true", "TRUE", "yes", "YES")


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


def _coerce_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def _coerce_timestamp(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts > 10_000_000_000:
        ts /= 1000
    if ts <= 0:
        return None
    return int(ts)


def _data_obj(response: Any) -> dict[str, Any]:
    data = response.get("data") if isinstance(response, dict) else None
    return data if isinstance(data, dict) else {}


def _data_list(response: Any) -> list[dict[str, Any]]:
    data = _data_obj(response)
    for key in ("holderRankingList", "holderRanking", "holderList", "list", "items"):
        items = data.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("holderRankingList", "holderRanking", "holderList", "list", "items"):
            items = response.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _safe_http_json(url: str, params: dict[str, Any], warnings: list[str] | None = None) -> Any:
    try:
        return http_json(url, params=params)
    except Exception as exc:
        if warnings is not None:
            warnings.append(f"Provider request skipped: {url} {params} -> {str(exc)[:160]}")
        return {}


def fetch_market_holders(mint: str, chain_id: int = SOL_CHAIN_ID) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Fetch holder ranking and token metadata from OKX/APIBase-style and Binance Web3 endpoints."""
    warnings: list[str] = []
    numeric_chain = str(int(chain_id))
    chain_variants = []
    for value in (numeric_chain, f"CT_{numeric_chain}", str(chain_id)):
        if value not in chain_variants:
            chain_variants.append(value)
    token_keys = ["tokenAddress", "tokenContractAddress", "contractAddress", "contract"]

    holders_response: dict[str, Any] = {}
    holders: list[dict[str, Any]] = []
    for key in token_keys:
        if holders:
            break
        for chain_value in chain_variants:
            response = _safe_http_json(f"{API_BASE}/holders/ranking-list", {key: mint, "chainId": chain_value})
            items = _data_list(response)
            if items:
                holders_response = response if isinstance(response, dict) else {}
                holders = items
                break

    if not holders:
        warnings.append("Market holder provider returned no holder ranking list.")

    info: dict[str, Any] = {}
    for key in token_keys:
        if info:
            break
        for chain_value in chain_variants:
            response = _safe_http_json(f"{API_BASE}/latest/info", {key: mint, "chainId": chain_value})
            data = _data_obj(response)
            if data:
                info.update(data)
                break

    binance_chain_variants = []
    for value in (f"CT_{numeric_chain}", numeric_chain, str(chain_id)):
        if value not in binance_chain_variants:
            binance_chain_variants.append(value)
    if not info:
        for key in ("contractAddress", "tokenContractAddress", "tokenAddress", "contract", "address"):
            if info:
                break
            for chain_value in binance_chain_variants:
                meta_data = _data_obj(_safe_http_json(BINANCE_META_URL, {key: mint, "chainId": chain_value}))
                dyn_data = _data_obj(_safe_http_json(BINANCE_DYN_URL, {key: mint, "chainId": chain_value}))
                if meta_data or dyn_data:
                    info.update(
                        {
                            "tokenName": meta_data.get("name") or meta_data.get("tokenId") or "",
                            "tokenSymbol": meta_data.get("symbol") or "",
                            "contractAddress": meta_data.get("contractAddress") or mint,
                            "decimals": meta_data.get("decimals"),
                            "creatorAddress": meta_data.get("creatorAddress"),
                            "createTime": meta_data.get("createTime"),
                            "chainName": meta_data.get("chainName"),
                            "price": dyn_data.get("price") or dyn_data.get("usdPrice"),
                            "marketCap": dyn_data.get("marketCap") or dyn_data.get("market_cap"),
                            "holders": dyn_data.get("holders") or dyn_data.get("holderCount") or dyn_data.get("holdersCount"),
                            "launchTime": dyn_data.get("launchTime"),
                        }
                    )
                    break

    if not info and holders_response:
        holder_data = _data_obj(holders_response)
        info.update(
            {
                "tokenName": holder_data.get("tokenName") or holder_data.get("tokenFullName") or holder_data.get("name"),
                "tokenSymbol": holder_data.get("tokenSymbol") or holder_data.get("symbol") or holder_data.get("token"),
                "holders": holder_data.get("holders") or holder_data.get("addressCount") or len(holders),
            }
        )
    return info, holders, warnings


def infer_creation_time_market(mint: str) -> int | None:
    try:
        info, _holders, _warnings = fetch_market_holders(mint)
    except Exception:
        return None
    for key in ("createTime", "launchTime", "createdTime", "created_time", "firstMintTime", "blockTime"):
        ts = _coerce_timestamp(info.get(key))
        if ts:
            return ts
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


def normalize_market_holder(item: dict[str, Any], mint: str) -> dict[str, Any]:
    address = (
        item.get("holderWalletAddress")
        or item.get("holderAddress")
        or item.get("holder")
        or item.get("address")
        or item.get("walletAddress")
    )
    percent = _coerce_number(item.get("holdAmountPercentage") or item.get("tokenHoldPercentage") or item.get("percentage"))
    amount = _coerce_number(item.get("holdAmount") or item.get("amount") or item.get("balance") or item.get("quantity"))
    hold_start = _coerce_timestamp(item.get("holdingTime") or item.get("holdStartTime") or item.get("firstHoldTime"))
    funding_time = _coerce_timestamp(item.get("fundingSourceTime"))
    last_trade_time = _coerce_timestamp(item.get("lastTradeTime"))
    tags: list[str] = []
    raw_tags = item.get("tagList") or item.get("tags") or []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, str):
                tags.append(tag)
            elif isinstance(tag, (list, tuple)) and tag:
                tags.append(str(tag[0]))
            elif isinstance(tag, dict):
                value = tag.get("name") or tag.get("k") or tag.get("label")
                if value:
                    tags.append(str(value))
    return {
        "address": address,
        "rank_value": percent,
        "token_in": amount,
        "token_out": 0.0,
        "token_net": amount,
        "hold_percent": percent,
        "tx_count": int(_coerce_number(item.get("buyCount"))) + int(_coerce_number(item.get("sellCount"))),
        "buy_count": int(_coerce_number(item.get("buyCount"))),
        "sell_count": int(_coerce_number(item.get("sellCount"))),
        "first_time": hold_start,
        "first_time_text": format_time(hold_start),
        "last_time": last_trade_time,
        "last_time_text": format_time(last_trade_time),
        "first_signature": None,
        "avg_price": item.get("boughtAvgPrice") or item.get("holdAvgPrice"),
        "profit": item.get("totalProfitPercentage") or item.get("totalProfit"),
        "funding_source": item.get("fundingSourceAddress"),
        "funding_source_name": item.get("fundingSourceAddressShowName"),
        "funding_source_time": funding_time,
        "funding_source_time_text": format_time(funding_time),
        "native_token_balance": _coerce_number(item.get("nativeTokenBalance")),
        "native_token_price": _coerce_number(item.get("nativeTokenPrice")),
        "in_flow_amount": _coerce_number(item.get("inFlowAmount")),
        "in_flow_value": _coerce_number(item.get("inFlowValue")),
        "buy_value": _coerce_number(item.get("buyValue")),
        "sell_value": _coerce_number(item.get("sellValue")),
        "hold_volume": _coerce_number(item.get("holdVolume") or item.get("tokenHoldVolume")),
        "tags": tags,
        "mint": mint,
        "raw": item,
    }


def _is_infrastructure_holder(row: dict[str, Any]) -> bool:
    tags = [str(tag).lower() for tag in row.get("tags") or []]
    infrastructure_terms = ("liquiditypool", "authority", "router", "vault")
    return any(any(term in tag for term in infrastructure_terms) for tag in tags)


def rank_market_holders(holders: list[dict[str, Any]], mint: str, include_infrastructure: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = [normalize_market_holder(item, mint) for item in holders]
    normalized = [row for row in normalized if row.get("address")]
    excluded = [row for row in normalized if _is_infrastructure_holder(row)]
    ranked = normalized if include_infrastructure else [row for row in normalized if not _is_infrastructure_holder(row)]
    ranked.sort(key=lambda x: (x.get("hold_percent") or 0.0, x.get("token_net") or 0.0), reverse=True)
    excluded.sort(key=lambda x: (x.get("hold_percent") or 0.0, x.get("token_net") or 0.0), reverse=True)
    return ranked, excluded


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
    lines.append(f"- Source: `{result['source']}`")
    lines.append(f"- Window: `{result['window']['from_time']}` to `{result['window']['to_time']}`")
    lines.append(f"- Metric: `{result['metric']}`")
    if result["summary"].get("transfer_count") is not None:
        lines.append(f"- Transfers indexed: {result['summary']['transfer_count']}")
    if result["summary"].get("holder_snapshot_count") is not None:
        lines.append(f"- Holder snapshot rows: {result['summary']['holder_snapshot_count']}")
    if result["summary"].get("excluded_infrastructure_count") is not None:
        lines.append(f"- Excluded infrastructure rows: {result['summary']['excluded_infrastructure_count']}")
    lines.append(f"- Participants ranked: {result['summary']['participant_count']}")
    token_info = result.get("token_info") or {}
    if token_info:
        name = token_info.get("tokenName") or token_info.get("name")
        symbol = token_info.get("tokenSymbol") or token_info.get("symbol")
        market_cap = token_info.get("marketCap") or token_info.get("market_cap")
        if name or symbol or market_cap:
            lines.append(f"- Token info: `{name or ''}` `{symbol or ''}` market_cap `{market_cap or ''}`")
    lines.append("")
    if result["source"] == "market_holders":
        lines.append("| Rank | Wallet | Hold % | Amount | Buys | Sells | First Hold | Funding | Label Hits |")
        lines.append("|---:|---|---:|---:|---:|---:|---|---|---:|")
    else:
        lines.append("| Rank | Wallet | Rank Value | In | Out | First Seen | Label Hits |")
        lines.append("|---:|---|---:|---:|---:|---|---:|")
    for idx, row in enumerate(result["top"], start=1):
        hits = len(result["label_hits"].get(row["address"], []))
        if result["source"] == "market_holders":
            funding = shorten(row.get("funding_source")) if row.get("funding_source") else ""
            lines.append(f"| {idx} | `{shorten(row['address'])}` | {row.get('hold_percent', 0):.6f} | {row.get('token_net', 0):.6f} | {row.get('buy_count', 0)} | {row.get('sell_count', 0)} | {row.get('first_time_text')} | `{funding}` | {hits} |")
        else:
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
    parser.add_argument("--from-time", help="Window start. If omitted, infer mint creation time from market metadata or explicit Solscan Pro mode.")
    parser.add_argument("--to-time", help="Window end. If omitted, use --hours-after-create from start.")
    parser.add_argument("--hours-after-create", type=float, default=3.0)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--metric", choices=["top_net_buyers", "top_gross_buy_volume", "top_current_holders"], default="top_net_buyers")
    parser.add_argument("--provider", choices=["auto", "solscan", "market_holders"], default="auto")
    parser.add_argument("--market-chain-id", type=int, default=SOL_CHAIN_ID)
    parser.add_argument("--include-infrastructure", action="store_true", help="Include liquidity pools, authority accounts, routers, and vault-like holders in holder rankings.")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    add_common_output_args(parser)
    args = parser.parse_args()

    warnings: list[str] = []
    provider_attempts: list[dict[str, Any]] = []
    start = parse_time(args.from_time, args.timezone) if args.from_time else None
    if start is None and args.provider in ("auto", "market_holders"):
        start = infer_creation_time_market(args.mint)
    if start is None and args.provider == "solscan" and os.getenv("SOLSCAN_API_KEY"):
        start = infer_creation_time(args.mint)
    if start is None:
        raise RuntimeError("Could not infer mint creation time. Provide --from-time or a mint creation tx/window.")
    end = parse_time(args.to_time, args.timezone) if args.to_time else int(start + args.hours_after_create * 3600)

    raw_transfers: list[dict[str, Any]] = []
    transfers: list[dict[str, Any]] = []
    raw_holders: list[dict[str, Any]] = []
    excluded_holders: list[dict[str, Any]] = []
    token_info: dict[str, Any] = {}
    source = args.provider
    ranked: list[dict[str, Any]]

    can_try_solscan = (
        args.provider == "solscan"
        or (args.provider == "auto" and solscan_pro_auto_enabled())
    ) and os.getenv("SOLSCAN_API_KEY")
    if args.provider == "solscan" and not os.getenv("SOLSCAN_API_KEY"):
        raise RuntimeError("SOLSCAN_API_KEY is required for --provider solscan.")
    if can_try_solscan:
        try:
            raw_transfers = fetch_token_transfers(args.mint, start, end, args.max_pages, args.page_size)
            transfers = [normalize_transfer(item, args.mint) for item in raw_transfers]
            if len(raw_transfers) >= args.max_pages * args.page_size:
                warnings.append("Transfer results reached max page limit; increase --max-pages for full coverage.")
            ranked = rank_participants(transfers, args.metric)
            source = "solscan"
            provider_attempts.append({"provider": "solscan", "ok": True, "rows": len(raw_transfers)})
        except Exception as exc:
            provider_attempts.append({"provider": "solscan", "ok": False, "error": str(exc)[:500]})
            if args.provider == "solscan":
                raise
            warnings.append(f"Solscan indexed token transfer provider failed; falling back to market holder snapshot: {str(exc)[:200]}")
            ranked = []
    else:
        ranked = []

    if not ranked and args.provider in ("auto", "market_holders"):
        token_info, raw_holders, holder_warnings = fetch_market_holders(args.mint, args.market_chain_id)
        warnings.extend(holder_warnings)
        ranked, excluded_holders = rank_market_holders(raw_holders, args.mint, args.include_infrastructure)
        source = "market_holders"
        provider_attempts.append({"provider": "market_holders", "ok": bool(ranked), "rows": len(raw_holders)})
        warnings.append("Market holder fallback is a current holder snapshot, not a complete historical transfer index for the requested window.")
        if args.metric != "top_current_holders":
            warnings.append(f"Requested metric `{args.metric}` was approximated by current holder percentage because historical transfer coverage was unavailable.")

    top = ranked[: args.top]
    labels = label_hits([row["address"] for row in top], load_label_map(args.label_file, args.label_sheets))
    result = {
        "ok": True,
        "tool": "trace_solana_mint_participants",
        "mint": args.mint,
        "metric": args.metric,
        "source": source,
        "provider_attempts": provider_attempts,
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "summary": {
            "transfer_count": len(transfers) if source == "solscan" else None,
            "holder_snapshot_count": len(raw_holders) if source == "market_holders" else None,
            "excluded_infrastructure_count": len(excluded_holders) if source == "market_holders" else None,
            "participant_count": len(ranked),
            "top_count": len(top),
            "status": "historical_transfer_index" if source == "solscan" else "holder_snapshot_fallback",
        },
        "token_info": token_info,
        "top": top,
        "label_hits": labels,
        "warnings": warnings,
        "transfers_sample": transfers[:50],
        "holders_sample": raw_holders[:50],
        "excluded_infrastructure": excluded_holders[:50],
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
