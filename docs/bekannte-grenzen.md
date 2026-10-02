# Bekannte Grenzen und Fallstricke

## Eine Anlage, ein Softwarestand

Alles hier ist an einer einzigen Dimplex System M mit Software M3.15 entstanden. Für andere
Geräte, andere Softwarestände des Wärmepumpenmanagers und andere Hydraulik gibt es keine
Erfahrung. Register können anders belegt sein.

## Ungeprüfte Teile

- **Heizkurven-Formel bei Frost.** Angepasst an Statistikdaten, direkt verglichen nur bei rund
  12 °C Außentemperatur.
- **Klartext der Meldecodes.** Die Tabellen stammen aus Dimplex-Unterlagen für Software L/M. An
  der Anlage bestätigt ist nur Sperrcode 9 (Pumpenvorlauf). Unbekannte Codes erscheinen als
  „Code N".
- **Warnungen.** Die Automationen für Anlagendruck und Takten haben noch nie ausgelöst. Die
  Schwellen sind Schätzwerte.
- **`dimplex_helfer.yaml`.** Die Datei bildet Helfer nach, die in der Ursprungsanlage über die
  Oberfläche angelegt sind. Als YAML lief sie noch nicht im Dauerbetrieb.
- **Smart-Grid-Register 7663.** Nur gelesen.
- **Kühlbetrieb.** Nicht getestet. Der Modus „Kühlen" fehlt bewusst in der Auswahlliste.
- **Volumenstrom-Überwachung.** Nicht gebaut. Der Durchfluss liegt je nach Betriebszustand
  zwischen rund 600 und 2600 l/h; für eine sinnvolle Schwelle fehlen Daten aus einer Heizsaison.

## Wärmemengen und Langzeitstatistik

Die Wärmemengenzähler stehen in drei Registern. Liefert das Gateway bei einem Neustart kurz
überall 0, sieht ein `total_increasing`-Sensor einen Zählerreset. Sobald der echte Wert
zurückkommt, addiert die Langzeitstatistik den gesamten Zählerstand ein zweites Mal. In der
Ursprungsanlage waren so über Monate mehrere hunderttausend Kilowattstunden zu viel in der
Statistik.

Gegenmaßnahme in `dimplex_steuerung.yaml`: Die Sensoren sind „nicht verfügbar", solange alle
drei Teilregister 0 liefern.

Ist die Statistik schon verfälscht, lässt sie sich reparieren: Entwicklerwerkzeuge → Statistik →
beim betroffenen Sensor auf das Symbol rechts → „Summe anpassen", die Stunde mit dem Sprung
suchen und korrigieren. Für viele Sprünge geht dasselbe über den WebSocket-Befehl
`recorder/adjust_sum_statistics`.

Dieselbe Falle gilt für jede Formeländerung an einem `total_increasing`-Sensor: Springt der
Wert, landet der Sprung in der Statistik.

## COP-Sensoren sind zeitweise „nicht verfügbar"

`Dimplex_WP COP` und `Dimplex_WP COP_Gemessen` haben nur bei laufendem Verdichter einen Wert.
Ohne Verdichter laufen nur Pumpen und Regelung, der Quotient aus Wärme- und Stromleistung wäre
dann Unsinn. Werte außerhalb von 1 bis 8 werden ebenfalls verworfen; sie entstehen beim Anlauf,
weil die beiden Leistungsregister nicht im selben Moment gelesen werden.

Im Dashboard verschwinden die zugehörigen Kacheln in dieser Zeit.

## Home-Assistant-Neustarts

`for:`-Wartezeiten in Auslösern und `delay` in laufenden Automationen überleben keinen Neustart.
Deshalb:

- Der Warmwasser-Boost endet bei einem Neustart sofort, statt für immer aktiv zu bleiben.
- Störmeldung und Druckwarnung haben zusätzlich eine tägliche Erinnerung um 9 Uhr.
- Der Sollwert-Wächter vergleicht alle 10 Minuten zustandslos, statt sich auf einen Timer zu
  verlassen.
- Die Heizkurven-Synchronisierung wartet nach dem Start 60 Sekunden, bis Modbus gültige Werte
  liefert.

## Schreiben über Helfer statt über Modbus-Entitäten

Geschrieben wird über `input_number`/`input_select` und `modbus.write_register`, nicht über
Modbus-Entitäten vom Typ `number`. Das ist umständlicher, erlaubt aber Entprellung, Grenzen und
Rücklesekontrolle in der Automation.

## Anlagendruck schwankt mit den Pumpen

Der Drucksensor zeigt bei laufenden Pumpen rund 0,2 bar weniger als im Stillstand. Die
Warnschwelle sollte entsprechend Abstand zum Betriebsdruck haben.

## Verzögerung der Wärmepumpe

Geänderte Heizkurvenwerte stehen sofort im Register, wirken aber erst nach etwa 1,5 bis
3,5 Minuten auf den Sollwert. Nach dem Umschalten auf „Winter" vergingen im Test gut
15 Minuten bis zum Verdichterstart, mit zwei Pumpenvorläufen davor.

## Namen

- Die Entitäten heißen `dimplex_wp_…`, weil die Modbus-Sensoren mit `Dimplex_WP …` benannt sind.
  Wer die Namen ändert, muss Pakete und Dashboard mitziehen.
- `sensor.heizung_stormverbrauch` enthält einen alten Tippfehler. Er ist geblieben, weil
  Statistik und Dashboard an der entity_id hängen.
- `sensor.dimplex_wp_temperatur_ruecklauf` ist die Isttemperatur des Heizkreises (Register 2),
  nicht der Rücklauf an der Wärmepumpe.
