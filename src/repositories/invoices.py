import sqlite3
from typing import Dict, List, Optional, Any

class InvoiceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, number: str, supplier: str, issued_at: str, total: float, currency: str, notes: str, created_by: str) -> Dict:
        # Insert the invoice and get the new ID
        cursor = self.conn.execute(
            """
            INSERT INTO invoices (number, supplier, issued_at, total, currency, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (number, supplier, issued_at, total, currency, notes, created_by)
        )
        invoice_id = cursor.lastrowid

        # Fetch the full record to return
        self.conn.commit()
        return self.get(invoice_id)

    def get(self, id: int) -> Optional[Dict]:
        cursor = self.conn.execute(
            """
            SELECT id, number, supplier, issued_at, total, currency, notes, created_by, created_at
            FROM invoices
            WHERE id = ?
            """,
            (id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def get_by_number(self, number: str) -> Optional[Dict]:
        cursor = self.conn.execute(
            """
            SELECT id, number, supplier, issued_at, total, currency, notes, created_by, created_at
            FROM invoices
            WHERE UPPER(number) = UPPER(?)
            """,
            (number,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def update(self, id: int, **fields) -> Optional[Dict]:
        # Validate that the fields are allowed
        allowed_fields = {'number', 'supplier', 'issued_at', 'total', 'currency', 'notes'}
        if not fields or not allowed_fields.intersection(fields.keys()):
            return None

        # Build the SET clause dynamically
        set_clauses = []
        values = []
        for key, value in fields.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        set_clause = ", ".join(set_clauses)

        # Add the ID to values for WHERE clause
        values.append(id)

        # Execute the update
        cursor = self.conn.execute(
            f"""
            UPDATE invoices
            SET {set_clause}
            WHERE id = ?
            """,
            values
        )
        self.conn.commit()

        # Check if any rows were affected
        if cursor.rowcount == 0:
            return None

        # Return the updated record
        return self.get(id)

    def delete(self, id: int) -> bool:
        # Check if any assets reference this invoice
        cursor = self.conn.execute(
            "SELECT 1 FROM assets WHERE invoice_id = ? LIMIT 1",
            (id,)
        )
        if cursor.fetchone() is not None:
            raise sqlite3.IntegrityError('invoice is referenced by assets')

        # Proceed with deletion
        cursor = self.conn.execute(
            "DELETE FROM invoices WHERE id = ?",
            (id,)
        )
        self.conn.commit()

        # Return True if any rows were deleted
        return cursor.rowcount > 0

    def list_all(self) -> List[Dict]:
        cursor = self.conn.execute(
            """
            SELECT i.id, i.number, i.supplier, i.issued_at, i.total, i.currency, i.notes, i.created_by, i.created_at,
                   COUNT(a.id) AS asset_count,
                   (SELECT COUNT(*) FROM attachments WHERE owner_type = 'invoice' AND owner_id = i.id) AS attachment_count
            FROM invoices i
            LEFT JOIN assets a ON i.id = a.invoice_id
            GROUP BY i.id
            ORDER BY i.id DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def search(self, q: str) -> List[Dict]:
        # Search in number or supplier fields (case-insensitive)
        cursor = self.conn.execute(
            """
            SELECT i.id, i.number, i.supplier, i.issued_at, i.total, i.currency, i.notes, i.created_by, i.created_at,
                   COUNT(a.id) AS asset_count,
                   (SELECT COUNT(*) FROM attachments WHERE owner_type = 'invoice' AND owner_id = i.id) AS attachment_count
            FROM invoices i
            LEFT JOIN assets a ON i.id = a.invoice_id
            WHERE UPPER(i.number) LIKE UPPER(?) OR UPPER(i.supplier) LIKE UPPER(?)
            GROUP BY i.id
            ORDER BY i.id DESC
            """,
            (f"%{q}%", f"%{q}%")
        )
        return [dict(row) for row in cursor.fetchall()]