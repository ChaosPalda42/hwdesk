"""Admin web: invoices, tags, locations, attachments, labels, goods intake
and the short link printed on labels. Mounted without a prefix; every
/admin route is admin_required.
"""

from __future__ import annotations

import sqlite3

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, send_file

from src.auth.guards import actor, admin_required, current_user, login_required
from src.config import ASSET_CONDITIONS, ASSET_TYPES, TAG_COLORS
from src.db import get_db
from src.repositories.assignments import AssignmentRepository
from src.repositories.attachments import AttachmentRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.attachment_service import AttachmentError
from src.services.factory import (
    build_asset_service,
    build_attachment_service,
    build_intake_service,
    build_label_service,
)

bp = Blueprint("catalog", __name__)

_NO_PRINTER = "Není nastavena tiskárna (LABEL_PRINTER_HOST v Nastavení)."


def _ids(raw: str | None) -> list[int]:
    return [int(part) for part in (raw or "").split(",") if part.strip().isdigit()]


def _form_ids(field: str) -> list[int]:
    ids: list[int] = []
    for value in request.form.getlist(field):
        ids.extend(_ids(value))
    return ids


def _invoice_fields() -> dict:
    form = request.form
    return {
        "number": (form.get("number") or "").strip(),
        "supplier": (form.get("supplier") or "").strip(),
        "issued_at": (form.get("issued_at") or "").strip(),
        "total": float((form.get("total") or "0").replace(",", ".").replace(" ", "") or 0),
        "currency": (form.get("currency") or "CZK").strip() or "CZK",
        "notes": form.get("notes") or "",
    }


# --- invoices -------------------------------------------------------------

@bp.get("/admin/invoices")
@admin_required
def invoices():
    repo = InvoiceRepository(get_db())
    q = (request.args.get("q") or "").strip()
    return render_template("admin/invoices.html", invoices=repo.search(q) if q else repo.list_all(), q=q)


@bp.get("/admin/invoices/new")
@admin_required
def new_invoice():
    return render_template("admin/invoice_form.html", invoice=None)


@bp.post("/admin/invoices/new")
@admin_required
def create_invoice():
    fields = _invoice_fields()
    if not fields["number"]:
        return render_template("admin/invoice_form.html", invoice=None, error="Číslo faktury je povinné."), 400
    try:
        invoice = InvoiceRepository(get_db()).create(created_by=actor(), **fields)
    except sqlite3.IntegrityError:
        return render_template("admin/invoice_form.html", invoice=None, error=f"Faktura {fields['number']} už existuje."), 409
    flash(f"Faktura {invoice['number']} založena.")
    return redirect(f"/admin/invoices/{invoice['id']}")


@bp.get("/admin/invoices/<int:id>")
@admin_required
def invoice_detail(id: int):
    db = get_db()
    invoice = InvoiceRepository(db).get(id)
    if invoice is None:
        abort(404)
    assets_repo = build_asset_service(db).assets
    unassigned = [a for a in assets_repo.search_assets() if a.get("invoice_id") is None][:200]
    return render_template(
        "admin/invoice_detail.html",
        invoice=invoice,
        assets=assets_repo.search_assets(invoice_id=id),
        attachments=AttachmentRepository(db).list_for("invoice", id),
        unassigned=unassigned,
    )


@bp.post("/admin/invoices/<int:id>/edit")
@admin_required
def edit_invoice(id: int):
    repo = InvoiceRepository(get_db())
    if repo.get(id) is None:
        abort(404)
    fields = _invoice_fields()
    if not fields["number"]:
        flash("Číslo faktury je povinné.", "error")
        return redirect(f"/admin/invoices/{id}")
    try:
        repo.update(id, **fields)
        flash("Faktura uložena.")
    except sqlite3.IntegrityError:
        flash(f"Faktura {fields['number']} už existuje.", "error")
    return redirect(f"/admin/invoices/{id}")


@bp.post("/admin/invoices/<int:id>/assets")
@admin_required
def attach_assets(id: int):
    ids = _form_ids("asset_ids")
    if ids:
        count = build_asset_service(get_db()).attach_invoice(actor(), ids, id)
        flash(f"Přiřazeno zařízení: {count}.")
    return redirect(f"/admin/invoices/{id}")


# --- attachments ----------------------------------------------------------

