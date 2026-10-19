# Download Python 3 from python.org and make sure to check "Add Python to PATH" during installation.
# Move the TempLogging folder to your desktop and open a terminal.
# Run this script by enetering: "cd ~/Desktop/TempLogging" without the quotes into the terminal. 
# Windows: Then run: "python FilterTemp.py" without the quotes.
# Mac: Then run: "python3 FilterTemp.py" without the quotes.
# Then drag your .wpilog file into the terminal and press enter.

from datalog import DataLogReader

def get_top_level_paths(log_path):
    with open(log_path, "rb") as f:
        reader = DataLogReader(f.read())
    paths = set()
    allowed = {"/Robot/RadioStatus", "/Robot/SuperSystem", "/Robot/SwerveDrive"}
    for record in reader:
        if record.isStart():
            data = record.getStartData()
            if data.name.startswith("NT:"):
                continue
            if data.name.startswith("/DS") or data.name.startswith("DS"):
                continue
            parts = data.name.strip("/").split("/")
            if len(parts) >= 2:
                path = "/" + "/".join(parts[:2])
                if path in allowed:
                    paths.add(path)
    return sorted(paths)

def get_subsystems(log_path):
    with open(log_path, "rb") as f:
        reader = DataLogReader(f.read())
    subsystems = set()
    for record in reader:
        if record.isStart():
            data = record.getStartData()
            if data.name.startswith("NT:"):
                continue
            if "/Robot/SuperSystem" not in data.name:
                continue
            parts = data.name.strip("/").split("/")
            if len(parts) >= 3:
                subsystems.add("/" + "/".join(parts[:3]))
    return sorted(subsystems)

def read_log(log_path, filters, show_max, show_full):
    with open(log_path, "rb") as f:
        reader = DataLogReader(f.read())
    entries = {}
    temp_entries = {}
    voltage_entries = {}
    bool_entries = {}
    temp_data = {}
    voltage_data = {}
    bool_data = {}

    for record in reader:
        if record.isStart():
            data = record.getStartData()
            entries[data.entry] = {"name": data.name, "type": data.type}
            name_lower = data.name.lower()

            if data.name.startswith("NT:"):
                continue
            if data.name.startswith("/DS") or data.name.startswith("DS"):
                continue
            if filters and not any(f in data.name for f in filters):
                continue

            if "/Robot/RadioStatus" in data.name and "connected" in name_lower:
                bool_entries[data.entry] = data.name
                bool_data[data.name] = {}
                continue

            if "temp" in name_lower or "temperature" in name_lower or "celsius" in name_lower:
                temp_entries[data.entry] = data.name
                temp_data[data.name] = {}

            if "voltage" in name_lower or "battery" in name_lower or "volt" in name_lower or "current" in name_lower or "rail" in name_lower:
                voltage_entries[data.entry] = data.name
                voltage_data[data.name] = {}

        elif not record.isControl():
            entry_id = record.entry
            timestamp_s = record.timestamp / 1_000_000
            entry_type = entries.get(entry_id, {}).get("type")

            if entry_id in bool_entries:
                name = bool_entries[entry_id]
                try:
                    value = record.getBoolean()
                    bool_data[name][timestamp_s] = value
                except Exception as e:
                    print(f"  Could not read {name}: {e}")

            if entry_id in temp_entries:
                name = temp_entries[entry_id]
                try:
                    if entry_type == "double":
                        value = record.getDouble()
                    elif entry_type == "float":
                        value = record.getFloat()
                    else:
                        continue
                    temp_data[name][timestamp_s] = value
                except Exception as e:
                    print(f"  Could not read {name}: {e}")

            if entry_id in voltage_entries:
                name = voltage_entries[entry_id]
                try:
                    if entry_type == "double":
                        value = record.getDouble()
                    elif entry_type == "float":
                        value = record.getFloat()
                    else:
                        continue
                    voltage_data[name][timestamp_s] = value
                except Exception as e:
                    print(f"  Could not read {name}: {e}")

    all_devices = set()
    for name in temp_data:
        all_devices.add(name.rsplit("/", 1)[0])
    for name in voltage_data:
        all_devices.add(name.rsplit("/", 1)[0])
    for name in bool_data:
        all_devices.add(name.rsplit("/", 1)[0])

    if any(name for name in bool_data):
        print("RADIO STATUS")
        for name, readings in bool_data.items():
            for timestamp_s in sorted(readings):
                value = readings[timestamp_s]
                print(f"  t={timestamp_s:.3f}s  {name} = {'Connected' if value else 'Disconnected'}")

    if show_max and (any(name for name in temp_data) or any(name for name in voltage_data)):
        print("MAX VALUES")
        for device in sorted(all_devices):
            if any(n for n in bool_data if n.rsplit("/", 1)[0] == device):
                continue
            device_temps = {name: readings for name, readings in temp_data.items() if name.rsplit("/", 1)[0] == device}
            device_volts = {name: readings for name, readings in voltage_data.items() if name.rsplit("/", 1)[0] == device}
            all_temp_values = [v for readings in device_temps.values() for v in readings.values()]
            all_volt_values = [v for readings in device_volts.values() for v in readings.values()]
            if all_temp_values and all_volt_values:
                print(f"  {device}  max temp: {max(all_temp_values):.2f}°C  max voltage: {max(all_volt_values):.2f}V")
            elif all_temp_values:
                print(f"  {device}  max temp: {max(all_temp_values):.2f}°C")
            elif all_volt_values:
                print(f"  {device}  max voltage: {max(all_volt_values):.2f}V")

    if show_full and (any(name for name in temp_data) or any(name for name in voltage_data)):
        print("FULL DATA")
        for device in sorted(all_devices):
            if any(n for n in bool_data if n.rsplit("/", 1)[0] == device):
                continue
            print(f"\n{device}")
            device_temps = {name: readings for name, readings in temp_data.items() if name.rsplit("/", 1)[0] == device}
            device_volts = {name: readings for name, readings in voltage_data.items() if name.rsplit("/", 1)[0] == device}
            all_timestamps = set()
            for readings in device_temps.values():
                all_timestamps.update(readings.keys())
            for readings in device_volts.values():
                all_timestamps.update(readings.keys())
            for timestamp_s in sorted(all_timestamps):
                temp_val = None
                volt_val = None
                for name, readings in device_temps.items():
                    if timestamp_s in readings:
                        temp_val = readings[timestamp_s]
                for name, readings in device_volts.items():
                    if timestamp_s in readings:
                        volt_val = readings[timestamp_s]
                if temp_val is not None and volt_val is not None:
                    print(f"  t={timestamp_s:.3f}s  temp: {temp_val:.2f}°C  voltage: {volt_val:.2f}V")
                elif temp_val is not None:
                    print(f"  t={timestamp_s:.3f}s  temp: {temp_val:.2f}°C")
                elif volt_val is not None:
                    print(f"  t={timestamp_s:.3f}s  voltage: {volt_val:.2f}V")

