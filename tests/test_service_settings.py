from src.repositories.settings import SettingsRepository
from src.services.settings_service import SETTINGS_SCHEMA, SettingsService


def test_schema_covers_the_configurable_keys():
    keys = {item["key"] for item in SETTINGS_SCHEMA}
    for key in ("AUTH_MODE", "OIDC_TENANT_ID", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "EMAIL_MODE", "EMAIL_FROM", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS", "PROTOCOL_COPY_TO", "HANDOVER_TOKEN_HOURS", "COMPANY_NAME", "BASE_URL", "DRUPAL_URL", "DRUPAL_AUTH_MODE", "DRUPAL_USER", "DRUPAL_PASSWORD", "DRUPAL_TOKEN", "DRUPAL_FIELD_MAP", "DRUPAL_FILTER", "TAG_PREFIXES", "TAG_PAD", "LABEL_PRINTER_HOST", "LABEL_PRINTER_PORT", "LABEL_ZPL_TEMPLATE"):
        assert key in keys, key
    secret = {item["key"] for item in SETTINGS_SCHEMA if item["secret"]}
    assert {"OIDC_CLIENT_SECRET", "SMTP_PASSWORD", "DRUPAL_PASSWORD", "DRUPAL_TOKEN"} <= secret


def test_effective_config_overrides_env_defaults_and_coerces_types(conn):
    repo = SettingsRepository(conn)
    service = SettingsService(repo)
    base = {"SMTP_HOST": "", "SMTP_PORT": 587, "SMTP_STARTTLS": True, "HANDOVER_TOKEN_HOURS": 168, "AUTH_MODE": "dev"}
    assert service.effective(base) == base
    service.save({"SMTP_HOST": "smtp.f.cz", "SMTP_PORT": "2525", "SMTP_STARTTLS": "0", "HANDOVER_TOKEN_HOURS": "48", "AUTH_MODE": "oidc"}, updated_by="admin@f.cz")
    effective = service.effective(base)
    assert effective["SMTP_HOST"] == "smtp.f.cz" and effective["SMTP_PORT"] == 2525
    assert effective["SMTP_STARTTLS"] is False and effective["HANDOVER_TOKEN_HOURS"] == 48 and effective["AUTH_MODE"] == "oidc"


def test_save_keeps_a_secret_when_the_form_sends_the_mask(conn):
    service = SettingsService(SettingsRepository(conn))
    service.save({"SMTP_PASSWORD": "s3cret"}, updated_by="a")
    service.save({"SMTP_PASSWORD": service.MASK, "SMTP_HOST": "x"}, updated_by="a")
    assert service.effective({})["SMTP_PASSWORD"] == "s3cret"
    service.save({"SMTP_PASSWORD": ""}, updated_by="a")
    assert service.effective({}).get("SMTP_PASSWORD", "") == ""


def test_for_form_masks_secrets_and_lists_schema(conn):
    service = SettingsService(SettingsRepository(conn))
    service.save({"SMTP_PASSWORD": "s3cret", "SMTP_HOST": "smtp.f.cz"}, updated_by="a")
    rows = service.for_form({"SMTP_PORT": 587})
    by_key = {r["key"]: r for r in rows}
    assert by_key["SMTP_PASSWORD"]["value"] == service.MASK and by_key["SMTP_PASSWORD"]["secret"] is True
    assert by_key["SMTP_HOST"]["value"] == "smtp.f.cz" and by_key["SMTP_PORT"]["value"] == "587"
    assert by_key["AUTH_MODE"]["choices"] == ["dev", "oidc"]
    assert all(r["group"] for r in rows) and all(r["label"] for r in rows)


def test_validation(conn):
    service = SettingsService(SettingsRepository(conn))
    problems = service.validate({"SMTP_PORT": "abc", "AUTH_MODE": "magic", "HANDOVER_TOKEN_HOURS": "0", "DRUPAL_FIELD_MAP": "{not json"})
    assert {p.split(":")[0] for p in problems} == {"SMTP_PORT", "AUTH_MODE", "HANDOVER_TOKEN_HOURS", "DRUPAL_FIELD_MAP"}
    assert service.validate({"SMTP_PORT": "587", "AUTH_MODE": "oidc"}) == []
