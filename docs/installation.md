# Einbau Schritt für Schritt

Die Reihenfolge ist Absicht: erst nur lesen und vergleichen, dann schreiben, zuletzt das
Dashboard.

## 1. Voraussetzungen

- Wärmepumpe mit NWPM Touch im Heimnetz, Modbus TCP erreichbar (Port 502).
- Feste IP-Adresse für das NWPM Touch, am einfachsten als feste Zuordnung im Router.
- Home Assistant mit Zugriff auf `/config` (File editor, Studio Code Server oder Samba).

Modbus TCP verträgt bei diesem Gateway nur wenige gleichzeitige Verbindungen. Wenn schon ein
anderes System per Modbus an der Wärmepumpe hängt, kann es zu Aussetzern kommen.

## 2. Pakete einschalten

In der `configuration.yaml`, falls noch nicht vorhanden:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Danach gibt es den Ordner `/config/packages/`. Jede YAML-Datei darin wird als eigenes Paket
geladen.

## 3. Nur lesen: Modbus

1. `packages/dimplex_modbus.yaml` nach `/config/packages/` kopieren.
   Wer in der `configuration.yaml` schon einen `modbus:`-Abschnitt hat (zum Beispiel für einen
   Wechselrichter), kann die Datei trotzdem als Paket verwenden; Home Assistant führt die Hubs
   zusammen. Alternativ den Hub dort als weiteren Listeneintrag einfügen.
2. In die eigene `/config/secrets.yaml` eintragen (Vorlage: `secrets.yaml.example`):

   ```yaml
   dimplex_modbus_host: 192.168.x.x  # TODO: Anpassen - IP des NWPM Touch
   ```

3. Entwicklerwerkzeuge → YAML → Konfiguration prüfen, dann Home Assistant neu starten.
4. Unter Entwicklerwerkzeuge → Zustände nach `dimplex_wp` filtern und die Werte mit dem Display
   der Wärmepumpe vergleichen: Außentemperatur, Warmwasser, Vorlauf, Rücklauf, Betriebsmodus.

Passt ein Wert nicht, hat die Anlage vermutlich einen anderen Softwarestand. Dann hilft
`tools/dimplex_scan.py`, siehe [`modbus-register.md`](modbus-register.md).

Solange nur diese Datei eingebaut ist, wird nichts in die Wärmepumpe geschrieben.

## 4. Helfer und Auswertung

1. `packages/dimplex_helfer.yaml` und `packages/dimplex_steuerung.yaml` kopieren.
2. In beiden Dateien nach `# TODO: Anpassen` suchen:
   - `notify.mobile_app_dein_geraet` durch den eigenen Benachrichtigungsdienst ersetzen.
   - `sensor.shellyem3_xxxxxxxxxxxx_channel_*_power` durch die eigenen Leistungssensoren
     ersetzen. Ohne Strommessung die betroffenen Sensoren löschen (im README aufgezählt).
   - Grenzen der Helfer prüfen: Warmwasser, Heizkurven-Endpunkt, Parallelverschiebung.
   - Warnschwellen prüfen: Anlagendruck, Verdichterstarts pro Tag.
3. Konfiguration prüfen, neu starten.

Die Helfer in `dimplex_helfer.yaml` lassen sich alternativ über die Oberfläche anlegen. Mit
denselben Namen entstehen dieselben entity_ids. Dann die entsprechenden Abschnitte in der Datei
löschen, sonst gibt es die Entitäten doppelt.

## 5. Schreibwege einzeln testen

Nach dem Neustart stehen die Helfer auf den Werten aus der Wärmepumpe (die
Synchronisierungs-Automationen laufen beim Start und bei jeder Änderung). Dann nacheinander
prüfen, jeweils mit Blick aufs Display:

| Test | Erwartung |
|---|---|
| Betriebsmodus im Helfer umstellen | Display zeigt den neuen Modus |
| Warmwasser-Soll um 1 K ändern | Display zeigt den neuen Sollwert |
| Heizkurven-Endpunkt um 1 K ändern | Rückmeldesensor zeigt den Wert nach wenigen Sekunden |
| Parallelverschiebung um 1 K ändern | ebenso |
| Wert am Display ändern | Helfer zieht nach |

Kommt ein Heizkurvenwert nicht an, erscheint eine Meldung in Home Assistant, und der Helfer
springt auf den Wert zurück, der wirklich in der Wärmepumpe steht.

Ablaufverfolgung: Einstellungen → Automationen → Automation öffnen → „Traces". Dort steht für
jeden Lauf, welcher Wert geschrieben und was zurückgelesen wurde.

## 6. Dashboard

1. Über HACS installieren: plotly-graph-card, apexcharts-card, lovelace-heat-pump-card,
   card-mod. Danach den Browser-Cache leeren.
2. Einstellungen → Dashboards → Dashboard hinzufügen, leer anlegen.
3. Im neuen Dashboard: Stift → drei Punkte → Raw-Konfigurationseditor, den Inhalt von
   `dashboards/heizung.yaml` einfügen, speichern.
4. Ohne das Theme `ios-dark-mode-blue-red` die sechs `theme:`-Zeilen löschen.
5. In der Ansicht „Energie" die Platzhalter der Strommessung ersetzen.

Wer nur das Heizkurven-Diagramm will: `dashboards/karten/heizkurve.yaml` als manuelle Karte
einfügen.

## 7. Was man im Auge behalten sollte

- Nach dem ersten Tag: Stimmen die Monatswerte der Wärmemengen im Dashboard, oder gibt es
  Sprünge? Hintergrund in [`bekannte-grenzen.md`](bekannte-grenzen.md).
- In der ersten Heizwoche: Trifft die Kurve im Diagramm den Sollwert der Wärmepumpe? Wenn die
  Sprechblase dauerhaft eine Zeile „laut Kurve" zeigt, passt die Formel nicht zur Anlage.
