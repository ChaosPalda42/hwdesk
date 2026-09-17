# HW Desk

Interní správa firemního hardwaru: evidence zařízení (štítky, lokality, stav
kusu, záruka, faktury, přílohy), přidělování zaměstnancům, předávací a vratné
protokoly potvrzované e-mailem (PDF s číslem), příjem zboží s generováním
inventárních čísel a tiskem štítků s QR, přehled pro každého zaměstnance po
přihlášení účtem Microsoft 365, JSON API pro integrace, synchronizace
zaměstnanců z HR, audit log.

## Ukázka

Klikací statická ukázka se vzorovými daty (bez serveru, formuláře jsou vypnuté):
**https://chaospalda42.github.io/hwdesk/** — generuje ji `tools/snapshot.py`
z běžící aplikace při každém pushi na `main` (GitHub Actions → Pages).

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

## Evidence

- **Inventární čísla:** prefix podle typu (`HWDESK_TAG_PREFIXES`, JSON, výchozí NB/PC/MO/PH/TB/KB/MS/HS/DK/OT)
  + pořadí doplněné nulami (`HWDESK_TAG_PAD`); pole lze i vyplnit ručně.
- **Příjem zboží (Příjem zařízení):** typ, model, počet, faktura, lokalita, štítky →
  založí N zařízení → načtení sériových čísel čtečkou → štítky k tisku.
- **Štítky 50×25 mm** s QR na `/a/<inventární číslo>`: tisk z prohlížeče
  (`/admin/labels?ids=…`), nebo ZPL přímo na síťovou tiskárnu Zebra
  (`HWDESK_LABEL_PRINTER_HOST`, port 9100, šablonu lze přepsat v `HWDESK_LABEL_ZPL_TEMPLATE`).
- **Faktury:** jedna faktura pro libovolný počet zařízení; přílohy (PDF/obrázky)
  k faktuře i k zařízení se ukládají do `HWDESK_ATTACHMENTS_DIR`.
- **Seznam zařízení:** filtry (hledání, typ, stav, štítek, lokalita, držitel, stav kusu),
  řazení, hromadné akce nad výběrem (štítek, lokalita, faktura, štítky k tisku, CSV).
- **CSV:** export `GET /api/v1/assets/export.csv`, import `POST /api/v1/assets/import.csv`
  (tělo = CSV se stejnou hlavičkou; existující inventární čísla se aktualizují).

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
               ?q=&status=&type=&location_id=&tag=&employee_email=&invoice_id=&warranty_before=&sort=
    GET/POST   /api/v1/assets/export.csv | /api/v1/assets/import.csv
    GET/POST   /api/v1/tags | /locations | /invoices    PATCH/DELETE …/<id>   GET /api/v1/invoices/<id> (+assets, attachments)
    POST       /api/v1/invoices/<id>/assets {"asset_ids":[…]}
    GET/POST   /api/v1/assets/<id>/attachments (multipart kind, file)   POST /api/v1/invoices/<id>/attachments
    GET/DELETE /api/v1/attachments/<id>    GET /api/v1/dashboard
    GET        /api/v1/employees         GET /api/v1/employees/<email>
    POST       /api/v1/hr/employees      {"employees":[{email, display_name, department, manager_email, hr_id, active}]}
    POST       /api/v1/hr/employees/csv  (tělo = CSV; oddělovač ; nebo ,)
    GET/POST   /api/v1/handovers         GET /api/v1/handovers/<id>  POST /api/v1/handovers/<id>/cancel  GET …/protocol.pdf
    POST       /api/v1/returns           {"asset_id", "note"}
    GET        /api/v1/audit?limit=50

## Testy

    uv run pytest -q
