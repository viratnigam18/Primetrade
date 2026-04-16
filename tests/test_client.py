"""Unit tests for the HTTP client layer."""

import hashlib
import hmac
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from bot.client import APIError, BinanceClient, NetworkError, _sanitize_params


@pytest.fixture()
def client():
    """Build a client with dummy credentials for unit testing."""
    with patch("bot.client.settings") as mock_settings:
        mock_settings.api_key = "test_api_key_12345"
        mock_settings.api_secret = "test_api_secret_67890"
        mock_settings.base_url = "https://testnet.binancefuture.com"
        mock_settings.timeout = 10
        mock_settings.max_retries = 3
        mock_settings.recv_window = 5000
        c = BinanceClient(
            api_key="test_api_key_12345",
            api_secret="test_api_secret_67890",
            base_url="https://testnet.binancefuture.com",
        )
        yield c


class TestSanitizeParams:
    """Verify sensitive parameter scrubbing."""

    def test_signature_is_masked(self):
        params = {"symbol": "BTCUSDT", "signature": "abc123secret"}
        clean = _sanitize_params(params)
        assert clean["signature"] == "***"
        assert clean["symbol"] == "BTCUSDT"

    def test_original_dict_unchanged(self):
        params = {"signature": "real_sig"}
        _sanitize_params(params)
        assert params["signature"] == "real_sig"


class TestSigning:
    """Verify HMAC-SHA256 signing logic."""

    def test_sign_adds_required_fields(self, client):
        params = {"symbol": "BTCUSDT"}
        signed = client._sign(params)
        assert "timestamp" in signed
        assert "recvWindow" in signed
        assert "signature" in signed
        assert signed["recvWindow"] == 5000

    def test_signature_is_valid_hmac(self, client):
        params = {"symbol": "ETHUSDT", "side": "BUY"}
        signed = client._sign(params)
        query_without_sig = "&".join(
            f"{k}={v}" for k, v in signed.items() if k != "signature"
        )
        expected = hmac.new(
            b"test_api_secret_67890",
            query_without_sig.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        assert signed["signature"] == expected


class TestRequest:
    """Verify request dispatching, error handling, and logging."""

    def test_get_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "50000.00"}
        mock_response.text = '{"price":"50000.00"}'

        client._session.request = MagicMock(return_value=mock_response)
        result = client.get("/fapi/v1/ticker/price", {"symbol": "BTCUSDT"})
        assert result["price"] == "50000.00"

    def test_post_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderId": 123, "status": "NEW"}
        mock_response.text = '{"orderId":123,"status":"NEW"}'

        client._session.request = MagicMock(return_value=mock_response)
        result = client.post("/fapi/v1/order", {"symbol": "BTCUSDT"})
        assert result["orderId"] == 123

    def test_api_error_raised_on_400(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"code": -1121, "msg": "Invalid symbol."}
        mock_response.text = '{"code":-1121,"msg":"Invalid symbol."}'

        client._session.request = MagicMock(return_value=mock_response)
        with pytest.raises(APIError) as exc_info:
            client.get("/fapi/v1/order", {"symbol": "INVALID"})
        assert exc_info.value.code == -1121

    def test_network_error_on_timeout(self, client):
        client._session.request = MagicMock(
            side_effect=requests.exceptions.Timeout("Connection timed out")
        )
        with pytest.raises(NetworkError):
            client.get("/fapi/v1/ticker/price")

    def test_network_error_on_connection_failure(self, client):
        client._session.request = MagicMock(
            side_effect=requests.exceptions.ConnectionError("DNS resolution failed")
        )
        with pytest.raises(NetworkError):
            client.post("/fapi/v1/order", {"symbol": "BTCUSDT"})

    def test_api_key_never_logged(self, client, caplog):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.text = "{}"

        client._session.request = MagicMock(return_value=mock_response)
        with caplog.at_level(logging.INFO):
            client.get("/fapi/v1/ping", {})

        full_log = caplog.text
        assert "test_api_key_12345" not in full_log
        assert "test_api_secret_67890" not in full_log

    def test_delete_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderId": 99, "status": "CANCELED"}
        mock_response.text = '{"orderId":99,"status":"CANCELED"}'

        client._session.request = MagicMock(return_value=mock_response)
        result = client.delete("/fapi/v1/order", {"symbol": "BTCUSDT", "orderId": 99})
        assert result["status"] == "CANCELED"
