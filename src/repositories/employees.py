from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class EmployeeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, email: str, display_name: str, department: str, manager_email: str, hr_id: str) -> dict:
        # Normalize email to lowercase
        email = email.lower()

        # Prepare the current UTC time for synced_at
        synced_at = datetime.now(timezone.utc).isoformat()

        # Check if employee exists by email
        existing = self.get_by_email(email)
        if existing:
            # Update existing employee, preserving active status and created_at
            self.conn.execute(
                """
                UPDATE employees
                SET display_name = ?, department = ?, manager_email = ?, hr_id = ?, synced_at = ?
                WHERE email = ?
                """,
                (display_name, department, manager_email, hr_id, synced_at, email)
            )
        else:
            # Insert new employee
            self.conn.execute(
                """
                INSERT INTO employees (email, display_name, department, manager_email, hr_id, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, display_name, department, manager_email, hr_id, synced_at)
            )

        self.conn.commit()

        # Return the updated/created employee record
        return self.get_by_email(email)

    def get(self, id: int) -> dict | None:
        cursor = self.conn.execute("SELECT * FROM employees WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def get_by_email(self, email: str) -> dict | None:
        cursor = self.conn.execute("SELECT * FROM employees WHERE LOWER(email) = ?", (email.lower(),))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_all(self, active_only: bool = False) -> list[dict]:
        query = "SELECT * FROM employees"
        params = ()
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY email"
        cursor = self.conn.execute(query, params)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search(self, q: str) -> list[dict]:
        query = """
            SELECT * FROM employees
            WHERE LOWER(display_name) LIKE ? OR LOWER(email) LIKE ?
            ORDER BY email
        """
        search_pattern = f"%{q.lower()}%"
        cursor = self.conn.execute(query, (search_pattern, search_pattern))
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def set_active(self, id: int, active: bool) -> bool:
        cursor = self.conn.execute("SELECT id FROM employees WHERE id = ?", (id,))
        if not cursor.fetchone():
            return False
        active_int = 1 if active else 0
        self.conn.execute("UPDATE employees SET active = ? WHERE id = ?", (active_int, id))
        self.conn.commit()
        return True

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        # Convert sqlite3.Row to a plain dict
        result = {}
        for key in row.keys():
            value = row[key]
            # Convert 0/1 to False/True for boolean fields
            if key in ("active",):
                result[key] = bool(value)
            else:
                result[key] = value
        return result