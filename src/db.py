"""SQLite access for HW Desk: one connection per request, schema ensured once.

Every repository receives a connection through its constructor and never
opens one itself; routes obtain it with `get_db()`. Rows come back as
`sqlite3.Row` so both index and key access work.
"""

from __future__ import annotations

import sqlite3

from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,          -- lower-case, the login identity (UPN)
    display_name  TEXT NOT NULL,
    department    TEXT NOT NULL DEFAULT '',
    manager_email TEXT NOT NULL DEFAULT '',
    hr_id         TEXT NOT NULL DEFAULT '',      -- identifier in the HR system
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at     TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag     TEXT NOT NULL UNIQUE,          -- inventory number, e.g. NB-0042
    type          TEXT NOT NULL,                 -- one of config.ASSET_TYPES
    brand         TEXT NOT NULL DEFAULT '',
    model         TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    purchase_date TEXT NOT NULL DEFAULT '',      -- ISO date or ''
    price         REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'in_stock',  -- one of config.ASSET_STATUSES
    notes         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS handovers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL,               -- 'handover' | 'return'
    asset_id        INTEGER NOT NULL REFERENCES assets(id),
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    created_by      TEXT NOT NULL,               -- admin e-mail
    status          TEXT NOT NULL DEFAULT 'pending',  -- config.HANDOVER_STATUSES
    protocol_number TEXT NOT NULL UNIQUE,        -- e.g. HP-2026-000017
    note            TEXT NOT NULL DEFAULT '',
    decline_reason  TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at         TEXT,
    confirmed_at    TEXT,
    protocol_path   TEXT NOT NULL DEFAULT ''     -- stored PDF after confirmation
);

CREATE TABLE IF NOT EXISTS assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     INTEGER NOT NULL REFERENCES assets(id),
    employee_id  INTEGER NOT NULL REFERENCES employees(id),
    handover_id  INTEGER NOT NULL REFERENCES handovers(id),  -- the confirmed handover
    return_id    INTEGER REFERENCES handovers(id),           -- the confirmed return, when ended
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at     TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL DEFAULT (datetime('now')),
    actor      TEXT NOT NULL,                    -- e-mail or 'system' / 'api:<key-prefix>'
    action     TEXT NOT NULL,                    -- e.g. asset.created, handover.confirmed
    entity     TEXT NOT NULL,                    -- asset | employee | handover | assignment
    entity_id  INTEGER NOT NULL,
    details    TEXT NOT NULL DEFAULT ''          -- JSON
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_assignments_open ON assignments(asset_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_handovers_status ON handovers(status);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def get_db() -> sqlite3.Connection:
    """The connection for the current app's configured DATABASE path."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
