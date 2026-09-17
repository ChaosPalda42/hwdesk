from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository


def _seed(conn):
    e = EmployeeRepository(conn).upsert(email="jan@f.cz", display_name="Jan", department="", manager_email="", hr_id="")
    a = AssetRepository(conn).create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    return e, a


def test_handover_lifecycle(conn):
    e, a = _seed(conn)
    repo = HandoverRepository(conn)
    h = repo.create(kind="handover", asset_id=a["id"], employee_id=e["id"], created_by="admin@f.cz", protocol_number="HP-2026-000001", note="new laptop")
    assert h["status"] == "pending" and h["sent_at"] is None and h["protocol_number"] == "HP-2026-000001"
    assert repo.mark_sent(h["id"]) is True and repo.get(h["id"])["sent_at"]
    assert repo.set_status(h["id"], "confirmed", confirmed_at="2026-09-17T10:00:00+00:00", protocol_path="protocols/HP-2026-000001.pdf") is True
    got = repo.get(h["id"])
    assert got["status"] == "confirmed" and got["confirmed_at"].startswith("2026-09-17") and got["protocol_path"].endswith(".pdf")
    assert repo.set_status(h["id"], "declined", decline_reason="wrong device") is True
    assert repo.get(h["id"])["decline_reason"] == "wrong device"
    assert repo.get(999) is None and repo.set_status(999, "expired") is False


def test_next_protocol_number_is_per_year_sequence(conn):
    e, a = _seed(conn)
    repo = HandoverRepository(conn)
    assert repo.next_protocol_number(2026) == "HP-2026-000001"
    repo.create(kind="handover", asset_id=a["id"], employee_id=e["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    assert repo.next_protocol_number(2026) == "HP-2026-000002"
    assert repo.next_protocol_number(2027) == "HP-2027-000001"


def test_list_filters_and_pending_for_employee(conn):
    e, a = _seed(conn)
    repo = HandoverRepository(conn)
    h1 = repo.create(kind="handover", asset_id=a["id"], employee_id=e["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    h2 = repo.create(kind="return", asset_id=a["id"], employee_id=e["id"], created_by="x", protocol_number="HP-2026-000002", note="")
    repo.set_status(h1["id"], "confirmed", confirmed_at="2026-09-17T10:00:00+00:00", protocol_path="")
    assert [h["id"] for h in repo.list_all(status="pending")] == [h2["id"]]
    assert [h["id"] for h in repo.list_for_employee(e["id"])] == [h2["id"], h1["id"]]  # newest first
    assert [h["id"] for h in repo.list_pending_for_employee(e["id"])] == [h2["id"]]
    assert [h["id"] for h in repo.list_for_asset(a["id"])] == [h2["id"], h1["id"]]


def test_assignments_open_and_close(conn):
    e, a = _seed(conn)
    hrepo = HandoverRepository(conn)
    h = hrepo.create(kind="handover", asset_id=a["id"], employee_id=e["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    repo = AssignmentRepository(conn)
    asg = repo.open(asset_id=a["id"], employee_id=e["id"], handover_id=h["id"])
    assert asg["ended_at"] is None and repo.get_open_for_asset(a["id"])["id"] == asg["id"]
    assert [x["asset_id"] for x in repo.list_open_for_employee(e["id"])] == [a["id"]]
    r = hrepo.create(kind="return", asset_id=a["id"], employee_id=e["id"], created_by="x", protocol_number="HP-2026-000002", note="")
    assert repo.close(asg["id"], return_id=r["id"]) is True
    assert repo.get_open_for_asset(a["id"]) is None
    assert repo.list_open_for_employee(e["id"]) == []
    assert [x["id"] for x in repo.history_for_asset(a["id"])] == [asg["id"]]
    assert repo.get(asg["id"])["return_id"] == r["id"] and repo.close(asg["id"], return_id=r["id"]) is False
