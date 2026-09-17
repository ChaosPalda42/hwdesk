# HW Desk

Interní správa firemního hardwaru: evidence zařízení, přidělování zaměstnancům,
předávací a vratné protokoly potvrzované e-mailem (PDF s číslem), přehled pro
každého zaměstnance po přihlášení účtem Microsoft 365, JSON API pro integrace,
synchronizace zaměstnanců z HR, audit log.

## Spuštění pro vývoj

    uv sync
    HWDESK_ADMIN_EMAILS=ja@firma.cz uv run flask --app src.app:create_app run
    # AUTH_MODE=dev: přihlášení jen e-mailem; e-maily se ukládají do outbox/ jako JSON

## Nasazení

1. `cp .env.example .env` a vyplnit (viz komentáře).
2. Entra ID: registrovat aplikaci (Web), redirect URI `<BASE_URL>/auth/callback`, povolit ID token; vyplnit tenant/client/secret.
3. SMTP: účet pro odesílání (M365 SMTP AUTH nebo relay).
4. `docker build -t hwdesk . && docker run --env-file .env -p 8000:8000 -v hwdesk-data:/data hwdesk`
5. Cron: denně `python -m src.cli expire` (expirace nepotvrzených žádostí) a např. každou hodinu `python -m src.cli hr-sync` (Drupal → zaměstnanci).
6. Entra ID, SMTP a Drupal lze nastavit i v aplikaci (Nastavení, jen správce); hodnoty v DB mají přednost před .env.

## Toky

- **Předání:** správce na detailu zařízení vybere zaměstnance → e-mail s odkazem →
  zaměstnanec se přihlásí a potvrdí (nebo odmítne s důvodem) → PDF protokol
  `HP-<rok>-<pořadí>` uložen a odeslán zaměstnanci, zadavateli a na `PROTOCOL_COPY_TO`.
- **Vrácení:** správce (nebo sám zaměstnanec v „Moje zařízení") → stejný postup.
- **Offboarding:** HR sync označí zaměstnance neaktivním → odpověď API vypíše, co má u sebe.

## HR synchronizace z Drupalu

Konektor čte `GET <DRUPAL_URL>/jsonapi/user/user` (JSON:API, stránkování `links.next`),
autentizace none/basic/token, mapování polí v Nastavení (`DRUPAL_FIELD_MAP`, JSON, cesty
tečkovou notací, výchozí `attributes.mail`, `attributes.display_name`,
`attributes.field_department`, `attributes.field_manager_email`,
`attributes.drupal_internal__uid`, `attributes.status`), volitelný filtr
(`DRUPAL_FILTER`, např. `filter[roles.meta.drupal_internal__target_id]=employee`).
Spouští se tlačítkem v Nastavení nebo cronem. Alternativně může Drupal tlačit
změny sám na `POST /api/v1/hr/employees`.

## API (`Authorization: Bearer <klíč>`)

    GET/POST   /api/v1/assets            GET/PATCH /api/v1/assets/<id>   POST /api/v1/assets/<id>/retire|lost
    GET        /api/v1/employees         GET /api/v1/employees/<email>
    POST       /api/v1/hr/employees      {"employees":[{email, display_name, department, manager_email, hr_id, active}]}
    POST       /api/v1/hr/employees/csv  (tělo = CSV; oddělovač ; nebo ,)
    GET/POST   /api/v1/handovers         GET /api/v1/handovers/<id>  POST /api/v1/handovers/<id>/cancel  GET …/protocol.pdf
    POST       /api/v1/returns           {"asset_id", "note"}
    GET        /api/v1/audit?limit=50

## Testy

    uv run pytest -q
