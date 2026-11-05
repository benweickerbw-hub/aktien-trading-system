"""Earnings overnight-only virtual market-on-close to next-open simulation.

Research baseline, NOT a live broker. No orders are placed. Requires verified
EODHD earnings timing. Create signal 15:25-15:50 America/New_York using
PREVIOUS completed EOD bars; book today's CLOSE and next session's OPEN only
after both published bars are accessible. The closes/opens are retrospective
proxy fills; not actual executable market-on-close/market-on-open transactions.
"""
import os
import sys
import uuid
import math
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from statistics import mean
from collections import defaultdict
import requests
import duckdb

NY = ZoneInfo("America/New_York")
MODEL_VERSION = "overnight_earnings_moc_moo_v0.1"
BET_EUR = 100.0
LEVERAGE = 5.0
EXPOSURE_EUR = BET_EUR * LEVERAGE
FEE_EUR = 1.0
SLIPPAGE_PCT = 0.001
MIN_TURNOVER = 2_000_000
MAX_DAILY_SIGNALS = 4
MIN_DAILY_TARGET = 2


def next_weekday(day):
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def eodhd_get(endpoint, params):
    key = os.environ.get("EODHD_API_KEY")
    if not key:
        raise RuntimeError("Missing EODHD_API_KEY")
    q = dict(params)
    q.update({"api_token": key, "fmt": "json"})
    r = requests.get(f"https://eodhd.com/api/{endpoint}", params=q, timeout=55)
    if r.status_code != 200:
        raise RuntimeError(f"EODHD HTTP {r.status_code} on {endpoint}")
    return r.json()


def earnings_for_close(day):
    """Only AMC today or BMO next session; never guessed event timestamps."""
    tomorrow = next_weekday(day)
    try:
        data = eodhd_get("calendar/earnings", {
            "from": day.isoformat(), "to": tomorrow.isoformat()
        })
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"EARNINGS_FEED_UNAVAILABLE ({type(exc).__name__}): no new trades")
        return {}
    records = data.get("earnings") if isinstance(data, dict) else None
    if not isinstance(records, list):
        print("EARNINGS_FEED_INVALID: no new trades")
        return {}
    out = {}
    for rec in records:
        if not isinstance(rec, dict) or rec.get("actual") is not None:
            continue
        symbol = rec.get("code")
        timing = rec.get("before_after_market")
        try:
            report = date.fromisoformat(str(rec.get("report_date", ""))[:10])
        except ValueError:
            continue
        if not symbol or not symbol.endswith(".US"):
            continue
        if ((timing == "AfterMarket" and report == day) or
                (timing == "BeforeMarket" and report == tomorrow)):
            out[symbol] = (report, timing, rec.get("estimate"))
    return out


