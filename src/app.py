from flask import Flask, jsonify, request
from pathlib import Path

# Import collaborators
from src.config import load_config
from src.db import close_db
from src.auth.guards import current_user

# (module path, attribute, url_prefix). Registered in order; see _register_blueprints.
BLUEPRINTS = (
    ('src.auth.oidc', 'bp', None),
    ('src.web.admin', 'bp', None),
    ('src.web.employee', 'bp', None),
    ('src.web.settings', 'bp', None),
    ('src.web.catalog', 'bp', None),
    ('src.api.assets', 'bp', '/api/v1'),
    ('src.api.employees', 'bp', '/api/v1'),
    ('src.api.handovers', 'bp', '/api/v1'),
    ('src.api.taxonomy', 'bp', '/api/v1'),
    ('src.api.repairs', 'bp', '/api/v1'),
)

def _register_blueprints(app) -> None:
    """Import and register every blueprint. While the Factory builds the
    project one contract at a time, HWDESK_ALLOW_MISSING_BLUEPRINTS=1 lets a
    not-yet-produced blueprint be skipped; in production every import is
    strict."""
    import importlib
    import os

    allow_missing = os.environ.get('HWDESK_ALLOW_MISSING_BLUEPRINTS') == '1'
    for module_name, attribute, prefix in BLUEPRINTS:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if allow_missing and exc.name == module_name:
                continue
            raise
        app.register_blueprint(getattr(module, attribute), url_prefix=prefix)

def _format_dt(value):
    """ISO timestamp -> '17. 9. 2026 12:21' in local time; passes through anything else."""
    if not value:
        return "—"
    from datetime import datetime, timezone
    try:
        parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone()
    return f"{local.day}. {local.month}. {local.year} {local:%H:%M}"

def create_app(overrides=None):
    # Create Flask app with proper template and static folders
    templates_dir = Path(__file__).resolve().parent.parent / 'templates'
    static_dir = Path(__file__).resolve().parent.parent / 'static'

    app = Flask(__name__, template_folder=str(templates_dir), static_folder=str(static_dir))

    # Load and update configuration
    app.config.update(load_config(overrides))
    app.jinja_env.filters['dt'] = _format_dt

    # Register blueprints as specified in the contract:
    _register_blueprints(app)

    # Register repairs endpoints (fallback if blueprint lacks routes)
    from src.db import get_db
    from src.services.repair_service import RepairService
    from src.repositories.assets import AssetRepository
    from src.repositories.repairs import RepairRepository
    from src.repositories.audit import AuditRepository
    @app.route('/api/v1/assets/<int:asset_id>/repairs', methods=['GET'])
    def list_repairs(asset_id):
        # List repairs for an asset using the service layer.
        db = get_db()
        service = RepairService(AssetRepository(db), RepairRepository(db), AuditRepository(db))
        repairs = service.repairs.list_for_asset(asset_id)
        return jsonify(repairs), 200
    @app.route('/api/v1/assets/<int:asset_id>/repairs', methods=['POST'])
    def open_repair(asset_id):
        payload = request.get_json() or {}
        actor = current_user().get('email') if isinstance(current_user(), dict) else str(current_user())
        service = RepairService(AssetRepository(get_db()), RepairRepository(get_db()), AuditRepository(get_db()))
        repair = service.open_repair(
            actor=actor,
            asset_id=asset_id,
            description=payload.get('description'),
            vendor=payload.get('vendor'),
            sent_at=payload.get('sent_at'),
            cost=payload.get('cost'),
        )
        return jsonify(repair), 201
    @app.route('/api/v1/repairs/<int:repair_id>/close', methods=['POST'])
    def close_repair(repair_id):
        payload = request.get_json() or {}
        actor = current_user().get('email') if isinstance(current_user(), dict) else str(current_user())
        service = RepairService(AssetRepository(get_db()), RepairRepository(get_db()), AuditRepository(get_db()))
        updated = service.close_repair(
            actor=actor,
            repair_id=repair_id,
            returned_at=payload.get('returned_at'),
            result=payload.get('result'),
            cost=payload.get('cost'),
        )
        return jsonify(updated), 200

    # Register teardown handler
    app.teardown_appcontext(close_db)

    # Health check endpoint
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    # Context processor for injecting user and config into templates
    @app.context_processor
    def inject_user_and_config():
        return {
            'user': current_user(),
            'config': app.config
        }

    # Settings stored in the database override the environment defaults.
    from src.web.settings import apply_settings
    with app.app_context():
        apply_settings(app)
    return app

if __name__ == '__main__':
    create_app().run()
