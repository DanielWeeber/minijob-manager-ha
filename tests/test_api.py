"""Tests for form parsing and PKCE."""

import base64
import json

import pytest

from custom_components.minijob_manager.api import (
    MinijobAuthError,
    _pkce,
    gp_id_from_token,
    parse_form_action,
)


def test_parse_form_action_unescapes():
    page = '<form id="form" class="x" action="https://iam/x?a=1&amp;b=2" method="post">'
    assert parse_form_action(page) == "https://iam/x?a=1&b=2"
    assert parse_form_action("<html></html>") is None


def test_pkce_lengths():
    verifier, challenge = _pkce()
    assert 43 <= len(verifier) <= 128
    assert len(challenge) == 43


def _jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"h.{body}.s"


def test_gp_id_from_token():
    token = _jwt({"gprollen": [{"geschaeftspartnerId": 123, "rolle": "ADMIN"}]})
    assert gp_id_from_token(token) == "123"
    with pytest.raises(MinijobAuthError):
        gp_id_from_token(_jwt({}))
