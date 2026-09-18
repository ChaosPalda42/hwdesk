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

CREATE TABLE IF NOT EXISTS locations (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    address  TEXT NOT NULL DEFAULT '',
    notes    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tags (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL UNIQUE,
    color  TEXT NOT NULL DEFAULT 'gray'          -- gray | blue | green | yellow | red | purple
);

CREATE TABLE IF NOT EXISTS invoices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    number     TEXT NOT NULL UNIQUE,              -- invoice number as printed
    supplier   TEXT NOT NULL DEFAULT '',
    issued_at  TEXT NOT NULL DEFAULT '',          -- ISO date or ''
    total      REAL NOT NULL DEFAULT 0,
    currency   TEXT NOT NULL DEFAULT 'CZK',
    notes      TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (asset_id, tag_id)
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
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    location_id   INTEGER REFERENCES locations(id),
    condition     TEXT NOT NULL DEFAULT 'good',    -- new | good | worn | broken
    supplier      TEXT NOT NULL DEFAULT '',
    warranty_until TEXT NOT NULL DEFAULT '',      -- ISO date or ''
    cost_center   TEXT NOT NULL DEFAULT '',
    invoice_id    INTEGER REFERENCES invoices(id),  -- one invoice covers many assets
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
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

CREATE TABLE IF NOT EXISTS attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type  TEXT NOT NULL,                    -- 'asset' | 'invoice'
    owner_id    INTEGER NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'other',    -- invoice | photo | document | other
    filename    TEXT NOT NULL,                    -- original name shown to users
    stored_name TEXT NOT NULL UNIQUE,             -- name on disk under ATTACHMENTS_DIR
    mime_type   TEXT NOT NULL DEFAULT 'application/octet-stream',
    size        INTEGER NOT NULL DEFAULT 0,
    uploaded_by TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS repairs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     INTEGER NOT NULL REFERENCES assets(id),
    description  TEXT NOT NULL,
    vendor       TEXT NOT NULL DEFAULT '',
    sent_at      TEXT NOT NULL DEFAULT '',        -- ISO date
    returned_at  TEXT NOT NULL DEFAULT '',        -- ISO date or '' while open
    cost         REAL NOT NULL DEFAULT 0,
    result       TEXT NOT NULL DEFAULT '',        -- '' until closed
    created_by   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
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


# Columns added after the first release; applied to older databases on connect.
_ASSET_COLUMNS_ADDED = (
    ("location_id", "INTEGER REFERENCES locations(id)"),
    ("condition", "TEXT NOT NULL DEFAULT 'good'"),
    ("supplier", "TEXT NOT NULL DEFAULT ''"),
    ("warranty_until", "TEXT NOT NULL DEFAULT ''"),
    ("cost_center", "TEXT NOT NULL DEFAULT ''"),
    ("invoice_id", "INTEGER REFERENCES invoices(id)"),
    ("updated_at", "TEXT NOT NULL DEFAULT ''"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(assets)")}
    for column, definition in _ASSET_COLUMNS_ADDED:
        if column not in existing:
            conn.execute(f"ALTER TABLE assets ADD COLUMN {column} {definition}")
    conn.commit()


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
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
