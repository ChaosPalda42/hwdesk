"""Admin web: dashboard, the asset catalogue, handovers, employees, audit.

Every route is admin_required; the actor of every change is the signed-in
admin (guards.actor()), never a form field. Catalogue side pages (invoices,
tags, locations, labels, intake) live in src/web/catalog.py.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, request

from src.auth.guards import actor, admin_required
from src.config import ASSET_CONDITIONS, ASSET_STATUSES, ASSET_TYPES
from src.db import get_db
from src.repositories.attachments import AttachmentRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_import_export import export_assets_csv
from src.services.asset_service import AssetValidationError, DuplicateAssetTag
from src.services.factory import build_asset_service, build_dashboard_service, build_handover_service
from src.services.handover_service import HandoverError

bp = Blueprint("admin", __name__, url_prefix="/admin")

PER_PAGE = 50
_FILTER_KEYS = ("q", "status", "type", "location_id", "tag_id", "employee_id", "condition")


def _int_or_none(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _ids(raw: str | None) -> list[int]:
    ids: list[int] = []
    for value in request.form.getlist("ids") if raw is None else [raw]:
        ids.extend(int(p) for p in value.split(",") if p.strip().isdigit())
    return ids


# --- dashboard -------------------------------------------------------------

@bp.route("")
@bp.route("/")
@bp.route("/dashboard")
@admin_required
def dashboard():
    stats = build_dashboard_service(get_db()).stats(today=date.today().isoformat(), warranty_days=90)
    return render_template("admin/dashboard.html", stats=stats)


# --- assets ---------------------------------------------------------------

@bp.get("/assets")
@admin_required
def assets_list():
    db = get_db()
    filters = {key: (request.args.get(key) or "").strip() for key in _FILTER_KEYS}
    sort = request.args.get("sort") or "asset_tag"
    page = max(1, _int_or_none(request.args.get("page")) or 1)
    rows = build_asset_service(db).assets.search_assets(
        q=filters["q"],
        status=filters["status"] or None,
        type=filters["type"] or None,
        location_id=_int_or_none(filters["location_id"]),
        tag_id=_int_or_none(filters["tag_id"]),
        employee_id=_int_or_none(filters["employee_id"]),
        condition=filters["condition"] or None,
        sort=sort,
    )
    total = len(rows)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, pages)
    window = rows[(page - 1) * PER_PAGE : page * PER_PAGE]
    tags = TagRepository(db).for_assets([r["id"] for r in window])
    return render_template(
        "admin/assets.html",
        assets=[{**r, "tags": tags.get(r["id"], [])} for r in window],
        filters=filters,
        types=ASSET_TYPES,
        statuses=ASSET_STATUSES,
        conditions=ASSET_CONDITIONS,
        tags=TagRepository(db).list_all(),
        locations=LocationRepository(db).list_all(),
        employees=EmployeeRepository(db).list_all(active_only=True),
        sort=sort,
        total=total,
        page=page,
        pages=pages,
    )


@bp.post("/assets/bulk")
@admin_required
def assets_bulk():
    db = get_db()
    service = build_asset_service(db)
    ids = _ids(request.form.get("ids"))
    action = request.form.get("action") or ""
    value = (request.form.get("value") or "").strip()
    back = request.form.get("back") or "/admin/assets"
    if not ids:
        flash("Nejdřív vyberte zařízení.", "error")
        return redirect(back)
    try:
        if action == "tag" and value:
            n = service.bulk_tag(actor(), ids, value)
            flash(f"Štítek „{value}“ přidán: {n} zařízení.")
        elif action == "untag" and value:
            n = service.bulk_tag(actor(), ids, value, remove=True)
            flash(f"Štítek „{value}“ odebrán: {n} zařízení.")
        elif action == "location":
            location_id = _int_or_none(value)
            n = 0
            for asset_id in ids:
                service.update(actor(), asset_id, location_id=location_id)
                n += 1
            flash(f"Lokalita změněna: {n} zařízení.")
        elif action == "invoice":
            invoice_id = _int_or_none(value)
            if invoice_id is None:
                invoice = InvoiceRepository(db).get_by_number(value)
                invoice_id = invoice["id"] if invoice else None
            if invoice_id is None:
                flash("Faktura nenalezena.", "error")
                return redirect(back)
            n = service.attach_invoice(actor(), ids, invoice_id)
            flash(f"Faktura přiřazena: {n} zařízení.")
        elif action == "labels":
            return redirect("/admin/labels?ids=" + ",".join(str(i) for i in ids))
        elif action == "export":
            lines = export_assets_csv(service.assets, TagRepository(db)).splitlines(keepends=True)
            header, body = lines[0], lines[1:]
            wanted = {a["asset_tag"] for a in (service.assets.get(i) for i in ids) if a}
            selected = [line for line in body if line.split(";", 1)[0].strip('"') in wanted]
            return Response(
                header + "".join(selected),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=zarizeni.csv"},
            )
        else:
            flash("Neznámá hromadná akce nebo chybí hodnota.", "error")
    except AssetValidationError as exc:
        flash(str(exc), "error")
    return redirect(back)


def _form_context(db, asset, error=None, next_tag=None):
    return dict(
        asset=asset,
        types=ASSET_TYPES,
        conditions=ASSET_CONDITIONS,
        tags=TagRepository(db).list_all(),
        locations=LocationRepository(db).list_all(),
        invoices=InvoiceRepository(db).list_all(),
        next_tag=next_tag,
        error=error,
    )


def _asset_fields() -> dict:
    form = request.form
    price = (form.get("price") or "0").replace(",", ".").replace(" ", "")
    return dict(
        type=form.get("type") or "",
        brand=(form.get("brand") or "").strip(),
        model=(form.get("model") or "").strip(),
        serial_number=(form.get("serial_number") or "").strip(),
        purchase_date=(form.get("purchase_date") or "").strip(),
        price=float(price or 0),
        notes=form.get("notes") or "",
        location_id=_int_or_none(form.get("location_id")),
        condition=form.get("condition") or "good",
        supplier=(form.get("supplier") or "").strip(),
        warranty_until=(form.get("warranty_until") or "").strip(),
        cost_center=(form.get("cost_center") or "").strip(),
        invoice_id=_int_or_none(form.get("invoice_id")),
        invoice_number=(form.get("invoice_number") or "").strip(),
        tag_names=[t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
    )


def _form_echo() -> dict:
    """The submitted form as the template's asset dict (tags as dicts)."""
    echo = dict(request.form)
    echo["tags"] = [{"name": t.strip()} for t in (request.form.get("tags") or "").split(",") if t.strip()]
    echo["location_id"] = _int_or_none(request.form.get("location_id"))
    echo["invoice_id"] = _int_or_none(request.form.get("invoice_id"))
    return echo


