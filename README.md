# Perfume Inventory & Sales Manager

A Streamlit app for tracking your perfume stock, sales, and payments.

## Setup (one-time)

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

This opens the app in your browser (usually http://localhost:8501). Keep the
terminal window open while you use it.

Your data is saved automatically to a file called `perfume_inventory.db`
that sits next to `app.py`. As long as you keep that file, your inventory
and sales history will still be there next time you run the app — just
don't delete it. Back it up occasionally (e.g. copy it to a cloud drive).

## What's inside

- **Dashboard** — stock value, profit earned, outstanding payables, low-stock alerts
- **Inventory** — all your perfumes with cost, selling price, margin %, and live stock counts
- **Stock In / Out** — restocking, samples, damage, or any non-sale stock change
- **Record a Sale** — pick a customer, mark paid/unpaid, choose quantities per item — stock and profit are calculated automatically
- **Sales & Payments** — full sales ledger, filter by customer or payment status, mark unpaid sales as paid, delete a mistaken entry (stock is restored)
- **Manage Items** — add new perfumes as your catalog grows, edit cost/selling price, remove items you no longer carry

Your existing items (Aventus Creed, Le Labo Santal 33, Bleu de Chanel, Dior
Sauvage, Lacoste White, D&G Light Blue, Joe Malone Woodsage & SS, Miss Dior)
are pre-loaded at ₱160 cost with their last known stock counts from your
tracker. Selling prices start at ₱0 — set them under **Manage Items** →
Edit. Add your 3 remaining items the same way.
