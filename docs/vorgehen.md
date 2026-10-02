# Wie das Projekt entstanden ist

Diese Seite beschreibt den Weg, nicht nur das Ergebnis. Wer eine andere Dimplex-Anlage oder
einen anderen Softwarestand hat, kann so prüfen, was davon bei ihm stimmt, und fehlende Werte
selbst finden.

## Womit gearbeitet wurde

| Werkzeug | Wofür |
|---|---|
| Home Assistant OS, eingebaute Modbus-Integration | Lesen und Schreiben der Register |
| NWPM Touch der Wärmepumpe | Modbus-TCP-Gateway, Verlaufsdatenbank |
| Display der Wärmepumpe und Dimplex Home App | Gegenprobe für jeden gefundenen Wert |
| Python 3, [`tools/dimplex_scan.py`](../tools/dimplex_scan.py) | Register und Coils auslesen, Scans vergleichen, Werte suchen |
| ein SQLite-Werkzeug (DB Browser for SQLite oder Python) | Verlaufsdatenbank auswerten |
| Shelly 3EM am Abgang der Wärmepumpe | unabhängige Strommessung für die Arbeitszahl |
| File editor oder Studio Code Server | YAML-Dateien bearbeiten |
| HACS mit plotly-graph-card, apexcharts-card, lovelace-heat-pump-card, card-mod | Dashboard |
| Claude (KI-Assistent von Anthropic) mit dem Add-on ha-mcp | Auswertung der Scans und der Datenbank, Entwurf der YAML-Dateien, Aufbau und Test des Dashboards direkt an der laufenden Anlage |

Die Konfiguration ist im Dialog mit dem KI-Assistenten entstanden. Jeder Schritt wurde an der
echten Anlage gegengeprüft; was nicht geprüft werden konnte, ist in
[`bekannte-grenzen.md`](bekannte-grenzen.md) als ungeprüft markiert.

## 1. Ausgangspunkt: die offiziellen Listen reichen nicht

Dimplex veröffentlicht Datenpunktlisten für Modbus. An dieser Anlage zeigte sich:

- Die Temperaturen liegen nicht auf den Adressen der Liste, sondern im Bereich 1xxx
  (Außentemperatur 1301, Vorlauf 1300, Warmwasser 1305).
- Drücke im Kältekreis, Anlagendruck, Volumenstrom und Inverterfrequenz stehen in keiner Liste,
  obwohl App und Display sie anzeigen.

Also mussten die Adressen an der Anlage selbst gefunden werden.

## 2. Register scannen

Das Skript liest Registerbereiche blockweise und schreibt sie in eine CSV-Datei. Es kennt nur
Lese-Funktionscodes und kann nichts verstellen.

```bash
# Scan bei stehender Wärmepumpe
python3 dimplex_scan.py 192.168.x.x --label wp_aus

# Scan bei laufendem Verdichter (z. B. während einer Warmwasserbereitung)
python3 dimplex_scan.py 192.168.x.x --label wp_laeuft

# Nur die Register zeigen, die sich unterscheiden
python3 dimplex_scan.py --diff dimplex_scan_wp_aus_*.csv dimplex_scan_wp_laeuft_*.csv

# Einen Wert suchen, den die App gerade anzeigt (alle Skalierungen, mit Toleranz)
python3 dimplex_scan.py --find dimplex_scan_wp_laeuft_*.csv 24.3 --tol 0.3

# Digitale Werte (Coils)
python3 dimplex_scan.py 192.168.x.x --range 1:0:2000 --label coils
```

Bewährtes Vorgehen:

1. Zwei Scans in unterschiedlichen Betriebszuständen, dann der Vergleich. Was sich nicht ändert,
   ist meist eine Einstellung oder ein Zähler; was sich ändert, ein Messwert.
2. Im selben Moment einen Wert in der App ablesen und mit `--find` suchen. Ein Treffer allein
   beweist nichts, weil viele Register zufällig ähnliche Zahlen enthalten. Erst wenn derselbe
   Kandidat in einem zweiten Scan mit einem anderen App-Wert wieder passt, gilt er als gefunden.
3. Den Kandidaten als Sensor anlegen und über einen ganzen Verdichterlauf beobachten. Ein
   Hochdruck muss beim Anlauf steigen, ein Niederdruck fallen.

## 3. Die Verlaufsdatenbank als Abkürzung

Das NWPM Touch speichert einen Verlauf und gibt ihn als SQLite-Datei heraus:

```
https://<IP-des-NWPM-Touch>/usr-cgi/downloadTelemetryData.cgi
```

Die Zugangsdaten zeigt das Display unter Analytics → Hard- und Software → Netzwerk → Gateway
Zugang.

Die Datei enthält eine Tabelle `telemetry_history` mit den Spalten `name`, `value` und `time`
(Millisekunden seit 1970). `name` ist die Kennung des Datenpunkts, zum Beispiel `1280a` oder
`1472i`. Ein Überblick, welche Kennungen es gibt:

```sql
SELECT name, COUNT(*) AS anzahl, MIN(value), MAX(value)
FROM telemetry_history
GROUP BY name
ORDER BY name;
```

