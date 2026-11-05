
import os
import csv
import random
import tempfile
import requests
import duckdb

API_KEY = os.environ["EODHD_API_KEY"]
TARGET = 500

# Verteilung auf internationale Aktienmärkte
EXCHANGES = {
    "US": 250,       # USA
    "XETRA": 100,    # Deutschland
    "PA": 75,        # Frankreich
    "LSE": 50,       # Großbritannien
    "AS": 25         # Niederlande
}

session = requests.Session()

def api_get(endpoint, params=None):
    params = dict(params or {})
    params["api_token"] = API_KEY
    params["fmt"] = "json"

    response = session.get(
        f"https://eodhd.com/api/{endpoint}",
        params=params,
        timeout=45
    )
    response.raise_for_status()
    return response.json()

def get_symbols(exchange, amount):
    selected = []

    # Bevorzugt große Unternehmen mit Handelsvolumen
    try:
        import json

        for offset in range(0, amount, 100):
            data = api_get(
                "screener",
                {
                    "filters": json.dumps([
                        ["exchange", "=", exchange.lower()],
                        ["market_capitalization", ">", 2000000000],
                        ["avgvol_200d", ">", 100000]
                    ]),
                    "sort": "market_capitalization.desc",
                    "limit": min(100, amount - offset),
                    "offset": offset
                }
            )

            records = data.get("data", [])
            if not records:
                break

            for item in records:
                code = item.get("code")
                if code:
                    selected.append(f"{code}.{exchange}")

        if selected:
            print(f"{exchange}: Screener verfügbar")

    except (requests.RequestException, ValueError, TypeError):
        print(f"{exchange}: Screener nicht verfügbar")

    # Fehlende Plätze aus der offiziellen Aktienliste
    if len(selected) < amount:
        try:
            listing = api_get(
                f"exchange-symbol-list/{exchange}",
                {"type": "common_stock"}
            )

            candidates = []

            for item in listing:
                code = item.get("Code")
                if not code:
                    continue

                # OTC-Aktien in der US-Auswahl vermeiden
                if exchange == "US":
                    venue = item.get("Exchange", "")
                    if venue not in ("NASDAQ", "NYSE", "NYSE MKT"):
                        continue

                symbol = f"{code}.{exchange}"

                if symbol not in selected:
                    candidates.append(symbol)

            # Reproduzierbare Stichprobe
            random.Random(42).shuffle(candidates)

            selected.extend(
                candidates[:amount - len(selected)]
            )

        except (requests.RequestException, ValueError, TypeError):
            print(f"{exchange}: Börsenliste nicht verfügbar")

    return selected[:amount]


# 500 Aktien auswählen
symbols = []

for exchange, amount in EXCHANGES.items():
    exchange_symbols = get_symbols(exchange, amount)
    symbols.extend(exchange_symbols)

    print(
        f"{exchange}: "
        f"{len(exchange_symbols)} Aktien ausgewählt"
    )

symbols = list(dict.fromkeys(symbols))

print(f"Gesamt: {len(symbols)} verschiedene Aktien")

if not symbols:
    raise RuntimeError("Keine Aktien gefunden")


# Verbindung zu MotherDuck
con = duckdb.connect("md:")

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


# Alle Kursdaten zunächst gesammelt in CSV schreiben
columns = [
    "symbol", "trade_date", "open", "high",
    "low", "close", "adjusted_close", "volume"
]

file = tempfile.NamedTemporaryFile(
    mode="w",
    suffix=".csv",
    newline="",
    delete=False
)

csv_path = file.name
writer = csv.writer(file)
writer.writerow(columns)

successful = 0
failed = 0
total_rows = 0

for i, symbol in enumerate(symbols, 1):
    try:
        data = api_get(
            f"eod/{symbol}",
            {"from": "2026-01-01"}
        )

        if not isinstance(data, list) or not data:
            failed += 1
            continue

        for item in data:
            writer.writerow([
                symbol,
                item.get("date"),
                item.get("open"),
                item.get("high"),
                item.get("low"),
                item.get("close"),
                item.get("adjusted_close"),
                item.get("volume")
            ])
            total_rows += 1

        successful += 1

    except requests.HTTPError as exc:
        failed += 1
        status = exc.response.status_code

        print(f"{symbol}: HTTP {status}")

        # Bei Tarif- oder API-Limit stoppen
        if status in (401, 402, 403, 429):
            print("API-Zugriff oder Kontingent begrenzt")
            break

    except (requests.RequestException, ValueError) as exc:
        failed += 1
        print(f"{symbol}: Abruf fehlgeschlagen")

    if i % 25 == 0:
        print(f"Fortschritt: {i}/{len(symbols)}")

file.close()


# Kursdaten effizient gesammelt importieren
if total_rows > 0:
    con.execute("""
        INSERT OR REPLACE INTO stock_prices
        SELECT
            symbol,
            TRY_CAST(trade_date AS DATE),
            TRY_CAST("open" AS DOUBLE),
            TRY_CAST(high AS DOUBLE),
            TRY_CAST(low AS DOUBLE),
            TRY_CAST("close" AS DOUBLE),
            TRY_CAST(adjusted_close AS DOUBLE),
            TRY_CAST(volume AS BIGINT)
        FROM read_csv_auto(
            ?,
            header=true,
            all_varchar=true
        )
        WHERE TRY_CAST(trade_date AS DATE) IS NOT NULL
    """, [csv_path])

os.remove(csv_path)

count = con.execute("""
    SELECT COUNT(DISTINCT symbol)
    FROM stock_prices
""").fetchone()[0]

print("--------------------------------")
print(f"Erfolgreiche Aktien: {successful}")
print(f"Fehlgeschlagene Abrufe: {failed}")
print(f"Neue Kursdatensätze verarbeitet: {total_rows}")
print(f"Aktien insgesamt in MotherDuck: {count}")
print("--------------------------------")

con.close()
