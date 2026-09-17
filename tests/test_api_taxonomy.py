from tests.conftest import api


def test_tags_and_locations_api(client):
    t = api(client, "POST", "/api/v1/tags", json={"name": "VIP", "color": "purple"})
    assert t.status_code == 201 and t.get_json()["color"] == "purple"
    assert api(client, "POST", "/api/v1/tags", json={"name": "VIP"}).status_code == 409
    assert api(client, "POST", "/api/v1/tags", json={"name": "X", "color": "pink"}).status_code == 400
    assert [x["name"] for x in api(client, "GET", "/api/v1/tags").get_json()] == ["VIP"]
    tid = t.get_json()["id"]
    assert api(client, "PATCH", f"/api/v1/tags/{tid}", json={"color": "red"}).get_json()["color"] == "red"
    l = api(client, "POST", "/api/v1/locations", json={"name": "HQ", "address": "Praha"})
    assert l.status_code == 201 and api(client, "GET", "/api/v1/locations").get_json()[0]["name"] == "HQ"
    a = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-1", "type": "notebook", "location_id": l.get_json()["id"], "tags": ["VIP", "Nový"], "condition": "new"})
    assert a.status_code == 201, a.get_data(as_text=True)
    assert [x["name"] for x in a.get_json()["tags"]] == ["Nový", "VIP"] or [x["name"] for x in a.get_json()["tags"]] == ["VIP", "Nový"]
    assert api(client, "GET", "/api/v1/assets?tag=VIP").get_json()[0]["asset_tag"] == "NB-1"
    assert api(client, "GET", "/api/v1/assets?location_id=1").get_json()[0]["location_name"] == "HQ"
    assert api(client, "DELETE", f"/api/v1/tags/{tid}").status_code == 204
    assert api(client, "DELETE", "/api/v1/locations/1").status_code == 409  # referenced
    exported = api(client, "GET", "/api/v1/assets/export.csv")
    assert exported.status_code == 200 and "NB-1" in exported.get_data(as_text=True)
    imported = api(client, "POST", "/api/v1/assets/import.csv", data="asset_tag;type;brand\nMO-1;monitor;LG\n", content_type="text/csv")
    assert imported.status_code == 200 and imported.get_json()["created"] == 1
    assert api(client, "GET", "/api/v1/dashboard").get_json()["totals"]["assets"] == 2
