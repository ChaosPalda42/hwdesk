import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List

from src.repositories.assets import AssetRepository
from src.repositories.handovers import HandoverRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository


class DashboardService:
    def __init__(
        self,
        assets: AssetRepository,
        handovers: HandoverRepository,
        audit: AuditRepository,
        employees: EmployeeRepository,
    ):
        self.assets = assets
        self.handovers = handovers
        self.audit = audit
        self.employees = employees

    def stats(self, today: str, warranty_days: int = 90) -> dict:
        # Parse the input date string to a datetime object
        today_date = datetime.fromisoformat(today)
        
        # Calculate the warranty expiration date
        warranty_date = today_date + timedelta(days=warranty_days)
        
        # Get totals
        all_assets = self.assets.list_all()
        total_assets = len(all_assets)
        total_value = sum(asset.get('price', 0) for asset in all_assets if asset.get('price') is not None)
        
        # Get active employees count
        active_employees = self.employees.list_all(active_only=True)
        total_employees = len(active_employees)
        
        # Get counts by status, type, and condition
        by_status = self.assets.count_by('status')
        by_type = self.assets.count_by('type')
        by_condition = self.assets.count_by('condition')
        
        # Get pending handovers with asset and employee details
        pending_handovers_list = self.handovers.list_all(status='pending')
        pending_handovers = []
        for handover in pending_handovers_list:
            asset = self.assets.get(handover['asset_id'])
            employee = self.employees.get(handover['employee_id'])
            if asset and employee:
                # Extract protocol_number from the handover record itself
                pending_handovers.append({
                    'asset': asset,
                    'employee': employee,
                    'protocol_number': handover.get('protocol_number', '')
                })
        
        # Get warranty expiring assets (excluding retired/lost)
        warranty_expiring = self.assets.search_assets(
            warranty_before=warranty_date.isoformat()
        )
        # Filter out retired and lost assets
        warranty_expiring = [
            asset for asset in warranty_expiring 
            if asset.get('status') not in ('retired', 'lost')
        ]
        # Sort by warranty_until
        warranty_expiring.sort(key=lambda x: x.get('warranty_until', ''))
        
        # Get recent activity (last 20 audit entries)
        recent_activity = self.audit.list_recent(20)
        
        return {
            'totals': {
                'assets': total_assets,
                'value': float(total_value),
                'employees': total_employees
            },
            'by_status': by_status,
            'by_type': by_type,
            'by_condition': by_condition,
            'pending_handovers': pending_handovers,
            'warranty_expiring': warranty_expiring,
            'recent_activity': recent_activity
        }