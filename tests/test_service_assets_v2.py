import pytest

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService, AssetValidationError


@pytest.fixture()
def service(conn):
    return AssetService(AssetRepository(conn), AuditRepository(conn), tags=TagRepository(conn), locations=LocationRepository(conn))


def test_create_with_taxonomy_and_validation(service, conn):
    loc = LocationRepository(conn).create("HQ", "", "")
    a = service.create(actor="a", asset_tag="NB-1", type="notebook", brand="Dell", model="L", serial_number="", purchase_date="", price=0, notes="", location_id=loc["id"], condition="new", warranty_until="2029-01-01", supplier="Alza", cost_center="IT", tag_names=["VIP", "Zápůjčka"])
    assert a["condition"] == "new" and a["location_id"] == loc["id"]
    assert [t["name"] for t in a["tags"]] == ["VIP", "Zápůjčka"]
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="NB-2", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", condition="shiny")
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="NB-3", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", warranty_until="soon")
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="NB-4", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", location_id=999)


def test_update_tags_and_get_includes_tags(service, conn):
    a = service.create(actor="a", asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    updated = service.update(actor="a", asset_id=a["id"], tag_names=["Servis"], condition="worn")
    assert [t["name"] for t in updated["tags"]] == ["Servis"] and updated["condition"] == "worn"
    assert [t["name"] for t in service.get(a["id"])["tags"]] == ["Servis"]
    assert service.update(actor="a", asset_id=a["id"], tag_names=[])["tags"] == []


def test_bulk_tag(service, conn):
    a = service.create(actor="a", asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    b = service.create(actor="a", asset_tag="NB-2", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    assert service.bulk_tag(actor="a", asset_ids=[a["id"], b["id"]], tag_name="Audit 2026", remove=False) == 2
    assert [t["name"] for t in service.get(b["id"])["tags"]] == ["Audit 2026"]
    assert service.bulk_tag(actor="a", asset_ids=[a["id"]], tag_name="Audit 2026", remove=True) == 1
    assert service.get(a["id"])["tags"] == []
