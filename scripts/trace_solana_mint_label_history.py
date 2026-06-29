#!/usr/bin/env python3
"""Scan candidate Solana addresses for historical participation in a mint."""

from __future__ import annotations

import argparse
import time
from typing import Any

from common import (
    SOL_RE,
    add_common_output_args,
    command_error,
    format_time,
    label_hits,
    load_label_map,
    parse_time,
    print_or_write,
    shorten,
    solana_rpc,
)
from trace_solana_mint_participants import fetch_market_holders, infer_creation_time_market


DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def candidate_addresses(address_args: list[str], label_file: str | None, label_sheets: str | None) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    labels = load_label_map(label_file, label_sheets)
    out: list[str] = []
    for value in address_args:
        if SOL_RE.fullmatch(value):
            out.append(value)
    for address in labels:
        if SOL_RE.fullmatch(address):
            out.append(address)
    seen: set[str] = set()
    deduped = []
    for address in out:
        if address not in seen:
            seen.add(address)
            deduped.append(address)
    return deduped, labels


def fetch_signatures_for_window(address: str, start: int, end: int, rpc_url: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    before = None
    remaining = limit
    while remaining > 0:
        batch_limit = min(1000, remaining)
        opts: dict[str, Any] = {"limit": batch_limit}
        if before:
            opts["before"] = before
        batch = solana_rpc("getSignaturesForAddress", [address, opts], rpc_url) or []
        if not batch:
            break
        stop = False
        for item in batch:
            ts = item.get("blockTime")
            if ts is None:
                continue
            if ts >= end:
                continue
            if ts < start:
                stop = True
                continue
            out.append(item)
        before = batch[-1].get("signature")
        remaining -= len(batch)
        if stop or len(batch) < batch_limit:
            break
    out.sort(key=lambda x: x.get("blockTime") or 0)
    return out


def tx_owner_mint_delta(tx: dict[str, Any], owner: str, mint: str) -> float:
    meta = tx.get("meta") or {}
    balances: dict[tuple[str | None, str | None, int | None], list[float]] = {}
    for b in meta.get("preTokenBalances") or []:
        key = (b.get("owner"), b.get("mint"), b.get("accountIndex"))
        balances.setdefault(key, [0.0, 0.0])[0] = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
    for b in meta.get("postTokenBalances") or []:
        key = (b.get("owner"), b.get("mint"), b.get("accountIndex"))
        balances.setdefault(key, [0.0, 0.0])[1] = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
    delta = 0.0
    for (bal_owner, bal_mint, _idx), (pre, post) in balances.items():
        if bal_owner == owner and bal_mint == mint:
            delta += post - pre
    return delta


def scan_address(address: str, mint: str, start: int, end: int, rpc_url: str, per_address_limit: int, sleep_s: float) -> dict[str, Any]:
    signatures = fetch_signatures_for_window(address, start, end, rpc_url, per_address_limit)
    events = []
    net = 0.0
    gross_in = 0.0
    gross_out = 0.0
    for sig in signatures:
        tx = solana_rpc("getTransaction", [sig["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}], rpc_url)
        if not tx:
            continue
        delta = tx_owner_mint_delta(tx, address, mint)
        if abs(delta) <= 1e-12:
            continue
        net += delta
        if delta > 0:
            gross_in += delta
        else:
            gross_out += abs(delta)
        events.append(
            {
                "signature": sig.get("signature"),
                "block_time": sig.get("blockTime"),
                "time": format_time(sig.get("blockTime")),
                "delta": delta,
                "direction": "in" if delta > 0 else "out",
                "err": sig.get("err"),
            }
        )
        if sleep_s > 0:
            time.sleep(sleep_s)
    return {
        "address": address,
        "scanned_signature_count": len(signatures),
        "tx_count": len(events),
        "gross_in": gross_in,
        "gross_out": gross_out,
        "net": net,
        "first_time": events[0]["block_time"] if events else None,
        "first_time_text": events[0]["time"] if events else None,
        "last_time": events[-1]["block_time"] if events else None,
        "last_time_text": events[-1]["time"] if events else None,
        "first_signature": events[0]["signature"] if events else None,
        "last_signature": events[-1]["signature"] if events else None,
        "events": events[:50],
    }


def current_holder_set(mint: str) -> tuple[set[str], list[str]]:
    warnings: list[str] = []
    try:
        _info, holders, holder_warnings = fetch_market_holders(mint)
        warnings.extend(holder_warnings)
    except Exception as exc:
        warnings.append(f"Could not fetch current holder snapshot: {str(exc)[:200]}")
        return set(), warnings
    out = set()
    for item in holders:
        address = item.get("holderWalletAddress") or item.get("holderAddress") or item.get("holder") or item.get("address")
        if isinstance(address, str) and address:
            out.add(address)
    return out, warnings


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# Solana Mint Candidate History Scan", ""]
    lines.append(f"- Mint: `{result['mint']}`")
    lines.append(f"- Window: `{result['window']['from_time']}` to `{result['window']['to_time']}`")
    lines.append(f"- Candidates: {result['summary']['candidate_count']}")
    lines.append(f"- Historical participants found: {result['summary']['participant_count']}")
    lines.append(f"- Historical-only participants: {result['summary']['historical_only_count']}")
    lines.append("")
    lines.append("| Wallet | Net | In | Out | Tx Count | Current Holder | First Seen | Label Hits |")
    lines.append("|---|---:|---:|---:|---:|---|---|---:|")
    for row in result["participants"][:100]:
        hits = len(result["label_hits"].get(row["address"], []))
        lines.append(
            f"| `{shorten(row['address'])}` | {row['net']:.6f} | {row['gross_in']:.6f} | {row['gross_out']:.6f} | {row['tx_count']} | {row['is_current_holder']} | {row.get('first_time_text')} | {hits} |"
        )
    if result["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan candidate Solana addresses for historical mint participation.")
    parser.add_argument("--mint", required=True)
    parser.add_argument("--addresses", nargs="*", default=[])
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    parser.add_argument("--from-time")
    parser.add_argument("--to-time")
    parser.add_argument("--hours-after-create", type=float, default=3.0)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    parser.add_argument("--max-addresses", type=int, default=500)
    parser.add_argument("--per-address-limit", type=int, default=1000)
    parser.add_argument("--sleep", type=float, default=0.0)
    add_common_output_args(parser)
    args = parser.parse_args()

    start = parse_time(args.from_time, args.timezone) if args.from_time else infer_creation_time_market(args.mint)
    if start is None:
        raise RuntimeError("Could not infer mint creation time. Provide --from-time or a mint creation tx/window.")
    end = parse_time(args.to_time, args.timezone) if args.to_time else int(start + args.hours_after_create * 3600)
    candidates, labels = candidate_addresses(args.addresses, args.label_file, args.label_sheets)
    warnings: list[str] = []
    if len(candidates) > args.max_addresses:
        warnings.append(f"Candidate list truncated from {len(candidates)} to {args.max_addresses}; increase --max-addresses for broader coverage.")
        candidates = candidates[: args.max_addresses]
    holders, holder_warnings = current_holder_set(args.mint)
    warnings.extend(holder_warnings)

    scanned = []
    participants = []
    for address in candidates:
        row = scan_address(address, args.mint, start, end, args.rpc_url, args.per_address_limit, args.sleep)
        row["is_current_holder"] = address in holders if holders else None
        row["historical_only"] = row["tx_count"] > 0 and row["is_current_holder"] is False
        scanned.append(row)
        if row["tx_count"] > 0:
            participants.append(row)
    participants.sort(key=lambda x: (x["gross_in"] + x["gross_out"], abs(x["net"])), reverse=True)
    result = {
        "ok": True,
        "tool": "trace_solana_mint_label_history",
        "mint": args.mint,
        "source": "solana_rpc_candidate_scan",
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "summary": {
            "candidate_count": len(candidates),
            "scanned_count": len(scanned),
            "participant_count": len(participants),
            "historical_only_count": sum(1 for row in participants if row.get("historical_only")),
            "current_holder_participant_count": sum(1 for row in participants if row.get("is_current_holder") is True),
        },
        "participants": participants,
        "scanned_nonparticipants_sample": [row for row in scanned if row["tx_count"] == 0][:50],
        "label_hits": label_hits([row["address"] for row in participants], labels),
        "warnings": warnings,
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
