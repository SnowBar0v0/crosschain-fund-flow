"""Shared EVM network metadata used by the bundled trace executors."""

from __future__ import annotations


DEFAULT_EVM_CHAIN_IDS = [1, 56, 8453, 42161, 10, 137, 43114, 4663]

CHAIN_NAMES = {
    1: "ethereum",
    10: "optimism",
    56: "bsc",
    137: "polygon",
    8453: "base",
    42161: "arbitrum",
    43114: "avalanche",
    4663: "robinhood",
    46630: "robinhood_testnet",
    792703809: "solana",
}

ROBINHOOD_BLOCKSCOUT_APIS = {
    4663: "https://robinhoodchain.blockscout.com/api",
    46630: "https://explorer.testnet.chain.robinhood.com/api",
}

ROBINHOOD_PUBLIC_RPCS = {
    4663: "https://rpc.mainnet.chain.robinhood.com",
    46630: "https://rpc.testnet.chain.robinhood.com",
}

ROBINHOOD_CANONICAL_TOKENS = {
    4663: {
        "WETH": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
        "USDG": "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168",
    }
}


def chain_name(chain_id: int) -> str:
    return CHAIN_NAMES.get(int(chain_id), f"evm_{chain_id}")


def robinhood_blockscout_api(chain_id: int) -> str | None:
    return ROBINHOOD_BLOCKSCOUT_APIS.get(int(chain_id))
