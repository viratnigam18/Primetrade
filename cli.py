"""Interactive CLI for the Binance Futures Testnet trading bot."""

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.client import APIError, BinanceClient, NetworkError
from bot.orders import OrderManager, friendly_error
from bot.validators import OrderType, Side, ValidationError

app = typer.Typer(
    name="primetrade",
    help="Binance Futures Testnet trading bot.",
    add_completion=False,
)
console = Console()


def _build_client() -> BinanceClient:
    """Instantiate the API client using environment configuration."""
    return BinanceClient()


def _prompt_if_missing(value: Optional[str], label: str, choices: list[str] | None = None) -> str:
    """Prompt the user interactively when a flag value was not provided.

    Args:
        value: Current value from CLI flag, possibly ``None``.
        label: Display name for the prompt.
        choices: Acceptable values; re-prompts on mismatch.

    Returns:
        Validated string value.
    """
    while not value:
        suffix = f" ({'/'.join(choices)})" if choices else ""
        value = console.input(f"[bold cyan]{label}{suffix}:[/] ").strip()
        if choices and value.upper() not in choices:
            console.print(f"[red]Invalid {label}. Must be one of: {', '.join(choices)}[/]")
            value = None
    return value


def _prompt_float(value: Optional[float], label: str, required: bool = False) -> Optional[float]:
    """Prompt for a numeric value with inline validation.

    Args:
        value: Current value from CLI flag, possibly ``None``.
        label: Display name for the prompt.
        required: Whether a value must be supplied.

    Returns:
        Validated float or ``None`` if not required and skipped.
    """
    if value is not None:
        return value
    while True:
        raw = console.input(f"[bold cyan]{label} {'(required)' if required else '(press Enter to skip)'}:[/] ").strip()
        if not raw and not required:
            return None
        if not raw and required:
            console.print(f"[red]{label} is required.[/]")
            continue
        try:
            parsed = float(raw)
            if parsed <= 0:
                console.print(f"[red]{label} must be positive.[/]")
                continue
            return parsed
        except ValueError:
            console.print(f"[red]Invalid number for {label}.[/]")


def _show_preview(symbol: str, side: str, order_type: str, quantity: float,
                  price: Optional[float], stop_price: Optional[float]) -> None:
    """Display a Rich table summarising the order before confirmation.

    Args:
        symbol: Trading pair.
        side: BUY or SELL.
        order_type: MARKET, LIMIT, or STOP_MARKET.
        quantity: Order quantity.
        price: Limit price if applicable.
        stop_price: Stop trigger price if applicable.
    """
    table = Table(title="Order Preview", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=14)
    table.add_column("Value", style="white")
    table.add_row("Symbol", symbol)
    table.add_row("Side", f"[green]{side}[/]" if side == "BUY" else f"[red]{side}[/]")
    table.add_row("Type", order_type)
    table.add_row("Quantity", str(quantity))
    if price is not None:
        table.add_row("Price", str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))
    console.print(table)


@app.command("place-order")
def place_order(
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: Optional[str] = typer.Option(None, "--side", help="BUY or SELL"),
    order_type: Optional[str] = typer.Option(None, "--type", "-t", help="MARKET, LIMIT, or STOP_MARKET"),
    quantity: Optional[float] = typer.Option(None, "--qty", "-q", help="Order quantity"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (LIMIT orders)"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price", help="Stop trigger price (STOP_MARKET orders)"),
) -> None:
    """Place a futures order with interactive prompts for missing fields."""
    symbol = _prompt_if_missing(symbol, "Symbol")
    side = _prompt_if_missing(side, "Side", ["BUY", "SELL"])
    order_type = _prompt_if_missing(order_type, "Order Type", ["MARKET", "LIMIT", "STOP_MARKET"])

    order_type_upper = order_type.upper()

    while quantity is None:
        quantity = _prompt_float(None, "Quantity", required=True)

    if order_type_upper == "LIMIT":
        price = _prompt_float(price, "Price", required=True)

    if order_type_upper == "STOP_MARKET":
        stop_price = _prompt_float(stop_price, "Stop Price", required=True)

    _show_preview(symbol.upper(), side.upper(), order_type_upper, quantity, price, stop_price)

    if not typer.confirm("Confirm order?", default=False):
        console.print("[yellow]Order cancelled by user.[/]")
        raise typer.Exit()

    try:
        client = _build_client()
        manager = OrderManager(client)
        response = manager.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
        console.print(Panel(
            f"[bold green]Order Placed Successfully[/]\n\n"
            f"  Order ID:      {response.order_id}\n"
            f"  Status:        {response.status}\n"
            f"  Executed Qty:  {response.executed_qty}",
            border_style="green",
        ))
    except ValidationError as exc:
        console.print(Panel(
            f"[bold red]Validation Error[/]\n\n"
            f"  Field:   {exc.field}\n"
            f"  Reason:  {exc.reason}",
            border_style="red",
        ))
        raise typer.Exit(code=1)
    except APIError as exc:
        msg = friendly_error(exc.code, exc.message)
        console.print(Panel(
            f"[bold red]Order Failed[/]\n\n"
            f"  Error Code:  {exc.code}\n"
            f"  Message:     {msg}",
            border_style="red",
        ))
        raise typer.Exit(code=1)
    except NetworkError as exc:
        console.print(Panel(
            f"[bold red]Network Error[/]\n\n  {exc}",
            border_style="red",
        ))
        raise typer.Exit(code=1)


@app.command("view-orders")
def view_orders(
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Filter by trading pair"),
) -> None:
    """Display all open orders as a formatted table."""
    try:
        client = _build_client()
        manager = OrderManager(client)
        orders = manager.get_open_orders(symbol)
    except (APIError, NetworkError, ValidationError) as exc:
        console.print(Panel(f"[bold red]Error[/]\n\n  {exc}", border_style="red"))
        raise typer.Exit(code=1)

    if not orders:
        console.print("[yellow]No open orders found.[/]")
        raise typer.Exit()

    table = Table(title="Open Orders", show_header=True, header_style="bold magenta")
    table.add_column("Order ID", style="cyan")
    table.add_column("Symbol", style="white")
    table.add_column("Side")
    table.add_column("Type")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Status")

    for order in orders:
        side_color = "green" if order.side == "BUY" else "red"
        table.add_row(
            str(order.order_id),
            order.symbol,
            f"[{side_color}]{order.side}[/]",
            order.order_type,
            order.orig_qty,
            order.price,
            order.status,
        )

    console.print(table)


@app.command("cancel-order")
def cancel_order(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair"),
    order_id: int = typer.Option(..., "--order-id", "-o", help="Order ID to cancel"),
) -> None:
    """Cancel an open order by its ID after user confirmation."""
    if not typer.confirm(f"Cancel order {order_id} on {symbol}?", default=False):
        console.print("[yellow]Cancellation aborted.[/]")
        raise typer.Exit()

    try:
        client = _build_client()
        manager = OrderManager(client)
        manager.cancel_order(symbol, order_id)
        console.print(Panel(
            f"[bold green]Order {order_id} cancelled successfully.[/]",
            border_style="green",
        ))
    except APIError as exc:
        msg = friendly_error(exc.code, exc.message)
        console.print(Panel(
            f"[bold red]Cancel Failed[/]\n\n"
            f"  Error Code:  {exc.code}\n"
            f"  Message:     {msg}",
            border_style="red",
        ))
        raise typer.Exit(code=1)
    except NetworkError as exc:
        console.print(Panel(f"[bold red]Network Error[/]\n\n  {exc}", border_style="red"))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
