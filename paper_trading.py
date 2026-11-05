"""Earnings-only PAPER TRADING research experiment (synthetic 5x EOD).

IMPORTANT: This is not a live broker, actual derivative quote, or calibrated
probability model. Signals use completed daily bars, and fills are only booked
after a later bar is available (next bar's open). Conservative stop priority if
both stop and target occur within a daily candle.
"""
from __future__ import annotations
import os
import math
import uuid
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
import duckdb
import requests

CAPITAL_EUR = 100.0
LEVERAGE = 5.0
EXPOSURE_EUR = CAPITAL_EUR * LEVERAGE
FEE_PER_SIDE_EUR = 1.0
SLIPPAGE_PCT = 0.001
MIN_DAILY_EARNINGS_TRADES_GOAL = 2  # goal, never substitute non-earnings
MAX_NEW_SIGNALS_PER_DAY = 4
MAX_OPEN_POSITIONS = 24
MAX_HOLDING_BARS = 5
MIN_DAILY_TURNOVER_LOCAL = 2_000_000
VERSION = "earnings_only_eod_0.2"


def sql_date(d):
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def upcoming_earnings(latest_market_date, symbols):
    """Use only future scheduled earnings; no regular momentum-only trading.

    Official EODHD earnings calendar is paid and may be absent on EOD-only plans.
    A missing/denied calendar always results in ZERO new trades, not invented dates.
    """
    api_key = os.environ.get("EODHD_API_KEY")
    if not api_key:
        print("EARNINGS_CALENDAR_UNAVAILABLE: EODHD_API_KEY not configured")
        return {}
    earliest_entry = max(latest_market_date + timedelta(days=1),
                         date.today() + timedelta(days=1))
    end = earliest_entry + timedelta(days=14)
    try:
        response = requests.get(
            "https://eodhd.com/api/calendar/earnings",
            params={"api_token": api_key, "fmt": "json",
                    "from": earliest_entry.isoformat(), "to": end.isoformat()},
            timeout=60,
        )
        if response.status_code != 200:
            print(f"EARNINGS_CALENDAR_UNAVAILABLE: HTTP {response.status_code}. "
                  "Check EODHD Corporate Events/Fundamentals subscription. "
                  "No earnings trades will be opened.")
            return {}
        payload = response.json()
        records = payload.get("earnings", []) if isinstance(payload, dict) else []
        if not isinstance(records, list):
            print("EARNINGS_CALENDAR_UNAVAILABLE: unexpected response schema")
            return {}
    except (requests.RequestException, ValueError) as exc:
        print(f"EARNINGS_CALENDAR_UNAVAILABLE: {type(exc).__name__}; no new signals")
        return {}

    valid = {}
    for event in records:
        if not isinstance(event, dict):
            continue
        symbol = event.get("code")
        timing = event.get("before_after_market")
        reported = event.get("report_date")
        if symbol not in symbols or timing not in ("BeforeMarket", "AfterMarket"):
            continue
        if event.get("actual") is not None:
            continue  # already reported; no pre-earnings signal
        try:
            event_date = date.fromisoformat(str(reported)[:10])
        except ValueError:
            continue
        # For BeforeMarket earnings, enter no later than previous session.
        if ((timing == "BeforeMarket" and event_date <= earliest_entry) or
                (timing == "AfterMarket" and event_date < earliest_entry)):
            continue
        if symbol not in valid or event_date < valid[symbol][0]:
            valid[symbol] = (event_date, timing)
    print(f"Earnings calendar: {len(valid)} eligible scheduled events "
          f"among {len(symbols)} stored symbols; earliest paper entry "
          f"{earliest_entry}")
    return valid


