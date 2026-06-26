# Report Style

Default to a readable Chinese report. Avoid dumping raw logs. Put the answer before the evidence.

## Default Template

````markdown
**先说结论**

这笔钱从 `<起点>` 出发，先通过 `<桥/平台/交易>` 到了 `<目标>`。目前我能确认它 `<停在何处/已继续转出/进入平台钱包>`。

**资金主线**

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

**这笔交易怎么理解**

用 2-5 句话解释它是普通转账、swap、桥订单、平台入金，还是复杂 CPI/multicall。不要把 router/pool/solver 当成最终用户地址。

**现在停在哪里**

`<status tags>`

一句话说明为什么停下，或者为什么需要用户确认再继续。

**证据**

- `<source>`: `<tx/order id/address label>`
- `<source>`: `<tx/order id/address label>`

**下一步**

只有需要继续追踪、缺 API、或需要用户确认时才写。
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
| 起点 | 主资金 | 路径 | 当前状态 | 置信度 |
|---|---:|---|---|---|
| `<addr>` | `6.605414 USDC` | Base -> Relay -> Solana | 未发现继续转出 | 高 |
```

## Status Tags

Use tags exactly as analysis metadata, but translate them in plain Chinese:

```text
closed_to_platform_wallet = 已闭环到平台钱包，不继续追平台内部账本
terminal_no_outgoing_detected = 当前未发现继续转出
first_layer_outgoing_detected = 第一层已继续转出，需要用户确认是否展开
not_closed_high_frequency_fanout = 高频分发节点，不能强行认定终点
not_closed_complex_dex_cpi_route = 复杂 DEX/CPI 路由，需要专门拆 swap
```

## Continuation Question

When continuation is needed, ask plainly:

```text
这个落地地址已经继续转出。我先停在第一层；要不要继续追 `<address>` 后面的路径？
```

If there are multiple branches:

```text
后面出现了 3 个分支。我建议先追金额最大的 `<branch>`，其余两条作为支线记录。是否继续？
```

## Tone

Prefer:

```text
这笔不是普通转账，更像是通过 Relay 把 Base 上的 USDC 打到 Solana。
```

Instead of:

```text
该交易疑似触发跨链桥接协议并完成异构链资产映射。
```

Use technical terms when they prevent ambiguity, especially `CPI`, `internal tx`, `transferFrom`, `orderbook`, `solver`, `router`, `token account owner`.
