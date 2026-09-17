import json

from tests.conftest import api, login, outbox


def test_settings_page_requires_admin_and_saves(app, client):
    login(client, "jan@firma.cz")
    assert client.get("/admin/settings").status_code == 403
    login(client, "admin@firma.cz")
    page = client.get("/admin/settings")
    assert page.status_code == 200 and "SMTP" in page.get_data(as_text=True) and "Entra" in page.get_data(as_text=True)
    resp = client.post("/admin/settings", data={"SMTP_HOST": "smtp.f.cz", "SMTP_PORT": "2525", "SMTP_PASSWORD": "pw", "COMPANY_NAME": "Firma s.r.o."}, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "smtp.f.cz" in body and "pw" not in body and "••••" in body
    assert app.config["SMTP_HOST"] == "smtp.f.cz" and app.config["SMTP_PORT"] == 2525 and app.config["COMPANY_NAME"] == "Firma s.r.o."
    bad = client.post("/admin/settings", data={"SMTP_PORT": "abc"}, follow_redirects=True)
    assert "SMTP_PORT" in bad.get_data(as_text=True) and app.config["SMTP_PORT"] == 2525


def test_settings_apply_on_the_next_request_after_an_api_change(app, client):
    login(client, "admin@firma.cz")
    client.post("/admin/settings", data={"COMPANY_NAME": "Nová"}, follow_redirects=True)
    assert app.config["COMPANY_NAME"] == "Nová"
    assert "Nová" in client.get("/admin/assets").get_data(as_text=True)


def test_test_email_button_sends_to_the_admin(app, client):
    login(client, "admin@firma.cz")
    resp = client.post("/admin/settings/test-email", follow_redirects=True)
    assert resp.status_code == 200
    assert outbox(app)[-1]["to"] == "admin@firma.cz" and "test" in outbox(app)[-1]["subject"].lower()


def test_oidc_redirect_uri_is_shown(client):
    login(client, "admin@firma.cz")
    assert "http://testserver/auth/callback" in client.get("/admin/settings/auth").get_data(as_text=True)


def test_hr_sync_now_uses_the_configured_drupal(app, client):
    login(client, "admin@firma.cz")
    page = {"data": [{"id": "u1", "attributes": {"drupal_internal__uid": 5, "mail": "petr@firma.cz", "display_name": "Petr Král", "status": True, "field_department": "Sklad"}}], "links": {}}
    app.config["DRUPAL_FETCH"] = lambda url, headers: (200, json.dumps(page))
    client.post("/admin/settings", data={"DRUPAL_URL": "https://hr.firma.cz", "DRUPAL_AUTH_MODE": "none"}, follow_redirects=True)
    resp = client.post("/admin/settings/hr-sync", follow_redirects=True)
    assert resp.status_code == 200 and "1" in resp.get_data(as_text=True)
    assert api(client, "GET", "/api/v1/employees/petr@firma.cz").get_json()["department"] == "Sklad"


def test_hr_sync_without_url_is_a_clear_error(client):
    login(client, "admin@firma.cz")
    resp = client.post("/admin/settings/hr-sync", follow_redirects=True)
    assert "DRUPAL_URL" in resp.get_data(as_text=True)
