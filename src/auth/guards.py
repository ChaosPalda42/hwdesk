from functools import wraps
from flask import session, g, request, redirect, url_for, current_app, jsonify
from typing import Dict, Optional, Union


def current_user() -> Optional[Dict[str, Union[str, bool]]]:
    """Get the current user from the session."""
    if 'email' not in session:
        return None
    
    email = session['email'].lower()
    is_admin = email in current_app.config['ADMIN_EMAILS']
    
    return {
        'email': email,
        'is_admin': is_admin
    }


def login_required(f):
    """Decorator to require login for a view function."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a view function."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if 'email' not in session:
            # Redirect to login page with next parameter
            return redirect(url_for('auth.login', next=request.path))
        
        # Check if user is admin
        email = session['email'].lower()
        if email not in current_app.config['ADMIN_EMAILS']:
            # Return 403 JSON for API routes, HTML for others
            if request.path.startswith('/api/'):
                return jsonify({'error': 'admin required'}), 403
            else:
                return 'Forbidden', 403
        
        return f(*args, **kwargs)
    return decorated_function


def api_auth_required(f):
    """Decorator to require API authentication for a view function."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            api_key = auth_header.split(' ')[1]
            if api_key in current_app.config['API_KEYS']:
                # Set the API actor
                g.api_actor = f'api:{api_key[:4]}'
                return f(*args, **kwargs)
        
        # Check for admin session
        if 'email' in session:
            email = session['email'].lower()
            if email in current_app.config['ADMIN_EMAILS']:
                return f(*args, **kwargs)
        
        # If no valid API key and not admin session
        if auth_header is None or not auth_header.startswith('Bearer '):
            # Return 401 JSON for API routes, HTML for others
            if request.path.startswith('/api/'):
                return jsonify({'error': 'unauthorized'}), 401
            else:
                return 'Unauthorized', 401
        
        # Invalid API key but session exists
        if request.path.startswith('/api/'):
            return jsonify({'error': 'admin required'}), 403
        else:
            return 'Forbidden', 403
    
    return decorated_function


def actor() -> str:
    """Get the actor identifier."""
    if hasattr(g, 'api_actor'):
        return g.api_actor
    elif 'email' in session:
        return session['email'].lower()
    else:
        return 'anonymous'