const API_BASE = window.location.origin.includes('http') ? window.location.origin : 'http://127.0.0.1:8001';

let products = [];
let cart = {}; // product_id -> quantity

async function init() {
    try {
        const response = await fetch(`${API_BASE}/api/products`);
        if (response.ok) {
            products = await response.json();
            renderProducts();
        }
    } catch (err) {
        console.warn('API fetch failed, falling back to mock catalog', err);
        products = [
            { id: "P1", name: "Mechanical Keyboard", price: 1200.0, stock: 20 },
            { id: "P2", name: "Ergonomic Mouse", price: 600.0, stock: 35 },
            { id: "P3", name: "USB-C Hub", price: 400.0, stock: 15 },
            { id: "P4", name: "27-inch 4K Monitor", price: 15000.0, stock: 8 },
        ];
        renderProducts();
    }

    document.getElementById('customerTier').addEventListener('change', updateCartUI);
    document.getElementById('checkoutBtn').addEventListener('click', placeOrder);
}

function renderProducts() {
    const grid = document.getElementById('productsGrid');
    const badge = document.getElementById('catalogCount');
    badge.textContent = `${products.length} products available`;

    grid.innerHTML = products.map(product => `
        <div class="product-card">
            <div>
                <h3>${product.name}</h3>
                <div class="product-meta">
                    <div class="product-price">₹${product.price.toFixed(2)}</div>
                    <div class="product-stock">In stock: ${product.stock} units</div>
                </div>
            </div>
            <button class="btn btn-primary" onclick="addToCart('${product.id}')">Add to Cart</button>
        </div>
    `).join('');
}

window.addToCart = function(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    cart[productId] = (cart[productId] || 0) + 1;
    updateCartUI();
};

function updateCartUI() {
    const cartList = document.getElementById('cartItemsList');
    const items = Object.entries(cart);

    if (items.length === 0) {
        cartList.innerHTML = '<p class="empty-state">Your cart is empty. Add items from the catalog.</p>';
        document.getElementById('subtotalAmount').textContent = '₹0.00';
        document.getElementById('discountAmount').textContent = '- ₹0.00';
        document.getElementById('totalAmount').textContent = '₹0.00';
        document.getElementById('checkoutBtn').disabled = true;
        return;
    }

    let subtotal = 0;
    cartList.innerHTML = items.map(([id, qty]) => {
        const prod = products.find(p => p.id === id);
        const itemTotal = prod.price * qty;
        subtotal += itemTotal;
        return `
            <div class="cart-item-row">
                <span>${prod.name} × ${qty}</span>
                <span>₹${itemTotal.toFixed(2)}</span>
            </div>
        `;
    }).join('');

    const customerTier = document.getElementById('customerTier').value;
    const isPremium = customerTier === 'C_PREMIUM';

    // Apply SRS discount rule: Premium gets 20% if subtotal > 1000
    let discount = 0;
    if (isPremium && subtotal > 1000) {
        discount = subtotal * 0.20;
    }

    const total = subtotal - discount;

    document.getElementById('subtotalAmount').textContent = `₹${subtotal.toFixed(2)}`;
    document.getElementById('discountAmount').textContent = `- ₹${discount.toFixed(2)}`;
    document.getElementById('totalAmount').textContent = `₹${total.toFixed(2)}`;
    document.getElementById('checkoutBtn').disabled = false;
}

async function placeOrder() {
    const customerId = document.getElementById('customerTier').value;
    const items = Object.entries(cart).map(([productId, quantity]) => ({
        product_id: productId,
        quantity: quantity
    }));

    const notif = document.getElementById('orderNotification');
    try {
        const response = await fetch(`${API_BASE}/api/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                customer_id: customerId,
                items: items
            })
        });

        if (response.ok) {
            const result = await response.json();
            notif.className = 'order-notification success';
            notif.innerHTML = `Order <strong>#${result.order_id.slice(0, 8)}</strong> confirmed! Total: ₹${result.total.toFixed(2)} saved to SQLite.`;
            cart = {};
            updateCartUI();
        } else {
            const err = await response.json();
            alert(`Order error: ${err.detail || 'Could not place order'}`);
        }
    } catch (err) {
        alert('Could not connect to backend server.');
    }
}

document.addEventListener('DOMContentLoaded', init);
