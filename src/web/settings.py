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


# Sections of the settings area: URL slug -> schema group. Locations and
# tags live in src/web/catalog.py and share the same sub-navigation.
SECTIONS = {
    'general': 'Obecné',
    'auth': 'Přihlášení Microsoft 365 (Entra ID)',
    'email': 'E-mail (SMTP)',
    'hr': 'HR synchronizace (Drupal)',
    'labels': 'Inventární čísla a štítky',
}


def _section_url(section: str) -> str:
    return '/admin/settings' if section == 'general' else f'/admin/settings/{section}'


def _section_for_keys(keys) -> str:
    """The section most of the posted keys belong to (ties: schema order)."""
    groups = {d['key']: d['group'] for d in SETTINGS_SCHEMA}
    counts: dict[str, int] = {}
    for key in keys:
        group = groups.get(key)
        if group:
            counts[group] = counts.get(group, 0) + 1
    if not counts:
        return 'general'
    best = max(counts.values())
    for slug, group in SECTIONS.items():
        if counts.get(group) == best:
            return slug
    return 'general'


def _render_section(section: str, problems=None, status=200):
    service = SettingsService(SettingsRepository(get_db()))
    group = SECTIONS[section]
    rows = [row for row in service.for_form(current_app.config) if row['group'] == group]
    return render_template(
        'admin/settings.html',
        section=section,
        section_url=_section_url(section),
        group=group,
        rows=rows,
        redirect_uri=current_app.config['BASE_URL'] + current_app.config['OIDC_REDIRECT_PATH'],
        problems=problems or [],
    ), status


@bp.route('', methods=['GET'])
@bp.route('/<section>', methods=['GET'])
@admin_required
def settings_page(section: str = 'general'):
    if section not in SECTIONS:
        return redirect('/admin/settings')
    return _render_section(section)


@bp.route('', methods=['POST'])
@bp.route('/<section>', methods=['POST'])
@admin_required
def save_settings(section: str | None = None):
    """Save the keys present in the form; other sections stay untouched.

    An unchecked checkbox is absent from the form, so each page lists its
    bool keys in `_bools` to turn absence into '0'.
    """
    service = SettingsService(SettingsRepository(get_db()))
    bools = set((request.form.get('_bools') or '').split(','))
    values = {}
    for setting_def in SETTINGS_SCHEMA:
        key = setting_def['key']
        if setting_def['type'] == 'bool':
            if key in request.form or key in bools:
                values[key] = '1' if key in request.form else '0'
        elif key in request.form:
            values[key] = request.form.get(key, '')
    if section not in SECTIONS:
        # A post to the bare URL (scripts, older forms): land where the keys live.
        section = _section_for_keys(values)
    problems = service.validate(values)
    if problems:
        return _render_section(section, problems=problems)
    service.save(values, updated_by=actor())
    apply_settings(current_app)
    flash('Nastavení uloženo.')
    return redirect(_section_url(section))


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
            return redirect('/admin/settings/email')
        
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
    
    return redirect('/admin/settings/email')


@bp.route('/hr-sync', methods=['POST'])
@admin_required
def hr_sync():
    """Trigger HR synchronization."""
    # Check if DRUPAL_URL is set
    if not current_app.config.get('DRUPAL_URL'):
        flash('Nejprve nastavte DRUPAL_URL.', 'error')
        return redirect('/admin/settings/hr')
    
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
    
    return redirect('/admin/settings/hr')