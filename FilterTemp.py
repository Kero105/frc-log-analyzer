# FRC Log Analyzer
# Reads a .wpilog file from Systemcore (2027+) or the roboRIO and reports motor temperatures,
# voltages, currents, radio status, and brownouts.
#
# Interactive mode (menus):
#   python FilterTemp.py                 then drag your .wpilog file in
#   python FilterTemp.py match.wpilog
#
# Command-line mode (no menus):
#   python FilterTemp.py match.wpilog --brownouts
#   python FilterTemp.py match.wpilog --max --filter /Robot/SuperSystem
#   python FilterTemp.py match.wpilog --csv match_data.csv
#   python FilterTemp.py old_match.wpilog --brownouts --platform roborio2
#
# On Windows you can also drag a .wpilog file onto Temp.bat.

import argparse
import csv
import sys

from datalog import DataLogReader

ALLOWED_PATHS = {"/Robot/RadioStatus", "/Robot/SuperSystem", "/Robot/SwerveDrive"}

# Brownout behavior for each FRC controller. Outputs turn off when the battery
# drops below "brownout" and stay off until it climbs back above "restore".
#   Systemcore (2027+): 6.3 V / 7.5 V   (configurable; values may change)
#   roboRIO 2:          6.75 V / 7.5 V  (6.75 V is the default; teams can change it)
#   roboRIO 1:          6.3 V / 7.5 V   (fixed)
PLATFORMS = {
    "systemcore": {"brownout": 6.3, "restore": 7.5},
    "roborio2": {"brownout": 6.75, "restore": 7.5},
    "roborio1": {"brownout": 6.3, "restore": 7.5},
}
DEFAULT_PLATFORM = "systemcore"
DEFAULT_BROWNOUT_VOLTS = PLATFORMS[DEFAULT_PLATFORM]["brownout"]
DEFAULT_RESTORE_VOLTS = PLATFORMS[DEFAULT_PLATFORM]["restore"]


# ---------- Reading the log (done once) ----------

class LogData:
    """Everything we need from one .wpilog file, read in a single pass."""

    def __init__(self):
        self.names = []    # every entry name, in the order it appeared
        self.series = {}   # entry name -> list of (timestamp_s, value)


def load_log(log_path):
    with open(log_path, "rb") as f:
        reader = DataLogReader(f.read())
    if not reader:
        raise ValueError(f"{log_path} is not a valid .wpilog file")

    log = LogData()
    entries = {}
    for record in reader:
        if record.isStart():
            data = record.getStartData()
            entries[data.entry] = (data.name, data.type)
            log.names.append(data.name)
            if data.type in ("double", "float", "int64", "boolean"):
                log.series.setdefault(data.name, [])
        elif not record.isControl():
            if record.entry not in entries:
                continue
            name, entry_type = entries[record.entry]
            timestamp_s = record.timestamp / 1_000_000
            try:
                if entry_type == "double":
                    value = record.getDouble()
                elif entry_type == "float":
                    value = record.getFloat()
                elif entry_type == "int64":
                    value = record.getInteger()
                elif entry_type == "boolean":
                    value = record.getBoolean()
                else:
                    continue
            except TypeError as e:
                print(f"  Could not read {name}: {e}")
                continue
            log.series[name].append((timestamp_s, value))
    return log


# ---------- Sorting entries into categories ----------

def is_skipped(name):
    return name.startswith("NT:") or name.startswith("/DS") or name.startswith("DS")


def is_radio(name):
    return "/Robot/RadioStatus" in name and "connected" in name.lower()


def is_temp(name):
    lower = name.lower()
    return "temp" in lower or "celsius" in lower


def is_current(name):
    lower = name.lower()
    return "current" in lower or "amps" in lower


def is_voltage(name):
    lower = name.lower()
    return not is_current(name) and ("voltage" in lower or "volt" in lower
                                     or "battery" in lower or "rail" in lower)


def is_battery_voltage(name):
    lower = name.lower()
    return "battery" in lower and "volt" in lower


