"""
Repository for device repairs.
Provides CRUD operations on the ``repairs`` table.
"""

import sqlite3
from typing import List, Optional, Dict


class RepairRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # Ensure rows are returned as dict-like objects
        self.conn.row_factory = sqlite3.Row

    def create(
        self,
        asset_id: int,
        description: str,
        vendor: str,
        sent_at: str,
        cost: float,
        created_by: str,
    ) -> Dict:
        """Insert a new repair record and return the full row.

        The ``repairs`` table is expected to have at least the following columns:
        id (PK), asset_id, description, vendor, sent_at, cost, created_by,
        returned_at, result, created_at.
        """
        cursor = self.conn.execute(
            """
            INSERT INTO repairs (
                asset_id, description, vendor, sent_at, cost, created_by, returned_at, result, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, '', '', datetime('now'))
            RETURNING id
            """,
            (asset_id, description, vendor, sent_at, cost, created_by),
        )
        row = self.conn.execute(
            "SELECT * FROM repairs WHERE id = ?", (cursor.fetchone()["id"],)
        ).fetchone()
        self.conn.commit()
        return dict(row) if row else {}

    def get(self, repair_id: int) -> Optional[Dict]:
        """Return a single repair record or ``None`` if not found."""
        row = self.conn.execute(
            "SELECT * FROM repairs WHERE id = ?", (repair_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_for_asset(self, asset_id: int) -> List[Dict]:
        """List all repairs for a given asset ordered by newest first."""
        rows = self.conn.execute(
            "SELECT * FROM repairs WHERE asset_id = ? ORDER BY created_at DESC",
            (asset_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_open(self) -> List[Dict]:
        """List repairs that have not been returned yet.
        ``returned_at`` is empty string or NULL for open repairs.
        """
        rows = self.conn.execute(
            "SELECT * FROM repairs WHERE returned_at = '' OR returned_at IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(
        self,
        repair_id: int,
        returned_at: str,
        result: str,
        cost: float,
    ) -> Dict:
        """Mark a repair as closed and return the updated row."""
        self.conn.execute(
            "UPDATE repairs SET returned_at = ?, result = ?, cost = ? WHERE id = ?",
            (returned_at, result, cost, repair_id),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM repairs WHERE id = ?", (repair_id,)
        ).fetchone()
        return dict(row) if row else {}
