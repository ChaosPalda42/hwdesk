import pytest

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.services.asset_service import AssetService, AssetValidationError, DuplicateAssetTag


@pytest.fixture()
def service(conn):
    return AssetService(AssetRepository(conn), AuditRepository(conn))


def test_create_validates_and_audits(service, conn):
    a = service.create(actor="admin@f.cz", asset_tag=" nb-0001 ", type="notebook", brand="Dell", model="L", serial_number="S", purchase_date="2026-01-01", price="32000", notes="")
    assert a["asset_tag"] == "NB-0001" and a["price"] == 32000.0
    assert AuditRepository(conn).list_for_entity("asset", a["id"])[0]["action"] == "asset.created"
    with pytest.raises(DuplicateAssetTag):
        service.create(actor="a", asset_tag="NB-0001", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="X-1", type="spaceship", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="X-2", type="mouse", brand="", model="", serial_number="", purchase_date="not-a-date", price=0, notes="")


def test_update_retire_and_lost(service, conn):
    a = service.create(actor="a", asset_tag="MO-1", type="monitor", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    assert service.update(actor="a", asset_id=a["id"], brand="LG")["brand"] == "LG"
    assert service.retire(actor="a", asset_id=a["id"])["status"] == "retired"
    assert service.mark_lost(actor="a", asset_id=a["id"])["status"] == "lost"
    actions = [e["action"] for e in AuditRepository(conn).list_for_entity("asset", a["id"])]
    assert "asset.retired" in actions and "asset.lost" in actions
    assert service.get(999) is None


def test_retire_refuses_an_assigned_asset(service, conn):
    a = service.create(actor="a", asset_tag="NB-2", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    AssetRepository(conn).set_status(a["id"], "assigned")
    with pytest.raises(AssetValidationError):
        service.retire(actor="a", asset_id=a["id"])
