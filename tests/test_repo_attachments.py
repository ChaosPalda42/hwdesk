from src.repositories.assets import AssetRepository
from src.repositories.attachments import AttachmentRepository


def test_repository(conn):
    a = AssetRepository(conn).create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    repo = AttachmentRepository(conn)
    f = repo.create(owner_type="asset", owner_id=a["id"], kind="document", filename="faktura 17.pdf", stored_name="1-abc.pdf", mime_type="application/pdf", size=1234, uploaded_by="a@f.cz")
    assert f["id"] == 1 and f["kind"] == "document" and f["owner_type"] == "asset" and f["uploaded_at"]
    assert [x["filename"] for x in repo.list_for("asset", a["id"])] == ["faktura 17.pdf"] and repo.list_for("invoice", a["id"]) == []
    assert repo.get(1)["stored_name"] == "1-abc.pdf" and repo.get(9) is None
    assert repo.delete(1) is True and repo.delete(1) is False
