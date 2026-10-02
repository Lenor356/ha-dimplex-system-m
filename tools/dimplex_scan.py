#!/usr/bin/env python3
"""
Dimplex WPM / System M - Modbus-TCP Register-Scan (NUR LESEN)
=============================================================

Sucht undokumentierte Datenpunkte (Hochdruck, Niederdruck, Anlagendruck,
Volumenstrom ...), indem Input- und Holding-Register blockweise gelesen
und als CSV gespeichert werden.

SICHERHEIT
  - Das Skript kann technisch NUR lesen: es kennt ausschliesslich die
    Lese-Funktionscodes 01 (Coils), 02 (Discrete Inputs), 03 (Holding)
    und 04 (Input). Schreib-Funktionscodes (05/06/15/16) existieren nicht.
  - Kleine Pause zwischen Anfragen, damit der WPM nicht ueberlastet wird.
  - Abbruch nach zu vielen Kommunikationsfehlern in Folge.

ADRESSEN
  Ausgegeben werden PDU-Adressen - identisch mit 'address:' in der
  Home-Assistant-modbus-YAML (z.B. Input 1301 = Aussentemperatur).

KEINE ZUSATZPAKETE NOETIG - nur Python 3.

AUFRUF
  Scan (Standard-Bereiche):
    python3 dimplex_scan.py 192.168.x.x --label wp_laeuft
  Eigene Bereiche (FC:Start:Ende, Ende exklusiv), mehrfach moeglich:
    python3 dimplex_scan.py 192.168.x.x --range 4:1250:1400
  Coils (digitale Werte, z.B. Anforderung Heizen/Warmwasser) lesen:
    python3 dimplex_scan.py 192.168.x.x --range 1:0:2000 --label coils
  Zwei Scans vergleichen (zeigt nur geaenderte Register):
    python3 dimplex_scan.py --diff scan_a.csv scan_b.csv
  Wert aus der App in einem Scan suchen (alle Skalierungen, +/- Toleranz):
    python3 dimplex_scan.py --find scan.csv 24.3 --tol 0.3
"""

import argparse
import csv
import socket
import struct
import sys
import time
from datetime import datetime

# (Funktionscode, Start, Ende exklusiv)
DEFAULT_RANGES = [
    (4, 0, 2000),      # Input-Register: Fuehler/Analogwerte (1301 = Aussentemp.)
    (3, 0, 400),       # Holding: Doku-Bereich (Status 103-106, Laufzeiten 72-78)
    (3, 5000, 5400),   # Holding: Einstellungen, Leistungen 5168/5170, Waermemengen
]

FC_NAME = {1: "coil", 2: "discrete", 3: "holding", 4: "input"}
ALLOWED_FC = (1, 2, 3, 4)
BIT_FC = (1, 2)