def is_brownout_flag(name):
    lower = name.lower()
    return "brownout" in lower or "brownedout" in lower


def device_of(name):
    return name.rsplit("/", 1)[0]


def get_top_level_paths(log):
    paths = set()
    for name in log.names:
        if is_skipped(name):
            continue
        parts = name.strip("/").split("/")
        if len(parts) >= 2:
            path = "/" + "/".join(parts[:2])
            if path in ALLOWED_PATHS:
                paths.add(path)
    return sorted(paths)


def get_subsystems(log):
    subsystems = set()
    for name in log.names:
        if is_skipped(name) or "/Robot/SuperSystem" not in name:
            continue
        parts = name.strip("/").split("/")
        if len(parts) >= 3:
            subsystems.add("/" + "/".join(parts[:3]))
    return sorted(subsystems)


def select(log, filters, test):
    """Return {name: readings} for entries that pass the filter and the test."""
    selected = {}
    for name, readings in log.series.items():
        if is_skipped(name) or not readings:
            continue
        if filters and not any(f in name for f in filters):
            continue
        if test(name):
            selected[name] = readings
    return selected


# ---------- Reports ----------

def print_radio(log, filters):
    radio = select(log, filters, is_radio)
    if not radio:
        return
    print("RADIO STATUS")
    for name, readings in radio.items():
        for timestamp_s, value in readings:
            print(f"  t={timestamp_s:.3f}s  {name} = {'Connected' if value else 'Disconnected'}")


def print_max(log, filters):
    temps = select(log, filters, lambda n: is_temp(n) and not is_radio(n))
    volts = select(log, filters, lambda n: is_voltage(n) and not is_radio(n))
    amps = select(log, filters, lambda n: is_current(n) and not is_radio(n))
    devices = sorted({device_of(n) for n in list(temps) + list(volts) + list(amps)})
    if not devices:
        return
    print("MAX VALUES")
    for device in devices:
        parts = []
        for label, group, unit in (("temp", temps, "°C"), ("voltage", volts, "V"), ("current", amps, "A")):
            values = [v for n, r in group.items() if device_of(n) == device for _, v in r]
            if values:
                parts.append(f"max {label}: {max(values):.2f}{unit}")
        print(f"  {device}  " + "  ".join(parts))


def print_full(log, filters):
    temps = select(log, filters, lambda n: is_temp(n) and not is_radio(n))
    volts = select(log, filters, lambda n: is_voltage(n) and not is_radio(n))
    amps = select(log, filters, lambda n: is_current(n) and not is_radio(n))
    devices = sorted({device_of(n) for n in list(temps) + list(volts) + list(amps)})
    if not devices:
        return
    print("FULL DATA")
    for device in devices:
        print(f"\n{device}")
        rows = {}
        for label, group, unit in (("temp", temps, "°C"), ("voltage", volts, "V"), ("current", amps, "A")):
            for name, readings in group.items():
                if device_of(name) != device:
                    continue
                for timestamp_s, value in readings:
                    rows.setdefault(timestamp_s, {})[label] = f"{label}: {value:.2f}{unit}"
        for timestamp_s in sorted(rows):
            cells = rows[timestamp_s]
            text = "  ".join(cells[k] for k in ("temp", "voltage", "current") if k in cells)
            print(f"  t={timestamp_s:.3f}s  {text}")


# ---------- Brownout detection ----------

def detect_brownouts(log, threshold=DEFAULT_BROWNOUT_VOLTS, restore=DEFAULT_RESTORE_VOLTS):
    """Find every stretch of time the robot browned out.

    Uses two sources:
      1. Any boolean entry named like "BrownedOut" (logged by the controller).
      2. Battery voltage dropping below the threshold. The event lasts until
         voltage climbs back above the restore level, because that is when
         the controller turns the motors back on.
    For each event, also reports the highest motor currents at that moment,
    so you can see what was drawing power when the voltage dropped.
    """
    events = []

    for name, readings in log.series.items():
        if is_brownout_flag(name):
            events.extend(_events_from_flag(name, readings))
        elif is_battery_voltage(name) and not is_current(name):
            events.extend(_events_from_voltage(name, readings, threshold, restore))

    currents = {n: r for n, r in log.series.items() if is_current(n) and not is_skipped(n)}
    for event in events:
        event["top_currents"] = _top_currents(currents, event["start"], event["end"])
    return sorted(events, key=lambda e: e["start"])


