# Crosschain Fund Flow

Crosschain Fund Flow is a Codex skill for tracing crypto fund movement across Solana, EVM chains, bridge orderbooks, exchanges, and platform wallets.

It is designed for practical investigation work: start from an address or transaction, reconstruct the main fund path, explain complex swaps or bridge records in plain language, and stop at the right point instead of pretending every router, pool, or platform ledger is a final wallet.

Created by [@SNOWBAR0_0](https://x.com/SNOWBAR0_0).

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

