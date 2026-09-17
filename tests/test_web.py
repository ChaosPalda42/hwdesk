from tests.conftest import api, login, outbox


def _seed(client):
    api(client, "POST", "/api/v1/hr/employees", json={"employees": [{"email": "jan@firma.cz", "display_name": "Jan Novák", "department": "IT", "manager_email": "", "hr_id": "1", "active": True}]})
    return api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-0001", "type": "notebook", "brand": "Dell", "model": "Latitude", "serial_number": "S", "purchase_date": "", "price": 0, "notes": ""}).get_json()["id"]


def test_admin_asset_pages(client):
    aid = _seed(client)
    login(client, "admin@firma.cz")
    page = client.get("/admin/assets").get_data(as_text=True)
    assert "NB-0001" in page and "Latitude" in page
    assert client.get("/admin/assets/new").status_code == 200
    created = client.post("/admin/assets/new", data={"asset_tag": "MO-0001", "type": "monitor", "brand": "LG", "model": "27", "serial_number": "", "purchase_date": "", "price": "5000", "notes": ""}, follow_redirects=True)
    assert created.status_code == 200 and "MO-0001" in created.get_data(as_text=True)
    detail = client.get(f"/admin/assets/{aid}").get_data(as_text=True)
    assert "Dell" in detail and "jan@firma.cz" in detail  # employee picker offers Jan
    assert client.get("/admin/assets/999").status_code == 404
    edited = client.post(f"/admin/assets/{aid}/edit", data={"asset_tag": "NB-0001", "type": "notebook", "brand": "DELL", "model": "Latitude", "serial_number": "S", "purchase_date": "", "price": "0", "notes": "x"}, follow_redirects=True)
    assert "DELL" in edited.get_data(as_text=True)


def test_admin_handover_from_the_asset_page(app, client):
    aid = _seed(client)
    login(client, "admin@firma.cz")
    resp = client.post(f"/admin/assets/{aid}/handover", data={"employee_email": "jan@firma.cz", "note": "vč. nabíječky"}, follow_redirects=True)
    assert resp.status_code == 200 and "pending_handover" in resp.get_data(as_text=True)
    assert outbox(app)[0]["to"] == "jan@firma.cz"
    listing = client.get("/admin/handovers").get_data(as_text=True)
    assert "NB-0001" in listing and "Jan Novák" in listing
    assert "jan@firma.cz" in client.get("/admin/employees").get_data(as_text=True)
    assert "Jan Novák" in client.get("/admin/employees/jan@firma.cz").get_data(as_text=True)
    assert "asset.created" in client.get("/admin/audit").get_data(as_text=True)


def test_employee_sees_own_devices_and_confirms(app, client):
    aid = _seed(client)
    login(client, "admin@firma.cz")
    client.post(f"/admin/assets/{aid}/handover", data={"employee_email": "jan@firma.cz", "note": ""})
    login(client, "jan@firma.cz")
    home = client.get("/").get_data(as_text=True)
    assert "NB-0001" in home and "potvr" in home.lower()  # pending confirmation shown
    link = outbox(app)[0]["text"].split("http://testserver", 1)[1].split()[0]
    client.post(link, data={"action": "confirm"}, follow_redirects=True)
    home = client.get("/").get_data(as_text=True)
    assert "NB-0001" in home and "HP-" in home  # assigned device with protocol number
    pdf = client.get(f"/my/protocols/{outbox(app)[1]['attachments'][0]['filename']}")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    ret = client.post(f"/my/assets/{aid}/return", data={"note": "končím"}, follow_redirects=True)
    assert ret.status_code == 200 and "pending_return" in ret.get_data(as_text=True)


def test_employee_cannot_confirm_someone_elses_handover(app, client):
    aid = _seed(client)
    login(client, "admin@firma.cz")
    client.post(f"/admin/assets/{aid}/handover", data={"employee_email": "jan@firma.cz", "note": ""})
    link = outbox(app)[0]["text"].split("http://testserver", 1)[1].split()[0]
    login(client, "eva@firma.cz")
    assert client.post(link, data={"action": "confirm"}).status_code == 403


def test_unknown_employee_gets_a_friendly_page(client):
    login(client, "ghost@firma.cz")
    page = client.get("/")
    assert page.status_code == 200 and "evidenci" in page.get_data(as_text=True)


def test_decline_from_the_page(app, client):
    aid = _seed(client)
    login(client, "admin@firma.cz")
    client.post(f"/admin/assets/{aid}/handover", data={"employee_email": "jan@firma.cz", "note": ""})
    link = outbox(app)[0]["text"].split("http://testserver", 1)[1].split()[0]
    login(client, "jan@firma.cz")
    resp = client.post(link, data={"action": "decline", "reason": "nedostal jsem ho"}, follow_redirects=True)
    assert resp.status_code == 200
    assert api(client, "GET", f"/api/v1/assets/{aid}", key="test-api-key").get_json()["status"] == "in_stock"
