# Anweisung für Codex / VS Code Agent

## Ziel

Erstelle eine lokale Windows-Desktop-App für eine vereinfachte Zeiterfassung als Vorschalt-Tool für Messerli Informatik Zeiterfassung.

Die App soll eine visuelle Tagesansicht bieten, in der Zeitblöcke per Drag erstellt, bearbeitet und validiert werden können. Danach soll die App die erzeugten Einträge automatisiert in die bereits geöffnete Messerli-Zeiterfassung eintragen.

Die Lösung soll robust, pragmatisch und lokal lauffähig sein. Kein Cloud-Zwang, kein Server, keine externe Datenbank.

## Technologiewahl

Verwende:

- Python 3.12+
- PySide6 für die Desktop-Oberfläche
- SQLite oder alternativ JSON für lokale Speicherung
- pyautogui und/oder keyboard für die Tastaturautomation
- optional pywinauto, falls für Fensterfokus oder Stabilität nötig
- pytest für zentrale Tests

Die App ist primär für Windows gedacht.

## Projektname

Arbeitsname: `messerli-helper`

## Zielbild der App

Die App ist ein visueller Tagesplaner für Zeiterfassungsblöcke.

### Kernablauf

1. Nutzer öffnet die App.
2. Nutzer sieht eine Tagesansicht mit Zeitleiste, z. B. 06:00–18:00.
3. Nutzer zieht per Drag einen Zeitblock auf.
4. Nach dem Erstellen öffnet sich eine kleine Eingabemaske oder ein Seitenpanel mit:
   - Projektnummer oder Projektauswahl aus Vorlagen
   - Bemerkung als Buttons
5. Nutzer speichert den Block.
6. Nutzer kann weitere Blöcke zeichnen, verschieben, teilen, löschen oder anpassen.
7. Unten oder rechts sieht der Nutzer eine Vorschau der Zeilen in Ausfüllreihenfolge.
8. Mit Klick auf **„Ausfüllen in Messerli“** startet ein Countdown.
9. Nutzer fokussiert manuell das erste leere Auftragsfeld in Messerli.
10. Die App schreibt alle Zeilen automatisch in die Zeiterfassung.

## Messerli-Ausfülllogik

Die Eingabe in Messerli folgt abhängig vom Blocktyp exakt diesem Ablauf pro Zeile.

### Normaler Eintrag

1. Projektnummer eingeben, z. B. `25344`
2. `Enter`
3. `Enter`
4. Bemerkung eingeben
5. `Enter`
6. Von eingeben
7. `Enter`
8. Bis eingeben
9. `Enter`

Beispiel:

`25344` → `Enter` → `Enter` → `Installation` → `Enter` → `06.50` → `Enter` → `10.00` → `Enter`

### Pause

1. `Enter`
2. `P` eingeben
3. `Enter`
4. Bemerkung eingeben
5. `Enter`
6. Von eingeben
7. `Enter`
8. Bis eingeben
9. `Enter`

Beispiel:

`Enter` → `P` → `Enter` → `Mittag` → `Enter` → `12.00` → `Enter` → `13.00` → `Enter`

Diese Sequenzen müssen exakt umgesetzt werden.

Die App darf nicht blind selbständig ins vorherige Fenster wechseln und sofort loslegen. Stattdessen:

1. Klick auf **„Ausfüllen in Messerli“**
2. Dialog mit Hinweis: **„Bitte jetzt das erste leere Auftragsfeld in Messerli anklicken.“**
3. 3-Sekunden-Countdown
4. Danach startet die Automatik

Zusätzlich muss es einen Sofort-Abbruch per `ESC` geben.

## Fachliche Anforderungen

### 1. Zeitblöcke

Die App verwaltet Tagesblöcke mit:

- Datum
- Startzeit
- Endzeit
- Blocktyp
- Projektnummer
- Bemerkung

Es gibt mindestens zwei Blocktypen:

- **Normaler Eintrag**
- **Pause**

Für **Pause** ist keine Projektnummer erforderlich.

### 2. Raster

Die Zeitleiste soll standardmässig auf 15-Minuten-Raster snappen.

Erlaubte Viertelstunden:

- `:00`
- `:15`
- `:30`
- `:45`

### 3. Bemerkungen

Für **normale Einträge** sind nur diese Werte erlaubt:

- `Programmierung`
- `AVOR`
- `Fahrt`
- `Installation`
- `IBN`
- `Admin`

Für **Pausen** sind nur diese Werte erlaubt:

- `Mittag`
- `Pause`

Kein Freitext. Keine anderen Werte.

Die UI soll dafür gut sichtbare Buttons oder eine feste Auswahl verwenden.

### 4. Zeitformat für Messerli

Wichtig: Messerli verwendet Minuten in Prozentdarstellung pro Stunde.

Beispiele:

- `09:00` → `09.00`
- `09:15` → `09.25`
- `09:30` → `09.50`
- `09:45` → `09.75`
- `10:00` → `10.00`

