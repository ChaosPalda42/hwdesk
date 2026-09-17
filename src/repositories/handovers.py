from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.config import HANDOVER_STATUSES


class HandoverRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        kind: str,
        asset_id: int,
        employee_id: int,
        created_by: str,
        protocol_number: str,
        note: str = "",
    ) -> dict[str, Any]:
        # Insert the new handover record
        self.conn.execute(
            """
            INSERT INTO handovers (
                kind, asset_id, employee_id, created_by, protocol_number, note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (kind, asset_id, employee_id, created_by, protocol_number, note),
        )
        self.conn.commit()
        # Retrieve the inserted record
        cursor = self.conn.execute(
            "SELECT * FROM handovers WHERE id = last_insert_rowid()"
        )
        row = cursor.fetchone()
        return dict(row)

    def get(self, id: int) -> dict[str, Any] | None:
        cursor = self.conn.execute(
            "SELECT * FROM handovers WHERE id = ?", (id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def mark_sent(self, id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE handovers SET sent_at = ? WHERE id = ?",
            (now, id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def set_status(
        self,
        id: int,
        status: str,
        confirmed_at: str | None = None,
        protocol_path: str | None = None,
        decline_reason: str | None = None,
    ) -> bool:
        if status not in HANDOVER_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        # Build the update query dynamically based on provided parameters
        updates = []
        params = []

        if confirmed_at is not None:
            updates.append("confirmed_at = ?")
            params.append(confirmed_at)
        if protocol_path is not None:
            updates.append("protocol_path = ?")
            params.append(protocol_path)
        if decline_reason is not None:
            updates.append("decline_reason = ?")
            params.append(decline_reason)

        updates.append("status = ?")
        params.append(status)
        params.append(id)

        query = f"UPDATE handovers SET {', '.join(updates)} WHERE id = ?"
        cursor = self.conn.execute(query, params)
        self.conn.commit()
        return cursor.rowcount > 0

    def next_protocol_number(self, year: int) -> str:
        prefix = f"HP-{year}-"
        cursor = self.conn.execute(
            "SELECT protocol_number FROM handovers WHERE protocol_number LIKE ?",
            (f"{prefix}%",),
        )
        rows = cursor.fetchall()
        count = len(rows)
        return f"{prefix}{count + 1:06d}"

    def list_all(self, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM handovers"
        params = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        if kind is not None:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY id DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def list_for_employee(self, employee_id: int) -> list[dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM handovers WHERE employee_id = ? ORDER BY id DESC",
            (employee_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_pending_for_employee(self, employee_id: int) -> list[dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM handovers WHERE employee_id = ? AND status = 'pending' ORDER BY id DESC",
            (employee_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_for_asset(self, asset_id: int) -> list[dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM handovers WHERE asset_id = ? ORDER BY id DESC",
            (asset_id,),
        )
        return [dict(row) for row in cursor.fetchall()]