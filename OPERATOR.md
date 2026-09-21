# OPERATOR — hwdesk

## Co a proč
HW Desk: interní webová aplikace pro správu firemního hardwaru (notebooky,
telefony, monitory, periferie). Správce eviduje zařízení a přiděluje je
zaměstnancům; každé předání i vrácení potvrzuje zaměstnanec kliknutím na
odkaz z e-mailu, čímž vzniká předávací protokol (PDF s číslem). Každý
zaměstnanec se přihlásí účtem Microsoft 365 a vidí, co má u sebe a co má
potvrdit. Integrace přes JSON API (klíče) — zejména synchronizace
zaměstnanců z HR (aktivní/neaktivní → offboarding = výzva k vrácení).

## Kde jsme
Viz STATE.md. Poslední shrnutí operátora (2026-09-17): 49/49 kontraktů zelených,
87 testů. Třetí dávka (plnohodnotný asset management: štítky, lokality,
faktury 1:N, přílohy, dashboard, filtry + hromadné akce, příjem zboží →
sériová čísla → štítky s QR (tisk z prohlížeče / ZPL na Zebru), CSV
import/export, nový design) hotová a ověřená v prohlížeči (dashboard, seznam
s filtry a bulk, detail, předání → potvrzení zaměstnancem, příjem, štítky,
faktury, štítky/lokality, nastavení). Demo: port 5077. Čeká na externí
vstupy: Entra ID registrace, SMTP účet, Drupal URL/auth, server.

## Rozhodnutí
- 2026-09-17: stack Flask + sqlite3 (raw SQL) + Jinja; žádný ORM, žádný JS
  framework — spolehlivé pro lokální modely, dostatečné pro interní nástroj.
  Postgres lze zavést později výměnou `src/db.py`.
- 2026-09-17: dva režimy přihlášení — `oidc` (Microsoft Entra ID přes MSAL,
  produkce) a `dev` (formulář s e-mailem; jen když `AUTH_MODE=dev`). Testy
  běží v `dev`.
- 2026-09-17: role = admin (e-mail v `ADMIN_EMAILS`) nebo zaměstnanec
  (kdokoli přihlášený, jehož e-mail je v tabulce employees; ostatní vidí
  „nejste v evidenci“).
- 2026-09-17: e-mail — `outbox` (JSON soubory, testy a vývoj) nebo `smtp`.
  Odkaz na potvrzení nese podepsaný token (itsdangerous), platnost
  `HANDOVER_TOKEN_HOURS`; potvrdit ho může jen přihlášený uživatel se
  stejným e-mailem jako adresát (token sám nestačí).
- 2026-09-17: stavy zařízení: in_stock → pending_handover → assigned →
  pending_return → in_stock; retired/lost ručně. Zařízení má nejvýše
  jedno otevřené přiřazení.
- 2026-09-17: protokol = PDF (reportlab) generované při potvrzení, uloženo do
  `PROTOCOL_DIR`, číslo `HP-<rok>-<pořadí>`; kopie e-mailem oběma stranám.
- 2026-09-17: Entra ID, SMTP a Drupal konfigurovatelné v aplikaci (tabulka settings,
  hodnoty v DB mají přednost před .env; tajemství maskovaná ve formuláři).
- 2026-09-17: HR = vlastní Drupal (JSON:API, `/jsonapi/user/user`), mapování polí
  konfigurovatelné; pull tlačítkem/cronem, push přes API zůstává.
- 2026-09-17: nasazení na server (Docker); přístupy dodá Michael později.
- 2026-09-17: HR sync = obecné rozhraní: `POST /api/v1/hr/employees` (upsert
  seznamu) + CSV import; konkrétní HR konektor až podle toho, který systém
  firma používá (otevřená otázka pro Michaela).
- 2026-09-17: audit log na každou změnu (kdo, co, kdy).
- 2026-09-17: data zůstávají na Macu; do balíčků smí jít kód, ne obsah DB.

- 2026-09-17: po ověření v prohlížeči doladěno operátorem (actor z guards,
  bez plošných except, Unicode font v PDF, kopie protokolu na PROTOCOL_COPY_TO).
