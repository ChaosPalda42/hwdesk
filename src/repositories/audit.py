import json
import sqlite3


class AuditRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record(self, actor: str, action: str, entity: str, entity_id: int, details: dict) -> dict:
        details_json = json.dumps(details)
        cursor = self.conn.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details) VALUES (?, ?, ?, ?, ?)",
            (actor, action, entity, entity_id, details_json)
        )
        self.conn.commit()
        # Fetch the inserted row to return it with the ID
        row = self.conn.execute(
            "SELECT id, at, actor, action, entity, entity_id, details FROM audit_log WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()
        return self._row_to_dict(row)

    def list_recent(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, at, actor, action, entity, entity_id, details FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_for_entity(self, entity: str, entity_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, at, actor, action, entity, entity_id, details FROM audit_log "
            "WHERE entity = ? AND entity_id = ? ORDER BY id DESC",
            (entity, entity_id)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        # Convert sqlite3.Row to a plain dict
        result = {}
        for key in row.keys():
            value = row[key]
            # Convert 0/1 to False/True for boolean fields
            if key in ("active",) and isinstance(value, int):
                result[key] = bool(value)
            else:
                result[key] = value
        # Parse the details JSON string back to a dict
        if "details" in result and isinstance(result["details"], str):
            try:
                result["details"] = json.loads(result["details"])
            except (json.JSONDecodeError, TypeError):
                result["details"] = {}
        return result