Implementiere dafür eine zentrale Konvertierungsfunktion. Diese Logik muss getestet werden.

### 5. Projektvorlagen

Die App soll lokale Projektvorlagen speichern können.

Mindestens:

- Projektnummer
- optional Anzeigename / Bezeichnung
- optional Standardbemerkung

In der Automation wird bei **normalen Einträgen** nur die Projektnummer in Messerli geschrieben.

Bei **Pausen** wird keine Projektnummer geschrieben. Stattdessen wird die definierte Pause-Sequenz mit `P` verwendet.

Die Projektvorlagen sollen lokal gespeichert und in der UI auswählbar sein.

### 6. Vorschau

Die App soll eine klare Vorschau aller Einträge in korrekter Reihenfolge anzeigen, z. B.:

- `25344 | Installation | 06.30 | 10.00`
- `25344 | Admin | 10.00 | 10.50`
- `Pause | Mittag | 12.00 | 13.00`

Die Vorschau soll vor der Automation sichtbar sein.

## UX-Anforderungen

### Tagesansicht

- vertikale oder horizontale Tageszeitleiste
- gut lesbar
- Drag zum Erstellen eines Blocks
- Resize am Anfang und Ende des Blocks
- Verschieben von Blöcken
- Löschen eines Blocks
- Block teilen
- optional Block duplizieren

### Farbkonzept

Verwende pro Bemerkung oder Blocktyp eine feste Farbe, damit der Tagesplan schnell lesbar ist.

Pausen sollen visuell eindeutig von normalen Arbeitsblöcken unterscheidbar sein.

### Komfortfunktionen

- letzter Projektwert darf beim nächsten neuen **normalen** Block vorbelegt werden
- letzter Bemerkungswert darf optional vorbelegt werden
- Datumsauswahl
- neuer Tag / anderer Tag
- Tagesdaten speichern und wieder laden

### Bedienung

Die Oberfläche soll funktional und schlicht sein. Kein unnötiger Designaufwand. Fokus auf Alltagstauglichkeit.

Der Standardablauf soll möglichst kurz sein:

1. Block zeichnen
2. Projekt wählen oder Projektnummer eingeben
3. Bemerkung wählen
4. Speichern
5. nächsten Block zeichnen
6. am Schluss **„Ausfüllen“**

Für Pausen soll der Ablauf sein:

1. Block zeichnen
2. Blocktyp **Pause** wählen
3. Bemerkung **Mittag** oder **Pause** wählen
4. Speichern

## Validierung

Die App muss vor dem Ausfüllen validieren:

- keine überlappenden Blöcke
- Startzeit < Endzeit
- bei normalen Einträgen ist Projektnummer vorhanden
- bei Pausen ist keine Projektnummer nötig
- Bemerkung vorhanden
- Bemerkung passt zum Blocktyp
- Zeiten liegen auf 15-Minuten-Raster
- Reihenfolge korrekt sortierbar
- keine ungültigen Zeitkonvertierungen

Bei Fehlern:

- verständliche Fehlermeldung
- Ausfüllen-Button deaktivieren oder blockieren

## Technische Anforderungen

### Architektur

Baue das Projekt sauber strukturiert auf, z. B.:

```text
app/
  main.py
  ui/
  models/
  services/
  storage/
  automation/
  validation/
  utils/
tests/
README.md
requirements.txt
```

### Trennung der Logik

Trenne sauber:

- UI
- Datenmodell
- Validierung
- Zeitkonvertierung
- Speicherung
- Automation

Keine harte Vermischung aller Logik in einer Datei.

### Logging

Füge einfaches Logging hinzu, damit Ausfüllfehler nachvollziehbar sind.

### Fehlerrobustheit

Die Automation darf nicht stillschweigend fehlschlagen. Zeige Statusmeldungen wie:

- bereit
- Countdown läuft
- Ausfüllen aktiv
- abgebrochen
- abgeschlossen
- Fehler bei Eingabe

## Datenmodell

Definiere mindestens folgende Modelle:

### TimeBlock

- id
- date
- start_time
- end_time
- block_type
- project_number
- remark

### ProjectTemplate

- id
- project_number
- display_name
- default_remark optional

Empfohlene Werte für `block_type`:

- `work`
- `break`

## Konkrete Funktionen, die implementiert werden müssen

### Pflicht

1. Tagesansicht mit Raster
2. Drag-Erstellung von Blöcken
3. Bearbeitung von Blöcken
4. Feste Auswahl der Bemerkung
5. Auswahl des Blocktyps normal oder Pause
6. Projektvorlagen speichern/laden
7. Validierung
8. Vorschau-Liste
9. Zeitkonvertierung ins Messerli-Format
10. Ausfüll-Automation mit Countdown
11. unterschiedliche Eingabelogik für Arbeit und Pause
12. `ESC`-Abbruch
13. Lokale Speicherung
14. `README` mit Startanleitung
15. Tests für zentrale Logik