- 2026-09-17: poučení pro kontrakty: jeden testovací soubor = jeden kontrakt;
  testy importují cizí moduly jen líně; kontrakt šablony musí vyjmenovat
  proměnné a klíče; blueprint bez vlastního url_prefix, když ho připojuje app.

- 2026-09-17: katalog: štítky (volné, barevné, N:N), lokality, faktury jako
  sdílená entita (jedna faktura ↔ mnoho zařízení), přílohy k zařízení i
  faktuře (PDF/obrázky v ATTACHMENTS_DIR, DB drží jen metadata), stav kusu
  (new/good/worn/broken), záruka, nákladové středisko.
- 2026-09-17: inventární čísla generuje aplikace: prefix podle typu
  (TAG_PREFIXES, konfigurovatelné) + pořadí (TAG_PAD); ruční číslo je možné.
  Štítek 50×25 mm s QR na `/a/<tag>` (přihlášený admin → detail, držitel →
  moje zařízení); tisk z prohlížeče, nebo ZPL přímo na síťovou tiskárnu
  (LABEL_PRINTER_HOST:9100).
- 2026-09-17: příjem zboží = jeden formulář (typ, model, počet, faktura,
  lokalita, štítky) → N zařízení → obrazovka pro načtení sériových čísel
  čtečkou → štítky k tisku.
- 2026-09-17: gluecode (admin/catalog/taxonomy blueprinty, services/factory)
  píše operátor ručně — modely ho vyrábějí hůř, než ho jde specifikovat;
  kontrakty zůstávají pro repozitáře, služby a testy. Každý kontrakt má
  akceptační test (C-017 bez něj „prošel“ beze změny souboru).

- 2026-09-17: veřejný repozitář github.com/ChaosPalda42/hwdesk; klikací
  statická ukázka na https://chaospalda42.github.io/hwdesk/ (Actions →
  Pages při každém pushi na main; `tools/snapshot.py` ji staví z aplikace
  se smyšlenými daty). Stejný postup jako u webu školy.

- 2026-09-17 (Michael): „vše, co ukazuje číslo, je odkaz na seznam s tím
  filtrem“ — statistiky na Přehledu, sloupce typ/lokalita/štítek, audit.
  Nastavení má vlastní podmenu (Obecné, Přihlášení, E-mail, HR, Inventární
  čísla a štítky, Lokality, Štítky); číselníky patří pod Nastavení, ne do
  hlavního menu. Každá sekce ukládá jen své klíče.

- 2026-09-21: modely běží na llama-serveru (:8080), LM Studio odstraněno;
  jediný model `qwen3.8-flash-next` (coder/tester bez thinkingu, 4/4 zelené,
  140 s/kontrakt). factory.toml bez [roles.*] = výchozí harnessu.

## Pravidla projektu
- Stack: Python 3.11+, Flask 3, sqlite3 (raw SQL, `sqlite3.Row`), Jinja2, reportlab, msal.
- Testy: `uv run pytest -q`
- Repozitáře dostávají `sqlite3.Connection` konstruktorem a po každém zápisu volají `conn.commit()`.
- Služby dostávají repozitáře konstruktorem; žádné výchozí hodnoty pro DB/repozitář.
- Routy staví služby per request: `XService(XRepository(get_db()))`; `get_db` je v `src/db.py`.
- Chybové odpovědi API: JSON `{"error": "<message>"}` se stavem 400/403/404/409; nikdy 2xx s chybou.
- Časy v UTC ISO 8601 (`datetime.now(timezone.utc).isoformat()`); do DB jako text.
- E-maily uživatelů vždy malými písmeny.
- UI česky; kód, identifikátory a komentáře anglicky.

## Jak spustit
- `uv run factory run --project ~/projects/hwdesk` — běh Factory
- `uv run factory status --project ~/projects/hwdesk` — stav
- `uv run factory packets --project ~/projects/hwdesk` — balíčky; `factory answer <id> …`
- Aplikace lokálně: `HWDESK_ADMIN_EMAILS=ja@firma.cz uv run flask --app src.app run`
