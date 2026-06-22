"""Tests for the duck-typed Anthropic error mapping (no SDK import)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aegis.gateway.errors import UpstreamProviderError
from aegis.gateway.providers.anthropic_translate import map_anthropic_error


class _StatusError(Exception):
    def __init__(self, status_code, retry_after=None):
        super().__init__("boom")
        self.status_code = status_code
        if retry_after is not None:
            self.response = SimpleNamespace(headers={"retry-after": retry_after})


# class names matter for the no-status branch (duck-typed on the name)
class APITimeoutError(Exception):
    status_code = None


class APIConnectionError(Exception):
    status_code = None


@pytest.mark.parametrize(
    "status,exp_status,exp_type,exp_code",
    [
        (401, 401, "authentication_error", "upstream_authentication"),
        (403, 403, "permission_error", "upstream_permission_denied"),
        (404, 404, "not_found_error", "upstream_model_not_found"),
        (400, 400, "invalid_request_error", "upstream_invalid_request"),
        (429, 429, "rate_limit_error", "rate_limit_exceeded"),
        (413, 502, "api_error", "upstream_error"),  # unmapped 4xx -> catch-all 502
        (500, 502, "api_error", "upstream_error"),  # 5xx -> 502 Bad Gateway
        (529, 502, "api_error", "upstream_error"),  # overloaded -> 502
    ],
)
def test_status_mapping(status, exp_status, exp_type, exp_code):
    err = map_anthropic_error(_StatusError(status))
    assert isinstance(err, UpstreamProviderError)
    assert err.status_code == exp_status
    assert err.type == exp_type
    assert err.code == exp_code


def test_rate_limit_surfaces_retry_after():
    err = map_anthropic_error(_StatusError(429, retry_after="30"))
    assert err.status_code == 429
    assert "30" in err.message


def test_rate_limit_without_retry_after():
    err = map_anthropic_error(_StatusError(429))
    assert err.status_code == 429
    assert "retry after" not in err.message


def test_timeout_maps_to_504():
    err = map_anthropic_error(APITimeoutError())
    assert err.status_code == 504
    assert err.code == "upstream_timeout"


def test_connection_maps_to_502():
    err = map_anthropic_error(APIConnectionError())
    assert err.status_code == 502
    assert err.code == "upstream_unavailable"


def test_unknown_no_status_maps_to_502():
    err = map_anthropic_error(Exception("mystery"))
    assert err.status_code == 502
    assert err.code == "upstream_error"


def test_message_does_not_leak_exception_text():
    # the original exception carries internal text ('secret-detail'); the mapped,
    # client-facing message must stay generic and never echo it
    err = map_anthropic_error(_StatusError(500))
    assert "boom" not in err.message
    assert err.message == "upstream provider error"
