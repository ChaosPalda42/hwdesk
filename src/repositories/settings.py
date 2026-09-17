import sqlite3
from typing import Optional


class SettingsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, key: str) -> Optional[str]:
        cur = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str, updated_by: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at, updated_by) "
            "VALUES (?, ?, datetime('now'), ?)",
            (key, value, updated_by)
        )
        self.conn.commit()

    def delete(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    def all(self) -> dict[str, str]:
        cur = self.conn.execute("SELECT key, value FROM settings")
        return dict(cur.fetchall())

    def version(self) -> int:
        # Count of rows plus max rowid
        cur = self.conn.execute("SELECT COUNT(*) as count, MAX(rowid) as max_rowid FROM settings")
        row = cur.fetchone()
        count = row[0] if row[0] is not None else 0
        max_rowid = row[1] if row[1] is not None else 0
        return count + max_rowid