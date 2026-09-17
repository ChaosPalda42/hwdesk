from tests.conftest import api, login, outbox


def _employee(client, email="jan@firma.cz", name="Jan Novák"):
    return api(client, "POST", "/api/v1/hr/employees", json={"employees": [{"email": email, "display_name": name, "department": "IT", "manager_email": "", "hr_id": "1", "active": True}]})


def _asset(client, tag="NB-0001", type="notebook"):
    return api(client, "POST", "/api/v1/assets", json={"asset_tag": tag, "type": type, "brand": "Dell", "model": "L", "serial_number": "S", "purchase_date": "2026-01-01", "price": 1000, "notes": ""})


def test_assets_crud(client):
    created = _asset(client)
    assert created.status_code == 201 and created.get_json()["asset_tag"] == "NB-0001"
    aid = created.get_json()["id"]
    assert _asset(client).status_code == 409
    bad = api(client, "POST", "/api/v1/assets", json={"asset_tag": "X", "type": "spaceship"})
    assert bad.status_code == 400 and "type" in bad.get_json()["error"]
    assert api(client, "GET", f"/api/v1/assets/{aid}").get_json()["brand"] == "Dell"
    assert api(client, "GET", "/api/v1/assets/999").status_code == 404
    assert api(client, "PATCH", f"/api/v1/assets/{aid}", json={"brand": "DELL"}).get_json()["brand"] == "DELL"
    listed = api(client, "GET", "/api/v1/assets?status=in_stock&q=nb-").get_json()
    assert [a["asset_tag"] for a in listed] == ["NB-0001"]
    assert api(client, "POST", f"/api/v1/assets/{aid}/retire").get_json()["status"] == "retired"


def test_employees_and_hr_sync(client):
    resp = _employee(client)
    assert resp.status_code == 200 and resp.get_json()["created"] == 1
    listed = api(client, "GET", "/api/v1/employees").get_json()
    assert listed[0]["email"] == "jan@firma.cz"
    assert api(client, "GET", "/api/v1/employees/jan@firma.cz").get_json()["display_name"] == "Jan Novák"
    assert api(client, "GET", "/api/v1/employees/nobody@firma.cz").status_code == 404
    bad = api(client, "POST", "/api/v1/hr/employees", json={"employees": [{"display_name": "no email"}]})
    assert bad.status_code == 400
    csv = api(client, "POST", "/api/v1/hr/employees/csv", data="email;display_name\neva@firma.cz;Eva\n", content_type="text/csv")
    assert csv.status_code == 200 and csv.get_json()["created"] == 1


def test_handover_and_return_via_api(app, client):
    _employee(client)
    aid = _asset(client).get_json()["id"]
    started = api(client, "POST", "/api/v1/handovers", json={"asset_id": aid, "employee_email": "jan@firma.cz", "note": "s taškou"})
    assert started.status_code == 201, started.get_data(as_text=True)
    hid = started.get_json()["id"]
    assert started.get_json()["status"] == "pending"
    assert api(client, "POST", "/api/v1/handovers", json={"asset_id": aid, "employee_email": "jan@firma.cz"}).status_code == 409
    assert api(client, "GET", f"/api/v1/handovers/{hid}").get_json()["asset"]["asset_tag"] == "NB-0001"
    assert [h["id"] for h in api(client, "GET", "/api/v1/handovers?status=pending").get_json()] == [hid]

    # the employee confirms through the link from the e-mail
    link = outbox(app)[0]["text"].split("http://testserver", 1)[1].split()[0]
    login(client, "jan@firma.cz")
    page = client.get(link)
    assert page.status_code == 200 and "NB-0001" in page.get_data(as_text=True)
    done = client.post(link, data={"action": "confirm"}, follow_redirects=True)
    assert done.status_code == 200 and "potvrzen" in done.get_data(as_text=True).lower()
    assert api(client, "GET", f"/api/v1/assets/{aid}").get_json()["status"] == "assigned"
    assert api(client, "GET", f"/api/v1/handovers/{hid}").get_json()["status"] == "confirmed"
    pdf = api(client, "GET", f"/api/v1/handovers/{hid}/protocol.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")

    ret = api(client, "POST", "/api/v1/returns", json={"asset_id": aid, "note": "konec"})
    assert ret.status_code == 201 and ret.get_json()["kind"] == "return"
    link = outbox(app)[-1]["text"].split("http://testserver", 1)[1].split()[0]
    client.post(link, data={"action": "confirm"}, follow_redirects=True)
    assert api(client, "GET", f"/api/v1/assets/{aid}").get_json()["status"] == "in_stock"
    assert api(client, "POST", f"/api/v1/handovers/{hid}/cancel").status_code == 409


def test_cancel_pending_handover(client):
    _employee(client)
    aid = _asset(client).get_json()["id"]
    hid = api(client, "POST", "/api/v1/handovers", json={"asset_id": aid, "employee_email": "jan@firma.cz"}).get_json()["id"]
    assert api(client, "POST", f"/api/v1/handovers/{hid}/cancel").get_json()["status"] == "cancelled"
    assert api(client, "GET", f"/api/v1/assets/{aid}").get_json()["status"] == "in_stock"


def test_audit_endpoint(client):
    _asset(client)
    entries = api(client, "GET", "/api/v1/audit?limit=5").get_json()
    assert entries and entries[0]["action"] == "asset.created"
