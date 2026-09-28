"""Smoke test over a synthetic queue. Run: python test_server.py (or pytest)."""

import json
import tempfile
from pathlib import Path

import server


def _ticket(rid, prio, cat, summary):
    return {"id": rid, "source_file": f"{rid}.txt",
            "message": "Secret body text that must never leave",
            "triage": {"category": cat, "priority": prio, "summary": summary,
                       "entities": {"user": "Demo Person"},
                       "draft_reply": "Draft reply text", "confidence": "high",
                       "route": "service-desk"},
            "status": "pending_review"}


def test_tools():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        server.DATA_DIR = root

        assert server.queue_status().startswith("Inbox: 0")
        assert server.pending_items() == "No pending items."
        assert server.recent_decisions() == "No decisions logged."

        for sub in ("inbox", "pending", "outbox"):
            (root / sub).mkdir()
        (root / "inbox" / "t9.txt").write_text("hello", encoding="utf-8")
        (root / "outbox" / "t1.txt").write_text("reply", encoding="utf-8")
        for rid, prio, cat, summ in [
            ("t2", "P3", "software_issue", "Spreadsheet app crashes on open"),
            ("t3", "P1", "network_issue", "Floor offline, mail ops@demo.example"),
        ]:
            (root / "pending" / f"{rid}.json").write_text(
                json.dumps(_ticket(rid, prio, cat, summ)), encoding="utf-8")
        (root / "pending" / "broken.json").write_text("{", encoding="utf-8")
        log = [
            {"id": "t1", "decision": "approved", "ai_category": "password_reset",
             "ai_priority": "P2", "decided": "2026-01-01T10:00:00+00:00",
             "reply": "Reply text"},
            {"id": "t4", "decision": "rejected", "ai_category": "billing_question",
             "ai_priority": "P4", "decided": "2026-01-02T10:00:00+00:00",
             "reason": "wrong team, see /home/demo/notes.txt"},
        ]
        (root / "decisions.jsonl").write_text(
            "\n".join(json.dumps(x) for x in log) + "\nnot json\n",
            encoding="utf-8")

        status = server.queue_status()
        assert "Inbox: 1 message(s)" in status
        assert "Pending review: 2 (P1 1, P3 1)" in status
        assert "Outbox: 1 reply file(s)" in status
        assert "Decisions logged: 2 (approved 1, rejected 1)" in status

        pend = server.pending_items()
        assert pend.startswith("2 pending item(s):\nt3 P1 network_issue")
        assert "[email]" in pend and "ops@demo.example" not in pend
        assert "Secret body" not in pend and "Draft reply" not in pend
        assert "Demo Person" not in pend
        assert server.pending_items("p3").startswith("1 pending item(s):\nt2")
        assert server.pending_items("P2") == "No pending items at P2."

        recent = server.recent_decisions(1)
        assert recent.startswith("2 decision(s) logged, latest 1:\n[2026-01-02] t4 rejected")
        assert "[path]" in recent and "/home/" not in recent
        assert "Reply text" not in server.recent_decisions()

        assert server.search_decisions("password").startswith("1 decision(s)")
        assert "wrong team" in server.search_decisions("WRONG")
        assert server.search_decisions("cobol").startswith("No decisions")

        # A large queue is capped at 25 lines.
        for i in range(30):
            (root / "pending" / f"x{i:02}.json").write_text(
                json.dumps(_ticket(f"x{i:02}", "P4", "general_question", "q")),
                encoding="utf-8")
        assert server.pending_items().endswith("...and 7 more")


if __name__ == "__main__":
    test_tools()
    print("ok")
