import sqlite3
from typing import Dict, List
from src.services.asset_service import AssetService
from src.repositories.invoices import InvoiceRepository
from src.repositories.audit import AuditRepository


class IntakeService:
    def __init__(
        self,
        assets: AssetService,
        invoices: InvoiceRepository,
        audit: AuditRepository
    ):
        self.assets = assets
        self.invoices = invoices
        self.audit = audit

    def create_batch(
        self,
        actor: str,
        type: str,
        brand: str,
        model: str,
        quantity: int,
        invoice_number: str,
        supplier: str,
        unit_price: float,
        location_id: int | None,
        tag_names: List[str],
        warranty_until: str,
        condition: str = 'new'
    ) -> Dict:
        """Create a batch of assets on one invoice."""
        # Validate quantity
        if not (1 <= quantity <= 500):
            raise ValueError("Quantity must be between 1 and 500")
        
        # Handle invoice creation or retrieval
        invoice = None
        if invoice_number:
            invoice = self.invoices.get_by_number(invoice_number)
            if not invoice:
                # Create new invoice
                invoice = self.invoices.create(
                    number=invoice_number,
                    supplier=supplier,
                    issued_at='',
                    total=quantity * unit_price,
                    currency='CZK',
                    notes='',
                    created_by=actor
                )
        
        # Create assets one by one
        asset_dicts = []
        asset_ids = []
        
        for i in range(quantity):
            # Create each asset with the same properties but different tags
            asset = self.assets.create(
                actor=actor,
                asset_tag='',
                type=type,
                brand=brand,
                model=model,
                serial_number='',
                purchase_date='',
                price=unit_price,
                notes='',
                location_id=location_id,
                condition=condition,
                supplier=supplier,
                warranty_until=warranty_until,
                cost_center='',
                invoice_id=invoice['id'] if invoice else None,
                tag_names=tag_names
            )
            
            asset_dicts.append(asset)
            asset_ids.append(asset['id'])
        
        # Record audit log
        self.audit.record(
            actor=actor,
            action='intake.batch',
            entity='asset',
            entity_id=0,  # Not applicable for batch operations
            details={
                'quantity': quantity,
                'asset_ids': asset_ids
            }
        )
        
        return {
            'invoice': invoice,
            'assets': asset_dicts
        }

    def set_serials(self, actor: str, serials: Dict[int, str]) -> int:
        """Set serial numbers for assets."""
        count = 0
        
        # Update each asset with its serial number
        for asset_id, serial_number in serials.items():
            if serial_number:  # Only update if serial number is provided
                self.assets.update(
                    actor=actor,
                    asset_id=asset_id,
                    serial_number=serial_number
                )
                count += 1
        
        return count