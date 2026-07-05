"""
Aroma Legante — Inventory & Sales Manager
--------------------------------------------
A single-file Streamlit app backed by a local SQLite database.

Run with:
    pip install -r requirements.txt
    streamlit run app.py

Your data is saved in perfume_inventory.db (created automatically the
first time you run the app) sitting next to this file, so it will still
be there the next time you open it.
"""

import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

DB_PATH = "perfume_inventory.db"
CURRENCY = "₱"
APP_NAME = "Aroma Legante"

st.set_page_config(page_title=APP_NAME, page_icon="🌸", layout="wide")

# ============================================================
# LOOK & FEEL — forced light, warm boutique palette
# (explicitly overrides the viewer's light/dark setting so the
#  app always looks the same, regardless of browser/system theme)
# ============================================================

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

:root { color-scheme: light !important; }

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stBottomBlockContainer"] {
    background-color: #FAF6F3 !important;
}
[data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; }

html, body, .stApp, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #2B2223;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"] {
    color: #2B2223 !important;
}

h1, h2, h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-weight: 700 !important;
    color: #5C2438 !important;
    letter-spacing: 0.2px;
}

h1 {
    font-size: 2.3rem !important;
    border-bottom: 2px solid #E7CDC7;
    padding-bottom: 0.5rem;
    margin-bottom: 1.3rem !important;
}
h2, h3 { margin-top: 1.1rem !important; }

