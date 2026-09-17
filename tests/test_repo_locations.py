import sqlite3

import pytest

from src.repositories.locations import LocationRepository


def test_locations_crud(conn):
    locations = LocationRepository(conn)
    hq = locations.create("Praha – HQ", "Vodičkova 1", "")
    assert hq["id"] == 1 and locations.get(1)["name"] == "Praha – HQ"
    locations.create("Brno", "", "sklad")
    assert [l["name"] for l in locations.list_all()] == ["Brno", "Praha – HQ"]
    assert locations.update(1, name="Praha", address="Vodičkova 1", notes="")["name"] == "Praha"
    assert locations.get_by_name("praha")["id"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        locations.create("Praha", "", "")
    conn.execute("INSERT INTO assets (asset_tag, type, location_id) VALUES ('NB-1', 'notebook', 1)")
    conn.commit()
    assert locations.list_all()[1]["asset_count"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        locations.delete(1)  # still referenced
    assert locations.delete(2) is True and locations.delete(2) is False
