"""Order placement and response mapping for Binance Futures."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from bot.client import APIError, BinanceClient
from bot.logging_config import get_logger
from bot.validators import (
    OrderType,
    Side,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

logger = get_logger(__name__)

ERROR_CODE_MAP: dict[int, str] = {
    -1121: "Invalid symbol — check the trading pair name.",
    -2010: "Insufficient margin balance to place this order.",
    -1111: "Precision issue — reduce decimal places on quantity.",
    -1013: "Price or quantity is outside the allowed range.",
}


class OrderRequest(BaseModel):
    """Validated order payload ready for submission."""

    symbol: str
    side: Side
    order_type: OrderType = Field(alias="type")
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = Field(default=None, alias="stopPrice")

    model_config = {"populate_by_name": True}


class OrderResponse(BaseModel):
    """Normalised response from a successful order placement."""

    order_id: int = Field(alias="orderId")
    symbol: str
    side: str
    order_type: str = Field(alias="type")
    status: str
    orig_qty: str = Field(alias="origQty")
    executed_qty: str = Field(alias="executedQty")
    price: str = "0"
    stop_price: str = Field(default="0", alias="stopPrice")

    model_config = {"populate_by_name": True}


def friendly_error(code: int, fallback: str) -> str:
    """Map a Binance error code to a readable message.

    Args:
        code: Binance numeric error code.
        fallback: Default message when the code is unmapped.

    Returns:
        Human-friendly error string.
    """
    return ERROR_CODE_MAP.get(code, fallback)


class OrderManager:
    """High-level order operations backed by a ``BinanceClient``.

    Args:
        client: Pre-configured HTTP client instance.
    """

    ENDPOINT = "/fapi/v1/order"
    OPEN_ORDERS_ENDPOINT = "/fapi/v1/openOrders"

    def __init__(self, client: BinanceClient) -> None:
        self._client = client

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
    ) -> OrderResponse:
        """Validate inputs and submit an order to Binance.

        Args:
            symbol: Trading pair, e.g. ``BTCUSDT``.
            side: ``BUY`` or ``SELL``.
            order_type: ``MARKET``, ``LIMIT``, or ``STOP_MARKET``.
            quantity: Order size.
            price: Limit price (required for LIMIT).
            stop_price: Trigger price (required for STOP_MARKET).

        Returns:
            Parsed ``OrderResponse`` on success.

        Raises:
            ValidationError: If any input fails validation.
            APIError: If Binance rejects the order.
            NetworkError: On transport failure.
        """
        symbol = validate_symbol(symbol)
        validated_side = validate_side(side)
        validated_type = validate_order_type(order_type)
        quantity = validate_quantity(quantity)
        price = validate_price(price, validated_type)
        stop_price = validate_stop_price(stop_price, validated_type)

        params: dict[str, Any] = {
            "symbol": symbol,
            "side": validated_side.value,
            "type": validated_type.value,
            "quantity": quantity,
        }

        if validated_type == OrderType.LIMIT:
            params["price"] = price
            params["timeInForce"] = "GTC"

        if validated_type == OrderType.STOP_MARKET:
            params["stopPrice"] = stop_price

        logger.info(
            "Placing %s %s order: %s qty=%s price=%s stop=%s",
            validated_side.value,
            validated_type.value,
            symbol,
            quantity,
            price,
            stop_price,
        )

        try:
            raw = self._client.post(self.ENDPOINT, params)
        except APIError as exc:
            msg = friendly_error(exc.code, exc.message)
            logger.error("Order rejected [%d]: %s", exc.code, msg)
            raise APIError(code=exc.code, message=msg) from exc

        response = OrderResponse.model_validate(raw)
        logger.info("Order filled: id=%d status=%s", response.order_id, response.status)
        return response

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        """Fetch open orders, optionally filtered by symbol.

        Args:
            symbol: Trading pair filter. If ``None``, returns all.

        Returns:
            List of ``OrderResponse`` objects.
        """
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = validate_symbol(symbol)

        raw = self._client.get(self.OPEN_ORDERS_ENDPOINT, params)
        if isinstance(raw, list):
            return [OrderResponse.model_validate(item) for item in raw]
        return []

    def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        """Cancel a specific order by ID.

        Args:
            symbol: Trading pair the order belongs to.
            order_id: Binance-assigned order identifier.

        Returns:
            Raw cancellation response from the API.

        Raises:
            APIError: If cancellation fails.
        """
        symbol = validate_symbol(symbol)
        params: dict[str, Any] = {
            "symbol": symbol,
            "orderId": order_id,
        }
        logger.info("Cancelling order %d on %s", order_id, symbol)

        try:
            result = self._client.delete(self.ENDPOINT, params)
        except APIError as exc:
            msg = friendly_error(exc.code, exc.message)
            logger.error("Cancel failed [%d]: %s", exc.code, msg)
            raise APIError(code=exc.code, message=msg) from exc

        logger.info("Order %d cancelled successfully", order_id)
        return result
