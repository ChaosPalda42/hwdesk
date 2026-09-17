import io

from tests.conftest import api, login


def test_invoices_api_and_web(app, client):
    inv = api(client, "POST", "/api/v1/invoices", json={"number": "FV-2026-0117", "supplier": "Alza", "issued_at": "2026-03-12", "total": 349900, "notes": "20× Latitude"})
    assert inv.status_code == 201, inv.get_data(as_text=True)
    iid = inv.get_json()["id"]
    assert api(client, "POST", "/api/v1/invoices", json={"number": "FV-2026-0117"}).status_code == 409
    ids = [api(client, "POST", "/api/v1/assets", json={"asset_tag": f"NB-{i}", "type": "notebook", "invoice_id": iid}).get_json()["id"] for i in range(2)]
    extra = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-9", "type": "notebook"}).get_json()["id"]
    assert api(client, "POST", f"/api/v1/invoices/{iid}/assets", json={"asset_ids": [extra]}).get_json()["attached"] == 1
    detail = api(client, "GET", f"/api/v1/invoices/{iid}").get_json()
    assert detail["number"] == "FV-2026-0117" and len(detail["assets"]) == 3
    up = api(client, "POST", f"/api/v1/invoices/{iid}/attachments", data={"kind": "invoice", "file": (io.BytesIO(b"%PDF-1.4 inv"), "FV-2026-0117.pdf", "application/pdf")}, content_type="multipart/form-data")
    assert up.status_code == 201
    assert api(client, "GET", f"/api/v1/assets/{ids[0]}").get_json()["invoice"]["number"] == "FV-2026-0117"
    listed = api(client, "GET", "/api/v1/invoices?q=0117").get_json()
    assert listed[0]["asset_count"] == 3 and listed[0]["attachment_count"] == 1

    login(client, "admin@firma.cz")
    page = client.get("/admin/invoices").get_data(as_text=True)
    assert "FV-2026-0117" in page and "Alza" in page
    detail_page = client.get(f"/admin/invoices/{iid}").get_data(as_text=True)
    assert "NB-0" in detail_page and "FV-2026-0117.pdf" in detail_page
    created = client.post("/admin/invoices/new", data={"number": "FV-2", "supplier": "Datart", "issued_at": "", "total": "1000", "currency": "CZK", "notes": ""}, follow_redirects=True)
    assert created.status_code == 200 and "FV-2" in created.get_data(as_text=True)
    asset_page = client.get(f"/admin/assets/{ids[0]}").get_data(as_text=True)
    assert "FV-2026-0117" in asset_page
    login(client, "jan@firma.cz")
    assert client.get("/admin/invoices").status_code == 403
