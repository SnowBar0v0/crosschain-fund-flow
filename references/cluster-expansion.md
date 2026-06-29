# Cross-Chain Cluster Expansion

Use this reference when the user asks to expand related wallets from a known seed cluster.

## Scope

This workflow produces chain-analysis candidates, not identity attribution.

The bundled MVP executor is:

```bash
python scripts/expand_crosschain_cluster.py \
  --seed-addresses <addr1> <addr2> \
  --from-time <from> \
  --to-time <to> \
  --post-window-hours 72 \
  --max-hop-solana 2 \
  --max-hop-evm 1 \
  --bridge-follow true \
  --min-score 5
```

It supports:

- seed lists from CLI or `--seed-file`;
- Solana RPC multi-hop transfer graph using transaction semantic classification plus SOL/token owner balance deltas;
- EVM account-action expansion through Etherscan or Blockscout when keys are configured;
- Relay orderbook lookup when bridge-like edges are detected;
- label matching from user spreadsheets;
- scored candidate output with JSON graph and Markdown report.

## MVP Boundaries

The first bundled version is intentionally conservative:

- Solana expansion uses RPC signatures and parsed transaction balance deltas.
- Solana transactions are classified before edge generation. DEX/router/AMM, account rent/close, WSOL wrap/unwrap, bridge deposit, and unknown complex transactions are preserved as evidence but do not create positive candidate edges.
- EVM expansion uses account actions: normal tx, ERC20 transfers, and internal tx.
- EVM approve/permit, zero-value contract calls, router/multicall/swap-like calls, and service endpoints are non-scoring edges unless receipts/logs prove a clean wallet-to-wallet value transfer.
- Relay orderbook is first-class. Other bridges should be treated as future coverage unless a dedicated orderbook API is added or manually checked.
- OKX token trade co-activity is not yet merged into cluster scoring automatically.
- High-frequency fanout detection is heuristic; do not force a terminal conclusion from service-like nodes.

When coverage is missing, report:

```text
not_closed_insufficient_api_coverage
bridge_orderbook_missing
not_closed_high_frequency_fanout
```

Do not invent paths.

## Scoring

Use these default signals:

```text
+8 seed-to-seed direct transfer
+7 multiple seeds send to the same non-service recipient
+7 same non-service address funds multiple seeds
+6 bridge order lands on a destination recipient
+6 multi-hop paths from multiple seeds converge on one address
+5 same address is a one-hop neighbor of multiple seeds
+3 common CEX/platform address, downgraded
+2 same weak tag or trading behavior only, weak evidence
-5 DEX/router/pool/bridge solver/program/token account/service node
-4 high-frequency fanout or commingled service node
-3 same token activity without fund-path overlap
```

Only direct economic wallet edges can add positive score:

```text
direct_value_transfer
token_owner_transfer
```

These edges are evidence only and must not create related-wallet candidates:

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

Confidence:

```text
score >= 12: high
score 7-11: medium
score 4-6: low
score < 4: ignore unless --include-low-confidence
```

## Interpretation Rules

- Treat DEX routers, pools, bridge solvers, CEX hot wallets, and program accounts as infrastructure, not personal wallets.
- Shared DEX, Pump.fun/PumpSwap, router, AMM pool, bonding curve, or platform interaction is not enough to classify wallets as related.
- Resolve token account owners before graph construction. Token accounts and program-owned/PDA accounts are not candidates unless there is separate evidence of user control.
- A common CEX deposit address is useful evidence of convergence, but it is weaker than a non-service shared funder or recipient.
- Multi-hop convergence is a clue, not proof. Increase skepticism as hop depth increases.
- Use labels as attribution support, not the only transaction truth source.
- If bridge orderbooks are unavailable, mark the gap and do not infer the destination recipient from router transfers alone.
- Use `references/solana-platforms.md` and `data/solana_platforms.json` when extending Solana DEX/platform classifications.

## Output Expectations

The JSON graph should include:

- `nodes`: seed, candidate, bridge, dex, cex, service, or contract nodes;
- `edges`: direct_value_transfer, token_owner_transfer, bridge, bridge_deposit, bridge_fill, swap_or_dex_route, contract_interaction, platform_deposit, platform_internal, account_rent_or_close, wrap_unwrap_native, unknown_complex, shared_funder, or shared_recipient edges;
- `clusters`: seed set, candidates, score, confidence, and main evidence;
- `warnings`: coverage or stop-point notes.

The Markdown report should lead with:

- high/medium/low candidate count;
- whether cross-chain bridge convergence was found;
- candidate related wallet table with score and main evidence;
- service/infrastructure nodes;
- shared platform interactions;
- excluded-from-scoring edges and reasons;
- compact scoring-eligible relationship evidence;
- stop points and risk notes.
