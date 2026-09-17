"""Configuration for HW Desk.

Everything comes from environment variables with safe development defaults;
`load_config()` returns a plain dict that `create_app` copies into
`app.config`. Nothing here ever holds real credentials in the repository.

Modes:
* AUTH_MODE      "dev" (form login by e-mail, tests and local runs) or "oidc" (Microsoft 365).
* EMAIL_MODE     "outbox" (messages written as JSON files to OUTBOX_DIR) or "smtp".
"""

from __future__ import annotations

import os
from pathlib import Path


def _list(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def load_config(overrides: dict | None = None) -> dict:
    env = os.environ
    config = {
        "SECRET_KEY": env.get("HWDESK_SECRET_KEY", "dev-secret-change-me"),
        "DATABASE": env.get("HWDESK_DATABASE", "hwdesk.db"),
        "BASE_URL": env.get("HWDESK_BASE_URL", "http://localhost:5000"),
        "COMPANY_NAME": env.get("HWDESK_COMPANY_NAME", "Naše firma"),
        # Who may manage assets and employees. E-mail addresses, lower-case.
        "ADMIN_EMAILS": _list(env.get("HWDESK_ADMIN_EMAILS", "admin@example.com")),
        # Integrations (HR sync, scripts) authenticate with one of these keys.
        "API_KEYS": _list(env.get("HWDESK_API_KEYS", "")),
        # Authentication.
        "AUTH_MODE": env.get("HWDESK_AUTH_MODE", "dev"),
        "OIDC_TENANT_ID": env.get("HWDESK_OIDC_TENANT_ID", ""),
        "OIDC_CLIENT_ID": env.get("HWDESK_OIDC_CLIENT_ID", ""),
        "OIDC_CLIENT_SECRET": env.get("HWDESK_OIDC_CLIENT_SECRET", ""),
        "OIDC_REDIRECT_PATH": "/auth/callback",
        # E-mail.
        "EMAIL_MODE": env.get("HWDESK_EMAIL_MODE", "outbox"),
        "EMAIL_FROM": env.get("HWDESK_EMAIL_FROM", "hwdesk@example.com"),
        "OUTBOX_DIR": env.get("HWDESK_OUTBOX_DIR", "outbox"),
        "SMTP_HOST": env.get("HWDESK_SMTP_HOST", ""),
        "SMTP_PORT": int(env.get("HWDESK_SMTP_PORT", "587")),
        "SMTP_USER": env.get("HWDESK_SMTP_USER", ""),
        "SMTP_PASSWORD": env.get("HWDESK_SMTP_PASSWORD", ""),
        "SMTP_STARTTLS": env.get("HWDESK_SMTP_STARTTLS", "1") == "1",
        # Handover links expire after this many hours.
        "HANDOVER_TOKEN_HOURS": int(env.get("HWDESK_HANDOVER_TOKEN_HOURS", "168")),
        # Where confirmed protocols (PDF) are stored.
        "PROTOCOL_DIR": env.get("HWDESK_PROTOCOL_DIR", "protocols"),
        # Every confirmed protocol is also mailed here (default: the first admin).
        "PROTOCOL_COPY_TO": env.get("HWDESK_PROTOCOL_COPY_TO", ""),
    }
    if overrides:
        config.update(overrides)
    for key in ("OUTBOX_DIR", "PROTOCOL_DIR"):
        Path(config[key]).mkdir(parents=True, exist_ok=True)
    return config


ASSET_TYPES = (
    "notebook",
    "desktop",
    "monitor",
    "phone",
    "tablet",
    "keyboard",
    "mouse",
    "headset",
    "dock",
    "other",
)

ASSET_STATUSES = ("in_stock", "pending_handover", "assigned", "pending_return", "retired", "lost")

HANDOVER_KINDS = ("handover", "return")
HANDOVER_STATUSES = ("pending", "confirmed", "declined", "expired", "cancelled")
