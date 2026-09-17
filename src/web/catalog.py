from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for, jsonify
from werkzeug.exceptions import NotFound

from src.auth.guards import admin_required, login_required, actor, current_user
from src.db import get_db
from src.services.factory import build_asset_service, build_attachment_service, build_label_service, build_intake_service
from src.repositories.tags import TagRepository
from src.repositories.locations import LocationRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.attachments import AttachmentRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.assignments import AssignmentRepository
from src.config import ASSET_TYPES, ASSET_STATUSES, ASSET_CONDITIONS, TAG_COLORS, ATTACHMENT_KINDS, ATTACHMENT_OWNERS, ATTACHMENT_ALLOWED_TYPES, HANDOVER_KINDS, HANDOVER_STATUSES

logger = logging.getLogger(__name__)

bp = Blueprint('catalog', __name__, url_prefix='')

# Invoices
@bp.route('/admin/invoices', methods=['GET'])
@admin_required
def invoices():
    db = get_db()
    
    q = request.args.get('q', '').strip()
    
    # Build query with optional search
    if q:
        # Search in invoice number, supplier, and notes
        query = """
            SELECT i.*, 
                   COUNT(DISTINCT a.id) as asset_count,
                   COUNT(DISTINCT att.id) as attachment_count
            FROM invoices i
            LEFT JOIN assets a ON i.id = a.invoice_id
            LEFT JOIN attachments att ON i.id = att.owner_id AND att.owner_type = 'invoice'
            WHERE i.number LIKE ? OR i.supplier LIKE ? OR i.notes LIKE ?
            GROUP BY i.id
            ORDER BY i.issued_at DESC, i.number
        """
        params = (f'%{q}%', f'%{q}%', f'%{q}%')
    else:
        query = """
            SELECT i.*, 
                   COUNT(DISTINCT a.id) as asset_count,
                   COUNT(DISTINCT att.id) as attachment_count
            FROM invoices i
            LEFT JOIN assets a ON i.id = a.invoice_id
            LEFT JOIN attachments att ON i.id = att.owner_id AND att.owner_type = 'invoice'
            GROUP BY i.id
            ORDER BY i.issued_at DESC, i.number
        """
        params = ()
    
    invoices = db.execute(query, params).fetchall()
    
    return render_template('admin/invoices.html', invoices=invoices, q=q)

@bp.route('/admin/invoices/new', methods=['GET'])
@admin_required
def new_invoice():
    return render_template('admin/invoice_form.html', invoice=None)

@bp.route('/admin/invoices/new', methods=['POST'])
@admin_required
def create_invoice():
    db = get_db()
    
    try:
        number = request.form.get('number', '').strip()
        supplier = request.form.get('supplier', '')
        issued_at = request.form.get('issued_at', '')
        total = request.form.get('total', '0')
        currency = request.form.get('currency', 'CZK')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not number:
            flash('Číslo faktury nemůže být prázdné', 'error')
            return render_template('admin/invoice_form.html', invoice=request.form)
        
        # Check if invoice already exists
        existing = db.execute("SELECT id FROM invoices WHERE number = ?", (number,)).fetchone()
        if existing:
            flash('Faktura s tímto číslem již existuje.', 'error')
            return render_template('admin/invoice_form.html', invoice=request.form)
        
        # Create new invoice
        db.execute("INSERT INTO invoices (number, supplier, issued_at, total, currency, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (number, supplier, issued_at, float(total), currency, notes, actor()))
        db.commit()
        
        # Get the created invoice ID
        new_invoice = db.execute("SELECT id FROM invoices WHERE number = ?", (number,)).fetchone()
        flash('Faktura byla úspěšně vytvořena', 'success')
        return redirect(url_for('catalog.invoice_detail', id=new_invoice['id']))
        
    except Exception as e:
        logger.exception("Error creating invoice")
        flash(f'Chyba při vytváření faktury: {str(e)}', 'error')
        return render_template('admin/invoice_form.html', invoice=request.form)

@bp.route('/admin/invoices/<int:id>', methods=['GET'])
@admin_required
def invoice_detail(id):
    db = get_db()
    
    # Get the invoice
    invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (id,)).fetchone()
    if not invoice:
        return "Faktura nenalezena", 404
    
    # Get assets associated with this invoice
    assets = db.execute("""
        SELECT a.*, l.name as location_name
        FROM assets a 
        LEFT JOIN locations l ON a.location_id = l.id
        WHERE a.invoice_id = ?
        ORDER BY a.asset_tag
    """, (id,)).fetchall()
    
    # Get attachments for this invoice
    attachments = db.execute("""
        SELECT * FROM attachments 
        WHERE owner_type = 'invoice' AND owner_id = ?
        ORDER BY uploaded_at DESC
    """, (id,)).fetchall()
    
    # Get unassigned assets for the picker (limited to 200)
    unassigned_assets = db.execute("""
        SELECT a.*, l.name as location_name
        FROM assets a 
        LEFT JOIN locations l ON a.location_id = l.id
        WHERE a.invoice_id IS NULL
        ORDER BY a.asset_tag
        LIMIT 200
    """).fetchall()
    
    return render_template('admin/invoice_detail.html', 
                         invoice=invoice, 
                         assets=assets,
                         attachments=attachments,
                         unassigned_assets=unassigned_assets)

