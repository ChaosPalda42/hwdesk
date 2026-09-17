import json
from pathlib import Path

import pytest

from src.services.email_sender import EmailSender
from src.services.protocol_pdf import render_protocol_pdf
from src.services.tokens import HandoverTokens


def test_outbox_sender_writes_json(tmp_path):
    sender = EmailSender(mode="outbox", outbox_dir=str(tmp_path / "out"), sender="hw@f.cz", smtp={})
    msg_id = sender.send(to="jan@f.cz", subject="Předání", text="Ahoj", html="<p>Ahoj</p>", attachments=[("a.txt", b"hi", "text/plain")])
    files = sorted((tmp_path / "out").glob("*.json"))
    assert len(files) == 1 and msg_id
    data = json.loads(files[0].read_text())
    assert data["to"] == "jan@f.cz" and data["subject"] == "Předání" and data["from"] == "hw@f.cz"
    assert data["text"] == "Ahoj" and "<p>Ahoj</p>" in data["html"]
    assert data["attachments"][0]["filename"] == "a.txt" and data["attachments"][0]["size"] == 2


def test_smtp_sender_uses_injected_transport():
    sent = []

    class FakeSMTP:
        def __init__(self, host, port):
            sent.append(("connect", host, port))

        def starttls(self):
            sent.append(("starttls",))

        def login(self, user, password):
            sent.append(("login", user))

        def send_message(self, message):
            sent.append(("message", message["To"], message["Subject"]))

        def quit(self):
            sent.append(("quit",))

    sender = EmailSender(mode="smtp", outbox_dir="", sender="hw@f.cz", smtp={"host": "smtp.f.cz", "port": 587, "user": "u", "password": "p", "starttls": True}, smtp_factory=FakeSMTP)
    sender.send(to="jan@f.cz", subject="S", text="t", html="<b>t</b>")
    assert sent == [("connect", "smtp.f.cz", 587), ("starttls",), ("login", "u"), ("message", "jan@f.cz", "S"), ("quit",)]


def test_tokens_round_trip_and_expiry():
    tokens = HandoverTokens(secret="s3cret", max_age_hours=1)
    token = tokens.issue(handover_id=42, email="jan@f.cz")
    assert tokens.verify(token) == {"handover_id": 42, "email": "jan@f.cz"}
    assert tokens.verify(token + "x") is None
    assert HandoverTokens(secret="other", max_age_hours=1).verify(token) is None
    stale = HandoverTokens(secret="s3cret", max_age_hours=0)
    assert stale.verify(stale.issue(handover_id=1, email="a@b"), now_offset_seconds=3600) is None


def test_protocol_pdf_is_a_pdf_with_the_facts(tmp_path):
    out = tmp_path / "HP-2026-000001.pdf"
    render_protocol_pdf(
        path=str(out),
        protocol_number="HP-2026-000001",
        kind="handover",
        company="Firma s.r.o.",
        employee={"display_name": "Jan Novák", "email": "jan@f.cz", "department": "IT"},
        asset={"asset_tag": "NB-0001", "type": "notebook", "brand": "Dell", "model": "Latitude 5540", "serial_number": "SN1"},
        created_by="admin@f.cz",
        confirmed_at="2026-09-17T10:00:00+00:00",
        note="včetně nabíječky",
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000
