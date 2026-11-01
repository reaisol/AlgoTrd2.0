from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any

import httpx

from ..config import Settings

BASE_URL = "https://api.groww.in"


class GrowwError(RuntimeError):
    pass


class GrowwAuthenticationError(GrowwError):
    pass


class GrowwClient:
    """Small, read-only client for documented Groww historical endpoints."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.client = httpx.Client(base_url=BASE_URL, timeout=settings.groww_timeout_seconds, transport=transport)
        self._last_request = 0.0
        self._access_token_cache: str | None = None

    def close(self) -> None:
        self.client.close()

    def _throttle(self) -> None:
        pause = 1 / self.settings.groww_rate_limit_per_second
        delay = pause - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()

    def access_token(self) -> str:
        if self._access_token_cache:
            return self._access_token_cache
        if self.settings.groww_access_token:
            self._access_token_cache = self.settings.groww_access_token.get_secret_value()
            return self._access_token_cache
        if not self.settings.groww_api_key or not self.settings.groww_api_secret:
            raise GrowwAuthenticationError("set GROWW_ACCESS_TOKEN or GROWW_API_KEY and GROWW_API_SECRET")
        timestamp = str(int(time.time()))
        secret = self.settings.groww_api_secret.get_secret_value()
        checksum = hashlib.sha256(f"{secret}{timestamp}".encode()).hexdigest()
        response = self._request(
            "POST", "/v1/token/api/access",
            headers={"Authorization": f"Bearer {self.settings.groww_api_key.get_secret_value()}"},
            json={"key_type": "approval", "checksum": checksum, "timestamp": timestamp},
        )
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise GrowwAuthenticationError("Groww did not return an access token")
        self._access_token_cache = token
        return token

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.settings.groww_max_retries + 1):
            try:
                self._throttle()
                response = self.client.request(method, path, **kwargs)
                if response.status_code in (401, 403):
                    raise GrowwAuthenticationError(f"Groww authentication failed ({response.status_code})")
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.settings.groww_max_retries:
                        time.sleep(min(2 ** attempt, 8))
                        continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise GrowwError("Groww returned a non-object JSON response")
                if data.get("status") == "FAILURE":
                    error = data.get("error", {})
                    raise GrowwError(f"Groww failure: {error.get('code', 'unknown')}")
                return data
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < self.settings.groww_max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                break
        raise GrowwError("Groww request failed after bounded retries") from last_error

    def historical_candles(self, *, groww_symbol: str, start: datetime, end: datetime, interval: str = "1minute", segment: str = "CASH") -> dict[str, Any]:
        token = self.access_token()
        return self._request(
            "GET", "/v1/historical/candles",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "X-API-VERSION": "1.0"},
            params={
                "exchange": "NSE", "segment": segment, "groww_symbol": groww_symbol,
                "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end.strftime("%Y-%m-%d %H:%M:%S"), "candle_interval": interval,
            },
        )

    def expiries(self, *, underlying: str, year: int, month: int | None = None) -> dict[str, Any]:
        token = self.access_token(); params={"exchange":"NSE","underlying_symbol":underlying,"year":year}
        if month is not None: params["month"] = month
        return self._request("GET", "/v1/historical/expiries", headers={"Authorization":f"Bearer {token}","Accept":"application/json","X-API-VERSION":"1.0"}, params=params)

    def contracts(self, *, underlying: str, expiry: str) -> dict[str, Any]:
        token = self.access_token()
        return self._request("GET", "/v1/historical/contracts", headers={"Authorization":f"Bearer {token}","Accept":"application/json","X-API-VERSION":"1.0"}, params={"exchange":"NSE","underlying_symbol":underlying,"expiry_date":expiry})
