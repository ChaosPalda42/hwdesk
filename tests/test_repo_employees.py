from src.repositories.employees import EmployeeRepository


def test_upsert_by_email_creates_then_updates(conn):
    repo = EmployeeRepository(conn)
    created = repo.upsert(email="Jan.Novak@Firma.cz", display_name="Jan Novák", department="IT", manager_email="", hr_id="H1")
    assert created["email"] == "jan.novak@firma.cz" and created["active"] is True
    updated = repo.upsert(email="jan.novak@firma.cz", display_name="Jan Novák", department="Provoz", manager_email="", hr_id="H1")
    assert updated["id"] == created["id"] and updated["department"] == "Provoz"
    assert repo.get(created["id"])["department"] == "Provoz"
    assert repo.get_by_email("JAN.NOVAK@firma.cz")["id"] == created["id"]
    assert repo.get(999) is None and repo.get_by_email("nobody@x") is None


def test_list_and_deactivate(conn):
    repo = EmployeeRepository(conn)
    a = repo.upsert(email="a@f.cz", display_name="A", department="", manager_email="", hr_id="")
    repo.upsert(email="b@f.cz", display_name="B", department="", manager_email="", hr_id="")
    assert [e["email"] for e in repo.list_all()] == ["a@f.cz", "b@f.cz"]
    assert repo.set_active(a["id"], False) is True
    assert repo.get(a["id"])["active"] is False
    assert [e["email"] for e in repo.list_all(active_only=True)] == ["b@f.cz"]
    assert repo.set_active(999, False) is False


def test_search_matches_name_and_email(conn):
    repo = EmployeeRepository(conn)
    repo.upsert(email="petr@f.cz", display_name="Petr Král", department="", manager_email="", hr_id="")
    repo.upsert(email="eva@f.cz", display_name="Eva Malá", department="", manager_email="", hr_id="")
    assert [e["email"] for e in repo.search("krá")] == ["petr@f.cz"]
    assert [e["email"] for e in repo.search("EVA@")] == ["eva@f.cz"]
