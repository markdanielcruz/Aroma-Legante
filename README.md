# Aroma Legante — Inventory & Sales Manager

A Streamlit app for tracking your perfume stock, sales, customers, and payments.

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
don't delete it. Back it up occasionally with the CSV download buttons on
the Inventory and Sales pages (e.g. copy them to a cloud drive).

## What's inside

- **Dashboard** — stock value, profit earned, outstanding payables, low-stock alerts, customer count
- **Inventory** — all your perfumes with cost, selling price, margin %, live stock counts, and a clear 🟢/🟠 stock status
- **Stock In / Out** — restocking, samples, damage, or any non-sale stock change
- **Record a Sale** — pick a customer from a dropdown (or add a new one on the spot), mark paid/unpaid, and set quantity **and price per item** — so regulars like Bimby or Abbie can each have their own price for the same perfume. Prices you use are remembered as that customer's "usual price" automatically.
- **Sales & Payments** — full sales ledger, filter by customer or payment status, mark unpaid sales as paid, delete a mistaken entry (stock is restored)
- **Customers** — a directory of everyone who's bought from you: total spent, paid vs outstanding, purchase history, and their saved custom prices per item (with a one-click reset back to the standard price)
- **Manage Items** — add new perfumes as your catalog grows, edit standard cost/selling price, remove items with no sales history

Your existing items (Aventus Creed, Le Labo Santal 33, Bleu de Chanel, Dior
Sauvage, Lacoste White, D&G Light Blue, Joe Malone Woodsage & SS, Miss Dior)
are pre-loaded at ₱160 cost with their last known stock counts from your
tracker. Standard selling prices start at ₱0 — set them under **Manage
Items** → Edit. Add your 3 remaining items the same way.

## Deploying on Streamlit Community Cloud

1. Push these files (`app.py`, `requirements.txt`, `.streamlit/config.toml`, this README) to your GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Repository: your repo (e.g. `yourusername/Aroma-Legante`)
4. Branch: `main`
5. Main file path: `app.py`
6. Deploy

⚠️ Note: Streamlit Cloud can wipe locally-written files (including
`perfume_inventory.db`) when the app restarts or you push new code. Use the
CSV download buttons regularly to keep a backup until you're ready to move
to a persistent cloud database.