### Optional, wenn gut machbar

1. Block teilen
2. Block duplizieren
3. Tageskopie vom Vortag
4. CSV-Export der Einträge
5. einfache Einstellungen wie Countdown-Dauer oder Tippgeschwindigkeit

## Tests und Validierung, die du selbst ausführen sollst

Implementiere automatisierte Tests für:

### Zeitkonvertierung

Teste mindestens:

- `06:00` → `06.00`
- `06:15` → `06.25`
- `06:30` → `06.50`
- `06:45` → `06.75`
- `10:00` → `10.00`

### Validierung

Teste mindestens:

- überlappende Blöcke werden erkannt
- leere Projektnummer bei normalem Eintrag wird erkannt
- Pause ohne Projektnummer wird akzeptiert
- ungültige Bemerkung wird erkannt
- Block mit Start >= Ende wird erkannt
- korrekt sortierte Blöcke werden akzeptiert
- Pause mit unzulässiger Arbeitsbemerkung wird erkannt
- normaler Eintrag mit Pausenbemerkung wird erkannt

### Sortierung

Teste, dass Blöcke chronologisch korrekt in Ausfüllreihenfolge gebracht werden.

### Serialisierung

Teste Speichern/Laden von Projekten und Tagesblöcken.

### Automation

Teste mindestens die Generierung der Eingabesequenz für:

- normalen Eintrag
- Pause

## Erwartete Deliverables

Am Ende sollen folgende Dinge vorhanden sein:

1. vollständiger Quellcode
2. funktionierende lokale Desktop-App
3. `README` mit:
   - Voraussetzungen
   - Installation
   - Start
   - Bedienung
   - bekannte Grenzen
4. `requirements.txt`
5. Tests mit `pytest`
6. Beispiel-Projektvorlagen
7. kurze Liste der nächsten sinnvollen Erweiterungen

## Arbeitsweise

Arbeite iterativ und dokumentiere die Schritte.

### Vorgehen

1. Projektstruktur erstellen
2. Datenmodelle und Utilities erstellen
3. Zeitkonvertierung implementieren
4. Validierung implementieren
5. lokale Speicherung implementieren
6. UI-Grundgerüst bauen
7. Zeitleisten-Interaktion bauen
8. Block-Editor bauen
9. Vorschau bauen
10. Automation einbauen
11. unterschiedliche Automation für Arbeitsblöcke und Pausen einbauen
12. Tests schreiben
13. `README` fertigstellen
14. finale Selbstprüfung durchführen

## Finale Selbstprüfung

Bevor du die Aufgabe als abgeschlossen betrachtest, prüfe Folgendes:

- Lässt sich die App lokal starten?
- Lassen sich Blöcke visuell erstellen und bearbeiten?
- Greifen die Validierungen korrekt?
- Ist die Vorschau logisch und korrekt sortiert?
- Ist die Messerli-Konvertierung korrekt?
- Werden Pausen korrekt mit `P` eingetragen?
- Startet die Automation erst nach Nutzerfokus und Countdown?
- Funktioniert der `ESC`-Abbruch?
- Sind die wichtigsten Tests vorhanden und grün?
- Ist das `README` ausreichend klar?

## Wichtige Grenzen

- Keine Änderung an Messerli selbst
- Keine direkte API-Integration mit Messerli voraussetzen
- Automation nur über Tastatureingaben
- Kein Freitext für Bemerkungen
- Lösung primär für Windows
- Keine unnötige technische Überkomplexität

## Ausgabeformat von dir

Arbeite das Projekt direkt aus. Gib nicht nur eine Beschreibung, sondern:

- lege die Dateien an
- implementiere den Code
- schreibe Tests
- dokumentiere alles
- validiere die Lösung

Wenn etwas technisch unsicher ist, entscheide pragmatisch und dokumentiere die Annahme kurz im `README`.

## Zusatz: konkrete Fachregeln

- Bemerkung bei normalen Einträgen darf nur einer der definierten Arbeitswerte sein
- Bemerkung bei Pausen darf nur `Mittag` oder `Pause` sein
- Projektnummer ist bei normalen Einträgen Pflichtfeld
- Projektnummer ist bei Pausen nicht erforderlich
- Blöcke dürfen sich nicht überschneiden
- Zeitraster ist 15 Minuten
- Ausgabe in Messerli-Zeitformat:
  - `:00 -> .00`
  - `:15 -> .25`
  - `:30 -> .50`
  - `:45 -> .75`
- Eingabelogik normaler Eintrag:
  - `Projektnummer -> Enter -> Enter -> Bemerkung -> Enter -> Von -> Enter -> Bis -> Enter`
- Eingabelogik Pause:
  - `Enter -> P -> Enter -> Bemerkung -> Enter -> Von -> Enter -> Bis -> Enter`

