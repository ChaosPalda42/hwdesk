from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from src.auth.guards import login_required, current_user
from src.services.factory import build_handover_service
from src.repositories.employees import EmployeeRepository
from src.db import get_db
from src.services.handover_service import HandoverError
import os
import logging

# Set up logging
logger = logging.getLogger(__name__)

bp = Blueprint('my', __name__, url_prefix=None)

@bp.route('/', methods=['GET'])
@login_required
def home():
    employee_repo = EmployeeRepository(get_db())
    user = current_user()
    employee = employee_repo.get_by_email(user['email'])
    
    if employee is None:
        return render_template('my/not_registered.html'), 200
    
    # Build the handover service to get employee overview
    try:
        service = build_handover_service(get_db())
        overview = service.overview_for_employee(employee['id'])
    except Exception as e:
        logger.exception("Failed to get employee overview")
        return render_template('my/not_registered.html'), 200
    
    return render_template('my/home.html', overview=overview, user=user)

@bp.route('/handovers/confirm/<token>', methods=['GET', 'POST'])
@login_required
def confirm_handover(token):
    user = current_user()
    
    if request.method == 'GET':
        # Verify the token
        try:
            service = build_handover_service(get_db())
            token_data = service.tokens.verify(token)
        except Exception as e:
            logger.exception("Failed to verify token")
            return render_template('my/handover_confirm.html', error="Neplatný nebo expirovaný odkaz"), 410
        
        if not token_data:
            # Token is invalid or expired
            return render_template('my/handover_confirm.html', error="Neplatný nebo expirovaný odkaz"), 410
        
        # Get the handover details
        try:
            handover = service.handovers.get(token_data['handover_id'])
        except Exception as e:
            logger.exception("Failed to get handover details")
            return render_template('my/handover_confirm.html', error="Neplatný nebo expirovaný odkaz"), 410
            
        # Check if the handover is still pending
        if handover['status'] != 'pending':
            return render_template('my/handover_confirm.html', notice="Převzetí zařízení již není možné"), 200
            
        # Check that the token email matches the logged-in user
        if user['email'].lower() != token_data['email'].lower():
            return "Forbidden", 403
            
        # Get the details for the handover
        try:
            handover_with_details = service.with_details(handover)
        except Exception as e:
            logger.exception("Failed to get handover details")
            return render_template('my/handover_confirm.html', error="Chyba při načítání detailů"), 410
            
        return render_template('my/handover_confirm.html', handover=handover_with_details)
    
    elif request.method == 'POST':
        # Process the confirmation or decline
        action = request.form.get('action')
        reason = request.form.get('reason', '')
        
        if action not in ('confirm', 'decline'):
            flash("Neplatná akce", "error")
            return redirect(url_for('my.home'))
            
        service = build_handover_service(get_db())
        
        try:
            if action == 'confirm':
                service.confirm(token, user['email'])
                flash("Potvrzeno", "success")
            else:  # action == 'decline'
                service.decline(token, user['email'], reason)
                flash("Odmítnuto", "success")
        except HandoverError as e:
            # Handle specific handover errors
            if "Actor email does not match token email" in str(e) or "email does not match" in str(e):
                return "Forbidden", 403
            else:
                flash(str(e), "error")
                return redirect(url_for('my.home'))
        except Exception as e:
            logger.exception("Failed to process handover confirmation/decline")
            flash("Došlo k chybě při zpracování požadavku", "error")
            return redirect(url_for('my.home'))
            
        return redirect(url_for('my.home'))

@bp.route('/my/assets/<int:id>/return', methods=['POST'])
@login_required
def request_asset_return(id):
    user = current_user()
    
    note = request.form.get('note', '')
    
    service = build_handover_service(get_db())
    
    try:
        service.request_return(employee_email=user['email'], asset_id=id, note=note)
        flash("Žádost o vrácení zařízení byla úspěšně odeslána", "success")
    except HandoverError as e:
        flash(str(e), "error")
    except Exception as e:
        logger.exception("Failed to request asset return")
        flash("Došlo k chybě při zpracování požadavku", "error")
    
    return redirect(url_for('my.home'))

@bp.route('/my/protocols/<filename>', methods=['GET'])
@login_required
def get_protocol(filename):
    user = current_user()
    
    # Check if the user is admin
    is_admin = user.get('is_admin', False)
    
    # If not admin, check if the user has a handover with that protocol
    if not is_admin:
        service = build_handover_service(get_db())
        
        # Find handovers that have this protocol file
        try:
            # Get all handovers to check if any belong to the user
            all_handovers = service.handovers.list_all()
            
            # Check if any handover has this protocol file
            found = False
            for handover in all_handovers:
                if handover.get('protocol_path') and filename in handover['protocol_path']:
                    # Check if this is the user's handover
                    employee = service.employees.get(handover['employee_id'])
                    if employee and employee['email'].lower() == user['email'].lower():
                        found = True
                        break
                        
            if not found:
                return "Not Found", 404
                
        except Exception as e:
            logger.exception("Failed to check protocol access")
            return "Not Found", 404
    
    # Get the protocol directory from config
    try:
        service = build_handover_service(get_db())
        protocol_dir = service.protocol_dir
    except Exception as e:
        logger.exception("Failed to get protocol directory")
        return "Not Found", 404

    # Serve the file
    try:
        return send_from_directory(protocol_dir, filename)
    except Exception as e:
        logger.exception("Failed to serve protocol file")
        return "Not Found", 404