def ensure_schema(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS overnight_signals (
            signal_id VARCHAR PRIMARY KEY,
            symbol VARCHAR,
            direction VARCHAR,
            signal_date DATE,
            report_date DATE,
            report_timing VARCHAR,
            information_cutoff TIMESTAMP,
            model_version VARCHAR,
            signal_score DOUBLE,
            reference_close DOUBLE,
            capital_eur DOUBLE,
            leverage DOUBLE,
            status VARCHAR,
            entry_price DOUBLE,
            entry_date DATE,
            exit_price DOUBLE,
            exit_date DATE,
            realized_pnl_eur DOUBLE,
            gross_pnl_eur DOUBLE,
            fees_eur DOUBLE,
            exit_reason VARCHAR,
            checked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS overnight_runs (
            run_id VARCHAR PRIMARY KEY,
            run_at TIMESTAMP,
            mode VARCHAR,
            market_date DATE,
            inspected INTEGER,
            eligible INTEGER,
            new_signals INTEGER,
            finalized INTEGER,
            status VARCHAR,
            message VARCHAR
        )
    """)


def record_run(con, mode, market_day, inspected, eligible, signals, closed, status, note):
    con.execute("""
      INSERT INTO overnight_runs
        (run_id,run_at,mode,market_date,inspected,eligible,
         new_signals,finalized,status,message)
      VALUES (?,CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?)
    """, [str(uuid.uuid4()), mode, market_day, inspected, eligible,
          signals, closed, status, note])


def prepare(con, now):
    day = now.date()
    if day.weekday() > 4:
        print("SKIP: US market weekend")
        return
    if not ((now.hour == 15 and 25 <= now.minute <= 50)):
        print(f"NO SIGNALS: this is not a timely US pre-close run ({now.isoformat()})")
        return
    event_map = earnings_for_close(day)
    if not event_map:
        record_run(con, "prepare", day, 0, 0, 0, 0, "NO_TRADE",
                   "No verified AMC/BMO earnings feed or eligible event")
        print("NO TRADE: No confirmed AMC/BMO earnings candidates")
        return
    holdings = con.execute("""
      SELECT DISTINCT symbol FROM overnight_signals
      WHERE status IN ('SIGNALLED','ENTRY_BOOKED')
    """).fetchall()
    held = {item[0] for item in holdings}
    needed = [x for x in event_map if x not in held]
    data = con.execute("""
        SELECT symbol,trade_date,close,volume,high,low
        FROM stock_prices WHERE symbol LIKE '%.US' AND trade_date < ?
        ORDER BY symbol,trade_date
    """, [day]).fetchall()
    bars_by_symbol = defaultdict(list)
    for symbol, trade_date, close, vol, high, low in data:
        if None in (close,high,low) or float(close)<=0:
            continue
        bars_by_symbol[symbol].append((trade_date,float(close),int(vol or 0),
                                       float(high),float(low)))
    candidates = []
    for symbol in needed:
        bars = bars_by_symbol.get(symbol, [])
        if len(bars)<60 or (day-bars[-1][0]).days>4:
            continue
        closes = [r[1] for r in bars]
        turn = mean(r[1]*r[2] for r in bars[-20:])
        if turn < MIN_TURNOVER or closes[-1]<2:
            continue
        m20, m50 = mean(closes[-20:]),mean(closes[-50:])
        mom5 = closes[-1]/closes[-6]-1
        mom20 = closes[-1]/closes[-21]-1
        # This ranks *uncalibrated* event candidates. No invented probabilities.
        trend = mom5 + mom20 + closes[-1]/m20 - 1
        side = "LONG" if trend>=0 else "SHORT"
        score = abs(trend)*5 + abs(mom5) + abs(mom20)
        report_day, timing, estimate = event_map[symbol]
        already = con.execute("""
          SELECT COUNT(*) FROM overnight_signals
          WHERE symbol=? AND signal_date=?
        """, [symbol,day]).fetchone()[0]
        if already:
            continue
        candidates.append((score,symbol,side,report_day,timing,closes[-1]))
    candidates.sort(key=lambda x:(-x[0],x[1]))
    n = 0
    side_count = {"LONG":0,"SHORT":0}
    for score,symbol,side,report_day,timing,reference in candidates:
        if n>=MAX_DAILY_SIGNALS:
            break
        if side_count[side]>=2:
            continue
        con.execute("""
            INSERT INTO overnight_signals
              (signal_id,symbol,direction,signal_date,report_date,
               report_timing,information_cutoff,model_version,signal_score,
               reference_close,capital_eur,leverage,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, [str(uuid.uuid4()),symbol,side,day,report_day,timing,
              now.astimezone(timezone.utc).replace(tzinfo=None),
              MODEL_VERSION,score,reference,BET_EUR,LEVERAGE,"SIGNALLED"])
        n += 1
        side_count[side]+=1
        print(f"PRE-CLOSE SIGNAL {side} {symbol}, earnings {report_day} "
              f"{timing}; no entry price until postclose EOD verified.")
    if n < MIN_DAILY_TARGET:
        print(f"ONLY {n}/{MIN_DAILY_TARGET} candidate signals: "
              "do not substitute ordinary momentum trades.")
    record_run(con,"prepare",day,len(bars_by_symbol),len(candidates),n,0,
               "OK" if n else "NO_TRADE",
               "Uncalibrated event-only signals; EOD proxy fills pending")


def get_eod_bars(symbol, start, end):
    try:
        data = eodhd_get(f"eod/{symbol}",{
            "from": start.isoformat(), "to": end.isoformat()
        })
    except (requests.RequestException,RuntimeError,ValueError) as exc:
        print(f"{symbol}: EOD not available ({type(exc).__name__})")
        return {}
    if not isinstance(data,list):
        return {}
    result={}
    for d in data:
        try:
            k = date.fromisoformat(str(d["date"])[:10])
            o,c=float(d["open"]),float(d["close"])
            if not math.isfinite(o) or not math.isfinite(c) or min(o,c)<=0:
                continue
            result[k]={"open":o,"close":c}
        except (KeyError,ValueError,TypeError):
            continue
    return result


def settle(con, now):
    # This only RECONCILES the previous MOC/MOO simulation once published;
    # it does not trade retroactively with knowledge of the earnings result.
    today = now.date()
    pending = con.execute("""
      SELECT signal_id,symbol,direction,signal_date,status,entry_price,entry_date
      FROM overnight_signals
      WHERE status IN ('SIGNALLED','ENTRY_BOOKED')
      ORDER BY signal_date,signal_id
    """).fetchall()
    completed=0
    for (signal_id,symbol,side,signal_date,status,entry,entry_day) in pending:
        if (today-signal_date).days > 10:
            con.execute("""
              UPDATE overnight_signals SET status='EXPIRED',
              exit_reason='UNRESOLVED_PRICE_FEED',checked_at=CURRENT_TIMESTAMP
              WHERE signal_id=?""",[signal_id])
            continue
        records=get_eod_bars(symbol,signal_date,today)
        candle=records.get(signal_date)
        if status=="SIGNALLED":
            if candle is None:
                print(f"{symbol}: waiting for verified official entry CLOSE")
                continue
            entry = candle["close"]
            entry_day = signal_date
            con.execute("""
              UPDATE overnight_signals SET entry_date=?,entry_price=?,
              status='ENTRY_BOOKED',checked_at=CURRENT_TIMESTAMP
              WHERE signal_id=?
            """,[entry_day,entry,signal_id])
            print(f"{symbol}: booked simulated entry at {entry:.4f} EOD CLOSE")
        next_sessions=sorted(d for d in records if d>entry_day)
        if not next_sessions:
            print(f"{symbol}: next trading session OPEN not published yet")
            continue
        exit_day=next_sessions[0]
        raw_exit=records[exit_day]["open"]
        # The simulation cannot sell at observed next-day open in realtime
        # on EOD data. This result is booked retrospectively on publication.
        # Proxy slippage and fees are illustrative, not real certificate quotes.
        if side=="LONG":
            entry_execution=entry*(1+SLIPPAGE_PCT)
            exit_execution=raw_exit*(1-SLIPPAGE_PCT)
            gross=EXPOSURE_EUR*(exit_execution/entry_execution-1)
        else:
            entry_execution=entry*(1-SLIPPAGE_PCT)
            exit_execution=raw_exit*(1+SLIPPAGE_PCT)
            gross=EXPOSURE_EUR*(1-exit_execution/entry_execution)
        fees=2*FEE_EUR
        net=max(-BET_EUR-fees,gross-fees)
        con.execute("""
          UPDATE overnight_signals SET status='CLOSED',exit_date=?,
          exit_price=?,gross_pnl_eur=?,fees_eur=?,realized_pnl_eur=?,
          exit_reason='NEXT_REGULAR_OPEN_EOD_PROXY',
          checked_at=CURRENT_TIMESTAMP WHERE signal_id=?
        """,[exit_day,raw_exit,gross,fees,net,signal_id])
        completed+=1
        print(f"CLOSED simulated {side} {symbol}: EUR {net:+.2f}, "
              f"entry CLOSE {entry_day}, exit OPEN {exit_day} "
              "[EOD retrospective proxy]")
    record_run(con,"settle",today,len(pending),len(pending),0,completed,
               "OK", "Book EOD proxy fills once dates are available")


def main():
    mode=sys.argv[1] if len(sys.argv)>1 else "status"
    now=datetime.now(NY)
    con=duckdb.connect("md:")
    ensure_schema(con)
    if mode=="prepare":
        prepare(con,now)
    elif mode=="settle":
        settle(con,now)
    elif mode=="status":
        items=con.execute("""
          SELECT status,COUNT(*) FROM overnight_signals GROUP BY status
        """).fetchall()
        print(f"{now.isoformat()} OVERNIGHT_STATUS: {items}")
    else:
        raise ValueError("Expected prepare, settle or status")
    con.close()


if __name__=="__main__":
    main()
