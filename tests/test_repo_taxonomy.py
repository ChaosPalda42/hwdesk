import sqlite3

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository


def _asset(repo, tag, **kw):
    data = dict(asset_tag=tag, type="notebook", brand="Dell", model="L", serial_number="", purchase_date="", price=0, notes="")
    data.update(kw)
    return repo.create(**data)


def test_tags_crud_and_assignment(conn):
    tags = TagRepository(conn)
    assets = AssetRepository(conn)
    a = _asset(assets, "NB-1")
    b = _asset(assets, "NB-2")
    vip = tags.create("VIP", "purple")
    assert vip == {"id": 1, "name": "VIP", "color": "purple"}
    assert tags.get_by_name("vip")["id"] == 1  # case-insensitive
    with pytest.raises(sqlite3.IntegrityError):
        tags.create("VIP", "gray")
    with pytest.raises(ValueError):
        tags.create("X", "magenta")
    loan = tags.create("Zápůjčka", "yellow")
    assert tags.update(vip["id"], name="VIP klient", color="red")["color"] == "red"
    assert [t["name"] for t in tags.list_all()] == ["VIP klient", "Zápůjčka"]
    assert tags.assign(a["id"], vip["id"]) is True and tags.assign(a["id"], vip["id"]) is False  # idempotent
    tags.assign(a["id"], loan["id"])
    tags.assign(b["id"], loan["id"])
    assert [t["name"] for t in tags.for_asset(a["id"])] == ["VIP klient", "Zápůjčka"]
    bulk = tags.for_assets([a["id"], b["id"]])
    assert [t["name"] for t in bulk[b["id"]]] == ["Zápůjčka"] and len(bulk[a["id"]]) == 2
    assert sorted(tags.asset_ids_with(loan["id"])) == [a["id"], b["id"]]
    assert tags.unassign(a["id"], vip["id"]) is True and tags.unassign(a["id"], vip["id"]) is False
    assert tags.set_for_asset(b["id"], [vip["id"]]) is None and [t["id"] for t in tags.for_asset(b["id"])] == [vip["id"]]
    assert tags.list_all()[0]["asset_count"] == 1  # VIP klient on b
    assert tags.delete(vip["id"]) is True and tags.for_asset(b["id"]) == [] and tags.delete(999) is False


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
    assets = AssetRepository(conn)
    _asset(assets, "NB-1", location_id=1)
    assert locations.list_all()[1]["asset_count"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        locations.delete(1)  # still referenced
    assert locations.delete(2) is True and locations.delete(2) is False
