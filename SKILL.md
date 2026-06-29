---
name: crosschain-fund-flow
description: Trace cryptocurrency fund flows and related-wallet clusters across Solana, EVM chains, bridge orderbooks, exchanges, and platform ledgers with bundled Python executors for Solana wallet traces, EVM first-layer traces, cross-chain multi-hop cluster expansion, Relay/Gas.zip bridge lookup, Solana mint top-N participant analysis, OKX Web3 token trade history, Solana mint label history scans, and label matching. Use when the user asks in plain language to trace wallet addresses, expand a seed wallet cluster, find related wallets, identify common funders/recipients, analyze Solana or EVM transfers, follow funds through Relay/Mayan/Gas.zip/deBridge/THORChain/NEAR Intents/ChangeNOW/FixedFloat, explain unusual transactions, identify where funds stopped, or run cross-chain fund-flow workflows with API keys and labels.
---

# Crosschain Fund Flow

## Core Posture

Act as a careful chain-analysis operator. Establish transaction facts first, then labels, then interpretation. Do not hardcode API keys, login state, bridge addresses, or front-end assumptions. When an API, explorer, or logged-in session is unavailable, say exactly what is missing and what was still verified.

Default to a plain-language report. Use professional/forensic detail only when the user asks for it or when a complex transaction needs explanation.

This skill includes runnable executors for the common trace paths, but it is not a full-chain indexer. For large jobs, use the bundled `scripts/` executors first and report provider coverage clearly. For unsupported pagination, missing orderbooks, platform-internal ledgers, or data that no configured provider exposes, read `references/execution-boundaries.md` before creating any temporary scripts.

## Required First Steps

1. Normalize the request:
   - Identify each input as Solana, EVM, bridge order, exchange/platform account, tx hash, or entity label.
   - Convert all user time windows to exact timestamps. If the user says "today", "yesterday", or uses local time, state the absolute date and timezone used.
   - If no time window is provided and the task is not a single tx hash, ask for one unless the user explicitly wants "latest" or "all recent".

2. Check setup before tracing:
   - If required API keys or sessions are missing, read `references/api-setup.md` and guide the user to obtain only the missing keys.
   - Never ask the user to paste private keys, seed phrases, wallet signatures, cookies, or browser localStorage.
   - If the user provides API keys, treat them as runtime secrets: do not write them into the skill, repo, reports, or command history beyond the current run.

3. Load task-specific references only as needed:
   - Plain-language request parsing and executor routing: read `references/request-routing.md`.
   - Bridge/orderbook work: read `references/bridge-orderbooks.md`.
   - Cross-chain multi-hop cluster expansion and related-wallet scoring: read `references/cluster-expansion.md`.
   - Solana DEX/platform semantic classification for cluster expansion: read `references/solana-platforms.md`.
   - Classification/stopping decisions: read `references/classification-rules.md`.
   - Report formatting: read `references/report-style.md`.
   - Bulk data processing, top-N analysis, or local scripts: read `references/execution-boundaries.md`.
   - Solana mint launch / top-N participant / token-owner analysis: read `references/solana-mint-analysis.md`.

## Data Source Order

Use the best available factual source for the chain, and make the source visible in the report.

- Solana:
  - Do not assume Solscan Pro is available; it usually requires a paid key. Use it only when the user explicitly provides paid Pro access, selects Solscan, or sets `CFF_ENABLE_SOLSCAN_PRO_AUTO=1`.
  - For Solana mint historical DEX trading activity, use the public OKX Web3 `trading-history/filter-list` endpoint through `fetch_okx_token_trades.py` or the `okx_trades` provider in `trace_solana_mint_participants.py`. It can return user wallet, tx hash, side, size, price, value, DEX, tags, and pagination without a user API key.
  - For Solana mint holder/current-position analysis, use public market holder providers (OKX/APIBase and Binance Web3 endpoints bundled in `trace_solana_mint_participants.py`) as the default no-key fallback.
  - For questions like "JAK addresses that ever traded", "cleared position", "no current holding but had transactions", or "historical label participants", use `trace_solana_mint_label_history.py` against the candidate label/address list. Do not use a current holder snapshot to claim full historical participation.
  - Binance Web3 token pages may expose visible `历史成交` rows, but until a stable global pagination API is confirmed, treat Binance page data as browser-visible supporting evidence rather than the primary historical source.
  - Use Solana RPC for signatures, transaction details, token account balances, and verification.
  - For Solana cluster expansion, use `expand_crosschain_cluster.py` with transaction semantic classification and Solana RPC owner-delta attribution. Do not treat token accounts, programs, routers, pools, bonding curves, fee accounts, or temporary accounts as personal candidates. Shared DEX/platform interaction is not related-wallet proof.
  - Always inspect token account owners; a Solana owner address may not appear in later token-account signatures.

