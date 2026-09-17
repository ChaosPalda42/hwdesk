import pytest

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService, AssetValidationError


def test_asset_service_links_invoice_by_id_or_number(conn):
    invoices = InvoiceRepository(conn)
    service = AssetService(AssetRepository(conn), AuditRepository(conn), tags=TagRepository(conn), locations=LocationRepository(conn), invoices=invoices)
    inv = invoices.create(number="FV-1", supplier="Alza", issued_at="", total=0, currency="CZK", notes="", created_by="a")
    a = service.create(actor="a", asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", invoice_id=inv["id"])
    assert a["invoice_id"] == inv["id"] and a["invoice"]["number"] == "FV-1"
    b = service.create(actor="a", asset_tag="NB-2", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", invoice_number="FV-2")
    assert b["invoice"]["number"] == "FV-2" and invoices.get_by_number("FV-2")["created_by"] == "a"  # created on the fly
    with pytest.raises(AssetValidationError):
        service.create(actor="a", asset_tag="NB-3", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", invoice_id=999)
    assert service.update(actor="a", asset_id=a["id"], invoice_id=None)["invoice"] is None
    assert service.attach_invoice(actor="a", asset_ids=[a["id"], b["id"]], invoice_id=inv["id"]) == 2
    assert service.get(b["id"])["invoice"]["id"] == inv["id"]