@bp.route('/admin/invoices/<int:id>/edit', methods=['POST'])
@admin_required
def edit_invoice(id):
    db = get_db()
    
    try:
        number = request.form.get('number', '').strip()
        supplier = request.form.get('supplier', '')
        issued_at = request.form.get('issued_at', '')
        total = request.form.get('total', '0')
        currency = request.form.get('currency', 'CZK')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not number:
            flash('Číslo faktury nemůže být prázdné', 'error')
            return redirect(url_for('catalog.invoice_detail', id=id))
        
        # Check if another invoice already has this number
        existing = db.execute("SELECT id FROM invoices WHERE number = ? AND id != ?", (number, id)).fetchone()
        if existing:
            flash('Faktura s tímto číslem již existuje.', 'error')
            return redirect(url_for('catalog.invoice_detail', id=id))
        
        # Update invoice
        db.execute("UPDATE invoices SET number = ?, supplier = ?, issued_at = ?, total = ?, currency = ?, notes = ? WHERE id = ?",
                  (number, supplier, issued_at, float(total), currency, notes, id))
        db.commit()
        
        flash('Faktura byla úspěšně upravena', 'success')
        return redirect(url_for('catalog.invoice_detail', id=id))
        
    except Exception as e:
        logger.exception("Error editing invoice")
        flash(f'Chyba při úpravě faktury: {str(e)}', 'error')
        return redirect(url_for('catalog.invoice_detail', id=id))

@bp.route('/admin/invoices/<int:id>/assets', methods=['POST'])
@admin_required
def attach_assets_to_invoice(id):
    db = get_db()
    
    try:
        # Get the invoice
        invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (id,)).fetchone()
        if not invoice:
            return "Faktura nenalezena", 404
        
        # Get asset IDs from form
        asset_ids_str = request.form.get('asset_ids', '')
        if not asset_ids_str:
            flash('Nebyly vybrány žádné majetky', 'error')
            return redirect(url_for('catalog.invoice_detail', id=id))
        
        asset_ids = [int(x.strip()) for x in asset_ids_str.split(',') if x.strip()]
        
        # Attach assets to invoice
        for asset_id in asset_ids:
            db.execute("UPDATE assets SET invoice_id = ? WHERE id = ?", (id, asset_id))
        
        db.commit()
        
        flash('Majetek byl úspěšně přiřazen k faktuře', 'success')
        return redirect(url_for('catalog.invoice_detail', id=id))
        
    except Exception as e:
        logger.exception("Error attaching assets to invoice")
        flash(f'Chyba při přiřazování majetku k faktuře: {str(e)}', 'error')
        return redirect(url_for('catalog.invoice_detail', id=id))