Aus dem Vergleich von Kennungen mit bereits bekannten Registern ergab sich die Adressregel
(`Na` → Register N, `Ni` → Register N + 5001, `Nd` → Coil N). Sie ist in
[`modbus-register.md`](modbus-register.md) mit den Prüfstellen beschrieben. Seitdem lässt sich zu
jeder Kennung aus der Datenbank die Modbus-Adresse ausrechnen, ohne zu suchen.

Die Bedeutung der Kennungen steht nicht in der Datenbank. Sie ergibt sich aus dem Verlauf: Ein
Wert, der nur während der Warmwasserbereitung auf 1 steht, ist die Warmwasserladepumpe; ein
Wert, der dem Niederdruck folgt, die Verdampfungstemperatur.

Die Datenbank enthält auch Gerätekennungen (Seriennummer, Hostname). Sie gehört nicht in ein
öffentliches Repository.

## 4. Sensoren anlegen

Ein Eintrag im Modbus-Paket sieht so aus:

```yaml
- name: Dimplex_WP Hochdruck
  unique_id: dimplex_wp_hochdruck
  slave: 1
  address: 1280
  input_type: input
  data_type: int16
  scale: 0.1
  precision: 1
  unit_of_measurement: bar
  device_class: pressure
  state_class: measurement
  scan_interval: 31
```

Was sich bewährt hat:

- **Abfrageintervalle versetzen.** Jeder Sensor hat ein anderes `scan_interval`, meist eine
  Primzahl. So fallen die Abfragen nicht auf denselben Moment, und das Gateway bleibt
  ansprechbar. Schnelle Werte (Drücke, Leistung) alle 30 bis 60 Sekunden, Zähler alle 10 Minuten.
- **`int16` für alles, was negativ werden kann** (Temperaturen, Umweltleistung beim Abtauen).
- **Temperaturdifferenzen ohne `device_class`.** Sonst rechnet Home Assistant Kelvin in Grad
  Celsius um und zieht 273 ab.
- **`unique_id` vergeben**, damit sich Name, Bereich und Symbol in der Oberfläche ändern lassen.
- **Rohwerte und Klartext trennen.** Der Modbus-Sensor liefert den Code (`…_raw`), ein
  Template-Sensor macht daraus Text. So bleibt der Code für Automationen erhalten.

## 5. Berechnete Werte

In `dimplex_steuerung.yaml`:

- **Wärmemengen** aus drei Registern zusammengesetzt, mit einer Verfügbarkeitsprüfung gegen
  0-Lesungen (siehe [`bekannte-grenzen.md`](bekannte-grenzen.md)).
- **COP** aus Wärmeleistung und elektrischer Leistung der Wärmepumpe, nur bei laufendem
  Verdichter. Als Gegenprobe ein zweiter COP mit der Leistung vom Shelly; er fällt niedriger
  aus, weil der Shelly Pumpen und Regelung mitmisst.
- **Status im Klartext** aus Verdichter, Warmwasserpumpe, zweitem Wärmeerzeuger und EVU-Sperre.
- **Spreizung und Regelabweichung** als einfache Differenzen.

Jeder Template-Sensor hat ein `availability`-Template. Beim Start von Home Assistant sind die
Modbus-Werte kurz „unbekannt"; ohne die Prüfung würden die Sensoren in dieser Zeit 0 anzeigen und
Statistik und Automationen stören.

## 6. Schreiben mit Kontrolle

Das Muster ist für alle Einstellwerte gleich:

```
Helfer in der Oberfläche  →  Automation „schreiben"  →  modbus.write_register
          ↑                                                      ↓
Automation „synchronisieren"  ←  Lesesensor  ←  Register in der Wärmepumpe
```

- Der Helfer (`input_number`, `input_select`) begrenzt, was überhaupt eingestellt werden kann.
- Die Schreib-Automation reagiert nur auf echte Änderungen, nicht auf den Start von Home
  Assistant.
- Die Synchronisierung holt Änderungen zurück, die am Display oder in der App gemacht wurden.

Bei der Heizkurve kommt dazu:

- **Vergleich vor dem Schreiben:** Steht der Wert schon in der Wärmepumpe, wird nicht
  geschrieben.
- **Entprellung:** 3 Sekunden warten, damit mehrfaches Tippen nur einmal schreibt.
- **Warteschlange:** `mode: queued`, damit nie zwei Schreibzugriffe gleichzeitig laufen.
- **Rücklesen:** nach dem Schreiben den Lesesensor aktualisieren und vergleichen. Stimmt der
  Wert nicht, gibt es eine Meldung und der Helfer springt zurück.
- **Schutz vor dem eigenen Echo:** Die Synchronisierung fasst einen Helfer nicht an, der in den
  letzten 15 Sekunden geändert wurde. Ohne das ging im ersten Test eine von zwei kurz
  nacheinander gemachten Änderungen verloren.

Die Parallelverschiebung hat eine Besonderheit: Das Register zählt von 0 bis 38, 19 heißt „keine
Verschiebung". Geschrieben wird also der gewünschte Wert plus 19, der Lesesensor zieht mit
`offset: -19` wieder ab.

