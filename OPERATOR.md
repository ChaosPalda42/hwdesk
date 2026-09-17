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
Viz STATE.md. Poslední shrnutí operátora: kontrakty napsány 2026-09-17,
první běh spuštěn.

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
- 2026-09-17: HR sync = obecné rozhraní: `POST /api/v1/hr/employees` (upsert
  seznamu) + CSV import; konkrétní HR konektor až podle toho, který systém
  firma používá (otevřená otázka pro Michaela).
- 2026-09-17: audit log na každou změnu (kdo, co, kdy).
- 2026-09-17: data zůstávají na Macu; do balíčků smí jít kód, ne obsah DB.

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