# Attachments
@bp.route('/admin/assets/<int:id>/attachments', methods=['POST'])
@admin_required
def add_asset_attachment(id):
    db = get_db()
    
    try:
        # Validate owner exists
        asset = db.execute("SELECT * FROM assets WHERE id = ?", (id,)).fetchone()
        if not asset:
            flash('Majetek nenalezen', 'error')
            return redirect(url_for('catalog.asset_detail', id=id))
        
        # Get attachment service
        attachment_service = build_attachment_service(db)
        
        # Process the uploaded file
        kind = request.form.get('kind', 'other')
        file = request.files.get('file')
        
        if not file or file.filename == '':
            flash('Nebyl vybrán žádný soubor', 'error')
            return redirect(url_for('catalog.asset_detail', id=id))
        
        # Store attachment
        attachment_service.store(owner_type='asset', owner_id=id, kind=kind, file=file)
        flash('Příloha byla úspěšně přidána', 'success')
        return redirect(url_for('catalog.asset_detail', id=id))
        
    except Exception as e:
        logger.exception("Error adding asset attachment")
        flash(f'Chyba při přidávání přílohy: {str(e)}', 'error')
        return redirect(url_for('catalog.asset_detail', id=id))

@bp.route('/admin/invoices/<int:id>/attachments', methods=['POST'])
@admin_required
def add_invoice_attachment(id):
    db = get_db()
    
    try:
        # Validate owner exists
        invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (id,)).fetchone()
        if not invoice:
            flash('Faktura nenalezena', 'error')
            return redirect(url_for('catalog.invoice_detail', id=id))
        
        # Get attachment service
        attachment_service = build_attachment_service(db)
        
        # Process the uploaded file
        kind = request.form.get('kind', 'other')
        file = request.files.get('file')
        
        if not file or file.filename == '':
            flash('Nebyl vybrán žádný soubor', 'error')
            return redirect(url_for('catalog.invoice_detail', id=id))
        
        # Store attachment
        attachment_service.store(owner_type='invoice', owner_id=id, kind=kind, file=file)
        flash('Příloha byla úspěšně přidána', 'success')
        return redirect(url_for('catalog.invoice_detail', id=id))
        
    except Exception as e:
        logger.exception("Error adding invoice attachment")
        flash(f'Chyba při přidávání přílohy: {str(e)}', 'error')
        return redirect(url_for('catalog.invoice_detail', id=id))

@bp.route('/admin/attachments/<int:id>', methods=['GET'])
@admin_required
def download_attachment(id):
    db = get_db()
    
    try:
        # Get attachment info
        attachment = db.execute("SELECT * FROM attachments WHERE id = ?", (id,)).fetchone()
        if not attachment:
            return "Příloha nenalezena", 404
        
        # Get attachment service
        attachment_service = build_attachment_service(db)
        
        # Serve file
        return attachment_service.serve(attachment['stored_name'], 
                                      download_name=attachment['filename'],
                                      mimetype=attachment['mime_type'])
        
    except Exception as e:
        logger.exception("Error downloading attachment")
        flash(f'Chyba při stahování přílohy: {str(e)}', 'error')
        return "Chyba při stahování přílohy", 500

@bp.route('/admin/attachments/<int:id>/delete', methods=['POST'])
@admin_required
def delete_attachment(id):
    db = get_db()
    
    try:
        # Get attachment info
        attachment = db.execute("SELECT * FROM attachments WHERE id = ?", (id,)).fetchone()
        if not attachment:
            flash('Příloha nenalezena', 'error')
            return redirect(url_for('catalog.asset_detail', id=attachment['owner_id']) if attachment['owner_type'] == 'asset' else redirect(url_for('catalog.invoice_detail', id=attachment['owner_id'])))
        
        # Get owner type and ID
        owner_type = attachment['owner_type']
        owner_id = attachment['owner_id']
        
        # Get attachment service
        attachment_service = build_attachment_service(db)
        
        # Delete attachment
        attachment_service.delete(attachment['id'])
        flash('Příloha byla úspěšně odstraněna', 'success')
        
        # Redirect back to the owner's detail page
        if owner_type == 'asset':
            return redirect(url_for('catalog.asset_detail', id=owner_id))
        else:  # invoice
            return redirect(url_for('catalog.invoice_detail', id=owner_id))
        
    except Exception as e:
        logger.exception("Error deleting attachment")
        flash(f'Chyba při odstraňování přílohy: {str(e)}', 'error')
        return redirect(url_for('catalog.asset_detail', id=owner_id) if owner_type == 'asset' else redirect(url_for('catalog.invoice_detail', id=owner_id)))

