from src.repositories.assets import AssetRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository
from src.services.dashboard_service import DashboardService


def test_dashboard_stats(conn):
    assets = AssetRepository(conn)
    emp = EmployeeRepository(conn).upsert(email="jan@f.cz", display_name="Jan", department="", manager_email="", hr_id="")
    a = assets.create(asset_tag="NB-1", type="notebook", brand="", model="", serial_number="", purchase_date="", price=30000, notes="", warranty_until="2026-10-01")
    assets.create(asset_tag="MO-1", type="monitor", brand="", model="", serial_number="", purchase_date="", price=5000, notes="", warranty_until="2030-01-01")
    assets.set_status(a["id"], "pending_handover")
    HandoverRepository(conn).create(kind="handover", asset_id=a["id"], employee_id=emp["id"], created_by="x", protocol_number="HP-2026-000001", note="")
    AuditRepository(conn).record(actor="x", action="asset.created", entity="asset", entity_id=1, details={})
    stats = DashboardService(assets, HandoverRepository(conn), AuditRepository(conn), EmployeeRepository(conn)).stats(today="2026-09-17", warranty_days=90)
    assert stats["totals"] == {"assets": 2, "value": 35000.0, "employees": 1}
    assert stats["by_status"]["pending_handover"] == 1 and stats["by_type"]["monitor"] == 1
    assert [h["protocol_number"] for h in stats["pending_handovers"]] == ["HP-2026-000001"]
    assert stats["pending_handovers"][0]["asset"]["asset_tag"] == "NB-1" and stats["pending_handovers"][0]["employee"]["email"] == "jan@f.cz"
    assert [w["asset_tag"] for w in stats["warranty_expiring"]] == ["NB-1"]
    assert stats["recent_activity"][0]["action"] == "asset.created"
