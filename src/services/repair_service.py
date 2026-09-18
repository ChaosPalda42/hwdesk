from typing import Dict

from src.repositories.assets import AssetRepository
from src.repositories.repairs import RepairRepository
from src.repositories.audit import AuditRepository


class RepairError(ValueError):
    """Domain‑specific error for repair operations."""


class RepairService:
    def __init__(self, assets: AssetRepository, repairs: RepairRepository, audit: AuditRepository):
        self.assets = assets
        self.repairs = repairs
        self.audit = audit

    def open_repair(
        self,
        actor: str,
        asset_id: int,
        description: str,
        vendor: str,
        sent_at: str,
        cost: float,
    ) -> Dict:
        # Verify the asset exists and is not retired or lost
        asset = self.assets.get(asset_id)
        if not asset:
            raise RepairError(f"Asset {asset_id} does not exist")
        status = asset.get("status", "")
        if status in ("retired", "lost"):
            raise RepairError(f"Cannot open repair for asset with status '{status}'")

        # Create the repair record
        created_by = actor.lower()
        repair = self.repairs.create(
            asset_id=asset_id,
            description=description,
            vendor=vendor,
            sent_at=sent_at,
            cost=cost,
            created_by=created_by,
        )

        # Record audit entry
        self.audit.record(
            actor=actor.lower(),
            action="repair.opened",
            entity="repair",
            entity_id=repair.get("id"),
            details={
                "asset_id": asset_id,
                "description": description,
                "vendor": vendor,
                "sent_at": sent_at,
                "cost": cost,
                "created_by": created_by,
            },
        )

        return repair

    def close_repair(
        self,
        actor: str,
        repair_id: int,
        returned_at: str,
        result: str,
        cost: float,
    ) -> Dict:
        # Fetch the repair and ensure it exists and is still open
        repair = self.repairs.get(repair_id)
        if not repair:
            raise RepairError(f"Repair {repair_id} does not exist")
        # An open repair has empty returned_at ('' or None)
        if repair.get("returned_at") not in ("", None):
            raise RepairError(f"Repair {repair_id} is already closed")

        updated = self.repairs.close(
            repair_id=repair_id,
            returned_at=returned_at,
            result=result,
            cost=cost,
        )

        # Record audit entry for closing
        self.audit.record(
            actor=actor.lower(),
            action="repair.closed",
            entity="repair",
            entity_id=repair_id,
            details={
                "returned_at": returned_at,
                "result": result,
                "cost": cost,
                "closed_by": actor.lower(),
            },
        )

        return updated
