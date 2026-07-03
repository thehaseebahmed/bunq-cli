"""Tests for `bunq payments draft ...` commands."""

from click.testing import CliRunner

import bunq_cli.commands.draft_payments as dp
from bunq_cli.client import BunqAPIError
from bunq_cli.main import cli

FAKE_STATE = {"user_id": "1", "session_token": "tok", "private_key_pem": "pem"}


def _invoke(monkeypatch, fake_request, args, state=FAKE_STATE):
    monkeypatch.setattr(dp, "load_state", lambda: state)
    monkeypatch.setattr(dp, "request", fake_request)
    return CliRunner().invoke(cli, args)


def test_draft_create(monkeypatch):
    calls = {}

    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        calls["method"], calls["path"], calls["body"] = method, path, body
        return {"Response": [{"DraftPayment": {"id": 42, "status": "PENDING"}}]}

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "create",
        "--account-id", "123", "--iban", "NL00BUNQ0123456789",
        "--amount", "12.50", "--description", "test",
    ])

    assert result.exit_code == 0, result.output
    assert calls["method"] == "POST"
    assert calls["path"] == "/user/1/monetary-account/123/draft-payment"
    assert calls["body"]["entries"][0]["amount"] == {"value": "12.50", "currency": "EUR"}
    assert calls["body"]["entries"][0]["counterparty_alias"] == {
        "type": "IBAN", "value": "NL00BUNQ0123456789"
    }
    assert calls["body"]["number_of_required_accepts"] == 1
    assert "42" in result.output


def test_draft_create_bad_amount(monkeypatch):
    result = _invoke(monkeypatch, lambda *a, **k: None, [
        "payments", "draft", "create",
        "--account-id", "123", "--iban", "NL00BUNQ0123456789",
        "--amount", "not-a-number",
    ])

    assert result.exit_code != 0
    assert "--amount" in result.output


def test_draft_create_requires_exactly_one_alias(monkeypatch):
    result = _invoke(monkeypatch, lambda *a, **k: None, [
        "payments", "draft", "create",
        "--account-id", "123", "--amount", "1.00",
    ])
    assert result.exit_code != 0
    assert "exactly one" in result.output

    result = _invoke(monkeypatch, lambda *a, **k: None, [
        "payments", "draft", "create",
        "--account-id", "123", "--amount", "1.00",
        "--iban", "NL00BUNQ0123456789", "--email", "a@b.com",
    ])
    assert result.exit_code != 0
    assert "exactly one" in result.output


def test_draft_list_empty(monkeypatch):
    result = _invoke(monkeypatch, lambda *a, **k: {"Response": []}, [
        "payments", "draft", "list", "--account-id", "123",
    ])
    assert result.exit_code == 0
    assert "No draft payments found." in result.output


def test_draft_list_pagination(monkeypatch):
    batch_full = [{"DraftPayment": {"id": i, "status": "PENDING", "entries": []}} for i in range(200)]
    batch_partial = [{"DraftPayment": {"id": 1000, "status": "PENDING", "entries": []}}]
    calls = []

    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        calls.append(path)
        if len(calls) == 1:
            return {"Response": batch_full}
        return {"Response": batch_partial}

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "list", "--account-id", "123", "--all",
    ])

    assert result.exit_code == 0, result.output
    assert len(calls) == 2
    assert "older_id=199" in calls[1]


def test_draft_status_filter(monkeypatch):
    drafts = [
        {"DraftPayment": {"id": 1, "status": "PENDING", "entries": []}},
        {"DraftPayment": {"id": 2, "status": "ACCEPTED", "entries": []}},
    ]

    result = _invoke(monkeypatch, lambda *a, **k: {"Response": drafts}, [
        "payments", "draft", "list", "--account-id", "123", "--status", "ACCEPTED", "--all",
    ])

    assert result.exit_code == 0
    assert "2" in result.output
    assert " 1 " not in result.output


def test_draft_get(monkeypatch):
    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        assert method == "GET"
        assert path == "/user/1/monetary-account/123/draft-payment/456"
        return {"Response": [{"DraftPayment": {
            "id": 456, "status": "PENDING", "number_of_required_accepts": 1,
            "created": "2026-01-01", "updated": "2026-01-01",
            "entries": [{
                "amount": {"value": "12.50", "currency": "EUR"},
                "counterparty_alias": {"value": "NL00BUNQ0123456789"},
                "description": "test",
            }],
        }}]}

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "get", "--account-id", "123", "456",
    ])

    assert result.exit_code == 0, result.output
    assert "456" in result.output
    assert "PENDING" in result.output


def test_draft_get_not_found(monkeypatch):
    result = _invoke(monkeypatch, lambda *a, **k: {"Response": []}, [
        "payments", "draft", "get", "--account-id", "123", "456",
    ])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_draft_accept(monkeypatch):
    calls = {}

    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        calls["method"], calls["path"], calls["body"] = method, path, body
        return {"Response": [{"DraftPayment": {"id": 456, "status": "ACCEPTED"}}]}

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "accept", "--account-id", "123", "456",
    ])

    assert result.exit_code == 0, result.output
    assert calls["method"] == "PUT"
    assert calls["path"] == "/user/1/monetary-account/123/draft-payment/456"
    assert calls["body"] == {"status": "ACCEPTED"}
    assert "ACCEPTED" in result.output


def test_draft_reject(monkeypatch):
    calls = {}

    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        calls["body"] = body
        return {"Response": [{"DraftPayment": {"id": 456, "status": "REJECTED"}}]}

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "reject", "--account-id", "123", "456",
    ])

    assert result.exit_code == 0, result.output
    assert calls["body"] == {"status": "REJECTED"}
    assert "REJECTED" in result.output


def test_draft_accept_api_error(monkeypatch):
    def fake_request(method, path, *, body=None, token=None, private_pem=None):
        raise BunqAPIError(["draft payment is not PENDING"], 400)

    result = _invoke(monkeypatch, fake_request, [
        "payments", "draft", "accept", "--account-id", "123", "456",
    ])

    assert result.exit_code != 0
    assert "not PENDING" in result.output


def test_no_active_session(monkeypatch):
    result = _invoke(monkeypatch, lambda *a, **k: None, [
        "payments", "draft", "list", "--account-id", "123",
    ], state={})

    assert result.exit_code != 0
    assert "No active session" in result.output
