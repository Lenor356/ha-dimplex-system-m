# Modbus-Register der Dimplex System M

Stand Oktober 2026, Software M3.15a04. Diese Seite beschreibt, wie die Adressen zustande kommen,
und listet die Datenpunkte, die in den offiziellen Dimplex-Listen fehlen. Am Ende steht die
vollständige Liste aller Datenpunkte aus [`packages/dimplex_modbus.yaml`](../packages/dimplex_modbus.yaml).

## Woher die Angaben stammen

- Register-Scan mit [`tools/dimplex_scan.py`](../tools/dimplex_scan.py) (nur lesend), einmal bei
  stehender und einmal bei laufender Wärmepumpe, danach Vergleich der beiden Scans.
- Verlaufsdatenbank des NWPM Touch. Sie lässt sich am Gerät herunterladen:
  `https://<IP-des-NWPM-Touch>/usr-cgi/downloadTelemetryData.cgi`. Die Zugangsdaten zeigt das
  Display unter Analytics → Hard- und Software → Netzwerk → Gateway Zugang. Die Datei ist eine
  SQLite-Datenbank mit den Datenpunkten samt Kennung.
- Abgleich der Werte mit Display und Dimplex Home App.

## Adressregel

Verlaufsdatenbank und MQTT-Gateway benennen Datenpunkte als `<Nummer><Typ>`. Daraus ergibt sich
die Modbus-Adresse:

| Kennung | Typ | Modbus | Geprüft an |
|---|---|---|---|
| `Na` | analog, Wert × 0,1 | Register **N** | Temperaturen, Drücke |
| `Ni` | ganzzahlig | Register **N + 5001** | 46i = 5047, 766i = 5767, 767i = 5768, 1042i = 6043, 1380i = 6381, 1491i–1493i = 6492–6494, 2662i = 7663 |
| `Nd` | digital | Coil **N** | 450 von 450 Werten der Datenbank stimmen mit dem Coil-Scan überein |

Weitere Beobachtungen:

- Input-Register (Funktionscode 04) und Holding-Register (Funktionscode 03) liefern dieselben
  Werte.
- Niedrige Register spiegeln sich mehrfach, zum Beispiel 1 = 1301, 2 = 1294, 3 = 1305,
  5 = 1300, 8 = 1280, 101 = 602 = 4865.

## Datenpunkte, die in den offiziellen Listen fehlen

