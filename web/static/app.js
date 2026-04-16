/**
 * Primetrade Dashboard — Client-side logic.
 *
 * Handles order form submission, live orders refresh, cancel actions,
 * and dynamic UI state (side toggle, conditional fields, toasts).
 */

const API = '/api/orders';

// ── DOM refs ───────────────────────────────────────────────────
const orderForm     = document.getElementById('orderForm');
const submitBtn     = document.getElementById('submitBtn');
const btnText       = submitBtn.querySelector('.btn-text');
const btnLoader     = submitBtn.querySelector('.btn-loader');
const sideToggle    = document.getElementById('sideToggle');
const orderTypeSel  = document.getElementById('orderType');
const priceGroup    = document.getElementById('priceGroup');
const stopPriceGrp  = document.getElementById('stopPriceGroup');
const ordersBody    = document.getElementById('ordersBody');
const refreshBtn    = document.getElementById('refreshBtn');
const filterInput   = document.getElementById('filterSymbol');
const statusDot     = document.getElementById('statusDot');
const statusText    = document.getElementById('statusText');
const toastEl       = document.getElementById('toast');
const clockEl       = document.getElementById('clock');

let currentSide = 'BUY';

// ── Utilities ──────────────────────────────────────────────────

function showToast(message, type = 'success') {
    toastEl.textContent = message;
    toastEl.className = `toast ${type}`;
    toastEl.style.display = 'block';
    setTimeout(() => { toastEl.style.display = 'none'; }, 4000);
}

function setLoading(loading) {
    submitBtn.disabled = loading;
    btnText.style.display = loading ? 'none' : 'inline';
    btnLoader.style.display = loading ? 'inline-block' : 'none';
}

function setConnected(ok) {
    statusDot.className = ok ? 'status-dot connected' : 'status-dot';
    statusText.textContent = ok ? 'Connected' : 'Disconnected';
}

// ── Clock ──────────────────────────────────────────────────────

function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Side toggle ────────────────────────────────────────────────

sideToggle.addEventListener('click', (e) => {
    const btn = e.target.closest('.toggle-btn');
    if (!btn) return;
    sideToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentSide = btn.dataset.value;

    // Update submit button style
    if (currentSide === 'SELL') {
        submitBtn.classList.add('sell-mode');
        btnText.textContent = 'Place Sell Order';
    } else {
        submitBtn.classList.remove('sell-mode');
        btnText.textContent = 'Place Order';
    }
});

// ── Order type → conditional fields ────────────────────────────

orderTypeSel.addEventListener('change', () => {
    const t = orderTypeSel.value;
    priceGroup.style.display    = t === 'LIMIT' ? 'flex' : 'none';
    stopPriceGrp.style.display  = t === 'STOP_MARKET' ? 'flex' : 'none';
});

// ── Place order ────────────────────────────────────────────────

orderForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    setLoading(true);

    const symbol    = document.getElementById('symbol').value.trim().toUpperCase();
    const quantity  = parseFloat(document.getElementById('quantity').value);
    const orderType = orderTypeSel.value;
    const price     = orderType === 'LIMIT' ? parseFloat(document.getElementById('price').value) : null;
    const stopPrice = orderType === 'STOP_MARKET' ? parseFloat(document.getElementById('stopPrice').value) : null;

    const payload = {
        symbol,
        side: currentSide,
        order_type: orderType,
        quantity,
    };
    if (price !== null)     payload.price = price;
    if (stopPrice !== null) payload.stop_price = stopPrice;

    try {
        const res = await fetch(API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Order placement failed');
        }

        const data = await res.json();
        showToast(`Order ${data.order_id} placed — ${data.status}`, 'success');
        orderForm.reset();
        currentSide = 'BUY';
        sideToggle.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
        sideToggle.querySelector('[data-value="BUY"]').classList.add('active');
        submitBtn.classList.remove('sell-mode');
        btnText.textContent = 'Place Order';
        priceGroup.style.display = 'none';
        stopPriceGrp.style.display = 'none';

        // Refresh the orders table
        await fetchOrders();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading(false);
    }
});

// ── Fetch & render orders ──────────────────────────────────────

async function fetchOrders() {
    const filter = filterInput.value.trim().toUpperCase();
    const url = filter ? `${API}?symbol=${encodeURIComponent(filter)}` : API;

    refreshBtn.classList.add('spinning');

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch orders');

        const orders = await res.json();
        setConnected(true);
        renderOrders(orders);
    } catch (err) {
        setConnected(false);
        ordersBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="8">
                    <div class="empty-state">
                        <p style="color:var(--accent-red)">⚠ ${err.message}</p>
                    </div>
                </td>
            </tr>`;
    } finally {
        refreshBtn.classList.remove('spinning');
    }
}

function renderOrders(orders) {
    if (!orders.length) {
        ordersBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="8">
                    <div class="empty-state">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                        </svg>
                        <p>No open orders</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    ordersBody.innerHTML = orders.map(o => `
        <tr>
            <td style="color:var(--accent-cyan)">${o.order_id}</td>
            <td style="color:var(--text-primary);font-weight:500">${o.symbol}</td>
            <td class="side-${o.side.toLowerCase()}">${o.side}</td>
            <td>${o.order_type}</td>
            <td>${o.orig_qty}</td>
            <td>${o.price === '0' ? '—' : o.price}</td>
            <td><span class="status-badge ${o.status.toLowerCase()}">${o.status}</span></td>
            <td>
                <button class="btn-cancel" onclick="cancelOrder('${o.symbol}', ${o.order_id})" title="Cancel order">
                    ✕
                </button>
            </td>
        </tr>
    `).join('');
}

// ── Cancel order ───────────────────────────────────────────────

async function cancelOrder(symbol, orderId) {
    if (!confirm(`Cancel order ${orderId} on ${symbol}?`)) return;

    try {
        const res = await fetch(`${API}/${symbol}/${orderId}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Cancel failed');
        }
        showToast(`Order ${orderId} cancelled`, 'success');
        await fetchOrders();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Filter ─────────────────────────────────────────────────────

let filterTimeout;
filterInput.addEventListener('input', () => {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(fetchOrders, 400);
});

// ── Refresh button ─────────────────────────────────────────────

refreshBtn.addEventListener('click', fetchOrders);

// ── Auto-refresh every 10s ─────────────────────────────────────

setInterval(fetchOrders, 10000);

// ── Initial load ───────────────────────────────────────────────

fetchOrders();
