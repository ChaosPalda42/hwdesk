import sqlite3

import pytest

from src.repositories.assets import AssetRepository


def _asset(repo, tag="NB-0001", **kw):
    data = dict(asset_tag=tag, type="notebook", brand="Dell", model="Latitude 5540", serial_number="SN1", purchase_date="2026-01-15", price=32000.0, notes="")
    data.update(kw)
    return repo.create(**data)


def test_create_get_update(conn):
    repo = AssetRepository(conn)
    a = _asset(repo)
    assert a["id"] == 1 and a["status"] == "in_stock" and a["price"] == 32000.0
    assert repo.get(a["id"])["asset_tag"] == "NB-0001"
    assert repo.get_by_tag("nb-0001")["id"] == a["id"]
    updated = repo.update(a["id"], brand="DELL", notes="stickers")
    assert updated["brand"] == "DELL" and updated["notes"] == "stickers"
    assert repo.update(999, brand="x") is None


def test_duplicate_tag_raises(conn):
    repo = AssetRepository(conn)
    _asset(repo)
    with pytest.raises(sqlite3.IntegrityError):
        _asset(repo)


def test_status_and_filters(conn):
    repo = AssetRepository(conn)
    a = _asset(repo, "NB-0001")
    b = _asset(repo, "MO-0001", type="monitor", model="27UK850")
    assert repo.set_status(a["id"], "assigned") is True
    assert repo.get(a["id"])["status"] == "assigned"
    assert [x["asset_tag"] for x in repo.list_all(status="in_stock")] == ["MO-0001"]
    assert [x["asset_tag"] for x in repo.list_all(type="notebook")] == ["NB-0001"]
    assert [x["asset_tag"] for x in repo.search("lati")] == ["NB-0001"]
    assert [x["asset_tag"] for x in repo.search("mo-")] == ["MO-0001"]
    assert repo.set_status(999, "retired") is False
    with pytest.raises(ValueError):
        repo.set_status(b["id"], "nonsense")
