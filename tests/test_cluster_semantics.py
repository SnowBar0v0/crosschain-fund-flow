#!/usr/bin/env python3
"""Regression tests for cluster-expansion transaction semantics."""

from __future__ import annotations

from expand_crosschain_cluster import (
    CHAIN_NAMES,
    ClusterGraph,
    DEFAULT_EVM_CHAIN_IDS,
    SOLANA_CHAIN,
    analyze_common_patterns,
    classify_evm_action,
    classify_solana_transaction,
    node_id,
    solana_edges_from_transaction,
    chain_name,
)
from evm_networks import ROBINHOOD_CANONICAL_TOKENS, robinhood_blockscout_api
from trace_evm_wallet import provider_api_key, resolve_provider
from trace_bridge_order import relay_lookup


SEED_A = "Seed111111111111111111111111111111111111111"
SEED_B = "Seed222222222222222222222222222222222222222"
TARGET = "Target1111111111111111111111111111111111111"
POOL = "Pool111111111111111111111111111111111111111"
MINT = "Mint111111111111111111111111111111111111111"


def tx(account_keys, pre_balances, post_balances, pre_tokens=None, post_tokens=None, logs=None, instructions=None):
    return {
        "transaction": {
            "message": {
                "accountKeys": account_keys,
                "instructions": instructions or [],
            }
        },
        "meta": {
            "preBalances": pre_balances,
            "postBalances": post_balances,
            "preTokenBalances": pre_tokens or [],
            "postTokenBalances": post_tokens or [],
            "logMessages": logs or [],
        },
    }


def token_balance(owner, mint, account_index, amount):
    return {
        "owner": owner,
        "mint": mint,
        "accountIndex": account_index,
        "uiTokenAmount": {"uiAmount": amount},
    }


def test_pump_fun_amm_sell_is_non_scoring_swap():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": POOL, "signer": False}],
        [2_000_000_000, 1_000_000_000],
        [2_400_000_000, 600_000_000],
        [token_balance(SEED_A, MINT, 2, 100), token_balance(POOL, MINT, 3, 1000)],
        [token_balance(SEED_A, MINT, 2, 50), token_balance(POOL, MINT, 3, 1050)],
        ["Program log: Pump.fun AMM instruction", "Program log: Instruction: Sell", "Invoking Pump Fees Program"],
    )
    classification = classify_solana_transaction(sample)
    assert classification["intent"] == "swap_or_dex_route"
    assert classification["platform"] == "pump.fun_amm"
    edges = solana_edges_from_transaction(SEED_A, "pump_sig", 1, sample)
    assert len(edges) == 1
    assert edges[0]["type"] == "swap_or_dex_route"
    assert edges[0]["eligible_for_scoring"] is False


def test_pump_fun_bonding_curve_buy_is_non_scoring_swap():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": POOL, "signer": False}],
        [2_000_000_000, 1_000_000_000],
        [1_500_000_000, 1_500_000_000],
        [token_balance(SEED_A, MINT, 2, 0), token_balance(POOL, MINT, 3, 1000)],
        [token_balance(SEED_A, MINT, 2, 100), token_balance(POOL, MINT, 3, 900)],
        ["Program log: Pump.fun", "Program log: Bonding Curve", "Program log: Instruction: Buy"],
    )
    classification = classify_solana_transaction(sample)
    assert classification["intent"] == "swap_or_dex_route"
    assert classification["platform"] == "pump.fun_bonding_curve"
    assert solana_edges_from_transaction(SEED_A, "bonding_sig", 1, sample)[0]["eligible_for_scoring"] is False


def test_plain_sol_transfer_scores_as_direct_value_transfer():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": TARGET, "signer": False}],
        [2_000_000_000, 0],
        [999_995_000, 1_000_000_000],
    )
    assert classify_solana_transaction(sample)["intent"] == "plain_transfer"
    edges = solana_edges_from_transaction(SEED_A, "sol_sig", 1, sample)
    assert edges[0]["type"] == "direct_value_transfer"
    assert edges[0]["eligible_for_scoring"] is True


def test_plain_spl_transfer_scores_as_token_owner_transfer():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": TARGET, "signer": False}],
        [2_000_000_000, 0],
        [1_999_995_000, 0],
        [token_balance(SEED_A, MINT, 2, 100), token_balance(TARGET, MINT, 3, 0)],
        [token_balance(SEED_A, MINT, 2, 25), token_balance(TARGET, MINT, 3, 75)],
    )
    assert classify_solana_transaction(sample)["intent"] == "token_transfer"
    edges = solana_edges_from_transaction(SEED_A, "spl_sig", 1, sample)
    assert edges[0]["type"] == "token_owner_transfer"
    assert edges[0]["eligible_for_scoring"] is True


