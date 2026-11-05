# Earnings Research Desk – Systemregeln

Dieses Repository verwaltet technische Dateneinspielung und **ausschließlich virtuelles Earnings-Paper-Trading**. Die entscheidende Research-Arbeit soll öffentlich verfügbare Finanzinformationen, Nachrichten und Marktreaktionen auswerten. EODHD und MotherDuck sind Hilfswerkzeuge, nicht die alleinige Entscheidungsgrundlage.

## Webresearch (wiederkehrend)
Es existiert eine ChatGPT-Scheduled-Aufgabe "Aktienresearch alle fünf Stunden". Sie soll aktuelle, zeitgestempelte Quellen aus den jeweils vorherigen ca. fünf Stunden untersuchen:
1. Primärquellen: IR-Meldungen, Gewinnwarnungen, SEC-/Börsenfilings, Earnings-Kalender, Unternehmenspräsentationen.
2. Vertrauenswürdige Finanzmedien: neue Fakten und deren ursprüngliche Urheber verifizieren.
3. Analysten- und Peer-Updates: Konsensänderungen, Veränderungen des Ausblicks, Quartalsberichte der Wettbewerber.
4. Diskussionsforen/Reddit/Stocktwits: **nur Sentiment, mögliche Themen und zu prüfende Hinweise**, niemals unbestätigte Behauptungen als Fakten.
5. Kurse, Futures, Optionsinformationen und Short-Interest, soweit tatsächliche Zeitstempel und lizenzierter Zugriff vorhanden sind.

Überwache besonders Unternehmen mit angekündigten Quartalszahlen innerhalb von 1–10 Handelstagen sowie offene Earnings-Paper-Trades. Kontinuierliche Echtzeit-Abdeckung des gesamten Webs ist nicht möglich: dokumentiere Quellen- und Universumsabdeckung je Durchlauf.

## Research-Ausgabe für "Aktienresearch Bericht"
Für jedes relevante Ereignis erfassen: tickers, Quelle/Link, Zeitpunkt der Veröffentlichung (Zeitzone), Zeitpunkt der Abfrage, Neuigkeitsgrad, verifizierbare Fakten, Ungewissheiten, mögliche Erwartungsüberraschung, Marktkursreaktion und Einfluss auf **vorher** festgelegte Long-/Short-These.
Ein Ranking der besten mindestens 10 belegbaren Kandidaten mit Anlass, Earnings-Termin, neuer vs. vorheriger These und Gründe für Re-Ranking erstellen. Nicht kalibrierte Scores NICHT als Wahrscheinlichkeiten deklarieren.
Abgeschlossene/aktive Paper-Trades in `my_db.main.paper_trades` und `paper_orders` abfragen und EUR-PnL mit 100€ Einsatz, synthetischem 5×-Hebel, Einstiegs-/Ausstiegszeit und TP/SL ausweisen. Einnahmen, Nachrichten und deren Kausalität unterscheiden. Modellprognosefehler dokumentieren.
Keine realen Orders und keine normalen Momentum-Trades.

## Technische Realität / Grenzen
- `sync.py`: EODHD-Preisdatenimport; kein Nachrichten-/Forumsscraper.
- `paper_trading.py`: **noch unkalibrierte** Kurstrend-Heuristik mit strengem Earnings-Kalender-Gating. Die Ergebnisse der Scheduled-Webrecherche sind aktuell **noch nicht** programmgesteuert mit diesem Trader verknüpft.
- `.github/workflows/sync.yml`: Datenimport + simulierte Signalverarbeitung; keine kontinuierliche Internetrecherche.
- ChatGPT Scheduled: kann in getrennten Durchläufen recherchieren, aber ein tatsächlich erfolgreicher persistenter Schreibvorgang muss jeweils überprüft werden.
- `my_db.main.stock_prices`: historische Kursdaten; keine Schlussfolgerung über echten Wert eines Turbo-Zertifikats.
- EODHD-Zugang für Earnings-Daten kann tarifabhängig fehlen. Dann neue Signale blockieren und dies ausdrücklich berichten.

## Roadmap
1. Research-Archiv mit unveränderlichen, zeitgestempelten Facts/Fundstellen und Thesenrevisionen.
2. Saubere Verknüpfung der Research-Faktoren mit Earnings-Paper-Trades; ohne dokumentierte Quellen/Signal keine Aktion.
3. Walk-forward-Backtest, Prognosekalibrierung, ex-post Analyse, Gegenhypothesen.
