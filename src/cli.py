"""Maintenance commands: `uv run python -m src.cli expire` (cron-friendly)."""

from __future__ import annotations

import sys

from src.app import create_app
from src.db import get_db
from src.services.factory import build_handover_service


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"expire", "hr-sync"}:
        print("usage: python -m src.cli expire    # expire pending handovers older than HANDOVER_TOKEN_HOURS")
        print("       python -m src.cli hr-sync   # pull employees from the configured Drupal HR")
        return 2
    app = create_app()
    with app.app_context():
        if argv[1] == "expire":
            service = build_handover_service(get_db())
            count = service.expire_stale(older_than_hours=app.config["HANDOVER_TOKEN_HOURS"])
            print(f"expired {count} handover(s)")
            return 0
        import json

        from src.repositories.assets import AssetRepository
        from src.repositories.assignments import AssignmentRepository
        from src.repositories.audit import AuditRepository
        from src.repositories.employees import EmployeeRepository
        from src.services.drupal_hr import DrupalHrClient
        from src.services.hr_sync import HrSyncService

        config = app.config
        if not config.get("DRUPAL_URL"):
            print("DRUPAL_URL is not configured (Nastavení → HR synchronizace)")
            return 2
        client = DrupalHrClient(
            base_url=config["DRUPAL_URL"],
            auth_mode=config.get("DRUPAL_AUTH_MODE", "none"),
            user=config.get("DRUPAL_USER", ""),
            password=config.get("DRUPAL_PASSWORD", ""),
            token=config.get("DRUPAL_TOKEN", ""),
            field_map=json.loads(config["DRUPAL_FIELD_MAP"]) if config.get("DRUPAL_FIELD_MAP") else {},
            filter_query=config.get("DRUPAL_FILTER", ""),
        )
        records, skipped = client.fetch_employees()
        db = get_db()
        result = HrSyncService(EmployeeRepository(db), AssetRepository(db), AuditRepository(db), assignments=AssignmentRepository(db)).sync(actor="cron:hr-sync", records=records)
        print(f"hr-sync: created {result['created']}, updated {result['updated']}, deactivated {result['deactivated']}, skipped {skipped}")
        for item in result["offboarding"]:
            print(f"  offboarding {item['email']}: {', '.join(item['asset_tags']) or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
