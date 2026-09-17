"""Maintenance commands: `uv run python -m src.cli expire` (cron-friendly)."""

from __future__ import annotations

import sys

from src.app import create_app
from src.db import get_db
from src.services.factory import build_handover_service


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"expire"}:
        print("usage: python -m src.cli expire   # expire pending handovers older than HANDOVER_TOKEN_HOURS")
        return 2
    app = create_app()
    with app.app_context():
        service = build_handover_service(get_db())
        count = service.expire_stale(older_than_hours=app.config["HANDOVER_TOKEN_HOURS"])
        print(f"expired {count} handover(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
