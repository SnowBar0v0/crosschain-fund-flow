# Execution Boundaries

Use this reference when the task requires bulk collection, aggregation, ranking, spreadsheet matching, or any local script.

## Main Rule

Do not silently create local scripts for bulk analysis.

First classify the task:

```text
manual_api_trace
bulk_analysis
tool_backed_analysis
```

Then tell the user what execution mode is required.

## When Direct API Work Is Enough

Use direct API/RPC/browser checks without asking for script approval when:

- the task has a small number of addresses or tx hashes;
- no top-N ranking or large pagination is required;
- the work can be completed with several API calls and manual reasoning;
- the user explicitly asked for a quick check or single-path trace.

## When To Ask Before Writing Scripts

Ask before creating or saving any script when the task includes:

- top-N holders, buyers, sellers, or funders;
- mint launch window analysis;
- pagination across many signatures, token accounts, or blocks;
- spreadsheet joins or label-sheet intersections;
- owner attribution across many token accounts;
- batch bridge-order matching;
- repeated API retries/rate-limit handling;
- any output file generation not explicitly requested.

Use a short prompt:

```text
This is bulk analysis, not a simple trace. I need an execution layer to paginate and aggregate data. Should I create a temporary script for this run, or would you prefer to provide/use an existing indexer or narrow the scope?
```

Render that prompt in the user's language.

## Temporary Script Rules

If the user approves temporary code:

- Place it in a temporary or clearly named working directory, not inside the skill.
- Do not modify the user's project source unless asked.
- Do not commit temporary analysis code unless asked.
- Print or report only summarized results, not huge raw logs.
- Delete or ignore temporary artifacts unless the user wants to keep them.

If a reusable script becomes necessary repeatedly, propose adding it as a formal `scripts/` resource in the skill in a separate update.

## Existing Tool Preference

Prefer existing tools in this order:

1. purpose-built explorer/orderbook API;
2. configured local project CLI;
3. official SDK/API client;
4. short temporary script approved by the user;
5. manual browser work only when API coverage is unavailable.

## What To Say When The Skill Has No Executor

Be explicit:

```text
The skill provides the investigation workflow and classification rules, but it does not currently include a bundled collector for this bulk task. To complete it accurately, I need either an indexer/API export or permission to run a temporary aggregation script.
```

Do not imply the skill is broken or not installed merely because it lacks a collector.
