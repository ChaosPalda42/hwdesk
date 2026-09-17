import sqlite3
from flask import current_app
from src.services.handover_service import HandoverService
from src.services.asset_service import AssetService
from src.services.email_sender import EmailSender
from src.services.tokens import HandoverTokens
from src.repositories.employees import EmployeeRepository
from src.repositories.assets import AssetRepository
from src.repositories.handovers import HandoverRepository
from src.repositories.assignments import AssignmentRepository
from src.repositories.audit import AuditRepository


def build_handover_service(db: sqlite3.Connection) -> HandoverService:
    """Build a HandoverService wired from current_app.config."""
    # Get config values from flask app config
    config = getattr(current_app, 'config', {})
    
    # Create the dependencies
    handovers = HandoverRepository(db)
    assignments = AssignmentRepository(db)
    assets = AssetRepository(db)
    employees = EmployeeRepository(db)
    audit = AuditRepository(db)
    
    # Create the email sender
    email_sender = EmailSender(
        mode=config['EMAIL_MODE'],
        outbox_dir=config['OUTBOX_DIR'],
        sender=config['EMAIL_FROM'],
        smtp={
            'host': config['SMTP_HOST'],
            'port': config['SMTP_PORT'],
            'user': config['SMTP_USER'],
            'password': config['SMTP_PASSWORD'],
            'starttls': config['SMTP_STARTTLS']
        }
    )
    
    # Create the tokens service
    tokens = HandoverTokens(
        secret=config['SECRET_KEY'],
        max_age_hours=config['HANDOVER_TOKEN_HOURS']
    )
    
    # Create and return the HandoverService
    return HandoverService(
        handovers=handovers,
        assignments=assignments,
        assets=assets,
        employees=employees,
        audit=audit,
        email=email_sender,
        tokens=tokens,
        base_url=config['BASE_URL'],
        company=config['COMPANY_NAME'],
        protocol_dir=config['PROTOCOL_DIR'],
        copy_to=config.get('PROTOCOL_COPY_TO') or (config['ADMIN_EMAILS'][0] if config.get('ADMIN_EMAILS') else '')
    )


def build_asset_service(db: sqlite3.Connection) -> AssetService:
    """Build an AssetService."""
    # Create the dependencies
    assets = AssetRepository(db)
    audit = AuditRepository(db)
    
    # Create and return the AssetService
    return AssetService(assets=assets, audit=audit)