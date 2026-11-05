# Aktien-Research: stündliches Deep-Dive Research & virtuelles Trading

## Zielbild
Die aktive Aufgabe **„Aktienresearch & Paper Trading“** untersucht stündlich globale Aktien auf verifizierbare fundamentale Ereignisse und analysiert mögliche LONG- und SHORT-Trades mit echten Quellen. Quartalszahlen und Gewinnwarnungen haben hohe Priorität, aber relevante andere Ereignisse sind ebenfalls erlaubt (Guidance, Produkteinführungen, Großaufträge, M&A, Regulierung, Gerichtsentscheidungen, Finanzierungsrisiken, wichtige Investitionsvorhaben). **Keine realen Wertpapierorders.**

## Quellenstandard
Für einen ernsthaft handelsfähigen Kandidaten soll ein belegtes, versioniertes Dossier aus mindestens **50 unterschiedlichen, inhaltlich gelesenen Publikationen** entstehen. Je Quelle: Original-URL, Publisher, Publikationsdatum, Prüfzeit, neue Erkenntnis, Bull/Bear-Relevanz, Zuverlässigkeit und bekannte Interessenkonflikte.

- Nicht nur 50 Suchtreffer, Schlagzeilen, Videosnippets oder Syndikationskopien zählen.
- Pro Quelle ursprüngliches Dokument lesen, wenn verfügbar; identische Agenturtexte zählen nicht mehrfach.
- Zugängliche Analysten- und Bankreports samt unterschiedlichen Schätzungen auswerten; kostenpflichtige Berichte nicht als gelesen ausgeben.
- Finanzberichte und -historie, Cashflow, Schulden, Produktpipeline, Guidance, Führung, Bilanzqualität, Bewertung, Wettbewerb, Marktstruktur, operative KPIs, Rohstoff-/Zinssensitivität, Regulierung, Sentiment, Positionierung und Gegenargumente.
- Dokumentieren: tatsächliche Quellenanzahl / 50, Zahl verschiedener Herausgeber, Qualitätsniveau und noch offene Lücken.
- Stündlich breit vorsortieren, dann 1–3 Titel intensiver weiterbearbeiten; Dossiers über mehrere Stunden vervollständigen. Keine vorgebliche 50-Quellen-Fertigstellung bei weniger Daten.
- Für Kandidaten mit einer tieferen Analyse: beste Bull- und Bear-These, zentrale Annahmen, Falsifikationskriterien, erwarteter Kurskatalysator, Zeit bis Veröffentlichung, Konsens- bzw. Erwartungslücke, realistische negative Szenarien.
- Jede Empfehlung als KANDIDAT, SIGNAL, PAPIERPOSITION oder GESCHLOSSEN eindeutig kennzeichnen; nur tatsächlich gespeicherte virtuelle Orders gelten als gebucht.
- Bei zu geringer Quellenqualität oder unklaren Erwartungen kann ausdrücklich **KEIN TRADE** das richtige Resultat sein.

## Research-Historie
Stündlicher Bericht durch ChatGPT-Automation (`Automation_97c046ea531c8191814c5f0ca7138390`). Forschung soll unter `research_dossiers/` mit getrennten Dokumenten pro Symbol nachvollziehbar fortgeschrieben werden. In jedem Durchlauf Informationen, konkrete Links, Quellenstände, Veränderungen des Rankings und tatsächliche Fortschritte seit dem letzten Research-Snapshot erfassen. Wenn Speichern nicht möglich ist, offen melden.

## Infrastruktur und Grenzziehung
- `sync.py`: EODHD OHLCV-Import in MotherDuck, aktuell begrenztes Universum. Breites Research-Universum ist **nicht** gleich der Menge gespeicherter Kursticker.
- `overnight.py` und `.github/workflows/overnight.yml`: experimenteller, earningsbezogener **synthetischer** Overnight-Simulator. Nur im Earnings-Zeitfenster aktiv, noch NICHT mit der vollständigen ChatGPT-Newsanalyse verbunden. Es ist derzeit nicht der allgemeine eventgesteuerte autonome Agent.
- `paper_trading.py`: historisches mehrtägiges Regelmodell, aus dem Scheduler entfernt. Nicht als aktiven autonomen Research-Trader bezeichnen.
- `paper_trade_probe.py` und `.github/workflows/paper-trade-probe.yml`: reiner **TEST** für MotherDuck-Read/Write anhand fiktiver TEST.SIM-Kurse (100→102) und 100 EUR/5×; schreibt in `paper_trade_test_ledger` und `paper_trade_test_results`. Diese Tabellen dürfen **niemals** in die Rendite echter virtueller Aktien-Trades eingerechnet werden.
- `my_db.main.stock_prices`: Tagesdaten, keine tatsächlichen Intraday-Einstiege, keine Knock-out- oder Optionsmarktpreise.
- Forschungs-Signale werden noch NICHT vollautomatisch von ChatGPT auf GitHub-Trades umgesetzt; bis diese Pipeline implementiert und getestet ist, bei jedem Statusbericht hervorheben.

## Statusfrage aus ChatGPT
Bei „Was ist interessant? Welche Trades?“ auf die neuesten Research-Dossiers und vorhandenen autonomen Aufgabenläufe zugreifen, dazu MotherDuck live abfragen. Unterscheide strikt:
1. Neue Nachrichten mit Quellen und Uhrzeiten.
2. Deep-Dive-Kandidaten mit Quellenanzahl / 50 und konkreten Bull/Bear-Widersprüchen.
3. Paper-Signale/Positionen mit tatsächlichem Zustand und Preisen.
4. Testinstrumente TEST.SIM als **Techniktest**, niemals als reale Marktprognose.
5. Performance, Fehleranalyse und begrenzte Abdeckung offen ausweisen.

Keine Finanzkennzahlen, Veröffentlichungsdaten, Trades, Quellen oder Erfolgsraten erfinden. Keine realen Orderausführungen.
