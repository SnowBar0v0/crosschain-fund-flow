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

## What It Does

- Trace Solana and EVM wallet flows within a user-defined time window.
- Follow bridge routes through Relay, Mayan, Gas.zip, deBridge, THORChain, NEAR Intents, ChangeNOW, and FixedFloat workflows.
- Use bridge orderbooks when available instead of guessing destination addresses from raw transfers.
- Mark CEX, platform wallets, Hyperliquid accounts, and bridge infrastructure as service endpoints.
- Detect when funds continue from the destination chain and ask before expanding deeper.
- Explain unusual transactions such as Solana CPI routes, DEX swaps, EVM multicalls, `transferFrom`, token account closes, and internal transfers.
- Produce readable reports by default, with professional evidence-heavy output when requested.

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

## First-Time Setup

The skill will only ask for the API keys needed for the current task.

Common environment variables:

```text
SOLSCAN_API_KEY=
HELIUS_API_KEY=
ETHERSCAN_API_KEY=
BLOCKSCOUT_API_KEY=
ALCHEMY_API_KEY=
ROUTESCAN_API_KEY=
ARKHAM_CAPTURE_PROFILE=
```

Never provide private keys, seed phrases, wallet signatures, cookies, browser localStorage, or raw session headers.

## Project Structure

```text
SKILL.md
agents/openai.yaml
references/
  api-setup.md
  bridge-orderbooks.md
  classification-rules.md
  report-style.md
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
