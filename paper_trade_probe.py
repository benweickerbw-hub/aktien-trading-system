"""One-time connectivity probe: two simulated fill events, never live orders.

Uses fictional TEST.SIM quotes (100 -> 102). This checks that GitHub Actions
can write a BUY and SELL to MotherDuck and read back the same TEST-only rows.
These rows MUST NEVER be included in investment performance statistics.
"""
import math
import duckdb

TEST_ID = "CONNECTIVITY-PROBE-2026-11-05"
SYMBOL = "TEST.SIM"
CAPITAL = 100.0
LEVERAGE = 5.0
ENTRY = 100.0
EXIT = 102.0
FEE = 1.0
UNITS = CAPITAL * LEVERAGE / ENTRY
GROSS_PNL = UNITS * (EXIT - ENTRY)
NET_PNL = GROSS_PNL - 2 * FEE

con = duckdb.connect("md:")
con.execute("""
CREATE TABLE IF NOT EXISTS paper_trade_test_ledger (
  test_id VARCHAR NOT NULL,
  event_number INTEGER NOT NULL,
  symbol VARCHAR NOT NULL,
  action VARCHAR NOT NULL,
  hypothetical_price DOUBLE NOT NULL,
  units DOUBLE NOT NULL,
  fee_eur DOUBLE NOT NULL,
  is_test BOOLEAN NOT NULL,
  recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(test_id, event_number)
)
""")
con.execute("""
CREATE TABLE IF NOT EXISTS paper_trade_test_results (
  test_id VARCHAR PRIMARY KEY,
  symbol VARCHAR NOT NULL,
  direction VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  capital_eur DOUBLE NOT NULL,
  leverage DOUBLE NOT NULL,
  entry_price DOUBLE NOT NULL,
  exit_price DOUBLE NOT NULL,
  gross_pnl_eur DOUBLE NOT NULL,
  net_pnl_eur DOUBLE NOT NULL,
  is_test BOOLEAN NOT NULL,
  method VARCHAR NOT NULL,
  recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
con.execute("""
INSERT OR REPLACE INTO paper_trade_test_ledger
(test_id,event_number,symbol,action,hypothetical_price,units,fee_eur,is_test)
VALUES (?,?,?,?,?,?,?,?)
""",[TEST_ID,1,SYMBOL,"BUY",ENTRY,UNITS,FEE,True])
con.execute("""
INSERT OR REPLACE INTO paper_trade_test_ledger
(test_id,event_number,symbol,action,hypothetical_price,units,fee_eur,is_test)
VALUES (?,?,?,?,?,?,?,?)
""",[TEST_ID,2,SYMBOL,"SELL",EXIT,UNITS,FEE,True])
con.execute("""
INSERT OR REPLACE INTO paper_trade_test_results
(test_id,symbol,direction,status,capital_eur,leverage,entry_price,
exit_price,gross_pnl_eur,net_pnl_eur,is_test,method)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
""",[TEST_ID,SYMBOL,"LONG","CLOSED",CAPITAL,LEVERAGE,ENTRY,
     EXIT,GROSS_PNL,NET_PNL,True,"SYNTHETIC_CONNECTIVITY_PROBE_NOT_A_REAL_TRADE"])
ledger=con.execute("""
SELECT event_number,action,hypothetical_price,units,fee_eur,is_test
FROM paper_trade_test_ledger WHERE test_id=?
ORDER BY event_number
""",[TEST_ID]).fetchall()
result=con.execute("""
SELECT status,capital_eur,leverage,gross_pnl_eur,net_pnl_eur,is_test
FROM paper_trade_test_results WHERE test_id=?
""",[TEST_ID]).fetchone()
assert len(ledger)==2, f"Expected 2 events, got {ledger}"
assert [r[1] for r in ledger]==["BUY","SELL"], ledger
assert all(row[5] is True for row in ledger), ledger
assert result is not None and result[0]=="CLOSED" and result[5] is True
assert math.isclose(result[4],8.0,abs_tol=1e-8), result
print(f"PASS: MotherDuck write/read test {TEST_ID}")
print(f"PASS: {len(ledger)} virtual ledger events: BUY + SELL, 100 EUR stake / 5x")
print(f"PASS: synthetic gross {result[3]:.2f} EUR, fees 2.00 EUR, net {result[4]:.2f} EUR")
print("TEST ONLY: TEST.SIM fictional quotes, excluded from any real paper-trading PnL.")
con.close()
