# Aroma Legante — Inventory & Sales Manager

A Streamlit app for tracking your perfume stock, sales, customers, and cash on hand.

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
that sits next to `app.py`. As long as you keep that file, everything will
still be there next time you run the app — just don't delete it. Back it up
occasionally with the CSV download buttons (e.g. copy it to a cloud drive).

## If the app ever looks dark or hard to read

The app forces a warm, light "boutique" look on purpose, but some browsers
remember a personal dark-mode override. If that ever happens: click the
**⋮ menu (top right)** → **Settings** → set **Theme** to **Light**. This is a
one-time, per-browser setting.

## What's inside

- **Dashboard** — cash on hand, stock value, profit earned, outstanding payables, low-stock alerts
- **Inventory** — all your perfumes with cost, selling price, margin %, live stock counts, and a clear 🟢/🟠 stock status
- **Stock In / Out** — restocking, samples, damage, or any non-sale stock change. If you pay for a restock in cash, enter the amount and it's deducted from Cash on Hand automatically.
- **Record a Sale** — pick a customer from a dropdown (or add a new one), mark paid/unpaid, and set quantity **and price per item** — so regulars can each have their own price for the same perfume. Prices are remembered as that customer's "usual price." Paid sales add to Cash on Hand automatically.
- **Sales & Payments** — full sales ledger, filter by customer or status, mark unpaid sales as paid (or back), delete a mistaken entry — stock and cash both stay in sync automatically.
- **Customers** — a directory of everyone who's bought from you: total spent, paid vs outstanding, purchase history, and their saved custom prices per item.
- **Cash on Hand** — set your beginning cash balance, see your running total, and add manual entries for anything not already tracked (owner deposits, withdrawals, other income/expenses). Includes a full ledger with running balance and CSV export.
- **Manage Items** — add new perfumes as your catalog grows, edit standard cost/selling price, remove items with no sales history.

### How Cash on Hand stays accurate
- Marking a sale **Paid** (when recording it, or later) adds that amount to cash automatically. Switching it back to Unpaid removes it.
- Deleting a sale removes its cash entry too, along with restoring the stock.
- A restock is only deducted from cash if you fill in "Amount paid from cash" on the Stock In / Out page — leave it at 0 if you paid another way, or haven't paid yet.
- Everything else (owner deposits, withdrawals, one-off expenses) goes through the manual entry form on the Cash on Hand page.

Your existing items (Aventus Creed, Le Labo Santal 33, Bleu de Chanel, Dior
Sauvage, Lacoste White, D&G Light Blue, Joe Malone Woodsage & SS, Miss Dior)
are pre-loaded at ₱160 cost with their last known stock counts from your
tracker. Standard selling prices start at ₱0 — set them under **Manage
Items** → Edit. Add your 3 remaining items the same way, and set your
beginning cash under **Cash on Hand**.

## Deploying on Streamlit Community Cloud

1. Push these files to your GitHub repo: `app.py`, `requirements.txt`, `.streamlit/config.toml`, this README
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Repository: your repo (e.g. `yourusername/Aroma-Legante`)
4. Branch: `main`
5. Main file path: `app.py`
6. Deploy

⚠️ Note: Streamlit Cloud can wipe locally-written files (including
`perfume_inventory.db`) when the app restarts or you push new code. Use the
CSV download buttons regularly to keep a backup until you're ready to move
to a persistent cloud database.
