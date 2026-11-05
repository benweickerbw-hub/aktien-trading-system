
import os
import requests
import duckdb

# API-Zugang aus GitHub Secrets
api_key = os.environ["EODHD_API_KEY"]

# Verbindung zu MotherDuck
con = duckdb.connect("md:")

# Tabelle erstellen
con.execute("""
CREATE TABLE IF NOT EXISTS stock_prices (
    symbol VARCHAR,
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    adjusted_close DOUBLE,
    volume BIGINT,
    PRIMARY KEY (symbol, trade_date)
)
""")

# Zuerst nur Apple als Verbindungstest
symbol = "AAPL.US"

response = requests.get(
    f"https://eodhd.com/api/eod/{symbol}",
    params={
        "api_token": api_key,
        "fmt": "json",
        "from": "2026-01-01"
    },
    timeout=30
)
response.raise_for_status()

data = response.json()

if not isinstance(data, list) or not data:
    raise RuntimeError("Keine Kursdaten erhalten")

rows = [
    (
        symbol,
        item["date"],
        item["open"],
        item["high"],
        item["low"],
        item["close"],
        item["adjusted_close"],
        item["volume"]
    )
    for item in data
]

con.executemany("""
INSERT OR REPLACE INTO stock_prices
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", rows)

print(f"Erfolgreich: {len(rows)} Kurstage importiert")
con.close()
