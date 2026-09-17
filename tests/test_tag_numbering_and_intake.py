import pytest

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService
from src.services.intake_service import IntakeService


def _service(conn, prefixes=None, pad=4):
    return AssetService(AssetRepository(conn), AuditRepository(conn), tags=TagRepository(conn), locations=LocationRepository(conn), invoices=InvoiceRepository(conn), tag_prefixes=prefixes or {"notebook": "NB", "monitor": "MO", "phone": "PH", "mouse": "MS", "keyboard": "KB", "other": "OT"}, tag_pad=pad)


def test_next_asset_tag_continues_the_sequence_per_prefix(conn):
    service = _service(conn)
    assert service.next_asset_tag("notebook") == "NB-0001"
    service.create(actor="a", asset_tag="NB-0007", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    assert service.next_asset_tag("notebook") == "NB-0008"
    assert service.next_asset_tag("monitor") == "MO-0001"
    assert service.next_asset_tag("dock") == "OT-0001"  # unknown type -> 'other' prefix
    generated = service.create(actor="a", asset_tag="", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    assert generated["asset_tag"] == "NB-0008"
    assert _service(conn, pad=6).next_asset_tag("notebook") == "NB-000009"


def test_intake_creates_a_batch_on_one_invoice(conn):
    service = _service(conn)
    intake = IntakeService(service, InvoiceRepository(conn), AuditRepository(conn))
    result = intake.create_batch(actor="a", type="notebook", brand="Dell", model="Latitude 5540", quantity=3, invoice_number="FV-2026-0117", supplier="Alza", unit_price=17495, location_id=None, tag_names=["Nákup 2026"], warranty_until="2029-03-12")
    assert [a["asset_tag"] for a in result["assets"]] == ["NB-0001", "NB-0002", "NB-0003"]
    assert result["invoice"]["number"] == "FV-2026-0117" and result["invoice"]["supplier"] == "Alza"
    assert all(a["invoice_id"] == result["invoice"]["id"] and a["price"] == 17495.0 and a["status"] == "in_stock" for a in result["assets"])
    assert [t["name"] for t in result["assets"][0]["tags"]] == ["Nákup 2026"]
    updated = intake.set_serials(actor="a", serials={result["assets"][0]["id"]: "5CG1", result["assets"][1]["id"]: "5CG2"})
    assert updated == 2 and service.get(result["assets"][0]["id"])["serial_number"] == "5CG1"
    with pytest.raises(ValueError):
        intake.create_batch(actor="a", type="notebook", brand="", model="", quantity=0, invoice_number="", supplier="", unit_price=0, location_id=None, tag_names=[], warranty_until="")
    with pytest.raises(ValueError):
        intake.create_batch(actor="a", type="notebook", brand="", model="", quantity=501, invoice_number="", supplier="", unit_price=0, location_id=None, tag_names=[], warranty_until="")
