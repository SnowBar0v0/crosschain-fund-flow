# Classification Rules

Use these rules when deciding whether to continue tracing, stop, or explain a transaction as complex.

## Status Tags

Use exact tags:

```text
bridge_order_success
bridge_orderbook_missing
landed_on_solana
landed_on_evm
closed_to_cex
closed_to_platform_wallet
closed_to_hyperliquid_account
terminal_no_outgoing_detected
first_layer_outgoing_detected
waiting_user_confirmation
not_closed_high_frequency_fanout
not_closed_complex_contract_route
not_closed_complex_dex_cpi_route
not_closed_insufficient_api_coverage
internal_trading_activity_detected
complex_swap_detected
```

## Stop Conditions

Stop by default when:

- recipient is a CEX, exchange deposit, exchange hot wallet, Hyperliquid account, ChangeNOW/FixedFloat service wallet, or similar platform account;
- bridge order completed and destination recipient has no detected outgoing transfer in the inspected first layer;
- target is a high-frequency commingled service node and branch expansion would be arbitrary;
- only platform-internal ledger trades are detected.

Ask before continuing when:

- bridge destination recipient moved funds onward;
- a complex swap creates a new asset and the user did not ask for recursive tracing;
- a high-frequency fanout requires multiple branch expansion;
- coverage requires a missing API key, logged-in browser, or unavailable bridge orderbook.

## Solana

Checklist:

1. Pull signatures for both owner addresses and token accounts.
2. Compare `preBalances/postBalances` for SOL and `preTokenBalances/postTokenBalances` for tokens.
3. Use token balance `owner` to attribute token-account deltas to wallets.
4. Inspect inner instructions for CPI, swaps, WSOL unwraps, close-account rent returns, and ATA creation.
5. Do not treat system program, token program, ATA program, router, pool, or temporary token account as terminal wallets.

Common Solana interpretations:

- Token account close can create SOL balance increases without being a transfer of trading profit.
- WSOL unwrap can look like SOL received; verify wrapped token account changes.
- DEX routes often show several pool/token-account deltas; explain the net owner asset changes.
- If an owner address shows no new signatures, still check its token account signatures.

## EVM

Checklist:

1. Pull normal tx, ERC-20 token tx, internal tx, and relevant logs.
2. Use receipts/logs to attribute actual token transfers.
3. Treat `approve`, `permit`, and allowance updates as non-flow.
4. Treat `transfer`, `transferFrom`, native value, and internal value calls as possible flow.
5. Decode router/multicall/bridge calls where possible; otherwise explain using events and balance deltas.
6. Check whether recipient is a contract. A router/pool/bridge contract is not a terminal wallet.

Common EVM interpretations:

- DEX router calls can emit token transfers to pools and back to the user; report input/output assets, not only the router address.
- Internal tx may show native asset movement that token transfer endpoints miss.
- Stablecoin bridge orders may show origin asset and destination asset with different token contracts but equivalent symbol/value.

## Platform Wallets

For Hyperliquid:

- Normal HyperEVM explorers may show no transactions for a Hyperliquid account even when the platform ledger has deposits/trades.
- Use Hyperliquid public info endpoints for account state, non-funding ledger updates, and fills when platform-ledger analysis is requested.
- Default classification after a bridge deposit to Hyperliquid: `closed_to_hyperliquid_account`.
- If fills/positions exist, add `internal_trading_activity_detected`, but do not continue as ordinary EVM tracing.

For CEX and service wallets:

- Mark `closed_to_cex` or `closed_to_platform_wallet`.
- Do not try to infer platform-internal user balances unless the user asks and a legitimate API/export is available.

## Confidence

Use plain confidence language by default:

```text
高：链上交易 + 桥订单簿/平台账本相互印证。
中：链上交易明确，但标签或订单簿缺失一部分。
低：只能看到相近时间/金额/标签，缺少直接订单或交易证据。
```

Use numeric confidence only for professional/JSON output.
