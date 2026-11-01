from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from algotrd.data.config import Settings
from algotrd.data.providers.groww import GrowwAuthenticationError, GrowwClient


def settings(**kwargs):
    return Settings(groww_access_token=SecretStr("token-not-for-output"), groww_max_retries=1, **kwargs)


def test_historical_request_uses_only_supported_endpoint_and_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/historical/candles"
        assert request.headers["authorization"] == "Bearer token-not-for-output"
        assert request.url.params["groww_symbol"] == "NSE-NIFTY"
        return httpx.Response(200, json={"status": "SUCCESS", "payload": {"candles": []}})
    client = GrowwClient(settings(), transport=httpx.MockTransport(handler))
    result = client.historical_candles(groww_symbol="NSE-NIFTY", start=__import__("datetime").datetime(2025, 1, 1), end=__import__("datetime").datetime(2025, 1, 1))
    assert result["status"] == "SUCCESS"


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_errors_are_explicit(status: int):
    client = GrowwClient(settings(), transport=httpx.MockTransport(lambda _: httpx.Response(status)))
    with pytest.raises(GrowwAuthenticationError):
        client.historical_candles(groww_symbol="NSE-NIFTY", start=__import__("datetime").datetime(2025, 1, 1), end=__import__("datetime").datetime(2025, 1, 1))


def test_429_is_retried(monkeypatch):
    calls = 0
    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, json={"status": "SUCCESS", "payload": {"candles": []}})
    monkeypatch.setattr("algotrd.data.providers.groww.time.sleep", lambda _: None)
    client = GrowwClient(settings(), transport=httpx.MockTransport(handler))
    result = client.historical_candles(groww_symbol="NSE-NIFTY", start=__import__("datetime").datetime(2025, 1, 1), end=__import__("datetime").datetime(2025, 1, 1))
    assert result["status"] == "SUCCESS" and calls == 2
