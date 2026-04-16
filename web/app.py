"""FastAPI web dashboard for Primetrade trading bot.

Exposes REST endpoints that wrap the existing ``bot/`` modules,
plus serves a single-page trading dashboard at the root URL.
"""

import os
import sys

# Ensure the project root is on sys.path so ``bot`` is importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from bot.client import APIError, BinanceClient, NetworkError
from bot.orders import OrderManager, friendly_error
from bot.validators import ValidationError

app = FastAPI(title="Primetrade Dashboard", version="1.0.0")

# Static files and templates
_here = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_here, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_here, "templates"))


def _get_manager() -> OrderManager:
    """Build a fresh OrderManager backed by the environment credentials."""
    return OrderManager(BinanceClient())


# ── Request / Response schemas ──────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    """JSON body for placing an order."""
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None


class OrderOut(BaseModel):
    """Serialised order for API responses."""
    order_id: int
    symbol: str
    side: str
    order_type: str
    status: str
    orig_qty: str
    executed_qty: str
    price: str
    stop_price: str


class MessageOut(BaseModel):
    """Generic status message."""
    message: str


# ── Pages ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the single-page trading dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


# ── API Routes ──────────────────────────────────────────────────────

@app.post("/api/orders", response_model=OrderOut)
async def api_place_order(body: PlaceOrderRequest):
    """Place a new futures order via the Binance Testnet API."""
    try:
        manager = _get_manager()
        resp = manager.place_order(
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            quantity=body.quantity,
            price=body.price,
            stop_price=body.stop_price,
        )
        return OrderOut(
            order_id=resp.order_id,
            symbol=resp.symbol,
            side=resp.side,
            order_type=resp.order_type,
            status=resp.status,
            orig_qty=resp.orig_qty,
            executed_qty=resp.executed_qty,
            price=resp.price,
            stop_price=resp.stop_price,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.reason}")
    except APIError as exc:
        msg = friendly_error(exc.code, exc.message)
        raise HTTPException(status_code=400, detail=f"[{exc.code}] {msg}")
    except NetworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/orders")
async def api_get_orders(symbol: Optional[str] = None):
    """List open orders, optionally filtered by symbol."""
    try:
        manager = _get_manager()
        orders = manager.get_open_orders(symbol)
        return [
            OrderOut(
                order_id=o.order_id,
                symbol=o.symbol,
                side=o.side,
                order_type=o.order_type,
                status=o.status,
                orig_qty=o.orig_qty,
                executed_qty=o.executed_qty,
                price=o.price,
                stop_price=o.stop_price,
            )
            for o in orders
        ]
    except (ValidationError, APIError, NetworkError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/orders/{symbol}/{order_id}", response_model=MessageOut)
async def api_cancel_order(symbol: str, order_id: int):
    """Cancel a specific open order by its ID."""
    try:
        manager = _get_manager()
        manager.cancel_order(symbol, order_id)
        return MessageOut(message=f"Order {order_id} on {symbol} cancelled successfully.")
    except APIError as exc:
        msg = friendly_error(exc.code, exc.message)
        raise HTTPException(status_code=400, detail=f"[{exc.code}] {msg}")
    except NetworkError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
