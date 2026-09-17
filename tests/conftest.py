import json
from pathlib import Path

import pytest

from src.db import connect


@pytest.fixture()
def conn(tmp_path):
    c = connect(str(tmp_path / "t.db"))
    yield c
    c.close()


@pytest.fixture()
def app(tmp_path):
    from src.app import create_app  # produced by the last contract

    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "app.db"),
            "OUTBOX_DIR": str(tmp_path / "outbox"),
            "PROTOCOL_DIR": str(tmp_path / "protocols"),
            "AUTH_MODE": "dev",
            "EMAIL_MODE": "outbox",
            "ADMIN_EMAILS": ["admin@firma.cz"],
            "API_KEYS": ["test-api-key"],
            "BASE_URL": "http://testserver",
        }
    )
    return application


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


def login(client, email):
    """Dev login: sets the session identity to the given e-mail."""
    resp = client.post("/auth/dev-login", data={"email": email}, follow_redirects=False)
    assert resp.status_code in (302, 303), resp.get_data(as_text=True)
    return resp


def outbox(app):
    """Messages written in outbox mode, oldest first, as dicts."""
    folder = Path(app.config["OUTBOX_DIR"])
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]


def api(client, method, path, key="test-api-key", **kwargs):
    return client.open(path, method=method, headers={"Authorization": f"Bearer {key}"}, **kwargs)
