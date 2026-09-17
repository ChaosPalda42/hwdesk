import sqlite3

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository


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



def test_new_columns_round_trip(conn):
    repo = AssetRepository(conn)
    loc = LocationRepository(conn).create("HQ", "", "")
    a = _asset(repo, "NB-1", location_id=loc["id"], condition="new", supplier="Alza", warranty_until="2029-03-12", cost_center="IT-100")
    assert a["location_id"] == loc["id"] and a["condition"] == "new" and a["supplier"] == "Alza" and a["warranty_until"] == "2029-03-12"
    assert a["cost_center"] == "IT-100" and a["invoice_id"] is None and a["updated_at"]
    b = _asset(repo, "NB-2")
    assert b["condition"] == "good" and b["location_id"] is None
    updated = repo.update(b["id"], condition="worn", location_id=loc["id"], warranty_until="2027-01-01")
    assert updated["condition"] == "worn" and updated["location_id"] == loc["id"]
    assert repo.update(b["id"], location_id=None)["location_id"] is None


def test_filtering_sorting_and_holder(conn):
    repo = AssetRepository(conn)
    tags = TagRepository(conn)
    loc = LocationRepository(conn).create("HQ", "", "")
    emp = EmployeeRepository(conn).upsert(email="jan@f.cz", display_name="Jan", department="", manager_email="", hr_id="")
    nb = _asset(repo, "NB-1", location_id=loc["id"], warranty_until="2026-10-01")
    mo = _asset(repo, "MO-1", type="monitor", brand="LG", model="27UK", warranty_until="2028-01-01")
    ph = _asset(repo, "PH-1", type="phone", brand="Apple", model="iPhone")
    vip = tags.create("VIP", "purple")
    tags.assign(nb["id"], vip["id"])
    h = HandoverRepository(conn).create(kind="handover", asset_id=nb["id"], employee_id=emp["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    AssignmentRepository(conn).open(asset_id=nb["id"], employee_id=emp["id"], handover_id=h["id"])
    repo.set_status(nb["id"], "assigned")

    assert [a["asset_tag"] for a in repo.search_assets()] == ["MO-1", "NB-1", "PH-1"]
    assert [a["asset_tag"] for a in repo.search_assets(sort="type")] == ["MO-1", "NB-1", "PH-1"]
    assert [a["asset_tag"] for a in repo.search_assets(sort="-asset_tag")] == ["PH-1", "NB-1", "MO-1"]
    assert [a["asset_tag"] for a in repo.search_assets(tag_id=vip["id"])] == ["NB-1"]
    assert [a["asset_tag"] for a in repo.search_assets(location_id=loc["id"])] == ["NB-1"]
    assert [a["asset_tag"] for a in repo.search_assets(employee_id=emp["id"])] == ["NB-1"]
    assert [a["asset_tag"] for a in repo.search_assets(status="in_stock", type="phone")] == ["PH-1"]
    assert [a["asset_tag"] for a in repo.search_assets(q="27uk")] == ["MO-1"]
    assert [a["asset_tag"] for a in repo.search_assets(warranty_before="2027-01-01")] == ["NB-1"]
    rows = repo.search_assets()
    nb_row = next(r for r in rows if r["asset_tag"] == "NB-1")
    assert nb_row["holder_email"] == "jan@f.cz" and nb_row["holder_name"] == "Jan" and nb_row["location_name"] == "HQ"
    assert next(r for r in rows if r["asset_tag"] == "MO-1")["holder_email"] is None
    assert repo.count_by("status") == {"assigned": 1, "in_stock": 2}
    assert repo.count_by("type") == {"monitor": 1, "notebook": 1, "phone": 1}