[data-testid="stMetricValue"] { color: #8C4A5C !important; font-weight: 700; font-size: 1.5rem; }
[data-testid="stMetricLabel"] { color: #6B5555 !important; }
[data-testid="stMetric"] {
    background-color: #F3E5E1 !important;
    border-radius: 14px;
    padding: 16px 18px;
    border: 1px solid #E8D3CD;
}

section[data-testid="stSidebar"] {
    background-color: #F6EDE9 !important;
    border-right: 1px solid #E8D3CD;
}
section[data-testid="stSidebar"] * { color: #3B2A2A !important; }
section[data-testid="stSidebar"] h1 {
    font-size: 1.5rem !important;
    border-bottom: none;
    margin-bottom: 0 !important;
    padding-bottom: 0;
}
section[data-testid="stSidebar"] .brand-caption { color: #8A7370 !important; }

input[type="radio"] { accent-color: #8C4A5C; }
section[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 8px 10px;
    border-radius: 8px;
    margin-bottom: 2px;
}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background-color: #EDD9D2; }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background-color: #E7C3BC;
    font-weight: 600;
}

.stDataFrame, .stTable { font-size: 1.0rem; }

div.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid #C98A96;
    color: #5C2438;
    background-color: #FFFFFF;
}
div.stButton > button[kind="primary"] { background-color: #8C4A5C; color: #FFFFFF !important; border: none; }
div.stButton > button[kind="primary"]:hover { background-color: #73394A; }
div.stDownloadButton > button { border-radius: 8px; font-weight: 600; }

hr, [data-testid="stDivider"] { border-color: #E8D3CD !important; }

.brand-caption {
    color: #8A7370;
    font-size: 0.82rem;
    margin-top: -6px;
    margin-bottom: 16px;
    letter-spacing: 1px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# DATABASE
# ============================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit_measure TEXT,
            unit_cost REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0,
            current_stock REAL NOT NULL DEFAULT 0,
            low_stock_threshold REAL NOT NULL DEFAULT 3,
            date_added TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            move_date TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            reason TEXT,
            FOREIGN KEY (item_id) REFERENCES items(id)
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            sale_date TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'Unpaid',
            note TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            date_added TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS customer_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            price REAL NOT NULL,
            UNIQUE(customer_id, item_id),
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS cash_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            beginning_cash REAL NOT NULL DEFAULT 0,
            start_date TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS cash_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            tx_type TEXT NOT NULL,      -- 'In' or 'Out'
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            ref_type TEXT,              -- 'sale', 'stock_movement', 'manual'
            ref_id INTEGER
        )"""
    )
    conn.commit()

    # Seed with the items visible in the user's original tracker, only once
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] == 0:
        seed = [
            ("Aventus Creed", "30ml bottle", 160.0, 8),
            ("Le Labo Santal 33", "30ml bottle", 160.0, 11),
            ("Bleu de Chanel", "30ml bottle", 160.0, 11),
            ("Dior Sauvage", "30ml bottle", 160.0, 3),
            ("Lacoste White - Men", "30ml bottle", 160.0, 1),
            ("D&G Light Blue - Women", "30ml bottle", 160.0, 7),
            ("Joe Malone Woodsage & SS", "30ml bottle", 160.0, 2),
            ("Miss Dior", "30ml bottle", 160.0, 5),
        ]
        today = date.today().isoformat()
        for name, um, cost, stock in seed:
            c.execute(
                """INSERT INTO items
                   (name, unit_measure, unit_cost, selling_price, current_stock, low_stock_threshold, date_added)
                   VALUES (?, ?, ?, 0, ?, 3, ?)""",
                (name, um, cost, stock, today),
            )
        conn.commit()

    # Backfill a customers directory from any sales already on file (safe to run every start)
    c.execute("SELECT DISTINCT customer_name FROM sales")
    for (nm,) in c.fetchall():
        if nm and nm.strip():
            c.execute(
                "INSERT OR IGNORE INTO customers (name, date_added) VALUES (?, ?)",
                (nm.strip(), date.today().isoformat()),
            )

    c.execute("SELECT COUNT(*) FROM cash_settings")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO cash_settings (id, beginning_cash, start_date) VALUES (1, 0, ?)",
            (date.today().isoformat(),),
        )
    conn.commit()
    conn.close()


# ---------- items ----------

def get_items_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM items ORDER BY name", conn)
    conn.close()
    return df


def add_item(name, unit_measure, unit_cost, selling_price, initial_stock, threshold):
    conn = get_conn()
    conn.execute(
        """INSERT INTO items (name, unit_measure, unit_cost, selling_price, current_stock, low_stock_threshold, date_added)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, unit_measure, unit_cost, selling_price, initial_stock, threshold, date.today().isoformat()),
    )
    conn.commit()
    conn.close()


def update_item(item_id, unit_measure, unit_cost, selling_price, threshold):
    conn = get_conn()
    conn.execute(
        """UPDATE items SET unit_measure=?, unit_cost=?, selling_price=?, low_stock_threshold=? WHERE id=?""",
        (unit_measure, unit_cost, selling_price, threshold, item_id),
    )
    conn.commit()
    conn.close()


def delete_item(item_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sale_items WHERE item_id=?", (item_id,))
    has_sales = c.fetchone()[0] > 0
    if has_sales:
        conn.close()
        return False, "This item has sales history and can't be deleted (to keep your records intact). You can set its stock to 0 instead."
    c.execute("DELETE FROM stock_movements WHERE item_id=?", (item_id,))
    c.execute("DELETE FROM customer_prices WHERE item_id=?", (item_id,))
    c.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return True, "Item deleted."


# ---------- stock movements ----------

def record_stock_movement(item_id, item_name, movement_type, quantity, reason, move_date, cash_paid=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO stock_movements (item_id, move_date, movement_type, quantity, reason) VALUES (?, ?, ?, ?, ?)",
        (item_id, move_date, movement_type, quantity, reason),
    )
    move_id = c.lastrowid
    if movement_type == "In":
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id=?", (quantity, item_id))
    else:
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id=?", (quantity, item_id))
    conn.commit()
    conn.close()

    if movement_type == "In" and cash_paid and cash_paid > 0:
        add_cash_transaction(
            move_date, "Out", "Stock Purchase", cash_paid,
            f"Restock: {item_name} x{quantity:.0f}", ref_type="stock_movement", ref_id=move_id,
        )


def get_movements_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT m.id, m.move_date AS Date, i.name AS Item, m.movement_type AS Type,
                  m.quantity AS Quantity, m.reason AS Reason
           FROM stock_movements m JOIN items i ON m.item_id = i.id
           ORDER BY m.move_date DESC, m.id DESC""",
        conn,
    )
    conn.close()
    return df


# ---------- customers ----------

def get_customers_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM customers ORDER BY name", conn)
    conn.close()
    return df


def get_or_create_customer(name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM customers WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        cid = row[0]
    else:
        c.execute("INSERT INTO customers (name, date_added) VALUES (?, ?)", (name, date.today().isoformat()))
        conn.commit()
        cid = c.lastrowid
    conn.close()
    return cid


def get_customer_price(customer_id, item_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT price FROM customer_prices WHERE customer_id=? AND item_id=?", (customer_id, item_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def upsert_customer_price(customer_id, item_id, price):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO customer_prices (customer_id, item_id, price) VALUES (?, ?, ?)
           ON CONFLICT(customer_id, item_id) DO UPDATE SET price=excluded.price""",
        (customer_id, item_id, price),
    )
    conn.commit()
    conn.close()


def delete_customer_price(price_id):
    conn = get_conn()
    conn.execute("DELETE FROM customer_prices WHERE id=?", (price_id,))
    conn.commit()
    conn.close()


def get_customer_prices_df(customer_id):
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT cp.id, i.name AS Item, cp.price AS Price
           FROM customer_prices cp JOIN items i ON cp.item_id = i.id
           WHERE cp.customer_id = ?
           ORDER BY i.name""",
        conn,
        params=(customer_id,),
    )
    conn.close()
    return df


def get_customer_summary_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT c.id AS CustomerID, c.name AS Name,
                  COUNT(DISTINCT s.id) AS Purchases,
                  COALESCE(SUM(si.quantity*si.unit_price), 0) AS TotalSpent,
                  COALESCE(SUM(CASE WHEN s.payment_status='Paid' THEN si.quantity*si.unit_price ELSE 0 END), 0) AS Paid,
                  COALESCE(SUM(CASE WHEN s.payment_status='Unpaid' THEN si.quantity*si.unit_price ELSE 0 END), 0) AS Outstanding,
                  MAX(s.sale_date) AS LastPurchase
           FROM customers c
           LEFT JOIN sales s ON s.customer_name = c.name
           LEFT JOIN sale_items si ON si.sale_id = s.id
           GROUP BY c.id
           ORDER BY c.name""",
        conn,
    )
    conn.close()
    return df


# ---------- cash on hand ----------

def get_beginning_cash():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT beginning_cash, start_date FROM cash_settings WHERE id=1")
    row = c.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (0.0, date.today().isoformat())


def set_beginning_cash(amount, start_date):
    conn = get_conn()
    conn.execute("UPDATE cash_settings SET beginning_cash=?, start_date=? WHERE id=1", (amount, start_date))
    conn.commit()
    conn.close()


def add_cash_transaction(tx_date, tx_type, category, amount, note="", ref_type=None, ref_id=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO cash_transactions (tx_date, tx_type, category, amount, note, ref_type, ref_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tx_date, tx_type, category, amount, note, ref_type, ref_id),
    )
    conn.commit()
    conn.close()


def delete_cash_transaction(tx_id):
    conn = get_conn()
    conn.execute("DELETE FROM cash_transactions WHERE id=?", (tx_id,))
    conn.commit()
    conn.close()


def remove_cash_tx_for_ref(ref_type, ref_id):
    conn = get_conn()
    conn.execute("DELETE FROM cash_transactions WHERE ref_type=? AND ref_id=?", (ref_type, ref_id))
    conn.commit()
    conn.close()


def has_cash_tx_for_ref(ref_type, ref_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cash_transactions WHERE ref_type=? AND ref_id=?", (ref_type, ref_id))
    n = c.fetchone()[0]
    conn.close()
    return n > 0


def get_cash_ledger_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT id, tx_date AS Date, tx_type AS Type, category AS Category, amount AS Amount, note AS Note
           FROM cash_transactions ORDER BY tx_date ASC, id ASC""",
        conn,
    )
    conn.close()
    return df


def get_manual_cash_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT id, tx_date AS Date, tx_type AS Type, category AS Category, amount AS Amount, note AS Note
           FROM cash_transactions WHERE ref_type='manual' ORDER BY tx_date DESC, id DESC""",
        conn,
    )
    conn.close()
    return df


def get_cash_balance():
    beginning, _ = get_beginning_cash()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) FROM cash_transactions WHERE tx_type='In'")
    total_in = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM cash_transactions WHERE tx_type='Out'")
    total_out = c.fetchone()[0]
    conn.close()
    return beginning + total_in - total_out, total_in, total_out


# ---------- sales ----------

def record_sale(customer_name, sale_date, payment_status, note, line_items):
    """line_items: list of dicts with item_id, item_name, quantity, unit_cost, unit_price"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sales (customer_name, sale_date, payment_status, note) VALUES (?, ?, ?, ?)",
        (customer_name, sale_date, payment_status, note),
    )
    sale_id = c.lastrowid
    total = 0.0
    for li in line_items:
        c.execute(
            """INSERT INTO sale_items (sale_id, item_id, item_name, quantity, unit_cost, unit_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sale_id, li["item_id"], li["item_name"], li["quantity"], li["unit_cost"], li["unit_price"]),
        )
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id=?", (li["quantity"], li["item_id"]))
        total += li["quantity"] * li["unit_price"]
    conn.commit()
    conn.close()

    if payment_status == "Paid" and total > 0:
        add_cash_transaction(sale_date, "In", "Sale Payment", total, f"Sale to {customer_name}", ref_type="sale", ref_id=sale_id)

    return sale_id


def get_sales_summary_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT s.id AS SaleID, s.sale_date AS Date, s.customer_name AS Customer,
                  s.payment_status AS Status,
                  SUM(si.quantity * si.unit_price) AS Total,
                  SUM((si.unit_price - si.unit_cost) * si.quantity) AS Profit
           FROM sales s JOIN sale_items si ON s.id = si.sale_id
           GROUP BY s.id
           ORDER BY s.sale_date DESC, s.id DESC""",
        conn,
    )
    conn.close()
    return df


def get_sale_line_items(sale_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT item_name AS Item, quantity AS Qty, unit_price AS 'Unit Price', unit_cost AS 'Unit Cost' FROM sale_items WHERE sale_id=?",
        conn,
        params=(sale_id,),
    )
    conn.close()
    return df


def update_payment_status(sale_id, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE sales SET payment_status=? WHERE id=?", (status, sale_id))
    conn.commit()
    conn.close()

    if status == "Paid":
        if not has_cash_tx_for_ref("sale", sale_id):
            conn2 = get_conn()
            c2 = conn2.cursor()
            c2.execute("SELECT sale_date, customer_name FROM sales WHERE id=?", (sale_id,))
            sdate, cname = c2.fetchone()
            c2.execute("SELECT COALESCE(SUM(quantity*unit_price),0) FROM sale_items WHERE sale_id=?", (sale_id,))
            total = c2.fetchone()[0]
            conn2.close()
            if total > 0:
                add_cash_transaction(sdate, "In", "Sale Payment", total, f"Sale to {cname}", ref_type="sale", ref_id=sale_id)
    else:
        remove_cash_tx_for_ref("sale", sale_id)


def delete_sale(sale_id):
    """Delete a sale, restore the stock it had taken out, and remove any linked cash entry."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT item_id, quantity FROM sale_items WHERE sale_id=?", (sale_id,))
    rows = c.fetchall()
    for item_id, qty in rows:
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id=?", (qty, item_id))
    c.execute("DELETE FROM sale_items WHERE sale_id=?", (sale_id,))
    c.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    conn.commit()
    conn.close()
    remove_cash_tx_for_ref("sale", sale_id)


