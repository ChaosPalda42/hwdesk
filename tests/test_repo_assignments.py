from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository


def _seed(conn):
    e = EmployeeRepository(conn).upsert(email="jan@f.cz", display_name="Jan", department="", manager_email="", hr_id="")
    a = AssetRepository(conn).create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    return e, a


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
