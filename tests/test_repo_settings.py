from src.repositories.settings import SettingsRepository


def test_get_set_all(conn):
    repo = SettingsRepository(conn)
    assert repo.get("SMTP_HOST") is None
    assert repo.all() == {}
    repo.set("SMTP_HOST", "smtp.office365.com", updated_by="admin@f.cz")
    repo.set("SMTP_PORT", "587", updated_by="admin@f.cz")
    assert repo.get("SMTP_HOST") == "smtp.office365.com"
    assert repo.all() == {"SMTP_HOST": "smtp.office365.com", "SMTP_PORT": "587"}
    repo.set("SMTP_HOST", "relay.f.cz", updated_by="x")
    assert repo.get("SMTP_HOST") == "relay.f.cz"
    assert repo.delete("SMTP_PORT") is True and repo.delete("SMTP_PORT") is False
    assert repo.all() == {"SMTP_HOST": "relay.f.cz"}
    assert repo.version() >= 1
