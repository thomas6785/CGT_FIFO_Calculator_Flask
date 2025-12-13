# Flask FIFO Capital Gains Calculator

A small Flask app that calculates realized capital gains using FIFO matching. It allows users to upload CSV files containing stock transactions and extracts the transaction `date`, `quantity`, and `price` columns.

## Features
- CSV upload
- Automatic column detection (best-effort)
- User column mapping UI
- FIFO matching for sell transactions
- Per-transaction breakdown and total realized gains

## Quick Start

Install dependencies (inside a virtualenv is recommended). This project targets **Python 3.13**:

```bash
# Ensure Python 3.13 is installed on your system (e.g. `python3.13`)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
export FLASK_APP=app.py
flask run
```

Open your browser at http://127.0.0.1:5000/ and upload a CSV.

## CSV format
The CSV should include columns for transaction date, quantity, and price. The app automatically tries to detect common column names. If detection fails, you'll be prompted to map the columns manually.

- Quantity should be positive for Buy and negative for Sell; the app determines buy/sell from the sign of the quantity.
 - Quantity should be positive for Buy and negative for Sell; the app determines buy/sell from the sign of the quantity.
 - Product column: include a column with the stock symbol or product name (e.g. `product`, `symbol`); the app will group transactions by product and produce a FIFO matching matrix for each product.
- Dates are parsed with `dateutil` and should be in a recognizable format.

## License
MIT