# Tags
@bp.route('/admin/tags', methods=['GET'])
@admin_required
def tags():
    db = get_db()
    
    # Get all tags with asset counts
    tags = db.execute("""
        SELECT t.*, COUNT(at.asset_id) as asset_count
        FROM tags t
        LEFT JOIN asset_tags at ON t.id = at.tag_id
        GROUP BY t.id
        ORDER BY t.name
    """).fetchall()
    
    return render_template('admin/tags.html', tags=tags, TAG_COLORS=TAG_COLORS)

@bp.route('/admin/tags', methods=['POST'])
@admin_required
def create_tag():
    db = get_db()
    
    try:
        name = request.form.get('name', '').strip()
        color = request.form.get('color', 'gray')
        
        # Validate required fields
        if not name:
            flash('Název štítku nemůže být prázdný', 'error')
            return redirect(url_for('catalog.tags'))
        
        # Check if tag already exists
        existing = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if existing:
            flash('Štítek s tímto názvem již existuje.', 'error')
            return redirect(url_for('catalog.tags'))
        
        # Create new tag
        db.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
        db.commit()
        
        flash('Štítek byl úspěšně vytvořen', 'success')
        return redirect(url_for('catalog.tags'))
        
    except Exception as e:
        logger.exception("Error creating tag")
        flash(f'Chyba při vytváření štítku: {str(e)}', 'error')
        return redirect(url_for('catalog.tags'))

@bp.route('/admin/tags/<int:id>/edit', methods=['POST'])
@admin_required
def edit_tag(id):
    db = get_db()
    
    try:
        name = request.form.get('name', '').strip()
        color = request.form.get('color', 'gray')
        
        # Validate required fields
        if not name:
            flash('Název štítku nemůže být prázdný', 'error')
            return redirect(url_for('catalog.tags'))
        
        # Check if another tag already has this name
        existing = db.execute("SELECT id FROM tags WHERE name = ? AND id != ?", (name, id)).fetchone()
        if existing:
            flash('Štítek s tímto názvem již existuje.', 'error')
            return redirect(url_for('catalog.tags'))
        
        # Update tag
        db.execute("UPDATE tags SET name = ?, color = ? WHERE id = ?", (name, color, id))
        db.commit()
        
        flash('Štítek byl úspěšně upraven', 'success')
        return redirect(url_for('catalog.tags'))
        
    except Exception as e:
        logger.exception("Error editing tag")
        flash(f'Chyba při úpravě štítku: {str(e)}', 'error')
        return redirect(url_for('catalog.tags'))

@bp.route('/admin/tags/<int:id>/delete', methods=['POST'])
@admin_required
def delete_tag(id):
    db = get_db()
    
    try:
        # Delete tag (will fail if referenced by assets)
        db.execute("DELETE FROM tags WHERE id = ?", (id,))
        db.commit()
        
        flash('Štítek byl úspěšně odstraněn', 'success')
        return redirect(url_for('catalog.tags'))
        
    except Exception as e:
        logger.exception("Error deleting tag")
        flash(f'Chyba při odstraňování štítku: {str(e)}', 'error')
        return redirect(url_for('catalog.tags'))

# Locations
@bp.route('/admin/locations', methods=['GET'])
@admin_required
def locations():
    db = get_db()
    
    # Get all locations with asset counts
    locations = db.execute("""
        SELECT l.*, COUNT(a.id) as asset_count
        FROM locations l
        LEFT JOIN assets a ON l.id = a.location_id
        GROUP BY l.id
        ORDER BY l.name
    """).fetchall()
    
    return render_template('admin/locations.html', locations=locations)

