#!/usr/bin/env python3
"""Expand likely related wallets from seed addresses across Solana, EVM, and bridge edges."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from common import (
    EVM_RE,
    SOL_RE,
    ToolError,
    add_common_output_args,
    command_error,
    extract_addresses,
    format_time,
    label_hits,
    load_label_map,
    parse_time,
    print_or_write,
    shorten,
    solana_rpc,
)
from trace_bridge_order import relay_lookup
from trace_evm_wallet import fetch_account_action


DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
DEFAULT_EVM_CHAIN_IDS = [1, 56, 8453, 42161, 10, 137, 43114]
SOLANA_CHAIN = "solana"
CHAIN_NAMES = {
    1: "ethereum",
    10: "optimism",
    56: "bsc",
    137: "polygon",
    8453: "base",
    42161: "arbitrum",
    43114: "avalanche",
    792703809: "solana",
}

SOLANA_PROGRAMS = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFJJZq8L1YdPzjzJVd2",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "SysvarRent111111111111111111111111111111111",
}
SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAMS = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFJJZq8L1YdPzjzJVd2",
}

KNOWN_BRIDGE_ADDRESSES = {
    "7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ",
    "F7p3dFrjRTbtRp8FRF6qHLomXbKRBzpvBLjtQcfcgmNe",
    "gasZT2bpe7mxu5wMgQbvry84vok5CuF2huCEokyC3qh",
    "FzuVV5WeLyWHDuX6SPbeLgqkvePDTzMCRKYAhDbiP3z3",
    "2snHHreXbpJ7UwZxPe37gnUNf7Wx7wv6UKDSR2JckKuS",
}

KNOWN_EVM_SERVICE_ADDRESSES = {
    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "0x0000000000000000000000000000000000000000",
    "0xf70da97812cb96acdf810712aa562db8dfa3dbef",
    "0x4cd00e387622c35bddb9b4c962c136462338bc31",
    "0x4337084d9e255ff0702461cf8895ce9e3b5ff108",
    "0xccc88a9d1b4ed6b0eaba998850414b24f1c315be",
    "0x555ce236c0220695b68341bc48c68d52210cc35b",
    "0xe547d2eed6dd60796013b485d284c17da1194c82",
}

SERVICE_TERMS = (
    "cex",
    "exchange",
    "binance",
    "okx",
    "coinbase",
    "kraken",
    "bybit",
    "gate",
    "mexc",
    "kucoin",
    "router",
    "pool",
    "vault",
    "bridge",
    "solver",
    "depository",
    "relay",
    "mayan",
    "debridge",
    "gas.zip",
    "gaszip",
    "thorchain",
    "near intents",
    "program",
    "token account",
    "temporary",
    "bot",
)

SERVICE_NODE_TYPES = {
    "bridge",
    "dex",
    "dex_pool",
    "cex",
    "service",
    "contract",
    "program",
    "program_owned",
    "token_account",
    "fee_account",
    "market",
    "temporary_account",
    "bonding_curve",
}
POSITIVE_SCORING_EDGE_TYPES = {"direct_value_transfer", "token_owner_transfer"}
NON_SCORING_EDGE_TYPES = {
    "swap_or_dex_route",
    "swap_user_input",
    "swap_user_output",
    "swap_fee",
    "liquidity_action",
    "account_rent_or_close",
    "wrap_unwrap_native",
    "bridge_deposit",
    "bridge_fill",
    "platform_deposit",
    "platform_internal",
    "contract_interaction",
    "unknown_complex",
}
DEX_TERMS = (
    "dex",
    "router",
    "pool",
    "amm",
    "market",
    "bonding curve",
    "pumpswap",
    "pump.fun",
    "raydium",
    "orca",
    "meteora",
    "jupiter",
    "openbook",
    "phoenix",
    "lifinity",
    "saber",
    "mercurial",
)
EVM_DEX_METHOD_TERMS = (
    "swap",
    "multicall",
    "exactinput",
    "exactoutput",
    "addliquidity",
    "removeliquidity",
    "unoswap",
    "uniswap",
    "pancake",
    "curve",
)
EVM_NON_FLOW_METHOD_TERMS = ("approve", "permit", "increaseallowance", "decreaseallowance", "setapprovalforall")
GENERIC_PLATFORM_LOG_TERMS = {"instruction: buy", "instruction: sell", "swap", "route"}


def load_solana_platforms() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "solana_platforms.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("platforms", [])
    data.setdefault("service_account_terms", list(SERVICE_TERMS))
    data.setdefault("non_flow_instruction_types", [])
    return data


SOLANA_PLATFORM_DATA = load_solana_platforms()


def bool_arg(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def node_id(chain: str, address: str) -> str:
    normalized = address.lower() if address.startswith("0x") else address
    return f"{chain}:{normalized}"


def normalize_address(address: str) -> str:
    return address.lower() if address.startswith("0x") else address


def chain_name(chain_id: int) -> str:
    return CHAIN_NAMES.get(int(chain_id), f"evm_{chain_id}")


def confidence(score: int) -> str:
    if score >= 12:
        return "high"
    if score >= 7:
        return "medium"
    if score >= 4:
        return "low"
    return "ignore"


def parse_seed_file(path: str | None) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        raise ToolError(f"Seed file not found: {path}")
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
        return extract_addresses(json.dumps(data))
    if p.suffix.lower() == ".csv":
        found: list[str] = []
        with p.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                found.extend(extract_addresses(" ".join(row)))
        return found
    return extract_addresses(p.read_text(encoding="utf-8", errors="ignore"))


def classify_seed(address: str, requested_chain: str) -> str:
    if requested_chain == "solana":
        return SOLANA_CHAIN
    if requested_chain == "evm":
        return "evm"
    if EVM_RE.fullmatch(address):
        return "evm"
    if SOL_RE.fullmatch(address):
        return SOLANA_CHAIN
    return "unknown"


def label_texts(address: str, labels: dict[str, list[dict[str, Any]]]) -> list[str]:
    key = address.lower() if address.startswith("0x") else address
    return [str(hit.get("text", "")) for hit in labels.get(key, [])]


def _label_text(address: str, labels: dict[str, list[dict[str, Any]]]) -> str:
    return " ".join(label_texts(address, labels)).lower()


def is_service_address(chain: str, address: str, labels: dict[str, list[dict[str, Any]]]) -> bool:
    normalized = normalize_address(address)
    if chain == SOLANA_CHAIN and (address in SOLANA_PROGRAMS or address in KNOWN_BRIDGE_ADDRESSES):
        return True
    if chain != SOLANA_CHAIN and normalized in KNOWN_EVM_SERVICE_ADDRESSES:
        return True
    text = _label_text(address, labels)
    return any(term in text for term in SERVICE_TERMS)


def service_type(chain: str, address: str, labels: dict[str, list[dict[str, Any]]]) -> str:
    normalized = normalize_address(address)
    text = _label_text(address, labels)
    if "cex" in text or "exchange" in text or any(x in text for x in ("binance", "okx", "coinbase", "bybit")):
        return "cex"
    if "bridge" in text or "relay" in text or "mayan" in text or "debridge" in text or "gas" in text:
        return "bridge"
    if "fee" in text and ("protocol" in text or "creator" in text):
        return "fee_account"
    if "token account" in text or "temporary" in text:
        return "token_account"
    if "bonding curve" in text:
        return "bonding_curve"
    if "market" in text:
        return "market"
    if any(term in text for term in DEX_TERMS):
        return "dex"
    if chain == SOLANA_CHAIN and (address in SOLANA_PROGRAMS or address in KNOWN_BRIDGE_ADDRESSES):
        return "bridge" if address in KNOWN_BRIDGE_ADDRESSES else "service"
    if chain != SOLANA_CHAIN and normalized in KNOWN_EVM_SERVICE_ADDRESSES:
        return "bridge"
    return "service"


def classify_address(
    address: str,
    chain: str,
    labels: dict[str, list[dict[str, Any]]],
    rpc_url: str | None = None,
    account_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_address(address)
    text = _label_text(address, labels)
    if chain != SOLANA_CHAIN:
        if normalized in KNOWN_EVM_SERVICE_ADDRESSES:
            return {
                "account_type": "bridge",
                "candidate_eligible": False,
                "owner": None,
                "public_name": text,
                "source": "known_evm_service",
            }
        if any(term in text for term in SERVICE_TERMS) or any(term in text for term in DEX_TERMS):
            return {
                "account_type": service_type(chain, address, labels),
                "candidate_eligible": False,
                "owner": None,
                "public_name": text,
                "source": "label",
            }
        if "contract" in text:
            return {
                "account_type": "contract",
                "candidate_eligible": False,
                "owner": None,
                "public_name": text,
                "source": "label",
            }
        return {"account_type": "wallet", "candidate_eligible": True, "owner": None, "public_name": text, "source": "heuristic"}

    if address in KNOWN_BRIDGE_ADDRESSES:
        return {
            "account_type": "bridge",
            "candidate_eligible": False,
            "owner": None,
            "public_name": text,
            "source": "known_solana_bridge",
        }
    if address in SOLANA_PROGRAMS:
        return {
            "account_type": "program",
            "candidate_eligible": False,
            "owner": None,
            "public_name": text,
            "source": "known_solana_program",
        }
    if any(term in text for term in SERVICE_TERMS) or any(term in text for term in DEX_TERMS):
        return {
            "account_type": service_type(chain, address, labels),
            "candidate_eligible": False,
            "owner": None,
            "public_name": text,
            "source": "label",
        }
    if account_cache is not None and normalized in account_cache:
        return account_cache[normalized]
    if rpc_url:
        try:
            value = solana_rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}], rpc_url) or {}
            info = value.get("value")
        except Exception:
            info = None
        if info:
            owner = info.get("owner")
            data = info.get("data") if isinstance(info, dict) else None
            parsed = data.get("parsed") if isinstance(data, dict) else None
            parsed_info = parsed.get("info") if isinstance(parsed, dict) else None
            if info.get("executable"):
                meta = {
                    "account_type": "program",
                    "candidate_eligible": False,
                    "owner": owner,
                    "public_name": text,
                    "source": "solana_rpc_executable",
                }
            elif owner in TOKEN_PROGRAMS:
                meta = {
                    "account_type": "token_account",
                    "candidate_eligible": False,
                    "owner": parsed_info.get("owner") if isinstance(parsed_info, dict) else owner,
                    "public_name": text,
                    "source": "solana_rpc_token_account",
                }
            elif owner == SYSTEM_PROGRAM:
                meta = {
                    "account_type": "wallet",
                    "candidate_eligible": True,
                    "owner": owner,
                    "public_name": text,
                    "source": "solana_rpc_system_owner",
                }
            else:
                meta = {
                    "account_type": "program_owned",
                    "candidate_eligible": False,
                    "owner": owner,
                    "public_name": text,
                    "source": "solana_rpc_program_owner",
                }
            if account_cache is not None:
                account_cache[normalized] = meta
            return meta
    meta = {"account_type": "wallet", "candidate_eligible": True, "owner": None, "public_name": text, "source": "heuristic_no_rpc"}
    if account_cache is not None:
        account_cache[normalized] = meta
    return meta


class ClusterGraph:
    def __init__(self, labels: dict[str, list[dict[str, Any]]], seed_ids: set[str], rpc_url: str | None = None) -> None:
        self.labels = labels
        self.seed_ids = seed_ids
        self.rpc_url = rpc_url
        self.account_cache: dict[str, dict[str, Any]] = {}
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.score: dict[str, int] = defaultdict(int)
        self.evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.stop_points: list[dict[str, Any]] = []
        self.warnings: list[str] = []

    def add_node(self, chain: str, address: str, node_type: str = "candidate") -> str:
        nid = node_id(chain, address)
        labels = self.labels.get(address.lower() if address.startswith("0x") else address, [])
        meta = classify_address(address, chain, self.labels, self.rpc_url if chain == SOLANA_CHAIN else None, self.account_cache)
        candidate_eligible = bool(meta.get("candidate_eligible"))
        if nid in self.seed_ids:
            node_type = "seed"
            candidate_eligible = True
        if node_type == "candidate" and not candidate_eligible:
            node_type = str(meta.get("account_type") or service_type(chain, address, self.labels))
        node = self.nodes.setdefault(
            nid,
            {
                "id": nid,
                "address": normalize_address(address),
                "chain": chain,
                "type": node_type,
                "account_type": meta.get("account_type"),
                "owner": meta.get("owner"),
                "public_name": meta.get("public_name"),
                "candidate_eligible": candidate_eligible,
                "classification_source": meta.get("source"),
                "labels": labels,
                "score": 0,
            },
        )
        if node.get("type") != "seed" and node_type != "candidate":
            node["type"] = node_type
        if node.get("type") != "seed":
            node["candidate_eligible"] = bool(node.get("candidate_eligible")) and node.get("type") not in SERVICE_NODE_TYPES
        return nid

    def add_edge(self, src_chain: str, src: str, dst_chain: str, dst: str, edge: dict[str, Any]) -> None:
        src_id = self.add_node(src_chain, src, edge.get("from_node_type", "candidate"))
        dst_id = self.add_node(dst_chain, dst, edge.get("to_node_type", "candidate"))
        edge_type = edge.get("type", "direct_value_transfer")
        eligible = edge.get("eligible_for_scoring")
        if eligible is None:
            eligible = edge_type in POSITIVE_SCORING_EDGE_TYPES
        if eligible and (not self.node_scoreable(src_id) or not self.node_scoreable(dst_id)):
            eligible = False
        record = {
            "from": src_id,
            "to": dst_id,
            "from_address": normalize_address(src),
            "to_address": normalize_address(dst),
            "chain": edge.get("chain") or src_chain,
            "type": edge_type,
            "intent": edge.get("intent") or edge_type,
            "tx": edge.get("tx"),
            "time": edge.get("time"),
            "timestamp": edge.get("timestamp"),
            "asset": edge.get("asset"),
            "amount": edge.get("amount"),
            "score": int(edge.get("score") or 0),
            "eligible_for_scoring": bool(eligible),
            "excluded_reason": edge.get("excluded_reason") or (None if eligible else edge.get("reason") or "non_scoring_semantic_edge"),
            "platform": edge.get("platform"),
            "service_nodes": edge.get("service_nodes") or [],
            "input_asset": edge.get("input_asset"),
            "input_amount": edge.get("input_amount"),
            "output_asset": edge.get("output_asset"),
            "output_amount": edge.get("output_amount"),
            "classification": edge.get("classification"),
            "evidence": edge.get("evidence", ""),
            "source": edge.get("source"),
            "hop": edge.get("hop"),
        }
        for service_node in record["service_nodes"]:
            if isinstance(service_node, dict) and service_node.get("address"):
                self.add_node(service_node.get("chain") or record["chain"], service_node["address"], service_node.get("type") or "service")
        key = (
            record["from"],
            record["to"],
            record["type"],
            record.get("tx"),
            record.get("asset"),
            str(record.get("amount")),
        )
        for existing in self.edges:
            existing_key = (
                existing["from"],
                existing["to"],
                existing["type"],
                existing.get("tx"),
                existing.get("asset"),
                str(existing.get("amount")),
            )
            if existing_key == key:
                return
        self.edges.append(record)

    def node_scoreable(self, nid: str) -> bool:
        if nid in self.seed_ids:
            return True
        node = self.nodes.get(nid) or {}
        return bool(node.get("candidate_eligible")) and node.get("type") not in SERVICE_NODE_TYPES

    def add_score(self, nid: str, points: int, reason: str, edge_refs: list[dict[str, Any]]) -> None:
        if nid in self.seed_ids:
            return
        node = self.nodes.get(nid)
        if not node:
            return
        if not self.node_scoreable(nid):
            points = min(points, -5 if points > 0 else points)
        self.score[nid] += points
        self.evidence[nid].append({"score": points, "reason": reason, "edges": edge_refs[:10]})

    def finalize_scores(self) -> None:
        for nid, score in self.score.items():
            if nid in self.nodes:
                self.nodes[nid]["score"] = score


def fetch_signatures_for_window(address: str, start: int | None, end: int | None, rpc_url: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    before = None
    remaining = limit
    while remaining > 0:
        opts: dict[str, Any] = {"limit": min(1000, remaining)}
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
            if end is not None and ts >= end:
                continue
            if start is not None and ts < start:
                stop = True
                continue
            out.append(item)
        before = batch[-1].get("signature")
        remaining -= len(batch)
        if stop or len(batch) < opts["limit"]:
            break
    out.sort(key=lambda x: x.get("blockTime") or 0)
    return out


def account_pubkeys(tx: dict[str, Any]) -> list[str]:
    keys = tx.get("transaction", {}).get("message", {}).get("accountKeys") or []
    out = []
    for key in keys:
        out.append(key.get("pubkey") if isinstance(key, dict) else str(key))
    return out


def signer_pubkeys(tx: dict[str, Any]) -> list[str]:
    keys = tx.get("transaction", {}).get("message", {}).get("accountKeys") or []
    signers = []
    for key in keys:
        if isinstance(key, dict) and key.get("signer") and key.get("pubkey"):
            signers.append(str(key["pubkey"]))
    return signers


def instruction_objects(tx: dict[str, Any]) -> list[dict[str, Any]]:
    message = tx.get("transaction", {}).get("message", {})
    out = [item for item in message.get("instructions") or [] if isinstance(item, dict)]
    meta = tx.get("meta") or {}
    for group in meta.get("innerInstructions") or []:
        for item in group.get("instructions") or []:
            if isinstance(item, dict):
                out.append(item)
    return out


def instruction_program_ids(tx: dict[str, Any]) -> list[str]:
    keys = account_pubkeys(tx)
    out = []
    for item in instruction_objects(tx):
        program_id = item.get("programId")
        if not program_id and item.get("programIdIndex") is not None:
            try:
                program_id = keys[int(item["programIdIndex"])]
            except (ValueError, TypeError, IndexError):
                program_id = None
        if program_id:
            out.append(str(program_id))
    return sorted(set(out))


def parsed_instruction_types(tx: dict[str, Any]) -> list[str]:
    out = []
    for item in instruction_objects(tx):
        parsed = item.get("parsed")
        if isinstance(parsed, dict) and parsed.get("type"):
            out.append(str(parsed["type"]))
        if item.get("type"):
            out.append(str(item["type"]))
    return out


def material_owners(changes: list[dict[str, Any]], negative: bool) -> set[str]:
    owners = set()
    for change in changes:
        delta = float(change.get("delta") or 0)
        if negative and delta < -1e-9:
            owners.add(str(change.get("owner")))
        if not negative and delta > 1e-9:
            owners.add(str(change.get("owner")))
    owners.discard("")
    owners.discard("None")
    return owners


def platform_matches(tx: dict[str, Any], labels: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    labels = labels or {}
    logs = "\n".join(tx.get("meta", {}).get("logMessages") or [])
    logs_l = logs.lower()
    accounts = account_pubkeys(tx)
    account_label_blob = " ".join(_label_text(account, labels) for account in accounts if account)
    programs = set(instruction_program_ids(tx))
    matches = []
    for platform in SOLANA_PLATFORM_DATA.get("platforms", []):
        reasons = []
        specific_reasons = []
        for program_id in platform.get("program_ids") or []:
            if program_id in programs or program_id in accounts:
                reason = f"program_id:{program_id}"
                reasons.append(reason)
                specific_reasons.append(reason)
        for keyword in platform.get("log_keywords") or []:
            if str(keyword).lower() in logs_l:
                reason = f"log:{keyword}"
                reasons.append(reason)
                if str(keyword).strip().lower() not in GENERIC_PLATFORM_LOG_TERMS:
                    specific_reasons.append(reason)
        for term in platform.get("account_label_terms") or []:
            if str(term).lower() in account_label_blob:
                reason = f"label:{term}"
                reasons.append(reason)
                specific_reasons.append(reason)
        if reasons and specific_reasons:
            item = dict(platform)
            item["match_reasons"] = reasons
            matches.append(item)
    return matches


def service_accounts_from_tx(tx: dict[str, Any], labels: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    labels = labels or {}
    out: list[dict[str, Any]] = []
    seen = set()
    for address in account_pubkeys(tx) + instruction_program_ids(tx):
        if not address or address in seen:
            continue
        seen.add(address)
        if address in SOLANA_PROGRAMS or address in KNOWN_BRIDGE_ADDRESSES:
            out.append({"chain": SOLANA_CHAIN, "address": address, "type": service_type(SOLANA_CHAIN, address, labels)})
            continue
        text = _label_text(address, labels)
        if any(term in text for term in SOLANA_PLATFORM_DATA.get("service_account_terms", [])) or any(term in text for term in DEX_TERMS):
            out.append({"chain": SOLANA_CHAIN, "address": address, "type": service_type(SOLANA_CHAIN, address, labels)})
    return out


def solana_owner_deltas(tx: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    meta = tx.get("meta") or {}
    keys = account_pubkeys(tx)
    sol_changes = []
    pre_balances = meta.get("preBalances") or []
    post_balances = meta.get("postBalances") or []
    for idx, address in enumerate(keys):
        if idx >= len(pre_balances) or idx >= len(post_balances):
            continue
        delta = (post_balances[idx] - pre_balances[idx]) / 1_000_000_000
        if abs(delta) > 1e-9:
            sol_changes.append({"owner": address, "mint": "SOL", "delta": delta})
    token_balances: dict[tuple[str | None, str | None, int | None], list[float]] = {}
    for item in meta.get("preTokenBalances") or []:
        key = (item.get("owner"), item.get("mint"), item.get("accountIndex"))
        token_balances.setdefault(key, [0.0, 0.0])[0] = float(item.get("uiTokenAmount", {}).get("uiAmount") or 0)
    for item in meta.get("postTokenBalances") or []:
        key = (item.get("owner"), item.get("mint"), item.get("accountIndex"))
        token_balances.setdefault(key, [0.0, 0.0])[1] = float(item.get("uiTokenAmount", {}).get("uiAmount") or 0)
    token_changes = []
    for (owner, mint, _idx), (pre, post) in token_balances.items():
        delta = post - pre
        if owner and mint and abs(delta) > 1e-12:
            token_changes.append({"owner": owner, "mint": mint, "delta": delta})
    return sol_changes, token_changes


def classify_solana_transaction(
    tx: dict[str, Any],
    labels: dict[str, list[dict[str, Any]]] | None = None,
    sol_changes: list[dict[str, Any]] | None = None,
    token_changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    labels = labels or {}
    if sol_changes is None or token_changes is None:
        sol_changes, token_changes = solana_owner_deltas(tx)
    matches = platform_matches(tx, labels)
    program_ids = instruction_program_ids(tx)
    instruction_types = parsed_instruction_types(tx)
    instruction_blob = " ".join(instruction_types).lower()
    logs = "\n".join(tx.get("meta", {}).get("logMessages") or [])
    logs_l = logs.lower()
    signers = signer_pubkeys(tx)
    service_nodes = service_accounts_from_tx(tx, labels)
    platform = matches[0]["id"] if matches else None
    reason = "; ".join(matches[0].get("match_reasons", [])[:5]) if matches else ""
    non_core_program_ids = [program_id for program_id in program_ids if program_id not in SOLANA_PROGRAMS]
    if matches and any(match.get("category") == "dex" for match in matches):
        return {
            "intent": "swap_or_dex_route",
            "platform": platform,
            "program_ids": program_ids,
            "program_labels": [match.get("name") for match in matches],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": signers,
            "confidence": "high",
            "reason": reason or "matched Solana DEX/platform dictionary",
        }
    if any(address in KNOWN_BRIDGE_ADDRESSES for address in account_pubkeys(tx) + program_ids):
        return {
            "intent": "bridge_order",
            "platform": "known_bridge",
            "program_ids": program_ids,
            "program_labels": [],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": signers,
            "confidence": "medium",
            "reason": "known bridge account/program present",
        }
    if any(term in logs_l for term in ("swap", "route", "amm", "pool", "bonding curve", "raydium", "orca", "meteora", "jupiter")):
        return {
            "intent": "swap_or_dex_route",
            "platform": platform or "unknown_dex_route",
            "program_ids": program_ids,
            "program_labels": [],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": signers,
            "confidence": "medium",
            "reason": "swap/router/AMM keyword in logs",
        }
    token_neg = material_owners(token_changes or [], True)
    token_pos = material_owners(token_changes or [], False)
    sol_neg = material_owners(sol_changes or [], True)
    sol_pos = material_owners(sol_changes or [], False)
    has_wrap = "syncnative" in instruction_blob or ("withdraw" in instruction_blob and "wrapped" in logs_l)
    has_account_noise = any(
        item.lower() in {x.lower() for x in SOLANA_PLATFORM_DATA.get("non_flow_instruction_types", [])}
        for item in instruction_types
    )
    if token_neg and token_pos and len(token_neg) == 1 and len(token_pos) == 1 and not non_core_program_ids:
        return {
            "intent": "token_transfer",
            "platform": None,
            "program_ids": program_ids,
            "program_labels": [],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": sorted(token_neg | token_pos),
            "confidence": "medium",
            "reason": "single owner-level SPL token debit and credit",
        }
    if has_wrap:
        intent = "wrap_unwrap_native"
    elif has_account_noise:
        intent = "account_create_close"
    elif not sol_neg and not sol_pos and not token_neg and not token_pos:
        intent = "fee_or_rent_noise"
    else:
        intent = None
    if intent is not None:
        return {
            "intent": intent,
            "platform": platform,
            "program_ids": program_ids,
            "program_labels": [match.get("name") for match in matches],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": signers,
            "confidence": "low",
            "reason": "not a clean direct owner-to-owner transfer",
        }
    if sol_neg and sol_pos and len(sol_neg) == 1 and len(sol_pos) == 1 and not token_changes and not non_core_program_ids:
        return {
            "intent": "plain_transfer",
            "platform": None,
            "program_ids": program_ids,
            "program_labels": [],
            "signers": signers,
            "service_accounts": service_nodes,
            "user_accounts": sorted(sol_neg | sol_pos),
            "confidence": "medium",
            "reason": "single SOL debit and credit",
        }
    return {
        "intent": "unknown_complex",
        "platform": platform,
        "program_ids": program_ids,
        "program_labels": [match.get("name") for match in matches],
        "signers": signers,
        "service_accounts": service_nodes,
        "user_accounts": signers,
        "confidence": "low",
        "reason": "not a clean direct owner-to-owner transfer",
    }


def pair_deltas(
    changes: list[dict[str, Any]],
    tx_hash: str,
    timestamp: int | None,
    source: str,
    edge_type: str,
    classification: dict[str, Any] | None = None,
    eligible_for_scoring: bool | None = None,
) -> list[dict[str, Any]]:
    edges = []
    by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for change in changes:
        by_asset[str(change.get("mint"))].append(change)
    for asset, rows in by_asset.items():
        negatives = sorted([r for r in rows if r["delta"] < 0], key=lambda x: abs(x["delta"]), reverse=True)
        positives = sorted([r for r in rows if r["delta"] > 0], key=lambda x: x["delta"], reverse=True)
        for neg in negatives[:5]:
            for pos in positives[:5]:
                if neg["owner"] == pos["owner"]:
                    continue
                amount = min(abs(neg["delta"]), pos["delta"])
                if amount <= 0:
                    continue
                edges.append(
                    {
                        "from": neg["owner"],
                        "to": pos["owner"],
                        "asset": asset,
                        "amount": amount,
                        "tx": tx_hash,
                        "timestamp": timestamp,
                        "time": format_time(timestamp),
                        "type": edge_type,
                        "intent": classification.get("intent") if classification else edge_type,
                        "source": source,
                        "score": 0,
                        "eligible_for_scoring": edge_type in POSITIVE_SCORING_EDGE_TYPES if eligible_for_scoring is None else eligible_for_scoring,
                        "classification": classification,
                        "evidence": f"{source} balance delta pair {shorten(tx_hash)} {amount:g} {asset}",
                    }
                )
    return edges


def _edge_involves_address(edge: dict[str, Any], address: str) -> bool:
    return normalize_address(edge.get("from", "")) == normalize_address(address) or normalize_address(edge.get("to", "")) == normalize_address(address)


def summarize_user_asset_changes(address: str, changes: list[dict[str, Any]], negative: bool) -> tuple[str | None, float | None]:
    rows = []
    for change in changes:
        if normalize_address(str(change.get("owner"))) != normalize_address(address):
            continue
        delta = float(change.get("delta") or 0)
        if negative and delta < 0:
            rows.append((str(change.get("mint")), abs(delta)))
        if not negative and delta > 0:
            rows.append((str(change.get("mint")), delta))
    if not rows:
        return None, None
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[0]


def non_scoring_self_edge(
    address: str,
    edge_type: str,
    signature: str,
    timestamp: int | None,
    classification: dict[str, Any],
    source: str = "solana_rpc",
) -> dict[str, Any]:
    return {
        "from": address,
        "to": address,
        "asset": None,
        "amount": None,
        "tx": signature,
        "timestamp": timestamp,
        "time": format_time(timestamp),
        "type": edge_type,
        "intent": classification.get("intent"),
        "source": source,
        "score": 0,
        "eligible_for_scoring": False,
        "platform": classification.get("platform"),
        "service_nodes": classification.get("service_accounts") or [],
        "classification": {k: v for k, v in classification.items() if k != "_tx"},
        "evidence": f"{classification.get('intent')} {shorten(signature)}: {classification.get('reason')}",
    }


def solana_edges_from_transaction(
    address: str,
    signature: str,
    timestamp: int | None,
    tx: dict[str, Any],
    labels: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    sol_changes, token_changes = solana_owner_deltas(tx)
    classification = classify_solana_transaction(tx, labels, sol_changes, token_changes)
    intent = classification.get("intent")
    classification_for_edge = {k: v for k, v in classification.items() if k != "_tx"}
    if intent == "swap_or_dex_route":
        in_asset, in_amount = summarize_user_asset_changes(address, sol_changes + token_changes, True)
        out_asset, out_amount = summarize_user_asset_changes(address, sol_changes + token_changes, False)
        return [
            {
                "from": address,
                "to": address,
                "asset": out_asset or in_asset,
                "amount": out_amount or in_amount,
                "tx": signature,
                "timestamp": timestamp,
                "time": format_time(timestamp),
                "type": "swap_or_dex_route",
                "intent": intent,
                "source": "solana_rpc_semantic_classifier",
                "score": 0,
                "eligible_for_scoring": False,
                "platform": classification.get("platform"),
                "service_nodes": classification.get("service_accounts") or [],
                "input_asset": in_asset,
                "input_amount": in_amount,
                "output_asset": out_asset,
                "output_amount": out_amount,
                "classification": classification_for_edge,
                "evidence": f"DEX/platform route {shorten(signature)} platform {classification.get('platform') or 'unknown'}; shared pool/router interaction is not candidate evidence",
            }
        ]
    if intent == "bridge_order":
        edges = []
        for edge in pair_deltas(sol_changes + token_changes, signature, timestamp, "solana_rpc_bridge_candidate", "bridge_deposit", classification_for_edge, False):
            if _edge_involves_address(edge, address):
                edge["platform"] = classification.get("platform")
                edge["service_nodes"] = classification.get("service_accounts") or []
                edges.append(edge)
        if edges:
            return edges
        return [non_scoring_self_edge(address, "bridge_deposit", signature, timestamp, classification_for_edge)]
    if intent == "plain_transfer":
        return [edge for edge in pair_deltas(sol_changes, signature, timestamp, "solana_rpc", "direct_value_transfer", classification_for_edge, True) if _edge_involves_address(edge, address)]
    if intent == "token_transfer":
        return [
            edge
            for edge in pair_deltas(token_changes, signature, timestamp, "solana_rpc_token_owner_delta", "token_owner_transfer", classification_for_edge, True)
            if _edge_involves_address(edge, address)
        ]
    if intent == "account_create_close":
        return [non_scoring_self_edge(address, "account_rent_or_close", signature, timestamp, classification_for_edge)]
    if intent == "wrap_unwrap_native":
        return [non_scoring_self_edge(address, "wrap_unwrap_native", signature, timestamp, classification_for_edge)]
    if intent == "fee_or_rent_noise":
        return []
    return [non_scoring_self_edge(address, "unknown_complex", signature, timestamp, classification_for_edge)]


def solana_edges_for_address(
    address: str,
    start: int | None,
    end: int | None,
    rpc_url: str,
    limit: int,
    labels: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    edges = []
    seen_txs: set[str] = set()
    for sig in fetch_signatures_for_window(address, start, end, rpc_url, limit):
        signature = sig.get("signature")
        if not signature or signature in seen_txs:
            continue
        seen_txs.add(signature)
        tx = solana_rpc("getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}], rpc_url)
        if not tx:
            continue
        timestamp = sig.get("blockTime")
        edges.extend(solana_edges_from_transaction(address, signature, timestamp, tx, labels))
    return edges


def evm_api_key(provider: str) -> str | None:
    if provider == "etherscan":
        return os.getenv("ETHERSCAN_API_KEY")
    if provider == "blockscout":
        return os.getenv("BLOCKSCOUT_API_KEY")
    return None


def choose_evm_provider(requested: str) -> str | None:
    if requested != "auto":
        return requested
    if os.getenv("ETHERSCAN_API_KEY"):
        return "etherscan"
    if os.getenv("BLOCKSCOUT_API_KEY"):
        return "blockscout"
    return None


def _evm_value_amount(row: dict[str, Any]) -> float:
    try:
        return float(row.get("value") or 0)
    except (TypeError, ValueError):
        return 0.0


def classify_evm_action(row: dict[str, Any], action: str, labels: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    labels = labels or {}
    src = str(row.get("from") or "").lower()
    dst = str(row.get("to") or "").lower()
    method_blob = " ".join(str(row.get(key) or "") for key in ("functionName", "methodId", "input")).lower().replace("_", "")
    src_service = is_service_address("evm", src, labels) if src else False
    dst_service = is_service_address("evm", dst, labels) if dst else False
    if any(term in method_blob for term in EVM_NON_FLOW_METHOD_TERMS):
        return {
            "intent": "contract_interaction",
            "edge_type": "contract_interaction",
            "eligible_for_scoring": False,
            "reason": "approve/permit/allowance update is not fund movement",
        }
    if any(term in method_blob for term in EVM_DEX_METHOD_TERMS):
        return {
            "intent": "swap_or_dex_route",
            "edge_type": "swap_or_dex_route",
            "eligible_for_scoring": False,
            "reason": "router/multicall/swap-like EVM method",
        }
    if action == "txlist" and method_blob and row.get("input") not in (None, "", "0x") and _evm_value_amount(row) <= 0:
        return {
            "intent": "contract_interaction",
            "edge_type": "contract_interaction",
            "eligible_for_scoring": False,
            "reason": "contract call with no native value",
        }
    if src_service or dst_service:
        return {
            "intent": "platform_or_service_transfer",
            "edge_type": "platform_internal" if src_service and dst_service else "platform_deposit",
            "eligible_for_scoring": False,
            "reason": "service/platform endpoint",
        }
    if action == "tokentx":
        return {
            "intent": "token_transfer",
            "edge_type": "token_owner_transfer",
            "eligible_for_scoring": True,
            "reason": "ERC20 transfer event between non-service endpoints",
        }
    return {
        "intent": "plain_transfer",
        "edge_type": "direct_value_transfer",
        "eligible_for_scoring": True,
        "reason": "native/internal value transfer between non-service endpoints",
    }


def evm_edges_for_address(
    address: str,
    chain_id: int,
    start: int | None,
    end: int | None,
    provider: str,
    limit: int,
    labels: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    key = evm_api_key(provider)
    if not key:
        raise ToolError(f"Missing {provider.upper()} API key for EVM cluster expansion.")
    chain = chain_name(chain_id)
    out = []
    actions = {"evm_native": "txlist", "evm_erc20": "tokentx", "evm_internal": "txlistinternal"}
    address_l = address.lower()
    for edge_type, action in actions.items():
        try:
            rows = fetch_account_action(provider, chain_id, action, address, key, limit)
        except Exception as exc:
            raise ToolError(f"{provider} {action} failed for {address} on {chain_id}: {exc}") from exc
        for row in rows:
            try:
                ts = int(row.get("timeStamp") or row.get("timestamp") or 0)
            except (TypeError, ValueError):
                ts = None
            if ts is not None and start is not None and ts < start:
                continue
            if ts is not None and end is not None and ts >= end:
                continue
            src = str(row.get("from") or "").lower()
            dst = str(row.get("to") or "").lower()
            if not EVM_RE.fullmatch(src) or not EVM_RE.fullmatch(dst):
                continue
            if src != address_l and dst != address_l:
                continue
            classification = classify_evm_action(row, action, labels)
            if action == "txlist" and classification["edge_type"] == "direct_value_transfer" and _evm_value_amount(row) <= 0:
                continue
            decimals = row.get("tokenDecimal")
            value = row.get("value")
            amount = value
            if decimals not in (None, "") and str(value).isdigit():
                amount = str(int(value) / (10 ** int(decimals)))
            out.append(
                {
                    "from": src,
                    "to": dst,
                    "chain": chain,
                    "chain_id": chain_id,
                    "asset": row.get("tokenSymbol") or row.get("contractAddress") or "native",
                    "amount": amount,
                    "tx": row.get("hash"),
                    "timestamp": ts,
                    "time": format_time(ts) if ts else None,
                    "type": classification["edge_type"],
                    "intent": classification["intent"],
                    "source": provider,
                    "score": 0,
                    "eligible_for_scoring": classification["eligible_for_scoring"],
                    "classification": classification,
                    "evidence": f"{provider} {action} {shorten(row.get('hash'))}: {classification['reason']}",
                }
            )
    return out


def edge_neighbor(edge: dict[str, Any], address: str) -> str | None:
    addr = normalize_address(address)
    src = normalize_address(str(edge.get("from") or ""))
    dst = normalize_address(str(edge.get("to") or ""))
    if src == addr:
        return dst
    if dst == addr:
        return src
    return None


def edge_scoreable(graph: ClusterGraph, edge: dict[str, Any]) -> bool:
    if edge.get("type") not in POSITIVE_SCORING_EDGE_TYPES:
        return False
    if not edge.get("eligible_for_scoring"):
        return False
    return graph.node_scoreable(edge["from"]) and graph.node_scoreable(edge["to"]) and edge["from"] != edge["to"]


def edge_expandable(graph: ClusterGraph, edge: dict[str, Any], next_id: str) -> bool:
    if edge.get("type") in NON_SCORING_EDGE_TYPES:
        return False
    if not edge.get("eligible_for_scoring"):
        return False
    return graph.node_scoreable(next_id)


def analyze_common_patterns(graph: ClusterGraph, seed_ids: set[str], min_score: int) -> list[dict[str, Any]]:
    by_to: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_from: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seed_direct_pairs: list[dict[str, Any]] = []
    for edge in graph.edges:
        if not edge_scoreable(graph, edge):
            continue
        by_to[edge["to"]].append(edge)
        by_from[edge["from"]].append(edge)
        if edge["from"] in seed_ids and edge["to"] in seed_ids:
            seed_direct_pairs.append(edge)
            graph.add_score(edge["to"], 8, "seed-to-seed direct transfer", [edge])
        if edge["to"] in seed_ids and edge["from"] in seed_ids:
            graph.add_score(edge["from"], 8, "seed-to-seed direct transfer", [edge])
    for target, incoming in by_to.items():
        seed_sources = [e for e in incoming if e["from"] in seed_ids]
        unique_sources = {e["from"] for e in seed_sources}
        if target not in seed_ids and len(unique_sources) >= 2:
            graph.add_score(target, 7, "multiple seeds sent to the same non-service recipient", seed_sources)
    for source, outgoing in by_from.items():
        seed_targets = [e for e in outgoing if e["to"] in seed_ids]
        unique_targets = {e["to"] for e in seed_targets}
        if source not in seed_ids and len(unique_targets) >= 2:
            graph.add_score(source, 7, "same non-service address funded multiple seeds", seed_targets)
    all_seed_neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if not edge_scoreable(graph, edge):
            continue
        if edge["from"] in seed_ids and edge["to"] not in seed_ids:
            all_seed_neighbors[edge["to"]].add(edge["from"])
        if edge["to"] in seed_ids and edge["from"] not in seed_ids:
            all_seed_neighbors[edge["from"]].add(edge["to"])
    for candidate, seeds in all_seed_neighbors.items():
        if len(seeds) >= 2:
            graph.add_score(candidate, 5, "same address is one-hop neighbor of multiple seeds", [e for e in graph.edges if e["from"] == candidate or e["to"] == candidate])
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for edge in graph.edges:
        if not edge_scoreable(graph, edge):
            continue
        adjacency[edge["from"]].append((edge["to"], edge))
        adjacency[edge["to"]].append((edge["from"], edge))
    multi_seed_reach: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for seed in seed_ids:
        queue: deque[tuple[str, int, list[dict[str, Any]]]] = deque([(seed, 0, [])])
        seen = {seed}
        while queue:
            current, depth, path = queue.popleft()
            if depth >= 3:
                continue
            for nxt, edge in adjacency.get(current, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                next_path = path + [edge]
                multi_seed_reach[nxt][seed] = next_path
                queue.append((nxt, depth + 1, next_path))
    for candidate, paths_by_seed in multi_seed_reach.items():
        if candidate in seed_ids:
            continue
        if len(paths_by_seed) >= 2:
            evidence_edges = []
            for path in list(paths_by_seed.values())[:3]:
                evidence_edges.extend(path[:3])
            graph.add_score(candidate, 6, "multi-hop paths from multiple seeds converge on this address", evidence_edges)
    for nid, node in graph.nodes.items():
        if nid not in seed_ids and not graph.node_scoreable(nid):
            graph.add_score(nid, -5, "service/infrastructure node is excluded from candidate scoring", [])
    graph.finalize_scores()
    candidates = []
    for nid, node in graph.nodes.items():
        if nid in seed_ids:
            continue
        if not graph.node_scoreable(nid):
            continue
        score = int(node.get("score") or 0)
        if score >= min_score:
            candidates.append(
                {
                    "id": nid,
                    "address": node.get("address"),
                    "chain": node.get("chain"),
                    "type": node.get("type"),
                    "score": score,
                    "confidence": confidence(score),
                    "evidence": graph.evidence.get(nid, []),
                }
            )
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def follow_relay_for_edge(graph: ClusterGraph, edge: dict[str, Any], limit: int = 5) -> bool:
    tx_hash = edge.get("tx")
    if not tx_hash:
        return False
    try:
        result = relay_lookup(tx_hash, None, limit)
    except Exception:
        return False
    orders = result.get("orders") or []
    if not orders:
        return False
    matched = False
    for order in orders:
        recipient = order.get("recipient")
        if not recipient:
            continue
        out_txs = order.get("out_txs") or []
        dst_chain_id = out_txs[0].get("chain_id") if out_txs else None
        dst_chain = chain_name(int(dst_chain_id)) if str(dst_chain_id or "").isdigit() else "unknown"
        src_chain = edge.get("chain") or SOLANA_CHAIN
        src = edge.get("from")
        if not src:
            continue
        graph.add_edge(
            src_chain,
            src,
            dst_chain,
            recipient,
            {
                "type": "bridge",
                "chain": src_chain,
                "tx": tx_hash,
                "timestamp": edge.get("timestamp"),
                "time": edge.get("time"),
                "asset": order.get("currency"),
                "amount": order.get("price"),
                "score": 6,
                "source": "relay_orderbook",
                "evidence": f"Relay order {order.get('id')} status {order.get('status')}",
            },
        )
        nid = node_id(dst_chain, recipient)
        graph.add_score(nid, 6, "bridge order landed on destination recipient", [])
        matched = True
    return matched


def build_markdown(result: dict[str, Any]) -> str:
    lines = ["# Cross-Chain Cluster Expansion", ""]
    lines.append("## Conclusion")
    lines.append("")
    high = [c for c in result["candidates"] if c["confidence"] == "high"]
    med = [c for c in result["candidates"] if c["confidence"] == "medium"]
    low = [c for c in result["candidates"] if c["confidence"] == "low"]
    service_nodes = [n for n in result["nodes"] if n.get("type") != "seed" and not n.get("candidate_eligible")]
    platform_edges = [e for e in result["edges"] if e.get("type") in {"swap_or_dex_route", "contract_interaction", "platform_deposit", "platform_internal"}]
    excluded_edges = [e for e in result["edges"] if not e.get("eligible_for_scoring")]
    lines.append(f"- Candidates above threshold: {len(result['candidates'])} (high {len(high)}, medium {len(med)}, low {len(low)}).")
    lines.append(f"- Service/infrastructure nodes excluded from candidate scoring: {len(service_nodes)}.")
    if platform_edges:
        lines.append(f"- Shared platform/DEX interactions recorded but not scored: {len(platform_edges)}.")
    if result["summary"].get("bridge_edges"):
        lines.append(f"- Bridge/orderbook edges found: {result['summary']['bridge_edges']}.")
    if result["warnings"]:
        lines.append(f"- Coverage warnings: {len(result['warnings'])}; review stop points before treating the cluster as closed.")
    lines.append("")
    lines.append("## Seed Overview")
    lines.append("")
    for seed in result["seed_addresses"]:
        lines.append(f"- `{seed['chain']}` `{seed['address']}`")
    lines.append("")
    lines.append("## Candidate Related Wallets")
    lines.append("")
    if result["candidates"]:
        lines.append("| Confidence | Score | Chain | Type | Address | Main Evidence |")
        lines.append("|---|---:|---|---|---|---|")
        for row in result["candidates"][:100]:
            ev = row.get("evidence") or []
            reason = ev[0].get("reason") if ev else ""
            lines.append(f"| {row['confidence']} | {row['score']} | {row['chain']} | {row['type']} | `{row['address']}` | {reason} |")
    else:
        lines.append("No candidate crossed the configured score threshold.")
    lines.append("")
    lines.append("## Service / Infrastructure Nodes")
    lines.append("")
    if service_nodes:
        lines.append("| Chain | Type | Address | Source | Label |")
        lines.append("|---|---|---|---|---|")
        for node in service_nodes[:80]:
            label = "; ".join(str(hit.get("text", "")) for hit in node.get("labels") or [])[:120]
            lines.append(f"| {node.get('chain')} | {node.get('type')} | `{node.get('address')}` | {node.get('classification_source')} | {label} |")
    else:
        lines.append("No service/infrastructure node was identified in the inspected graph.")
    lines.append("")
    lines.append("## Shared Platform Interactions")
    lines.append("")
    if platform_edges:
        for edge in platform_edges[:80]:
            detail = ""
            if edge.get("type") == "swap_or_dex_route":
                detail = f" input `{edge.get('input_amount')}` `{edge.get('input_asset')}` output `{edge.get('output_amount')}` `{edge.get('output_asset')}`"
            lines.append(
                f"- `{edge['type']}` platform `{edge.get('platform') or 'unknown'}` `{edge['from']}` tx `{shorten(edge.get('tx'))}` time `{edge.get('time')}`{detail}. This is protocol activity, not wallet-cluster proof."
            )
    else:
        lines.append("No DEX/platform interaction was separated in the inspected scope.")
    lines.append("")
    lines.append("## Excluded From Scoring")
    lines.append("")
    if excluded_edges:
        for edge in excluded_edges[:80]:
            lines.append(f"- `{edge['type']}` `{edge['from']}` -> `{edge['to']}` tx `{shorten(edge.get('tx'))}` reason `{edge.get('excluded_reason')}`")
    else:
        lines.append("No edge was excluded after semantic classification.")
    lines.append("")
    lines.append("## Relationship Evidence")
    lines.append("")
    scoring_edges = [edge for edge in result["edges"] if edge.get("eligible_for_scoring")]
    for edge in scoring_edges[:80]:
        lines.append(
            f"- `{edge['type']}` `{edge['from']}` -> `{edge['to']}` asset `{edge.get('asset')}` amount `{edge.get('amount')}` tx `{shorten(edge.get('tx'))}` time `{edge.get('time')}` source `{edge.get('source')}`"
        )
    if not scoring_edges:
        lines.append("No scoring-eligible wallet-to-wallet transfer edge was found in the inspected scope.")
    lines.append("")
    lines.append("## Stop Points And Coverage")
    lines.append("")
    if result["stop_points"]:
        for item in result["stop_points"][:50]:
            lines.append(f"- `{item.get('status')}` `{item.get('node')}`: {item.get('reason')}")
    else:
        lines.append("- No explicit service stop point was produced in the inspected scope.")
    if result["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append("## Risk Notes")
    lines.append("")
    lines.append("- This output is chain-analysis clustering, not identity proof.")
    lines.append("- Shared Pump.fun/PumpSwap/Raydium/Orca/Meteora/Jupiter or other DEX interaction does not prove the wallets are the same cluster.")
    lines.append("- DEX routers, pools, bridge solvers, CEX hot wallets, token accounts, programs, and high-frequency service nodes are excluded from positive scoring.")
    lines.append("- Deeper hops increase false positives; review score evidence before merging candidates into a real entity cluster.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-chain multi-hop cluster expansion from seed wallets.")
    parser.add_argument("--seed-addresses", nargs="*", default=[])
    parser.add_argument("--seed-file")
    parser.add_argument("--chain", choices=["solana", "evm", "auto"], default="auto")
    parser.add_argument("--from-time")
    parser.add_argument("--to-time")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--post-window-hours", type=float, default=72.0)
    parser.add_argument("--max-hop-solana", type=int, default=2)
    parser.add_argument("--max-hop-evm", type=int, default=1)
    parser.add_argument("--bridge-follow", type=bool_arg, default=True)
    parser.add_argument("--min-score", type=int, default=5)
    parser.add_argument("--label-file")
    parser.add_argument("--label-sheets")
    parser.add_argument("--evm-chain-ids", default="1,56,8453,42161,10,137,43114")
    parser.add_argument("--evm-provider", choices=["auto", "etherscan", "blockscout"], default="auto")
    parser.add_argument("--include-low-confidence", action="store_true")
    parser.add_argument("--stop-at-platform", type=bool_arg, default=True)
    parser.add_argument("--max-edges-per-node", type=int, default=100)
    parser.add_argument("--max-total-nodes", type=int, default=2000)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    parser.add_argument("--solana-limit", type=int, default=100)
    parser.add_argument("--evm-limit", type=int, default=100)
    add_common_output_args(parser)
    args = parser.parse_args()

    raw_seeds = args.seed_addresses + parse_seed_file(args.seed_file)
    seeds = []
    seen_seed: set[str] = set()
    for addr in raw_seeds:
        if not isinstance(addr, str):
            continue
        addr = addr.strip()
        if not addr:
            continue
        chain_kind = classify_seed(addr, args.chain)
        if chain_kind == "unknown":
            continue
        key = f"{chain_kind}:{normalize_address(addr)}"
        if key in seen_seed:
            continue
        seen_seed.add(key)
        seeds.append({"address": normalize_address(addr), "chain_kind": chain_kind})
    if not seeds:
        raise ToolError("No valid seed addresses were provided.")

    start = parse_time(args.from_time, args.timezone)
    base_end = parse_time(args.to_time, args.timezone)
    end = base_end
    if end is not None and args.post_window_hours:
        end = int(end + args.post_window_hours * 3600)
    labels = load_label_map(args.label_file, args.label_sheets)
    seed_ids: set[str] = set()
    evm_chain_ids = [int(x.strip()) for x in args.evm_chain_ids.split(",") if x.strip()]
    for seed in seeds:
        if seed["chain_kind"] == SOLANA_CHAIN:
            seed_ids.add(node_id(SOLANA_CHAIN, seed["address"]))
        else:
            for chain_id in evm_chain_ids:
                seed_ids.add(node_id(chain_name(chain_id), seed["address"]))
    graph = ClusterGraph(labels, seed_ids, args.rpc_url)
    for seed in seeds:
        if seed["chain_kind"] == SOLANA_CHAIN:
            graph.add_node(SOLANA_CHAIN, seed["address"], "seed")
        else:
            for chain_id in evm_chain_ids:
                graph.add_node(chain_name(chain_id), seed["address"], "seed")

    queue: deque[tuple[str, str, int]] = deque()
    for seed in seeds:
        if seed["chain_kind"] == SOLANA_CHAIN:
            queue.append((SOLANA_CHAIN, seed["address"], 0))
        else:
            for chain_id in evm_chain_ids:
                queue.append((chain_name(chain_id), seed["address"], 0))
    visited: set[tuple[str, str, int]] = set()
    evm_provider = choose_evm_provider(args.evm_provider)

    while queue and len(graph.nodes) < args.max_total_nodes:
        chain, address, hop = queue.popleft()
        key = (chain, normalize_address(address), hop)
        if key in visited:
            continue
        visited.add(key)
        current_id = graph.add_node(chain, address, "seed" if node_id(chain, address) in seed_ids else "candidate")
        if args.stop_at_platform and current_id not in seed_ids and not graph.node_scoreable(current_id):
            graph.stop_points.append({"node": node_id(chain, address), "status": "closed_to_platform_wallet", "reason": "service or infrastructure node"})
            continue
        try:
            if chain == SOLANA_CHAIN:
                if hop >= args.max_hop_solana:
                    continue
                raw_edges = solana_edges_for_address(address, start, end, args.rpc_url, min(args.solana_limit, args.max_edges_per_node), labels)
                for edge in raw_edges[: args.max_edges_per_node]:
                    src, dst = edge["from"], edge["to"]
                    edge["hop"] = hop + 1
                    graph.add_edge(SOLANA_CHAIN, src, SOLANA_CHAIN, dst, edge)
                    if args.bridge_follow and (src in KNOWN_BRIDGE_ADDRESSES or dst in KNOWN_BRIDGE_ADDRESSES):
                        if not follow_relay_for_edge(graph, edge):
                            graph.warnings.append(f"bridge_orderbook_missing for possible bridge tx {shorten(edge.get('tx'))}")
                    neighbor = edge_neighbor(edge, address)
                    neighbor_id = node_id(SOLANA_CHAIN, neighbor) if neighbor else None
                    if neighbor and neighbor_id and edge_expandable(graph, edge, neighbor_id) and hop + 1 < args.max_hop_solana:
                        queue.append((SOLANA_CHAIN, neighbor, hop + 1))
            else:
                if hop >= args.max_hop_evm:
                    continue
                if evm_provider is None:
                    graph.warnings.append("EVM expansion skipped: missing ETHERSCAN_API_KEY or BLOCKSCOUT_API_KEY.")
                    continue
                chain_id = next((cid for cid, name in CHAIN_NAMES.items() if name == chain), None)
                if chain_id is None or chain_id == 792703809:
                    continue
                raw_edges = evm_edges_for_address(address, chain_id, start, end, evm_provider, min(args.evm_limit, args.max_edges_per_node), labels)
                for edge in raw_edges[: args.max_edges_per_node]:
                    src, dst = edge["from"], edge["to"]
                    edge["hop"] = hop + 1
                    graph.add_edge(chain, src, chain, dst, edge)
                    if args.bridge_follow:
                        if (src in KNOWN_EVM_SERVICE_ADDRESSES or dst in KNOWN_EVM_SERVICE_ADDRESSES) and not follow_relay_for_edge(graph, edge):
                            graph.warnings.append(f"bridge_orderbook_missing for possible EVM bridge tx {shorten(edge.get('tx'))}")
                    neighbor = edge_neighbor(edge, address)
                    neighbor_id = node_id(chain, neighbor) if neighbor else None
                    if neighbor and neighbor_id and edge_expandable(graph, edge, neighbor_id) and hop + 1 < args.max_hop_evm:
                        queue.append((chain, neighbor, hop + 1))
        except Exception as exc:
            graph.warnings.append(f"Expansion skipped for {chain}:{shorten(address)} hop {hop}: {str(exc)[:240]}")

    candidates = analyze_common_patterns(graph, seed_ids, 4 if args.include_low_confidence else args.min_score)
    if not args.include_low_confidence:
        candidates = [row for row in candidates if row["score"] >= args.min_score]
    graph.finalize_scores()
    cluster_score = max([row["score"] for row in candidates], default=0)
    candidate_ids = [row["id"] for row in candidates]
    result = {
        "ok": True,
        "tool": "expand_crosschain_cluster",
        "status": "not_closed_insufficient_api_coverage" if graph.warnings else "cluster_expansion_completed",
        "window": {"from": start, "to": end, "from_time": format_time(start), "to_time": format_time(end)},
        "seed_addresses": [
            {"address": seed["address"], "chain": seed["chain_kind"] if seed["chain_kind"] == SOLANA_CHAIN else "evm"} for seed in seeds
        ],
        "summary": {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "candidate_count": len(candidates),
            "bridge_edges": sum(1 for edge in graph.edges if edge.get("type") == "bridge"),
            "max_hop_solana": args.max_hop_solana,
            "max_hop_evm": args.max_hop_evm,
        },
        "nodes": list(graph.nodes.values()),
        "edges": graph.edges,
        "clusters": [
            {
                "id": "cluster_1",
                "seed_addresses": sorted(seed_ids),
                "candidate_addresses": candidate_ids,
                "score": cluster_score,
                "confidence": confidence(cluster_score),
                "main_evidence": [item for row in candidates[:10] for item in row.get("evidence", [])[:2]],
            }
        ],
        "candidates": candidates,
        "label_hits": label_hits([node["address"] for node in graph.nodes.values()], labels),
        "stop_points": graph.stop_points,
        "warnings": graph.warnings,
        "limitations": [
            "This is chain-analysis clustering, not identity attribution.",
            "MVP coverage: Solana RPC multi-hop, Etherscan/Blockscout EVM account actions, and Relay orderbook lookup when detected.",
            "Bridge providers other than Relay are marked as future coverage unless exposed by labels or existing orderbooks.",
            "High-frequency service nodes, routers, pools, bridge solvers, and CEX hot wallets are downgraded or stopped.",
        ],
    }
    print_or_write(result, build_markdown(result), args.output_json, args.output_md)


if __name__ == "__main__":
    command_error(main)