class ModbusReadOnlyClient:
    """Minimaler Modbus-TCP-Client, der ausschliesslich lesen kann (FC01-04)."""

    def __init__(self, host, port, unit, timeout):
        self.host = host
        self.port = port
        self.unit = unit
        self.timeout = timeout
        self.sock = None
        self.tid = 0

    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Verbindung vom Geraet geschlossen")
            buf += chunk
        return buf

    def read(self, fc, address, count):
        """
        Rueckgabe:
          ("ok",  [uint16, ...])   Werte gelesen
          ("exc", code)            Modbus-Exception (Register existiert nicht o.ae.)
          ("err", text)            Kommunikationsfehler (Timeout, Abbruch ...)
        """
        if fc not in ALLOWED_FC:
            raise ValueError("Nur FC01-04 erlaubt - dieses Skript liest nur.")
        try:
            if self.sock is None:
                self.connect()
            self.tid = (self.tid + 1) % 0x10000
            pdu = struct.pack(">BHH", fc, address, count)
            mbap = struct.pack(">HHHB", self.tid, 0, len(pdu) + 1, self.unit)
            self.sock.sendall(mbap + pdu)

            header = self._recv_exact(7)
            tid, _pid, length, _unit = struct.unpack(">HHHB", header)
            body = self._recv_exact(length - 1)
            if tid != self.tid:
                # Verspaetete Antwort einer frueheren Anfrage -> sauber neu verbinden
                self.close()
                return ("err", "Transaction-ID passt nicht")

            rfc = body[0]
            if rfc == (fc | 0x80):
                return ("exc", body[1])
            if rfc != fc:
                self.close()
                return ("err", "Unerwarteter Funktionscode %d" % rfc)

            bytecount = body[1]
            data = body[2:2 + bytecount]
            if fc in BIT_FC:
                if len(data) != (count + 7) // 8:
                    return ("err", "Unvollstaendige Antwort")
                return ("ok", [(data[i // 8] >> (i % 8)) & 1 for i in range(count)])
            if len(data) != 2 * count:
                return ("err", "Unvollstaendige Antwort")
            return ("ok", list(struct.unpack(">%dH" % count, data)))
        except (socket.timeout, OSError, ConnectionError) as exc:
            self.close()
            return ("err", str(exc) or exc.__class__.__name__)


def to_int16(value):
    return value - 0x10000 if value >= 0x8000 else value


class Scanner:
    def __init__(self, client, block, pause, max_errors):
        self.client = client
        self.block = block
        self.pause = pause
        self.max_errors = max_errors
        self.consecutive_errors = 0
        self.results = {}          # (fc, addr) -> uint16
        self.stats = {"requests": 0, "exceptions": 0, "errors": 0}

    def _read(self, fc, addr, count):
        """Liest mit einem Wiederholungsversuch bei Kommunikationsfehlern."""
        for attempt in range(2):
            time.sleep(self.pause)
            self.stats["requests"] += 1
            status, payload = self.client.read(fc, addr, count)
            if status != "err":
                self.consecutive_errors = 0
                if status == "exc":
                    self.stats["exceptions"] += 1
                return status, payload
            self.stats["errors"] += 1
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.max_errors:
                raise RuntimeError(
                    "Zu viele Kommunikationsfehler in Folge (%d) - Abbruch zum Schutz "
                    "des WPM. Letzter Fehler: %s" % (self.consecutive_errors, payload)
                )
            time.sleep(1.0 + attempt)  # kurz durchatmen, dann neu verbinden
        return status, payload

    def scan_range(self, fc, start, end):
        addr = start
        total = end - start
        while addr < end:
            count = min(self.block, end - addr)
            status, payload = self._read(fc, addr, count)
            if status == "ok":
                for i, value in enumerate(payload):
                    self.results[(fc, addr + i)] = value
            elif status == "exc":
                # Block enthaelt nicht vorhandene Register -> einzeln nachlesen
                for single in range(addr, addr + count):
                    s_status, s_payload = self._read(fc, single, 1)
                    if s_status == "ok":
                        self.results[(fc, single)] = s_payload[0]
            # status "err" nach Wiederholung: Block ueberspringen
            addr += count
            done = addr - start
            if not sys.stderr.isatty() and addr < end:
                continue
            sys.stderr.write(
                "\r  %s %5d-%5d: %3d%%  (%d Register gefunden)   "
                % (FC_NAME[fc], start, end - 1, done * 100 // total, len(self.results))
            )
            sys.stderr.flush()
        sys.stderr.write("\n")


def write_csv(path, results):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["fc", "typ", "adresse", "uint16", "int16", "int16_x0.1", "int16_x0.01"])
        for (fc, addr) in sorted(results):
            raw = results[(fc, addr)]
            signed = to_int16(raw)
            writer.writerow([fc, FC_NAME[fc], addr, raw, signed,
                             "%.1f" % (signed / 10), "%.2f" % (signed / 100)])


def read_csv(path):
    data = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            data[(int(row["fc"]), int(row["adresse"]))] = int(row["uint16"])
    return data


def run_diff(path_a, path_b):
    a = read_csv(path_a)
    b = read_csv(path_b)
    common = sorted(set(a) & set(b))
    print("typ;adresse;A_int16;B_int16;A_x0.1;B_x0.1;delta_x0.1")
    changed = 0
    for key in common:
        sa, sb = to_int16(a[key]), to_int16(b[key])
        if sa == sb:
            continue
        changed += 1
        print("%s;%d;%d;%d;%.1f;%.1f;%+.1f" % (FC_NAME[key[0]], key[1], sa, sb,
                                              sa / 10, sb / 10, (sb - sa) / 10))
    only = len(set(a) ^ set(b))
    sys.stderr.write("%d von %d gemeinsamen Registern unterscheiden sich"
                     % (changed, len(common)))
    sys.stderr.write((" (%d nur in einem der Scans, ignoriert).\n" % only) if only else ".\n")


def run_find(path, target, tol):
    data = read_csv(path)
    scales = (("x1", 1.0), ("x0.1", 0.1), ("x0.01", 0.01))
    hits = []
    for (fc, addr), raw in sorted(data.items()):
        signed = to_int16(raw)
        for label, factor in scales:
            value = signed * factor
            if abs(value - target) <= tol:
                hits.append((abs(value - target), fc, addr, signed, label, value))
    hits.sort()
    print("typ;adresse;roh_int16;skalierung;wert;abweichung")
    for diff, fc, addr, signed, label, value in hits:
        print("%s;%d;%d;%s;%.2f;%.2f" % (FC_NAME[fc], addr, signed, label, value, diff))
    sys.stderr.write("%d Treffer fuer %.2f +/- %.2f\n" % (len(hits), target, tol))


def parse_range(text):
    try:
        fc, start, end = (int(part) for part in text.split(":"))
    except ValueError:
        raise argparse.ArgumentTypeError("Format FC:Start:Ende, z.B. 4:1250:1400")
    if fc not in ALLOWED_FC:
        raise argparse.ArgumentTypeError(
            "Nur FC 1 (coil), 2 (discrete), 3 (holding) oder 4 (input) erlaubt")
    if not 0 <= start < end <= 65536:
        raise argparse.ArgumentTypeError("Ungueltiger Bereich")
    return (fc, start, end)


def main():
    parser = argparse.ArgumentParser(description="Dimplex Modbus-TCP Register-Scan (nur lesen)")
    parser.add_argument("host", nargs="?", help="IP der Waermepumpe, z.B. 192.168.x.x")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit", type=int, default=1, help="Slave-/Device-Adresse (Standard 1)")
    parser.add_argument("--range", dest="ranges", action="append", type=parse_range,
                        help="FC:Start:Ende (Ende exklusiv), mehrfach moeglich")
    parser.add_argument("--block", type=int, default=20, help="Register pro Anfrage (Standard 20)")
    parser.add_argument("--pause", type=float, default=0.1, help="Pause zwischen Anfragen in s (Standard 0.1)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket-Timeout in s")
    parser.add_argument("--max-errors", type=int, default=10)
    parser.add_argument("--label", default="scan", help="Kennung im Dateinamen, z.B. wp_laeuft")
    parser.add_argument("--diff", nargs=2, metavar=("A.csv", "B.csv"),
                        help="Zwei Scan-Dateien vergleichen statt zu scannen")
    parser.add_argument("--find", nargs=2, metavar=("SCAN.csv", "WERT"),
                        help="Wert (z.B. aus der Dimplex-App) in einer Scan-Datei suchen")
    parser.add_argument("--tol", type=float, default=0.3,
                        help="Toleranz fuer --find (Standard 0.3)")
    args = parser.parse_args()

    if args.diff:
        run_diff(*args.diff)
        return 0
    if args.find:
        try:
            target = float(args.find[1].replace(",", "."))
        except ValueError:
            parser.error("--find: WERT muss eine Zahl sein, z.B. 24.3")
        run_find(args.find[0], target, args.tol)
        return 0
    if not args.host:
        parser.error("IP der Waermepumpe fehlt (oder --diff verwenden)")
    if not 1 <= args.block <= 125:
        parser.error("--block muss zwischen 1 und 125 liegen")

    ranges = args.ranges or DEFAULT_RANGES
    client = ModbusReadOnlyClient(args.host, args.port, args.unit, args.timeout)
    scanner = Scanner(client, args.block, args.pause, args.max_errors)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = "dimplex_scan_%s_%s.csv" % (args.label, stamp)
    sys.stderr.write("Scanne %s:%d (Unit %d) - nur lesend ...\n" % (args.host, args.port, args.unit))
    started = time.time()
    try:
        for fc, start, end in ranges:
            scanner.scan_range(fc, start, end)
    except RuntimeError as exc:
        sys.stderr.write("\n%s\n" % exc)
    except KeyboardInterrupt:
        sys.stderr.write("\nAbgebrochen - bisherige Ergebnisse werden gespeichert.\n")
    finally:
        client.close()

    write_csv(out_path, scanner.results)
    nonzero = sum(1 for v in scanner.results.values() if v != 0)
    sys.stderr.write(
        "Fertig in %.0f s: %d Register lesbar, davon %d ungleich 0. "
        "Anfragen: %d, Exceptions: %d, Fehler: %d\n"
        "Datei: %s\n" % (time.time() - started, len(scanner.results), nonzero,
                         scanner.stats["requests"], scanner.stats["exceptions"],
                         scanner.stats["errors"], out_path)
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Ausgabe in z.B. "| head" umgeleitet und vorzeitig geschlossen
        sys.stderr.close()
        sys.exit(0)
