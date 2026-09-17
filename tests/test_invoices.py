import io
import sqlite3

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService, AssetValidationError
from tests.conftest import api, login


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


def test_invoices_api_and_web(app, client):
    inv = api(client, "POST", "/api/v1/invoices", json={"number": "FV-2026-0117", "supplier": "Alza", "issued_at": "2026-03-12", "total": 349900, "notes": "20× Latitude"})
    assert inv.status_code == 201, inv.get_data(as_text=True)
    iid = inv.get_json()["id"]
    assert api(client, "POST", "/api/v1/invoices", json={"number": "FV-2026-0117"}).status_code == 409
    ids = [api(client, "POST", "/api/v1/assets", json={"asset_tag": f"NB-{i}", "type": "notebook", "invoice_id": iid}).get_json()["id"] for i in range(2)]
    extra = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-9", "type": "notebook"}).get_json()["id"]
    assert api(client, "POST", f"/api/v1/invoices/{iid}/assets", json={"asset_ids": [extra]}).get_json()["attached"] == 1
    detail = api(client, "GET", f"/api/v1/invoices/{iid}").get_json()
    assert detail["number"] == "FV-2026-0117" and len(detail["assets"]) == 3
    up = api(client, "POST", f"/api/v1/invoices/{iid}/attachments", data={"kind": "invoice", "file": (io.BytesIO(b"%PDF-1.4 inv"), "FV-2026-0117.pdf", "application/pdf")}, content_type="multipart/form-data")
    assert up.status_code == 201
    assert api(client, "GET", f"/api/v1/assets/{ids[0]}").get_json()["invoice"]["number"] == "FV-2026-0117"
    listed = api(client, "GET", "/api/v1/invoices?q=0117").get_json()
    assert listed[0]["asset_count"] == 3 and listed[0]["attachment_count"] == 1

    login(client, "admin@firma.cz")
    page = client.get("/admin/invoices").get_data(as_text=True)
    assert "FV-2026-0117" in page and "Alza" in page
    detail_page = client.get(f"/admin/invoices/{iid}").get_data(as_text=True)
    assert "NB-0" in detail_page and "FV-2026-0117.pdf" in detail_page
    created = client.post("/admin/invoices/new", data={"number": "FV-2", "supplier": "Datart", "issued_at": "", "total": "1000", "currency": "CZK", "notes": ""}, follow_redirects=True)
    assert created.status_code == 200 and "FV-2" in created.get_data(as_text=True)
    asset_page = client.get(f"/admin/assets/{ids[0]}").get_data(as_text=True)
    assert "FV-2026-0117" in asset_page
    login(client, "jan@firma.cz")
    assert client.get("/admin/invoices").status_code == 403
