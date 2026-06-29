# Solana Platform Semantics

Use this reference with `scripts/expand_crosschain_cluster.py` when classifying Solana transactions before graph scoring.

## Principle

Classify the transaction intent before creating graph edges.

Protocol-mediated activity is not the same thing as a wallet-to-wallet transfer. A DEX swap can show token/SOL balance deltas across routers, pools, vaults, fee accounts, temporary token accounts, and user accounts. Those infrastructure accounts must not become related-wallet candidates.

## Evidence Priority

Use evidence in this order:

1. Program id, executable account, account owner, token-account owner.
2. Parsed instruction type, inner CPI, and logs.
3. Owner-level token balance deltas.
4. Explorer or spreadsheet labels.
5. UI summaries.

Do not let a UI summary or raw balance delta overrule a clear DEX/router/platform instruction.

## Pump.fun / PumpSwap

Classify as `swap_or_dex_route` when the transaction logs, labels, or accounts indicate:

- `Pump.fun AMM`
- `PumpSwap`
- `Bonding Curve`
- `Instruction: Buy`
- `Instruction: Sell`
- `Invoking Pump Fees Program`
- protocol fee / creator fee / AMM pool / AMM market labels

For these transactions:

- report the user's net input/output assets;
- mark pools, bonding curves, fee accounts, and markets as service/infrastructure;
- do not score shared pool or shared market interaction as a related-wallet signal.

## Scoring Boundary

Only these edge types may add positive related-wallet score:

```text
direct_value_transfer
token_owner_transfer
```

These edge types are graph evidence but must not add positive score:

```text
swap_or_dex_route
swap_user_input
swap_user_output
swap_fee
liquidity_action
account_rent_or_close
wrap_unwrap_native
bridge_deposit
bridge_fill
platform_deposit
platform_internal
contract_interaction
unknown_complex
```

Shared DEX, router, pool, fee, or platform interaction can be mentioned as weak context, but it is not enough to call two wallets related.

## Dictionary

The machine-readable dictionary lives at:

```text
data/solana_platforms.json
```

It is deliberately extendable. Add verified program ids, label terms, and log phrases as they are confirmed. When a platform is not covered, classify conservatively as `unknown_complex` rather than turning every balance delta into a candidate edge.
