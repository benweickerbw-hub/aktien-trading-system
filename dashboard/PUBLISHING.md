# Aktien-Kommandozentrale als öffentliche GitHub Pages Website

## Einmalig aktivieren

1. Öffne **https://github.com/benweickerbw-hub/aktien-trading-system/settings/pages**
2. Unter **Build and deployment → Source** wähle **GitHub Actions**.
3. Öffne https://github.com/benweickerbw-hub/aktien-trading-system/actions/workflows/aktien-pages.yml und klicke **Run workflow** auf Branch `main`, falls nicht automatisch ein neuer Deploy-Lauf startet.
4. Nach erfolgreichem Deploy: **https://benweickerbw-hub.github.io/aktien-trading-system/**.

**Status beim Einrichten:** Der erste GitHub Actions Lauf `42130063195` hat den statischen HTML-Build bereits erfolgreich ausgeführt, scheiterte aber erwartungsgemäß am Schritt `Configure GitHub Pages`, weil Pages noch nicht aktiviert war. Die Website war zu diesem Zeitpunkt NICHT live.

### Plan-Voraussetzung

GitHub Free kann Pages nur aus öffentlichen Repositories veröffentlichen. Das vorhandene `aktien-trading-system` ist PRIVAT. GitHub Pro oder ein anderer Pages-fähiger Plan ist nötig, wenn dieses Repository privat bleiben soll. **Nicht das gesamte Repo auf public schalten, nur um Pages zu nutzen:** Es enthält andere Research-Dateien und Workflow-Konfigurationen, die nicht automatisch publiziert werden sollen. Alternativ könnte ein gesondertes öffentliches Repo ausschließlich die generierte Website hosten. Das erfordert separat eingerichtete Repo- und Sync-Berechtigungen.

## Laufende Veröffentlichung (kein HTML-Download)

Der Workflow `.github/workflows/aktien-pages.yml` läuft bei jeder Änderung der Dateien
- `dashboard/template.html` (Layout + Charts + Deep-Dives)
- `dashboard/positions.json` (Paper-Trade-Portfolio; manche user-reported Positionen)
- `dashboard/research.json` (stündliche Berichte, Dossiers, Screening-Funnel)
- `scripts/build_dashboard_pages.py` (Publisher)

Der Publisher erzeugt ausschließlich `public/index.html`, `public/release.json` und `public/.nojekyll` als GitHub Pages Artefakt. Andere private Repositorydateien bleiben außerhalb des bereitgestellten Artefakts. **Die Inhalte der veröffentlichten drei Dashboard-Dateien werden vollständig öffentlich.** Keine Zugangstoken oder Geheimnisse in die Dashboard-JSON/HTML schreiben.

Die Seite vergleicht alle 60 Sekunden `release.json` mit ihrem beim Laden eingebetteten Commit SHA. Nach erfolgreichem neuen Deployment lädt sie sich im sichtbaren Browser-Tab unter derselben URL mit erhaltenem Hash-Routenfilter neu. Bei geschlossenem Browser wird beim nächsten Öffnen der aktuelle Stand geladen. GitHub Actions und GitHub Pages können eine kurze Deploy- oder CDN-Verzögerung haben. Wenn ein Research-Agent keinen GitHub-Commit schreibt, wird die Site nicht erneuert.

TradingView stellt Chartdaten über einen externen Widget-Anbieter bereit. Das ist **nicht notwendigerweise ein unverzögerter Echtzeitkurs**. Paper-PnL berechnet das Dashboard anhand separat verifizierter Preisstempel und ist keine Brokerposition. Es werden keine echten Orders ausgeführt.

## Technische Prüfung

GitHub Actions → `Publish Aktien Kommandozentrale`: der Schritt `Build static command center` muss erfolgreich sein, danach `Configure GitHub Pages`, `Upload PUBLIC dashboard only` und `Deploy current snapshot`. Sichtbare Website-URL und Deploymentstatus stehen im erfolgreichen Actions-Lauf.

Dokumentation: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