@bp.route('/admin/locations', methods=['POST'])
@admin_required
def create_location():
    db = get_db()
    
    try:
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not name:
            flash('Název lokace nemůže být prázdný', 'error')
            return redirect(url_for('catalog.locations'))
        
        # Check if location already exists
        existing = db.execute("SELECT id FROM locations WHERE name = ?", (name,)).fetchone()
        if existing:
            flash('Lokace s tímto názvem již existuje.', 'error')
            return redirect(url_for('catalog.locations'))
        
        # Create new location
        db.execute("INSERT INTO locations (name, address, notes) VALUES (?, ?, ?)", (name, address, notes))
        db.commit()
        
        flash('Lokace byla úspěšně vytvořena', 'success')
        return redirect(url_for('catalog.locations'))
        
    except Exception as e:
        logger.exception("Error creating location")
        flash(f'Chyba při vytváření lokace: {str(e)}', 'error')
        return redirect(url_for('catalog.locations'))

@bp.route('/admin/locations/<int:id>/edit', methods=['POST'])
@admin_required
def edit_location(id):
    db = get_db()
    
    try:
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '')
        notes = request.form.get('notes', '')
        
        # Validate required fields
        if not name:
            flash('Název lokace nemůže být prázdný', 'error')
            return redirect(url_for('catalog.locations'))
        
        # Update location
        db.execute("UPDATE locations SET name = ?, address = ?, notes = ? WHERE id = ?", (name, address, notes, id))
        db.commit()
        
        flash('Lokace byla úspěšně upravena', 'success')
        return redirect(url_for('catalog.locations'))
        
    except Exception as e:
        logger.exception("Error editing location")
        flash(f'Chyba při úpravě lokace: {str(e)}', 'error')
        return redirect(url_for('catalog.locations'))

@bp.route('/admin/locations/<int:id>/delete', methods=['POST'])
@admin_required
def delete_location(id):
    db = get_db()
    
    try:
        # Delete location (will fail if referenced by assets)
        db.execute("DELETE FROM locations WHERE id = ?", (id,))
        db.commit()
        
        flash('Lokace byla úspěšně odstraněna', 'success')
        return redirect(url_for('catalog.locations'))
        
    except Exception as e:
        logger.exception("Error deleting location")
        flash(f'Chyba při odstraňování lokace: {str(e)}', 'error')
        return redirect(url_for('catalog.locations'))

# Labels
@bp.route('/admin/labels', methods=['GET'])
@admin_required
def labels():
    ids = request.args.get('ids', '')
    
    if ids:
        # Parse IDs
        asset_ids = [int(x.strip()) for x in ids.split(',') if x.strip()]
    else:
        asset_ids = []
    
    # Get assets for labels
    db = get_db()
    assets = []
    
    if asset_ids:
        placeholders = ','.join('?' * len(asset_ids))
        assets = db.execute(f"""
            SELECT a.*, l.name as location_name, t.name as tag_name
            FROM assets a 
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN asset_tags at ON a.id = at.asset_id
            LEFT JOIN tags t ON at.tag_id = t.id
            WHERE a.id IN ({placeholders})
            ORDER BY a.asset_tag
        """, asset_ids).fetchall()
    
    # Check if label printer is configured
    label_printer_host = current_app.config.get('LABEL_PRINTER_HOST', '')
    
    return render_template('admin/labels.html', 
                         labels=[{'asset': asset, 'qr_svg': None} for asset in assets],
                         printer_configured=bool(label_printer_host))

@bp.route('/admin/labels/zpl', methods=['GET'])
@admin_required
def labels_zpl():
    ids = request.args.get('ids', '')
    
    if not ids:
        return "", 204
    
    # Parse IDs
    asset_ids = [int(x.strip()) for x in ids.split(',') if x.strip()]
    
    # Get assets and generate ZPL
    db = get_db()
    assets = []
    
    if asset_ids:
        placeholders = ','.join('?' * len(asset_ids))
        assets = db.execute(f"""
            SELECT a.*, l.name as location_name, t.name as tag_name
            FROM assets a 
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN asset_tags at ON a.id = at.asset_id
            LEFT JOIN tags t ON at.tag_id = t.id
            WHERE a.id IN ({placeholders})
            ORDER BY a.asset_tag
        """, asset_ids).fetchall()
    
    # Generate ZPL content (simplified)
    zpl_content = ""
    for asset in assets:
        # This is a simplified ZPL generation - in real app would use proper template
        zpl_content += f"""^XA
^FO50,50^BQN,2,10,M,0^FDLA,{asset['asset_tag']}^FS
^FO50,150^A0N,30,30^FD{asset['asset_tag']}^FS
^XZ
"""
    
    return zpl_content, 200, {'Content-Type': 'text/plain'}

