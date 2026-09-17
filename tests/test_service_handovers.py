import json
from pathlib import Path

import pytest

from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository
from src.services.email_sender import EmailSender
from src.services.handover_service import HandoverError, HandoverService
from src.services.tokens import HandoverTokens


@pytest.fixture()
def ctx(conn, tmp_path):
    employees = EmployeeRepository(conn)
    assets = AssetRepository(conn)
    sender = EmailSender(mode="outbox", outbox_dir=str(tmp_path / "out"), sender="hw@f.cz", smtp={})
    service = HandoverService(
        handovers=HandoverRepository(conn),
        assignments=AssignmentRepository(conn),
        assets=assets,
        employees=employees,
        audit=AuditRepository(conn),
        email=sender,
        tokens=HandoverTokens(secret="s", max_age_hours=24),
        base_url="http://testserver",
        company="Firma",
        protocol_dir=str(tmp_path / "protocols"),
    )
    jan = employees.upsert(email="jan@f.cz", display_name="Jan Novák", department="IT", manager_email="", hr_id="")
    nb = assets.create(asset_tag="NB-1", type="notebook", brand="Dell", model="L", serial_number="S", purchase_date="", price=0, notes="")
    return service, jan, nb, assets, tmp_path


def _outbox(tmp_path):
    return [json.loads(p.read_text()) for p in sorted((tmp_path / "out").glob("*.json"))]


def test_handover_flow_sends_email_and_confirms(ctx):
    service, jan, nb, assets, tmp_path = ctx
    h = service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="s nabíječkou")
    assert h["status"] == "pending" and h["kind"] == "handover" and h["protocol_number"].startswith("HP-")
    assert assets.get(nb["id"])["status"] == "pending_handover"
    mail = _outbox(tmp_path)
    assert len(mail) == 1 and mail[0]["to"] == "jan@f.cz" and "NB-1" in mail[0]["text"]
    assert "http://testserver/handovers/confirm/" in mail[0]["text"]
    token = mail[0]["text"].split("/handovers/confirm/", 1)[1].split()[0]

    confirmed = service.confirm(token=token, actor_email="JAN@f.cz")
    assert confirmed["status"] == "confirmed" and confirmed["confirmed_at"]
    assert Path(confirmed["protocol_path"]).exists() and confirmed["protocol_path"].endswith(".pdf")
    assert assets.get(nb["id"])["status"] == "assigned"
    assert service.assignments.get_open_for_asset(nb["id"])["employee_id"] == jan["id"]
    # protocol copy to both parties
    mail = _outbox(tmp_path)
    assert len(mail) == 3 and {m["to"] for m in mail[1:]} == {"jan@f.cz", "admin@f.cz"}
    assert all(any(a["filename"].endswith(".pdf") for a in m["attachments"]) for m in mail[1:])


def test_confirm_requires_the_addressee(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    token = _outbox(tmp_path)[0]["text"].split("/handovers/confirm/", 1)[1].split()[0]
    with pytest.raises(HandoverError):
        service.confirm(token=token, actor_email="someone.else@f.cz")
    with pytest.raises(HandoverError):
        service.confirm(token="garbage", actor_email="jan@f.cz")
    assert assets.get(nb["id"])["status"] == "pending_handover"


def test_decline_and_cancel_release_the_asset(ctx):
    service, jan, nb, assets, tmp_path = ctx
    h = service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    token = _outbox(tmp_path)[0]["text"].split("/handovers/confirm/", 1)[1].split()[0]
    declined = service.decline(token=token, actor_email="jan@f.cz", reason="nemám ho")
    assert declined["status"] == "declined" and declined["decline_reason"] == "nemám ho"
    assert assets.get(nb["id"])["status"] == "in_stock"
    h2 = service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    assert service.cancel(actor="admin@f.cz", handover_id=h2["id"])["status"] == "cancelled"
    assert assets.get(nb["id"])["status"] == "in_stock"
    with pytest.raises(HandoverError):
        service.cancel(actor="admin@f.cz", handover_id=h["id"])  # not pending any more


def test_cannot_hand_over_an_unavailable_asset(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    with pytest.raises(HandoverError):
        service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    with pytest.raises(HandoverError):
        service.start_handover(actor="admin@f.cz", asset_id=999, employee_id=jan["id"], note="")
    with pytest.raises(HandoverError):
        service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=999, note="")


def _confirm_handover(service, tmp_path, index=0):
    token = _outbox(tmp_path)[index]["text"].split("/handovers/confirm/", 1)[1].split()[0]
    return service.confirm(token=token, actor_email="jan@f.cz")


def test_return_flow(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    _confirm_handover(service, tmp_path)
    r = service.start_return(actor="admin@f.cz", asset_id=nb["id"], note="konec smlouvy")
    assert r["kind"] == "return" and r["employee_id"] == jan["id"] and assets.get(nb["id"])["status"] == "pending_return"
    mail = _outbox(tmp_path)
    assert mail[-1]["to"] == "jan@f.cz" and "/handovers/confirm/" in mail[-1]["text"]
    token = mail[-1]["text"].split("/handovers/confirm/", 1)[1].split()[0]
    done = service.confirm(token=token, actor_email="jan@f.cz")
    assert done["status"] == "confirmed" and assets.get(nb["id"])["status"] == "in_stock"
    assert service.assignments.get_open_for_asset(nb["id"]) is None
    assert service.assignments.history_for_asset(nb["id"])[0]["return_id"] == r["id"]
    with pytest.raises(HandoverError):
        service.start_return(actor="admin@f.cz", asset_id=nb["id"], note="")  # nothing assigned


def test_employee_may_request_return_of_own_asset(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    _confirm_handover(service, tmp_path)
    r = service.request_return(employee_email="jan@f.cz", asset_id=nb["id"], note="odcházím")
    assert r["kind"] == "return" and r["created_by"] == "jan@f.cz"
    with pytest.raises(HandoverError):
        service.request_return(employee_email="other@f.cz", asset_id=nb["id"], note="")


def test_overview_for_employee(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    view = service.overview_for_employee(jan["id"])
    assert view["assigned"] == [] and [h["id"] for h in view["pending"]] and view["pending"][0]["asset"]["asset_tag"] == "NB-1"
    _confirm_handover(service, tmp_path)
    view = service.overview_for_employee(jan["id"])
    assert [a["asset"]["asset_tag"] for a in view["assigned"]] == ["NB-1"] and view["pending"] == []
    assert view["history"][0]["protocol_number"].startswith("HP-")


def test_expire_stale_handovers(ctx):
    service, jan, nb, assets, tmp_path = ctx
    service.start_handover(actor="admin@f.cz", asset_id=nb["id"], employee_id=jan["id"], note="")
    assert service.expire_stale(older_than_hours=0) == 1
    assert assets.get(nb["id"])["status"] == "in_stock"
    assert service.expire_stale(older_than_hours=0) == 0
