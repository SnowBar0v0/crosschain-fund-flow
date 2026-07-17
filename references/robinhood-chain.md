# Robinhood Chain

Use this reference for Robinhood Chain wallet traces, bridge continuity, and provider selection.

## Networks

| Network | Chain ID | Public RPC | Explorer / account API |
|---|---:|---|---|
| Mainnet | `4663` | `https://rpc.mainnet.chain.robinhood.com` | `https://robinhoodchain.blockscout.com` / `https://robinhoodchain.blockscout.com/api` |
| Testnet | `46630` | `https://rpc.testnet.chain.robinhood.com` | `https://explorer.testnet.chain.robinhood.com` / `https://explorer.testnet.chain.robinhood.com/api` |

Mainnet is included in the default cluster-expansion chain list. Testnet is supported only when explicitly selected so test activity is not mixed with value-bearing mainnet activity.

`trace_evm_wallet.py --chain-id 4663 --provider auto` and cluster expansion use the public Robinhood Blockscout instance without an API key. The supported account actions are `txlist`, `tokentx`, and `txlistinternal`. A Blockscout response with status `2` can still contain valid partial internal-transaction rows; retain those rows and disclose the partial-index warning when it matters.

## Canonical Mainnet Tokens

| Symbol | Contract |
|---|---|
| WETH | `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73` |
| USDG | `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` |

Treat symbols as display metadata and verify material conclusions against contract addresses.

## Cross-Chain Handling

- Relay orders expose Robinhood Chain as EIP-155 chain ID `4663`; render it as `robinhood`, not `evm_4663`.
- Follow both origin and destination transaction hashes from the Relay orderbook before attributing the recipient.
- Across deposits on Robinhood Chain may route USDG to USDC on another chain. Decode the destination chain, output token, recipient, and amount from the deposit event/order data rather than equating the router with the final recipient.
- Known Robinhood bridge infrastructure includes Across Universal SpokePool proxy `0xD29C85F15DF544bA632C9E25829fd29d767d7978` and Relay RouterV3 `0xb92fe925DC43a0ECdE6c8b1a2709c170Ec4fFf4f`. Classify these as bridge/service nodes and exclude them from related-wallet scoring.

## Sources

- Robinhood Chain connection details: `https://docs.robinhood.com/chain/connecting/`
- Robinhood Chain mainnet support article: `https://robinhood.com/us/en/support/articles/robinhood-chain-mainnet/`
- Canonical contract addresses: `https://docs.robinhood.com/chain/contracts/`
