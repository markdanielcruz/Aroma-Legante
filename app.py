"""
Aroma Legante — Inventory & Sales Manager
--------------------------------------------
A single-file Streamlit app.

WHERE YOUR DATA LIVES
    The permanent copy of every item, sale, customer and cash entry is kept
    in your Google Sheet ("Aroma Legante — App Database"), one tab per table.
    The app works on a fast local copy (perfume_inventory.db) and saves every
    change back to the Google Sheet automatically. Whenever the app restarts
    (new code uploaded, app woke up from sleep, reboot) it rebuilds the local
    copy from the Google Sheet — so nothing is lost.

    The connection is a small Google Apps Script attached to the Sheet. Its
    web-app link and password go in Streamlit "Secrets":
        apps_script_url   = "https://script.google.com/macros/s/.../exec"
        apps_script_token = "..."
    Without them, the app still runs but only saves on the server (and can be lost).

Run locally with:
    pip install -r requirements.txt
    streamlit run app.py
"""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

DB_PATH = "perfume_inventory.db"
CURRENCY = "₱"
APP_NAME = "Aroma Legante"
TZ = ZoneInfo("Asia/Manila")


def today_ph():
    """Today's date in the Philippines (the cloud server runs on UTC)."""
    return datetime.now(TZ).date()


st.set_page_config(page_title=APP_NAME, page_icon="🌸", layout="wide")

# ============================================================
# LOOK & FEEL — warm dark boutique palette, built in so it
# always applies even if .streamlit/config.toml is missing
# ============================================================

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

:root { color-scheme: dark !important; }

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stBottomBlockContainer"],
[data-testid="stMain"] {
    background-color: #15110D !important;
}
[data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; }

html, body, .stApp, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #E7DED6;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"],
label, .stSelectbox, .stTextInput, .stNumberInput, .stDateInput {
    color: #E7DED6 !important;
}

h1, h2, h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-weight: 700 !important;
    color: #D9A9B3 !important;
    letter-spacing: 0.2px;
}
h1 {
    font-size: 2.3rem !important;
    border-bottom: 1px solid #3A2E28;
    padding-bottom: 0.5rem;
    margin-bottom: 1.3rem !important;
}
h2, h3 { margin-top: 1.1rem !important; }

