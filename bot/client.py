"""HTTP transport layer for Binance Futures Testnet API."""

import hashlib
import hmac
import time
import traceback
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bot.config import settings
from bot.logging_config import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Raised when Binance returns a non-2xx response with an error payload."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class NetworkError(Exception):
    """Raised on connection failures, timeouts, or exhausted retries."""


def _sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive fields before logging.

    Args:
        params: Raw query parameters.

    Returns:
        Copy with ``signature`` replaced by ``***``.
    """
    clean = dict(params)
    for key in ("signature",):
        if key in clean:
            clean[key] = "***"
    return clean


class BinanceClient:
    """Low-level authenticated HTTP client for Binance Futures Testnet.

    Handles HMAC-SHA256 signing, automatic retries with exponential backoff,
    and structured logging of every request/response cycle.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.api_key
        self._api_secret = api_secret or settings.api_secret
        self._base_url = base_url or settings.base_url

        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

        retry_strategy = Retry(
            total=settings.max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        """Add timestamp, recvWindow, and HMAC-SHA256 signature to params.

        Args:
            params: Existing query parameters.

        Returns:
            Params dict with ``timestamp``, ``recvWindow``, and ``signature`` added.
        """
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = settings.recv_window
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        signed: bool = True,
    ) -> dict[str, Any]:
        """Execute an authenticated HTTP request against the API.

        Args:
            method: HTTP verb (``GET``, ``POST``, ``DELETE``).
            endpoint: API path, e.g. ``/fapi/v1/order``.
            params: Query/body parameters.
            signed: Whether to attach HMAC signature.

        Returns:
            Parsed JSON response body.

        Raises:
            APIError: Binance returned an error payload.
            NetworkError: Connection or timeout failure.
        """
        params = dict(params) if params else {}
        if signed:
            params = self._sign(params)

        url = f"{self._base_url}{endpoint}"
        safe_params = _sanitize_params(params)
        logger.info(">>> %s %s params=%s", method.upper(), endpoint, safe_params)

        try:
            response = self._session.request(
                method=method.upper(),
                url=url,
                params=params if method.upper() == "GET" else None,
                data=urlencode(params) if method.upper() != "GET" else None,
                timeout=settings.timeout,
            )
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Network failure %s %s: %s\n%s",
                method.upper(),
                endpoint,
                exc,
                traceback.format_exc(),
            )
            raise NetworkError(f"Request to {endpoint} failed: {exc}") from exc

        logger.info(
            "<<< %s %s status=%d body=%s",
            method.upper(),
            endpoint,
            response.status_code,
            response.text[:500],
        )

        if response.status_code >= 400:
            try:
                body = response.json()
                code = body.get("code", response.status_code)
                msg = body.get("msg", response.text)
            except ValueError:
                code = response.status_code
                msg = response.text
            logger.error("API error %s %s: [%d] %s", method.upper(), endpoint, code, msg)
            raise APIError(code=code, message=msg)

        return response.json()

    def get(
        self, endpoint: str, params: dict[str, Any] | None = None, signed: bool = True
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Send a signed GET request.

        Args:
            endpoint: API path.
            params: Query parameters.
            signed: Whether to sign the request.

        Returns:
            Parsed JSON response.
        """
        return self._request("GET", endpoint, params, signed)

    def post(
        self, endpoint: str, params: dict[str, Any] | None = None, signed: bool = True
    ) -> dict[str, Any]:
        """Send a signed POST request.

        Args:
            endpoint: API path.
            params: Body parameters.
            signed: Whether to sign the request.

        Returns:
            Parsed JSON response.
        """
        return self._request("POST", endpoint, params, signed)

    def delete(
        self, endpoint: str, params: dict[str, Any] | None = None, signed: bool = True
    ) -> dict[str, Any]:
        """Send a signed DELETE request.

        Args:
            endpoint: API path.
            params: Query parameters.
            signed: Whether to sign the request.

        Returns:
            Parsed JSON response.
        """
        return self._request("DELETE", endpoint, params, signed)
