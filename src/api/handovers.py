from flask import Blueprint, request, jsonify, send_file
import os
import logging
from src.services.factory import build_handover_service
from src.db import get_db
from src.auth.guards import api_auth_required, actor
from src.services.handover_service import HandoverError

bp = Blueprint('api_handovers', __name__)
logger = logging.getLogger(__name__)

def get_handover_service():
    """Get a configured handover service instance."""
    return build_handover_service(get_db())

@bp.route('/handovers', methods=['GET'])
@api_auth_required
def list_handovers():
    """Get list of handovers with optional filtering."""
    status = request.args.get('status')
    kind = request.args.get('kind')
    
    service = get_handover_service()
    
    try:
        # Get handovers with details
        handovers = service.handovers.list_all(status=status, kind=kind)
        
        # Add details to each handover
        result = []
        for handover in handovers:
            try:
                detailed_handover = service.with_details(handover)
                result.append(detailed_handover)
            except Exception as e:
                logger.exception("Failed to enrich handover with details")
                # Skip handovers that can't be enriched with details
                continue
        
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Failed to list handovers")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/handovers', methods=['POST'])
@api_auth_required
def create_handover():
    """Create a new handover."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'asset_id' not in data or 'employee_email' not in data:
            return jsonify({'error': 'Missing required fields: asset_id, employee_email'}), 400
        
        asset_id = data['asset_id']
        employee_email = data['employee_email']
        note = data.get('note', '')
        
        # Get employee by email
        service = get_handover_service()
        employee = service.employees.get_by_email(employee_email)
        if not employee:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Create handover
        actor_email = actor()
        handover = service.start_handover(
            actor=actor_email,
            asset_id=asset_id,
            employee_id=employee['id'],
            note=note
        )
        
        # Return the created handover with details
        detailed_handover = service.with_details(handover)
        return jsonify(detailed_handover), 201
        
    except HandoverError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.exception("Failed to create handover")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/handovers/<int:id>', methods=['GET'])
@api_auth_required
def get_handover(id):
    """Get a specific handover by ID."""
    service = get_handover_service()
    
    try:
        handover = service.handovers.get(id)
        if not handover:
            return jsonify({'error': 'Handover not found'}), 404
            
        detailed_handover = service.with_details(handover)
        return jsonify(detailed_handover), 200
        
    except Exception as e:
        logger.exception("Failed to get handover")
        return jsonify({'error': 'Handover not found'}), 404

@bp.route('/handovers/<int:id>/cancel', methods=['POST'])
@api_auth_required
def cancel_handover(id):
    """Cancel a pending handover."""
    service = get_handover_service()
    
    try:
        actor_email = actor()
        handover = service.cancel(actor_email, id)
        
        # Return the updated handover with details
        detailed_handover = service.with_details(handover)
        return jsonify(detailed_handover), 200
        
    except HandoverError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.exception("Failed to cancel handover")
        return jsonify({'error': 'Handover not found'}), 404

@bp.route('/handovers/<int:id>/protocol.pdf', methods=['GET'])
@api_auth_required
def get_protocol(id):
    """Get the protocol PDF for a handover."""
    service = get_handover_service()
    
    try:
        handover = service.handovers.get(id)
        if not handover:
            return jsonify({'error': 'Handover not found'}), 404
            
        # Check if protocol exists
        protocol_path = handover.get('protocol_path', '')
        if not protocol_path or not os.path.exists(protocol_path):
            return jsonify({'error': 'Protocol not found'}), 404
            
        # Return the PDF file
        return send_file(protocol_path, mimetype='application/pdf')
        
    except Exception as e:
        logger.exception("Failed to get protocol")
        return jsonify({'error': 'Protocol not found'}), 404

@bp.route('/returns', methods=['POST'])
@api_auth_required
def create_return():
    """Create a new return."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'asset_id' not in data:
            return jsonify({'error': 'Missing required fields: asset_id'}), 400
        
        asset_id = data['asset_id']
        note = data.get('note', '')
        
        # Create return
        actor_email = actor()
        service = get_handover_service()
        handover = service.start_return(
            actor=actor_email,
            asset_id=asset_id,
            note=note
        )
        
        # Return the created handover with details
        detailed_handover = service.with_details(handover)
        return jsonify(detailed_handover), 201
        
    except HandoverError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.exception("Failed to create return")
        return jsonify({'error': 'Internal server error'}), 500