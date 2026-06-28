# API Setup

Use this reference only when required data sources are missing or the user is using the skill for the first time.

## Ask For Only What Is Missing

Do not request every key at once if the current task only needs one chain. Explain the minimum needed for the user's requested trace.

Never ask for private keys, seed phrases, wallet signatures, cookies, browser localStorage, or raw session headers.

## Recommended Environment Variables

```text
SOLSCAN_API_KEY=
HELIUS_API_KEY=
ETHERSCAN_API_KEY=
BLOCKSCOUT_API_KEY=
ALCHEMY_API_KEY=
ROUTESCAN_API_KEY=
ARKHAM_CAPTURE_PROFILE=
```

All are optional until a task needs that provider. Keep secrets in the runtime environment or `.env` excluded from git.

## What To Ask The User To Get

### Etherscan API V2

Use for Ethereum and supported EVM chains via:

```text
https://api.etherscan.io/v2/api?chainid=<chainId>&module=account&action=<action>&...
```

Needed actions: `txlist`, `tokentx`, `txlistinternal`, logs, receipts/proxy where available.

Ask the user to create a key from the Etherscan API dashboard. Remind them that the free tier covers selected chains only; BNB/Base/OP/Avalanche may require another provider or a paid tier depending on the current official list.

### Blockscout PRO API

Use as the broad EVM fallback, especially for chains Etherscan free tier does not cover.

Preferred Etherscan-compatible form:

```text
https://api.blockscout.com/v2/api?chain_id=<chainId>&module=account&action=<action>&address=<address>&apikey=<key>
```

Do not assume old per-instance endpoints will remain stable.

### Alchemy

Use `alchemy_getAssetTransfers` for fast address transfer scans on supported EVM chains.

Typical endpoint shape:

```text
https://eth-mainnet.g.alchemy.com/v2/<key>
https://base-mainnet.g.alchemy.com/v2/<key>
https://arb-mainnet.g.alchemy.com/v2/<key>
https://opt-mainnet.g.alchemy.com/v2/<key>
https://polygon-mainnet.g.alchemy.com/v2/<key>
```

Use RPC/receipt calls for single-transaction verification.

### Solana Providers

Use Solscan Pro, Helius, or Solana RPC depending on availability:

- Solscan/Helius are better for enhanced decoded transaction data.
- Solana RPC is enough for signatures, parsed transactions, balances, token-account owner checks, and verification.

If no enhanced Solana API is present, say that complex route decoding may be less complete.

### Arkham Logged-In Session

Use only when the task needs entity labels for services such as ChangeNOW, FixedFloat, NEAR Intents, or exchange hot wallets.

Requirements:

- The user must already be logged in in an authorized browser/session.
- Capture only needed Arkham API responses.
- Do not save cookies, headers, or localStorage.
- If the session is expired or blocked, ask the user to re-open/login manually.

## First-Use Message Template

Use a short message like:

```text
First use needs several read-only APIs. For this task, the minimum is:
- Etherscan V2: normal tx, ERC20 transfers, internal tx on EVM chains.
- Blockscout PRO: Base/OP/long-tail EVM fallback.
- Alchemy: fast address-level transfer scans, optional but useful.

Put keys in environment variables. Do not provide private keys, seed phrases, cookies, wallet signatures, or raw sessions.
```

Only mention Solscan/Helius/Arkham when the current task needs Solana enhanced parsing or entity labels.