/* Metric cards */
[data-testid="stMetricValue"] { color: #D9A9B3 !important; font-weight: 700; font-size: 1.5rem; }
[data-testid="stMetricLabel"] { color: #B8A99E !important; }
[data-testid="stMetric"] {
    background-color: #221C18 !important;
    border-radius: 14px;
    padding: 16px 18px;
    border: 1px solid #3A2E28;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #1C1714 !important;
    border-right: 1px solid #3A2E28;
}
section[data-testid="stSidebar"] * { color: #E7DED6 !important; }
section[data-testid="stSidebar"] h1 {
    font-size: 1.5rem !important;
    border-bottom: none;
    margin-bottom: 0 !important;
    padding-bottom: 0;
}
section[data-testid="stSidebar"] .brand-caption { color: #9C8880 !important; }

input[type="radio"] { accent-color: #C98A96; }
section[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 8px 10px;
    border-radius: 8px;
    margin-bottom: 2px;
}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background-color: #241D19; }
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background-color: #3A2E28;
    font-weight: 600;
}

/* Alerts (info/success/error/warning) — one calm, consistent card style */
[data-testid="stAlert"] {
    background-color: #221C18 !important;
    border: 1px solid #3A2E28 !important;
}
[data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #E7DED6 !important; }

/* Tables / editors — dark surround so there's no bright halo */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid #3A2E28;
    border-radius: 8px;
}

/* Inputs */
input, textarea, select, .stTextInput input, .stNumberInput input {
    background-color: #221C18 !important;
    color: #E7DED6 !important;
    border-color: #3A2E28 !important;
}

div.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid #C98A96;
    color: #E7DED6;
    background-color: #221C18;
}
div.stButton > button[kind="primary"] { background-color: #C98A96; color: #171310 !important; border: none; }
div.stButton > button[kind="primary"]:hover { background-color: #B87786; }
div.stDownloadButton > button { border-radius: 8px; font-weight: 600; }

hr, [data-testid="stDivider"] { border-color: #3A2E28 !important; }

.brand-caption {
    color: #9C8880;
    font-size: 0.82rem;
    margin-top: -6px;
    margin-bottom: 16px;
    letter-spacing: 1px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# DATABASE (local working copy)
# ============================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn):
    """Create any missing tables (safe to run any time)."""
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
    c.execute(
        """CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )"""
    )
    conn.commit()


def init_db():
    conn = get_conn()
    create_schema(conn)
    c = conn.cursor()

    # Seed with the items from the original tracker — ONLY on a brand-new database.
    c.execute("SELECT value FROM app_meta WHERE key='seeded'")
    already_seeded = c.fetchone() is not None
    c.execute("SELECT COUNT(*) FROM items")
    if not already_seeded and c.fetchone()[0] == 0:
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
        today = today_ph().isoformat()
        for name, um, cost, stock in seed:
            c.execute(
                """INSERT INTO items
                   (name, unit_measure, unit_cost, selling_price, current_stock, low_stock_threshold, date_added)
                   VALUES (?, ?, ?, 0, ?, 3, ?)""",
                (name, um, cost, stock, today),
            )
        conn.commit()
    if not already_seeded:
        c.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('seeded', '1')")
        conn.commit()

    # Backfill a customers directory from any sales already on file (safe to run every start)
    c.execute("SELECT DISTINCT customer_name FROM sales")
    for (nm,) in c.fetchall():
        if nm and str(nm).strip():
            c.execute(
                "INSERT OR IGNORE INTO customers (name, date_added) VALUES (?, ?)",
                (str(nm).strip(), today_ph().isoformat()),
            )

    c.execute("SELECT COUNT(*) FROM cash_settings")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO cash_settings (id, beginning_cash, start_date) VALUES (1, 0, ?)",
            (today_ph().isoformat(),),
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
        (name, unit_measure, unit_cost, selling_price, initial_stock, threshold, today_ph().isoformat()),
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
    _sync_state()["allow_empty_items"] = True  # you deleted on purpose
    return True, "Item deleted."


def bulk_upsert_items(rows):
    """rows: list of dicts with name, unit_measure, unit_cost, selling_price, current_stock, low_stock_threshold.
    Existing items are matched (and updated) by name; anything new is inserted."""
    conn = get_conn()
    c = conn.cursor()
    added, updated = 0, 0
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        c.execute("SELECT id FROM items WHERE name=?", (name,))
        existing = c.fetchone()
        if existing:
            c.execute(
                """UPDATE items SET unit_measure=?, unit_cost=?, selling_price=?, current_stock=?, low_stock_threshold=? WHERE id=?""",
                (
                    r.get("unit_measure") or "",
                    float(r.get("unit_cost") or 0),
                    float(r.get("selling_price") or 0),
                    float(r.get("current_stock") or 0),
                    float(r.get("low_stock_threshold") or 3),
                    existing[0],
                ),
            )
            updated += 1
        else:
            c.execute(
                """INSERT INTO items (name, unit_measure, unit_cost, selling_price, current_stock, low_stock_threshold, date_added)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    r.get("unit_measure") or "",
                    float(r.get("unit_cost") or 0),
                    float(r.get("selling_price") or 0),
                    float(r.get("current_stock") or 0),
                    float(r.get("low_stock_threshold") or 3),
                    today_ph().isoformat(),
                ),
            )
            added += 1
    conn.commit()
    conn.close()
    return added, updated


def reset_all_stock_to_zero():
    conn = get_conn()
    conn.execute("UPDATE items SET current_stock = 0")
    conn.commit()
    conn.close()


def full_wipe_all_data():
    """Deletes everything — items, sales, customers, stock history, cash records. Cannot be undone."""
    conn = get_conn()
    c = conn.cursor()
    for table in ["sale_items", "sales", "stock_movements", "customer_prices", "customers", "items", "cash_transactions"]:
        c.execute(f"DELETE FROM {table}")
    c.execute("DELETE FROM sqlite_sequence")
    c.execute("UPDATE cash_settings SET beginning_cash = 0, start_date = ?", (today_ph().isoformat(),))
    conn.commit()
    conn.close()
    _sync_state()["allow_empty_items"] = True


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
        c.execute("INSERT INTO customers (name, date_added) VALUES (?, ?)", (name, today_ph().isoformat()))
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
    return (row[0], row[1]) if row else (0.0, today_ph().isoformat())


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


# ============================================================
# GOOGLE SHEET — permanent storage (through Google Apps Script)
# ------------------------------------------------------------
#   * On startup: if the Sheet has data, the local copy is rebuilt from it.
#     If the Sheet is empty (very first time), local data is copied up to it.
#   * After every click: any table that changed is sent to the Sheet.
#   * If the Sheet can't be reached at startup, the app stops instead of
#     starting blank — so an empty app can never overwrite your Sheet.
# ============================================================

SHEET_TABLES = [
    "items", "sales", "sale_items", "customers", "customer_prices",
    "stock_movements", "cash_transactions", "cash_settings", "app_meta",
]
SHEET_ID = "1t_AqDymCXbsEBHjJlpzw1oaynednm22t41JQEdz3WMQ"
SHEET_LINK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"


def _secret(name):
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:  # no secrets at all
        return ""


def sheets_configured():
    url = _secret("apps_script_url")
    return url.startswith("https://script.google.com/") and url.rstrip("/").endswith("/exec") and bool(_secret("apps_script_token"))


@st.cache_resource(show_spinner=False)
def _sync_state():
    # Shared by every browser tab using this app (one copy per server process)
    return {
        "lock": threading.RLock(),
        "loaded": False,            # local copy has been matched with the Sheet
        "hashes": {},               # fingerprint of each table as last saved to the Sheet
        "allow_empty_items": False, # set only when you delete items on purpose
        "error": None,
        "last_sync": None,
    }


class SheetError(Exception):
    pass


def _parse_reply(resp):
    if resp.status_code != 200:
        raise SheetError(f"Google replied with error {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        raise SheetError(
            "Google sent back a web page instead of data. Usually this means the Apps Script "
            "web app isn't deployed with \"Who has access: Anyone\", or the URL in Secrets is wrong."
        )
    if not data.get("ok"):
        raise SheetError(data.get("error") or "unknown error from the Apps Script")
    return data


def _api_load():
    resp = requests.get(
        _secret("apps_script_url"),
        params={"token": _secret("apps_script_token")},
        timeout=60,
    )
    return _parse_reply(resp).get("tables", {})


def _api_save(tables, allow_empty_items=False):
    body = json.dumps(
        {"token": _secret("apps_script_token"), "tables": tables, "allow_empty_items": bool(allow_empty_items)}
    )
    resp = requests.post(
        _secret("apps_script_url"),
        data=body.encode("utf-8"),
        headers={"Content-Type": "text/plain;charset=utf-8"},
        timeout=90,
    )
    _parse_reply(resp)


def _table_snapshot(conn, table):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid").fetchall()
    fingerprint = hashlib.md5(repr((cols, rows)).encode("utf-8")).hexdigest()
    return cols, rows, fingerprint


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def push_changes(force=False):
    """Send every table that changed since the last save to the Google Sheet."""
    if not sheets_configured():
        return
    state = _sync_state()
    with state["lock"]:
        if not state["loaded"]:
            return  # never write to the Sheet before we've read it
        conn = get_conn()
        changed = {}
        for t in SHEET_TABLES:
            cols, rows, fp = _table_snapshot(conn, t)
            if force or state["hashes"].get(t) != fp:
                changed[t] = (cols, rows, fp)
        conn.close()
        if not changed:
            return
        payload = {t: [cols] + [[_cell(v) for v in r] for r in rows] for t, (cols, rows, fp) in changed.items()}
        try:
            _api_save(payload, allow_empty_items=state["allow_empty_items"])
            for t, (cols, rows, fp) in changed.items():
                state["hashes"][t] = fp
            state["allow_empty_items"] = False
            state["error"] = None
            state["last_sync"] = datetime.now(TZ)
        except Exception as e:  # change stays here; it retries on the next click
            state["error"] = f"{type(e).__name__}: {e}"


def _rebuild_local_from_sheet(tables):
    """Replace the local database with the contents of the Google Sheet."""
    tmp_path = DB_PATH + ".loading"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    conn = sqlite3.connect(tmp_path)
    create_schema(conn)
    for t in SHEET_TABLES:
        values = tables.get(t) or []
        if len(values) < 2:
            continue
        known = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        header = [str(h).strip() for h in values[0]]
        idx = [(i, h) for i, h in enumerate(header) if h in known]
        if not idx:
            continue
        cols = [h for _, h in idx]
        sql = f"INSERT OR REPLACE INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        for raw in values[1:]:
            row = [str(raw[i]) if i < len(raw) and raw[i] is not None else "" for i, _ in idx]
            if all(v.strip() == "" for v in row):
                continue
            conn.execute(sql, [None if v == "" else v for v in row])
    conn.commit()
    conn.close()
    os.replace(tmp_path, DB_PATH)


def _remember_saved_state():
    state = _sync_state()
    conn = get_conn()
    for t in SHEET_TABLES:
        state["hashes"][t] = _table_snapshot(conn, t)[2]
    conn.close()


def load_from_sheet():
    """Match the local copy with the Google Sheet. Runs once per app start (and on Reload)."""
    state = _sync_state()
    with state["lock"]:
        tables = _api_load()
        sheet_has_data = any(len(tables.get(t) or []) > 1 for t in SHEET_TABLES)
        if sheet_has_data:
            _rebuild_local_from_sheet(tables)
            init_db()  # fills in anything missing; never re-seeds (the Sheet remembers)
            _remember_saved_state()
            state["loaded"] = True
            push_changes()  # only sends something if init_db had to fill a gap
        else:
            # Brand-new, empty Sheet: copy whatever is here up to it
            init_db()
            state["loaded"] = True
            push_changes(force=True)
        if state["error"] is None:
            state["last_sync"] = datetime.now(TZ)


def startup():
    state = _sync_state()
    if not sheets_configured():
        init_db()
        return
    with state["lock"]:
        if state["loaded"]:
            return
        try:
            load_from_sheet()
        except Exception as e:
            st.error(
                "**Couldn't open your Google Sheet, so the app has paused to protect your data.**\n\n"
                f"Details: `{type(e).__name__}: {e}`\n\n"
                "Check the setup guide: the Apps Script must be deployed as a Web app with "
                "\"Execute as: Me\" and \"Who has access: Anyone\", and the URL + token in "
                "Streamlit Secrets must match."
            )
            if st.button("🔄 Try again", type="primary"):
                st.rerun()
            st.stop()


startup()
push_changes()  # saves whatever the previous click changed


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.markdown(f"# {APP_NAME}")
st.sidebar.markdown('<div class="brand-caption">INVENTORY &amp; SALES</div>', unsafe_allow_html=True)
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Inventory", "Stock In / Out", "Record a Sale", "Sales & Payments", "Customers", "Cash on Hand", "Manage Items", "Data & Backup"],
    label_visibility="collapsed",
)

_state = _sync_state()
st.sidebar.markdown("---")
if not sheets_configured():
    st.sidebar.warning("⚠️ Not connected to Google Sheets — data is only saved on this server and can be lost. See **Data & Backup**.")
elif _state["error"]:
    st.sidebar.error("⚠️ Last save to Google Sheets failed — it will retry automatically. See **Data & Backup**.")
elif _state["last_sync"]:
    st.sidebar.caption(f"✅ Saved to Google Sheets · {_state['last_sync']:%b %d, %I:%M %p}")

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
            st.dataframe(show, hide_index=True, width="stretch")

        st.subheader("Recent sales")
        if sales_df.empty:
            st.caption("No sales recorded yet.")
        else:
            recent = sales_df.head(5)[["Date", "Customer", "Status", "Total", "Profit"]].copy()
            recent["Total"] = recent["Total"].map(peso)
            recent["Profit"] = recent["Profit"].map(peso)
            st.dataframe(recent, hide_index=True, width="stretch")


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
            width="stretch",
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
                move_date = st.date_input("Date", value=today_ph())
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
            st.dataframe(moves.drop(columns=["id"]), hide_index=True, width="stretch")


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
            sale_date = st.date_input("Date", value=today_ph())
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
            width="stretch",
            key=editor_key,
        )

        note = st.text_input("Note (optional)", placeholder="e.g. picked up personally, half payment, etc.")
        remember_prices = st.checkbox(
            f"💾 Remember these prices as {customer_name or 'this customer'}'s usual pricing",
            value=True,
            disabled=not bool(customer_name),
        )

        chosen = edited[edited["Quantity"].fillna(0) > 0]
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
        st.dataframe(show, hide_index=True, width="stretch")

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
            st.dataframe(get_sale_line_items(pick), hide_index=True, width="stretch")
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
        st.dataframe(show, hide_index=True, width="stretch")

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
            st.dataframe(hist, hide_index=True, width="stretch")

        st.subheader(f"Saved prices for {pick}")
        prices_df = get_customer_prices_df(cust_id)
        if prices_df.empty:
            st.caption("No custom prices saved yet — prices are remembered automatically after a sale.")
        else:
            pcol1, pcol2 = st.columns([3, 1])
            with pcol1:
                display_prices = prices_df[["Item", "Price"]].copy()
                display_prices["Price"] = display_prices["Price"].map(peso)
                st.dataframe(display_prices, hide_index=True, width="stretch")
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
                value=pd.to_datetime(start_date).date() if start_date else today_ph(),
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
            tx_date = st.date_input("Date", value=today_ph())
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
        st.dataframe(display_ledger, hide_index=True, width="stretch")

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

    _flash = st.session_state.pop("_flash", None)
    if _flash:
        kind, msg = _flash
        (st.success if kind == "success" else st.error)(msg)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Add new item", "✏️ Edit / remove one item", "📋 Bulk edit", "⬆️⬇️ Import / Export"]
    )

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
                unit_measure = st.text_input("Unit of measure", value=row["unit_measure"] or "")
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

    with tab3:
        st.caption(
            "Edit cells directly, use the trash icon on a row to delete it, or scroll to the bottom "
            "row to add a new item — like a spreadsheet. Click **Save all changes** when you're done."
        )
        cols = ["id", "name", "unit_measure", "unit_cost", "selling_price", "current_stock", "low_stock_threshold"]
        if items_df.empty:
            base_df = pd.DataFrame(columns=cols)
        else:
            base_df = items_df[cols].copy()

        rename_map = {
            "id": "ID",
            "name": "Item",
            "unit_measure": "Unit",
            "unit_cost": "Cost",
            "selling_price": "Selling Price",
            "current_stock": "Current Stock",
            "low_stock_threshold": "Threshold",
        }
        editable_df = base_df.rename(columns=rename_map)

        edited_bulk = st.data_editor(
            editable_df,
            num_rows="dynamic",
            width="stretch",
            key="bulk_items_editor",
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True, width="small"),
                "Cost": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f", min_value=0.0),
                "Selling Price": st.column_config.NumberColumn(format=f"{CURRENCY}%.2f", min_value=0.0),
                "Current Stock": st.column_config.NumberColumn(min_value=0.0),
                "Threshold": st.column_config.NumberColumn(min_value=0.0),
            },
        )

        if st.button("💾 Save all changes", type="primary", key="save_bulk_items"):
            original_ids = set(base_df["id"].dropna().astype(int).tolist())
            kept_ids = set(pd.to_numeric(edited_bulk["ID"], errors="coerce").dropna().astype(int).tolist())
            deleted_ids = original_ids - kept_ids

            blocked = []
            deleted_count = 0
            for did in deleted_ids:
                ok, msg = delete_item(int(did))
                if ok:
                    deleted_count += 1
                else:
                    blocked.append((did, msg))

            rows_to_upsert = []
            for _, r in edited_bulk.iterrows():
                name = str(r.get("Item", "") or "").strip()
                if not name or name.lower() == "nan":
                    continue
                rows_to_upsert.append(
                    {
                        "name": name,
                        "unit_measure": r.get("Unit") or "",
                        "unit_cost": r.get("Cost") or 0,
                        "selling_price": r.get("Selling Price") or 0,
                        "current_stock": r.get("Current Stock") or 0,
                        "low_stock_threshold": r.get("Threshold") or 3,
                    }
                )
            added, updated = bulk_upsert_items(rows_to_upsert)

            parts = []
            if added:
                parts.append(f"{added} added")
            if updated:
                parts.append(f"{updated} updated")
            if deleted_count:
                parts.append(f"{deleted_count} deleted")
            st.success("Saved — " + ", ".join(parts) if parts else "No changes to save.")
            for did, msg in blocked:
                st.warning(msg)
            st.rerun()

    with tab4:
        st.caption(
            "Download your current items as a CSV — handy as a backup, or as a template you can edit "
            "in Excel/Google Sheets and re-upload. Matching is done by item name: existing names get "
            "updated, new names get added."
        )
        export_cols = ["name", "unit_measure", "unit_cost", "selling_price", "current_stock", "low_stock_threshold"]
        export_rename = {
            "name": "Item", "unit_measure": "Unit", "unit_cost": "Cost",
            "selling_price": "Selling Price", "current_stock": "Current Stock", "low_stock_threshold": "Threshold",
        }
        if items_df.empty:
            export_df = pd.DataFrame(columns=list(export_rename.values()))
        else:
            export_df = items_df[export_cols].rename(columns=export_rename)
        st.download_button(
            "⬇️ Download items as CSV",
            export_df.to_csv(index=False).encode("utf-8"),
            "aroma_legante_items.csv",
            "text/csv",
        )

        st.divider()
        uploaded = st.file_uploader("Upload a CSV to bulk add/update items", type=["csv"])
        if uploaded is not None:
            try:
                upload_df = pd.read_csv(uploaded)
                required_cols = {"Item", "Unit", "Cost", "Selling Price", "Current Stock", "Threshold"}
                missing = required_cols - set(upload_df.columns)
                if missing:
                    st.error(f"Missing column(s): {', '.join(sorted(missing))}. Please match the template from the download button above.")
                else:
                    st.write("Preview:")
                    st.dataframe(upload_df, hide_index=True, width="stretch")
                    if st.button("✅ Confirm import", type="primary"):
                        upload_df = upload_df.fillna({"Unit": "", "Cost": 0, "Selling Price": 0, "Current Stock": 0, "Threshold": 3})
                        rows = [
                            {
                                "name": str(r["Item"]).strip(),
                                "unit_measure": str(r.get("Unit", "") or ""),
                                "unit_cost": r.get("Cost", 0),
                                "selling_price": r.get("Selling Price", 0),
                                "current_stock": r.get("Current Stock", 0),
                                "low_stock_threshold": r.get("Threshold", 3),
                            }
                            for _, r in upload_df.iterrows()
                            if str(r["Item"]).strip() and str(r["Item"]).strip().lower() != "nan"
                        ]
                        added, updated = bulk_upsert_items(rows)
                        st.success(f"Import complete — {added} added, {updated} updated.")
                        st.rerun()
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")

    st.divider()
    with st.expander("⚠️ Danger zone"):
        st.markdown("**Reset all stock counts to 0** — keeps your items, costs, and prices, just zeroes out quantities. Useful before a fresh physical count.")
        if st.checkbox("I understand this will zero out every item's stock count", key="confirm_reset_stock"):
            def _do_reset_stock():
                reset_all_stock_to_zero()
                st.session_state["confirm_reset_stock"] = False
                st.session_state.pop("bulk_items_editor", None)
                st.session_state["_flash"] = ("success", "All stock counts reset to 0.")

            st.button("Reset all stock to 0", key="do_reset_stock", on_click=_do_reset_stock)

        st.markdown("---")
        st.markdown(
            "**Wipe everything and start completely fresh** — permanently deletes ALL items, sales, "
            "customers, stock history, and cash records (in the Google Sheet too). This cannot be undone "
            "from the app — though the daily Drive backup will still have yesterday's copy."
        )
        st.text_input("Type DELETE (all caps) to confirm", key="wipe_confirm_text")

        def _do_full_wipe():
            if st.session_state.get("wipe_confirm_text", "").strip() == "DELETE":
                full_wipe_all_data()
                st.session_state["wipe_confirm_text"] = ""
                st.session_state.pop("bulk_items_editor", None)
                st.session_state["_flash"] = ("success", "Everything has been wiped. Add your items to get started again.")
            else:
                st.session_state["_flash"] = ("error", "Type DELETE (all caps) in the box first to confirm.")

        st.button("🗑️ Wipe everything", key="do_full_wipe", on_click=_do_full_wipe)


# ============================================================
# DATA & BACKUP
# ============================================================

elif page == "Data & Backup":
    st.title("Data & Backup")

    _flash = st.session_state.pop("_flash_backup", None)
    if _flash:
        kind, msg = _flash
        (st.success if kind == "success" else st.error)(msg)

    st.subheader("Google Sheet")
    if not sheets_configured():
        st.warning(
            "Not connected. Right now your data only lives on this server, and Streamlit Cloud "
            "deletes it whenever the app restarts or you upload new code. Follow the SETUP GUIDE "
            "to connect your Google Sheet (about 5 minutes, no coding)."
        )
    else:
        st.markdown(f"Connected — every change is saved to [your Google Sheet]({SHEET_LINK}) automatically, "
                    "and a full copy is kept each day in the **Aroma Legante Backups** folder in your Google Drive.")
        if _state["error"]:
            st.error(f"Last save failed (it will retry on your next click): `{_state['error']}`")
            if st.button("🔁 Retry saving now"):
                push_changes(force=True)
                st.rerun()
        elif _state["last_sync"]:
            st.caption(f"Last saved: {_state['last_sync']:%B %d, %Y %I:%M:%S %p}")

        st.caption(
            "Edited the Google Sheet by hand? Click below to load those changes into the app. "
            "(Best to make changes in the app itself — hand edits must keep the same columns.)"
        )
        if st.button("🔄 Reload from Google Sheet"):
            try:
                with _state["lock"]:
                    _state["loaded"] = False
                    load_from_sheet()
                st.session_state["_flash_backup"] = ("success", "Reloaded everything from the Google Sheet.")
            except Exception as e:
                _state["loaded"] = True  # keep working from the local copy
                st.session_state["_flash_backup"] = ("error", f"Couldn't reload: {type(e).__name__}: {e}")
            st.rerun()

    st.divider()
    st.subheader("Full backup file")
    st.caption(
        "Downloads everything — items, sales, customers, saved prices, stock history and cash — "
        "as one file. Keep a copy somewhere safe every now and then."
    )
    with open(DB_PATH, "rb") as f:
        db_bytes = f.read()
    st.download_button(
        "⬇️ Download full backup",
        db_bytes,
        f"aroma_legante_backup_{today_ph().isoformat()}.db",
        "application/octet-stream",
    )

    st.markdown("**Restore from a backup file**")
    st.caption("⚠️ This replaces ALL current data (and the Google Sheet) with the contents of the backup file.")
    _rk = st.session_state.setdefault("_restore_round", 0)
    restore_file = st.file_uploader("Choose a backup file (.db)", type=["db", "sqlite", "sqlite3"], key=f"restore_upload_{_rk}")
    if restore_file is not None:
        if st.checkbox("I understand this replaces all current data", key=f"confirm_restore_{_rk}"):
            if st.button("♻️ Restore this backup", type="primary"):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                tmp.write(restore_file.getvalue())
                tmp.close()
                try:
                    chk = sqlite3.connect(tmp.name)
                    tables = {r[0] for r in chk.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    chk.close()
                    if not {"items", "sales", "sale_items"}.issubset(tables):
                        raise ValueError("this doesn't look like an Aroma Legante backup file")
                    with _state["lock"]:
                        shutil.copyfile(tmp.name, DB_PATH)
                        init_db()
                        _state["allow_empty_items"] = True
                        push_changes(force=True)
                    if sheets_configured() and _state["error"]:
                        st.session_state["_flash_backup"] = ("error", "Restored here, but saving to Google Sheets failed — it will retry.")
                    else:
                        st.session_state["_flash_backup"] = ("success", "Backup restored.")
                except Exception as e:
                    st.session_state["_flash_backup"] = ("error", f"Couldn't restore: {e}")
                finally:
                    os.remove(tmp.name)
                st.session_state["_restore_round"] = _rk + 1
                st.rerun()


# Save anything changed during this page load
push_changes()
