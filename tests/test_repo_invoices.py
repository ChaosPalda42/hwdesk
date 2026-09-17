import sqlite3

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.invoices import InvoiceRepository


def test_invoice_repository(conn):
    repo = InvoiceRepository(conn)
    inv = repo.create(number="FV-2026-0117", supplier="Alza", issued_at="2026-03-12", total=349900.0, currency="CZK", notes="20× Latitude", created_by="a@f.cz")
    assert inv["id"] == 1 and inv["total"] == 349900.0 and inv["created_at"]
    assert repo.get_by_number("fv-2026-0117")["id"] == 1
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(number="FV-2026-0117", supplier="", issued_at="", total=0, currency="CZK", notes="", created_by="")
    assets = AssetRepository(conn)
    for i in range(3):
        assets.create(asset_tag=f"NB-{i}", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="", invoice_id=1)
    listed = repo.list_all()
    assert listed[0]["asset_count"] == 3
    assert repo.update(1, supplier="Alza.cz", total=350000)["supplier"] == "Alza.cz"
    assert [a["asset_tag"] for a in assets.search_assets(invoice_id=1)] == ["NB-0", "NB-1", "NB-2"]
    assert [x["number"] for x in repo.search("0117")] == ["FV-2026-0117"]
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete(1)  # still referenced
    assets.update(1, invoice_id=None); assets.update(2, invoice_id=None); assets.update(3, invoice_id=None)
    assert repo.delete(1) is True
