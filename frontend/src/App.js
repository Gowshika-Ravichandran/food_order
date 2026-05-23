import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { useCart } from "./useCart";
import styles from "./App.module.css";

const API_BASE = "http://localhost:8000";
const CATEGORIES = ["All", "Pizza", "Burger", "Dosa", "Sandwich"];
const STATUS_FLOW = [
  { value: "pending", label: "Pending" },
  { value: "preparing", label: "Preparing" },
  { value: "out-for-delivery", label: "Ready" },
  { value: "delivered", label: "Delivered" },
];

function formatCurrency(value) {
  return `Rs. ${Number(value).toFixed(2)}`;
}

function getCategory(item) {
  const text = `${item.name} ${item.description}`.toLowerCase();
  return CATEGORIES.find((category) => category !== "All" && text.includes(category.toLowerCase())) || "Other";
}

function getDietType(item) {
  const text = `${item.name} ${item.description}`.toLowerCase();
  return /(chicken|mutton|fish|egg|meat|beef)/.test(text) ? "Non-Veg" : "Veg";
}

function getItemImage(item) {
  const category = getCategory(item);
  const images = {
    Pizza: "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=500&q=70",
    Burger: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=500&q=70",
    Dosa: "https://images.unsplash.com/photo-1668236543090-82eba5ee5976?auto=format&fit=crop&w=500&q=70",
    Sandwich: "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=500&q=70",
  };
  return images[category] || "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=500&q=70";
}

function isValidCustomerName(value) {
  if (value.trim() === "") {
    return true;
  }

  return /^[A-Za-z]+(?: [A-Za-z]+)*$/.test(value.trim());
}

function isValidWhatsAppNumber(value) {
  return /^\+[1-9]\d{9,14}$/.test(value.trim());
}

function nextStatusFor(currentStatus) {
  const index = STATUS_FLOW.findIndex((status) => status.value === currentStatus);
  return STATUS_FLOW[index + 1]?.value;
}

function normalizeName(value) {
  return value.trim().toLowerCase();
}

