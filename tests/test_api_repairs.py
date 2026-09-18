from tests.conftest import api

def test_repairs_api_endpoints(client):
    # create an asset via existing API
    asset_resp = api(
        client,
        "POST",
        "/api/v1/assets",
        json={
            "asset_tag": "R-003",
            "type": "other",
            "brand": "Canon",
            "model": "iPF7500",
            "serial_number": "SN789",
            "purchase_date": "2023-03-15",
            "price": 250.0,
        },
    )
    assert asset_resp.status_code == 201
    asset = asset_resp.get_json()
    aid = asset["id"]

    # initially no repairs
    list_resp = api(client, "GET", f"/api/v1/assets/{aid}/repairs")
    assert list_resp.status_code == 200 and list_resp.get_json() == []

    # open a repair
    open_resp = api(
        client,
        "POST",
        f"/api/v1/assets/{aid}/repairs",
        json={
            "description": "Paper jam",
            "vendor": "PrintFix",
            "sent_at": "2024-03-05T10:00:00+00:00",
            "cost": 45.0,
        },
    )
    assert open_resp.status_code == 201
    repair = open_resp.get_json()
    rid = repair["id"]
    assert repair["description"] == "Paper jam"

    # close the repair
    close_resp = api(
        client,
        "POST",
        f"/api/v1/repairs/{rid}/close",
        json={
            "returned_at": "2024-03-10T15:30:00+00:00",
            "result": "Jam cleared, printer functional",
            "cost": 50.0,
        },
    )
    assert close_resp.status_code == 200
    closed = close_resp.get_json()
    assert closed["result"] == "Jam cleared, printer functional"

    # list again – should contain the (now closed) repair
    list2 = api(client, "GET", f"/api/v1/assets/{aid}/repairs")
    assert list2.status_code == 200 and any(r["id"] == rid for r in list2.get_json())