- EVM:
  - For token-level DEX trading activity on OKX Web3-supported EVM chains, use `fetch_okx_token_trades.py` with the EVM `--chain-id` and contract address. This is the same OKX `trading-history/filter-list` source used for Solana; Solana uses `chainId=501`, while EVM chains generally use their normal EIP-155 chain IDs such as Ethereum `1`, BNB Chain `56`, Base `8453`, Arbitrum `42161`, Optimism `10`, Polygon `137`, and Avalanche `43114`.
  - Prefer Etherscan V2 for supported chains.
  - Use Blockscout PRO for chains Etherscan free tier does not cover or when Blockscout has better decoded data.
  - Use Alchemy Transfers API for fast address-level asset transfer scans.
  - Use chain RPC for receipts, logs, code checks, and single-transaction verification.
  - For EVM cluster expansion, use `expand_crosschain_cluster.py` with Etherscan/Blockscout account actions first, then receipts/logs/RPC for verification when needed.

- Labels:
  - Use the user's label spreadsheets or local label store when provided.
  - Use Arkham logged-in browser/session only for entity labels and service attribution, not as the only transaction truth source.
  - For ChangeNOW and FixedFloat, use Arkham/entity transfers when the user has authorized a logged-in session.

- Bridge orderbooks:
  - Query bridge-specific orderbooks before guessing destination addresses from raw transfers.
  - For cluster expansion, represent bridge continuity as graph edges. Router, solver, pool, depository, and vault addresses are bridge infrastructure, not terminal entity wallets.
  - If a bridge/orderbook is unavailable, mark `bridge_orderbook_missing` and give the exact missing bridge/source.

## Workflow

### 0. Choose Execution Mode

First translate the user's plain-language request into an internal task spec. Do not ask the user to provide command-line flags. Use the model to infer task type, chain, addresses, tx hashes, mint, time window, top-N count, label sheets, and output style. Ask only for information that cannot be reasonably inferred or discovered.

Use `references/request-routing.md` for the routing rules.

Before doing work, decide and state the execution mode:

- `manual_api_trace`: small number of addresses/transactions; direct API/RPC/browser checks are enough.
- `bulk_analysis`: pagination, aggregation, top-N, spreadsheet intersection, or many token accounts are required.
- `tool_backed_analysis`: a known CLI/script/tool already exists and the user asked to use it.

If the task is `bulk_analysis` and no approved tool or bundled script exists, do not silently create project scripts. Explain that an execution layer is needed and ask whether to create a temporary script, use an external indexer/API, or narrow the scope. If the user explicitly asked for end-to-end execution and accepts local computation, keep temporary code outside the project unless they ask to save it.

### 0.1 Prefer Bundled Executors

When a bundled executor fits the request, run it instead of creating new scripts:

```text
scripts/trace_solana_wallet.py            Solana wallet time-window trace.
scripts/trace_evm_wallet.py               EVM first-layer wallet trace.
scripts/expand_crosschain_cluster.py      Cross-chain multi-hop cluster expansion and related-wallet scoring.
scripts/trace_bridge_order.py             Relay/Gas.zip bridge order lookup.
scripts/trace_solana_mint_participants.py Solana mint launch top-N participant analysis.
scripts/fetch_okx_token_trades.py         OKX Web3 token trading activity and participant ranking.
scripts/trace_solana_mint_label_history.py Candidate label/address historical mint participation scan.
scripts/label_match.py                    Address-to-label-file matching.
```

For mint participant requests, map the user's requested count directly to `--top`. Examples: top10 uses `--top 10`, top50 uses `--top 50`. Do not hardcode 20 unless the user did not specify a count.

Before running an executor, briefly tell the user what you parsed:

```text
Parsed task: <task_type>
Inputs: <addresses/mint/tx>
Window: <exact time window>
Executor: <script>
Key defaults: <top/metric/depth/label sheets>
```

Render that notice in the user's language.

### 1. Build The Window Activity

For each starting address:

1. Pull transactions in the exact time window.
2. Separate:
   - native transfers,
   - token transfers,
   - internal transfers,
   - swaps,
   - bridge deposits/fills,
   - approvals/permits,
   - account create/close/rent/fee noise.
3. Summarize net asset changes, but choose the main trace path by material outflows and service interactions, not by net balance alone.

### 2. Identify The Main Flow

Classify each relevant movement:

- `plain_transfer`: ordinary address-to-address value transfer.
- `swap_or_dex_route`: DEX/router/AMM/CPI/multicall route; do not call the router the terminal wallet.
- `bridge_order`: bridge deposit/fill/order; switch to bridge orderbook.
- `platform_wallet`: CEX, Hyperliquid, exchange deposit, or platform-controlled wallet; mark and stop by default.
- `high_frequency_fanout`: service-like address with rapid commingled outgoing flows; do not force a terminal wallet.
- `insufficient_coverage`: API/session/indexer cannot prove the next hop.

### 3. Follow Cross-Chain Orders

When a transfer touches a known bridge, read `references/bridge-orderbooks.md` and query the matching orderbook/API.

For each bridge order, extract:

- origin chain, origin tx, origin sender,
- token and amount paid,
- destination chain, destination tx,
- recipient address,
- amount delivered,
- solver/router/depository where available,
- order status and timestamps.

If the bridge destination is a platform wallet, CEX, Hyperliquid account, or known exchange ledger, mark it and stop. Do not continue platform-internal tracing unless the user specifically asks for platform ledger analysis.

### 4. Destination First-Layer Rule

After bridge landing, perform only one destination-chain layer by default:

1. Confirm destination tx success and delivered asset.
2. Check whether the recipient later transfers or swaps that asset.
3. If no outgoing is detected, mark `terminal_no_outgoing_detected`.
4. If outgoing is detected, summarize the first outgoing and ask whether the user wants continuation.
5. If the outgoing is a swap/DEX route, explain it as a complex transaction rather than pretending the router is the final wallet.

Continue beyond this first layer only when:

- the user explicitly asked for full recursive tracing, or
- the task started on that destination chain and the user's requested depth/time window implies continuation.

### 5. Special Handling

Use `references/classification-rules.md` for detailed heuristics. The most important rules:

- `approve`, `permit`, and allowance changes are not fund movement.
- `transferFrom` is fund movement; attribute by actual balance deltas.
- Wrapped native token deposit/withdraw and token account close may explain balance changes.
- On Solana, inspect CPI, inner instructions, owner token balances, WSOL unwraps, and token account signatures.
- On EVM, inspect normal tx, ERC-20 transfers, internal tx, event logs, router calls, multicall, and contract code status.
- Do not identify a program, router, pool, solver, or exchange hot wallet as a personal terminal wallet.
- In cluster expansion, only clean wallet-to-wallet `direct_value_transfer` and `token_owner_transfer` edges may add positive related-wallet score. Keep swaps, pools, fee accounts, account close/rent, wrap/unwrap, approvals, and contract calls as non-scoring evidence.

## Output Rules

Default report structure:

1. `Conclusion` - one or two plain-language bullets.
2. `Main Flow` - arrow path with chain, amount, timestamp, and tx hashes.
3. `Transaction Meaning` - short explanation for swaps, bridges, platforms, or weird records.
4. `Stop Point` - terminal/stop status and why.
5. `Evidence` - compact list of tx hashes, order IDs, source APIs, and confidence notes.
6. `Next Step` - only include if continuation, missing API, or user confirmation is needed.

Render headings in the user's language. For Chinese users, use natural Simplified Chinese headings, but do not depend on hardcoded Chinese text from this file.

Use the exact status tags from `references/report-style.md`, but keep them secondary to the readable explanation.

When the user asks for professional output, include:

- full addresses,
- full tx hashes,
- source URLs/API names,
- confidence score components,
- unresolved branches,
- JSON graph or table if requested.

## Stop And Ask Conditions

Pause and ask the user before continuing when:

- a bridge recipient has already moved funds onward and the user did not explicitly request recursive tracing;
- a high-frequency fanout address would require broad branch expansion;
- a platform/exchange ledger would require platform-specific account analysis;
- API coverage is missing for a chain or bridge;
- continuing would require logged-in Arkham/Chrome state not currently available.

Do not ask before marking platform wallets/CEX/Hyperliquid as closed; mark them as platform terminals and stop.

## Evidence Discipline

Every conclusion needs at least one concrete evidence item:

- tx hash,
- bridge order ID,
- account/address label source,
- API response source,
- balance delta,
- or decoded instruction/event.

If two sources conflict, prefer live chain/runtime behavior, then captured network/API responses, then explorer UI text, then labels, then assumptions. Say when a claim is an inference.

## Safety And Privacy

- Never store API keys in skill files, source code, reports, or committed config.
- Never collect cookies, browser localStorage, wallet credentials, private keys, or seed phrases.
- Do not attempt to bypass login, Cloudflare, paywalls, or API authorization.
- For logged-in Arkham, rely on the user's existing authorized browser session and capture only necessary API responses.
- Keep reports focused on chain activity and service labels; avoid exposing unrelated local files or personal account data.
