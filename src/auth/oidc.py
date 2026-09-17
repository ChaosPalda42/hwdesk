from flask import Blueprint, request, session, redirect, url_for, current_app, jsonify, render_template
import msal
import os

bp = Blueprint('auth', __name__, url_prefix='/auth')

def get_base_url():
    return current_app.config.get('BASE_URL', 'http://localhost:5000')

def get_oidc_config():
    return {
        'client_id': current_app.config.get('OIDC_CLIENT_ID'),
        'client_secret': current_app.config.get('OIDC_CLIENT_SECRET'),
        'tenant': current_app.config.get('OIDC_TENANT_ID'),
        'redirect_path': current_app.config.get('OIDC_REDIRECT_PATH', '/auth/callback')
    }

@bp.route('/login', methods=['GET'])
def login():
    auth_mode = current_app.config.get('AUTH_MODE', 'dev')
    
    if auth_mode == 'dev':
        return render_template('login.html')
    elif auth_mode == 'oidc':
        oidc_config = get_oidc_config()
        app = msal.ConfidentialClientApplication(
            client_id=oidc_config['client_id'],
            authority=f'https://login.microsoftonline.com/{oidc_config["tenant"]}',
            client_credential=oidc_config['client_secret']
        )
        
        # Generate state and store in session
        state = os.urandom(24).hex()
        session['oauth_state'] = state
        
        redirect_uri = get_base_url() + oidc_config['redirect_path']
        
        auth_url = app.get_authorization_request_url(
            scopes=['User.Read'],
            state=state,
            redirect_uri=redirect_uri
        )
        
        return redirect(auth_url)
    else:
        # Handle unknown auth mode
        return 'Unauthorized', 401

@bp.route('/callback', methods=['GET'])
def callback():
    auth_mode = current_app.config.get('AUTH_MODE', 'dev')
    
    if auth_mode != 'oidc':
        return 'Unauthorized', 401
    
    # Verify state
    if 'oauth_state' not in session:
        return 'Unauthorized', 401
    
    state = session['oauth_state']
    
    # Get the authorization code from the query parameters
    code = request.args.get('code')
    
    if not code:
        return 'Unauthorized', 401
    
    oidc_config = get_oidc_config()
    app = msal.ConfidentialClientApplication(
        client_id=oidc_config['client_id'],
        authority=f'https://login.microsoftonline.com/{oidc_config["tenant"]}',
        client_credential=oidc_config['client_secret']
    )
    
    redirect_uri = get_base_url() + oidc_config['redirect_path']
    
    # Acquire token by authorization code
    token_result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=['User.Read'],
        redirect_uri=redirect_uri
    )
    
    # Check for errors in token acquisition
    if 'error' in token_result:
        return token_result['error_description'], 400
    
    # Extract email and name from id_token_claims
    id_token_claims = token_result.get('id_token_claims', {})
    
    email = id_token_claims.get('preferred_username') or id_token_claims.get('email')
    
    if email:
        session['email'] = email.lower()
        session['name'] = id_token_claims.get('name', email)
    
    return redirect('/')

@bp.route('/dev-login', methods=['POST'])
def dev_login():
    auth_mode = current_app.config.get('AUTH_MODE', 'dev')
    
    if auth_mode != 'dev':
        return 'Not Found', 404
    
    email = request.form.get('email')
    
    if email:
        session['email'] = email.lower()
        session['name'] = email
    
    next_url = request.form.get('next', '/')
    return redirect(next_url)

@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@bp.route('/me', methods=['GET'])
def me():
    from .guards import current_user
    
    user = current_user()
    
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    
    return jsonify(user)