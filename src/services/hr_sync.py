import csv
import io
from typing import List, Dict, Any
from src.repositories.employees import EmployeeRepository
from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.assignments import AssignmentRepository


class HrSyncService:
    def __init__(self, employees: EmployeeRepository, assets: AssetRepository, audit: AuditRepository, assignments: AssignmentRepository = None):
        self.employees = employees
        self.assets = assets
        self.audit = audit
        self.assignments = assignments

    def sync(self, actor: str, records: List[Dict[str, Any]]) -> Dict[str, int]:
        # Initialize counters
        created = 0
        updated = 0
        deactivated = 0
        offboarding = []
        
        # Process each record
        for record in records:
            # Validate email is present
            if 'email' not in record or not record['email']:
                raise ValueError("Email is required for all records")
            
            email = record['email'].lower()
            display_name = record.get('display_name', '')
            department = record.get('department', '')
            manager_email = record.get('manager_email', '')
            hr_id = record.get('hr_id', '')
            active = record.get('active', True)
            
            # Parse active field from string
            if isinstance(active, str):
                active = active.lower() in ('1', 'true', 'yes')
            
            # Check if employee exists
            existing_employee = self.employees.get_by_email(email)
            
            if not existing_employee:
                # New employee - create
                self.employees.upsert(email, display_name, department, manager_email, hr_id)
                created += 1
            else:
                # Existing employee - check if they're being deactivated
                current_active = existing_employee.get('active', True)
                
                # If the employee is currently active but being deactivated in this sync
                if current_active and not active:
                    # Deactivate the employee
                    employee_id = existing_employee['id']
                    self.employees.set_active(employee_id, False)
                    deactivated += 1
                    
                    # Check for open assignments if assignments repository is provided
                    asset_tags = []
                    if self.assignments:
                        # Use the AssignmentRepository to get open assignments
                        open_assignments = self.assignments.list_open_for_employee(employee_id)
                    else:
                        # Fallback to raw SQL query
                        cursor = self.assets.conn.execute(
                            "SELECT asset_id FROM assignments WHERE employee_id=? AND ended_at IS NULL",
                            (employee_id,)
                        )
                        open_assignments = [{'asset_id': row[0]} for row in cursor.fetchall()]
                    
                    # Get asset tags for the assets
                    for assignment in open_assignments:
                        asset_id = assignment['asset_id']
                        asset = self.assets.get(asset_id)
                        if asset:
                            asset_tags.append(asset['asset_tag'])
                    
                    # Add to offboarding list if they have assets
                    if asset_tags:
                        offboarding.append({
                            'email': email,
                            'asset_tags': asset_tags
                        })
                else:
                    # Update existing employee
                    self.employees.upsert(email, display_name, department, manager_email, hr_id)
                    updated += 1
        
        # Record audit log
        audit_details = {
            'created': created,
            'updated': updated,
            'deactivated': deactivated
        }
        self.audit.record(actor, 'employee.synced', 'employee', 0, audit_details)
        
        return {
            'created': created,
            'updated': updated,
            'deactivated': deactivated,
            'offboarding': offboarding
        }

    def parse_csv(self, text: str) -> List[Dict[str, str]]:
        # Determine delimiter
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(text[:1024], delimiters=";,").delimiter
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        
        records = []
        for row in reader:
            # Normalize fields
            record = {
                'email': row.get('email', '').strip(),
                'display_name': row.get('display_name', '').strip(),
                'department': row.get('department', '').strip(),
                'manager_email': row.get('manager_email', '').strip(),
                'hr_id': row.get('hr_id', '').strip(),
                'active': row.get('active', '').strip()
            }
            
            # Parse active field
            if record['active'] == '':
                record['active'] = True
            else:
                active_str = record['active'].lower()
                record['active'] = active_str in ('1', 'true', 'yes')
            
            records.append(record)
        
        return records