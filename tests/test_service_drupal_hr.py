import json

import pytest

from src.services.drupal_hr import DrupalHrClient, DrupalHrError

PAGE1 = {
    "data": [
        {"id": "u1", "attributes": {"drupal_internal__uid": 12, "mail": "Jan@f.cz", "display_name": "Jan Novák", "status": True, "field_department": "IT", "field_manager_email": ""}},
        {"id": "u2", "attributes": {"drupal_internal__uid": 13, "mail": "eva@f.cz", "display_name": "Eva", "status": False, "field_department": "HR", "field_manager_email": "jan@f.cz"}},
    ],
    "links": {"next": {"href": "https://hr.f.cz/jsonapi/user/user?page[offset]=50"}},
}
PAGE2 = {"data": [{"id": "u3", "attributes": {"drupal_internal__uid": 14, "mail": "", "display_name": "No mail", "status": True}}], "links": {}}


def _fetcher(calls):
    def fetch(url, headers):
        calls.append((url, headers))
        if "offset" in url:
            return 200, json.dumps(PAGE2)
        return 200, json.dumps(PAGE1)
    return fetch


def test_fetch_follows_pagination_and_maps_records():
    calls = []
    client = DrupalHrClient(base_url="https://hr.f.cz/", auth_mode="basic", user="api", password="pw", token="", field_map={}, filter_query="", fetch=_fetcher(calls))
    records, skipped = client.fetch_employees()
    assert calls[0][0] == "https://hr.f.cz/jsonapi/user/user?page[limit]=50"
    assert calls[0][1]["Authorization"].startswith("Basic ") and calls[0][1]["Accept"] == "application/vnd.api+json"
    assert len(calls) == 2
    assert records[0] == {"email": "jan@f.cz", "display_name": "Jan Novák", "department": "IT", "manager_email": "", "hr_id": "12", "active": True}
    assert records[1]["active"] is False and records[1]["manager_email"] == "jan@f.cz"
    assert skipped == 1  # the record without e-mail


def test_custom_field_map_and_token_auth_and_filter():
    calls = []
    page = {"data": [{"id": "x", "attributes": {"email_work": "a@f.cz", "name": "A", "dept": {"name": "Ops"}, "active": 1}}], "links": {}}
    client = DrupalHrClient(base_url="https://hr.f.cz", auth_mode="token", user="", password="", token="tok", field_map={"email": "attributes.email_work", "display_name": "attributes.name", "department": "attributes.dept.name", "active": "attributes.active"}, filter_query="filter[roles.meta.drupal_internal__target_id]=employee", fetch=lambda url, headers: (calls.append((url, headers)) or (200, json.dumps(page))))
    records, skipped = client.fetch_employees()
    assert calls[0][1]["Authorization"] == "Bearer tok"
    assert "filter[roles.meta.drupal_internal__target_id]=employee" in calls[0][0]
    assert records == [{"email": "a@f.cz", "display_name": "A", "department": "Ops", "manager_email": "", "hr_id": "x", "active": True}]


def test_http_error_raises():
    client = DrupalHrClient(base_url="https://hr.f.cz", auth_mode="none", user="", password="", token="", field_map={}, filter_query="", fetch=lambda url, headers: (403, "forbidden"))
    with pytest.raises(DrupalHrError):
        client.fetch_employees()
