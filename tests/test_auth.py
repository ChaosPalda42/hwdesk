from tests.conftest import login


def test_dev_login_and_whoami(client):
    assert client.get("/").status_code in (302, 303)  # anonymous -> login
    login(client, "Jan@Firma.cz")
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.get_json() == {"email": "jan@firma.cz", "is_admin": False}
    login(client, "admin@firma.cz")
    assert client.get("/auth/me").get_json()["is_admin"] is True
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_dev_login_is_refused_in_oidc_mode(app, client):
    app.config["AUTH_MODE"] = "oidc"
    app.config["OIDC_TENANT_ID"] = "t"
    app.config["OIDC_CLIENT_ID"] = "c"
    app.config["OIDC_CLIENT_SECRET"] = "s"
    assert client.post("/auth/dev-login", data={"email": "x@y"}).status_code == 404
    resp = client.get("/auth/login")
    assert resp.status_code in (302, 303) and "login.microsoftonline.com" in resp.headers["Location"]


def test_admin_pages_need_admin(client):
    login(client, "jan@firma.cz")
    assert client.get("/admin/assets").status_code == 403
    login(client, "admin@firma.cz")
    assert client.get("/admin/assets").status_code == 200


def test_api_needs_key_or_admin_session(client):
    assert client.get("/api/v1/assets").status_code == 401
    assert client.get("/api/v1/assets", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/v1/assets", headers={"Authorization": "Bearer test-api-key"}).status_code == 200
    login(client, "admin@firma.cz")
    assert client.get("/api/v1/assets").status_code == 200
    login(client, "jan@firma.cz")
    assert client.get("/api/v1/assets").status_code == 403
