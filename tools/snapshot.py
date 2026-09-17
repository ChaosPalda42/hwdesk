"""Static, clickable snapshot of HW Desk with sample data — for GitHub Pages.

Runs the app in-process (dev auth, outbox e-mail, temporary SQLite), seeds
fictional data, crawls every GET page as the admin and as an employee and
writes them under `site/` with links rewritten to the published prefix.
Forms are disabled in the snapshot; a banner says so.

    uv run python tools/snapshot.py [--prefix /hwdesk] [--out site]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import re
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BANNER = """
<div style="position:sticky;top:0;z-index:1000;background:#fff7e6;border-bottom:1px solid #f0c36d;color:#5a3d00;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;padding:8px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
  <b>Statická ukázka HW Desk</b> — vzorová data, tlačítka a formuláře jsou vypnuté.
  <span>Pohled: <a href="{prefix}/admin/index.html">správce</a> · <a href="{prefix}/my/index.html">zaměstnanec</a> · <a href="{prefix}/my/potvrzeni.html">potvrzení převzetí</a></span>
  <a href="https://github.com/ChaosPalda42/hwdesk" style="margin-left:auto">zdrojový kód</a>
</div>
<script>
document.addEventListener('submit', function (e) {{ e.preventDefault(); alert('Statická ukázka: akce jsou vypnuté.'); }}, true);
</script>
"""

SKIP_PREFIXES = ("/auth/", "/static/", "/api/", "/admin/attachments/", "/admin/labels/zpl", "/my/protocols/", "/handovers/confirm/")


def seed(app):
    """Fictional data: a few employees, tags, locations, invoices, assets, one confirmed and one pending handover."""
    from src.db import connect
    from src.services.factory import build_asset_service, build_attachment_service, build_handover_service

    client = app.test_client()
    key = {"Authorization": "Bearer snapshot"}
    j = lambda path, body: client.post(path, json=body, headers=key)
    j("/api/v1/hr/employees", {"employees": [
        {"email": "jan.novak@firma.cz", "display_name": "Jan Novák", "department": "IT", "manager_email": "eva.kralova@firma.cz"},
        {"email": "petra.mala@firma.cz", "display_name": "Petra Malá", "department": "Obchod"},
        {"email": "eva.kralova@firma.cz", "display_name": "Eva Králová", "department": "Vedení"},
        {"email": "tomas.dvorak@firma.cz", "display_name": "Tomáš Dvořák", "department": "Výroba"},
    ]})
    for name, color in (("Nákup 2026", "blue"), ("VIP", "purple"), ("Zápůjčka", "yellow"), ("Home office", "green"), ("K reklamaci", "red")):
        j("/api/v1/tags", {"name": name, "color": color})
    for name, address in (("Praha – HQ", "Na Poříčí 1, Praha 1"), ("Brno – sklad", "Vídeňská 120, Brno"), ("Home office", "")):
        j("/api/v1/locations", {"name": name, "address": address})
    j("/api/v1/invoices", {"number": "FV-2026-0117", "supplier": "Alza.cz", "issued_at": "2026-08-28", "total": 148500})
    j("/api/v1/invoices", {"number": "FV-2026-0120", "supplier": "Datart", "issued_at": "2026-09-03", "total": 7470})
    j("/api/v1/invoices", {"number": "2026/00412", "supplier": "T-Mobile", "issued_at": "2026-07-15", "total": 65880})
    assets = [
        ("notebook", "Dell", "Latitude 5450", "5CG4123XYZ", 29700, 1, 1, ["Nákup 2026"], "new", "2029-08-28"),
        ("notebook", "Dell", "Latitude 5450", "5CG4123ABC", 29700, 1, 1, ["Nákup 2026"], "new", "2029-08-28"),
        ("notebook", "Dell", "Latitude 5450", "5CG4123DEF", 29700, 1, 1, ["Nákup 2026", "VIP"], "new", "2029-08-28"),
        ("notebook", "Apple", "MacBook Pro 14 M4", "C02XK1ABCD", 59900, 1, 1, ["VIP"], "good", "2028-01-10"),
        ("notebook", "Lenovo", "ThinkPad T14 Gen 3", "PF3ABCD1", 24500, 2, None, ["Zápůjčka"], "worn", "2026-10-02"),
        ("monitor", "LG", "27UL850", "2011NTQ7", 8990, 1, None, [], "good", "2027-03-01"),
        ("monitor", "Dell", "U2723QE", "CN0ABC123", 12900, 3, None, ["Home office"], "good", "2027-11-20"),
        ("phone", "Apple", "iPhone 16", "F2LX1ABCD", 21990, 1, 3, [], "new", "2028-07-15"),
        ("phone", "Samsung", "Galaxy S24", "R5CX2ABCD", 18990, 1, 3, [], "good", "2026-10-15"),
        ("phone", "Apple", "iPhone 13", "DNPX3ABCD", 0, 2, None, ["K reklamaci"], "broken", ""),
        ("mouse", "Logitech", "MX Master 3S", "LG-001", 2490, 1, 2, ["Nákup 2026"], "new", "2028-09-03"),
        ("mouse", "Logitech", "MX Master 3S", "LG-002", 2490, 1, 2, ["Nákup 2026"], "new", "2028-09-03"),
        ("mouse", "Logitech", "MX Master 3S", "LG-003", 2490, 1, 2, ["Nákup 2026"], "new", "2028-09-03"),
        ("keyboard", "Logitech", "MX Keys", "KB-77", 2790, 1, None, [], "good", ""),
        ("dock", "Dell", "WD22TB4", "CN0DOCK1", 6900, 1, None, [], "good", "2027-05-05"),
        ("headset", "Jabra", "Evolve2 65", "JB-4451", 5490, 1, None, ["Home office"], "good", ""),
        ("tablet", "Apple", "iPad Air", "DMPX4ABCD", 17990, 1, None, ["Zápůjčka"], "good", "2027-02-02"),
    ]
    ids = []
    for type_, brand, model, sn, price, loc, inv, tags, cond, warranty in assets:
        r = j("/api/v1/assets", {"type": type_, "brand": brand, "model": model, "serial_number": sn, "price": price,
                                 "location_id": loc, "invoice_id": inv, "tags": tags, "condition": cond,
                                 "warranty_until": warranty, "purchase_date": "2026-08-28" if inv == 1 else ""})
        assert r.status_code == 201, r.get_data(as_text=True)
        ids.append(r.get_json()["id"])
    client.post("/api/v1/invoices/1/attachments", headers=key, content_type="multipart/form-data",
                data={"kind": "invoice", "file": (io.BytesIO(b"%PDF-1.4 sample"), "FV-2026-0117.pdf", "application/pdf")})
    client.post(f"/api/v1/assets/{ids[3]}/attachments", headers=key, content_type="multipart/form-data",
                data={"kind": "photo", "file": (io.BytesIO(b"\x89PNG sample"), "macbook-predni.png", "image/png")})

    with app.app_context():
        db = connect(app.config["DATABASE"])
        handovers = build_handover_service(db)
        jan = handovers.employees.get_by_email("jan.novak@firma.cz")
        petra = handovers.employees.get_by_email("petra.mala@firma.cz")
        tomas = handovers.employees.get_by_email("tomas.dvorak@firma.cz")
        for asset_id in (ids[0], ids[5], ids[10]):
            h = handovers.start_handover("admin@firma.cz", asset_id, jan["id"], note="včetně nabíječky")
            handovers.confirm(handovers.tokens.issue(h["id"], jan["email"]), jan["email"])
        h = handovers.start_handover("admin@firma.cz", ids[7], tomas["id"])
        handovers.confirm(handovers.tokens.issue(h["id"], tomas["email"]), tomas["email"])
        pending = handovers.start_handover("admin@firma.cz", ids[3], petra["id"], note="MacBook + adaptér USB-C")
        handovers.start_return("admin@firma.cz", ids[5], note="výměna za větší monitor")
        build_asset_service(db).retire("admin@firma.cz", ids[9])
        token = handovers.tokens.issue(pending["id"], petra["email"])
        db.close()
    return token


def file_for(url: str) -> str:
    """Map a site URL to a file path inside the output directory."""
    parts = urlsplit(url)
    path = parts.path.strip("/")
    if not parts.query:
        return f"{path}/index.html" if path else "index.html"
    digest = hashlib.sha1(parts.query.encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", parts.query.lower()).strip("-")[:60]
    return f"{path}/q-{slug}-{digest}.html"


def crawl(client, start: list[str], seen: dict[str, str], out: Path, prefix: str, views: dict[str, str]):
    queue = deque(start)
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        resp = client.get(url, follow_redirects=True)
        if resp.status_code != 200 or not resp.mimetype.startswith("text/html"):
            seen[url] = ""
            continue
        target = views.get(url) or file_for(url)
        seen[url] = target
        body = resp.get_data(as_text=True)
        for href in re.findall(r'href="([^"#]+)"', body):
            href = html.unescape(href)
            if href.startswith("/") and not href.startswith(SKIP_PREFIXES) and href not in seen:
                queue.append(href)
        (out / target).parent.mkdir(parents=True, exist_ok=True)
        (out / target).write_text(body)


def rewrite(out: Path, seen: dict[str, str], prefix: str):
    for target in set(v for v in seen.values() if v):
        path = out / target
        body = path.read_text()

        def link(match):
            raw = html.unescape(match.group(2))
            mapped = seen.get(raw)
            if mapped:
                return f'{match.group(1)}="{prefix}/{mapped}"'
            if raw.startswith("/static/"):
                return f'{match.group(1)}="{prefix}{raw}"'
            if raw.startswith("/"):
                return f'{match.group(1)}="#"'
            return match.group(0)

        body = re.sub(r'(href|src|action)="([^"]+)"', link, body)
        body = body.replace("<body>", "<body>" + BANNER.format(prefix=prefix), 1)
        path.write_text(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="/hwdesk")
    parser.add_argument("--out", default="site")
    args = parser.parse_args()
    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    from src.app import create_app

    tmp = Path(tempfile.mkdtemp())
    app = create_app({
        "TESTING": True, "DATABASE": str(tmp / "demo.db"), "OUTBOX_DIR": str(tmp / "outbox"),
        "PROTOCOL_DIR": str(tmp / "protocols"), "ATTACHMENTS_DIR": str(tmp / "attachments"),
        "AUTH_MODE": "dev", "EMAIL_MODE": "outbox", "ADMIN_EMAILS": ["admin@firma.cz"],
        "API_KEYS": ["snapshot"], "BASE_URL": "https://hwdesk.example", "COMPANY_NAME": "Ukázková firma s.r.o.",
        "SECRET_KEY": "snapshot-only",
    })
    token = seed(app)
    seen: dict[str, str] = {}

    admin = app.test_client()
    admin.post("/auth/dev-login", data={"email": "admin@firma.cz"})
    crawl(admin, ["/admin", "/admin/assets", "/admin/intake", "/admin/labels?ids=11,12,13", "/admin/assets/new",
                  "/admin/invoices/new", "/admin/assets/1/edit"], seen, out, args.prefix, {"/admin": "admin/index.html"})

    employee = app.test_client()
    employee.post("/auth/dev-login", data={"email": "petra.mala@firma.cz"})
    seen_employee: dict[str, str] = {}
    crawl(employee, ["/", f"/handovers/confirm/{token}"], seen_employee, out, args.prefix,
          {"/": "my/index.html", f"/handovers/confirm/{token}": "my/potvrzeni.html"})
    seen.update({k: v for k, v in seen_employee.items() if v})

    rewrite(out, seen, args.prefix)
    shutil.copytree(ROOT / "static", out / "static")
    (out / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={args.prefix}/admin/index.html">'
        f'<a href="{args.prefix}/admin/index.html">HW Desk – ukázka</a>'
    )
    (out / ".nojekyll").write_text("")
    print(f"{sum(1 for v in seen.values() if v)} pages → {out}")


if __name__ == "__main__":
    main()
