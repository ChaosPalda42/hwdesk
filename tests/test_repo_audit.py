from src.repositories.audit import AuditRepository


def test_record_and_list(conn):
    repo = AuditRepository(conn)
    first = repo.record(actor="admin@f.cz", action="asset.created", entity="asset", entity_id=1, details={"asset_tag": "NB-1"})
    repo.record(actor="system", action="handover.confirmed", entity="handover", entity_id=7, details={})
    assert first["id"] == 1 and first["details"] == {"asset_tag": "NB-1"}
    entries = repo.list_recent(limit=10)
    assert [e["action"] for e in entries] == ["handover.confirmed", "asset.created"]  # newest first
    assert [e["id"] for e in repo.list_for_entity("asset", 1)] == [1]
    assert repo.list_recent(limit=1)[0]["details"] == {}
