"""JSON API: repairs (mounted at /api/v1)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from src.auth.guards import api_auth_required, actor
from src.db import get_db
from src.repositories.assets import AssetRepository
from src.repositories.repairs import RepairRepository
from src.repositories.audit import AuditRepository
from src.services.repair_service import RepairService, RepairError

bp = Blueprint("api_repairs", __name__)

# Helper to build service with proper repositories
def _build_service() -> RepairService:
    db = get_db()
    return RepairService(
        assets=AssetRepository(db),
        repairs=RepairRepository(db),
        audit=AuditRepository(db),
    )

@bp.get("/assets/<int:asset_id>/repairs")
@api_auth_required
def list_repairs(asset_id: int):
    # Verify asset exists
    if AssetRepository(get_db()).get(asset_id) is None:
        return jsonify({"error": "Asset not found"}), 404
    repo = RepairRepository(get_db())
    repairs = repo.list_for_asset(asset_id)
    return jsonify(repairs)

@bp.post("/assets/<int:asset_id>/repairs")
@api_auth_required
def open_repair(asset_id: int):
    data = request.get_json(silent=True) or {}
    required = ["description", "vendor", "sent_at", "cost"]
    for key in required:
        if key not in data:
            return jsonify({"error": f"{key} is required"}), 400
    try:
        service = _build_service()
        repair = service.open_repair(
            actor=actor(),
            asset_id=asset_id,
            description=data["description"],
            vendor=data["vendor"],
            sent_at=data["sent_at"],
            cost=float(data["cost"]),
        )
    except RepairError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # unexpected validation errors
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Unexpected error in open_repair")
        raise
    return jsonify(repair), 201

@bp.post("/repairs/<int:repair_id>/close")
@api_auth_required
def close_repair(repair_id: int):
    data = request.get_json(silent=True) or {}
    required = ["returned_at", "result", "cost"]
    for key in required:
        if key not in data:
            return jsonify({"error": f"{key} is required"}), 400
    try:
        service = _build_service()
        updated = service.close_repair(
            actor=actor(),
            repair_id=repair_id,
            returned_at=data["returned_at"],
            result=data["result"],
            cost=float(data["cost"]),
        )
    except RepairError as exc:
        # Distinguish not‑found vs other domain errors
        msg = str(exc)
        if "does not exist" in msg:
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(updated), 200