def run():
    con = duckdb.connect("md:")
    con.execute("""
    CREATE TABLE IF NOT EXISTS paper_orders (
        order_id VARCHAR PRIMARY KEY,
        symbol VARCHAR, direction VARCHAR, signal_date DATE,
        score DOUBLE, risk_fraction DOUBLE, target_fraction DOUBLE,
        status VARCHAR, model_version VARCHAR
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades (
        trade_id VARCHAR PRIMARY KEY,
        symbol VARCHAR, direction VARCHAR, signal_date DATE,
        entry_date DATE, entry_price DOUBLE,
        stop_price DOUBLE, target_price DOUBLE,
        exposure_eur DOUBLE, capital_eur DOUBLE,
        entry_fee_eur DOUBLE,
        exit_date DATE, exit_price DOUBLE, exit_fee_eur DOUBLE,
        realized_pnl_eur DOUBLE,
        status VARCHAR, exit_reason VARCHAR, last_checked_date DATE,
        score DOUBLE, model_version VARCHAR
    )
    """)
    # Add event provenance to orders and positions, including older databases.
    for table, column, typ in [
        ("paper_orders", "earnings_date", "DATE"),
        ("paper_orders", "event_timing", "VARCHAR"),
        ("paper_orders", "earliest_entry_date", "DATE"),
        ("paper_trades", "earnings_date", "DATE"),
        ("paper_trades", "event_timing", "VARCHAR"),
    ]:
        con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {typ}")
    con.execute("""
    CREATE TABLE IF NOT EXISTS paper_runs (
        run_id VARCHAR PRIMARY KEY, last_market_date DATE,
        inspected_symbols INTEGER, candidates INTEGER,
        new_signals INTEGER, open_positions INTEGER,
        completed_positions INTEGER, model_version VARCHAR,
        run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    raw = con.execute("""
        SELECT symbol, trade_date, "open", high, low, close, volume
        FROM stock_prices
        WHERE trade_date >= CURRENT_DATE - INTERVAL '400 DAYS'
          AND close > 0 AND "open" > 0
        ORDER BY symbol, trade_date
    """).fetchall()
    history = defaultdict(list)
    for symbol, day, o, h, l, c, volume in raw:
        if None in (o, h, l, c):
            continue
        if min(float(o), float(h), float(l), float(c)) <= 0:
            continue
        history[symbol].append({
            "day": day, "open": float(o), "high": float(h),
            "low": float(l), "close": float(c),
            "volume": int(volume or 0),
        })
    if not history:
        raise RuntimeError("Keine verwendbaren stock_prices-Kursdaten gefunden")
    latest_market_date = max(bars[-1]["day"] for bars in history.values())
    print(f"Latest EOD date: {latest_market_date}; symbols: {len(history)}")

    # 1. Execute OLD pending signals at the NEXT AVAILABLE daily open.
    pending = con.execute("""
       SELECT order_id, symbol, direction, signal_date, score,
              risk_fraction, target_fraction, earnings_date,
              event_timing, earliest_entry_date
       FROM paper_orders WHERE status = 'PENDING'
       ORDER BY signal_date, order_id
    """).fetchall()
    for (order_id, symbol, side, signal_date, score, risk_pct,
         reward_pct, earnings_date, event_timing, earliest_entry_date) in pending:
        if earnings_date is None or earliest_entry_date is None:
            con.execute("UPDATE paper_orders SET status='EXPIRED' WHERE order_id=?", [order_id])
            continue
        later = [bar for bar in history.get(symbol, [])
                 if bar["day"] >= earliest_entry_date and bar["day"] > signal_date]
        if not later:
            continue
        first = later[0]
        if ((event_timing == "BeforeMarket" and first["day"] >= earnings_date) or
                (event_timing == "AfterMarket" and first["day"] > earnings_date)):
            con.execute("UPDATE paper_orders SET status='EXPIRED' WHERE order_id=?", [order_id])
            print(f"EXPIRED {symbol}: earnings occurred before eligible entry")
            continue
        if (first["day"] - signal_date).days > 15:
            con.execute("UPDATE paper_orders SET status='EXPIRED' WHERE order_id=?", [order_id])
            continue
        # For a long, worse execution = higher buy; short sell = lower sale.
        entry = first["open"] * (1 + SLIPPAGE_PCT if side == "LONG" else 1 - SLIPPAGE_PCT)
        stop = entry * (1 - risk_pct if side == "LONG" else 1 + risk_pct)
        target = entry * (1 + reward_pct if side == "LONG" else 1 - reward_pct)
        trade_id = str(uuid.uuid4())
        con.execute("""
           INSERT INTO paper_trades VALUES (
             ?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,'OPEN',NULL,NULL,?,?
           )
        """, [
            trade_id, symbol, side, signal_date, first["day"], entry,
            stop, target, EXPOSURE_EUR, CAPITAL_EUR, FEE_PER_SIDE_EUR,
            score, VERSION
        ])
        con.execute("UPDATE paper_trades SET earnings_date=?, event_timing=? "
                    "WHERE trade_id=?", [earnings_date, event_timing, trade_id])
        con.execute("UPDATE paper_orders SET status='FILLED' WHERE order_id=?", [order_id])
        print(f"FILLED {side} {symbol} on {first['day']}: {entry:.4f}")

    # 2. Update all open trades with NEW candles only.
    active = con.execute("""
      SELECT trade_id, symbol, direction, entry_date, entry_price,
             stop_price, target_price, last_checked_date
      FROM paper_trades WHERE status='OPEN'
    """).fetchall()
    closed_now = 0
    for trade_id, symbol, side, entry_date, entry, stop, target, checked in active:
        candles = [b for b in history.get(symbol, [])
                   if b["day"] >= entry_date and
                      (checked is None or b["day"] > checked)]
        if not candles:
            continue
        entire = history[symbol]
        entry_idx = next((i for i,b in enumerate(entire) if b["day"] == entry_date), None)
        for bar in candles:
            idx = next(i for i,b in enumerate(entire) if b["day"] == bar["day"])
            days_held = idx - entry_idx + 1
            outcome = None
            raw_exit = None
            if side == "LONG":
                if bar["open"] <= stop:
                    outcome, raw_exit = "STOP_GAP", bar["open"]
                elif bar["open"] >= target:
                    outcome, raw_exit = "TARGET_GAP", bar["open"]
                elif bar["low"] <= stop:
                    outcome, raw_exit = "STOP", stop
                elif bar["high"] >= target:
                    outcome, raw_exit = "TARGET", target
            else:
                if bar["open"] >= stop:
                    outcome, raw_exit = "STOP_GAP", bar["open"]
                elif bar["open"] <= target:
                    outcome, raw_exit = "TARGET_GAP", bar["open"]
                elif bar["high"] >= stop:
                    outcome, raw_exit = "STOP", stop
                elif bar["low"] <= target:
                    outcome, raw_exit = "TARGET", target
            # Intrabar stop takes precedence over target, conservatively.
            if outcome is None and days_held >= MAX_HOLDING_BARS:
                outcome, raw_exit = "TIME", bar["close"]
            if outcome:
                exit_price = raw_exit * (1 - SLIPPAGE_PCT if side == "LONG" else 1 + SLIPPAGE_PCT)
                gross = EXPOSURE_EUR * (
                    (exit_price - entry) / entry if side == "LONG"
                    else (entry - exit_price) / entry
                )
                # A synthetic limited-loss product approximation, fees separate.
                pnl = max(-CAPITAL_EUR - FEE_PER_SIDE_EUR, gross - 2 * FEE_PER_SIDE_EUR)
                con.execute("""
                   UPDATE paper_trades
                   SET status='CLOSED', exit_date=?, exit_price=?,
                       exit_fee_eur=?, realized_pnl_eur=?,
                       exit_reason=?, last_checked_date=?
                   WHERE trade_id=?
                """, [bar["day"], exit_price, FEE_PER_SIDE_EUR,
                      pnl, outcome, bar["day"], trade_id])
                closed_now += 1
                print(f"CLOSED {side} {symbol}: {pnl:.2f} EUR, {outcome}")
                break
            con.execute(
                "UPDATE paper_trades SET last_checked_date=? WHERE trade_id=?",
                [bar["day"], trade_id]
            )

    # 3. NEW signals are strictly gated by upcoming earnings dates. NEVER
    #    create a regular momentum trade as a fallback.
    earnings = upcoming_earnings(latest_market_date, set(history))
    earliest_entry = max(latest_market_date + timedelta(days=1),
                         date.today() + timedelta(days=1))
    open_symbols = set(x[0] for x in con.execute(
        "SELECT symbol FROM paper_trades WHERE status='OPEN'"
    ).fetchall())
    pending_symbols = set(x[0] for x in con.execute(
        "SELECT symbol FROM paper_orders WHERE status='PENDING'"
    ).fetchall())
    existing_signal_symbols = set(x[0] for x in con.execute(
        "SELECT symbol FROM paper_orders WHERE signal_date=?", [latest_market_date]
    ).fetchall())
    slots = min(MAX_NEW_SIGNALS_PER_DAY,
                max(0, MAX_OPEN_POSITIONS - len(open_symbols) - len(pending_symbols)))
    candidates = []

    for symbol, bars in history.items():
        if len(bars) < 60 or bars[-1]["day"] != latest_market_date:
            continue
        if symbol not in earnings:
            continue
        if symbol in open_symbols or symbol in pending_symbols or symbol in existing_signal_symbols:
            continue
        closes = [b["close"] for b in bars]
        turnover = mean(b["close"] * b["volume"] for b in bars[-20:])
        if turnover < MIN_DAILY_TURNOVER_LOCAL or closes[-1] < 2:
            continue
        ma20, ma50 = mean(closes[-20:]), mean(closes[-50:])
        mom5 = closes[-1] / closes[-6] - 1
        mom20 = closes[-1] / closes[-21] - 1
        trs = [
            max(bars[i]["high"] - bars[i]["low"],
                abs(bars[i]["high"] - bars[i-1]["close"]),
                abs(bars[i]["low"] - bars[i-1]["close"]))
            for i in range(len(bars)-14, len(bars))
        ]
        atr_pct = mean(trs) / closes[-1]
        if atr_pct <= 0 or atr_pct > 0.15:
            continue
        # Exploratory pre-earnings direction: transparent momentum/trend heuristic.
        # NOT a reliable earnings-surprise model or calibrated probability.
        direction = "LONG" if mom5 + mom20 + (closes[-1] / ma20 - 1) >= 0 else "SHORT"
        event_date, event_timing = earnings[symbol]
        days_to_event = (event_date - earliest_entry).days
        score = (abs(mom5) / max(atr_pct, 0.005) + abs(mom20) * 5
                 + 2.0 / (1.0 + days_to_event))
        risk_pct = min(0.06, max(0.015, atr_pct * 1.5))
        reward_pct = risk_pct * 2.0
        candidates.append((score, symbol, direction, risk_pct, reward_pct,
                           event_date, event_timing))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    new_count = 0
    sides = {"LONG": 0, "SHORT": 0}
    for score, symbol, side, risk_pct, reward_pct, event_date, event_timing in candidates:
        if new_count >= slots:
            break
        if sides[side] >= 2:
            continue  # limit direction concentration on each day
        con.execute("""
            INSERT INTO paper_orders (
                order_id,symbol,direction,signal_date,score,
                risk_fraction,target_fraction,status,model_version,
                earnings_date,event_timing,earliest_entry_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, [str(uuid.uuid4()), symbol, side, latest_market_date,
              score, risk_pct, reward_pct, 'PENDING', VERSION,
              event_date, event_timing, earliest_entry])
        sides[side] += 1
        new_count += 1
        print(f"EARNINGS SIGNAL {side} {symbol}, EPS report {event_date} "
              f"({event_timing}), heuristic_score={score:.2f}, "
              f"stop={risk_pct:.1%}, target={reward_pct:.1%}")

    if new_count < MIN_DAILY_EARNINGS_TRADES_GOAL:
        print(f"EARNINGS_ONLY: {new_count} new signals, below target "
              f"{MIN_DAILY_EARNINGS_TRADES_GOAL}; no unrelated trades substituted.")

    current_open = con.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'"
    ).fetchone()[0]
    completed = con.execute(
        "SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'"
    ).fetchone()[0]
    con.execute("""
        INSERT INTO paper_runs
          (run_id,last_market_date,inspected_symbols,candidates,
           new_signals,open_positions,completed_positions,model_version)
        VALUES (?,?,?,?,?,?,?,?)
    """, [str(uuid.uuid4()), latest_market_date, len(history), len(candidates),
          new_count, current_open, completed, VERSION])
    print(f"SUMMARY: {len(history)} symbols, {len(candidates)} candidates, "
          f"{new_count} NEW pending signals, {current_open} open, "
          f"{completed} closed, {closed_now} closed today.")
    con.close()


if __name__ == "__main__":
    run()
