from flask import Flask, jsonify
from pathlib import Path

# Import collaborators
from src.config import load_config
from src.db import close_db
from src.auth.oidc import bp as auth_bp
from src.web.admin import bp as admin_bp
from src.web.employee import bp as employee_bp
from src.api.assets import bp as assets_api_bp
from src.api.employees import bp as employees_api_bp
from src.api.handovers import bp as handovers_api_bp
from src.auth.guards import current_user

def create_app(overrides=None):
    # Create Flask app with proper template and static folders
    templates_dir = Path(__file__).resolve().parent.parent / 'templates'
    static_dir = Path(__file__).resolve().parent.parent / 'static'
    
    app = Flask(__name__, template_folder=str(templates_dir), static_folder=str(static_dir))
    
    # Load and update configuration
    app.config.update(load_config(overrides))
    
    # Register blueprints as specified in the contract:
    # auth bp (src/auth/oidc.py), admin bp (src/web/admin.py), employee bp (src/web/employee.py, no prefix)
    # and the three API blueprints at url_prefix '/api/v1'
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(employee_bp)
    
    # Register API blueprints at url_prefix '/api/v1'
    app.register_blueprint(assets_api_bp, url_prefix='/api/v1')
    app.register_blueprint(employees_api_bp, url_prefix='/api/v1')
    app.register_blueprint(handovers_api_bp, url_prefix='/api/v1')
    
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
    
    return app

if __name__ == '__main__':
    create_app().run()