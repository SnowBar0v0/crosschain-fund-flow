# Crosschain Fund Flow

## 中文简介

Crosschain Fund Flow 是一个用于链上资金追踪的 Codex Skill，面向 Solana、EVM 链、跨链桥订单簿、交易所地址和平台钱包等场景。

它的目标不是简单罗列交易，而是帮助调查者从地址或交易哈希出发，还原主要资金路径，识别跨链桥、DEX 路由、平台钱包和复杂交易，并用偏白话的方式说明“钱从哪里来、去了哪里、为什么在这里停止追踪”。

默认流程会在跨链落地后只做第一层检查；如果资金继续转出，会先询问用户是否继续展开。对于 CEX、Hyperliquid、ChangeNOW、FixedFloat 等平台钱包，会标记为平台闭环，不默认追踪平台内部账本。

作者：[SnowBar / @SNOWBAR0_0](https://x.com/SNOWBAR0_0)

## English Introduction

Crosschain Fund Flow is a Codex skill for tracing crypto fund movement across Solana, EVM chains, bridge orderbooks, exchanges, and platform wallets.

It is designed for practical investigation work: start from an address or transaction, reconstruct the main fund path, explain complex swaps or bridge records in plain language, and stop at the right point instead of pretending every router, pool, or platform ledger is a final wallet.

Created by [@SNOWBAR0_0](https://x.com/SNOWBAR0_0).

## 功能概览

- 追踪 Solana 与 EVM 地址在指定时间窗口内的资金流。
- 通过 Relay、Mayan、Gas.zip、deBridge、THORChain、NEAR Intents、ChangeNOW、FixedFloat 等桥或服务继续闭环。
- 优先使用跨链桥订单簿确认目标链、目标地址和到账交易，不靠猜。
- 遇到 CEX、平台钱包、Hyperliquid 账户或桥基础设施时做标记并停止。
- 发现落地地址继续转出时，默认暂停并询问是否继续追。
- 解释 Solana CPI、DEX swap、EVM multicall、`transferFrom`、token account close、internal transfer 等不直观交易。
- 默认输出偏白话；用户需要时再切换为更专业的证据型报告。

## 执行边界

这个项目带有可运行的 Python 执行器，用于 Solana 地址追踪、EVM 第一层追踪、跨链桥订单查询、Solana mint top-N 参与者分析、OKX Web3 token 交易活动抓取、候选标签地址历史参与扫描和标签匹配。它不是全链索引器；遇到超大范围分页、缺 API 权限、跨链桥未公开订单簿或平台内部账本时，会说明缺口并给出下一步需要的 API、订单簿或授权入口。

它不会默认在用户项目里临时创建本地脚本；批量分析会优先调用 skill 自带的 `scripts/` 执行器。

## What It Does

- Trace Solana and EVM wallet flows within a user-defined time window.
- Follow bridge routes through Relay, Mayan, Gas.zip, deBridge, THORChain, NEAR Intents, ChangeNOW, and FixedFloat workflows.
- Use bridge orderbooks when available instead of guessing destination addresses from raw transfers.
- Mark CEX, platform wallets, Hyperliquid accounts, and bridge infrastructure as service endpoints.
- Detect when funds continue from the destination chain and ask before expanding deeper.
- Explain unusual transactions such as Solana CPI routes, DEX swaps, EVM multicalls, `transferFrom`, token account closes, and internal transfers.
- Produce readable reports by default, with professional evidence-heavy output when requested.

## Execution Boundary

This skill includes runnable Python executors for Solana wallet traces, EVM first-layer traces, bridge order lookups, Solana mint top-N participant analysis, OKX Web3 token trading activity, candidate label-address history scans, and label matching. It is not a full-chain indexer. For very large pagination jobs, missing API permissions, unavailable bridge orderbooks, or platform-internal ledgers, it should explain the gap and state what API, orderbook, or authorized session is needed next.

It should not silently create temporary scripts inside a user's project. Bulk analysis should use the bundled `scripts/` executors first.

## Output Philosophy

The default report is written for humans first:

1. Say the conclusion first.
2. Show the main fund path.
3. Explain what the transaction actually means.
4. State where tracing stops and why.
5. List compact evidence: tx hashes, order IDs, labels, APIs, and confidence notes.

For audit-style usage, the skill can also produce full addresses, full tx hashes, confidence components, unresolved branches, and JSON-style graph summaries.

## Data Sources

The skill is data-source aware, but does not ship with secrets or API keys.

Recommended optional providers:

- Etherscan API V2 for Ethereum and supported EVM chains.
- Blockscout PRO API for broad EVM coverage and fallback.
- Alchemy Transfers API for fast EVM address-level scans.
- Solscan, Helius, or Solana RPC for Solana transaction verification.
- Public OKX/APIBase and Binance Web3 market endpoints for Solana/EVM token holder snapshots, token metadata, price, market cap, holder count, funding-source hints, and top-holder fallback.
- Public OKX Web3 trading activity endpoint for Solana and supported EVM token historical DEX trades, including wallet, tx hash, side, amount, value, DEX, tags, and pagination. For EVM contracts, pass the normal chain id, e.g. Ethereum `1`, BNB Chain `56`, Base `8453`, Arbitrum `42161`, Optimism `10`, Polygon `137`, Avalanche `43114`. Binance Web3 `历史成交` pages are useful visible evidence, but are not treated as a stable global historical API until their pagination endpoint is confirmed.
- Arkham logged-in browser session for entity labels only, especially ChangeNOW, FixedFloat, NEAR Intents, CEX labels, and hot-wallet attribution.
- Bridge orderbooks for Relay, Mayan, Gas.zip, deBridge, THORChain, and NEAR Intents.

Secrets should live in runtime environment variables, never in the repo.

## Install

Clone this repository into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/SnowBar0v0/crosschain-fund-flow.git ~/.codex/skills/crosschain-fund-flow
```

Then invoke it in Codex:

```text
Use $crosschain-fund-flow to trace this Solana address from 00:00 to 10:00 UTC+8.
```

Users do not need to write CLI flags. Natural-language requests are expected:

```text
用 $crosschain-fund-flow 看这个 mint 创建后 3 小时 top50 资金流向，和 JAK 表做交集。

用 $crosschain-fund-flow 看这个地址今天 0 点到 10 点资金最后停在哪里。

用 $crosschain-fund-flow 查这笔 Relay 跨链最后到了哪个 Solana 地址。
```

## First-Time Setup

The skill will only ask for the API keys needed for the current task.

Common environment variables:

```text
HELIUS_API_KEY=
ETHERSCAN_API_KEY=
BLOCKSCOUT_API_KEY=
ALCHEMY_API_KEY=
ROUTESCAN_API_KEY=
ARKHAM_CAPTURE_PROFILE=
```

Solscan Pro is not part of the default setup because it usually requires a paid key. If you do have paid Pro access, set `SOLSCAN_API_KEY` and explicitly select Solscan, or set `CFF_ENABLE_SOLSCAN_PRO_AUTO=1` to let `auto` try it.

Never provide private keys, seed phrases, wallet signatures, cookies, browser localStorage, or raw session headers.

## CLI Executors

This skill includes runnable executors:

```bash
python scripts/trace_solana_wallet.py --address <SOL_ADDRESS> --from-time "2026-06-26 00:00" --to-time "2026-06-26 10:00"

python scripts/trace_evm_wallet.py --address <EVM_ADDRESS> --chain-id 8453 --from-time "2026-06-26 00:00" --to-time "2026-06-26 10:00"

python scripts/trace_bridge_order.py --bridge relay --address <EVM_OR_SOL_ADDRESS>

python scripts/trace_solana_mint_participants.py --mint <MINT> --hours-after-create 3 --top 50 --label-file labels.xlsx --label-sheets JAK

python scripts/fetch_okx_token_trades.py --mint <MINT> --from-time "2026-06-25 10:00" --to-time "2026-06-25 13:00" --top 50 --label-file labels.xlsx --label-sheets JAK

python scripts/fetch_okx_token_trades.py --chain-id 1 --mint <EVM_TOKEN_CONTRACT> --from-time "2026-06-29 09:00" --to-time "2026-06-29 10:00" --top 50

python scripts/trace_solana_mint_label_history.py --mint <MINT> --hours-after-create 3 --label-file labels.xlsx --label-sheets JAK

python scripts/label_match.py <ADDRESS> --label-file labels.xlsx --label-sheets JAK
```

Use `--top 10`, `--top 20`, `--top 50`, or any requested count. The default is 20 only when the user does not specify a count.

Use `fetch_okx_token_trades.py` when the user needs no-key historical DEX trading activity for a Solana or EVM token. It uses OKX Web3's public trading-activity endpoint and supports time windows, pagination, top-N participant ranking, and label-sheet matching.

Use `trace_solana_mint_label_history.py` when the user wants to know whether addresses from a label sheet ever participated in a mint window, including wallets that bought/sold and later cleared to zero. It scans candidate owner signatures through Solana RPC and reports historical-only hits separately from current holders. This is candidate verification, not global all-wallet discovery.

## Project Structure

```text
SKILL.md
agents/openai.yaml
references/
  request-routing.md
  api-setup.md
  bridge-orderbooks.md
  classification-rules.md
  report-style.md
scripts/
  trace_solana_wallet.py
  trace_evm_wallet.py
  trace_bridge_order.py
  trace_solana_mint_participants.py
  fetch_okx_token_trades.py
  trace_solana_mint_label_history.py
  label_match.py
```

## Important Rules

- Platform wallets are marked and stopped by default.
- Bridge destinations get one first-layer check by default.
- If the destination wallet sends funds onward, the skill asks before continuing.
- High-frequency fanout addresses are not forced into fake terminal conclusions.
- DEX routers, pools, solvers, token programs, and temporary accounts are not treated as personal wallets.
- Arkham labels are used as attribution intelligence, not as the only transaction truth source.

## Author

Built and maintained by [@SNOWBAR0_0](https://x.com/SNOWBAR0_0).
