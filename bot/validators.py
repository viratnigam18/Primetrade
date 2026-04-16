"""Input validation for order parameters."""

import re
from enum import Enum


class ValidationError(Exception):
    """Raised when an order parameter fails validation.

    Attributes:
        field: Name of the invalid parameter.
        reason: Human-readable explanation.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class Side(str, Enum):
    """Order direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Supported order types."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


_VALID_QUOTE_ASSETS = ("USDT", "BUSD", "BTC")
_SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,20}$")


def validate_symbol(symbol: str) -> str:
    """Ensure symbol is uppercase, no whitespace, and ends in a valid quote asset.

    Args:
        symbol: Trading pair, e.g. ``BTCUSDT``.

    Returns:
        The validated symbol string.

    Raises:
        ValidationError: If the symbol is malformed.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValidationError("symbol", "Symbol must be a non-empty string.")

    symbol = symbol.strip().upper()

    if " " in symbol or "\t" in symbol:
        raise ValidationError("symbol", "Symbol must not contain whitespace.")

    if not _SYMBOL_PATTERN.match(symbol):
        raise ValidationError(
            "symbol", "Symbol must contain only uppercase letters (2-20 chars)."
        )

    if not any(symbol.endswith(q) for q in _VALID_QUOTE_ASSETS):
        raise ValidationError(
            "symbol",
            f"Symbol must end in one of {', '.join(_VALID_QUOTE_ASSETS)}.",
        )

    return symbol


def validate_quantity(quantity: float) -> float:
    """Ensure quantity is a positive number with at most 8 decimal places.

    Args:
        quantity: Order quantity.

    Returns:
        The validated quantity.

    Raises:
        ValidationError: If quantity is non-positive or over-precise.
    """
    if not isinstance(quantity, (int, float)):
        raise ValidationError("quantity", "Quantity must be a number.")

    if quantity <= 0:
        raise ValidationError("quantity", "Quantity must be greater than zero.")

    text = f"{quantity:.10f}".rstrip("0")
    if "." in text:
        decimals = len(text.split(".")[1])
        if decimals > 8:
            raise ValidationError(
                "quantity", "Quantity must have at most 8 decimal places."
            )

    return float(quantity)


def validate_price(price: float | None, order_type: str) -> float | None:
    """Validate price; required for LIMIT orders.

    Args:
        price: Limit price, or ``None`` for non-LIMIT orders.
        order_type: One of ``MARKET``, ``LIMIT``, ``STOP_MARKET``.

    Returns:
        The validated price or ``None``.

    Raises:
        ValidationError: If price is missing/invalid for a LIMIT order.
    """
    if order_type == OrderType.LIMIT:
        if price is None:
            raise ValidationError("price", "Price is required for LIMIT orders.")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValidationError("price", "Price must be a positive number.")
    elif price is not None:
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValidationError("price", "Price must be a positive number.")
    return price


def validate_stop_price(stop_price: float | None, order_type: str) -> float | None:
    """Validate stopPrice; required for STOP_MARKET orders.

    Args:
        stop_price: Trigger price, or ``None`` for non-STOP_MARKET orders.
        order_type: One of ``MARKET``, ``LIMIT``, ``STOP_MARKET``.

    Returns:
        The validated stop price or ``None``.

    Raises:
        ValidationError: If stop price is missing/invalid for a STOP_MARKET order.
    """
    if order_type == OrderType.STOP_MARKET:
        if stop_price is None:
            raise ValidationError(
                "stopPrice", "Stop price is required for STOP_MARKET orders."
            )
        if not isinstance(stop_price, (int, float)) or stop_price <= 0:
            raise ValidationError("stopPrice", "Stop price must be a positive number.")
    elif stop_price is not None:
        if not isinstance(stop_price, (int, float)) or stop_price <= 0:
            raise ValidationError("stopPrice", "Stop price must be a positive number.")
    return stop_price


def validate_side(side: str) -> Side:
    """Verify side is BUY or SELL.

    Args:
        side: Order side string.

    Returns:
        The matching ``Side`` enum member.

    Raises:
        ValidationError: If side is unrecognised.
    """
    try:
        return Side(side.upper())
    except (ValueError, AttributeError):
        raise ValidationError("side", "Side must be BUY or SELL.")


def validate_order_type(order_type: str) -> OrderType:
    """Verify order type is MARKET, LIMIT, or STOP_MARKET.

    Args:
        order_type: Order type string.

    Returns:
        The matching ``OrderType`` enum member.

    Raises:
        ValidationError: If order type is unrecognised.
    """
    try:
        return OrderType(order_type.upper())
    except (ValueError, AttributeError):
        raise ValidationError(
            "orderType", "Order type must be MARKET, LIMIT, or STOP_MARKET."
        )
