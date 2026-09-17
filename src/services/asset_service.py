import sqlite3
from typing import Dict, List, Optional
from src.config import ASSET_TYPES, ASSET_CONDITIONS, ASSET_STATUSES
from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.tags import TagRepository
from src.repositories.locations import LocationRepository
from src.repositories.invoices import InvoiceRepository


class AssetValidationError(ValueError):
    """Raised when asset data validation fails."""
    pass


class DuplicateAssetTag(ValueError):
    """Raised when an asset tag already exists."""
    pass


class AssetService:
    def __init__(
        self,
        assets: AssetRepository,
        audit: AuditRepository,
        tags: TagRepository | None = None,
        locations: LocationRepository | None = None,
        invoices: InvoiceRepository | None = None,
        tag_prefixes: dict | None = None,
        tag_pad: int = 4
    ):
        self.assets = assets
        self.audit = audit
        self.tags = tags
        self.locations = locations
        self.invoices = invoices
        self.tag_prefixes = tag_prefixes or {}
        self.tag_pad = tag_pad

    def next_asset_tag(self, type: str) -> str:
        """Generate the next asset tag for a given type."""
        prefix = self.tag_prefixes.get(type) or self.tag_prefixes.get('other') or 'AS'
        
        # Find all existing asset tags with this prefix
        cursor = self.assets.conn.execute(
            "SELECT asset_tag FROM assets WHERE asset_tag LIKE ?",
            (f"{prefix}-%",)
        )
        
        # Extract numeric suffixes and find the maximum
        max_number = 0
        for row in cursor.fetchall():
            asset_tag = row['asset_tag']
            # Split by dash and get the part after the first dash
            parts = asset_tag.split('-', 1)
            if len(parts) > 1:
                suffix_part = parts[1]
                # Check if the suffix part is numeric
                if suffix_part.isdigit():
                    number = int(suffix_part)
                    max_number = max(max_number, number)
        
        # Generate the next tag with zero padding
        next_number = max_number + 1
        return f"{prefix}-{next_number:0{self.tag_pad}d}"

    def create(
        self,
        actor: str,
        asset_tag: str,
        type: str,
        brand: str,
        model: str,
        serial_number: str,
        purchase_date: str,
        price: float,
        notes: str,
        location_id: int | None = None,
        condition: str = 'good',
        supplier: str = '',
        warranty_until: str = '',
        cost_center: str = '',
        invoice_id: int | None = None,
        invoice_number: str = '',
        tag_names: List[str] | None = None
    ) -> Dict:
        """Create a new asset."""
        # Validate required fields
        if not type or type.strip() == "":
            raise AssetValidationError("Asset type cannot be empty")
        if type not in ASSET_TYPES:
            raise AssetValidationError(f"Invalid asset type: {type}")
        
        if condition not in ASSET_CONDITIONS:
            raise AssetValidationError(f"Invalid asset condition: {condition}")
        
        # Validate date formats (empty or ISO format)
        if purchase_date and not self._is_valid_iso_date(purchase_date):
            raise AssetValidationError("Invalid purchase date format")
        
        if warranty_until and not self._is_valid_iso_date(warranty_until):
            raise AssetValidationError("Invalid warranty until date format")
        
        # Process asset tag
        if not asset_tag:
            asset_tag = self.next_asset_tag(type)
        else:
            asset_tag = asset_tag.strip().upper()
        
        # Validate location_id if provided
        if location_id is not None:
            if self.locations is None:
                raise AssetValidationError("Locations repository not provided")
            location = self.locations.get(location_id)
            if not location:
                raise AssetValidationError(f"Location with ID {location_id} does not exist")
        
        # Process invoice_id if provided
        if invoice_id is not None:
            if self.invoices is None:
                raise AssetValidationError("Invoices repository not provided")
            invoice = self.invoices.get(invoice_id)
            if not invoice:
                raise AssetValidationError(f"Invoice with ID {invoice_id} does not exist")
        
        # Process invoice_number if provided
        if invoice_number:
            if self.invoices is None:
                raise AssetValidationError("Invoices repository not provided")
            
            # Try to find existing invoice by number
            invoice = self.invoices.get_by_number(invoice_number)
            if not invoice:
                # Create new invoice if it doesn't exist
                invoice = self.invoices.create(
                    number=invoice_number,
                    supplier=supplier,
                    issued_at='',
                    total=0,
                    currency='CZK',
                    notes='',
                    created_by=actor
                )
            invoice_id = invoice['id']
        
        # Create the asset
        try:
            asset = self.assets.create(
                asset_tag=asset_tag,
                type=type,
                brand=brand,
                model=model,
                serial_number=serial_number,
                purchase_date=purchase_date,
                price=price,
                notes=notes,
                location_id=location_id,
                condition=condition,
                supplier=supplier,
                warranty_until=warranty_until,
                cost_center=cost_center,
                invoice_id=invoice_id
            )
        except sqlite3.IntegrityError as e:
            if "Asset tag already exists" in str(e):
                raise DuplicateAssetTag("Asset tag already exists")
            raise
        
        # Set tags if provided
        if tag_names:
            if self.tags is None:
                raise AssetValidationError("Tags repository not provided")
            
            tag_ids = []
            for tag_name in tag_names:
                # Get or create the tag
                tag = self.tags.get_by_name(tag_name)
                if not tag:
                    tag = self.tags.create(name=tag_name, color='gray')
                
                tag_ids.append(tag['id'])
            
            # Set tags for the asset
            self.tags.set_for_asset(asset['id'], tag_ids)
        
        # Record audit log
        self.audit.record(
            actor=actor,
            action='asset.created',
            entity='asset',
            entity_id=asset['id'],
            details={
                'asset_tag': asset_tag,
                'type': type,
                'brand': brand,
                'model': model,
                'serial_number': serial_number,
                'purchase_date': purchase_date,
                'price': price,
                'notes': notes,
                'location_id': location_id,
                'condition': condition,
                'supplier': supplier,
                'warranty_until': warranty_until,
                'cost_center': cost_center,
                'invoice_id': invoice_id,
                'tag_names': tag_names or []
            }
        )
        
        # Return the created asset with enriched data
        return self.get(asset['id'])

    def get(self, id: int) -> Dict | None:
        """Get an asset by ID."""
        asset = self.assets.get(id)
        if not asset:
            return None
        
        # Enrich with tags
        if self.tags is not None:
            asset['tags'] = self.tags.for_asset(id)
        else:
            asset['tags'] = []
        
        # Enrich with invoice info
        if self.invoices is not None and asset.get('invoice_id'):
            asset['invoice'] = self.invoices.get(asset['invoice_id'])
        else:
            asset['invoice'] = None
        
        return asset

    def update(
        self,
        actor: str,
        asset_id: int,
        **fields
    ) -> Dict:
        """Update an existing asset."""
        # Get the current asset to validate existence
        existing_asset = self.assets.get(asset_id)
        if not existing_asset:
            raise AssetValidationError(f"Asset with ID {asset_id} does not exist")
        
        # Validate fields that are being updated
        if 'type' in fields and fields['type'] not in ASSET_TYPES:
            raise AssetValidationError(f"Invalid asset type: {fields['type']}")
        
        if 'condition' in fields and fields['condition'] not in ASSET_CONDITIONS:
            raise AssetValidationError(f"Invalid asset condition: {fields['condition']}")
        
        # Validate date formats (empty or ISO format)
        if 'purchase_date' in fields and fields['purchase_date'] and not self._is_valid_iso_date(fields['purchase_date']):
            raise AssetValidationError("Invalid purchase date format")
        
        if 'warranty_until' in fields and fields['warranty_until'] and not self._is_valid_iso_date(fields['warranty_until']):
            raise AssetValidationError("Invalid warranty until date format")
        
        # Validate location_id if provided
        if 'location_id' in fields and fields['location_id'] is not None:
            if self.locations is None:
                raise AssetValidationError("Locations repository not provided")
            location = self.locations.get(fields['location_id'])
            if not location:
                raise AssetValidationError(f"Location with ID {fields['location_id']} does not exist")
        
        # Process invoice_number if provided
        if 'invoice_number' in fields and fields['invoice_number']:
            if self.invoices is None:
                raise AssetValidationError("Invoices repository not provided")
            
            # Try to find existing invoice by number
            invoice = self.invoices.get_by_number(fields['invoice_number'])
            if not invoice:
                # Create new invoice if it doesn't exist
                invoice = self.invoices.create(
                    number=fields['invoice_number'],
                    supplier=fields.get('supplier', ''),
                    issued_at='',
                    total=0,
                    currency='CZK',
                    notes='',
                    created_by=actor
                )
            fields['invoice_id'] = invoice['id']
        
        # Handle tag_names update
        if 'tag_names' in fields:
            if self.tags is None:
                raise AssetValidationError("Tags repository not provided")
            
            tag_ids = []
            for tag_name in fields['tag_names']:
                # Get or create the tag
                tag = self.tags.get_by_name(tag_name)
                if not tag:
                    tag = self.tags.create(name=tag_name, color='gray')
                
                tag_ids.append(tag['id'])
            
            # Replace the existing tags with new ones
            self.tags.set_for_asset(asset_id, tag_ids)
            
            # Remove tag_names from fields to avoid passing it to the repository
            fields.pop('tag_names')
        
        # Update the asset
        updated_asset = self.assets.update(asset_id, **fields)
        
        if not updated_asset:
            raise AssetValidationError(f"Failed to update asset with ID {asset_id}")
        
        # Record audit log
        changed_fields = list(fields.keys())
        self.audit.record(
            actor=actor,
            action='asset.updated',
            entity='asset',
            entity_id=asset_id,
            details={
                'changed_fields': changed_fields,
                'before': existing_asset,
                'after': updated_asset
            }
        )
        
        # Return the updated asset with enriched data
        return self.get(asset_id)

    def retire(self, actor: str, asset_id: int) -> Dict:
        """Retire an asset."""
        asset = self.assets.get(asset_id)
        if not asset:
            raise AssetValidationError(f"Asset with ID {asset_id} does not exist")
        
        # Check if asset is assigned or pending
        if asset.get('status') in ('assigned', 'pending_handover', 'pending_return'):
            raise AssetValidationError("Cannot retire assigned or pending asset")
        
        # Set status to retired
        self.assets.set_status(asset_id, 'retired')
        
        # Record audit log
        self.audit.record(
            actor=actor,
            action='asset.retired',
            entity='asset',
            entity_id=asset_id,
            details={'status': 'retired'}
        )
        
        # Return the updated asset with enriched data
        return self.get(asset_id)

    def mark_lost(self, actor: str, asset_id: int) -> Dict:
        """Mark an asset as lost."""
        asset = self.assets.get(asset_id)
        if not asset:
            raise AssetValidationError(f"Asset with ID {asset_id} does not exist")
        
        # Check if asset is assigned or pending
        if asset.get('status') in ('assigned', 'pending_handover', 'pending_return'):
            raise AssetValidationError("Cannot mark assigned or pending asset as lost")
        
        # Set status to lost
        self.assets.set_status(asset_id, 'lost')
        
        # Record audit log - FIXED: Use correct action name
        self.audit.record(
            actor=actor,
            action='asset.lost',  # Changed from 'asset.marked_lost' to 'asset.lost'
            entity='asset',
            entity_id=asset_id,
            details={'status': 'lost'}
        )
        
        # Return the updated asset with enriched data
        return self.get(asset_id)

    def list(
        self,
        status: str | None = None,
        type: str | None = None,
        q: str = ''
    ) -> List[Dict]:
        """List assets with optional filtering."""
        if q:
            # Search by query
            assets = self.assets.search(q)
        else:
            # List all with filters
            assets = self.assets.list_all(status, type)
        
        # Enrich each asset with tags and invoice info
        enriched_assets = []
        for asset in assets:
            # Enrich with tags
            if self.tags is not None:
                asset['tags'] = self.tags.for_asset(asset['id'])
            else:
                asset['tags'] = []
            
            # Enrich with invoice info
            if self.invoices is not None and asset.get('invoice_id'):
                asset['invoice'] = self.invoices.get(asset['invoice_id'])
            else:
                asset['invoice'] = None
            
            enriched_assets.append(asset)
        
        return enriched_assets

    def bulk_tag(
        self,
        actor: str,
        asset_ids: List[int],
        tag_name: str,
        remove: bool = False
    ) -> int:
        """Apply or remove a tag from multiple assets."""
        if self.tags is None:
            raise AssetValidationError("Tags repository not provided")
        
        # Get or create the tag
        tag = self.tags.get_by_name(tag_name)
        if not tag:
            tag = self.tags.create(name=tag_name, color='gray')
        
        # Apply or remove the tag to all assets
        count = 0
        for asset_id in asset_ids:
            asset = self.assets.get(asset_id)
            if not asset:
                continue  # Skip non-existent assets
            
            if remove:
                # Remove the tag
                self.tags.unassign(asset_id, tag['id'])
            else:
                # Apply the tag
                self.tags.assign(asset_id, tag['id'])
            
            count += 1
        
        # Record audit log once for the bulk operation
        self.audit.record(
            actor=actor,
            action='asset.bulk_tag',
            entity='asset',
            entity_id=0,  # Not applicable for bulk operations
            details={
                'asset_ids': asset_ids,
                'tag_name': tag_name,
                'remove': remove,
                'count': count
            }
        )
        
        return count

    def attach_invoice(
        self,
        actor: str,
        asset_ids: List[int],
        invoice_id: int
    ) -> int:
        """Attach an invoice to multiple assets."""
        if self.invoices is None:
            raise AssetValidationError("Invoices repository not provided")
        
        # Validate that the invoice exists
        invoice = self.invoices.get(invoice_id)
        if not invoice:
            raise AssetValidationError(f"Invoice with ID {invoice_id} does not exist")
        
        # Attach the invoice to all assets
        count = 0
        for asset_id in asset_ids:
            asset = self.assets.get(asset_id)
            if not asset:
                continue  # Skip non-existent assets
            
            # Update the asset with the invoice_id
            self.assets.update(asset_id, invoice_id=invoice_id)
            count += 1
        
        # Record audit log once for the bulk operation
        self.audit.record(
            actor=actor,
            action='asset.bulk_attach_invoice',
            entity='asset',
            entity_id=0,  # Not applicable for bulk operations
            details={
                'asset_ids': asset_ids,
                'invoice_id': invoice_id,
                'count': count
            }
        )
        
        return count

    def _is_valid_iso_date(self, date_str: str) -> bool:
        """Check if a string is a valid ISO date format."""
        import re
        # Basic pattern for ISO date (YYYY-MM-DD)
        iso_pattern = r'^\d{4}-\d{2}-\d{2}$'
        return bool(re.match(iso_pattern, date_str))