# ============================================================
# HELPERS
# ============================================================

def peso(x):
    try:
        return f"{CURRENCY}{x:,.2f}"
    except (TypeError, ValueError):
        return f"{CURRENCY}0.00"


NEW_CUSTOMER_LABEL = "➕ Add a new customer..."

init_db()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.markdown(f"# {APP_NAME}")
st.sidebar.markdown('<div class="brand-caption">INVENTORY &amp; SALES</div>', unsafe_allow_html=True)
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Inventory", "Stock In / Out", "Record a Sale", "Sales & Payments", "Customers", "Cash on Hand", "Manage Items"],
    label_visibility="collapsed",
)

items_df = get_items_df()


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":
    st.title("Dashboard")

    if items_df.empty:
        st.info("No items yet — add your first perfume under **Manage Items**.")
    else:
        cash_balance, cash_in, cash_out = get_cash_balance()
        st.metric("💵 Cash on Hand", peso(cash_balance))
        st.caption(f"₱{cash_in:,.2f} received and ₱{cash_out:,.2f} spent so far, on top of your beginning cash.")

        st.divider()

        total_items = len(items_df)
        total_units = items_df["current_stock"].sum()
        stock_value_cost = (items_df["current_stock"] * items_df["unit_cost"]).sum()
        total_customers = len(get_customers_df())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Items tracked", total_items)
        c2.metric("Units in stock", f"{total_units:,.0f}")
        c3.metric("Stock value (cost)", peso(stock_value_cost))
        c4.metric("Customers", total_customers)

        sales_df = get_sales_summary_df()
        realized_profit = sales_df.loc[sales_df["Status"] == "Paid", "Profit"].sum() if not sales_df.empty else 0
        pending_profit = sales_df.loc[sales_df["Status"] == "Unpaid", "Profit"].sum() if not sales_df.empty else 0
        outstanding_payables = sales_df.loc[sales_df["Status"] == "Unpaid", "Total"].sum() if not sales_df.empty else 0

        c5, c6, c7 = st.columns(3)
        c5.metric("Profit earned (paid)", peso(realized_profit))
        c6.metric("Profit pending (unpaid)", peso(pending_profit))
        c7.metric("Outstanding payables", peso(outstanding_payables))

        st.divider()

        low_stock = items_df[items_df["current_stock"] <= items_df["low_stock_threshold"]]
        st.subheader("Low stock")
        if low_stock.empty:
            st.success("All items are above their low-stock threshold.")
        else:
            show = low_stock[["name", "current_stock", "low_stock_threshold", "unit_measure"]].rename(
                columns={"name": "Item", "current_stock": "In Stock", "low_stock_threshold": "Threshold", "unit_measure": "Unit"}
            )
            st.dataframe(show, hide_index=True, use_container_width=True)

        st.subheader("Recent sales")
        if sales_df.empty:
            st.caption("No sales recorded yet.")
        else:
            recent = sales_df.head(5)[["Date", "Customer", "Status", "Total", "Profit"]].copy()
            recent["Total"] = recent["Total"].map(peso)
            recent["Profit"] = recent["Profit"].map(peso)
            st.dataframe(recent, hide_index=True, use_container_width=True)


