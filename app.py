"""
Perfume Business Inventory & Sales Manager
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

st.set_page_config(page_title="Perfume Inventory Manager", page_icon="🌸", layout="wide")


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
            movement_type TEXT NOT NULL,   -- 'In' or 'Out'
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
    conn.commit()

    # Seed with the items visible in the user's existing tracker, only once
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
        return False, "This item has sales history and can't be deleted (to keep your records intact). You can rename its cost/price instead, or set its stock to 0."
    c.execute("DELETE FROM stock_movements WHERE item_id=?", (item_id,))
    c.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return True, "Item deleted."


# ---------- stock movements ----------

def record_stock_movement(item_id, movement_type, quantity, reason, move_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO stock_movements (item_id, move_date, movement_type, quantity, reason) VALUES (?, ?, ?, ?, ?)",
        (item_id, move_date, movement_type, quantity, reason),
    )
    if movement_type == "In":
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id=?", (quantity, item_id))
    else:
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id=?", (quantity, item_id))
    conn.commit()
    conn.close()


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
    for li in line_items:
        c.execute(
            """INSERT INTO sale_items (sale_id, item_id, item_name, quantity, unit_cost, unit_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sale_id, li["item_id"], li["item_name"], li["quantity"], li["unit_cost"], li["unit_price"]),
        )
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id=?", (li["quantity"], li["item_id"]))
    conn.commit()
    conn.close()
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
    conn.execute("UPDATE sales SET payment_status=? WHERE id=?", (status, sale_id))
    conn.commit()
    conn.close()


def delete_sale(sale_id):
    """Delete a sale and restore the stock it had taken out."""
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


# ============================================================
# HELPERS
# ============================================================

def peso(x):
    try:
        return f"{CURRENCY}{x:,.2f}"
    except (TypeError, ValueError):
        return f"{CURRENCY}0.00"


init_db()


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("🌸 Perfume Biz")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Inventory", "Stock In / Out", "Record a Sale", "Sales & Payments", "Manage Items"],
)

items_df = get_items_df()


# ============================================================
# DASHBOARD
# ============================================================

