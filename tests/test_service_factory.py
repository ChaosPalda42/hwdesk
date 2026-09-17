from src.db import connect
from src.services.factory import (
    build_asset_service,
    build_attachment_service,
    build_dashboard_service,
    build_handover_service,
    build_intake_service,
    build_label_service,
)


def test_builders_wire_every_collaborator(app):
    with app.app_context():
        db = connect(app.config["DATABASE"])
        assets = build_asset_service(db)
        assert assets.tags is not None and assets.locations is not None and assets.invoices is not None
        assert assets.tag_prefixes["notebook"] == "NB" and assets.tag_pad == 4
        attachments = build_attachment_service(db)
        assert attachments.audit is not None and attachments.directory == app.config["ATTACHMENTS_DIR"]
        assert attachments.max_bytes == app.config["ATTACHMENT_MAX_MB"] * 1024 * 1024
        assert attachments.owner_exists("asset", 999) is False and attachments.owner_exists("invoice", 999) is False
        assert build_dashboard_service(db).stats(today="2026-01-01")["totals"]["assets"] == 0
        assert build_label_service().company == app.config["COMPANY_NAME"]
        assert build_intake_service(db).assets.tags is not None
        assert build_handover_service(db).copy_to
        db.close()