def _events_from_voltage(name, readings, threshold, restore):
    events, current = [], None
    for timestamp_s, volts in sorted(readings):
        if current is None:
            if volts < threshold:
                current = {"source": name, "start": timestamp_s, "end": timestamp_s, "min_volts": volts}
        elif volts > restore:
            current["end"] = timestamp_s          # motors turn back on here
            events.append(current)
            current = None
        else:
            current["end"] = timestamp_s          # still browned out
            current["min_volts"] = min(current["min_volts"], volts)
    if current is not None:
        events.append(current)
    return events


def _events_from_flag(name, readings):
    events, start = [], None
    for timestamp_s, value in sorted(readings):
        if value and start is None:
            start = timestamp_s
        elif not value and start is not None:
            events.append({"source": name, "start": start, "end": timestamp_s, "min_volts": None})
            start = None
    if start is not None:
        last = max(t for t, _ in readings)
        events.append({"source": name, "start": start, "end": last, "min_volts": None})
    return events


def _top_currents(currents, start, end, count=3):
    """Highest current per channel during [start, end], or the last reading before it."""
    peaks = []
    for name, readings in currents.items():
        during = [v for t, v in readings if start <= t <= end]
        if not during:
            before = [v for t, v in readings if t <= start]
            during = before[-1:]
        if during:
            peaks.append((name, max(during)))
    return sorted(peaks, key=lambda p: p[1], reverse=True)[:count]


def print_brownouts(log, threshold=DEFAULT_BROWNOUT_VOLTS, restore=DEFAULT_RESTORE_VOLTS):
    battery = [n for n in log.series if is_battery_voltage(n) and log.series[n]]
    flags = [n for n in log.series if is_brownout_flag(n) and log.series[n]]
    print(f"BROWNOUTS (below {threshold:.2f}V, restored above {restore:.2f}V)")
    if not battery and not flags:
        print("  No battery voltage or brownout entries found in this log.")
        return
    events = detect_brownouts(log, threshold, restore)
    if not events:
        lowest = min((v for n in battery for _, v in log.series[n]), default=None)
        if lowest is not None:
            print(f"  None. Lowest battery voltage: {lowest:.2f}V")
        else:
            print("  None.")
        return
    for i, event in enumerate(events, 1):
        length = event["end"] - event["start"]
        volts = f"  min {event['min_volts']:.2f}V" if event["min_volts"] is not None else ""
        print(f"  #{i}  t={event['start']:.3f}s to {event['end']:.3f}s ({length:.3f}s){volts}  [{event['source']}]")
        for name, amps in event["top_currents"]:
            print(f"        {name}: {amps:.1f}A")
    print(f"  Total: {len(events)} brownout event(s)")


# ---------- CSV export ----------

def export_csv(log, filters, csv_path):
    """Write every temperature, voltage, and current reading to a CSV file."""
    rows = 0
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "entry", "kind", "value"])
        for name, readings in sorted(log.series.items()):
            if is_skipped(name) or (filters and not any(x in name for x in filters)):
                continue
            if is_temp(name):
                kind = "temp_c"
            elif is_current(name):
                kind = "current_a"
            elif is_voltage(name):
                kind = "voltage_v"
            else:
                continue
            for timestamp_s, value in readings:
                writer.writerow([f"{timestamp_s:.6f}", name, kind, value])
                rows += 1
    print(f"Wrote {rows} readings to {csv_path}")


# ---------- Interactive menus ----------

