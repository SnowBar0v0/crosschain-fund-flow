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
- Solana RPC multi-hop transfer graph using SOL/token owner balance deltas;
- EVM account-action expansion through Etherscan or Blockscout when keys are configured;
- Relay orderbook lookup when bridge-like edges are detected;
- label matching from user spreadsheets;
- scored candidate output with JSON graph and Markdown report.

## MVP Boundaries

The first bundled version is intentionally conservative:

- Solana expansion uses RPC signatures and parsed transaction balance deltas.
- EVM expansion uses account actions: normal tx, ERC20 transfers, and internal tx.
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

Confidence:

```text
score >= 12: high
score 7-11: medium
score 4-6: low
score < 4: ignore unless --include-low-confidence
```

## Interpretation Rules

- Treat DEX routers, pools, bridge solvers, CEX hot wallets, and program accounts as infrastructure, not personal wallets.
- A common CEX deposit address is useful evidence of convergence, but it is weaker than a non-service shared funder or recipient.
- Multi-hop convergence is a clue, not proof. Increase skepticism as hop depth increases.
- Use labels as attribution support, not the only transaction truth source.
- If bridge orderbooks are unavailable, mark the gap and do not infer the destination recipient from router transfers alone.

## Output Expectations

The JSON graph should include:

- `nodes`: seed, candidate, bridge, dex, cex, service, or contract nodes;
- `edges`: transfer, token_transfer, bridge, evm_native, evm_erc20, evm_internal, shared_funder, shared_recipient, or contract_interaction edges;
- `clusters`: seed set, candidates, score, confidence, and main evidence;
- `warnings`: coverage or stop-point notes.

The Markdown report should lead with:

- high/medium/low candidate count;
- whether cross-chain bridge convergence was found;
- candidate table with score and main evidence;
- compact relationship evidence;
- stop points and risk notes.
