"""Tests for form parsing and PKCE."""

from custom_components.minijob_manager.api import _pkce, parse_form_action


def test_parse_form_action_unescapes():
    page = '<form id="form" class="x" action="https://iam/x?a=1&amp;b=2" method="post">'
    assert parse_form_action(page) == "https://iam/x?a=1&b=2"
    assert parse_form_action("<html></html>") is None


def test_pkce_lengths():
    verifier, challenge = _pkce()
    assert 43 <= len(verifier) <= 128
    assert len(challenge) == 43
