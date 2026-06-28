# Report Style

Default to a readable report in the user's language. Avoid dumping raw logs. Put the answer before the evidence.

This file intentionally keeps template labels in ASCII to avoid Windows encoding issues. When the user writes in Chinese, render the final report in natural Simplified Chinese.

## Default Template

````markdown
**Conclusion**

Funds moved from `<root>` through `<bridge/platform/route>` to `<target>`. The current trace state is `<stopped/moved onward/closed to platform wallet>`.

**Main Flow**

```text
<chain>:<address>
  -> <bridge/router/platform>
     <amount> <token>
     tx: <hash>
     time: <YYYY-MM-DD HH:mm:ss UTC+8>

<destination chain>:<recipient>
     received: <amount> <token>
     tx: <hash>
```

**Transaction Meaning**

Explain in 2-5 sentences whether this is a plain transfer, swap, bridge order, platform deposit, or complex CPI/multicall. Do not call a router, pool, or solver the final user wallet.

**Stop Point**

`<status tags>`

Explain why tracing stops here, or why user confirmation is needed before continuing.

**Evidence**

- `<source>`: `<tx/order id/address label>`
- `<source>`: `<tx/order id/address label>`

**Next Step**

Only include this section when continuation, missing API coverage, or user confirmation is needed.
````

## Professional Template

Use when the user asks for professional, forensic, JSON, or audit-style output.

Include:

- full tx hashes,
- full addresses,
- full order IDs,
- source API URLs or source names,
- chain IDs,
- token contract/mint,
- amount in raw and human units when useful,
- confidence and unresolved assumptions,
- status tags,
- branch table if multiple paths.

## Tables

Use small tables for multi-address summaries:

```markdown
| Root | Main Amount | Path | Current State | Confidence |
|---|---:|---|---|---|
| `<addr>` | `6.605414 USDC` | Base -> Relay -> Solana | no outgoing detected | high |
```

## Status Tags

Use tags exactly as analysis metadata. Translate the explanation into the user's language in the final answer:

```text
closed_to_platform_wallet = closed to a platform wallet; do not trace platform-internal ledger by default
terminal_no_outgoing_detected = no outgoing transfer detected in the inspected scope
first_layer_outgoing_detected = first-layer outgoing detected; ask before expanding
not_closed_high_frequency_fanout = high-frequency fanout node; do not force a fake terminal
not_closed_complex_dex_cpi_route = complex DEX/CPI route; requires swap reconstruction
```

## Continuation Question

When continuation is needed, ask plainly:

```text
The landing address has already moved funds onward. I stopped at the first layer. Should I continue tracing `<address>`?
```

If there are multiple branches:

```text
There are 3 downstream branches. I recommend following the largest branch `<branch>` first and recording the other two as side branches. Continue?
```

## Tone

Prefer:

```text
This is not a plain transfer; it looks more like Relay moving USDC from Base to Solana.
```

Instead of:

```text
The transaction appears to trigger a heterogeneous cross-chain asset mapping protocol.
```

Use technical terms when they prevent ambiguity, especially `CPI`, `internal tx`, `transferFrom`, `orderbook`, `solver`, `router`, `token account owner`.
