from __future__ import annotations

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging

from src.auth.guards import api_auth_required, actor
from src.db import get_db
from src.services.asset_service import AssetService, AssetValidationError, DuplicateAssetTag
from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository

bp = Blueprint('api_assets', __name__, url_prefix='/assets')
logger = logging.getLogger(__name__)

def build_asset_service():
    """Build an AssetService instance with proper repositories."""
    return AssetService(
        AssetRepository(get_db()),
        AuditRepository(get_db())
    )

@bp.route('', methods=['GET'])
@api_auth_required
def list_assets():
    """List assets with optional filtering."""
    status = request.args.get('status')
    type_filter = request.args.get('type')
    q = request.args.get('q', '')
    
    try:
        service = build_asset_service()
        assets = service.list(status, type_filter, q)
        return jsonify(assets)
    except Exception as e:
        logger.exception("Error listing assets")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('', methods=['POST'])
@api_auth_required
def create_asset():
    """Create a new asset."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'asset_tag' not in data or 'type' not in data:
            return jsonify({'error': 'Missing asset_tag or type'}), 400
            
        actor_email = actor()
        
        service = build_asset_service()
        asset = service.create(
            actor=actor_email,
            asset_tag=data['asset_tag'],
            type=data['type'],
            brand=data.get('brand', ''),
            model=data.get('model', ''),
            serial_number=data.get('serial_number', ''),
            purchase_date=data.get('purchase_date', ''),
            price=data.get('price', 0.0),
            notes=data.get('notes', '')
        )
        
        return jsonify(asset), 201
        
    except AssetValidationError as e:
        return jsonify({'error': str(e)}), 400
    except DuplicateAssetTag as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.exception("Error creating asset")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<int:id>', methods=['GET'])
@api_auth_required
def get_asset(id):
    """Get a specific asset by ID."""
    try:
        service = build_asset_service()
        asset = service.get(id)
        
        if asset is None:
            return jsonify({'error': 'not found'}), 404
            
        return jsonify(asset)
    except Exception as e:
        logger.exception("Error getting asset")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<int:id>', methods=['PATCH'])
@api_auth_required
def update_asset(id):
    """Update a specific asset by ID."""
    try:
        data = request.get_json()
        
        actor_email = actor()
        
        service = build_asset_service()
        asset = service.update(actor=actor_email, asset_id=id, **data)
        
        if asset is None:
            return jsonify({'error': 'not found'}), 404
            
        return jsonify(asset)
        
    except AssetValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error updating asset")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<int:id>/retire', methods=['POST'])
@api_auth_required
def retire_asset(id):
    """Retire an asset."""
    try:
        actor_email = actor()
        
        service = build_asset_service()
        asset = service.retire(actor=actor_email, asset_id=id)
        
        return jsonify(asset)
        
    except AssetValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error retiring asset")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/<int:id>/lost', methods=['POST'])
@api_auth_required
def mark_asset_lost(id):
    """Mark an asset as lost."""
    try:
        actor_email = actor()
        
        service = build_asset_service()
        asset = service.mark_lost(actor=actor_email, asset_id=id)
        
        return jsonify(asset)
        
    except AssetValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error marking asset lost")
        return jsonify({'error': 'Internal server error'}), 500