def _upload(owner_type: str, owner_id: int, back: str):
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Vyberte soubor.", "error")
        return redirect(back)
    try:
        build_attachment_service(get_db()).store(
            actor=actor(),
            owner_type=owner_type,
            owner_id=owner_id,
            kind=request.form.get("kind") or "other",
            filename=upload.filename,
            mime_type=upload.mimetype or "application/octet-stream",
            data=upload.read(),
        )
        flash(f"Příloha {upload.filename} nahrána.")
    except AttachmentError as exc:
        flash(f"Přílohu nelze uložit: {exc}", "error")
    return redirect(back)


@bp.post("/admin/assets/<int:id>/attachments")
@admin_required
def add_asset_attachment(id: int):
    return _upload("asset", id, f"/admin/assets/{id}")


@bp.post("/admin/invoices/<int:id>/attachments")
@admin_required
def add_invoice_attachment(id: int):
    return _upload("invoice", id, f"/admin/invoices/{id}")


@bp.get("/admin/attachments/<int:id>")
@admin_required
def download_attachment(id: int):
    db = get_db()
    attachment = AttachmentRepository(db).get(id)
    if attachment is None:
        abort(404)
    return send_file(
        build_attachment_service(db).path_for(id),
        as_attachment=True,
        download_name=attachment["filename"],
        mimetype=attachment["mime_type"],
    )


@bp.post("/admin/attachments/<int:id>/delete")
@admin_required
def delete_attachment(id: int):
    db = get_db()
    attachment = AttachmentRepository(db).get(id)
    if attachment is None:
        abort(404)
    build_attachment_service(db).delete(actor(), id)
    flash("Příloha smazána.")
    owner = "invoices" if attachment["owner_type"] == "invoice" else "assets"
    return redirect(f"/admin/{owner}/{attachment['owner_id']}")


# --- tags -----------------------------------------------------------------

@bp.get("/admin/tags")
@admin_required
def tags():
    return render_template("admin/tags.html", tags=TagRepository(get_db()).list_all(), colors=TAG_COLORS)


