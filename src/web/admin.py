from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
import logging
from src.auth.guards import admin_required, actor
from src.services.factory import build_handover_service, build_asset_service
from src.db import get_db
from src.config import ASSET_TYPES, ASSET_STATUSES, HANDOVER_KINDS, HANDOVER_STATUSES
from src.services.handover_service import HandoverError
from src.services.asset_service import AssetValidationError, DuplicateAssetTag

# Set up logging
logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/assets')
@admin_required
def assets_list():
    q = request.args.get('q', '')
    status = request.args.get('status', '')
    type_filter = request.args.get('type', '')
    
    db = get_db()
    asset_service = build_asset_service(db)
    
    assets = asset_service.list(status=status or None, type=type_filter or None, q=q)
    
    return render_template('admin/assets.html', assets=assets, q=q, status=status, type=type_filter,
                           asset_types=ASSET_TYPES, asset_statuses=ASSET_STATUSES)

@bp.route('/assets/new', methods=['GET', 'POST'])
@admin_required
def assets_new():
    db = get_db()
    
    if request.method == 'POST':
        asset_service = build_asset_service(db)
        current_actor = actor()
        
        asset_tag = request.form.get('asset_tag', '').strip().upper()
        type = request.form.get('type', '')
        brand = request.form.get('brand', '')
        model = request.form.get('model', '')
        serial_number = request.form.get('serial_number', '')
        purchase_date = request.form.get('purchase_date', '')
        price = request.form.get('price', '0')
        notes = request.form.get('notes', '')
        
        try:
            asset = asset_service.create(
                actor=current_actor,
                asset_tag=asset_tag,
                type=type,
                brand=brand,
                model=model,
                serial_number=serial_number,
                purchase_date=purchase_date,
                price=float(price) if price else 0.0,
                notes=notes
            )
        except (AssetValidationError, DuplicateAssetTag) as e:
            return render_template('admin/asset_form.html', asset=request.form, types=ASSET_TYPES, error=str(e))
        
        flash('Zařízení bylo vytvořeno.', 'success')
        return redirect(url_for('admin.assets_detail', id=asset['id']))
            
    
    return render_template('admin/asset_form.html', 
                           asset=None, 
                           errors=[],
                           asset_types=ASSET_TYPES,
                           asset_statuses=ASSET_STATUSES)

@bp.route('/assets/<int:id>')
@admin_required
def assets_detail(id):
    db = get_db()
    
    asset_service = build_asset_service(db)
    handover_service = build_handover_service(db)
    
    asset = asset_service.get(id)
    if not asset:
        abort(404)
    
    # Get handovers for this asset with details
    handovers = handover_service.handovers.list_for_asset(id)
    handovers_with_details = [handover_service.with_details(h) for h in handovers]
    
    # Get assignment history, each with its employee
    assignments = [
        {**a, 'employee': handover_service.employees.get(a['employee_id'])}
        for a in handover_service.assignments.history_for_asset(id)
    ]
    
    # Get the open assignment if exists
    open_assignment = None
    for assignment in assignments:
        if assignment['ended_at'] is None:
            open_assignment = assignment
            break
    
    # Get active employees for handover picker
    employees = handover_service.employees.list_all(active_only=True)
    
    return render_template('admin/asset_detail.html', 
                           asset=asset,
                           handovers=handovers_with_details,
                           assignments=assignments,
                           open_assignment=open_assignment,
                           employees=employees)

