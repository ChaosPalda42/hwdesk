from __future__ import annotations

import sqlite3


class AttachmentRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, owner_type: str, owner_id: int, kind: str, filename: str, stored_name: str, mime_type: str, size: int, uploaded_by: str) -> dict:
        self.conn.execute(
            "INSERT INTO attachments (owner_type, owner_id, kind, filename, stored_name, mime_type, size, uploaded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_type, owner_id, kind, filename, stored_name, mime_type, size, uploaded_by)
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM attachments WHERE id = last_insert_rowid()").fetchone()
        return dict(row)

    def get(self, id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM attachments WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None

    def list_for(self, owner_type: str, owner_id: int) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM attachments WHERE owner_type = ? AND owner_id = ? ORDER BY id", (owner_type, owner_id)).fetchall()
        return [dict(row) for row in rows]

    def delete(self, id: int) -> bool:
        deleted = self.conn.execute("DELETE FROM attachments WHERE id = ?", (id,)).rowcount > 0
        self.conn.commit()
        return deleted

    def count_for(self, owner_type: str, owner_id: int) -> int:
        row = self.conn.execute("SELECT COUNT(*) as count FROM attachments WHERE owner_type = ? AND owner_id = ?", (owner_type, owner_id)).fetchone()
        return row["count"]