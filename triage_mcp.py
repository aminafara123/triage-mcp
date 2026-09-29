#!/usr/bin/env python3
"""triage-mcp: an MCP server over my ai-triage-agent queue.

Exposes the triage queue and the human decision log as read-only tools
any MCP-capable model can call. What is waiting for review, what got
approved or rejected, and why.

Run (stdio):  triage-mcp
Wire into Claude Code:
  claude mcp add triage -- triage-mcp
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

DATA_DIR = Path(os.environ.get("TRIAGE_DATA_DIR", Path.home() / "aiProjects/aminWork/automation-portfolio/ai-triage-agent"))
CAP = 25

server = MCPServer(
    "triage",
    instructions=(
        "Read-only tools over a local support ticket triage queue. A local "
        "LLM classifies tickets into pending/, a human approves or rejects "
        "each draft reply, and every decision lands in decisions.jsonl."
    ),
)

# Every tool only reads local queue files, so one shared annotation set.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
HOME_PATH = re.compile(r"(/home/|/Users/|[A-Za-z]:\\Users\\)\S*")


def _clip(text, n: int = 100) -> str:
    # Summaries and reasons are free text, so emails and home paths go
    # and everything is cut short. Message bodies and replies never leave.
    text = HOME_PATH.sub("[path]", EMAIL.sub("[email]", str(text or "")))
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _capped(lines: list) -> str:
    out = "\n".join(lines[:CAP])
    if len(lines) > CAP:
        out += f"\n...and {len(lines) - CAP} more"
    return out


def _pending() -> list:
    items = []
    for p in sorted((DATA_DIR / "pending").glob("*.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return items


def _decisions() -> list:
    log = DATA_DIR / "decisions.jsonl"
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _count(folder: str) -> int:
    d = DATA_DIR / folder
    return sum(1 for p in d.iterdir() if p.is_file()) if d.is_dir() else 0


def _fmt_decision(d: dict) -> str:
    line = (f"[{str(d.get('decided', '?'))[:10]}] {_clip(d.get('id'), 40)} "
            f"{d.get('decision', '?')} (AI said {d.get('ai_category', '?')} "
            f"{d.get('ai_priority', '?')})")
    if d.get("reason"):
        line += f": {_clip(d['reason'])}"
    return line


@server.tool(annotations=READ_ONLY)
def queue_status() -> str:
    """Counts across the pipeline: inbox, pending review by priority,
    outbox, and logged decisions by outcome."""
    pending = _pending()
    decisions = _decisions()
    prios = Counter(r.get("triage", {}).get("priority", "?") for r in pending)
    outcomes = Counter(d.get("decision", "?") for d in decisions)
    lines = [
        f"Inbox: {_count('inbox')} message(s)",
        f"Pending review: {len(pending)}"
        + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(prios.items())) + ")"
           if pending else ""),
        f"Outbox: {_count('outbox')} reply file(s)",
        f"Decisions logged: {len(decisions)}"
        + (" (" + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())) + ")"
           if decisions else ""),
    ]
    return "\n".join(lines)


@server.tool(annotations=READ_ONLY)
def pending_items(priority: str = "") -> str:
    """Tickets waiting for human review, most urgent first, with category,
    route, model confidence and a short summary. Optional priority filter
    like "P1"."""
    items = _pending()
    if priority:
        items = [r for r in items
                 if r.get("triage", {}).get("priority", "").upper() == priority.upper()]
    if not items:
        return "No pending items" + (f" at {priority}." if priority else ".")
    items.sort(key=lambda r: (r.get("triage", {}).get("priority", "P9"),
                              str(r.get("id"))))
    lines = []
    for r in items:
        t = r.get("triage", {})
        lines.append(f"{_clip(r.get('id'), 40)} {t.get('priority', '?')} "
                     f"{t.get('category', '?')} -> {t.get('route', '?')} "
                     f"({t.get('confidence', '?')}): {_clip(t.get('summary'))}")
    return f"{len(items)} pending item(s):\n" + _capped(lines)


@server.tool(annotations=READ_ONLY)
def recent_decisions(limit: int = 10) -> str:
    """The latest human decisions from the audit log, newest first: what
    the AI proposed and whether the reviewer approved, edited or rejected."""
    decisions = _decisions()
    if not decisions:
        return "No decisions logged."
    limit = max(1, min(limit, CAP))
    recent = decisions[::-1][:limit]
    return (f"{len(decisions)} decision(s) logged, latest {len(recent)}:\n"
            + "\n".join(_fmt_decision(d) for d in recent))


@server.tool(annotations=READ_ONLY)
def search_decisions(query: str) -> str:
    """Case-insensitive search over the decision log by ticket id, outcome,
    AI category, priority or reject reason."""
    q = query.lower().strip()
    if not q:
        return "Empty query."
    fields = ("id", "decision", "ai_category", "ai_priority", "reason")
    hits = [d for d in reversed(_decisions())
            if any(q in str(d.get(f, "")).lower() for f in fields)]
    if not hits:
        return f"No decisions matching {query!r}."
    return (f"{len(hits)} decision(s) matching {query!r}:\n"
            + _capped([_fmt_decision(d) for d in hits]))


def main():
    server.run()


if __name__ == "__main__":
    main()