def interactive(log):
    paths = get_top_level_paths(log)
    subsystems = get_subsystems(log)

    while True:
        print("\nAvailable filters:")
        print("  0  No filter (show everything)")
        for i, path in enumerate(paths, 1):
            print(f"  {i}  {path}")
        print("  b  Brownout report")
        print("  q  Quit")

        raw = input("\nEnter numbers separated by commas: ").strip().lower()
        if raw == "q":
            break
        if raw == "b":
            print("\nWhich controller recorded this log?")
            print("  1  Systemcore (2027+)")
            print("  2  roboRIO 2")
            print("  3  roboRIO 1")
            choice = input("\nEnter number (Enter = 1): ").strip()
            platform = {"2": "roborio2", "3": "roborio1"}.get(choice, "systemcore")
            levels = PLATFORMS[platform]
            print_brownouts(log, levels["brownout"], levels["restore"])
            continue

        numbers = [int(s.strip()) for s in raw.split(",") if s.strip().isdigit()]
        if 0 in numbers or not numbers:
            filters = []
        else:
            filters = [paths[n - 1] for n in numbers if 1 <= n <= len(paths)]

        is_supersystem = any("/Robot/SuperSystem" in f for f in filters) or not filters
        radio_only = all("/Robot/RadioStatus" in f for f in filters) if filters else False

        if radio_only:
            print_radio(log, filters)
            continue

        while True:
            print("\nWhat do you want to see?")
            print("  1  Max values only")
            print("  2  Full data only")
            print("  3  Both")
            print("  b  Back")
            view_choice = input("\nEnter number: ").strip().lower()
            if view_choice == "b":
                break
            if view_choice not in ("1", "2", "3"):
                continue

            final_filters = list(filters)
            if is_supersystem:
                print("\nSubsystem filter:")
                print("  0  All subsystems")
                for i, sub in enumerate(subsystems, 1):
                    print(f"  {i}  {sub}")
                print("  b  Back")
                sub_raw = input("\nEnter number: ").strip().lower()
                if sub_raw == "b":
                    continue
                if sub_raw.isdigit() and 1 <= int(sub_raw) <= len(subsystems):
                    final_filters = [subsystems[int(sub_raw) - 1]]

            print_radio(log, final_filters)
            if view_choice in ("1", "3"):
                print_max(log, final_filters)
            if view_choice in ("2", "3"):
                print_full(log, final_filters)
            break


# ---------- Entry point ----------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze an FRC .wpilog file.")
    parser.add_argument("log", nargs="?", help="path to the .wpilog file")
    parser.add_argument("--brownouts", action="store_true", help="report brownout events")
    parser.add_argument("--platform", choices=sorted(PLATFORMS), default=DEFAULT_PLATFORM,
                        help=f"controller the log came from (default {DEFAULT_PLATFORM})")
    parser.add_argument("--threshold", type=float,
                        help="custom brownout voltage (overrides --platform), e.g. if your code changed it")
    parser.add_argument("--max", action="store_true", help="print max temp/voltage/current per device")
    parser.add_argument("--full", action="store_true", help="print every reading")
    parser.add_argument("--radio", action="store_true", help="print radio connection changes")
    parser.add_argument("--filter", action="append", default=[], help="only entries containing this path (repeatable)")
    parser.add_argument("--csv", metavar="FILE", help="export readings to a CSV file")
    args = parser.parse_args(argv)

    log_path = args.log or input("Drag your .wpilog file here and press Enter: ")
    log_path = log_path.strip().strip('"').strip("'")
    try:
        log = load_log(log_path)
    except (OSError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    batch = args.brownouts or args.max or args.full or args.radio or args.csv
    if not batch:
        interactive(log)
        return 0

    if args.radio:
        print_radio(log, args.filter)
    if args.max:
        print_max(log, args.filter)
    if args.full:
        print_full(log, args.filter)
    if args.brownouts:
        levels = PLATFORMS[args.platform]
        threshold = args.threshold if args.threshold is not None else levels["brownout"]
        print_brownouts(log, threshold, levels["restore"])
    if args.csv:
        export_csv(log, args.filter, args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
