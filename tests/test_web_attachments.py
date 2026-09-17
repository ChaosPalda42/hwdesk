import io

from tests.conftest import api, login


def test_upload_and_download_through_api_and_web(app, client):
    aid = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-1", "type": "notebook"}).get_json()["id"]
    up = api(client, "POST", f"/api/v1/assets/{aid}/attachments", data={"kind": "document", "file": (io.BytesIO(b"%PDF-1.4 x"), "faktura.pdf", "application/pdf")}, content_type="multipart/form-data")
    assert up.status_code == 201, up.get_data(as_text=True)
    att = up.get_json()
    listed = api(client, "GET", f"/api/v1/assets/{aid}/attachments").get_json()
    assert listed[0]["filename"] == "faktura.pdf" and listed[0]["kind"] == "document"
    down = api(client, "GET", f"/api/v1/attachments/{att['id']}")
    assert down.status_code == 200 and down.data.startswith(b"%PDF") and "faktura.pdf" in down.headers.get("Content-Disposition", "")
    assert api(client, "GET", "/api/v1/attachments/999").status_code == 404
    login(client, "jan@firma.cz")
    assert client.get(f"/admin/attachments/{att['id']}").status_code == 403
    login(client, "admin@firma.cz")
    assert client.get(f"/admin/attachments/{att['id']}").status_code == 200
    detail = client.get(f"/admin/assets/{aid}").get_data(as_text=True)
    assert "faktura.pdf" in detail
    web_up = client.post(f"/admin/assets/{aid}/attachments", data={"kind": "photo", "file": (io.BytesIO(b"\x89PNG"), "foto.png", "image/png")}, content_type="multipart/form-data", follow_redirects=True)
    assert web_up.status_code == 200 and "foto.png" in web_up.get_data(as_text=True)
    gone = client.post(f"/admin/attachments/{att['id']}/delete", follow_redirects=True)
    assert gone.status_code == 200 and "faktura.pdf" not in gone.get_data(as_text=True)
    assert api(client, "DELETE", f"/api/v1/attachments/{att['id']}").status_code == 404
