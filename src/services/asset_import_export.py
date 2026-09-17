import csv
import io
from typing import Dict, List
import logging

from src.services.asset_service import AssetService, AssetValidationError, DuplicateAssetTag
from src.repositories.assets import AssetRepository
from src.repositories.tags import TagRepository
from src.repositories.locations import LocationRepository

logger = logging.getLogger(__name__)


def export_assets_csv(assets: AssetRepository, tags: TagRepository) -> str:
    """Export assets to CSV format with specified header and data."""
    
    # Get all assets with their details
    asset_rows = assets.search_assets()
    
    # Prepare CSV content
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # Write header
    header = [
        'asset_tag', 'type', 'brand', 'model', 'serial_number',
        'status', 'condition', 'location', 'tags', 'holder_email',
        'warranty_until', 'supplier', 'cost_center', 'invoice', 
        'purchase_date', 'price', 'notes'
    ]
    writer.writerow(header)
    
    # Process each asset row
    for asset in asset_rows:
        # Get tags for this asset
        asset_tags = tags.for_asset(asset['id']) if tags else []
        tag_names = [tag['name'] for tag in asset_tags]
        
        # Get invoice number if available
        invoice_number = ''
        if asset.get('invoice_id') and assets.conn:
            cursor = assets.conn.execute(
                "SELECT number FROM invoices WHERE id=?", 
                (asset['invoice_id'],)
            )
            result = cursor.fetchone()
            if result:
                invoice_number = result[0]
        
        # Write the row
        writer.writerow([
            asset.get('asset_tag', ''),
            asset.get('type', ''),
            asset.get('brand', ''),
            asset.get('model', ''),
            asset.get('serial_number', ''),
            asset.get('status', ''),
            asset.get('condition', ''),
            asset.get('location_name', '') or '',
            '|'.join(tag_names),
            asset.get('holder_email', '') or '',
            asset.get('warranty_until', ''),
            asset.get('supplier', ''),
            asset.get('cost_center', ''),
            invoice_number,
            asset.get('purchase_date', ''),
            str(asset.get('price', 0)) if asset.get('price') is not None else '',
            asset.get('notes', '')
        ])
    
    return output.getvalue()


def import_assets_csv(service: AssetService, locations: LocationRepository, actor: str, text: str) -> Dict[str, object]:
    """Import assets from CSV format."""
    
    # Determine delimiter using csv.Sniffer
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:1024], delimiters=';,')
        delimiter = dialect.delimiter
    except csv.Error:
        # Fallback to semicolon if sniffing fails
        delimiter = ';'
    
    # Parse CSV content
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    
    # Initialize result counters
    result = {
        'created': 0,
        'updated': 0,
        'errors': []
    }
    
    # Process each row - skip header if it exists
    rows = list(reader)
    for i, row in enumerate(rows):
        try:
            # Validate required fields
            asset_tag = row.get('asset_tag', '').strip()
            if not asset_tag:
                result['errors'].append(f"řádek {i+2}: asset_tag is required")
                continue
            
            # Check if asset exists
            existing_asset = service.assets.get_by_tag(asset_tag)
            
            # Prepare fields for update or create
            # Only the columns present AND non-empty in the row are sent; an
            # empty cell means "leave as is" for an update and "default" for
            # a create. asset_tag is always present.
            fields = {'asset_tag': asset_tag}
            for column in ('type', 'brand', 'model', 'serial_number', 'purchase_date', 'notes', 'condition', 'supplier', 'warranty_until', 'cost_center'):
                value = (row.get(column) or '').strip()
                if value:
                    fields[column] = value
            if (row.get('price') or '').strip():
                fields['price'] = float(row['price'])
            
            # Handle location
            location_name = row.get('location', '').strip()
            location_id = None
            if location_name:
                location = locations.get_by_name(location_name)
                if not location:
                    location = locations.create(name=location_name)
                location_id = location['id']
            
            fields['location_id'] = location_id
            
            # Handle invoice
            invoice_number = row.get('invoice', '').strip()
            if invoice_number:
                fields['invoice_number'] = invoice_number
            
            # Handle tags
            tag_names = []
            tags_str = row.get('tags', '')
            if tags_str:
                tag_names = [tag.strip() for tag in tags_str.split('|') if tag.strip()]
            
            # Update or create asset
            if existing_asset:
                # Update existing asset
                fields['tag_names'] = tag_names
                service.update(actor, existing_asset['id'], **fields)
                result['updated'] += 1
            else:
                # Create new asset
                if not fields.get('type'):
                    result['errors'].append(f"řádek {i+2}: type is required for new asset")
                    continue
                
                fields['tag_names'] = tag_names
                fields.setdefault('brand', ''); fields.setdefault('model', ''); fields.setdefault('serial_number', ''); fields.setdefault('purchase_date', ''); fields.setdefault('price', 0); fields.setdefault('notes', '')
                service.create(actor, **fields)
                result['created'] += 1
                
        except (AssetValidationError, DuplicateAssetTag, ValueError) as e:
            # These specific exceptions should not be caught and logged - they should propagate
            # But since we're in a loop, we need to catch them and record as errors
            result['errors'].append(f"řádek {i+2}: {str(e)}")
    
    return result