def test_solana_close_account_is_non_scoring_rent_noise():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": "TempTokenAccount111111111111111111111111111"}],
        [2_000_000_000, 2_039_280],
        [2_002_034_280, 0],
        instructions=[{"program": "spl-token", "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "parsed": {"type": "closeAccount"}}],
    )
    classification = classify_solana_transaction(sample)
    assert classification["intent"] == "account_create_close"
    edges = solana_edges_from_transaction(SEED_A, "close_sig", 1, sample)
    assert edges[0]["type"] == "account_rent_or_close"
    assert edges[0]["eligible_for_scoring"] is False


def test_evm_approve_is_non_scoring_contract_interaction():
    row = {
        "from": "0xbe1eaa605d3694639988dd4fcd7cee7ab8b1d74d",
        "to": "0x111111125421ca6dc452d289314280a0f8842a65",
        "value": "0",
        "input": "0x095ea7b3",
        "functionName": "approve(address spender,uint256 amount)",
    }
    classification = classify_evm_action(row, "txlist")
    assert classification["edge_type"] == "contract_interaction"
    assert classification["eligible_for_scoring"] is False


def test_robinhood_mainnet_is_in_default_scan_and_named():
    assert 4663 in DEFAULT_EVM_CHAIN_IDS
    assert CHAIN_NAMES[4663] == "robinhood"
    assert chain_name(4663) == "robinhood"
    assert chain_name(46630) == "robinhood_testnet"
    assert 46630 not in DEFAULT_EVM_CHAIN_IDS


def test_robinhood_uses_public_blockscout_without_key():
    assert resolve_provider("auto", 4663) == "robinhood_blockscout"
    assert provider_api_key("robinhood_blockscout") == ""
    assert robinhood_blockscout_api(4663) == "https://robinhoodchain.blockscout.com/api"
    assert ROBINHOOD_CANONICAL_TOKENS[4663]["USDG"].lower() == "0x5fc5360d0400a0fd4f2af552add042d716f1d168"


def test_relay_limit_is_capped_at_public_api_max(monkeypatch):
    captured = {}

    def fake_http_json(url, params):
        captured.update(params)
        return {"requests": []}

    monkeypatch.setattr("trace_bridge_order.http_json", fake_http_json)
    relay_lookup(None, "0x44fbe0006661d6d17188f1f6d42b32b5577179f7", 100)
    assert captured["limit"] == 50


def test_unknown_non_core_program_is_not_promoted_to_transfer():
    sample = tx(
        [{"pubkey": SEED_A, "signer": True}, {"pubkey": TARGET, "signer": False}],
        [2_000_000_000, 0],
        [1_999_995_000, 0],
        [token_balance(SEED_A, MINT, 2, 100), token_balance(TARGET, MINT, 3, 0)],
        [token_balance(SEED_A, MINT, 2, 25), token_balance(TARGET, MINT, 3, 75)],
        instructions=[{"programId": "UnknownDexProgram1111111111111111111111111111"}],
    )
    classification = classify_solana_transaction(sample)
    assert classification["intent"] == "unknown_complex"
    edges = solana_edges_from_transaction(SEED_A, "unknown_program_sig", 1, sample)
    assert edges[0]["type"] == "unknown_complex"
    assert edges[0]["eligible_for_scoring"] is False


def test_multiple_seed_swaps_same_pool_do_not_create_candidate():
    seed_ids = {node_id(SOLANA_CHAIN, SEED_A), node_id(SOLANA_CHAIN, SEED_B)}
    graph = ClusterGraph({}, seed_ids)
    graph.add_node(SOLANA_CHAIN, SEED_A, "seed")
    graph.add_node(SOLANA_CHAIN, SEED_B, "seed")
    for seed, sig in ((SEED_A, "swap_a"), (SEED_B, "swap_b")):
        graph.add_edge(
            SOLANA_CHAIN,
            seed,
            SOLANA_CHAIN,
            seed,
            {
                "type": "swap_or_dex_route",
                "tx": sig,
                "eligible_for_scoring": False,
                "platform": "pump.fun_amm",
                "service_nodes": [{"chain": SOLANA_CHAIN, "address": POOL, "type": "dex"}],
                "evidence": "shared pool is protocol activity",
            },
        )
    candidates = analyze_common_patterns(graph, seed_ids, 5)
    assert candidates == []
    assert graph.nodes[node_id(SOLANA_CHAIN, POOL)]["candidate_eligible"] is False


def test_multiple_seed_transfers_to_same_wallet_remain_high_signal():
    seed_ids = {node_id(SOLANA_CHAIN, SEED_A), node_id(SOLANA_CHAIN, SEED_B)}
    graph = ClusterGraph({}, seed_ids)
    graph.add_node(SOLANA_CHAIN, SEED_A, "seed")
    graph.add_node(SOLANA_CHAIN, SEED_B, "seed")
    for seed, sig in ((SEED_A, "pay_a"), (SEED_B, "pay_b")):
        graph.add_edge(
            SOLANA_CHAIN,
            seed,
            SOLANA_CHAIN,
            TARGET,
            {
                "type": "direct_value_transfer",
                "tx": sig,
                "asset": "SOL",
                "amount": 1,
                "eligible_for_scoring": True,
                "evidence": "ordinary transfer",
            },
        )
    candidates = analyze_common_patterns(graph, seed_ids, 5)
    assert candidates
    assert candidates[0]["address"] == TARGET
    assert candidates[0]["score"] >= 7


if __name__ == "__main__":
    tests = [
        test_pump_fun_amm_sell_is_non_scoring_swap,
        test_pump_fun_bonding_curve_buy_is_non_scoring_swap,
        test_plain_sol_transfer_scores_as_direct_value_transfer,
        test_plain_spl_transfer_scores_as_token_owner_transfer,
        test_solana_close_account_is_non_scoring_rent_noise,
        test_evm_approve_is_non_scoring_contract_interaction,
        test_robinhood_mainnet_is_in_default_scan_and_named,
        test_robinhood_uses_public_blockscout_without_key,
        test_unknown_non_core_program_is_not_promoted_to_transfer,
        test_multiple_seed_swaps_same_pool_do_not_create_candidate,
        test_multiple_seed_transfers_to_same_wallet_remain_high_signal,
    ]
    for test in tests:
        test()
    print(f"ok - {len(tests)} cluster semantic tests passed")