| Wert | Kennung | Register | Skalierung | Status |
|---|---|---|---|---|
| Hochdruck Kältekreis | 1280a | 1280 (= 8) | × 0,1 bar | bestätigt (App; im Warmwasserlauf 12,5 → 32 bar) |
| Niederdruck Kältekreis | 4865a | 4865 (= 101, 602) | × 0,1 bar | bestätigt (im Warmwasserlauf 12,6 → 7,5–9,5 bar) |
| Heizwasser-Anlagendruck | 556a | 556 | × 0,1 bar | bestätigt (App). Fällt bei laufenden Pumpen um etwa 0,2 bar |
| Volumenstrom | 1472i | 6473 | l/h | bestätigt. Gesehen: rund 2400–2600 l/h bei laufendem Verdichter, rund 600 l/h bei Umwälzung ohne Verdichter |
| Inverterfrequenz | 1550i | 6551 | Hz | bestätigt (38–66 Hz) |
| Rücklauf Wärmepumpe (App: „Rücklauftemperatur", „Kühlen Ist") | 637a | 637 (= 800) | × 0,1 °C | bestätigt |
| Heizen Isttemperatur (App: „System") | 1294a | 2 (= 1294) | × 0,1 °C | bestätigt |
| Verdampfungstemperatur | 601a | 601 (= 99) | × 0,1 °C | Deutung aus dem Verlauf |
| Verflüssigungstemperatur | 696a | 696 | × 0,1 °C | Deutung aus dem Verlauf |
| Sauggastemperatur | – | 4866 | × 0,1 °C | Deutung aus dem Verlauf |
| Überhitzung | – | 604 | × 0,1 K | im Verlauf nachgerechnet: Sauggas minus Verdampfung |
| Arbeitszahl Monat / Vormonat / Jahr | – | 8691 / 8645 / 8692 | × 0,01 | Monat entspricht der Seite „Effizienz" der App; Vormonat und Jahr sind Deutung |
| Wärmeleistung / Umweltleistung / elektrische Leistung | 2666i / 2667i / 2668i | 7667 / 7668 / 7669 | × 0,01 kW | Werte plausibel, Zuordnung ist Deutung. Das Paket nutzt davon nur 7668 (Umwelt); Wärme- und elektrische Leistung kommen aus 5168 und 5170 |
| Verdichterstarts gesamt / Heizen / Warmwasser | 1491i / 1492i / 1493i | 6492 / 6493 / 6494 | Anzahl | bestätigt |
| Laufzeit Warmwasserpumpe | 1788i | 6789 | h | bestätigt |
| Heizkurve Parallelverschiebung | 767i | 5036 (= 5768) | Rohwert 0–38, 19 = 0 K | bestätigt, Schreiben getestet |
| Heizkurve Endpunkt bei −20 °C | 766i | 5038 (= 5767) | °C | bestätigt, Schreiben getestet |
| Smart-Grid-Modus per Software | 2662i | 7663 | 0 = Hardware-Eingang, 10–13 = Software-Stufen | nur gelesen. Das Paket liest stattdessen Register 5167; ob beide immer dasselbe liefern, ist nicht geprüft |
| Status / Sperre / Störung / Sensorfehler | – | 103 / 104 / 105 / 106 | Code | in Nutzung |

Der Sensor für Register 2 heißt in diesem Projekt aus historischen Gründen
`sensor.dimplex_wp_temperatur_ruecklauf`. Gemeint ist die Isttemperatur, auf die die Wärmepumpe
im Heizbetrieb regelt. Der echte Rücklauf an der Wärmepumpe ist
`sensor.dimplex_wp_temperatur_ruecklauf_waermepumpe` (Register 637).

## Register, in die geschrieben wird

| Zweck | Register | Wert |
|---|---|---|
| Betriebsmodus | 5015 | 0 Sommer, 1 Winter, 2 Urlaub, 3 Party, 4 Heizstab, 5 Kühlen |
| Heizkurve Parallelverschiebung | 5036 | gewünschte Verschiebung in K **+ 19** (19 = keine Verschiebung) |
| Heizkurve Endpunkt | 5038 | °C |
| Warmwasser-Solltemperatur | 5047 | °C |
| Heizkreis 1 Absenkung/Anhebung | 5065 | 0 Normal, 1 Absenkung, 2 Anhebung |

Geänderte Heizkurvenwerte übernimmt die Wärmepumpe erst nach etwa 1,5 bis 3,5 Minuten in den
Sollwert.

## Digitale Signale (Coils)

Die Coil-Adressen sind bestätigt, die Bedeutung ist aus dem Verlauf abgeleitet
(Schaltzeitpunkte rund um Verdichterläufe).

| Signal | Coil | Verhalten |
|---|---|---|
| Anforderung Heizen | 1205 | 1 kurz vor dem Verdichterstart im Heizbetrieb, 0 am Ende |
| Anforderung Warmwasser | 1206 (identisch: 726) | 1 rund 60 s vor dem Verdichterstart, 0 am Ende |
| Verdichter / Ventilator | 1500 / 1502 | parallel zum Verdichterlauf |
| Erzeugerkreispumpe M16 (vermutlich) | 1516 | läuft bei Heizen und Warmwasser, 20 s Nachlauf |
| Warmwasserladepumpe M18 (vermutlich) | 1517 | läuft nur bei Warmwasser |
| Abtauung | 1504 | schaltet genau dann, wenn die Wärmeleistung negativ wird |

## Wärmemengen

Die Zähler liegen stellenweise in drei Registern (`_1_4`, `_5_8`, `_9_12`):

```
Zählerstand = (1_4) + (5_8) × 10 000 + (9_12) × 100 000 000
```

Beim Neustart des Gateways liefern alle drei Register kurz 0. Ein `total_increasing`-Sensor
wertet das als Zählerreset und addiert danach den vollen Stand noch einmal auf die
Langzeitstatistik. Die Template-Sensoren in `dimplex_steuerung.yaml` gehen deshalb bei einer
0-Lesung aller drei Register auf „nicht verfügbar". Siehe auch
[`bekannte-grenzen.md`](bekannte-grenzen.md).

## Alle Datenpunkte im Paket

Erzeugt aus [`packages/dimplex_modbus.yaml`](../packages/dimplex_modbus.yaml), sortiert nach
Adresse. „Abfrage" ist das `scan_interval` in Sekunden.

### Register

| Register | Typ | Datentyp | Umrechnung | Einheit | Abfrage (s) | Entität |
|---|---|---|---|---|---|---|
| 53 | Input | int16 | × 0,1 | °C | 179 | `sensor.dimplex_wp_temperatur_ruecklauf_soll` |
| 58 | Input | int16 | × 0,1 | °C | 193 | `sensor.dimplex_wp_temperatur_warmwasser_soll_2` |
| 72 | Input | uint16 | – | h | 601 | `sensor.dimplex_wp_betriebsstunden_verdichter_1` |
| 74 | Input | uint16 | – | h | 607 | `sensor.dimplex_wp_betriebsstunden_primaerpumpe` |
| 75 | Input | uint16 | – | h | 613 | `sensor.dimplex_wp_betriebsstunden_2_waermeerzeuger` |
| 76 | Input | uint16 | – | h | 619 | `sensor.dimplex_wp_betriebsstunden_heizungspumpe` |
| 77 | Input | uint16 | – | h | 623 | `sensor.dimplex_wp_betriebsstunden_warmwasserpumpe` |
| 78 | Input | uint16 | – | h | 629 | `sensor.dimplex_wp_betriebsstunden_heizstab` |
| 103 | Input | uint16 | – | – | 29 | `sensor.dimplex_wp_statusmeldung_raw` |
| 104 | Input | uint16 | – | – | 61 | `sensor.dimplex_wp_sperrmeldung_raw` |
| 105 | Input | uint16 | – | – | 59 | `sensor.dimplex_wp_stoermeldung_raw` |
| 106 | Input | uint16 | – | – | 61 | `sensor.dimplex_wp_sensorfehler_raw` |
| 556 | Input | int16 | × 0,1 | bar | 293 | `sensor.dimplex_wp_heizwasser_anlagendruck` |
| 601 | Input | int16 | × 0,1 | °C | 53 | `sensor.dimplex_wp_temperatur_verdampfung` |
| 604 | Input | int16 | × 0,1 | K | 67 | `sensor.dimplex_wp_ueberhitzung` |
| 637 | Input | int16 | × 0,1 | °C | 47 | `sensor.dimplex_wp_temperatur_ruecklauf_waermepumpe` |
| 696 | Input | int16 | × 0,1 | °C | 59 | `sensor.dimplex_wp_temperatur_verfluessigung` |
| 1280 | Input | int16 | × 0,1 | bar | 31 | `sensor.dimplex_wp_hochdruck` |
| 1294 | Input | int16 | × 0,1 | °C | 67 | `sensor.dimplex_wp_temperatur_ruecklauf` |
| 1300 | Input | int16 | × 0,1 | °C | 61 | `sensor.dimplex_wp_temperatur_vorlauf` |
| 1301 | Input | int16 | × 0,1 | °C | 181 | `sensor.dimplex_wp_temperatur_aussentemperatur` |
| 1305 | Input | int16 | × 0,1 | °C | 127 | `sensor.dimplex_wp_temperatur_warmwasser` |
| 4865 | Input | int16 | × 0,1 | bar | 37 | `sensor.dimplex_wp_niederdruck` |
| 4866 | Input | int16 | × 0,1 | °C | 61 | `sensor.dimplex_wp_temperatur_sauggas` |
| 5015 | Input | uint16 | – | – | 307 | `sensor.dimplex_wp_betriebsmodus_raw` |
| 5036 | Holding | uint16 | − 19 | K | 199 | `sensor.dimplex_wp_heizkurve_parallelverschiebung_lesen` |
| 5038 | Holding | uint16 | – | °C | 300 | `sensor.dimplex_wp_heizkurve_endpunkt_lesen` |
| 5047 | Input | int16 | – | °C | 191 | `sensor.dimplex_wp_temperatur_warmwasser_soll_lesen` |
| 5065 | Holding | uint16 | – | – | 197 | `sensor.dimplex_wp_hk1_betriebsverschiebung_raw` |
| 5096 | Input | uint16 | – | kWh | 641 | `sensor.dimplex_wp_waermemenge_heizen_1_4` |
| 5097 | Input | uint16 | – | kWh | 643 | `sensor.dimplex_wp_waermemenge_heizen_5_8` |
| 5098 | Input | uint16 | – | kWh | 647 | `sensor.dimplex_wp_waermemenge_heizen_9_12` |
| 5099 | Input | uint16 | – | kWh | 653 | `sensor.dimplex_wp_waermemenge_warmwasser_1_4` |
| 5100 | Input | uint16 | – | kWh | 659 | `sensor.dimplex_wp_waermemenge_warmwasser_5_8` |
| 5101 | Input | uint16 | – | kWh | 661 | `sensor.dimplex_wp_waermemenge_warmwasser_9_12` |
| 5127 | Input | uint16 | – | kWh | 673 | `sensor.dimplex_wp_umweltenergie_1_4` |
| 5128 | Input | uint16 | – | kWh | 677 | `sensor.dimplex_wp_umweltenergie_5_8` |
| 5129 | Input | uint16 | – | kWh | 683 | `sensor.dimplex_wp_umweltenergie_9_12` |
| 5167 | Input | uint16 | – | – | 311 | `sensor.dimplex_smart_grid` |
| 5168 | Input | uint16 | × 0,01 | kW | 31 | `sensor.dimplex_wp_leistung_thermisch` |
| 5170 | Input | uint16 | × 0,01 | kW | 37 | `sensor.dimplex_wp_leistung_elektrisch` |
| 6473 | Input | uint16 | – | L/h | 41 | `sensor.dimplex_wp_volumenstrom` |
| 6492 | Input | uint16 | – | – | 601 | `sensor.dimplex_wp_taktungen_verdichter_gesamt` |
| 6493 | Input | uint16 | – | – | 607 | `sensor.dimplex_wp_taktungen_verdichter_heizen` |
| 6494 | Input | uint16 | – | – | 613 | `sensor.dimplex_wp_taktungen_verdichter_warmwasser` |
| 6551 | Input | uint16 | – | Hz | 43 | `sensor.dimplex_wp_inverterfrequenz` |
| 7668 | Input | int16 | × 0,01 | kW | 71 | `sensor.dimplex_wp_leistung_umwelt` |
| 8645 | Input | uint16 | × 0,01 | – | 3607 | `sensor.dimplex_wp_cop_vormonat` |
| 8691 | Input | uint16 | × 0,01 | – | 907 | `sensor.dimplex_wp_cop_monat` |
| 8692 | Input | uint16 | × 0,01 | – | 3613 | `sensor.dimplex_wp_cop_jahr` |

### Coils

| Coil | Abfrage (s) | Entität |
|---|---|---|
| 3 | 71 | `binary_sensor.dimplex_wp_smartgrid_eingang_1` |
| 4 | 73 | `binary_sensor.dimplex_wp_smartgrid_eingang_2` |
| 5 | 79 | `binary_sensor.dimplex_wp_evu_sperre` |
| 41 | 31 | `binary_sensor.dimplex_wp_verdichter_1` |
| 42 | 53 | `binary_sensor.dimplex_wp_verdichter_2` |
| 43 | 37 | `binary_sensor.dimplex_wp_primaerpumpe_m11_ventilator_m2` |
| 44 | 41 | `binary_sensor.dimplex_wp_waermeerzeuger_2_e10` |
| 45 | 43 | `binary_sensor.dimplex_wp_heizungspumpe_m13` |
| 46 | 47 | `binary_sensor.dimplex_wp_warmwasserpumpe_m18` |
| 49 | 59 | `binary_sensor.dimplex_wp_zusatzumwaelzpumpe` |
| 50 | 61 | `binary_sensor.dimplex_wp_heizstab_ausgang` |
| 57 | 67 | `binary_sensor.dimplex_wp_stoermeldeausgang` |
| 1205 | 23 | `binary_sensor.dimplex_wp_anforderung_heizen` |
| 1206 | 29 | `binary_sensor.dimplex_wp_anforderung_warmwasser` |
| 1504 | 19 | `binary_sensor.dimplex_wp_abtauung` |

Das Paket fragt Verdichter, Pumpen und Ausgänge über die niedrigen Coils ab (41 bis 57). Die
Coils 1500, 1502, 1516 und 1517 aus der Tabelle weiter oben zeigen dieselben Vorgänge aus Sicht
der Verlaufsdatenbank und werden im Paket nicht verwendet.

## Was nicht funktioniert hat

- Die inoffizielle REST-Schnittstelle `/api/v2/…` am Display ist seit einem Firmware-Update
  gesperrt.
- Das MQTT-Gateway des NWPM Touch wurde nicht getestet.
