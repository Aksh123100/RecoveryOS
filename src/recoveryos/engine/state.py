from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from recoveryos.domain.models import RecoveryCase


class CaseStore:
    """Small durable SQLite state store for the live-sandbox integration."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or "recoveryos_state.sqlite3")
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS order_map (
                    order_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    event TEXT,
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                )"""
            )

    def has_event(self, event_id: str) -> bool:
        with self._connect() as c:
            return c.execute("SELECT 1 FROM processed_events WHERE event_id=?", (event_id,)).fetchone() is not None

    def mark_event(self, event_id: str, event: str | None):
        with self._connect() as c:
            c.execute("INSERT OR IGNORE INTO processed_events(event_id,event) VALUES(?,?)", (event_id, event))

    def get_case(self, case_id: str) -> RecoveryCase | None:
        with self._connect() as c:
            row = c.execute("SELECT state_json FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not row:
            return None
        return RecoveryCase(**json.loads(row[0]))

    def put_case(self, case: RecoveryCase):
        state = asdict(case)
        with self._connect() as c:
            c.execute(
                "INSERT INTO cases(case_id,state_json,updated_at) VALUES(?,?,strftime('%s','now')) "
                "ON CONFLICT(case_id) DO UPDATE SET state_json=excluded.state_json,updated_at=excluded.updated_at",
                (case.case_id, json.dumps(state, default=str)),
            )

    def map_order(self, order_id: str, case_id: str):
        if not order_id:
            return
        with self._connect() as c:
            c.execute("INSERT OR REPLACE INTO order_map(order_id,case_id) VALUES(?,?)", (order_id, case_id))

    def list_cases(self, limit: int = 25) -> list[dict]:
        with self._connect() as c:
            rows = c.execute("SELECT state_json FROM cases ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for (raw,) in rows:
            state = json.loads(raw)
            out.append({
                "case_id": state.get("case_id", ""),
                "amount": float(state.get("amount", 0)),
                "failure_code": state.get("failure_code", "UNKNOWN"),
                "status": state.get("status", "OPEN"),
                "last_action": (state.get("actions_attempted") or [None])[-1],
                "episode_retry_count": int(state.get("episode_retry_count", 0)),
                "agent_invoked": bool(state.get("agent_invoked", False)),
            })
        return out

    def case_id_for_order(self, order_id: str | None) -> str | None:
        if not order_id:
            return None
        with self._connect() as c:
            row = c.execute("SELECT case_id FROM order_map WHERE order_id=?", (order_id,)).fetchone()
        return row[0] if row else None

    def order_id_for_case(self, case_id: str) -> str | None:
        if not case_id:
            return None

        with self._connect() as c:
            row = c.execute(
                "SELECT order_id FROM order_map WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
                (case_id,),
            ).fetchone()

        return row[0] if row else None