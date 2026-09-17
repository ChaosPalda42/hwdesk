import json
from pathlib import Path

import pytest

from src.services.protocol_pdf import render_protocol_pdf


def test_protocol_pdf_is_a_pdf_with_the_facts(tmp_path):
    out = tmp_path / "HP-2026-000001.pdf"
    render_protocol_pdf(
        path=str(out),
        protocol_number="HP-2026-000001",
        kind="handover",
        company="Firma s.r.o.",
        employee={"display_name": "Jan Novák", "email": "jan@f.cz", "department": "IT"},
        asset={"asset_tag": "NB-0001", "type": "notebook", "brand": "Dell", "model": "Latitude 5540", "serial_number": "SN1"},
        created_by="admin@f.cz",
        confirmed_at="2026-09-17T10:00:00+00:00",
        note="včetně nabíječky",
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000