@bp.route("/assets/new", methods=["GET", "POST"])
@admin_required
def assets_new():
    db = get_db()
    service = build_asset_service(db)
    if request.method == "GET":
        return render_template("admin/asset_form.html", **_form_context(db, None, next_tag=service.next_asset_tag("notebook")))
    try:
        fields = _asset_fields()
        asset = service.create(actor(), (request.form.get("asset_tag") or "").strip().upper(), **fields)
    except (AssetValidationError, DuplicateAssetTag, ValueError) as exc:
        return render_template("admin/asset_form.html", **_form_context(db, _form_echo(), error=str(exc)))
    flash(f"Zařízení {asset['asset_tag']} založeno.")
    return redirect(f"/admin/assets/{asset['id']}")


@bp.get("/assets/<int:id>")
@admin_required
def assets_detail(id: int):
    db = get_db()
    service = build_asset_service(db)
    handovers = build_handover_service(db)
    asset = service.get(id)
    if asset is None:
        abort(404)
    history = [
        {**a, "employee": handovers.employees.get(a["employee_id"])}
        for a in handovers.assignments.history_for_asset(id)
    ]
    open_assignment = next((a for a in history if a["ended_at"] is None), None)
    return render_template(
        "admin/asset_detail.html",
        asset=asset,
        location=LocationRepository(db).get(asset["location_id"]) if asset.get("location_id") else None,
        holder=open_assignment["employee"] if open_assignment else None,
        open_assignment=open_assignment,
        handovers=[handovers.with_details(h) for h in handovers.handovers.list_for_asset(id)],
        history=history,
        attachments=AttachmentRepository(db).list_for("asset", id),
        employees=handovers.employees.list_all(active_only=True),
        tags_all=TagRepository(db).list_all(),
        locations_all=LocationRepository(db).list_all(),
    )


