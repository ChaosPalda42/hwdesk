from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from src.config import ASSET_STATUSES


class AssetRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, asset_tag: str, type: str, brand: str, model: str, serial_number: str, purchase_date: str, price: float, notes: str) -> dict:
        asset_tag = asset_tag.strip().upper()
        status = "in_stock"
        self.conn.execute(
            """
            INSERT INTO assets (asset_tag, type, brand, model, serial_number, purchase_date, price, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (asset_tag, type, brand, model, serial_number, purchase_date, price, status, notes)
        )
        self.conn.commit()
        return self.get_by_tag(asset_tag)

    def get(self, id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM assets WHERE id = ?", (id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_by_tag(self, tag: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM assets WHERE UPPER(asset_tag) = ?", (tag.upper(),)).fetchone()
        if row is None:
            return None
        return dict(row)

    def update(self, id: int, **fields) -> dict | None:
        allowed_fields = {
            "asset_tag",
            "type",
            "brand",
            "model",
            "serial_number",
            "purchase_date",
            "price",
            "notes"
        }
        updates = {k: v for k, v in fields.items() if k in allowed_fields}
        if not updates:
            return None

        set_clause = ", ".join([f"{k} = ?" for k in updates])
        values = list(updates.values()) + [id]
        self.conn.execute(
            f"UPDATE assets SET {set_clause} WHERE id = ?",
            values
        )
        self.conn.commit()
        return self.get(id)

    def set_status(self, id: int, status: str) -> bool:
        if status not in ASSET_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        result = self.conn.execute(
            "UPDATE assets SET status = ? WHERE id = ?",
            (status, id)
        )
        self.conn.commit()
        return result.rowcount > 0

    def list_all(self, status: str | None = None, type: str | None = None) -> list[dict]:
        query = "SELECT * FROM assets"
        params = []
        if status is not None or type is not None:
            query += " WHERE"
            if status is not None:
                query += " status = ?"
                params.append(status)
                if type is not None:
                    query += " AND"
            if type is not None:
                query += " type = ?"
                params.append(type)
        query += " ORDER BY asset_tag"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def search(self, q: str) -> list[dict]:
        query = """
            SELECT * FROM assets
            WHERE UPPER(asset_tag) LIKE ?
               OR UPPER(brand) LIKE ?
               OR UPPER(model) LIKE ?
               OR UPPER(serial_number) LIKE ?
            ORDER BY asset_tag
        """
        search_term = f"%{q.upper()}%"
        rows = self.conn.execute(query, (search_term, search_term, search_term, search_term)).fetchall()
        return [dict(row) for row in rows]