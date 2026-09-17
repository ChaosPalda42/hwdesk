from flask import Flask, jsonify
from pathlib import Path

# Import collaborators
from src.config import load_config
from src.db import close_db
from src.auth.oidc import bp as auth_bp
from src.web.admin import bp as admin_bp
from src.web.employee import bp as employee_bp
from src.web.settings import bp as settings_bp, apply_settings
from src.web.catalog import bp as catalog_bp
from src.api.taxonomy import bp as taxonomy_api_bp
from src.api.assets import bp as assets_api_bp
from src.api.employees import bp as employees_api_bp
from src.api.handovers import bp as handovers_api_bp
from src.auth.guards import current_user

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
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(catalog_bp)
    
    # Register API blueprints at url_prefix '/api/v1'
    app.register_blueprint(assets_api_bp, url_prefix='/api/v1')
    app.register_blueprint(employees_api_bp, url_prefix='/api/v1')
    app.register_blueprint(handovers_api_bp, url_prefix='/api/v1')
    app.register_blueprint(taxonomy_api_bp, url_prefix='/api/v1')
    
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
    with app.app_context():
        apply_settings(app)
    return app

if __name__ == '__main__':
    create_app().run()