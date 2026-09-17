import pytest

from src.repositories.assets import AssetRepository
from src.repositories.attachments import AttachmentRepository
from src.repositories.audit import AuditRepository
from src.services.attachment_service import AttachmentError, AttachmentService


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
