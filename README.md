# triage-mcp

An MCP server over my [ai-triage-agent](https://github.com/aminafara123/ai-triage-agent) queue. A local LLM classifies support tickets and drafts replies, a human approves or rejects every one, and this server lets any MCP-capable AI client read that queue and the decision log.

It answers questions like "whats waiting for review?" or "what did I reject this week and why?" straight from the files the agent writes. Four tools, all read-only. The model can look at the queue but it cant approve, reject or send anything.

## Tools

| Tool | What it does |
|---|---|
| `queue_status()` | Counts for inbox, pending review by priority, outbox and logged decisions |
| `pending_items(priority)` | Tickets waiting for review, most urgent first, optional priority filter |
| `recent_decisions(limit)` | Latest human decisions from the audit log, newest first |
| `search_decisions(query)` | Search the decision log by id, outcome, category, priority or reject reason |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install mcp
```

It reads `~/aiProjects/aminWork/automation-portfolio/ai-triage-agent/`. Change `DATA_DIR` at the top of `server.py` if your copy lives somewhere else.

Wire it into Claude Code:

```bash
claude mcp add triage -- /path/to/triage-mcp/.venv/bin/python /path/to/triage-mcp/server.py
```

## Demo

What it looks like from Claude Code:

```
> anything urgent sitting in the triage queue?

⏺ triage · pending_items()

  2 pending item(s):
  demo-014 P1 security_incident -> security-team (high): User entered their password on a fake helpdesk link and asks what to do next.
  demo-017 P3 software_issue -> service-desk (medium): Spreadsheet app crashes when opening one monthly report file.

⏺ One P1. demo-014 looks like a phishing hit and is routed to security.
  Id review that one first. The Excel crash can wait.
```

The tickets above are demo data. The format is exactly what the server returns.

## Design notes

- **Read-only by construction.** No tool writes to the queue, the outbox or the log. Approving stays in `review.py` with a human at the keyboard.
- **Only metadata crosses the protocol.** Ticket bodies, extracted entities and reply text never leave the server. Summaries and reject reasons are cut to 100 characters with emails and home paths masked.
- **Small on purpose.** One file, standard library plus the `mcp` SDK.

## Honest notes

- It only reads what ai-triage-agent has already written. With an empty `pending/` folder most answers are zeros, which is normal between triage runs.
- The masking is regex based. It catches emails and home paths, not names written into a summary.
- All ticket content in the demo and the tests is made up. The logic is tested against a synthetic queue in `test_server.py`. Run `python test_server.py`.

## About

Al Amin Bashir Afara, Dubai · [github.com/aminafara123](https://github.com/aminafara123) · [linkedin.com/in/aminafara](https://www.linkedin.com/in/aminafara)
