from tests.conftest import conn

def test_repairs_repository_flow(conn):
    # create an asset first (required foreign key)
    from src.repositories.assets import AssetRepository
    assets = AssetRepository(conn)
    asset = assets.create(
        asset_tag="R-001",
        type="notebook",
        brand="Dell",
        model="XPS13",
        serial_number="SN123",
        purchase_date="2023-01-01T00:00:00+00:00",
        price=1500.0,
        notes="",
    )
    asset_id = asset["id"]

    # now test RepairRepository
    from src.repositories.repairs import RepairRepository
    repairs = RepairRepository(conn)

    repair = repairs.create(
        asset_id=asset_id,
        description="Screen cracked",
        vendor="RepairCo",
        sent_at="2024-01-10T12:00:00+00:00",
        cost=200.0,
        created_by="admin@firma.cz",
    )
    assert repair["id"] > 0
    assert repair["asset_id"] == asset_id
    assert repair["description"] == "Screen cracked"
    assert repair["returned_at"] == ""

    fetched = repairs.get(repair["id"])
    assert fetched == repair

    for_asset = repairs.list_for_asset(asset_id)
    assert isinstance(for_asset, list) and any(r["id"] == repair["id"] for r in for_asset)

    open_list = repairs.list_open()
    assert any(r["id"] == repair["id"] for r in open_list)

    closed = repairs.close(
        repair_id=repair["id"],
        returned_at="2024-01-20T15:30:00+00:00",
        result="Repaired, new screen installed",
        cost=210.0,
    )
    assert closed["returned_at"] == "2024-01-20T15:30:00+00:00"
    assert closed["result"] == "Repaired, new screen installed"
    assert closed["cost"] == 210.0

    # after closing it should disappear from open list
    assert not any(r["id"] == repair["id"] for r in repairs.list_open())
