import sqlite3
from typing import Optional, List, Dict, Any


class LocationRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, name: str, address: str = '', notes: str = '') -> Dict[str, Any]:
        # Insert new location and return the created record
        cursor = self.conn.execute(
            "INSERT INTO locations (name, address, notes) VALUES (?, ?, ?)",
            (name, address, notes)
        )
        self.conn.commit()
        # Fetch and return the created record
        row = self.conn.execute(
            "SELECT id, name, address, notes FROM locations WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    def get(self, id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT id, name, address, notes FROM locations WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            "SELECT id, name, address, notes FROM locations WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, id: int, name: Optional[str] = None, address: Optional[str] = None, notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # Build dynamic update query
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if address is not None:
            updates.append("address = ?")
            params.append(address)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return None

        # Add ID to params for WHERE clause
        params.append(id)

        query = f"UPDATE locations SET {', '.join(updates)} WHERE id = ?"
        self.conn.execute(query, params)
        self.conn.commit()

        # Fetch and return updated record
        row = self.conn.execute(
            "SELECT id, name, address, notes FROM locations WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def delete(self, id: int) -> bool:
        # Check if location is referenced by any asset
        count = self.conn.execute(
            "SELECT COUNT(*) FROM assets WHERE location_id = ?", (id,)
        ).fetchone()[0]
        if count > 0:
            raise sqlite3.IntegrityError('location is referenced by assets')

        # Perform deletion
        cursor = self.conn.execute("DELETE FROM locations WHERE id = ?", (id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, name, address, notes FROM locations ORDER BY name"
        ).fetchall()

        # Add asset_count for each location
        result = []
        for row in rows:
            row_dict = dict(row)
            asset_count = self.conn.execute(
                "SELECT COUNT(*) FROM assets WHERE location_id = ?", (row_dict['id'],)
            ).fetchone()[0]
            row_dict['asset_count'] = asset_count
            result.append(row_dict)

        return result