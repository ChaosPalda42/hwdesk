Evidence oprav (servisních zásahů) k zařízení.

- Nová tabulka `repairs` v src/db.py (soubor operátora — vypiš přesné SQL do operator_changes): id, asset_id (FK assets), description, vendor, sent_at (ISO date), returned_at (ISO date nebo ''), cost REAL, result TEXT ('' dokud není uzavřeno), created_by, created_at.
- Repozitář src/repositories/repairs.py: create, get, list_for_asset, list_open, close(id, returned_at, result, cost).
- Služba src/services/repair_service.py: open_repair(actor, asset_id, description, vendor, sent_at, cost) — zařízení musí existovat a nesmí být retired/lost; zapíše audit 'repair.opened'; close_repair(actor, repair_id, returned_at, result, cost) — audit 'repair.closed'; chyby jako RepairError. Audit přes AuditRepository.record(actor, action, entity='repair', entity_id, details).
- JSON API src/api/repairs.py (Blueprint 'api_repairs', bez url_prefix, mount /api/v1, api_auth_required, actor z guards): GET /assets/<id>/repairs, POST /assets/<id>/repairs -> 201, POST /repairs/<id>/close -> 200, chyby {"error": …} 400/404.
- Registrace blueprintu do BLUEPRINTS v src/app.py (kontrakt C-032 se rozšíří o řádek ('src.api.repairs', 'bp', '/api/v1')).
- UI (šablony, admin) tentokrát NE — jen data a API.
