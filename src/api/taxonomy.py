"""JSON API for the catalogue around assets: tags, locations, invoices,
attachments and the dashboard. Mounted under /api/v1 next to api_assets.

Repositories raise sqlite3.IntegrityError for duplicates and references,
ValueError for bad enumerations; the services raise their own error types.
Those map to 409 / 400 here, everything else propagates.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from flask import Blueprint, jsonify, request, send_file

from src.auth.guards import actor, api_auth_required
from src.db import get_db
from src.repositories.attachments import AttachmentRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetValidationError
from src.services.attachment_service import AttachmentError
from src.services.factory import build_asset_service, build_attachment_service, build_dashboard_service

bp = Blueprint("api_taxonomy", __name__)

_INVOICE_FIELDS = ("number", "supplier", "issued_at", "total", "currency", "notes")


def _json() -> dict:
    return request.get_json(silent=True) or {}


def _error(message: str, status: int):
    return jsonify({"error": message}), status


@bp.errorhandler(sqlite3.IntegrityError)
def _conflict(exc):
    return _error(str(exc), 409)


@bp.errorhandler(ValueError)
def _bad_value(exc):
    return _error(str(exc), 400)


@bp.errorhandler(AttachmentError)
def _bad_attachment(exc):
    return _error(str(exc), 400)


@bp.errorhandler(AssetValidationError)
def _bad_asset(exc):
    return _error(str(exc), 400)


# --- tags -----------------------------------------------------------------

@bp.get("/tags")
@api_auth_required
def list_tags():
    return jsonify(TagRepository(get_db()).list_all())


@bp.post("/tags")
@api_auth_required
def create_tag():
    data = _json()
    name = (data.get("name") or "").strip()
    if not name:
        return _error("name is required", 400)
    tag = TagRepository(get_db()).create(name, data.get("color") or "gray")
    return jsonify(tag), 201


@bp.patch("/tags/<int:id>")
@api_auth_required
def update_tag(id: int):
    data = _json()
    tag = TagRepository(get_db()).update(id, name=data.get("name"), color=data.get("color"))
    if tag is None:
        return _error("tag not found", 404)
    return jsonify(tag)


@bp.delete("/tags/<int:id>")
@api_auth_required
def delete_tag(id: int):
    if not TagRepository(get_db()).delete(id):
        return _error("tag not found", 404)
    return "", 204


# --- locations ------------------------------------------------------------

@bp.get("/locations")
@api_auth_required
def list_locations():
    return jsonify(LocationRepository(get_db()).list_all())


@bp.post("/locations")
@api_auth_required
def create_location():
    data = _json()
    name = (data.get("name") or "").strip()
    if not name:
        return _error("name is required", 400)
    location = LocationRepository(get_db()).create(name, data.get("address") or "", data.get("notes") or "")
    return jsonify(location), 201


@bp.patch("/locations/<int:id>")
@api_auth_required
def update_location(id: int):
    data = _json()
    location = LocationRepository(get_db()).update(
        id, name=data.get("name"), address=data.get("address"), notes=data.get("notes")
    )
    if location is None:
        return _error("location not found", 404)
    return jsonify(location)


@bp.delete("/locations/<int:id>")
@api_auth_required
def delete_location(id: int):
    if not LocationRepository(get_db()).delete(id):
        return _error("location not found", 404)
    return "", 204


# --- invoices -------------------------------------------------------------

@bp.get("/invoices")
@api_auth_required
def list_invoices():
    repo = InvoiceRepository(get_db())
    q = (request.args.get("q") or "").strip()
    return jsonify(repo.search(q) if q else repo.list_all())


@bp.post("/invoices")
@api_auth_required
def create_invoice():
    data = _json()
    number = (data.get("number") or "").strip()
    if not number:
        return _error("number is required", 400)
    invoice = InvoiceRepository(get_db()).create(
        number=number,
        supplier=data.get("supplier") or "",
        issued_at=data.get("issued_at") or "",
        total=float(data.get("total") or 0),
        currency=data.get("currency") or "CZK",
        notes=data.get("notes") or "",
        created_by=actor(),
    )
    return jsonify(invoice), 201


@bp.get("/invoices/<int:id>")
@api_auth_required
def get_invoice(id: int):
    db = get_db()
    invoice = InvoiceRepository(db).get(id)
    if invoice is None:
        return _error("invoice not found", 404)
    service = build_asset_service(db)
    return jsonify({
        **invoice,
        "assets": service.assets.search_assets(invoice_id=id),
        "attachments": AttachmentRepository(db).list_for("invoice", id),
    })


@bp.patch("/invoices/<int:id>")
@api_auth_required
def update_invoice(id: int):
    data = _json()
    fields = {key: data[key] for key in _INVOICE_FIELDS if key in data}
    if "total" in fields:
        fields["total"] = float(fields["total"] or 0)
    invoice = InvoiceRepository(get_db()).update(id, **fields)
    if invoice is None:
        return _error("invoice not found", 404)
    return jsonify(invoice)


@bp.delete("/invoices/<int:id>")
@api_auth_required
def delete_invoice(id: int):
    if not InvoiceRepository(get_db()).delete(id):
        return _error("invoice not found", 404)
    return "", 204


@bp.post("/invoices/<int:id>/assets")
@api_auth_required
def attach_invoice(id: int):
    ids = _json().get("asset_ids") or []
    if not isinstance(ids, list):
        return _error("asset_ids must be a list", 400)
    count = build_asset_service(get_db()).attach_invoice(actor(), [int(x) for x in ids], id)
    return jsonify({"attached": count})


# --- attachments ----------------------------------------------------------

def _store(owner_type: str, owner_id: int):
    db = get_db()
    owner = InvoiceRepository(db).get(owner_id) if owner_type == "invoice" else build_asset_service(db).assets.get(owner_id)
    if owner is None:
        return _error(f"{owner_type} not found", 404)
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _error("file is required", 400)
    attachment = build_attachment_service(db).store(
        actor=actor(),
        owner_type=owner_type,
        owner_id=owner_id,
        kind=request.form.get("kind") or "other",
        filename=upload.filename,
        mime_type=upload.mimetype or "application/octet-stream",
        data=upload.read(),
    )
    return jsonify(attachment), 201


@bp.get("/assets/<int:id>/attachments")
@api_auth_required
def list_asset_attachments(id: int):
    return jsonify(AttachmentRepository(get_db()).list_for("asset", id))


@bp.post("/assets/<int:id>/attachments")
@api_auth_required
def upload_asset_attachment(id: int):
    return _store("asset", id)


@bp.post("/invoices/<int:id>/attachments")
@api_auth_required
def upload_invoice_attachment(id: int):
    return _store("invoice", id)


@bp.get("/attachments/<int:id>")
@api_auth_required
def download_attachment(id: int):
    db = get_db()
    attachment = AttachmentRepository(db).get(id)
    if attachment is None:
        return _error("attachment not found", 404)
    return send_file(
        build_attachment_service(db).path_for(id),
        as_attachment=True,
        download_name=attachment["filename"],
        mimetype=attachment["mime_type"],
    )


@bp.delete("/attachments/<int:id>")
@api_auth_required
def delete_attachment(id: int):
    if not build_attachment_service(get_db()).delete(actor(), id):
        return _error("attachment not found", 404)
    return "", 204


# --- dashboard ------------------------------------------------------------

@bp.get("/dashboard")
@api_auth_required
def dashboard():
    return jsonify(build_dashboard_service(get_db()).stats(today=date.today().isoformat()))
