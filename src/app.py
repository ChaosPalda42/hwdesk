from flask import Flask, jsonify
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
    # auth bp (src/auth/oidc.py), admin bp (src/web/admin.py), employee bp (src/web/employee.py, no prefix)
    # and the three API blueprints at url_prefix '/api/v1'
    _register_blueprints(app)
    
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