if page == "Dashboard":
    st.title("📊 Dashboard")

    if items_df.empty:
        st.info("No items yet — add your first perfume under **Manage Items**.")
    else:
        total_items = len(items_df)
        total_units = items_df["current_stock"].sum()
        stock_value_cost = (items_df["current_stock"] * items_df["unit_cost"]).sum()
        stock_value_retail = (items_df["current_stock"] * items_df["selling_price"]).sum()

        sales_df = get_sales_summary_df()
        realized_profit = sales_df.loc[sales_df["Status"] == "Paid", "Profit"].sum() if not sales_df.empty else 0
        pending_profit = sales_df.loc[sales_df["Status"] == "Unpaid", "Profit"].sum() if not sales_df.empty else 0
        outstanding_payables = sales_df.loc[sales_df["Status"] == "Unpaid", "Total"].sum() if not sales_df.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Items tracked", total_items)
        c2.metric("Total units in stock", f"{total_units:,.0f}")
        c3.metric("Stock value (at cost)", peso(stock_value_cost))
        c4.metric("Stock value (at retail)", peso(stock_value_retail))

        c5, c6, c7 = st.columns(3)
        c5.metric("Profit earned (paid sales)", peso(realized_profit))
        c6.metric("Profit pending (unpaid sales)", peso(pending_profit))
        c7.metric("Outstanding payables", peso(outstanding_payables))

        st.divider()

        low_stock = items_df[items_df["current_stock"] <= items_df["low_stock_threshold"]]
        st.subheader("⚠️ Low stock alerts")
        if low_stock.empty:
            st.success("All items are above their low-stock threshold.")
        else:
            show = low_stock[["name", "current_stock", "low_stock_threshold", "unit_measure"]].rename(
                columns={"name": "Item", "current_stock": "In Stock", "low_stock_threshold": "Threshold", "unit_measure": "Unit"}
            )
            st.dataframe(show, hide_index=True, use_container_width=True)

        st.subheader("🕒 Recent sales")
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
    st.title("📦 Inventory")

    if items_df.empty:
        st.info("No items yet — add your first perfume under **Manage Items**.")
    else:
        view = items_df.copy()
        view["margin"] = view["selling_price"] - view["unit_cost"]
        view["margin_pct"] = view.apply(
            lambda r: (r["margin"] / r["selling_price"] * 100) if r["selling_price"] > 0 else 0, axis=1
        )
        view["stock_value"] = view["current_stock"] * view["unit_cost"]
        view["low"] = view["current_stock"] <= view["low_stock_threshold"]

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
        )[["Item", "Unit", "Cost", "Selling Price", "Profit/Unit", "Margin %", "In Stock", "Stock Value (cost)", "low"]]

        def highlight_low(row):
            color = "background-color: #ffe3e3" if row["low"] else ""
            return [color] * len(row)

        styled = display.drop(columns=["low"]).style.apply(
            lambda _: ["background-color: #ffe3e3" if low else "" for low in display["low"]], axis=0
        )
        fmt = {
            "Cost": lambda x: peso(x),
            "Selling Price": lambda x: peso(x),
            "Profit/Unit": lambda x: peso(x),
            "Margin %": lambda x: f"{x:.0f}%",
            "Stock Value (cost)": lambda x: peso(x),
        }
        styled = styled.format(fmt)
        st.dataframe(styled, hide_index=True, use_container_width=True)
        st.caption("Rows highlighted in red are at or below their low-stock threshold.")

        csv = display.drop(columns=["low"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download inventory as CSV", csv, "inventory.csv", "text/csv")


# ============================================================
# STOCK IN / OUT
# ============================================================

elif page == "Stock In / Out":
    st.title("🔄 Stock In / Out")
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
            submitted = st.form_submit_button("Save movement", type="primary")

            if submitted:
                if quantity <= 0:
                    st.error("Quantity must be greater than 0.")
                else:
                    item_row = items_df[items_df["name"] == item_name].iloc[0]
                    if movement_type == "Out" and quantity > item_row["current_stock"]:
                        st.error(f"Only {item_row['current_stock']:.0f} in stock for {item_name} — can't remove {quantity:.0f}.")
                    else:
                        record_stock_movement(int(item_row["id"]), movement_type, quantity, reason, move_date.isoformat())
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
    st.title("🛒 Record a Sale")

    if items_df.empty:
        st.info("Add items first under **Manage Items**.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            customer_name = st.text_input("Customer name", placeholder="e.g. Bimby")
        with col2:
            sale_date = st.date_input("Date", value=date.today())
        with col3:
            payment_status = st.radio("Payment status", ["Paid", "Unpaid"], horizontal=True)

        st.markdown("**Items purchased** — enter quantity for each item being bought:")

        editor_source = items_df[["id", "name", "current_stock", "selling_price", "unit_cost"]].copy()
        editor_source["Quantity"] = 0
        editor_display = editor_source.rename(
            columns={"name": "Item", "current_stock": "Available", "selling_price": "Unit Price"}
        )[["Item", "Available", "Unit Price", "Quantity"]]

        edited = st.data_editor(
            editor_display,
            column_config={
                "Item": st.column_config.TextColumn(disabled=True),
                "Available": st.column_config.NumberColumn(disabled=True),
                "Unit Price": st.column_config.NumberColumn(disabled=True, format=f"{CURRENCY}%.2f"),
                "Quantity": st.column_config.NumberColumn(min_value=0, step=1),
            },
            hide_index=True,
            use_container_width=True,
            key="sale_editor",
        )

        note = st.text_input("Note (optional)", placeholder="e.g. picked up personally, half payment, etc.")

        # live preview of total & profit
        chosen = edited[edited["Quantity"] > 0]
        if not chosen.empty:
            preview_rows = []
            total = 0.0
            profit = 0.0
            for _, row in chosen.iterrows():
                src = items_df[items_df["name"] == row["Item"]].iloc[0]
                line_total = row["Quantity"] * src["selling_price"]
                line_profit = row["Quantity"] * (src["selling_price"] - src["unit_cost"])
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
            if not customer_name.strip():
                st.error("Please enter a customer name.")
            elif chosen.empty:
                st.error("Please enter a quantity for at least one item.")
            else:
                # validate stock
                problems = []
                line_items = []
                for _, row in chosen.iterrows():
                    src = items_df[items_df["name"] == row["Item"]].iloc[0]
                    if row["Quantity"] > src["current_stock"]:
                        problems.append(f"{row['Item']}: only {src['current_stock']:.0f} in stock")
                    else:
                        line_items.append(
                            {
                                "item_id": int(src["id"]),
                                "item_name": src["name"],
                                "quantity": float(row["Quantity"]),
                                "unit_cost": float(src["unit_cost"]),
                                "unit_price": float(src["selling_price"]),
                            }
                        )
                if problems:
                    st.error("Not enough stock for: " + "; ".join(problems))
                else:
                    record_sale(customer_name.strip(), sale_date.isoformat(), payment_status, note, line_items)
                    st.success(f"Sale recorded for {customer_name.strip()}!")
                    st.rerun()


# ============================================================
# SALES & PAYMENTS
# ============================================================

elif page == "Sales & Payments":
    st.title("📋 Sales & Payments")

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
# MANAGE ITEMS
# ============================================================

elif page == "Manage Items":
    st.title("⚙️ Manage Items")

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
