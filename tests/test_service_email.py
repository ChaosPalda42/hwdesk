import json
from pathlib import Path

import pytest

from src.services.email_sender import EmailSender


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
