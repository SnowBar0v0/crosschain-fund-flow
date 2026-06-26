# Bridge Orderbooks

Use bridge orderbooks to prove cross-chain continuity. Do not infer destination addresses only from router transfers when an orderbook exists.

## Relay

Orderbook:

```text
https://relay.link/transactions?address=<address>
```

API:

```text
https://api.relay.link/requests/v2?user=<address>&limit=20
https://api.relay.link/requests/v2?hash=<txHash>&limit=20
```

Extract:

- `id`, `status`, `user`, `recipient`, `createdAt`, `updatedAt`
- `data.inTxs[]`: origin chain, origin tx, paid token/amount from state changes
- `data.outTxs[]`: destination chain, destination tx, delivered token/amount from state changes
- solver/router/depository addresses from calldata/state changes when available

Known chain IDs seen in this workflow:

```text
1 = Ethereum
8453 = Base
792703809 = Solana
1337 = Hyperliquid destination in Relay context
```

Known Relay-related addresses from prior sampling:

```text
Solana relay-link: 7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ
Solana Relay solver: F7p3dFrjRTbtRp8FRF6qHLomXbKRBzpvBLjtQcfcgmNe
EVM solver: 0xf70da97812cb96acdf810712aa562db8dfa3dbef
EVM depository: 0x4cd00e387622c35bddb9b4c962c136462338bc31
EVM router candidates: 0x4337084d9e255ff0702461cf8895ce9e3b5ff108, 0xccc88a9d1b4ed6b0eaba998850414b24f1c315be
```

Classify repeated solver/depository/router addresses as bridge infrastructure, not terminal users.

## Mayan

Orderbook:

```text
https://explorer.mayan.finance/transactions
https://explorer.mayan.finance/tx/<orderOrTxId>
```

API:

```text
https://explorer-api.mayan.finance/v3/swaps
```

Use for Mayan/SWIFT orders. Extract source tx, destination tx, status, recipient, input/output assets, amount, and refund state.

## Gas.zip

Orderbook:

```text
https://www.gas.zip/scan
https://www.gas.zip/scan/tx/<txHash>
```

API patterns:

```text
https://backend.gas.zip/v2/search/<hash>
https://backend.gas.zip/v2/deposit/<hash>
https://backend.gas.zip/v2/outbound/<hash>
https://backend.gas.zip/v2/user/<address>
```

Known Solana trigger addresses:

```text
Program: FzuVV5WeLyWHDuX6SPbeLgqkvePDTzMCRKYAhDbiP3z3
Recipient: gasZT2bpe7mxu5wMgQbvry84vok5CuF2huCEokyC3qh
```

Classify Gas.zip as bridge infrastructure. Follow the orderbook to the destination recipient.

## deBridge

Orderbook:

```text
https://app.debridge.com/orders
https://app.debridge.com/order?orderId=<orderId>&txHash=<txHash>&chainId=<chainId>
```

Useful APIs:

```text
/api/Transaction/<txHash>/orderIds
/api/Transaction/<txHash>/liteModels
/api/Orders/<orderId>
```

If a swap route contains deBridge, treat the transaction as a cross-chain candidate and query the orderbook.

Known deBridge-related addresses from prior sampling:

```text
Solana: 2snHHreXbpJ7UwZxPe37gnUNf7Wx7wv6UKDSR2JckKuS
EVM: 0x555ce236c0220695b68341bc48c68d52210cc35b
EVM: 0xe547d2eed6dd60796013b485d284c17da1194c82
```

## THORChain

Explorer:

```text
https://thorchain.net/dashboard
https://thorchain.net/tx/<txHash>
```

APIs:

```text
https://gateway.liquify.com/chain/thorchain_midgard/v2/actions?txid=<txHash>
https://gateway.liquify.com/chain/thorchain_api/thorchain/inbound_addresses
```

Known EVM router/vault examples:

```text
Vault: 0x382d6d83a31a41a569ca45e6ca093036c2137d29
ETH router: 0xD37BbE5744D730a1d98d8DC97c42F0Ca46aD7146
BSC router: 0xb30ec53f98ff5947ede720d32ac2da7e52a5f56b
AVAX/BASE router: 0x00dc6100103BC402d490aEE3F9a5560cBd91f1d4
```

## NEAR Intents

Explorer:

```text
https://explorer.near-intents.org/
https://explorer.near-intents.org/transactions/<addressOrTx>
```

Use official explorer pages and Arkham labels when public APIs reject unauthenticated bulk queries.

Known EVM NEAR-related addresses from prior sampling:

```text
0x2CfF890f0378a11913B6129B2E97417a2c302680
0x233c5370CCfb3cD7409d9A3fb98ab94dE94Cb4Cd
0xbb2f33f73ccc2c74e3fb9bb8eb75241ac15337e0
```

## ChangeNOW And FixedFloat

Use Arkham entity transfers and labels when the user has authorized a logged-in session. Do not assume official APIs are available for forensic tracing.

Recommended entity slugs:

```text
changenow
fixedfloat
```

Mark these as platform/exchange service flows when labels and transfer evidence support it.
