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
  "task_type": "solana_wallet | evm_wallet | bridge_order | solana_mint_participants | okx_token_trades | solana_mint_label_history | label_match | manual_analysis",
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
- If the user asks for current holders, holder ranking, holder percentage, market cap, or asks to use holder APIs, use `top_current_holders` and allow `--provider market_holders` or `--provider auto`.
- If unclear, default to `top_net_buyers` and state it.

Provider:

- Use `--provider auto` by default.
- Do not assume Solscan Pro is available in `auto`; ordinary Solscan keys may not have token-transfer index permissions.
- Use `--provider solscan` only when the user explicitly says they have paid Pro access or wants to force Solscan. `auto` may try paid Pro only when `CFF_ENABLE_SOLSCAN_PRO_AUTO=1` is set.
- Fall back to market holder snapshot when the task can be answered or partially answered from holder/current-position data.
- If the user specifically asks for historical net buyers in an exact launch window, label market holder fallback as approximate/current snapshot coverage.
- In `auto`, ordinary no-key historical DEX trade coverage should try OKX trading activity before falling back to current holder snapshots. Use `--provider okx_trades` to force that path.

Window:

- "3 hours after creation" => `--hours-after-create 3`.
- "first 3 hours" near a mint launch usually means first 3 hours after creation; state this assumption.
- If exact dates are provided, use `--from-time` and `--to-time`.

Labels:

- "intersect with JAK sheet" => include `--label-sheets JAK`.
- "exchange and router sheets" => include the exact workbook and the corresponding `--label-sheets` if available.

### OKX Token Trades

Trigger when the request asks for a Solana token's historical DEX trades, transaction activity, OKX `交易活动`, no-key token trade history, top buyers from token activity, or all wallets that traded in a time window.

Executor:

```bash
python scripts/fetch_okx_token_trades.py --mint <mint> --from-time <from> --to-time <to> --top <n>
```

Use this executor when the user specifically points to an OKX Web3 token page or asks whether the page's `交易活动` can be used as a transaction source. It returns wallet addresses, tx hashes, buy/sell side, token amount, value, DEX, tags, and pagination.

Use `trace_solana_mint_participants.py --provider okx_trades` when the requested output is the normal mint top-N participant report:

```bash
python scripts/trace_solana_mint_participants.py --mint <mint> --from-time <from> --to-time <to> --top <n> --provider okx_trades
```

If the user mentions Binance Web3 `历史成交`, inspect it as browser-visible supporting evidence, but do not rely on it as the main historical index until a stable global pagination API is confirmed.

### Solana Mint Label History

Trigger when the user asks whether addresses from a label sheet or candidate list ever participated in a mint, including phrases such as:

```text
JAK 里所有曾经交易过的地址
没持仓但是有过交易
买过卖过但清仓了
窗口内参与过但现在余额为 0
historical participants from this label sheet
cleared positions from the candidate list
```

Executor:

```bash
python scripts/trace_solana_mint_label_history.py --mint <mint> --hours-after-create <hours> --label-file <file> --label-sheets <sheets>
```

Use this executor to answer candidate-list history questions. It uses Solana RPC to scan candidate owner-address signatures and compare token balance deltas for the mint. It can find addresses that are no longer current holders, but it is not a global all-wallet top-N indexer.

If the user asks for both global top-N and label-sheet historical participation, run both:

```bash
python scripts/trace_solana_mint_participants.py --mint <mint> --hours-after-create <hours> --top <n> --provider auto --label-file <file> --label-sheets <sheets>
python scripts/trace_solana_mint_label_history.py --mint <mint> --hours-after-create <hours> --label-file <file> --label-sheets <sheets>
```

Report them as two separate coverage layers:

```text
Top-N/current-holder coverage: ranked participant or holder result.
Label-history coverage: candidate label addresses that actually had mint balance deltas in the window.
```

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
