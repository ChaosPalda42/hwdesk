import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict


class AssignmentRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def open(self, asset_id: int, employee_id: int, handover_id: int) -> Dict:
        """Create a new assignment and return its details."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO assignments (asset_id, employee_id, handover_id, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (asset_id, employee_id, handover_id, now),
        )
        self.conn.commit()
        
        # Fetch and return the created assignment
        row = self.conn.execute(
            "SELECT * FROM assignments WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        
        # Convert 0/1 to boolean values
        return {
            "id": row["id"],
            "asset_id": row["asset_id"],
            "employee_id": row["employee_id"],
            "handover_id": row["handover_id"],
            "return_id": row["return_id"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"]
        }

    def get(self, id: int) -> Optional[Dict]:
        """Get an assignment by ID."""
        row = self.conn.execute(
            "SELECT * FROM assignments WHERE id = ?", (id,)
        ).fetchone()
        
        if row is None:
            return None
            
        # Convert 0/1 to boolean values
        return {
            "id": row["id"],
            "asset_id": row["asset_id"],
            "employee_id": row["employee_id"],
            "handover_id": row["handover_id"],
            "return_id": row["return_id"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"]
        }

    def get_open_for_asset(self, asset_id: int) -> Optional[Dict]:
        """Get the open assignment for an asset."""
        row = self.conn.execute(
            "SELECT * FROM assignments WHERE asset_id = ? AND ended_at IS NULL",
            (asset_id,)
        ).fetchone()
        
        if row is None:
            return None
            
        # Convert 0/1 to boolean values
        return {
            "id": row["id"],
            "asset_id": row["asset_id"],
            "employee_id": row["employee_id"],
            "handover_id": row["handover_id"],
            "return_id": row["return_id"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"]
        }

    def list_open_for_employee(self, employee_id: int) -> List[Dict]:
        """List all open assignments for an employee."""
        rows = self.conn.execute(
            "SELECT * FROM assignments WHERE employee_id = ? AND ended_at IS NULL",
            (employee_id,)
        ).fetchall()
        
        # Convert 0/1 to boolean values
        return [
            {
                "id": row["id"],
                "asset_id": row["asset_id"],
                "employee_id": row["employee_id"],
                "handover_id": row["handover_id"],
                "return_id": row["return_id"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"]
            }
            for row in rows
        ]

    def close(self, id: int, return_id: int) -> bool:
        """Close an assignment by setting ended_at and return_id."""
        # Check if the assignment exists and is not already closed
        existing = self.get(id)
        if existing is None or existing["ended_at"] is not None:
            return False
            
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE assignments SET ended_at = ?, return_id = ? WHERE id = ?",
            (now, return_id, id)
        )
        self.conn.commit()
        return True

    def history_for_asset(self, asset_id: int) -> List[Dict]:
        """Get the assignment history for an asset, newest first."""
        rows = self.conn.execute(
            "SELECT * FROM assignments WHERE asset_id = ? ORDER BY started_at DESC",
            (asset_id,)
        ).fetchall()
        
        # Convert 0/1 to boolean values
        return [
            {
                "id": row["id"],
                "asset_id": row["asset_id"],
                "employee_id": row["employee_id"],
                "handover_id": row["handover_id"],
                "return_id": row["return_id"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"]
            }
            for row in rows
        ]