@bp.route('/assets/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def assets_edit(id):
    db = get_db()
    
    asset_service = build_asset_service(db)
    handover_service = build_handover_service(db)
    
    asset = asset_service.get(id)
    if not asset:
        abort(404)
    
    if request.method == 'POST':
        current_actor = actor()
        
        # Get form data
        type = request.form.get('type', asset['type'])
        brand = request.form.get('brand', asset['brand'])
        model = request.form.get('model', asset['model'])
        serial_number = request.form.get('serial_number', asset['serial_number'])
        purchase_date = request.form.get('purchase_date', asset['purchase_date'])
        price = request.form.get('price', asset['price'])
        notes = request.form.get('notes', asset['notes'])
        
        try:
            updated_asset = asset_service.update(
                actor=current_actor,
                asset_id=id,
                type=type,
                brand=brand,
                model=model,
                serial_number=serial_number,
                purchase_date=purchase_date,
                price=float(price) if price else 0.0,
                notes=notes
            )
        except (AssetValidationError, DuplicateAssetTag) as e:
            return render_template('admin/asset_form.html', asset={**asset, **request.form}, types=ASSET_TYPES, error=str(e))
        
        flash('Zařízení bylo upraveno.', 'success')
        return redirect(url_for('admin.assets_detail', id=updated_asset['id']))
            
    
    return render_template('admin/asset_form.html', 
                           asset=asset, 
                           errors=[],
                           asset_types=ASSET_TYPES,
                           asset_statuses=ASSET_STATUSES)

@bp.route('/assets/<int:id>/handover', methods=['POST'])
@admin_required
def assets_handover(id):
    db = get_db()
    handover_service = build_handover_service(db)
    
    try:
        employee_email = request.form.get('employee_email')
        note = request.form.get('note', '')
        
        # Get employee by email
        employee = handover_service.employees.get_by_email(employee_email)
        if not employee:
            flash('Zaměstnanec nenalezen.', 'error')
            return redirect(url_for('admin.assets_detail', id=id))
        
        # Start handover
        handover = handover_service.start_handover(
            actor=actor(),
            asset_id=id,
            employee_id=employee['id'],
            note=note
        )
        
        flash('Žádost o potvrzení převzetí byla odeslána.', 'success')
        return redirect(url_for('admin.assets_detail', id=id))
        
    except HandoverError as e:
        flash(f'Handover error: {str(e)}', 'error')
        return redirect(url_for('admin.assets_detail', id=id))

@bp.route('/assets/<int:id>/return', methods=['POST'])
@admin_required
def assets_return(id):
    db = get_db()
    handover_service = build_handover_service(db)
    
    try:
        note = request.form.get('note', '')
        
        # Start return
        handover = handover_service.start_return(
            actor=actor(),
            asset_id=id,
            note=note
        )
        
        flash('Žádost o potvrzení vrácení byla odeslána.', 'success')
        return redirect(url_for('admin.assets_detail', id=id))
        
    except HandoverError as e:
        flash(f'Return error: {str(e)}', 'error')
        return redirect(url_for('admin.assets_detail', id=id))

@bp.route('/assets/<int:id>/retire', methods=['POST'])
@admin_required
def assets_retire(id):
    db = get_db()
    asset_service = build_asset_service(db)
    
    asset_service.retire(
        actor=actor(),
        asset_id=id
    )
    
    flash('Zařízení bylo vyřazeno.', 'success')
    return redirect(url_for('admin.assets_detail', id=id))
        

@bp.route('/assets/<int:id>/lost', methods=['POST'])
@admin_required
def assets_lost(id):
    db = get_db()
    asset_service = build_asset_service(db)
    
    asset_service.mark_lost(
        actor=actor(),
        asset_id=id
    )
    
    flash('Zařízení bylo označeno jako ztracené.', 'success')
    return redirect(url_for('admin.assets_detail', id=id))
        

@bp.route('/handovers')
@admin_required
def handovers_list():
    status = request.args.get('status', '')
    
    db = get_db()
    handover_service = build_handover_service(db)
    
    handovers = handover_service.handovers.list_all(status=status or None, kind=None)
    handovers_with_details = [handover_service.with_details(h) for h in handovers]
    
    return render_template('admin/handovers.html', 
                           handovers=handovers_with_details,
                           status=status,
                           handover_kinds=HANDOVER_KINDS,
                           handover_statuses=HANDOVER_STATUSES)

@bp.route('/handovers/<int:id>/cancel', methods=['POST'])
@admin_required
def handovers_cancel(id):
    db = get_db()
    handover_service = build_handover_service(db)
    
    try:
        handover_service.cancel(
            actor=actor(),
            handover_id=id
        )
        
        flash('Předání bylo zrušeno.', 'success')
        return redirect(url_for('admin.handovers_list'))
        
    except HandoverError as e:
        flash(f'Handover cancellation error: {str(e)}', 'error')
        return redirect(url_for('admin.handovers_list'))

@bp.route('/employees')
@admin_required
def employees_list():
    q = request.args.get('q', '')
    
    db = get_db()
    # Import the EmployeeRepository properly
    from src.repositories.employees import EmployeeRepository
    employees_repo = EmployeeRepository(db)
    
    if q:
        employees = employees_repo.search(q)
    else:
        employees = employees_repo.list_all()
    
    return render_template('admin/employees.html', employees=employees, q=q)

@bp.route('/employees/<path:email>')
@admin_required
def employees_detail(email):
    db = get_db()
    handover_service = build_handover_service(db)
    
    employee = handover_service.employees.get_by_email(email)
    if not employee:
        abort(404)
    
    overview = handover_service.overview_for_employee(employee['id'])
    
    return render_template('admin/employee_detail.html', 
                           employee=employee,
                           overview=overview)

@bp.route('/audit')
@admin_required
def audit():
    db = get_db()
    # Import the AuditRepository properly
    from src.repositories.audit import AuditRepository
    audit_repo = AuditRepository(db)
    
    audit_log = audit_repo.list_recent(200)
    
    return render_template('admin/audit.html', entries=audit_log)