@bp.route('/admin/labels/print', methods=['POST'])
@admin_required
def print_labels():
    ids = request.form.get('ids', '')
    
    if not ids:
        flash('Nebyly vybrány žádné majetky', 'error')
        return redirect(url_for('catalog.labels'))
    
    # Parse IDs
    asset_ids = [int(x.strip()) for x in ids.split(',') if x.strip()]
    
    # Check if label printer is configured
    label_printer_host = current_app.config.get('LABEL_PRINTER_HOST', '')
    
    if not label_printer_host:
        flash('Není nastavena tiskárna (LABEL_PRINTER_HOST v Nastavení).', 'error')
        return redirect(url_for('catalog.labels'))
    
    try:
        # In a real implementation, this would send ZPL to the printer
        # For now, we'll just simulate it
        flash(f'Tisknout {len(asset_ids)} štítků na tiskárně', 'success')
        
        # Return to labels page with the same IDs
        return redirect(url_for('catalog.labels', ids=ids))
        
    except Exception as e:
        logger.exception("Error printing labels")
        flash(f'Chyba při tisku štítků: {str(e)}', 'error')
        return redirect(url_for('catalog.labels'))

# Intake
@bp.route('/admin/intake', methods=['GET'])
@admin_required
def intake():
    db = get_db()
    
    # Get all types, conditions, locations, tags for the form
    types = ASSET_TYPES
    conditions = ASSET_CONDITIONS
    locations = db.execute("SELECT * FROM locations ORDER BY name").fetchall()
    tags = db.execute("SELECT * FROM tags ORDER BY name").fetchall()
    invoices = db.execute("SELECT * FROM invoices ORDER BY issued_at DESC").fetchall()
    
    # Get next tag for each type (simplified)
    next_tags = {}
    for asset_type in types:
        # This is a simplified approach - in real app would use proper tag generation logic
        next_tags[asset_type] = f"{asset_type.upper()}-0001"
    
    return render_template('admin/intake.html', 
                         types=types, 
                         conditions=conditions,
                         locations=locations,
                         tags=tags,
                         invoices=invoices,
                         next_tags=next_tags)

@bp.route('/admin/intake', methods=['POST'])
@admin_required
def intake_submit():
    db = get_db()
    
    try:
        # Build the intake service
        intake_service = build_intake_service(db)
        
        # Get form data
        asset_type = request.form.get('type')
        brand = request.form.get('brand', '')
        model = request.form.get('model', '')
        quantity = int(request.form.get('quantity', 1))
        invoice_number = request.form.get('invoice_number')
        supplier = request.form.get('supplier', '')
        unit_price = float(request.form.get('unit_price', 0))
        location_id = request.form.get('location_id')
        tags_str = request.form.get('tags', '')
        warranty_until = request.form.get('warranty_until', '')
        condition = request.form.get('condition', 'good')
        
        # Process tags
        tag_ids = []
        if tags_str:
            tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]
            # Get or create tags
            for tag_name in tag_names:
                tag = db.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
                if not tag:
                    db.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    db.commit()
                    tag = db.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
                tag_ids.append(tag['id'])
        
        # Create batch of assets
        batch = intake_service.create_batch(
            asset_type=asset_type,
            brand=brand,
            model=model,
            quantity=quantity,
            invoice_number=invoice_number,
            supplier=supplier,
            unit_price=unit_price,
            location_id=location_id,
            tag_ids=tag_ids,
            warranty_until=warranty_until,
            condition=condition
        )
        
        # Redirect to the intake batch page
        return redirect(url_for('catalog.intake_batch', ids=','.join(str(id) for id in batch)))
        
    except Exception as e:
        logger.exception("Error creating intake batch")
        flash(f'Chyba při vytváření majetku: {str(e)}', 'error')
        return redirect(url_for('catalog.intake'))