# ============================================================
# INVENTORY
# ============================================================

elif page == "Inventory":
    st.title("Inventory")

    if items_df.empty:
        st.info("No items yet — add your first perfume under **Manage Items**.")
    else:
        view = items_df.copy()
        view["margin"] = view["selling_price"] - view["unit_cost"]
        view["margin_pct"] = view.apply(
            lambda r: (r["margin"] / r["selling_price"] * 100) if r["selling_price"] > 0 else 0, axis=1
        )
        view["stock_value"] = view["current_stock"] * view["unit_cost"]
        view["Status"] = view.apply(
            lambda r: "🟠 Low stock" if r["current_stock"] <= r["low_stock_threshold"] else "🟢 In stock", axis=1
        )

        display = view.rename(
            columns={
                "name": "Item",
                "unit_measure": "Unit",
                "unit_cost": "Cost",
                "selling_price": "Selling Price",
                "current_stock": "In Stock",
                "margin": "Profit/Unit",
                "margin_pct": "Margin %",
                "stock_value": "Stock Value (cost)",
            }
        )[["Item", "Unit", "Cost", "Selling Price", "Profit/Unit", "Margin %", "In Stock", "Stock Value (cost)", "Status"]]

        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Cost": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f"),
                "Selling Price": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f"),
                "Profit/Unit": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f"),
                "Margin %": st.column_config.NumberColumn(format="%.0f%%"),
                "Stock Value (cost)": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f"),
            },
        )
        st.caption("🟠 means the item is at or below its low-stock threshold.")

        csv = display.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download inventory as CSV", csv, "inventory.csv", "text/csv")


