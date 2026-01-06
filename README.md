# Flask FIFO Capital Gains Calculator

A small Flask app that calculates realized capital gains using FIFO matching. It allows users to upload CSV files containing stock transactions and extracts the transaction `date`, `quantity`, and `price` columns.

Largely vibe-coded as an experimental trial with Copilot. Code is a bit messy but results seem consistent with expectations and are easily verified.

## Features
- CSV upload
- Automatic column detection (best-effort)
- User column mapping UI
- FIFO matching for sell transactions
- Per-transaction breakdown and total realized gains

## TODO
- [ ] Deploy to Azure — See the Microsoft Azure App Service quickstart for Python (Flask):
	- https://learn.microsoft.com/en-us/azure/app-service/quickstart-python?tabs=flask%2Cwindows%2Cazure-cli%2Cazure-cli-deploy%2Cdeploy-instructions-azportal%2Cterminal-bash%2Cdeploy-instructions-zip-azcli#create-a-web-app-in-azure
	- Note: these are instructions for deploying the app using Azure App Service (Flask).
- [ ] Remove behaviour that all CSV's are stored in ./uploads/ (would be better if it were done locally but this is not feasible in Python)

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
- Product column: include a column with the stock symbol or product name (e.g. `product`, `symbol`); the app will group transactions by product and produce a FIFO matching matrix for each product.
- Total value of each transaction
- Dates are parsed with `dateutil` and should be in a recognizable format.

## License
MIT
