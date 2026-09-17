import sqlite3
from typing import List, Dict, Optional

from src.config import TAG_COLORS


class TagRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, name: str, color: str = 'gray') -> dict:
        if color not in TAG_COLORS:
            raise ValueError(f"Invalid color '{color}'. Must be one of: {TAG_COLORS}")
        
        # Insert the tag
        cursor = self.conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (name, color)
        )
        self.conn.commit()
        
        # Return the created tag
        return dict(self.conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone())

    def get(self, id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?",
            (id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_name(self, name: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, name, color FROM tags WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))",
            (name,)
        ).fetchone()
        return dict(row) if row else None

    def update(self, id: int, name: str = None, color: str = None) -> Optional[dict]:
        # Check if tag exists
        existing = self.get(id)
        if not existing:
            return None
            
        # Build update query
        updates = []
        params = []
        
        if name is not None:
            # Check for duplicate name
            existing_name_check = self.conn.execute(
                "SELECT id FROM tags WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) AND id != ?",
                (name, id)
            ).fetchone()
            if existing_name_check:
                raise sqlite3.IntegrityError("Tag name already exists")
            
            updates.append("name = ?")
            params.append(name)
            
        if color is not None:
            if color not in TAG_COLORS:
                raise ValueError(f"Invalid color '{color}'. Must be one of: {TAG_COLORS}")
            updates.append("color = ?")
            params.append(color)
            
        if not updates:
            return existing
            
        # Execute update
        params.append(id)
        self.conn.execute(
            f"UPDATE tags SET {', '.join(updates)} WHERE id = ?",
            params
        )
        self.conn.commit()
        
        # Return updated tag
        return dict(self.conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?",
            (id,)
        ).fetchone())

    def delete(self, id: int) -> bool:
        # First remove all asset_tag associations
        self.conn.execute(
            "DELETE FROM asset_tags WHERE tag_id = ?",
            (id,)
        )
        
        # Then delete the tag
        cursor = self.conn.execute(
            "DELETE FROM tags WHERE id = ?",
            (id,)
        )
        self.conn.commit()
        
        return cursor.rowcount > 0

    def list_all(self) -> List[dict]:
        rows = self.conn.execute("""
            SELECT t.id, t.name, t.color,
                   (SELECT COUNT(*) FROM asset_tags at WHERE at.tag_id = t.id) as asset_count
            FROM tags t
            ORDER BY t.name
        """).fetchall()
        
        return [dict(row) for row in rows]

    def assign(self, asset_id: int, tag_id: int) -> bool:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO asset_tags (asset_id, tag_id) VALUES (?, ?)",
            (asset_id, tag_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def unassign(self, asset_id: int, tag_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
            (asset_id, tag_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def set_for_asset(self, asset_id: int, tag_ids: List[int]) -> None:
        # First remove all existing tags for this asset
        self.conn.execute(
            "DELETE FROM asset_tags WHERE asset_id = ?",
            (asset_id,)
        )
        
        # Then add the new tags
        if tag_ids:
            values = [(asset_id, tag_id) for tag_id in tag_ids]
            placeholders = ','.join(['(?, ?)'] * len(values))
            query = f"INSERT INTO asset_tags (asset_id, tag_id) VALUES {placeholders}"
            flat_values = [item for pair in values for item in pair]
            self.conn.execute(query, flat_values)
        self.conn.commit()

    def for_asset(self, asset_id: int) -> List[dict]:
        rows = self.conn.execute("""
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            WHERE at.asset_id = ?
            ORDER BY t.name
        """, (asset_id,)).fetchall()
        
        return [dict(row) for row in rows]

    def for_assets(self, asset_ids: List[int]) -> Dict[int, List[dict]]:
        if not asset_ids:
            return {}
            
        placeholders = ','.join('?' * len(asset_ids))
        rows = self.conn.execute(f"""
            SELECT t.id, t.name, t.color, at.asset_id
            FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            WHERE at.asset_id IN ({placeholders})
            ORDER BY at.asset_id, t.name
        """, asset_ids).fetchall()
        
        result = {}
        for asset_id in asset_ids:
            result[asset_id] = []
            
        for row in rows:
            result[row["asset_id"]].append(dict(row))
            
        return result

    def asset_ids_with(self, tag_id: int) -> List[int]:
        rows = self.conn.execute(
            "SELECT asset_id FROM asset_tags WHERE tag_id = ?",
            (tag_id,)
        ).fetchall()
        
        return [row["asset_id"] for row in rows]