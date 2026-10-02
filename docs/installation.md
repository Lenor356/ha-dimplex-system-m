# Einbau Schritt für Schritt

Die Reihenfolge ist Absicht: erst nur lesen und vergleichen, dann schreiben, zuletzt das
Dashboard.

## 1. Voraussetzungen

- Wärmepumpe mit **NWPM Touch-Erweiterung** im Heimnetz (Dimplex-Artikel 378800, sitzt im
  Wärmepumpenmanager im Steckplatz „Serial Card/BMS Card"). Laut Dimplex-Wiki ab WPM-Software
  M3.3 und Firmware A2.1.0 – B2.1.0.
- Feste IP-Adresse für das Modul, am einfachsten als feste Zuordnung im Router.
- Home Assistant mit Zugriff auf `/config` (File editor, Studio Code Server oder Samba).

### Modbus TCP freigeben

Modbus TCP ist an der NWPM Touch-Erweiterung nicht von selbst aktiv. Einmalig in der
Weboberfläche des Moduls freigeben:

1. **IP-Adresse ablesen:** am Display der Wärmepumpe im Menü „Analytics".
2. **Weboberfläche öffnen:** im Browser `https://<IP-Adresse>/` eingeben. Das `https://` muss
   davorstehen, sonst kommt keine Verbindung zustande. Der Browser meldet „Dies ist keine
   sichere Verbindung", weil das Modul ein eigenes Zertifikat verwendet: „Erweitert" wählen,
   dann „Weiter zu … (unsicher)".
3. **Anmelden:** Benutzer `admin`. Das Passwort steht am Display unter
   Analytics → Hard- und Software → Netzwerk → Gateway Zugang.
4. **Freigeben:** in der Weboberfläche „Einstellungen" öffnen, in der Kachel „Gateway Zugang"
   die Netzwerkdienste freigeben.
5. **Neu starten** und danach nachsehen, ob die Freigabe noch gesetzt ist.

Danach antwortet das Modul auf Modbus TCP, Port 502. In diesem Projekt wird Unit 1 (`slave: 1`)
verwendet.

Quelle der Schritte: Dimplex-Wiki,
[Modbus TCP Anbindung](https://dimplex.atlassian.net/wiki/spaces/DW/pages/3303571457) und
[NWPM Touch-Erweiterung](https://dimplex.atlassian.net/wiki/spaces/DW/pages/3017506817).

### Modbus und App nebeneinander

An der Ursprungsanlage laufen Modbus TCP und die Dimplex Home App gleichzeitig. Die
Cloud-Anbindung lässt sich in derselben Kachel („Gateway Zugang" → „Cloud Sync") ein- und
ausschalten, muss für Modbus aber nicht aus sein. Die App ist beim Einrichten nützlich: Jeder
Wert aus Home Assistant lässt sich dort gegenprüfen.

Ob mehrere Modbus-Clients gleichzeitig funktionieren (zum Beispiel Home Assistant und ein
Energiemanager), ist an der Ursprungsanlage nicht getestet.

### Zugangsdaten für die Verlaufsdatenbank

Dieselbe Anmeldung gilt für den Download der Verlaufsdatenbank unter
`https://<IP-Adresse>/usr-cgi/downloadTelemetryData.cgi`. Wozu sie gut ist, steht in
[`vorgehen.md`](vorgehen.md).

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
   dimplex_modbus_host: 192.168.x.x  # TODO: Anpassen - IP der NWPM Touch-Erweiterung
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
