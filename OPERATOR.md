# OPERATOR — hwdesk

## Co a proč
Správa firemního HW (notebooky, telefony, monitory, periferie): evidence, předávací protokoly potvrzované e-mailem, přehled pro zaměstnance, API, přihlášení přes Microsoft 365, synchronizace s HR.

## Kde jsme
Viz STATE.md (generuje harness). Poslední shrnutí operátora: —

## Rozhodnutí
- 2026-09-17: projekt založen.

## Pravidla projektu
- Stack: python
- Testy: `uv run pytest -q`
- Nic nad rámec harnessu; obecná pravidla jsou v ~/factory/docs.

## Jak spustit
- `factory run` — spustí běh (kontrakty → workeři → brány → checkpointy)
- `factory status` — stav, otevřené balíčky
- `factory packets` — balíčky čekající na rozhodnutí; `factory answer <id> …`
