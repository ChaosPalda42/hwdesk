import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from src.config import ASSET_STATUSES


class AssetRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        asset_tag: str,
        type: str,
        brand: str,
        model: str,
        serial_number: str,
        purchase_date: str,
        price: float,
        notes: str,
        location_id: Optional[int] = None,
        condition: str = "good",
        supplier: str = "",
        warranty_until: str = "",
        cost_center: str = "",
        invoice_id: Optional[int] = None,
    ) -> Dict:
        asset_tag = asset_tag.strip().upper()
        
        # Check if the asset tag already exists
        existing = self.conn.execute(
            "SELECT id FROM assets WHERE asset_tag = ?", (asset_tag,)
        ).fetchone()
        if existing:
            raise sqlite3.IntegrityError("Asset tag already exists")

        now = datetime.now().isoformat()
        result = self.conn.execute(
            """
            INSERT INTO assets (
                asset_tag, type, brand, model, serial_number,
                purchase_date, price, notes, location_id, condition,
                supplier, warranty_until, cost_center, invoice_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                asset_tag,
                type,
                brand,
                model,
                serial_number,
                purchase_date,
                price,
                notes,
                location_id,
                condition,
                supplier,
                warranty_until,
                cost_center,
                invoice_id,
                now,
            ),
        ).fetchone()
        
        self.conn.commit()
        
        # Fetch the created asset with all fields
        asset = self.get(result["id"])
        return asset

    def get(self, id: int) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM assets WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_tag(self, tag: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM assets WHERE UPPER(asset_tag) = ?", (tag.strip().upper(),)
        ).fetchone()
        return dict(row) if row else None

    def update(self, id: int, **fields) -> Optional[Dict]:
        # Get current asset to check if it exists
        existing = self.get(id)
        if not existing:
            return None
            
        # Build the update query dynamically
        allowed_fields = {
            "asset_tag", "type", "brand", "model", "serial_number",
            "purchase_date", "price", "notes", "location_id", "condition",
            "supplier", "warranty_until", "cost_center", "invoice_id"
        }
        
        # Filter fields to only allowed ones
        update_fields = {k: v for k, v in fields.items() if k in allowed_fields}
        
        if not update_fields:
            return existing
            
        # Add updated_at timestamp
        update_fields["updated_at"] = datetime.now().isoformat()
        
        # Build SET clause
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values()) + [id]
        
        self.conn.execute(
            f"UPDATE assets SET {set_clause} WHERE id = ?",
            values
        )
        
        self.conn.commit()
        
        # Return updated asset
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

    def list_all(self, status: Optional[str] = None, type: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM assets"
        params = []
        
        where_clauses = []
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if type is not None:
            where_clauses.append("type = ?")
            params.append(type)
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY asset_tag"
        
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def search(self, q: str) -> List[Dict]:
        query = """
            SELECT * FROM assets 
            WHERE UPPER(asset_tag) LIKE ? 
               OR UPPER(brand) LIKE ? 
               OR UPPER(model) LIKE ? 
               OR UPPER(serial_number) LIKE ?
            ORDER BY asset_tag
        """
        search_term = f"%{q.strip().upper()}%"
        rows = self.conn.execute(
            query,
            (search_term, search_term, search_term, search_term)
        ).fetchall()
        return [dict(row) for row in rows]

    def search_assets(
        self,
        q: str = "",
        status: Optional[str] = None,
        type: Optional[str] = None,
        location_id: Optional[int] = None,
        tag_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        warranty_before: Optional[str] = None,
        sort: str = "asset_tag",
        condition: Optional[str] = None
    ) -> List[Dict]:
        # Build the base query with joins
        query = """
            SELECT 
                a.*, 
                l.name as location_name,
                e.email as holder_email,
                e.display_name as holder_name,
                e.id as holder_employee_id
            FROM assets a
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN assignments ass ON a.id = ass.asset_id AND ass.ended_at IS NULL
            LEFT JOIN employees e ON ass.employee_id = e.id
        """
        
        params = []
        where_clauses = []
        
        # Add filters
        if status is not None:
            where_clauses.append("a.status = ?")
            params.append(status)
            
        if type is not None:
            where_clauses.append("a.type = ?")
            params.append(type)
            
        if location_id is not None:
            where_clauses.append("a.location_id = ?")
            params.append(location_id)
            
        if tag_id is not None:
            query += " JOIN asset_tags at ON a.id = at.asset_id "
            where_clauses.append("at.tag_id = ?")
            params.append(tag_id)
            
        if employee_id is not None:
            where_clauses.append("ass.employee_id = ?")
            params.append(employee_id)
            
        if invoice_id is not None:
            where_clauses.append("a.invoice_id = ?")
            params.append(invoice_id)

        if condition is not None:
            where_clauses.append("a.condition = ?")
            params.append(condition)
            
        if warranty_before is not None:
            where_clauses.append("a.warranty_until != '' AND a.warranty_until <= ?")
            params.append(warranty_before)
            
        if q:
            search_term = f"%{q.strip().upper()}%"
            where_clauses.append(
                "(UPPER(a.asset_tag) LIKE ? OR UPPER(a.brand) LIKE ? OR UPPER(a.model) LIKE ? OR UPPER(a.serial_number) LIKE ?)"
            )
            params.extend([search_term, search_term, search_term, search_term])
            
        # Add WHERE clause if needed
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        # Add sorting
        sort_fields = {
            "asset_tag": "a.asset_tag",
            "type": "a.type",
            "brand": "a.brand",
            "model": "a.model",
            "status": "a.status",
            "created_at": "a.created_at",
            "updated_at": "a.updated_at",
            "warranty_until": "a.warranty_until",
            "purchase_date": "a.purchase_date"
        }
        
        # Handle descending sort (prefixed with -)
        if sort.startswith("-"):
            sort_field = sort[1:]
            direction = "DESC"
        else:
            sort_field = sort
            direction = "ASC"
            
        if sort_field in sort_fields:
            query += f" ORDER BY {sort_fields[sort_field]} {direction}"
        else:
            # Default to asset_tag if unknown sort field
            query += " ORDER BY a.asset_tag"
            
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_by(self, field: str) -> Dict:
        if field not in ("status", "type", "condition", "location_id"):
            raise ValueError(f"Invalid field for count_by: {field}")
            
        query = f"SELECT {field}, COUNT(*) as count FROM assets GROUP BY {field}"
        rows = self.conn.execute(query).fetchall()
        
        result = {}
        for row in rows:
            key = row[field] if row[field] is not None else "None"
            result[key] = row["count"]
            
        return result