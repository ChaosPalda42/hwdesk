from flask import Blueprint, request, jsonify
from src.auth.guards import api_auth_required, actor
from src.db import get_db
from src.services.hr_sync import HrSyncService
from src.repositories.employees import EmployeeRepository
from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.audit import AuditRepository

bp = Blueprint('api_employees', __name__)

def get_hr_sync_service():
    """Create an HrSyncService instance with repositories for the current request."""
    db = get_db()
    return HrSyncService(
        EmployeeRepository(db),
        AssetRepository(db),
        AuditRepository(db),
        AssignmentRepository(db)
    )

@bp.route('/employees', methods=['GET'])
@api_auth_required
def get_employees():
    """Get list of employees with optional search and active filter."""
    q = request.args.get('q', '')
    active = request.args.get('active', type=str)
    
    db = get_db()
    employee_repo = EmployeeRepository(db)
    
    if q:
        employees = employee_repo.search(q)
    else:
        active_only = active is not None and active.lower() in ('1', 'true', 'yes')
        employees = employee_repo.list_all(active_only)
    
    return jsonify(employees)

@bp.route('/employees/<path:email>', methods=['GET'])
@api_auth_required
def get_employee(email):
    """Get a specific employee by email."""
    db = get_db()
    employee_repo = EmployeeRepository(db)
    
    employee = employee_repo.get_by_email(email)
    if not employee:
        return jsonify({'error': 'not found'}), 404
    
    return jsonify(employee)

@bp.route('/hr/employees', methods=['POST'])
@api_auth_required
def hr_sync_employees():
    """Sync employees from HR system."""
    data = request.get_json()
    if not data or 'employees' not in data:
        return jsonify({'error': 'missing employees list'}), 400
    
    records = data['employees']
    if not isinstance(records, list):
        return jsonify({'error': 'employees must be a list'}), 400
    
    try:
        service = get_hr_sync_service()
        result = service.sync(actor(), records)
        
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/hr/employees/csv', methods=['POST'])
@api_auth_required
def hr_sync_employees_csv():
    """Sync employees from CSV data."""
    csv_text = request.get_data(as_text=True)
    if not csv_text:
        return jsonify({'error': 'empty CSV data'}), 400
    
    try:
        service = get_hr_sync_service()
        records = service.parse_csv(csv_text)
        
        result = service.sync(actor(), records)
        
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/audit', methods=['GET'])
@api_auth_required
def get_audit():
    """Get audit log entries."""
    limit = request.args.get('limit', 50, type=int)
    
    db = get_db()
    audit_repo = AuditRepository(db)
    
    entries = audit_repo.list_recent(limit)
    return jsonify(entries)