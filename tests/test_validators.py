"""Unit tests for input validators."""

import pytest

from bot.validators import (
    OrderType,
    Side,
    ValidationError,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)


class TestValidateSymbol:
    """Symbol validation edge cases."""

    def test_valid_usdt_pair(self):
        assert validate_symbol("BTCUSDT") == "BTCUSDT"

    def test_valid_busd_pair(self):
        assert validate_symbol("ETHBUSD") == "ETHBUSD"

    def test_valid_btc_pair(self):
        assert validate_symbol("ETHBTC") == "ETHBTC"

    def test_lowercase_normalised(self):
        assert validate_symbol("btcusdt") == "BTCUSDT"

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError, match="symbol"):
            validate_symbol("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError, match="symbol"):
            validate_symbol("   ")

    def test_invalid_quote_asset(self):
        with pytest.raises(ValidationError, match="symbol"):
            validate_symbol("BTCEUR")

    def test_numeric_characters_rejected(self):
        with pytest.raises(ValidationError, match="symbol"):
            validate_symbol("BTC123USDT")

    def test_spaces_in_middle_rejected(self):
        with pytest.raises(ValidationError, match="symbol"):
            validate_symbol("BTC USDT")


class TestValidateQuantity:
    """Quantity validation boundary cases."""

    def test_valid_quantity(self):
        assert validate_quantity(1.5) == 1.5

    def test_integer_quantity(self):
        assert validate_quantity(10) == 10.0

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="quantity"):
            validate_quantity(0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="quantity"):
            validate_quantity(-0.5)

    def test_max_precision_accepted(self):
        assert validate_quantity(0.00000001) == 0.00000001

    def test_over_precision_rejected(self):
        with pytest.raises(ValidationError, match="quantity"):
            validate_quantity(0.000000001)


class TestValidatePrice:
    """Price validation for LIMIT orders."""

    def test_price_required_for_limit(self):
        with pytest.raises(ValidationError, match="price"):
            validate_price(None, OrderType.LIMIT)

    def test_valid_price_for_limit(self):
        assert validate_price(50000.0, OrderType.LIMIT) == 50000.0

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError, match="price"):
            validate_price(-100.0, OrderType.LIMIT)

    def test_price_optional_for_market(self):
        assert validate_price(None, OrderType.MARKET) is None


class TestValidateStopPrice:
    """Stop price validation for STOP_MARKET orders."""

    def test_stop_price_required(self):
        with pytest.raises(ValidationError, match="stopPrice"):
            validate_stop_price(None, OrderType.STOP_MARKET)

    def test_valid_stop_price(self):
        assert validate_stop_price(48000.0, OrderType.STOP_MARKET) == 48000.0

    def test_negative_stop_price_rejected(self):
        with pytest.raises(ValidationError, match="stopPrice"):
            validate_stop_price(-1.0, OrderType.STOP_MARKET)

    def test_stop_price_optional_for_limit(self):
        assert validate_stop_price(None, OrderType.LIMIT) is None


class TestValidateSide:
    """Side validation."""

    def test_buy(self):
        assert validate_side("BUY") == Side.BUY

    def test_sell_lowercase(self):
        assert validate_side("sell") == Side.SELL

    def test_invalid_side(self):
        with pytest.raises(ValidationError, match="side"):
            validate_side("HOLD")


class TestValidateOrderType:
    """Order type validation."""

    def test_market(self):
        assert validate_order_type("MARKET") == OrderType.MARKET

    def test_limit_lowercase(self):
        assert validate_order_type("limit") == OrderType.LIMIT

    def test_stop_market(self):
        assert validate_order_type("STOP_MARKET") == OrderType.STOP_MARKET

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="orderType"):
            validate_order_type("TRAILING_STOP")
