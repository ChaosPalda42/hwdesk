from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

from src.config import ASSET_TYPES
from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository


class AssetValidationError(ValueError):
    pass


class DuplicateAssetTag(ValueError):
    pass


class AssetService:
    def __init__(self, assets: AssetRepository, audit: AuditRepository):
        self.assets = assets
        self.audit = audit

    def create(self, actor: str, asset_tag: str, type: str, brand: str, model: str, serial_number: str, purchase_date: str, price: float, notes: str) -> dict:
        # Validate and process asset_tag
        asset_tag = asset_tag.strip().upper()
        if not asset_tag:
            raise AssetValidationError("Asset tag cannot be empty")

        # Validate type
        if type not in ASSET_TYPES:
            raise AssetValidationError(f"Invalid asset type: {type}. Must be one of {ASSET_TYPES}")

        # Validate purchase_date
        if purchase_date and not self._is_valid_iso_date(purchase_date):
            raise AssetValidationError("Purchase date must be in YYYY-MM-DD format or empty")

        # Validate price
        try:
            price = float(price)
        except (ValueError, TypeError):
            raise AssetValidationError("Price must be a valid number")

        try:
            result = self.assets.create(
                asset_tag=asset_tag,
                type=type,
                brand=brand,
                model=model,
                serial_number=serial_number,
                purchase_date=purchase_date,
                price=price,
                notes=notes
            )
            
            # Record audit log
            self.audit.record(
                actor=actor,
                action="asset.created",
                entity="asset",
                entity_id=result["id"],
                details={
                    "asset_tag": asset_tag,
                    "type": type,
                    "brand": brand,
                    "model": model,
                    "serial_number": serial_number,
                    "purchase_date": purchase_date,
                    "price": price,
                    "notes": notes
                }
            )
            
            return result
            
        except sqlite3.IntegrityError:
            raise DuplicateAssetTag("Asset tag already exists")

    def get(self, id: int) -> dict | None:
        return self.assets.get(id)

    def update(self, actor: str, asset_id: int, **fields) -> dict:
        # Validate that the asset exists
        existing_asset = self.assets.get(asset_id)
        if not existing_asset:
            raise AssetValidationError("Asset not found")

        # Validate fields before updating
        validated_fields = {}
        for key, value in fields.items():
            if key == "asset_tag":
                validated_fields[key] = value.strip().upper()
                if not validated_fields[key]:
                    raise AssetValidationError("Asset tag cannot be empty")
            elif key == "type":
                if value not in ASSET_TYPES:
                    raise AssetValidationError(f"Invalid asset type: {value}. Must be one of {ASSET_TYPES}")
                validated_fields[key] = value
            elif key == "purchase_date":
                if value and not self._is_valid_iso_date(value):
                    raise AssetValidationError("Purchase date must be in YYYY-MM-DD format or empty")
                validated_fields[key] = value
            elif key == "price":
                try:
                    validated_fields[key] = float(value)
                except (ValueError, TypeError):
                    raise AssetValidationError("Price must be a valid number")
                validated_fields[key] = float(value)
            else:
                validated_fields[key] = value

        # Perform the update
        result = self.assets.update(asset_id, **validated_fields)

        # Record audit log
        self.audit.record(
            actor=actor,
            action="asset.updated",
            entity="asset",
            entity_id=asset_id,
            details=validated_fields
        )

        return result

    def retire(self, actor: str, asset_id: int) -> dict:
        # Check if the asset exists
        asset = self.assets.get(asset_id)
        if not asset:
            raise AssetValidationError("Asset not found")

        # Check status restrictions
        if asset["status"] in ("assigned", "pending_handover", "pending_return"):
            raise AssetValidationError("Cannot retire asset with status 'assigned', 'pending_handover' or 'pending_return'")

        # Set status to retired
        self.assets.set_status(asset_id, "retired")

        # Record audit log
        self.audit.record(
            actor=actor,
            action="asset.retired",
            entity="asset",
            entity_id=asset_id,
            details={"status": "retired"}
        )

        return self.assets.get(asset_id)

    def mark_lost(self, actor: str, asset_id: int) -> dict:
        # Check if the asset exists
        asset = self.assets.get(asset_id)
        if not asset:
            raise AssetValidationError("Asset not found")

        # Check status restrictions
        if asset["status"] in ("assigned", "pending_handover", "pending_return"):
            raise AssetValidationError("Cannot mark asset as lost with status 'assigned', 'pending_handover' or 'pending_return'")

        # Set status to lost
        self.assets.set_status(asset_id, "lost")

        # Record audit log
        self.audit.record(
            actor=actor,
            action="asset.lost",
            entity="asset",
            entity_id=asset_id,
            details={"status": "lost"}
        )

        return self.assets.get(asset_id)

    def list(self, status: str | None = None, type: str | None = None, q: str = '') -> list[dict]:
        if q:
            # Search by query string
            return self.assets.search(q)
        else:
            # Filter by status and type
            return self.assets.list_all(status, type)

    def _is_valid_iso_date(self, date_str: str) -> bool:
        """Check if a string is a valid ISO date (YYYY-MM-DD)."""
        import re
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))