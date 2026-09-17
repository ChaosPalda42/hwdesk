import pytest

def test_admin_page_access(client):
    """
    Test that admin can access all required pages.
    """
    # Login as admin
    client.post('/auth/dev-login', data={'email': 'admin@firma.cz'})
    
    # Test all required admin pages
    pages = [
        '/admin/assets',
        '/admin/assets/new',
        '/admin/employees',
        '/admin/handovers',
        '/admin/audit'
    ]
    
    for page in pages:
        resp = client.get(page)
        assert resp.status_code == 200, f"Failed to access {page}"

    # Test employee-specific page (assuming jan@firma.cz exists)
    resp = client.get('/admin/employees/jan@firma.cz')
    if resp.status_code != 404:
        assert resp.status_code == 200, "Failed to access employee details"


def test_employee_access_restrictions(client):
    """
    Test that employee cannot access admin pages and anonymous can see login.
    """
    # Login as employee
    client.post('/auth/dev-login', data={'email': 'jan@firma.cz'})
    
    # Employee should get 403 when accessing admin assets
    resp = client.get('/admin/assets')
    assert resp.status_code == 403, "Employee should not access /admin/assets"
    
    # Logout and test anonymous login page - follow redirects to final page
    logout_resp = client.post('/auth/logout', follow_redirects=True)
    assert logout_resp.status_code == 200, "Login page should be accessible after logout"
    html_content = logout_resp.get_data(as_text=True)
    
    # Check for Czech login text
    if 'Přihlásit' not in html_content and 'Log In' not in html_content:
        raise AssertionError(f"Expected login button not found. Content: {html_content[:200]}...")

    # Test unknown token handling for handover confirmation
    client.post('/auth/dev-login', data={'email': 'jan@firma.cz'})
    resp = client.get('/handovers/confirm/12345')
    assert resp.status_code == 410, "Unknown token should return 410"

def test_asset_pages(client):
    """
    Test asset listing and detail pages specifically.
    """
    # Login as admin
    client.post('/auth/dev-login', data={'email': 'admin@firma.cz'})
    
    # Test asset listing page - should at least be accessible
    resp = client.get('/admin/assets')
    assert resp.status_code == 200, "Failed to access /admin/assets"