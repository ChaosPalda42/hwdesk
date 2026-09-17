"""JSON API: assets (mounted at /api/v1)."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from src.auth.guards import actor, api_auth_required
from src.db import get_db
from src.repositories.employees import EmployeeRepository
from src.repositories.tags import TagRepository
from src.services.asset_import_export import export_assets_csv, import_assets_csv
from src.services.asset_service import AssetValidationError, DuplicateAssetTag
from src.services.factory import build_asset_service

bp = Blueprint("api_assets", __name__)

# JSON keys accepted by create/update, passed 1:1 to the service.
_FIELDS = (
    "asset_tag", "type", "brand", "model", "serial_number", "purchase_date", "price", "notes",
    "location_id", "condition", "supplier", "warranty_until", "cost_center", "invoice_id", "invoice_number",
)

def _payload(data: dict, *, for_create: bool) -> dict:
    fields = {key: data[key] for key in _FIELDS if key in data}
    if "tags" in data:
        tags = data["tags"]
        fields["tag_names"] = [t.strip() for t in tags.split(",")] if isinstance(tags, str) else list(tags or [])
    if for_create:
        for key in ("asset_tag", "brand", "model", "serial_number", "purchase_date", "notes"):
            fields.setdefault(key, "")
        fields.setdefault("price", 0)
    return fields

def _with_tags(rows: list[dict]) -> list[dict]:
    tags = TagRepository(get_db()).for_assets([r["id"] for r in rows])
    return [{**r, "tags": tags.get(r["id"], [])} for r in rows]


@bp.get("/assets")
@api_auth_required
def list_assets():
    service = build_asset_service(get_db())
    args = request.args
    tag_id = args.get("tag_id", type=int)
    if args.get("tag") and tag_id is None:
        tag = service.tags.get_by_name(args["tag"])
        if tag is None:
            return jsonify([])
        tag_id = tag["id"]
    employee_id = None
    if args.get("employee_email"):
        employee = EmployeeRepository(get_db()).get_by_email(args["employee_email"])
        if employee is None:
            return jsonify([])
        employee_id = employee["id"]
    rows = service.assets.search_assets(
        q=args.get("q", ""),
        status=args.get("status") or None,
        type=args.get("type") or None,
        location_id=args.get("location_id", type=int),
        tag_id=tag_id,
        employee_id=employee_id,
        invoice_id=args.get("invoice_id", type=int),
        warranty_before=args.get("warranty_before") or None,
        sort=args.get("sort") or "asset_tag",
    )
    return jsonify(_with_tags(rows))


@bp.post("/assets")
@api_auth_required
def create_asset():
    data = request.get_json(silent=True) or {}
    if not data.get("type"):
        return jsonify({"error": "type is required"}), 400
    service = build_asset_service(get_db())
    try:
        asset = service.create(actor=actor(), **_payload(data, for_create=True))
    except DuplicateAssetTag as exc:
        return jsonify({"error": str(exc)}), 409
    except AssetValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asset), 201


@bp.get("/assets/export.csv")
@api_auth_required
def export_csv():
    db = get_db()
    text = export_assets_csv(build_asset_service(db).assets, TagRepository(db))
    return Response(text, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=assets.csv"})


@bp.post("/assets/import.csv")
@api_auth_required
def import_csv():
    service = build_asset_service(get_db())
    result = import_assets_csv(service, service.locations, actor(), request.get_data(as_text=True))
    return jsonify(result)


@bp.get("/assets/<int:id>")
@api_auth_required
def get_asset(id: int):
    service = build_asset_service(get_db())
    asset = service.get(id)
    if asset is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(asset)


@bp.patch("/assets/<int:id>")
@api_auth_required
def update_asset(id: int):
    data = request.get_json(silent=True) or {}
    service = build_asset_service(get_db())
    if service.get(id) is None:
        return jsonify({"error": "not found"}), 404
    try:
        asset = service.update(actor=actor(), asset_id=id, **_payload(data, for_create=False))
    except DuplicateAssetTag as exc:
        return jsonify({"error": str(exc)}), 409
    except AssetValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asset)


@bp.post("/assets/<int:id>/retire")
@api_auth_required
def retire_asset(id: int):
    return _transition(id, "retire")





def _transition(id: int, method: str):
    service = build_asset_service(get_db())
    if service.get(id) is None:
        return jsonify({"error": "not found"}), 404
    try:
        asset = getattr(service, method)(actor=actor(), asset_id=id)
    except AssetValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asset)