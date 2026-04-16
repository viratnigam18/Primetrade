"""Unit tests for order placement and error mapping."""

from unittest.mock import MagicMock, patch

import pytest

from bot.client import APIError
from bot.orders import OrderManager, OrderResponse, friendly_error
from bot.validators import ValidationError


MOCK_MARKET_RESPONSE = {
    "orderId": 100001,
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "status": "FILLED",
    "origQty": "0.001",
    "executedQty": "0.001",
    "price": "0",
}

MOCK_LIMIT_RESPONSE = {
    "orderId": 100002,
    "symbol": "ETHUSDT",
    "side": "SELL",
    "type": "LIMIT",
    "status": "NEW",
    "origQty": "0.5",
    "executedQty": "0",
    "price": "3500.00",
}

MOCK_STOP_RESPONSE = {
    "orderId": 100003,
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP_MARKET",
    "status": "NEW",
    "origQty": "0.01",
    "executedQty": "0",
    "price": "0",
    "stopPrice": "45000.00",
}


@pytest.fixture()
def mock_client():
    """Return a mock BinanceClient for order testing."""
    return MagicMock()


@pytest.fixture()
def manager(mock_client):
    """Return an OrderManager backed by the mock client."""
    return OrderManager(mock_client)


class TestPlaceOrder:
    """Test order submission across all supported types."""

    def test_market_buy(self, manager, mock_client):
        mock_client.post.return_value = MOCK_MARKET_RESPONSE
        result = manager.place_order("BTCUSDT", "BUY", "MARKET", 0.001)

        assert isinstance(result, OrderResponse)
        assert result.order_id == 100001
        assert result.status == "FILLED"
        assert result.executed_qty == "0.001"
        mock_client.post.assert_called_once()

    def test_limit_sell(self, manager, mock_client):
        mock_client.post.return_value = MOCK_LIMIT_RESPONSE
        result = manager.place_order("ETHUSDT", "SELL", "LIMIT", 0.5, price=3500.0)

        assert result.order_id == 100002
        assert result.order_type == "LIMIT"
        assert result.price == "3500.00"

    def test_stop_market_sell(self, manager, mock_client):
        mock_client.post.return_value = MOCK_STOP_RESPONSE
        result = manager.place_order(
            "BTCUSDT", "SELL", "STOP_MARKET", 0.01, stop_price=45000.0
        )

        assert result.order_id == 100003
        assert result.stop_price == "45000.00"

    def test_limit_without_price_raises(self, manager):
        with pytest.raises(ValidationError, match="price"):
            manager.place_order("BTCUSDT", "BUY", "LIMIT", 0.01)

    def test_stop_market_without_stop_price_raises(self, manager):
        with pytest.raises(ValidationError, match="stopPrice"):
            manager.place_order("BTCUSDT", "SELL", "STOP_MARKET", 0.01)

    def test_invalid_symbol_raises(self, manager):
        with pytest.raises(ValidationError, match="symbol"):
            manager.place_order("INVALID", "BUY", "MARKET", 0.01)

    def test_zero_quantity_raises(self, manager):
        with pytest.raises(ValidationError, match="quantity"):
            manager.place_order("BTCUSDT", "BUY", "MARKET", 0)


class TestErrorMapping:
    """Verify Binance error code translation."""

    def test_invalid_symbol_code(self):
        msg = friendly_error(-1121, "fallback")
        assert "Invalid symbol" in msg

    def test_insufficient_balance_code(self):
        msg = friendly_error(-2010, "fallback")
        assert "balance" in msg.lower()

    def test_precision_code(self):
        msg = friendly_error(-1111, "fallback")
        assert "Precision" in msg

    def test_range_code(self):
        msg = friendly_error(-1013, "fallback")
        assert "range" in msg

    def test_unknown_code_returns_fallback(self):
        msg = friendly_error(-9999, "something went wrong")
        assert msg == "something went wrong"

    def test_api_error_remapped_on_placement(self, manager, mock_client):
        mock_client.post.side_effect = APIError(code=-1121, message="Invalid symbol.")
        with pytest.raises(APIError) as exc_info:
            manager.place_order("BTCUSDT", "BUY", "MARKET", 0.001)
        assert "Invalid symbol" in exc_info.value.message


class TestOpenOrders:
    """Test fetching open orders."""

    def test_open_orders_returns_list(self, manager, mock_client):
        mock_client.get.return_value = [MOCK_LIMIT_RESPONSE]
        orders = manager.get_open_orders("ETHUSDT")
        assert len(orders) == 1
        assert orders[0].order_id == 100002

    def test_open_orders_empty(self, manager, mock_client):
        mock_client.get.return_value = []
        orders = manager.get_open_orders()
        assert orders == []


class TestCancelOrder:
    """Test order cancellation."""

    def test_cancel_success(self, manager, mock_client):
        mock_client.delete.return_value = {"orderId": 100001, "status": "CANCELED"}
        result = manager.cancel_order("BTCUSDT", 100001)
        assert result["status"] == "CANCELED"

    def test_cancel_api_error(self, manager, mock_client):
        mock_client.delete.side_effect = APIError(code=-2011, message="Unknown order.")
        with pytest.raises(APIError):
            manager.cancel_order("BTCUSDT", 999999)