## 7. Die Heizkurve nachbilden

Die Wärmepumpe verrät nur zwei Einstellwerte, nicht die Kurvenform. Vorgehen:

1. Aus der Langzeitstatistik von Home Assistant die Wertepaare Außentemperatur und
   Rücklauf-Sollwert eines Winters nehmen. Zeiten ohne Heizbetrieb (Sollwert 15 °C) weglassen.
2. Eine Kurvenform ansetzen, die bei 20 °C außen durch 20 °C geht und bei −20 °C den Endpunkt
   erreicht: `20 + (Endpunkt − 20) × ((20 − Außen) / 40) ^ p`.
3. Den Exponenten `p` so wählen, dass die Abweichung zu den Statistikwerten minimal wird.
   Ergebnis: 0,733.
4. Gegenprobe an der Anlage: Endpunkt und Parallelverschiebung verstellen, einige Minuten
   warten, Sollwert der Wärmepumpe mit der Formel vergleichen.

Messpunkte und Ergebnis stehen in [`heizkurve.md`](heizkurve.md).

## 8. Das Heizkurven-Diagramm

Die Karte `plotly-graph` ist eigentlich für Verläufe gedacht. Hier zeichnet sie eine berechnete
Kurve:

- Die ersten fünf Einträge sind echte Entitäten mit `internal: true`. Sie werden nicht
  gezeichnet, sorgen aber dafür, dass die Karte neu rechnet, sobald sich einer der Werte ändert.
- Der erste Eintrag trägt eine Funktion `fn`. Sie liest die aktuellen Werte aus `hass.states`,
  rechnet Kurve, Punkte und Achsengrenzen aus und legt alles in `vars.hk` ab.
- Alle sichtbaren Linien und Punkte sind Einträge ohne Entität (`entity: ''`), deren `x` und `y`
  per `$ex` aus `vars.hk` kommen.
- Die x-Achse ist auf `type: linear` gestellt und läuft durch einen umgedrehten `range` von warm
  nach kalt.

## 9. Überwachung

- **Tageswerte** über `history_stats`: Verdichterstarts, Laufzeit und Abtauungen seit
  Mitternacht. Daraus die mittlere Laufzeit je Start als Hinweis auf Takten.
- **Arbeitszahl über 7 Tage** über `statistics` (Änderung der Wärmemenge und des Stromzählers in
  7 Tagen), geteilt durch einen Template-Sensor.
- **Warnungen** bei falschem Anlagendruck, bei vielen Verdichterstarts und bei Störung. Alle mit
  einer zweiten Auslösung, die einen Neustart von Home Assistant überlebt.

## 10. Testen an der laufenden Anlage

Rechnerisch stimmige Konfiguration reicht nicht. Geprüft wurde so:

- **Warmwasserlauf beobachten:** Anforderung, Pumpen, Verdichter, Drücke, Volumenstrom und
  Frequenz müssen in der richtigen Reihenfolge und Richtung reagieren.
- **Heiztest:** Betriebsmodus auf Winter, Heizkurve deutlich anheben, zusehen, bis der
  Verdichter startet. Dabei zeigte sich die Reihenfolge Pumpenvorlauf → Anforderung → Verdichter
  und dass die Wärmepumpe neue Kurvenwerte erst nach einigen Minuten übernimmt.
- **Plausibilität:** Wärmeleistung gegen Volumenstrom × Spreizung × 1,163 gerechnet. Kurz nach
  dem Start passte das auf 2 %. Während der Verdichter hochfährt, liegen die Werte bis 20 %
  auseinander, weil die Register zu verschiedenen Zeitpunkten gelesen werden.
- **Zähler:** Nach jedem Lauf nachsehen, ob Starts, Laufzeit und Wärmemenge weiterzählen.

Die Ablaufverfolgung der Automationen (Einstellungen → Automationen → Automation → „Traces")
zeigt für jeden Lauf, was geschrieben und was zurückgelesen wurde.

## 11. Was unterwegs schiefging

- **Statistik der Wärmemengen:** 0-Lesungen des Gateways hatten den Zählerstand mehrfach
  aufaddiert. Reparatur und Gegenmaßnahme stehen in [`bekannte-grenzen.md`](bekannte-grenzen.md).
- **Doppelter `automation:`-Schlüssel:** Beim Zusammenkopieren stand der Schlüssel zweimal in
  der Paketdatei. YAML nimmt dann stillschweigend nur den letzten Block; elf Automationen
  fehlten. Jeder Schlüssel darf in einer Datei nur einmal vorkommen.
- **Modbus-Sensor in der Template-Liste:** Ein Modbus-Eintrag war in den `template:`-Abschnitt
  gerutscht. Home Assistant verwirft dann den ganzen Block. Modbus-Sensoren gehören unter den
  Hub, Template-Sensoren unter `template:`.
- **Falsche Stromstatistik:** Ein Verbrauchszähler zeigte rund das 2,4-Fache. Monatswerte immer
  gegen eine zweite Quelle prüfen.