@bp.route('/admin/intake/<ids>', methods=['GET'])
@admin_required
def intake_batch(ids):
    db = get_db()
    
    # Parse IDs
    asset_ids = [int(x.strip()) for x in ids.split(',') if x.strip()]
    
    # Get assets
    placeholders = ','.join('?' * len(asset_ids))
    assets = db.execute(f"""
        SELECT a.*, l.name as location_name
        FROM assets a 
        LEFT JOIN locations l ON a.location_id = l.id
        WHERE a.id IN ({placeholders})
        ORDER BY a.asset_tag
    """, asset_ids).fetchall()
    
    return render_template('admin/intake_serials.html', assets=assets)

@bp.route('/admin/intake/<ids>/serials', methods=['POST'])
@admin_required
def intake_batch_serials(ids):
    db = get_db()
    
    # Parse IDs
    asset_ids = [int(x.strip()) for x in ids.split(',') if x.strip()]
    
    # Get serial numbers from form
    serials = {}
    for asset_id in asset_ids:
        key = f'serial_{asset_id}'
        serials[asset_id] = request.form.get(key, '')
    
    # Update assets with serial numbers
    for asset_id, serial in serials.items():
        db.execute("UPDATE assets SET serial_number = ? WHERE id = ?", (serial, asset_id))
    
    db.commit()
    
    # Redirect to labels page with the new assets
    return redirect(url_for('catalog.labels', ids=ids))

# Short link
@bp.route('/a/<tag>', methods=['GET'])
@login_required
def short_link(tag):
    db = get_db()
    
    # Find asset by tag
    asset = db.execute("SELECT * FROM assets WHERE asset_tag = ?", (tag,)).fetchone()
    
    if not asset:
        return "Asset not found", 404
    
    # Get current user
    user = current_user()
    
    if not user:
        return "Unauthorized", 401
    
    # Check if user is admin
    if user['is_admin']:
        return redirect(url_for('catalog.asset_detail', id=asset['id']))
    
    # Check if user holds this asset (is assigned)
    from src.repositories.assignments import AssignmentRepository
    assignment_repo = AssignmentRepository(db)
    
    # Check if the user is assigned to this asset
    assignment = db.execute("""
        SELECT * FROM assignments 
        WHERE asset_id = ? AND ended_at IS NULL
    """, (asset['id'],)).fetchone()
    
    if assignment:
        # Check if the current user is the assignee
        from src.repositories.employees import EmployeeRepository
        employee_repo = EmployeeRepository(db)
        employee = employee_repo.get_by_email(user['email'])
        
        if employee and assignment['employee_id'] == employee['id']:
            return redirect(url_for('employee.home'))
    
    # User doesn't have access to this asset
    return "Forbidden", 403

# Asset detail (for completeness)
@bp.route('/admin/assets/<int:id>', methods=['GET'])
@admin_required
def asset_detail(id):
    db = get_db()
    
    # Get the asset
    asset = db.execute("SELECT * FROM assets WHERE id = ?", (id,)).fetchone()
    if not asset:
        return "Majetek nenalezen", 404
    
    # Get tags for this asset
    tags = db.execute("""
        SELECT t.* FROM tags t 
        JOIN asset_tags at ON t.id = at.tag_id 
        WHERE at.asset_id = ?
    """, (id,)).fetchall()
    
    # Get attachments for this asset
    attachments = db.execute("""
        SELECT * FROM attachments 
        WHERE owner_type = 'asset' AND owner_id = ?
        ORDER BY uploaded_at DESC
    """, (id,)).fetchall()
    
    # Get assignments for this asset
    assignments = db.execute("""
        SELECT a.*, e.display_name as employee_name 
        FROM assignments a 
        JOIN employees e ON a.employee_id = e.id
        WHERE a.asset_id = ? 
        ORDER BY a.started_at DESC
    """, (id,)).fetchall()
    
    return render_template('admin/asset_detail.html', 
                         asset=asset, 
                         tags=tags,
                         attachments=attachments,
                         assignments=assignments)