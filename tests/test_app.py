def test_health_and_static(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    assert client.get("/static/style.css").status_code == 200
