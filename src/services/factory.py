"""Service construction from the app config.

Every view builds its services here so the wiring lives in one place; the
connection is passed in (one per request, see src.db.get_db).
"""

from __future__ import annotations

import json
import sqlite3

from flask import current_app

from src.repositories.assets import AssetRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.attachments import AttachmentRepository
from src.repositories.audit import AuditRepository
from src.repositories.employees import EmployeeRepository
from src.repositories.handovers import HandoverRepository
from src.repositories.invoices import InvoiceRepository
from src.repositories.locations import LocationRepository
from src.repositories.tags import TagRepository
from src.services.asset_service import AssetService
from src.services.attachment_service import AttachmentService
from src.services.dashboard_service import DashboardService
from src.services.email_sender import EmailSender
from src.services.handover_service import HandoverService
from src.services.intake_service import IntakeService
from src.services.label_service import LabelService
from src.services.tokens import HandoverTokens


def _config():
    return current_app.config


def build_email_sender(config) -> EmailSender:
    """The e-mail transport for a config mapping (app.config or a plain dict)."""
    return EmailSender(
        mode=config["EMAIL_MODE"],
        outbox_dir=config["OUTBOX_DIR"],
        sender=config["EMAIL_FROM"],
        smtp={
            "host": config["SMTP_HOST"],
            "port": config["SMTP_PORT"],
            "user": config["SMTP_USER"],
            "password": config["SMTP_PASSWORD"],
            "starttls": config["SMTP_STARTTLS"],
        },
    )


def build_handover_service(db: sqlite3.Connection) -> HandoverService:
    """Build a HandoverService wired from current_app.config."""
    config = _config()
    return HandoverService(
        handovers=HandoverRepository(db),
        assignments=AssignmentRepository(db),
        assets=AssetRepository(db),
        employees=EmployeeRepository(db),
        audit=AuditRepository(db),
        email=build_email_sender(config),
        tokens=HandoverTokens(secret=config["SECRET_KEY"], max_age_hours=config["HANDOVER_TOKEN_HOURS"]),
        base_url=config["BASE_URL"],
        company=config["COMPANY_NAME"],
        protocol_dir=config["PROTOCOL_DIR"],
        copy_to=config.get("PROTOCOL_COPY_TO") or (config["ADMIN_EMAILS"][0] if config.get("ADMIN_EMAILS") else ""),
    )


def build_asset_service(db: sqlite3.Connection) -> AssetService:
    """An AssetService with tags, locations, invoices and inventory-number generation."""
    config = _config()
    raw_prefixes = config.get("TAG_PREFIXES")
    try:
        prefixes = json.loads(raw_prefixes) if isinstance(raw_prefixes, str) and raw_prefixes else (raw_prefixes or {})
    except ValueError:
        prefixes = {}
    return AssetService(
        AssetRepository(db),
        AuditRepository(db),
        tags=TagRepository(db),
        locations=LocationRepository(db),
        invoices=InvoiceRepository(db),
        tag_prefixes=prefixes,
        tag_pad=int(config.get("TAG_PAD", 4)),
    )


def build_dashboard_service(db: sqlite3.Connection) -> DashboardService:
    return DashboardService(AssetRepository(db), HandoverRepository(db), AuditRepository(db), EmployeeRepository(db))


def build_attachment_service(db: sqlite3.Connection) -> AttachmentService:
    config = _config()
    assets = AssetRepository(db)
    invoices = InvoiceRepository(db)

    def owner_exists(owner_type: str, owner_id: int) -> bool:
        repo = assets if owner_type == "asset" else invoices
        return repo.get(owner_id) is not None

    return AttachmentService(
        AttachmentRepository(db),
        AuditRepository(db),
        directory=config["ATTACHMENTS_DIR"],
        max_bytes=int(config.get("ATTACHMENT_MAX_MB", 20)) * 1024 * 1024,
        owner_exists=owner_exists,
    )


def build_label_service() -> LabelService:
    config = _config()
    service = LabelService(
        base_url=config["BASE_URL"],
        company=config["COMPANY_NAME"],
        zpl_template=config.get("LABEL_ZPL_TEMPLATE") or None,
    )
    return service


def build_intake_service(db: sqlite3.Connection) -> IntakeService:
    return IntakeService(build_asset_service(db), InvoiceRepository(db), AuditRepository(db))
