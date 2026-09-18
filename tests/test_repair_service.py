from tests.conftest import conn

def test_repair_service_open_and_close(conn):
    from src.repositories.assets import AssetRepository
    from src.repositories.repairs import RepairRepository
    from src.repositories.audit import AuditRepository
    from src.services.repair_service import RepairService, RepairError

    assets = AssetRepository(conn)
    repairs = RepairRepository(conn)
    audit = AuditRepository(conn)

    # create an asset to repair
    asset = assets.create(
        asset_tag="R-002",
        type="monitor",
        brand="HP",
        model="EliteDisplay",
        serial_number="SN456",
        purchase_date="2022-05-01T00:00:00+00:00",
        price=300.0,
        notes="",
    )
    asset_id = asset["id"]

    service = RepairService(assets, repairs, audit)

    # open a repair
    opened = service.open_repair(
        actor="admin@firma.cz",
        asset_id=asset_id,
        description="Dead backlight",
        vendor="FixIt Ltd.",
        sent_at="2024-02-01T09:00:00+00:00",
        cost=120.0,
    )
    assert opened["description"] == "Dead backlight"
    repair_id = opened["id"]

    # audit should contain a record of the opening
    recent = audit.list_recent(limit=5)
    assert any(entry["action"] == "repair.opened" and entry["entity_id"] == repair_id for entry in recent)

    # close the repair
    closed = service.close_repair(
        actor="admin@firma.cz",
        repair_id=repair_id,
        returned_at="2024-02-10T14:45:00+00:00",
        result="Backlight replaced, works now",
        cost=130.0,
    )
    assert closed["result"] == "Backlight replaced, works now"

    recent = audit.list_recent(limit=5)
    assert any(entry["action"] == "repair.closed" and entry["entity_id"] == repair_id for entry in recent)

    # trying to close a non‑existent repair raises RepairError
    try:
        service.close_repair("admin@firma.cz", 9999, "2024-01-01T00:00:00+00:00", "none", 0.0)
        assert False, "Expected RepairError"
    except RepairError:
        pass
