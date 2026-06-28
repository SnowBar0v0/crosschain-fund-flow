# Request Routing

Use this reference to translate a user's plain-language request into executor calls.

## Main Principle

Do not make the user speak CLI.

The user can say things like:

```text
check where this address sent funds from 00:00 to 10:00 today
for this mint, analyze first 3 hours top50 and intersect with the JAK sheet
find where this Relay cross-chain transaction landed
check whether this EVM address moved funds onward in the first layer
```

Codex must parse the intent, fill safe defaults, and call the right bundled script. Ask only when a required value is missing and cannot be inferred.

## Task Spec

Internally normalize every request into:

```json
{
  "task_type": "solana_wallet | evm_wallet | bridge_order | solana_mint_participants | label_match | manual_analysis",
  "inputs": {
    "addresses": [],
    "tx_hashes": [],
    "mint": null
  },
  "window": {
    "from": null,
    "to": null,
    "timezone": "Asia/Shanghai"
  },
  "options": {
    "top": null,
    "metric": null,
    "label_file": null,
    "label_sheets": [],
    "depth": "first_layer"
  },
  "executor": null
}
```

Do not expose this JSON unless useful. It is a thinking aid for routing.

## Routing Rules

### Solana Wallet

Trigger when the request contains a Solana address and asks about funds, transfers, flows, outflows, stop address, or a time window.

Executor:

```bash
python scripts/trace_solana_wallet.py --address <address> --from-time <from> --to-time <to>
```

Add `--label-file` and `--label-sheets` when the user references a label workbook or a sheet such as JAK/exchange/router.

### EVM Wallet

Trigger when the request contains an EVM address and asks about first layer, outgoing, transfer, wallet flow, or bridge destination follow-up.

Executor:

```bash
python scripts/trace_evm_wallet.py --address <address> --chain-id <chain_id> --from-time <from> --to-time <to>
```

Infer chain id from context, bridge order, URL, or user text. If impossible, ask for chain.

### Bridge Order

Trigger when the request mentions Relay, Gas.zip, bridge order, cross-chain tx, route, destination tx, or gives a bridge tx hash.

Executor:

```bash
python scripts/trace_bridge_order.py --bridge relay --tx <tx_hash>
python scripts/trace_bridge_order.py --bridge relay --address <address>
```

Use Relay by default only when Relay is mentioned or a Relay address/router/label is known. Otherwise infer bridge name from labels or ask.

### Solana Mint Participants

Trigger when the request mentions a mint, token launch, creation window, top buyers, top holders, top participants, top funds, or first N hours.

Executor:

```bash
python scripts/trace_solana_mint_participants.py --mint <mint> --hours-after-create <hours> --top <n>
```

Top count:

- Parse Arabic numbers: top10, top 10, top50.
- Parse common Chinese number forms such as "front 10", "front twenty", "front fifty", and "front 100" when written in Chinese by the user.
- If no count is given, default to 20 and state the default.

Metric:

- If the user says buy/participation/position/holding in Chinese or English, use `top_net_buyers`.
- If the user says volume/turnover/gross buy volume in Chinese or English, use `top_gross_buy_volume`.
- If unclear, default to `top_net_buyers` and state it.

Window:

- "3 hours after creation" => `--hours-after-create 3`.
- "first 3 hours" near a mint launch usually means first 3 hours after creation; state this assumption.
- If exact dates are provided, use `--from-time` and `--to-time`.

Labels:

- "intersect with JAK sheet" => include `--label-sheets JAK`.
- "exchange and router sheets" => include the exact workbook and the corresponding `--label-sheets` if available.

### Label Match

Trigger when the user only asks whether a list of addresses hits a label sheet.

Executor:

```bash
python scripts/label_match.py <addresses...> --label-file <file> --label-sheets <sheets>
```

## Natural Language Defaults

Use these defaults and state them briefly:

```text
timezone: Asia/Shanghai unless user says otherwise
depth after bridge landing: first_layer
platform wallets: mark and stop
mint participant metric: top_net_buyers
top count: 20 only when omitted
report style: plain language
```

## When To Ask

Ask only when required information is missing:

- address/mint/tx hash is absent;
- chain cannot be inferred for an EVM address;
- time window is needed and not provided for broad wallet tracing;
- label workbook path is referenced but not provided or not discoverable;
- bridge name cannot be inferred from tx/address/context.

Do not ask:

- for command syntax;
- for `--top` if user already said top10/top50/etc.;
- for metric if a safe default can be stated;
- for depth when first-layer default applies.

## Pre-Run Notice

Before executing, say a short notice in the user's language:

```text
Parsed task: Solana mint participant analysis.
Window: first 3 hours after mint creation.
Ranking: top50 by net token acquired.
Labels: intersect with JAK sheet.
Executor: scripts/trace_solana_mint_participants.py.
```