if __name__ == "__main__":
    log_path = input("Drag your .wpilog file here and press Enter: ")
    log_path = log_path.strip().strip('"')

    paths = get_top_level_paths(log_path)
    subsystems = get_subsystems(log_path)

    while True:
        print("\nAvailable filters:")
        print("  0  No filter (show everything)")
        for i, path in enumerate(paths, 1):
            print(f"  {i}  {path}")
        print("  q  Quit")

        raw = input("\nEnter numbers separated by commas: ")
        if raw.strip().lower() == "q":
            break

        selected = [s.strip() for s in raw.split(",") if s.strip().isdigit()]
        numbers = [int(s) for s in selected]

        if 0 in numbers or not numbers:
            filters = []
        else:
            filters = [paths[n - 1] for n in numbers if 1 <= n <= len(paths)]

        is_supersystem = any("/Robot/SuperSystem" in f for f in filters) or not filters
        is_radio = all("/Robot/RadioStatus" in f for f in filters) if filters else False

        if not is_radio:
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

                show_max = view_choice in ("1", "3")
                show_full = view_choice in ("2", "3")

                if is_supersystem:
                    while True:
                        print("\nSubsystem filter:")
                        print("  0  All subsystems")
                        for i, sub in enumerate(subsystems, 1):
                            print(f"  {i}  {sub}")
                        print("  b  Back")
                        sub_raw = input("\nEnter number: ").strip().lower()

                        if sub_raw == "b":
                            break

                        final_filters = list(filters)
                        if sub_raw.isdigit() and int(sub_raw) != 0:
                            idx = int(sub_raw)
                            if 1 <= idx <= len(subsystems):
                                final_filters = [subsystems[idx - 1]]

                        read_log(log_path, final_filters, show_max, show_full)
                        break
                else:
                    read_log(log_path, filters, show_max, show_full)
                    break
        else:
            read_log(log_path, filters, False, False)