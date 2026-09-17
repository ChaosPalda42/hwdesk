from tests.conftest import api, login


def test_label_pages_and_short_link(app, client):
    aid = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-0042", "type": "notebook", "brand": "Dell", "model": "Latitude"}).get_json()["id"]
    login(client, "admin@firma.cz")
    sheet = client.get(f"/admin/labels?ids={aid}")
    assert sheet.status_code == 200 and "NB-0042" in sheet.get_data(as_text=True) and "<svg" in sheet.get_data(as_text=True)
    assert client.get("/admin/labels?ids=").status_code == 200  # empty selection is a page, not an error
    zpl = client.get(f"/admin/labels/zpl?ids={aid}")
    assert zpl.status_code == 200 and zpl.get_data(as_text=True).startswith("^XA") and zpl.mimetype == "text/plain"
    no_printer = client.post("/admin/labels/print", data={"ids": str(aid)}, follow_redirects=True)
    assert "LABEL_PRINTER_HOST" in no_printer.get_data(as_text=True)
    resp = client.get("/a/NB-0042")
    assert resp.status_code in (302, 303) and resp.headers["Location"].endswith(f"/admin/assets/{aid}")
    login(client, "jan@firma.cz")
    assert client.get("/a/NB-0042").status_code in (302, 303, 403, 404)
