# Messerli Helper

Messerli Helper ist eine lokale Windows-Desktop-App für die Tagesplanung und die anschliessende Tastatur-Automation für die Messerli-Zeiterfassung. Die Anwendung kombiniert eine einfache Zeitleisten-UI mit lokaler JSON-Speicherung und einem PyInstaller-/Inno-Setup-Build für die Verteilung.

## Funktionsumfang

- Tagesplanung im 15-Minuten-Raster von 06:00 bis 18:00
- Zeitblöcke per Drag anlegen, verschieben, vergrössern, verkleinern, teilen und löschen
- Blocktypen für Arbeit, Pause und Kompensation
- Projektvorlagen mit lokaler Speicherung, Standardbemerkungen und Favoriten
- Validierung gegen Überlappungen, ungültige Zeiträume und fehlende Pflichtfelder
- Produktivzeit-Anzeige mit Soll/Ist-Differenz pro Wochentag
- Automation mit Countdown und sofortigem Abbruch über `ESC`
- Lokales Logging unter `%LOCALAPPDATA%\MesserliHelper\logs`

## Voraussetzungen

- Windows 10 oder neuer
- Python 3.12 oder neuer
- geöffnete Messerli-Zeiterfassung für die eigentliche Automation
- optional: Inno Setup 6 (`ISCC.exe`) für den Installer-Build

## Installation und Start

Für den lokalen Start reichen die Runtime-Abhängigkeiten:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

Für Tests, PyInstaller und Packaging:

```powershell
python -m pip install -r requirements-dev.txt
```

Die App speichert ihre Daten standardmässig unter `%LOCALAPPDATA%\MesserliHelper`. Beim ersten Start werden die Beispielvorlagen aus [examples/project_templates.json](examples/project_templates.json) automatisch in den lokalen Datenspeicher übernommen.

## Bedienung

1. Datum wählen oder bei Bedarf den Vortag kopieren.
2. In der Tagesansicht einen Zeitblock per Drag aufziehen.
3. Blocktyp, Zeitraum, Projektnummer und Bemerkung festlegen.
4. Weitere Blöcke erstellen oder bestehende Einträge per Doppelklick bearbeiten.
5. Rechts die Validierung und die Produktivzeit prüfen.
6. Auf `Ausfüllen in Messerli` klicken.
7. Das erste leere Auftragsfeld in Messerli anklicken und den Countdown bestätigen.
8. Die Automation bei Bedarf jederzeit mit `ESC` abbrechen.

## Tests

```powershell
python -m pytest tests
```

Die Tests decken aktuell unter anderem Zeitkonvertierung, Validierung, Sortierung, JSON-Serialisierung und die Generierung der Automationsschritte ab.

## Build und Packaging

### EXE bauen

```powershell
.\build_exe.ps1
```

Der Standard-Build erzeugt eine gebündelte Anwendung unter `dist\MesserliHelper\MesserliHelper.exe`.

Für eine einzelne EXE-Datei:

```powershell
.\build_exe.ps1 -OneFile
```

Dann liegt das Ergebnis unter `dist\MesserliHelper.exe`.

Der Build läuft über [MesserliHelper.spec](MesserliHelper.spec). Vor dem Packaging werden die Dateien `packaging/windows/version_info.txt` und `packaging/windows/installer_metadata.iss` automatisch aus den Metadaten in `app/metadata.py` erzeugt.

### Installer bauen

```powershell
.\build_installer.ps1
```

Optional kann der EXE-Build übersprungen werden:

```powershell
.\build_installer.ps1 -SkipExeBuild
```

Der Installer wird als Per-User-Setup gebaut und installiert standardmässig nach `%LOCALAPPDATA%\Programs\Messerli Helper`. Die erzeugten Installer-Dateien landen unter `dist\installer\`.

### Auto-Updates Ã¼ber GitHub Releases

Die App prÃ¼ft beim Start automatisch auf neue Versionen Ã¼ber das GitHub-Release `latest` des konfigurierten Repositorys. ZusÃ¤tzlich gibt es in der Toolbar den Button `Nach Updates suchen`.

Aktuell erwartet der Updater:

- ein Ã¶ffentliches GitHub-Repository
- einen verÃ¶ffentlichten Release mit Tag `vX.Y.Z` oder `X.Y.Z`
- ein Installer-Asset mit dem Namen `MesserliHelper-Setup-X.Y.Z.exe`

Der Download erfolgt direkt vom `browser_download_url` des passenden Release-Assets. Nach dem Download startet die App den Inno-Setup-Installer und beendet sich anschliessend selbst.

Typischer Release-Ablauf:

1. Version in `app/metadata.py` erhÃ¶hen.
2. Installer mit `.\build_installer.ps1` bauen.
3. Auf GitHub einen neuen Release mit passendem Tag erstellen, z. B. `v0.1.7`.
4. Die Datei `dist\installer\MesserliHelper-Setup-0.1.7.exe` als Release-Asset hochladen.
5. Release verÃ¶ffentlichen.

Wichtige Hinweise:

- Ohne verÃ¶ffentlichten GitHub Release findet die App kein Update.
- Der Asset-Name muss exakt zum Versionsschema passen.
- FÃ¼r weniger SmartScreen-Warnungen ist ein Code-Signing-Zertifikat empfehlenswert, aber nicht Teil dieser Umsetzung.

## Projektstruktur

```text
app/                  Anwendungscode für UI, Modelle, Services und Automation
tests/                Pytest-Testfälle
examples/             Beispiel- und Seed-Daten
packaging/windows/    Icons, Inno-Setup-Skripte und Build-Metadaten
build_exe.ps1         PyInstaller-Build
build_installer.ps1   Inno-Setup-Build
MesserliHelper.spec   PyInstaller-Spezifikation
```

## Lokale Daten

Die Anwendung schreibt ihre Nutzdaten in `%LOCALAPPDATA%\MesserliHelper`:

- `days\YYYY-MM-DD.json` für gespeicherte Tagesblöcke
- `templates.json` für Projektvorlagen
- `preferences.json` für lokale Einstellungen
- `logs\messerli-helper.log` für Laufzeitprotokolle

## Grenzen und Hinweise

- Die Automation arbeitet ausschliesslich über Tastatureingaben und setzt den manuellen Fokus auf das erste leere Messerli-Feld voraus.
- Der globale `ESC`-Abbruch verwendet `keyboard`; je nach Windows-Rechtekontext kann eine erhöhte Berechtigung hilfreich sein.
- Die Zeitleiste ist bewusst auf den Bereich 06:00 bis 18:00 ausgelegt.
- Build-Artefakte und lokale Cache-Dateien gehören nicht ins Repository und werden über die `.gitignore` ausgeschlossen.
