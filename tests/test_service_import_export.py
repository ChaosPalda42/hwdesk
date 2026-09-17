from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService
from src.services.asset_import_export import export_assets_csv, import_assets_csv


def _service(conn):
    return AssetService(AssetRepository(conn), AuditRepository(conn), tags=TagRepository(conn), locations=LocationRepository(conn))


def test_export_round_trips_through_import(conn):
    service = _service(conn)
    loc = LocationRepository(conn).create("HQ", "", "")
    service.create(actor="a", asset_tag="NB-1", type="notebook", brand="Dell", model="L", serial_number="S1", purchase_date="2026-01-02", price=30000, notes="n", location_id=loc["id"], condition="new", warranty_until="2029-01-02", supplier="Alza", cost_center="IT", tag_names=["VIP", "Zápůjčka"])
    csv_text = export_assets_csv(AssetRepository(conn), TagRepository(conn))
    header = csv_text.splitlines()[0]
    for column in ("asset_tag", "type", "brand", "model", "serial_number", "status", "condition", "location", "tags", "holder_email", "warranty_until", "supplier", "cost_center", "invoice", "purchase_date", "price", "notes"):
        assert column in header
    assert "VIP|Zápůjčka" in csv_text and "HQ" in csv_text

    result = import_assets_csv(service, LocationRepository(conn), "a", csv_text.replace("NB-1", "NB-9"))
    assert result == {"created": 1, "updated": 0, "errors": []}
    imported = AssetRepository(conn).get_by_tag("NB-9")
    assert imported["location_id"] == loc["id"] and imported["supplier"] == "Alza"
    assert [t["name"] for t in TagRepository(conn).for_asset(imported["id"])] == ["VIP", "Zápůjčka"]


def test_import_updates_existing_creates_locations_and_reports_row_errors(conn):
    service = _service(conn)
    service.create(actor="a", asset_tag="NB-1", type="notebook", brand="Dell", model="L", serial_number="", purchase_date="", price=0, notes="")
    text = "asset_tag;type;brand;model;location;tags;condition\nNB-1;notebook;Dell;Latitude 7;Brno;Servis;worn\nMO-1;monitor;LG;27;;;\nBAD-1;spaceship;;;;;\n"
    result = import_assets_csv(service, LocationRepository(conn), "a", text)
    assert result["created"] == 1 and result["updated"] == 1 and len(result["errors"]) == 1 and result["errors"][0].startswith("řádek 4")
    nb = service.get(AssetRepository(conn).get_by_tag("NB-1")["id"])
    assert nb["model"] == "Latitude 7" and nb["condition"] == "worn" and [t["name"] for t in nb["tags"]] == ["Servis"]
    assert LocationRepository(conn).get_by_name("Brno") is not None and nb["location_id"] == LocationRepository(conn).get_by_name("Brno")["id"]
