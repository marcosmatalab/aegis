"""Tests for the OpenAI error envelope, param rendering, and exception handlers."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aegis.gateway.errors import (
    ProviderNotConfiguredError,
    _param_from_loc,
    error_response,
    register_exception_handlers,
)
from aegis.gateway.schemas import ChatCompletionRequest


# --- _param_from_loc (direct unit tests) ------------------------------------ #
def test_param_from_loc_simple_field():
    assert _param_from_loc(("body", "model")) == "model"


def test_param_from_loc_nested_index():
    assert _param_from_loc(("body", "messages", 0, "role")) == "messages[0].role"


def test_param_from_loc_all_int_is_none():
    assert _param_from_loc(("body", 12)) is None


def test_param_from_loc_empty_is_none():
    assert _param_from_loc(()) is None


# --- error_response envelope shape ------------------------------------------ #
def test_error_response_includes_all_keys():
    resp = error_response(status_code=400, message="bad", type="invalid_request_error")
    body = json.loads(resp.body)
    assert resp.status_code == 400
    assert body["error"] == {
        "message": "bad",
        "type": "invalid_request_error",
        "param": None,
        "code": None,
    }


# --- handlers wired into a minimal app -------------------------------------- #
@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/echo")
    async def echo(req: ChatCompletionRequest):  # triggers RequestValidationError
        return {"ok": True}

    @app.get("/boom-provider")
    async def boom_provider():
        raise ProviderNotConfiguredError("Provider 'openai' is not configured in F1.")

    @app.get("/boom-generic")
    async def boom_generic():
        raise ValueError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


def _assert_envelope(resp):
    err = resp.json()["error"]
    assert set(err) == {"message", "type", "param", "code"}
    return err


def test_validation_missing_field_returns_400(client):
    resp = client.post("/echo", json={})
    assert resp.status_code == 400
    err = _assert_envelope(resp)
    assert err["type"] == "invalid_request_error"
    assert err["param"] == "model"  # first missing required field


def test_validation_nested_param(client):
    resp = client.post(
        "/echo",
        json={"model": "m", "messages": [{"role": "wizard", "content": "x"}]},
    )
    assert resp.status_code == 400
    err = _assert_envelope(resp)
    assert err["param"] == "messages[0].role"


def test_validation_malformed_json_param_is_none(client):
    resp = client.post(
        "/echo",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
    err = _assert_envelope(resp)
    assert err["type"] == "invalid_request_error"
    assert err["param"] is None


def test_aegis_provider_error_renders_cleanly(client):
    resp = client.get("/boom-provider")
    assert resp.status_code == 500
    err = _assert_envelope(resp)
    assert err["type"] == "api_error"
    assert err["code"] == "provider_not_configured"
    assert "openai" in err["message"]
    assert "Traceback" not in resp.text  # no internal leak


def test_unhandled_exception_returns_opaque_500(client):
    resp = client.get("/boom-generic")
    assert resp.status_code == 500
    err = _assert_envelope(resp)
    assert err["type"] == "api_error"
    assert "kaboom" not in resp.text  # internal detail not leaked
