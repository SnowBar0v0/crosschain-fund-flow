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
