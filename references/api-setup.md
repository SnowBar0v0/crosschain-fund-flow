# API Setup

Use this reference only when required data sources are missing or the user is using the skill for the first time.

## Ask For Only What Is Missing

Do not request every key at once if the current task only needs one chain. Explain the minimum needed for the user's requested trace.

Never ask for private keys, seed phrases, wallet signatures, cookies, browser localStorage, or raw session headers.

## Recommended Environment Variables

```text
HELIUS_API_KEY=
ETHERSCAN_API_KEY=
BLOCKSCOUT_API_KEY=
ALCHEMY_API_KEY=
ROUTESCAN_API_KEY=
ARKHAM_CAPTURE_PROFILE=
```

All are optional until a task needs that provider. Keep secrets in the runtime environment or `.env` excluded from git.

Solscan Pro is a paid/permissioned path. Do not ask first-time users for `SOLSCAN_API_KEY` by default. Mention it only if the user says they have paid Pro access, wants to force Solscan, or needs a historical token-transfer index that no configured free provider can cover. To let auto mode try a paid Pro key, use:

```text
SOLSCAN_API_KEY=
CFF_ENABLE_SOLSCAN_PRO_AUTO=1
```

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

Use public market holder providers, Helius, or Solana RPC by default. Use Solscan Pro only when explicitly available:

- Solscan Pro/Helius are better for enhanced decoded transaction data, but Solscan Pro usually requires paid access.
- Solana RPC is enough for signatures, parsed transactions, balances, token-account owner checks, and verification.
- Candidate label-history scans can use Solana RPC without Solscan Pro: they scan the supplied owner addresses and inspect parsed token balance deltas. This is good for "did these label-sheet addresses ever trade in this window" checks, but it can be slower and can miss activity that only appears through token-account-only history or unavailable RPC history.
- Public OKX/APIBase and Binance Web3 market endpoints can provide token holder snapshots, token metadata, price, market cap, holder count, launch/create time, funding-source hints, and top-holder fallback without a user API key. Treat these as market-data providers.
- OKX Web3 token `交易活动` can provide no-key Solana token historical DEX trade rows through the bundled `fetch_okx_token_trades.py` executor, including wallet, tx hash, buy/sell side, token amount, value, DEX, tags, and pagination. Treat it as a historical DEX-trade index, not complete raw token-transfer truth.
- Binance Web3 token `历史成交` pages can be inspected in a browser and may show useful wallet/trade rows, but do not treat Binance as a stable global historical API until the exact paginated endpoint is confirmed.

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
