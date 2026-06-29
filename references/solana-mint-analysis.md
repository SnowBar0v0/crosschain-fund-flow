# Solana Mint Analysis

Use this reference for Solana mint launch analysis, top-N participant analysis, token-account owner attribution, and label-sheet intersections such as a `JAK` worksheet.

## Clarify The Metric First

Before running a top-N task, state or ask for the ranking metric. Do not guess silently.

Common metrics:

```text
top_net_buyers        = wallets with largest net token increase in the window
top_gross_buy_volume  = wallets with largest total token bought, ignoring later sells
top_funders           = wallets that funded participant wallets with SOL/USDC/USDT
top_profit_takers     = wallets with largest stable/SOL outflow after selling
top_flow_value        = wallets ranked by estimated SOL/stable value moved
top_current_holders   = current holder snapshot ranked by holder percentage or token amount
okx_token_trades      = wallets ranked from OKX Web3 token trading activity rows
label_history_hits    = candidate label-sheet wallets that had mint balance deltas in the window, including cleared positions
```

Default if the user says "mint top participants fund flow" without a metric:

```text
Rank participant wallets by net token acquired during the requested launch window, then trace their funding source and first material outflow.
```

Say this default before executing.

## Mint Creation Window

For a request such as "first 3 hours after mint creation":

1. Determine the mint creation transaction or earliest reliable mint/account initialization evidence.
2. Record the exact creation timestamp and timezone.
3. Define the window as `[creation_time, creation_time + 3 hours)`.
4. If creation time cannot be proven from available APIs, mark `mint_creation_time_unconfirmed` and ask for a tx hash or explorer link.

## Required Solana Attribution

For every token movement:

1. Resolve token account to wallet owner.
2. Exclude program-owned accounts, pools, routers, vaults, and temporary token accounts from participant rankings unless the user explicitly wants infrastructure.
3. Attribute balance deltas using `preTokenBalances/postTokenBalances.owner`.
4. Check token-account signatures when owner-address signatures do not show later movement.
5. Track SOL/WSOL, USDC, USDT, and native fee/rent separately.

## Provider Fallbacks

For mint participant tasks, do not assume Solscan Pro is mandatory.

Provider order:

1. Public market holder providers (OKX/APIBase holders plus Binance Web3 meta/dynamic info) for no-key `top_current_holders`, market cap, price, holders count, creation/launch time, funding-source hints, buy/sell counts, PnL fields, and current top-holder label matching.
2. OKX Web3 token trading activity for no-key historical DEX trades in a time window. It can return tx hash, wallet, buy/sell side, token size, value, DEX, and tags with pagination.
3. Helius or another available historical/enhanced transaction index for exact raw transfer coverage when configured.
4. Solana RPC verification for signatures, transactions, token balance deltas, owner attribution, and spot checks.
5. Solscan Pro only when the user explicitly has paid Pro access or forces the Solscan provider. Do not rely on it in default `auto` mode for ordinary users.

When using OKX trading activity, state that it is a market DEX-trade index rather than raw token-transfer truth. Verify important rows through tx hashes on Solana RPC/explorer. When using market holder fallback for a historical-window request, clearly state that it is a current holder snapshot rather than a complete historical transfer index. Exclude liquidity pools, authorities, routers, and vault-like holder rows from participant rankings by default, but keep them in evidence as excluded infrastructure.

## Current Holder Snapshot vs Historical Participation

Do not collapse these into one conclusion:

```text
Current holder snapshot = who still holds now, with holder ranking and optional buy/sell/funding hints.
OKX token trades = who bought/sold through indexed DEX activity inside the requested window.
Historical candidate scan = which provided label/list addresses had mint balance changes inside the requested window.
```

If a user asks "what if there is no holding but they traded", "all JAK addresses that participated", "cleared positions", or anything equivalent, run the candidate history executor:

```bash
python scripts/trace_solana_mint_label_history.py --mint <mint> --hours-after-create <hours> --label-file <file> --label-sheets <sheets>
```

Use it together with `trace_solana_mint_participants.py` when needed:

- `trace_solana_mint_participants.py` answers top-N/current-holder style questions and can use `--provider okx_trades` for no-key historical DEX trades.
- `fetch_okx_token_trades.py` answers raw OKX token `交易活动` extraction and participant ranking questions.
- `trace_solana_mint_label_history.py` answers candidate label/list historical participation questions.

State the limitation plainly: the candidate history executor scans the provided owner addresses through Solana RPC. It can catch wallets that traded and later cleared to zero when those owner signatures expose the relevant transactions, but it is not a substitute for a full indexed token-transfer provider for discovering every historical participant globally.

## JAK Or Label-Sheet Matching

When the user provides a spreadsheet:

1. Use a spreadsheet parser rather than text scraping.
2. Confirm the worksheet name, e.g. `JAK`, exchange-label sheet, or routing-label sheet.
3. Normalize addresses by chain and case rules:
   - Solana: exact base58 string.
   - EVM: lowercase checksum-insensitive.
4. Match both wallet owner addresses and token accounts where relevant.
5. Report intersections separately:
   - participant wallet hit,
   - historical-only label hit,
   - funder hit,
   - recipient hit,
   - infrastructure/router hit.

## Bulk Requirement

Mint top-N participant analysis is normally `bulk_analysis`. If no existing indexer/export/collector is available, read `execution-boundaries.md` and ask before creating a temporary script.

Do not pretend a large mint analysis can be completed accurately from a few manually inspected explorer pages.

## Minimal Report Shape

For a default user-facing report:

```text
Conclusion:
- State the launch window and ranking metric.
- State whether the requested top-N was fully computed or limited by data coverage.

Top-N Summary:
- wallet
- rank metric
- funding source
- first material outflow
- label-sheet hit
- confidence

Notes:
- Explain excluded infrastructure addresses.
- Explain unresolved or rate-limited branches.
```

Render the final report in the user's language.