function uniqueMenuItems(menu) {
  const seen = new Set();
  return menu.filter((item) => {
    const key = normalizeName(item.name);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function MenuCard({ item, quantity, onIncrement, onDecrement }) {
  const dietType = getDietType(item);

  return (
    <article className={`${styles.menuCard} ${quantity > 0 ? styles.selectedCard : ""}`}>
      <div className={styles.imageWrap}>
        <img src={getItemImage(item)} alt="" loading="lazy" />
        {quantity > 0 && <span className={styles.quantityBadge}>{quantity}</span>}
        {item.id <= 2 && <span className={styles.popularBadge}>Popular</span>}
      </div>
      <div className={styles.cardBody}>
        <div className={styles.cardTitleRow}>
          <div>
            <h3>{item.name}</h3>
            <span className={dietType === "Veg" ? styles.vegTag : styles.nonVegTag}>{dietType}</span>
          </div>
          <strong>{formatCurrency(item.price)}</strong>
        </div>
        <p>{item.description}</p>
        <div className={styles.quantityControls} aria-label={`${item.name} quantity controls`}>
          <button type="button" onClick={() => onDecrement(item.name)} disabled={quantity === 0} aria-label={`Decrease ${item.name}`}>
            -
          </button>
          <span aria-live="polite">{quantity}</span>
          <button type="button" onClick={() => onIncrement(item.name)} aria-label={`Increase ${item.name}`}>
            +
          </button>
        </div>
      </div>
    </article>
  );
}

function CartPanel({ cart, orderForm, errors, isSending, orderFeedback, onFormChange, onRemove, onSubmit }) {
  const canSubmit = cart.items.length > 0 && !errors.customer_name && !errors.whatsapp_number && orderForm.customer_name && orderForm.whatsapp_number;

  return (
    <aside className={styles.cartPanel}>
      <div className={styles.panelHeader}>
        <div>
          <span className={styles.eyebrow}>Your Cart</span>
          <h2>Order Summary</h2>
        </div>
        <span className={styles.cartCount}>{cart.summary.totalItems}</span>
      </div>

      {cart.items.length === 0 ? (
        <div className={styles.emptyCart}>
          <strong>Your cart is empty</strong>
          <p>Add items from the menu to start your WhatsApp order.</p>
        </div>
      ) : (
        <div className={styles.cartItems}>
          {cart.items.map((item) => (
            <div className={styles.cartItem} key={item.name}>
              <div>
                <strong>{item.name}</strong>
                <span>Qty {item.quantity} x {formatCurrency(item.price)}</span>
              </div>
              <div>
                <b>{formatCurrency(item.subtotal)}</b>
                <button type="button" onClick={() => onRemove(item.name)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className={styles.billBox}>
        <div><span>Subtotal</span><strong>{formatCurrency(cart.summary.subtotal)}</strong></div>
        <div><span>GST 5%</span><strong>{formatCurrency(cart.summary.tax)}</strong></div>
        <div><span>Items</span><strong>{cart.summary.totalItems}</strong></div>
        <div><span>Est. prep time</span><strong>{cart.summary.prepTime || 0} min</strong></div>
        <div className={styles.totalRow}><span>Payable</span><strong>{formatCurrency(cart.summary.total)}</strong></div>
      </div>

      <form className={styles.orderForm} onSubmit={onSubmit}>
        <label>
          Customer Name
          <input
            value={orderForm.customer_name}
            onChange={(event) => onFormChange("customer_name", event.target.value)}
            aria-invalid={Boolean(errors.customer_name)}
            placeholder="John Doe"
            autoComplete="name"
          />
          {errors.customer_name && <small>{errors.customer_name}</small>}
        </label>
        <label>
          WhatsApp Number
          <input
            value={orderForm.whatsapp_number}
            onChange={(event) => onFormChange("whatsapp_number", event.target.value)}
            aria-invalid={Boolean(errors.whatsapp_number)}
            placeholder="+919876543210"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
          />
          {errors.whatsapp_number && <small>{errors.whatsapp_number}</small>}
        </label>
        <button className={styles.primaryButton} type="submit" disabled={!canSubmit || isSending}>
          {isSending ? "Sending..." : "Send Order"}
        </button>
        {orderFeedback && (
          <div className={`${styles.orderFeedback} ${orderFeedback.type === "success" ? styles.orderFeedbackSuccess : styles.orderFeedbackError}`} role="status">
            {orderFeedback.message}
          </div>
        )}
      </form>
    </aside>
  );
}

function CustomerView({ menu, cart, orderForm, errors, isSending, orderFeedback, searchTerm, category, setSearchTerm, setCategory, onFormChange, onSubmit }) {
  const filteredMenu = useMemo(() => {
    return menu
      .filter((item) => item.is_available)
      .filter((item) => category === "All" || getCategory(item) === category)
      .filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [category, menu, searchTerm]);

  return (
    <section className={styles.customerGrid}>
      <div className={styles.menuColumn}>
        <div className={styles.menuToolbar}>
          <label className={styles.searchField}>
            Search menu
            <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search pizza, dosa, burger..." />
          </label>
          <div className={styles.filters} aria-label="Menu category filters">
            {CATEGORIES.map((itemCategory) => (
              <button
                key={itemCategory}
                type="button"
                className={category === itemCategory ? styles.activeFilter : ""}
                onClick={() => setCategory(itemCategory)}
              >
                {itemCategory}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.menuGrid}>
          {filteredMenu.length === 0 ? (
            <div className={styles.emptyState}>No available items match your search.</div>
          ) : (
            filteredMenu.map((item) => (
              <MenuCard
                key={item.id}
                item={item}
                quantity={cart.quantities[item.name] || 0}
                onIncrement={cart.increment}
                onDecrement={cart.decrement}
              />
            ))
          )}
        </div>
      </div>

      <CartPanel
        cart={cart}
        orderForm={orderForm}
        errors={errors}
        isSending={isSending}
        orderFeedback={orderFeedback}
        onFormChange={onFormChange}
        onRemove={cart.remove}
        onSubmit={onSubmit}
      />
    </section>
  );
}

function StaffDashboard({
  menu,
  orders,
  menuForm,
  orderLookupId,
  selectedOrder,
  showAllOrders,
  editingMenuItemId,
  onMenuFormChange,
  onAddMenuItem,
  onEditMenuItem,
  onCancelEdit,
  onUpdateStatus,
  onCancelOrder,
  onToggleAvailability,
  onOrderLookupChange,
  onShowAllOrdersChange,
  onFindOrder,
  onClearOrderDetails,
}) {
  const activeCount = orders.filter((order) => !["cancelled", "delivered"].includes(order.status)).length;
  const counts = {
    pending: orders.filter((order) => order.status === "pending").length,
    preparing: orders.filter((order) => order.status === "preparing").length,
    ready: orders.filter((order) => order.status === "out-for-delivery").length,
    shown: orders.length,
  };
  const visibleMenu = uniqueMenuItems(menu);
  const duplicateCount = menu.length - visibleMenu.length;
  const duplicateName = visibleMenu.some(
    (item) => normalizeName(item.name) === normalizeName(menuForm.name) && item.id !== editingMenuItemId,
  );

  return (
    <>
      <section className={styles.statsGrid}>
        <div><span>{showAllOrders ? "Shown" : "Active"}</span><strong>{counts.shown}</strong></div>
        <div><span>Pending</span><strong>{counts.pending}</strong></div>
        <div><span>Preparing</span><strong>{counts.preparing}</strong></div>
        <div><span>Ready</span><strong>{counts.ready}</strong></div>
      </section>

      <section className={styles.staffGrid}>
        <form className={styles.staffPanel} onSubmit={onAddMenuItem}>
          <div className={styles.staffPanelTitle}>
            <div>
              <span className={styles.eyebrow}>Menu Setup</span>
              <h2>{editingMenuItemId ? "Edit Menu Item" : "Add Menu Item"}</h2>
            </div>
            {duplicateName && <span className={styles.warningPill}>Duplicate</span>}
          </div>
          <label>
            Name
            <input value={menuForm.name} onChange={(event) => onMenuFormChange("name", event.target.value)} required />
            {duplicateName && <small className={styles.fieldHint}>This item is already on the menu.</small>}
          </label>
          <label>Description<input value={menuForm.description} onChange={(event) => onMenuFormChange("description", event.target.value)} required /></label>
          <label>Price<input type="number" min="0" step="0.01" value={menuForm.price} onChange={(event) => onMenuFormChange("price", event.target.value)} required /></label>
          <label className={styles.inlineCheck}><input type="checkbox" checked={menuForm.is_available} onChange={(event) => onMenuFormChange("is_available", event.target.checked)} /> Available</label>
          <div className={styles.actionGroup}>
            <button className={styles.primaryButton} type="submit" disabled={duplicateName}>
              {editingMenuItemId ? "Update Item" : "Save Item"}
            </button>
            {editingMenuItemId && (
              <button type="button" className={styles.secondaryButton} onClick={onCancelEdit}>
                Cancel Edit
              </button>
            )}
          </div>
        </form>

        <section className={styles.staffPanel}>
          <div className={styles.staffPanelTitle}>
            <div>
              <span className={styles.eyebrow}>Kitchen Control</span>
              <h2>Menu Availability</h2>
            </div>
            {duplicateCount > 0 && <span className={styles.warningPill}>{duplicateCount} duplicate hidden</span>}
          </div>
          <div className={styles.compactList}>
            {visibleMenu.length === 0 ? <p className={styles.emptyText}>No menu items yet.</p> : visibleMenu.map((item) => (
              <div className={styles.availabilityRow} key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{formatCurrency(item.price)}</span>
                </div>
                <div className={styles.actionGroup}>
                  <button type="button" className={styles.editButton} onClick={() => onEditMenuItem(item)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className={item.is_available ? styles.availableButton : styles.unavailableButton}
                    onClick={() => onToggleAvailability(item)}
                    aria-pressed={item.is_available}
                  >
                    {item.is_available ? "Available" : "Unavailable"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </section>

      <section className={styles.ordersPanel}>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.eyebrow}>Live Queue</span>
            <h2>{showAllOrders ? "All Orders" : "Active Orders"}</h2>
          </div>
          <span className={styles.timestamp}>Updated {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
        <div className={styles.orderModeToggle} aria-label="Order list filter">
          <button
            type="button"
            className={!showAllOrders ? styles.activeFilter : ""}
            onClick={() => onShowAllOrdersChange(false)}
          >
            Active Orders
          </button>
          <button
            type="button"
            className={showAllOrders ? styles.activeFilter : ""}
            onClick={() => onShowAllOrdersChange(true)}
          >
            All Orders
          </button>
          {showAllOrders && <span>{activeCount} active in this list</span>}
        </div>
        <form className={styles.orderLookup} onSubmit={onFindOrder}>
          <label>
            Find Order
            <input
              type="number"
              min="1"
              value={orderLookupId}
              onChange={(event) => onOrderLookupChange(event.target.value)}
              placeholder="Enter order ID"
            />
          </label>
          <button type="submit">View Details</button>
        </form>
        {selectedOrder && (
          <section className={styles.orderDetails} aria-label="Order details">
            <div className={styles.staffPanelTitle}>
              <div>
                <span className={styles.eyebrow}>Order Details</span>
                <h2>#{selectedOrder.id}</h2>
              </div>
              <button type="button" className={styles.secondaryButton} onClick={onClearOrderDetails}>Close</button>
            </div>
            <dl>
              <div><dt>Customer</dt><dd>{selectedOrder.customer_name}</dd></div>
              <div><dt>WhatsApp</dt><dd>{selectedOrder.whatsapp_number}</dd></div>
              <div><dt>Items</dt><dd>{selectedOrder.items.join(", ")}</dd></div>
              <div><dt>Status</dt><dd><span className={styles.statusPill}>{selectedOrder.status}</span></dd></div>
            </dl>
          </section>
        )}
        <div className={styles.tableWrap}>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Customer</th>
                <th>WhatsApp</th>
                <th>Items</th>
                <th>Status</th>
                <th>Next Step</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 ? (
                <tr><td colSpan="7">{showAllOrders ? "No orders found." : "No active orders."}</td></tr>
              ) : (
                orders.map((order) => {
                  const nextStatus = nextStatusFor(order.status);
                  const statusLabel = STATUS_FLOW.find((status) => status.value === order.status)?.label || order.status;
                  const nextLabel = STATUS_FLOW.find((status) => status.value === nextStatus)?.label;
                  return (
                    <tr key={order.id}>
                      <td>#{order.id}</td>
                      <td>{order.customer_name}</td>
                      <td>{order.whatsapp_number}</td>
                      <td>{order.items.join(", ")}</td>
                      <td><span className={styles.statusPill}>{statusLabel}</span></td>
                      <td>
                        {nextStatus ? (
                          <button type="button" onClick={() => onUpdateStatus(order.id, nextStatus)}>{nextLabel}</button>
                        ) : order.status === "cancelled" ? (
                          <span className={styles.emptyText}>Cancelled</span>
                        ) : (
                          <span className={styles.emptyText}>Complete</span>
                        )}
                      </td>
                      <td>
                        <div className={styles.actionGroup}>
                          <button
                            type="button"
                            className={styles.secondaryButton}
                            onClick={() => onFindOrder(order.id)}
                          >
                            Details
                          </button>
                          {!["cancelled", "delivered"].includes(order.status) && (
                            <button
                              type="button"
                              className={styles.cancelButton}
                              onClick={() => onCancelOrder(order.id)}
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function App() {
  const [activeView, setActiveView] = useState("customer");
  const [menu, setMenu] = useState([]);
  const [orders, setOrders] = useState([]);
  const [notice, setNotice] = useState("");
  const [orderFeedback, setOrderFeedback] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [category, setCategory] = useState("All");
  const [isSending, setIsSending] = useState(false);
  const defaultMenuForm = { name: "", description: "", price: "", is_available: true };
  const [menuForm, setMenuForm] = useState(defaultMenuForm);
  const [editingMenuItemId, setEditingMenuItemId] = useState(null);
  const [orderForm, setOrderForm] = useState({ customer_name: "", whatsapp_number: "" });
  const [orderLookupId, setOrderLookupId] = useState("");
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [showAllOrders, setShowAllOrders] = useState(false);
  const visibleMenu = useMemo(() => uniqueMenuItems(menu), [menu]);
  const cart = useCart(visibleMenu.filter((item) => item.is_available));

  const errors = useMemo(() => ({
    customer_name: isValidCustomerName(orderForm.customer_name)
      ? ""
      : "Enter letters and spaces only.",
    whatsapp_number: isValidWhatsAppNumber(orderForm.whatsapp_number)
      ? ""
      : "Use international format, e.g. +919876543210.",
  }), [orderForm]);

  const showNotice = useCallback((message) => {
    setNotice(message);
    window.clearTimeout(showNotice.timer);
    showNotice.timer = window.setTimeout(() => setNotice(""), 4200);
  }, []);

  const clearOrderFeedback = useCallback(() => {
    setOrderFeedback(null);
  }, []);

  const loadData = useCallback(async () => {
    try {
      const ordersUrl = showAllOrders ? `${API_BASE}/orders/?include_all=true` : `${API_BASE}/orders/`;
      const [menuRes, orderRes] = await Promise.all([axios.get(`${API_BASE}/menu/`), axios.get(ordersUrl)]);
      setMenu(menuRes.data);
      setOrders(orderRes.data);
    } catch {
      showNotice("Backend is not reachable.");
    }
  }, [showAllOrders, showNotice]);

  useEffect(() => {
    loadData();
    const interval = window.setInterval(loadData, 5000);
    return () => window.clearInterval(interval);
  }, [loadData]);

  const addMenuItem = async (event) => {
    event.preventDefault();
    const normalizedName = menuForm.name.trim();
    const normalizedDescription = menuForm.description.trim();
    const parsedPrice = Number(menuForm.price);

    if (!normalizedName || !normalizedDescription || Number.isNaN(parsedPrice)) {
      showNotice("Enter a name, description, and price to save the menu item.");
      return;
    }

    const duplicateName = visibleMenu.some(
      (item) => normalizeName(item.name) === normalizeName(normalizedName) && item.id !== editingMenuItemId,
    );

    if (duplicateName) {
      showNotice("That menu item already exists. Edit the existing item or choose a different name.");
      return;
    }

    try {
      if (editingMenuItemId) {
        await axios.patch(`${API_BASE}/menu/${editingMenuItemId}`, {
          name: normalizedName,
          description: normalizedDescription,
          price: parsedPrice,
          is_available: menuForm.is_available,
        });
        showNotice("Menu item updated.");
      } else {
        await axios.post(`${API_BASE}/menu/`, {
          name: normalizedName,
          description: normalizedDescription,
          price: parsedPrice,
          is_available: menuForm.is_available,
        });
        showNotice("Menu item saved.");
      }

      setMenuForm(defaultMenuForm);
      setEditingMenuItemId(null);
      loadData();
    } catch (err) {
      showNotice(err.response?.data?.detail || "Menu item could not be saved.");
    }
  };

  const startEditingMenuItem = (item) => {
    setEditingMenuItemId(item.id);
    setMenuForm({
      name: item.name,
      description: item.description,
      price: String(item.price),
      is_available: item.is_available,
    });
  };

  const cancelEditingMenuItem = () => {
    setEditingMenuItemId(null);
    setMenuForm(defaultMenuForm);
  };

  const handleOrderFormChange = (field, value) => {
    clearOrderFeedback();
    setOrderForm((current) => ({ ...current, [field]: value }));
  };

  const placeOrder = async (event) => {
    event.preventDefault();
    if (cart.items.length === 0 || errors.customer_name || errors.whatsapp_number) return;

    setIsSending(true);
    try {
      // The backend accepts a list of item names, so quantities are sent as repeated names.
      const orderedItems = cart.items.flatMap((item) => Array(item.quantity).fill(item.name));
      await axios.post(`${API_BASE}/orders/`, { ...orderForm, items: orderedItems });
      setOrderForm({ customer_name: "", whatsapp_number: "" });
      setOrderFeedback({ type: "success", message: "Order placed successfully. WhatsApp confirmation sent." });
      window.clearTimeout(placeOrder.feedbackTimer);
      placeOrder.feedbackTimer = window.setTimeout(() => setOrderFeedback(null), 4000);
      cart.clear();
      showNotice("Order placed successfully. WhatsApp confirmation sent.");
      loadData();
    } catch (err) {
      setOrderFeedback({ type: "error", message: err.response?.data?.detail || "Order could not be placed." });
      window.clearTimeout(placeOrder.feedbackTimer);
      placeOrder.feedbackTimer = window.setTimeout(() => setOrderFeedback(null), 4000);
      showNotice(err.response?.data?.detail || "Order could not be placed.");
    } finally {
      setIsSending(false);
    }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.patch(`${API_BASE}/orders/${id}`, { status });
      showNotice("Order status updated and customer notified.");
      loadData();
    } catch (err) {
      showNotice(err.response?.data?.detail || "Status could not be updated.");
    }
  };

  const cancelOrder = async (id) => {
    try {
      await axios.delete(`${API_BASE}/orders/${id}`);
      setSelectedOrder((current) => (current?.id === id ? null : current));
      showNotice("Order cancelled and customer notified.");
      loadData();
    } catch (err) {
      showNotice(err.response?.data?.detail || "Order could not be cancelled.");
    }
  };

  const findOrder = async (eventOrId) => {
    if (eventOrId?.preventDefault) {
      eventOrId.preventDefault();
    }

    const id = typeof eventOrId === "number" ? eventOrId : Number(orderLookupId);
    if (!id) {
      showNotice("Enter an order ID to view details.");
      return;
    }

    try {
      const response = await axios.get(`${API_BASE}/orders/${id}`);
      setSelectedOrder(response.data);
      setOrderLookupId(String(id));
    } catch (err) {
      setSelectedOrder(null);
      showNotice(err.response?.data?.detail || "Order details could not be loaded.");
    }
  };

  const toggleAvailability = async (item) => {
    try {
      await axios.patch(`${API_BASE}/menu/${item.id}/availability`, { is_available: !item.is_available });
      showNotice(`${item.name} marked ${item.is_available ? "unavailable" : "available"}.`);
      loadData();
    } catch (err) {
      showNotice(err.response?.data?.detail || "Availability could not be updated.");
    }
  };

  return (
    <main className={styles.appShell}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>WhatsApp ordering</span>
          <h1>Fresh food, fast updates.</h1>
          <p>Browse the menu, build your cart, and receive order updates directly on WhatsApp.</p>
        </div>
        {notice && <div className={styles.toast} role="status">{notice}</div>}
      </header>

      <nav className={styles.tabs} aria-label="Views">
        <button className={activeView === "customer" ? styles.activeTab : ""} type="button" onClick={() => setActiveView("customer")}>Customer Order</button>
        <button className={activeView === "staff" ? styles.activeTab : ""} type="button" onClick={() => setActiveView("staff")}>Staff Dashboard</button>
      </nav>

      {activeView === "customer" ? (
        <CustomerView
          menu={visibleMenu}
          cart={cart}
          orderForm={orderForm}
          errors={errors}
          isSending={isSending}
          orderFeedback={orderFeedback}
          searchTerm={searchTerm}
          category={category}
          setSearchTerm={setSearchTerm}
          setCategory={setCategory}
          onFormChange={handleOrderFormChange}
          onSubmit={placeOrder}
        />
      ) : (
        <StaffDashboard
          menu={menu}
          orders={orders}
          menuForm={menuForm}
          orderLookupId={orderLookupId}
          selectedOrder={selectedOrder}
          showAllOrders={showAllOrders}
          editingMenuItemId={editingMenuItemId}
          onMenuFormChange={(field, value) => setMenuForm((current) => ({ ...current, [field]: value }))}
          onAddMenuItem={addMenuItem}
          onEditMenuItem={startEditingMenuItem}
          onCancelEdit={cancelEditingMenuItem}
          onUpdateStatus={updateStatus}
          onCancelOrder={cancelOrder}
          onToggleAvailability={toggleAvailability}
          onOrderLookupChange={setOrderLookupId}
          onShowAllOrdersChange={setShowAllOrders}
          onFindOrder={findOrder}
          onClearOrderDetails={() => setSelectedOrder(null)}
        />
      )}
    </main>
  );
}

export default App;