# ============================================================
# STOCK IN / OUT
# ============================================================

elif page == "Stock In / Out":
    st.title("Stock In / Out")
    st.caption("Use this for restocking (In) or non-sale reductions like samples, damage, or personal use (Out). Regular sales are handled on the **Record a Sale** page.")

    if items_df.empty:
        st.info("Add items first under **Manage Items**.")
    else:
        with st.form("stock_move_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                item_name = st.selectbox("Item", items_df["name"].tolist())
                movement_type = st.radio("Movement", ["In", "Out"], horizontal=True)
            with col2:
                quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
                move_date = st.date_input("Date", value=date.today())
            reason = st.text_input(
                "Reason / note",
                placeholder="e.g. Restocked from supplier / Sample given / Damaged bottle",
            )
            cash_paid = st.number_input(
                "Amount paid from cash (only if this was a restock paid in cash)",
                min_value=0.0, step=50.0, value=0.0,
                help="Leave at 0 if this restock wasn't paid in cash right now (e.g. paid by bank transfer, or this is a stock-out).",
            )
            submitted = st.form_submit_button("Save movement", type="primary")

            if submitted:
                if quantity <= 0:
                    st.error("Quantity must be greater than 0.")
                else:
                    item_row = items_df[items_df["name"] == item_name].iloc[0]
                    if movement_type == "Out" and quantity > item_row["current_stock"]:
                        st.error(f"Only {item_row['current_stock']:.0f} in stock for {item_name} — can't remove {quantity:.0f}.")
                    else:
                        record_stock_movement(
                            int(item_row["id"]), item_name, movement_type, quantity, reason, move_date.isoformat(),
                            cash_paid=cash_paid if movement_type == "In" else None,
                        )
                        st.success(f"Recorded: {movement_type} {quantity:.0f} x {item_name}")
                        st.rerun()

        st.divider()
        st.subheader("Movement history")
        moves = get_movements_df()
        if moves.empty:
            st.caption("No stock movements yet.")
        else:
            st.dataframe(moves.drop(columns=["id"]), hide_index=True, use_container_width=True)


# ============================================================
# RECORD A SALE
# ============================================================

elif page == "Record a Sale":
    st.title("Record a Sale")

    if items_df.empty:
        st.info("Add items first under **Manage Items**.")
    else:
        customers_df = get_customers_df()
        existing_names = customers_df["name"].tolist()

        col1, col2, col3 = st.columns(3)
        with col1:
            pick = st.selectbox("Customer", existing_names + [NEW_CUSTOMER_LABEL])
            if pick == NEW_CUSTOMER_LABEL:
                customer_name = st.text_input("New customer's name", placeholder="e.g. Bimby").strip()
            else:
                customer_name = pick
        with col2:
            sale_date = st.date_input("Date", value=date.today())
        with col3:
            payment_status = st.radio("Payment status", ["Paid", "Unpaid"], horizontal=True)

        existing_customer_id = None
        if customer_name and customer_name in existing_names:
            existing_customer_id = int(customers_df.loc[customers_df["name"] == customer_name, "id"].iloc[0])

        st.markdown("**Items purchased** — enter quantity for each item being bought. Prices can be adjusted per customer.")

        editor_source = items_df[["id", "name", "current_stock", "selling_price", "unit_cost"]].copy()

        def _default_price(row):
            if existing_customer_id is not None:
                custom = get_customer_price(existing_customer_id, int(row["id"]))
                if custom is not None:
                    return custom
            return row["selling_price"]

        editor_source["Unit Price"] = editor_source.apply(_default_price, axis=1)
        editor_source["Quantity"] = 0
        editor_display = editor_source.rename(columns={"name": "Item", "current_stock": "Available"})[
            ["Item", "Available", "Unit Price", "Quantity"]
        ]

        editor_key = f"sale_editor_{customer_name or 'unset'}"
        edited = st.data_editor(
            editor_display,
            column_config={
                "Item": st.column_config.TextColumn(disabled=True),
                "Available": st.column_config.NumberColumn(disabled=True),
                "Unit Price": st.column_config.NumberColumn(min_value=0.0, step=1.0, format=f"{CURRENCY}%.2f"),
                "Quantity": st.column_config.NumberColumn(min_value=0, step=1),
            },
            hide_index=True,
            use_container_width=True,
            key=editor_key,
        )

        note = st.text_input("Note (optional)", placeholder="e.g. picked up personally, half payment, etc.")
        remember_prices = st.checkbox(
            f"💾 Remember these prices as {customer_name or 'this customer'}'s usual pricing",
            value=True,
            disabled=not bool(customer_name),
        )

        chosen = edited[edited["Quantity"] > 0]
        if not chosen.empty:
            preview_rows = []
            total = 0.0
            profit = 0.0
            for _, row in chosen.iterrows():
                src = items_df[items_df["name"] == row["Item"]].iloc[0]
                line_total = row["Quantity"] * row["Unit Price"]
                line_profit = row["Quantity"] * (row["Unit Price"] - src["unit_cost"])
                total += line_total
                profit += line_profit
                preview_rows.append(
                    {"Item": row["Item"], "Qty": row["Quantity"], "Line Total": peso(line_total), "Line Profit": peso(line_profit)}
                )
            st.table(pd.DataFrame(preview_rows))
            pc1, pc2 = st.columns(2)
            pc1.metric("Total sale amount", peso(total))
            pc2.metric("Profit on this sale", peso(profit))

        if st.button("✅ Confirm & Save Sale", type="primary"):
            if not customer_name:
                st.error("Please choose or enter a customer name.")
            elif chosen.empty:
                st.error("Please enter a quantity for at least one item.")
            else:
                problems = []
                line_items = []
                for _, row in chosen.iterrows():
                    src = items_df[items_df["name"] == row["Item"]].iloc[0]
                    if row["Quantity"] > src["current_stock"]:
                        problems.append(f"{row['Item']}: only {src['current_stock']:.0f} in stock")
                    elif row["Unit Price"] < 0:
                        problems.append(f"{row['Item']}: price can't be negative")
                    else:
                        line_items.append(
                            {
                                "item_id": int(src["id"]),
                                "item_name": src["name"],
                                "quantity": float(row["Quantity"]),
                                "unit_cost": float(src["unit_cost"]),
                                "unit_price": float(row["Unit Price"]),
                            }
                        )
                if problems:
                    st.error("Please check: " + "; ".join(problems))
                else:
                    cust_id = get_or_create_customer(customer_name)
                    record_sale(customer_name, sale_date.isoformat(), payment_status, note, line_items)
                    if remember_prices:
                        for li in line_items:
                            upsert_customer_price(cust_id, li["item_id"], li["unit_price"])
                    st.success(f"Sale recorded for {customer_name}!")
                    st.rerun()


# ============================================================
# SALES & PAYMENTS
# ============================================================

elif page == "Sales & Payments":
    st.title("Sales & Payments")

    sales_df = get_sales_summary_df()
    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        colf1, colf2 = st.columns(2)
        with colf1:
            customers = ["All"] + sorted(sales_df["Customer"].unique().tolist())
            customer_filter = st.selectbox("Filter by customer", customers)
        with colf2:
            status_filter = st.selectbox("Filter by status", ["All", "Paid", "Unpaid"])

        filtered = sales_df.copy()
        if customer_filter != "All":
            filtered = filtered[filtered["Customer"] == customer_filter]
        if status_filter != "All":
            filtered = filtered[filtered["Status"] == status_filter]

        show = filtered.copy()
        show["Total"] = show["Total"].map(peso)
        show["Profit"] = show["Profit"].map(peso)
        st.dataframe(show, hide_index=True, use_container_width=True)

        total_outstanding = filtered.loc[filtered["Status"] == "Unpaid", "Total"].sum()
        st.caption(f"Outstanding (in current view): {peso(total_outstanding)}")

        st.divider()
        st.subheader("Update a sale")
        sale_ids = filtered["SaleID"].tolist()
        if sale_ids:
            pick = st.selectbox(
                "Select a sale",
                sale_ids,
                format_func=lambda sid: (
                    f"#{sid} — "
                    f"{filtered.loc[filtered['SaleID']==sid,'Customer'].values[0]} — "
                    f"{filtered.loc[filtered['SaleID']==sid,'Date'].values[0]} — "
                    f"{filtered.loc[filtered['SaleID']==sid,'Status'].values[0]}"
                ),
            )
            st.write("**Items in this sale:**")
            st.dataframe(get_sale_line_items(pick), hide_index=True, use_container_width=True)
            st.caption("Marking as Paid/Unpaid or deleting will automatically keep your Cash on Hand in sync.")

            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Mark as Paid"):
                    update_payment_status(pick, "Paid")
                    st.success("Updated to Paid.")
                    st.rerun()
            with b2:
                if st.button("Mark as Unpaid"):
                    update_payment_status(pick, "Unpaid")
                    st.success("Updated to Unpaid.")
                    st.rerun()
            with b3:
                if st.button("🗑️ Delete sale (restores stock)"):
                    delete_sale(pick)
                    st.success("Sale deleted and stock restored.")
                    st.rerun()

        csv = sales_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download all sales as CSV", csv, "sales_ledger.csv", "text/csv")


# ============================================================
# CUSTOMERS
# ============================================================

elif page == "Customers":
    st.title("Customers")

    customers_df = get_customers_df()
    if customers_df.empty:
        st.info("No customers yet — they're added automatically the first time you record a sale for them.")
    else:
        summary = get_customer_summary_df()
        show = summary.drop(columns=["CustomerID"]).rename(columns={"LastPurchase": "Last Purchase", "TotalSpent": "Total Spent"})
        show["Total Spent"] = show["Total Spent"].map(peso)
        show["Paid"] = show["Paid"].map(peso)
        show["Outstanding"] = show["Outstanding"].map(peso)
        show["Last Purchase"] = show["Last Purchase"].fillna("—")
        st.dataframe(show, hide_index=True, use_container_width=True)

        st.divider()
        pick = st.selectbox("View a customer's details", customers_df["name"].tolist())
        cust_id = int(customers_df.loc[customers_df["name"] == pick, "id"].iloc[0])

        st.subheader(f"Purchase history — {pick}")
        sales_df = get_sales_summary_df()
        hist = sales_df[sales_df["Customer"] == pick].drop(columns=["Customer"]).copy()
        if hist.empty:
            st.caption("No purchases recorded yet.")
        else:
            hist["Total"] = hist["Total"].map(peso)
            hist["Profit"] = hist["Profit"].map(peso)
            st.dataframe(hist, hide_index=True, use_container_width=True)

        st.subheader(f"Saved prices for {pick}")
        prices_df = get_customer_prices_df(cust_id)
        if prices_df.empty:
            st.caption("No custom prices saved yet — prices are remembered automatically after a sale.")
        else:
            pcol1, pcol2 = st.columns([3, 1])
            with pcol1:
                display_prices = prices_df[["Item", "Price"]].copy()
                display_prices["Price"] = display_prices["Price"].map(peso)
                st.dataframe(display_prices, hide_index=True, use_container_width=True)
            with pcol2:
                remove_item = st.selectbox("Reset an item's price", prices_df["Item"].tolist(), key="reset_price_pick")
                if st.button("Reset to default price"):
                    row_id = int(prices_df.loc[prices_df["Item"] == remove_item, "id"].iloc[0])
                    delete_customer_price(row_id)
                    st.success(f"{remove_item}'s price for {pick} reset to the standard price.")
                    st.rerun()


# ============================================================
# CASH ON HAND
# ============================================================

elif page == "Cash on Hand":
    st.title("Cash on Hand")
    st.caption("Sale payments (marked Paid) and cash-paid restocks are added here automatically. Use the form below for anything else — owner deposits, withdrawals, or other expenses.")

    balance, total_in, total_out = get_cash_balance()
    beginning, start_date = get_beginning_cash()

    c1, c2, c3 = st.columns(3)
    c1.metric("Cash on hand", peso(balance))
    c2.metric("Total cash in", peso(total_in))
    c3.metric("Total cash out", peso(total_out))

    with st.expander("⚙️ Set / update beginning cash"):
        with st.form("beginning_cash_form"):
            new_amount = st.number_input("Beginning cash amount", min_value=0.0, step=100.0, value=float(beginning))
            new_date = st.date_input(
                "As of date",
                value=pd.to_datetime(start_date).date() if start_date else date.today(),
            )
            if st.form_submit_button("Save", type="primary"):
                set_beginning_cash(new_amount, new_date.isoformat())
                st.success("Beginning cash updated.")
                st.rerun()

    st.divider()
    st.subheader("Add a manual cash entry")
    with st.form("manual_cash_form", clear_on_submit=True):
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            tx_type = st.radio("Type", ["In", "Out"], horizontal=True)
        with cc2:
            amount = st.number_input("Amount", min_value=0.0, step=50.0)
        with cc3:
            tx_date = st.date_input("Date", value=date.today())
        category = st.selectbox("Category", ["Owner Deposit", "Withdrawal", "Other Income", "Other Expense"])
        note = st.text_input("Note (optional)")
        if st.form_submit_button("Add entry", type="primary"):
            if amount <= 0:
                st.error("Amount must be greater than 0.")
            else:
                add_cash_transaction(tx_date.isoformat(), tx_type, category, amount, note, ref_type="manual", ref_id=None)
                st.success("Cash entry added.")
                st.rerun()

    st.divider()
    st.subheader("Cash ledger")
    ledger = get_cash_ledger_df()
    if ledger.empty:
        st.caption("No cash transactions yet.")
    else:
        ledger = ledger.sort_values(["Date", "id"]).reset_index(drop=True)
        running = beginning
        balances = []
        for _, row in ledger.iterrows():
            running += row["Amount"] if row["Type"] == "In" else -row["Amount"]
            balances.append(running)
        ledger["Balance"] = balances

        display_ledger = ledger.sort_values(["Date", "id"], ascending=False).drop(columns=["id"]).copy()
        display_ledger["Amount"] = display_ledger["Amount"].map(peso)
        display_ledger["Balance"] = display_ledger["Balance"].map(peso)
        st.dataframe(display_ledger, hide_index=True, use_container_width=True)

        csv = ledger.drop(columns=["id"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download cash ledger as CSV", csv, "cash_ledger.csv", "text/csv")

        manual_df = get_manual_cash_df()
        if not manual_df.empty:
            st.divider()
            st.subheader("Remove a manual entry")
            st.caption("Only entries you added manually can be removed here. Sale and restock entries are managed from their own pages.")
            pick = st.selectbox(
                "Select entry to remove",
                manual_df["id"].tolist(),
                format_func=lambda i: (
                    f"#{i} — {manual_df.loc[manual_df['id']==i,'Date'].values[0]} — "
                    f"{manual_df.loc[manual_df['id']==i,'Category'].values[0]} — "
                    f"{peso(manual_df.loc[manual_df['id']==i,'Amount'].values[0])}"
                ),
            )
            if st.button("🗑️ Remove entry"):
                delete_cash_transaction(pick)
                st.success("Removed.")
                st.rerun()


# ============================================================
# MANAGE ITEMS
# ============================================================

elif page == "Manage Items":
    st.title("Manage Items")

    tab1, tab2 = st.tabs(["➕ Add new item", "✏️ Edit / remove existing item"])

    with tab1:
        with st.form("add_item_form", clear_on_submit=True):
            name = st.text_input("Perfume name")
            unit_measure = st.text_input("Unit of measure", value="30ml bottle")
            c1, c2 = st.columns(2)
            with c1:
                unit_cost = st.number_input("Unit cost", min_value=0.0, step=1.0, format="%.2f")
            with c2:
                selling_price = st.number_input("Selling price", min_value=0.0, step=1.0, format="%.2f")
            c3, c4 = st.columns(2)
            with c3:
                initial_stock = st.number_input("Starting stock", min_value=0.0, step=1.0)
            with c4:
                threshold = st.number_input("Low-stock threshold", min_value=0.0, step=1.0, value=3.0)
            submitted = st.form_submit_button("Add item", type="primary")
            if submitted:
                if not name.strip():
                    st.error("Please enter a name.")
                elif name.strip() in items_df["name"].tolist():
                    st.error("An item with that name already exists.")
                else:
                    add_item(name.strip(), unit_measure, unit_cost, selling_price, initial_stock, threshold)
                    st.success(f"Added {name.strip()}!")
                    st.rerun()

    with tab2:
        if items_df.empty:
            st.caption("No items yet.")
        else:
            selected_name = st.selectbox("Choose an item", items_df["name"].tolist())
            row = items_df[items_df["name"] == selected_name].iloc[0]

            with st.form("edit_item_form"):
                unit_measure = st.text_input("Unit of measure", value=row["unit_measure"])
                c1, c2 = st.columns(2)
                with c1:
                    unit_cost = st.number_input("Unit cost", min_value=0.0, step=1.0, value=float(row["unit_cost"]), format="%.2f")
                with c2:
                    selling_price = st.number_input(
                        "Selling price", min_value=0.0, step=1.0, value=float(row["selling_price"]), format="%.2f"
                    )
                threshold = st.number_input(
                    "Low-stock threshold", min_value=0.0, step=1.0, value=float(row["low_stock_threshold"])
                )
                st.caption(f"Current stock: {row['current_stock']:.0f} — adjust this from the **Stock In / Out** page.")
                st.caption("This is the standard/default selling price. Individual customers can still be charged differently on the Record a Sale page.")
                save = st.form_submit_button("Save changes", type="primary")
                if save:
                    update_item(int(row["id"]), unit_measure, unit_cost, selling_price, threshold)
                    st.success("Item updated.")
                    st.rerun()

            st.divider()
            if st.checkbox("I want to delete this item"):
                if st.button("🗑️ Confirm delete", type="secondary"):
                    ok, msg = delete_item(int(row["id"]))
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