@bp.route("/assets/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def assets_edit(id: int):
    db = get_db()
    service = build_asset_service(db)
    asset = service.get(id)
    if asset is None:
        abort(404)
    if request.method == "GET":
        return render_template("admin/asset_form.html", **_form_context(db, asset))
    try:
        fields = _asset_fields()
        new_tag = (request.form.get("asset_tag") or "").strip().upper()
        if new_tag and new_tag != asset["asset_tag"]:
            fields["asset_tag"] = new_tag
        service.update(actor(), id, **fields)
    except (AssetValidationError, DuplicateAssetTag, ValueError) as exc:
        return render_template("admin/asset_form.html", **_form_context(db, {**asset, **_form_echo()}, error=str(exc)))
    flash("Zařízení uloženo.")
    return redirect(f"/admin/assets/{id}")


@bp.post("/assets/<int:id>/handover")
@admin_required
def assets_handover(id: int):
    service = build_handover_service(get_db())
    email = (request.form.get("employee_email") or "").strip().lower()
    employee = service.employees.get_by_email(email) if email else None
    if employee is None:
        flash("Vyberte zaměstnance.", "error")
        return redirect(f"/admin/assets/{id}")
    try:
        handover = service.start_handover(actor(), id, employee["id"], note=request.form.get("note") or "")
        flash(f"Žádost o potvrzení převzetí {handover['protocol_number']} odeslána na {employee['email']}.")
    except HandoverError as exc:
        flash(str(exc), "error")
    return redirect(f"/admin/assets/{id}")


@bp.post("/assets/<int:id>/return")
@admin_required
def assets_return(id: int):
    try:
        handover = build_handover_service(get_db()).start_return(actor(), id, note=request.form.get("note") or "")
        flash(f"Žádost o potvrzení vrácení {handover['protocol_number']} odeslána.")
    except HandoverError as exc:
        flash(str(exc), "error")
    return redirect(f"/admin/assets/{id}")


@bp.post("/assets/<int:id>/retire")
@admin_required
def assets_retire(id: int):
    try:
        build_asset_service(get_db()).retire(actor(), id)
        flash("Zařízení vyřazeno.")
    except AssetValidationError as exc:
        flash(str(exc), "error")
    return redirect(f"/admin/assets/{id}")


@bp.post("/assets/<int:id>/lost")
@admin_required
def assets_lost(id: int):
    try:
        build_asset_service(get_db()).mark_lost(actor(), id)
        flash("Zařízení označeno jako ztracené.")
    except AssetValidationError as exc:
        flash(str(exc), "error")
    return redirect(f"/admin/assets/{id}")


# --- handovers ------------------------------------------------------------

@bp.get("/handovers")
@admin_required
def handovers_list():
    service = build_handover_service(get_db())
    status = (request.args.get("status") or "").strip()
    rows = service.handovers.list_all(status=status or None)
    return render_template("admin/handovers.html", handovers=[service.with_details(h) for h in rows], status=status)


@bp.post("/handovers/<int:id>/cancel")
@admin_required
def handovers_cancel(id: int):
    try:
        build_handover_service(get_db()).cancel(actor(), id)
        flash("Žádost zrušena.")
    except HandoverError as exc:
        flash(str(exc), "error")
    return redirect(request.form.get("back") or "/admin/handovers")


# --- employees, audit -----------------------------------------------------

@bp.get("/employees")
@admin_required
def employees_list():
    repo = EmployeeRepository(get_db())
    q = (request.args.get("q") or "").strip()
    return render_template("admin/employees.html", employees=repo.search(q) if q else repo.list_all(), q=q)


@bp.get("/employees/<path:email>")
@admin_required
def employees_detail(email: str):
    service = build_handover_service(get_db())
    employee = service.employees.get_by_email(email.lower())
    if employee is None:
        abort(404)
    return render_template("admin/employee_detail.html", employee=employee, overview=service.overview_for_employee(employee["id"]))


@bp.get("/audit")
@admin_required
def audit():
    return render_template("admin/audit.html", entries=AuditRepository(get_db()).list_recent(200))
