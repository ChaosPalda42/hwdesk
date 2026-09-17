import json
from pathlib import Path

import pytest

from src.services.tokens import HandoverTokens


def test_tokens_round_trip_and_expiry():
    tokens = HandoverTokens(secret="s3cret", max_age_hours=1)
    token = tokens.issue(handover_id=42, email="jan@f.cz")
    assert tokens.verify(token) == {"handover_id": 42, "email": "jan@f.cz"}
    assert tokens.verify(token + "x") is None
    assert HandoverTokens(secret="other", max_age_hours=1).verify(token) is None
    stale = HandoverTokens(secret="s3cret", max_age_hours=0)
    assert stale.verify(stale.issue(handover_id=1, email="a@b"), now_offset_seconds=3600) is None