@bp.post("/admin/tags")
@admin_required
def create_tag():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Název štítku je povinný.", "error")
        return redirect("/admin/tags")
    try:
        TagRepository(get_db()).create(name, request.form.get("color") or "gray")
        flash(f"Štítek {name} vytvořen.")
    except sqlite3.IntegrityError:
        flash(f"Štítek {name} už existuje.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect("/admin/tags")


@bp.post("/admin/tags/<int:id>/edit")
@admin_required
def edit_tag(id: int):
    try:
        if TagRepository(get_db()).update(id, name=(request.form.get("name") or "").strip() or None, color=request.form.get("color")) is None:
            abort(404)
        flash("Štítek uložen.")
    except sqlite3.IntegrityError:
        flash("Štítek s tímto názvem už existuje.", "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect("/admin/tags")


@bp.post("/admin/tags/<int:id>/delete")
@admin_required
def delete_tag(id: int):
    if not TagRepository(get_db()).delete(id):
        abort(404)
    flash("Štítek smazán.")
    return redirect("/admin/tags")


# --- locations ------------------------------------------------------------

@bp.get("/admin/locations")
@admin_required
def locations():
    return render_template("admin/locations.html", locations=LocationRepository(get_db()).list_all())


@bp.post("/admin/locations")
@admin_required
def create_location():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Název lokality je povinný.", "error")
        return redirect("/admin/locations")
    try:
        LocationRepository(get_db()).create(name, request.form.get("address") or "", request.form.get("notes") or "")
        flash(f"Lokalita {name} vytvořena.")
    except sqlite3.IntegrityError:
        flash(f"Lokalita {name} už existuje.", "error")
    return redirect("/admin/locations")


@bp.post("/admin/locations/<int:id>/edit")
@admin_required
def edit_location(id: int):
    try:
        updated = LocationRepository(get_db()).update(
            id,
            name=(request.form.get("name") or "").strip() or None,
            address=request.form.get("address"),
            notes=request.form.get("notes"),
        )
        if updated is None:
            abort(404)
        flash("Lokalita uložena.")
    except sqlite3.IntegrityError:
        flash("Lokalita s tímto názvem už existuje.", "error")
    return redirect("/admin/locations")


@bp.post("/admin/locations/<int:id>/delete")
@admin_required
def delete_location(id: int):
    try:
        if not LocationRepository(get_db()).delete(id):
            abort(404)
        flash("Lokalita smazána.")
    except sqlite3.IntegrityError:
        flash("Lokalitu nelze smazat, jsou na ní zařízení.", "error")
    return redirect("/admin/locations")


# --- labels ---------------------------------------------------------------

def _assets_for(ids: list[int]) -> list[dict]:
    repo = build_asset_service(get_db()).assets
    return [a for a in (repo.get(i) for i in ids) if a is not None]


@bp.get("/admin/labels")
@admin_required
def labels():
    service = build_label_service()
    assets = _assets_for(_ids(request.args.get("ids")))
    return render_template(
        "admin/labels.html",
        labels=[{"asset": a, "qr_svg": service.qr_svg(a)} for a in assets],
        printer_configured=bool(current_app.config.get("LABEL_PRINTER_HOST")),
    )


@bp.get("/admin/labels/zpl")
@admin_required
def labels_zpl():
    service = build_label_service()
    body = "".join(service.zpl(a) for a in _assets_for(_ids(request.args.get("ids"))))
    return Response(body, mimetype="text/plain")


@bp.post("/admin/labels/print")
@admin_required
def print_labels():
    raw = ",".join(str(i) for i in _form_ids("ids"))
    host = current_app.config.get("LABEL_PRINTER_HOST")
    if not host:
        flash(_NO_PRINTER, "error")
        return redirect(f"/admin/labels?ids={raw}")
    assets = _assets_for(_ids(raw))
    try:
        build_label_service().print_zpl(assets, host, int(current_app.config.get("LABEL_PRINTER_PORT") or 9100))
        flash(f"Odesláno na tiskárnu: {len(assets)} štítků.")
    except OSError as exc:
        flash(f"Tiskárna {host} neodpovídá: {exc}", "error")
    return redirect(f"/admin/labels?ids={raw}")


# --- intake ---------------------------------------------------------------

def _intake_page(error: str | None = None, status: int = 200):
    db = get_db()
    service = build_asset_service(db)
    return render_template(
        "admin/intake.html",
        types=ASSET_TYPES,
        conditions=ASSET_CONDITIONS,
        locations=LocationRepository(db).list_all(),
        tags=TagRepository(db).list_all(),
        invoices=InvoiceRepository(db).list_all(),
        next_tags={t: service.next_asset_tag(t) for t in ASSET_TYPES},
        error=error,
    ), status


@bp.get("/admin/intake")
@admin_required
def intake():
    return _intake_page()


@bp.post("/admin/intake")
@admin_required
def intake_submit():
    form = request.form
    try:
        quantity = int(form.get("quantity") or 1)
        unit_price = float((form.get("unit_price") or "0").replace(",", ".").replace(" ", "") or 0)
        location_id = int(form["location_id"]) if form.get("location_id") else None
        batch = build_intake_service(get_db()).create_batch(
            actor=actor(),
            type=form.get("type") or "",
            brand=(form.get("brand") or "").strip(),
            model=(form.get("model") or "").strip(),
            quantity=quantity,
            invoice_number=(form.get("invoice_number") or "").strip(),
            supplier=(form.get("supplier") or "").strip(),
            unit_price=unit_price,
            location_id=location_id,
            tag_names=[t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
            warranty_until=(form.get("warranty_until") or "").strip(),
            condition=form.get("condition") or "new",
        )
    except ValueError as exc:
        return _intake_page(error=str(exc), status=400)
    ids = ",".join(str(a["id"]) for a in batch["assets"])
    flash(f"Založeno {len(batch['assets'])} zařízení.")
    return redirect(f"/admin/intake/{ids}")


@bp.get("/admin/intake/<ids>")
@admin_required
def intake_batch(ids: str):
    assets = _assets_for(_ids(ids))
    if not assets:
        abort(404)
    return render_template("admin/intake_serials.html", assets=assets)


@bp.post("/admin/intake/<ids>/serials")
@admin_required
def intake_serials(ids: str):
    serials = {i: (request.form.get(f"serial_{i}") or "").strip() for i in _ids(ids)}
    count = build_intake_service(get_db()).set_serials(actor(), serials)
    flash(f"Sériová čísla uložena: {count}.")
    return redirect(f"/admin/labels?ids={ids}")


# --- short link printed on labels ------------------------------------------

@bp.get("/a/<tag>")
@login_required
def short_link(tag: str):
    db = get_db()
    asset = build_asset_service(db).assets.get_by_tag(tag)
    if asset is None:
        abort(404)
    user = current_user()
    if user and user["is_admin"]:
        return redirect(f"/admin/assets/{asset['id']}")
    employee = EmployeeRepository(db).get_by_email(user["email"]) if user else None
    open_assignment = AssignmentRepository(db).get_open_for_asset(asset["id"])
    if employee and open_assignment and open_assignment["employee_id"] == employee["id"]:
        return redirect("/")
    abort(404)
