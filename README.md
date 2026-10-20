# Aroma Legante — Inventory & Sales Manager

A Streamlit app for tracking perfume stock, sales, customers, and cash on hand.

## Where the data is saved

Everything is saved to the Google Sheet **"Aroma Legante — App Database"** through a
small Google Apps Script. The app keeps a fast local copy and sends every change to
the Sheet automatically; when Streamlit restarts, it reloads everything from the Sheet.
A daily copy of the Sheet is kept in the Google Drive folder **Aroma Legante Backups**.

The connection details live in Streamlit **Secrets** (never in this repo):

```toml
apps_script_url = "https://script.google.com/macros/s/.../exec"
apps_script_token = "..."
```

If the Sheet can't be reached when the app starts, the app pauses instead of starting
blank, so an empty app can never overwrite your data.

## Files

- `app.py` — the whole app (styling is built in)
- `requirements.txt` — Python packages
- `.streamlit/config.toml` — theme colors for tables and grids

## Pages

Dashboard · Inventory · Stock In / Out · Record a Sale · Sales & Payments ·
Customers · Cash on Hand · Manage Items · Data & Backup

## Run on your own computer (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

To connect it to the Sheet locally, put the two Secrets lines in `.streamlit/secrets.toml`
next to `app.py` (don't upload that file to GitHub).
