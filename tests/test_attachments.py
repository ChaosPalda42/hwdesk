import io

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.attachments import AttachmentRepository
from src.repositories.audit import AuditRepository
from src.services.attachment_service import AttachmentError, AttachmentService
from tests.conftest import api, login


def test_repository(conn):
    a = AssetRepository(conn).create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    repo = AttachmentRepository(conn)
    f = repo.create(owner_type="asset", owner_id=a["id"], kind="document", filename="faktura 17.pdf", stored_name="1-abc.pdf", mime_type="application/pdf", size=1234, uploaded_by="a@f.cz")
    assert f["id"] == 1 and f["kind"] == "document" and f["owner_type"] == "asset" and f["uploaded_at"]
    assert [x["filename"] for x in repo.list_for("asset", a["id"])] == ["faktura 17.pdf"] and repo.list_for("invoice", a["id"]) == []
    assert repo.get(1)["stored_name"] == "1-abc.pdf" and repo.get(9) is None
    assert repo.delete(1) is True and repo.delete(1) is False


def test_service_stores_validates_and_deletes(conn, tmp_path):
    a = AssetRepository(conn).create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    service = AttachmentService(AttachmentRepository(conn), AuditRepository(conn), directory=str(tmp_path / "att"), max_bytes=1000, owner_exists=lambda owner_type, owner_id: owner_type == "asset" and AssetRepository(conn).get(owner_id) is not None)
    stored = service.store(actor="a@f.cz", owner_type="asset", owner_id=a["id"], kind="document", filename="../faktura.pdf", mime_type="application/pdf", data=b"%PDF-1.4 test")
    assert stored["filename"] == "faktura.pdf" and stored["size"] == 13 and (tmp_path / "att" / stored["stored_name"]).read_bytes() == b"%PDF-1.4 test"
    assert stored["stored_name"].endswith(".pdf") and "/" not in stored["stored_name"]
    path = service.path_for(stored["id"])
    assert path.endswith(stored["stored_name"])
    with pytest.raises(AttachmentError):
        service.store(actor="a", owner_type="asset", owner_id=a["id"], kind="document", filename="x.exe", mime_type="application/x-msdownload", data=b"MZ")
    with pytest.raises(AttachmentError):
        service.store(actor="a", owner_type="asset", owner_id=a["id"], kind="photo", filename="big.png", mime_type="image/png", data=b"0" * 1001)
    with pytest.raises(AttachmentError):
        service.store(actor="a", owner_type="asset", owner_id=999, kind="document", filename="f.pdf", mime_type="application/pdf", data=b"%PDF")
    with pytest.raises(AttachmentError):
        service.store(actor="a", owner_type="asset", owner_id=a["id"], kind="weird", filename="f.pdf", mime_type="application/pdf", data=b"%PDF")
    assert service.delete(actor="a", attachment_id=stored["id"]) is True
    assert not (tmp_path / "att" / stored["stored_name"]).exists()
    actions = [e["action"] for e in AuditRepository(conn).list_for_entity("asset", a["id"])]
    assert "attachment.added" in actions and "attachment.deleted" in actions


def test_upload_and_download_through_api_and_web(app, client):
    aid = api(client, "POST", "/api/v1/assets", json={"asset_tag": "NB-1", "type": "notebook"}).get_json()["id"]
    up = api(client, "POST", f"/api/v1/assets/{aid}/attachments", data={"kind": "document", "file": (io.BytesIO(b"%PDF-1.4 x"), "faktura.pdf", "application/pdf")}, content_type="multipart/form-data")
    assert up.status_code == 201, up.get_data(as_text=True)
    att = up.get_json()
    listed = api(client, "GET", f"/api/v1/assets/{aid}/attachments").get_json()
    assert listed[0]["filename"] == "faktura.pdf" and listed[0]["kind"] == "document"
    down = api(client, "GET", f"/api/v1/attachments/{att['id']}")
    assert down.status_code == 200 and down.data.startswith(b"%PDF") and "faktura.pdf" in down.headers.get("Content-Disposition", "")
    assert api(client, "GET", "/api/v1/attachments/999").status_code == 404
    login(client, "jan@firma.cz")
    assert client.get(f"/admin/attachments/{att['id']}").status_code == 403
    login(client, "admin@firma.cz")
    assert client.get(f"/admin/attachments/{att['id']}").status_code == 200
    detail = client.get(f"/admin/assets/{aid}").get_data(as_text=True)
    assert "faktura.pdf" in detail
    web_up = client.post(f"/admin/assets/{aid}/attachments", data={"kind": "photo", "file": (io.BytesIO(b"\x89PNG"), "foto.png", "image/png")}, content_type="multipart/form-data", follow_redirects=True)
    assert web_up.status_code == 200 and "foto.png" in web_up.get_data(as_text=True)
    gone = client.post(f"/admin/attachments/{att['id']}/delete", follow_redirects=True)
    assert gone.status_code == 200 and "faktura.pdf" not in gone.get_data(as_text=True)
    assert api(client, "DELETE", f"/api/v1/attachments/{att['id']}").status_code == 404
