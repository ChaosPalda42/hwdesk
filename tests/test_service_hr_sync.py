import json

from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository
from src.services.hr_sync import HrSyncService


def test_sync_upserts_and_reports_offboarded(conn):
    employees = EmployeeRepository(conn)
    assets = AssetRepository(conn)
    service = HrSyncService(employees, assets, AuditRepository(conn))
    first = service.sync(actor="api:hr", records=[
        {"email": "Jan@f.cz", "display_name": "Jan", "department": "IT", "manager_email": "", "hr_id": "1", "active": True},
        {"email": "eva@f.cz", "display_name": "Eva", "department": "HR", "manager_email": "jan@f.cz", "hr_id": "2", "active": True},
    ])
    assert first == {"created": 2, "updated": 0, "deactivated": 0, "offboarding": []}
    second = service.sync(actor="api:hr", records=[
        {"email": "jan@f.cz", "display_name": "Jan Novák", "department": "IT", "manager_email": "", "hr_id": "1", "active": True},
        {"email": "eva@f.cz", "display_name": "Eva", "department": "HR", "manager_email": "", "hr_id": "2", "active": False},
    ])
    assert second["created"] == 0 and second["updated"] == 1 and second["deactivated"] == 1
    assert employees.get_by_email("eva@f.cz")["active"] is False
    assert employees.get_by_email("jan@f.cz")["display_name"] == "Jan Novák"


def test_offboarding_lists_assets_still_held(conn):
    employees = EmployeeRepository(conn)
    assets = AssetRepository(conn)
    service = HrSyncService(employees, assets, AuditRepository(conn))
    service.sync(actor="api:hr", records=[{"email": "eva@f.cz", "display_name": "Eva", "department": "", "manager_email": "", "hr_id": "2", "active": True}])
    eva = employees.get_by_email("eva@f.cz")
    nb = assets.create(asset_tag="NB-9", type="notebook", brand="", model="", serial_number="", purchase_date="", price=0, notes="")
    from src.repositories.assignments import AssignmentRepository
    from src.repositories.handovers import HandoverRepository
    h = HandoverRepository(conn).create(kind="handover", asset_id=nb["id"], employee_id=eva["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    AssignmentRepository(conn).open(asset_id=nb["id"], employee_id=eva["id"], handover_id=h["id"])
    assets.set_status(nb["id"], "assigned")
    result = service.sync(actor="api:hr", records=[{"email": "eva@f.cz", "display_name": "Eva", "department": "", "manager_email": "", "hr_id": "2", "active": False}])
    assert result["offboarding"] == [{"email": "eva@f.cz", "asset_tags": ["NB-9"]}]


def test_parse_csv(conn):
    service = HrSyncService(EmployeeRepository(conn), AssetRepository(conn), AuditRepository(conn))
    rows = service.parse_csv("email;display_name;department;manager_email;hr_id;active\njan@f.cz;Jan;IT;;1;1\neva@f.cz;Eva;HR;jan@f.cz;2;0\n")
    assert rows[0] == {"email": "jan@f.cz", "display_name": "Jan", "department": "IT", "manager_email": "", "hr_id": "1", "active": True}
    assert rows[1]["active"] is False
    rows = service.parse_csv("email,display_name\nx@f.cz,X\n")
    assert rows == [{"email": "x@f.cz", "display_name": "X", "department": "", "manager_email": "", "hr_id": "", "active": True}]
