from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
import json
import logging
from src.services.settings_service import SettingsService, SETTINGS_SCHEMA
from src.repositories.settings import SettingsRepository
from src.config import load_config
from src.db import get_db
from src.auth.guards import admin_required, actor, current_user
from src.services.factory import build_email_sender
from src.services.drupal_hr import DrupalHrClient, DrupalHrError
from src.services.hr_sync import HrSyncService
from src.repositories.employees import EmployeeRepository
from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.assignments import AssignmentRepository


bp = Blueprint('settings', __name__, url_prefix='/admin/settings')


def apply_settings(app) -> None:
    """Read settings from the repository and update app.config."""
    service = SettingsService(SettingsRepository(get_db()))
    # Base = what the app is running with now (env defaults + explicit
    # overrides); stored settings win over it, never the other way round.
    base = {item['key']: app.config.get(item['key']) for item in SETTINGS_SCHEMA if item['key'] in app.config}
    effective_config = service.effective(base)
    
    # Only update keys that are in SETTINGS_SCHEMA
    for key in SETTINGS_SCHEMA:
        setting_key = key['key']
        if setting_key in effective_config:
            app.config[setting_key] = effective_config[setting_key]
    
    # Store the repository version in app.config
    app.config['SETTINGS_VERSION'] = service.repo.version()


@bp.before_app_request
def check_settings_version():
    """Check if settings have changed and update app config if needed."""
    if not hasattr(current_app, 'config'):
        return
    
    stored_version = SettingsRepository(get_db()).version()
    current_version = current_app.config.get('SETTINGS_VERSION', 0)
    
    if stored_version != current_version:
        apply_settings(current_app)


@bp.route('', methods=['GET'])
@admin_required
def settings_page():
    """Display the admin settings page."""
    service = SettingsService(SettingsRepository(get_db()))
    
    # Group settings by group
    rows = service.for_form(current_app.config)
    
    # Group by group name
    groups = []
    group_dict = {}
    
    for row in rows:
        group_name = row['group']
        if group_name not in group_dict:
            group_dict[group_name] = []
            groups.append((group_name, group_dict[group_name]))
        group_dict[group_name].append(row)
    
    return render_template(
        'admin/settings.html',
        rows=rows,
        groups=groups,
        redirect_uri=current_app.config['BASE_URL'] + current_app.config['OIDC_REDIRECT_PATH'],
        problems=[]
    )


@bp.route('', methods=['POST'])
@admin_required
def save_settings():
    """Save admin settings."""
    service = SettingsService(SettingsRepository(get_db()))
    
    # Process form values
    values = {}
    for setting_def in SETTINGS_SCHEMA:
        key = setting_def['key']
        # For boolean fields, check if they're present in form data
        if setting_def['type'] == 'bool':
            values[key] = '1' if key in request.form else '0'
        else:
            values[key] = request.form.get(key, '')
    
    # Validate settings
    problems = service.validate(values)
    
    if problems:
        # Re-render the page with validation errors
        return render_template(
            'admin/settings.html',
            rows=service.for_form(current_app.config),
            groups=[(group, [row for row in service.for_form(current_app.config) if row['group'] == group]) 
                    for group in set(row['group'] for row in service.for_form(current_app.config))],
            redirect_uri=current_app.config['BASE_URL'] + current_app.config['OIDC_REDIRECT_PATH'],
            problems=problems
        ), 200
    
    # Save the settings
    service.save(values, updated_by=actor())
    
    # Apply the new settings to app config
    apply_settings(current_app)
    
    # Log audit event
    changed_keys = [key for key in values if key in SETTINGS_SCHEMA]
    flash('Nastavení uloženo.')
    
    return redirect(url_for('settings.settings_page'))


@bp.route('/test-email', methods=['POST'])
@admin_required
def test_email():
    """Send a test email to the logged-in admin."""
    try:
        # Build email sender from current config
        email_sender = build_email_sender(current_app.config)
        
        # Get the logged-in admin's email
        user = current_user()
        if not user:
            flash('Chyba: Nejste přihlášen', 'error')
            return redirect(url_for('settings.settings_page'))
        
        # Send test email
        email_sender.send(
            to=user['email'],
            subject='HW Desk – testovací e-mail',
            text='Toto je testovací e-mail z HW Desk. Pokud jej čtete, odesílání funguje.',
            html='<p>Toto je testovací e-mail z HW Desk. Pokud jej čtete, odesílání funguje.</p>',
        )
        
        flash('Testovací e-mail byl odeslán.', 'success')
    except Exception as e:
        logging.exception("Failed to send test email")
        flash(f'Chyba při odesílání e-mailu: {str(e)}', 'error')
    
    return redirect(url_for('settings.settings_page'))


@bp.route('/hr-sync', methods=['POST'])
@admin_required
def hr_sync():
    """Trigger HR synchronization."""
    # Check if DRUPAL_URL is set
    if not current_app.config.get('DRUPAL_URL'):
        flash('Nejprve nastavte DRUPAL_URL.', 'error')
        return redirect(url_for('settings.settings_page'))
    
    try:
        # Build Drupal HR client
        field_map = {}
        if current_app.config.get('DRUPAL_FIELD_MAP'):
            field_map = json.loads(current_app.config['DRUPAL_FIELD_MAP'])
        
        client = DrupalHrClient(
            base_url=current_app.config['DRUPAL_URL'],
            auth_mode=current_app.config.get('DRUPAL_AUTH_MODE', 'none'),
            user=current_app.config.get('DRUPAL_USER', ''),
            password=current_app.config.get('DRUPAL_PASSWORD', ''),
            token=current_app.config.get('DRUPAL_TOKEN', ''),
            field_map=field_map,
            filter_query=current_app.config.get('DRUPAL_FILTER', ''),
            fetch=current_app.config.get('DRUPAL_FETCH')  # Test hook
        )
        
        # Fetch employees
        records, skipped = client.fetch_employees()
        
        # Run HR sync service
        employees_repo = EmployeeRepository(get_db())
        assets_repo = AssetRepository(get_db())
        audit_repo = AuditRepository(get_db())
        assignments_repo = AssignmentRepository(get_db())
        
        sync_service = HrSyncService(
            employees=employees_repo,
            assets=assets_repo,
            audit=audit_repo,
            assignments=assignments_repo
        )
        
        result = sync_service.sync(actor(), records)
        
        # Flash summary message
        summary = f'HR synchronizace: {result["created"]} nových, {result["updated"]} upravených, {result["deactivated"]} deaktivovaných, {skipped} přeskočeno'
        flash(summary, 'success')
        
    except DrupalHrError as e:
        flash(f'Chyba HR synchronizace: {str(e)}', 'error')
    except Exception as e:
        logging.exception("Failed to sync HR data")
        flash(f'Neznámá chyba: {str(e)}', 'error')
    
    return redirect(url_for('settings.settings_page'))