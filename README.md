# FRC Log Analyzer

A Python tool for FRC teams that reads `.wpilog` match logs from **Systemcore** (the 2027+ control system) or the **roboRIO** and reports motor temperatures, voltages, currents, radio dropouts and brownouts. It was built for Team 687 Nerd Herd so that pit crew can check the robot's health between matches.

## What it does

- **Brownout detection.** It finds every point where battery voltage dropped below the controller's brownout level and reports how long the motors stayed off and how low the voltage went. It also lists the motors drawing the most current at that moment, which shows what caused the drop.
- **Max values.** It reports the peak temperature, voltage and current for each subsystem.
- **Full data.** It prints every reading, sorted by timestamp.
- **Radio status.** It shows each time the robot radio connected or disconnected.
- **CSV export.** It saves readings to a spreadsheet so you can graph them.
- **Filters.** You can narrow the output to `/Robot/SuperSystem`, `/Robot/SwerveDrive`, `/Robot/RadioStatus` or a single subsystem.

## Supported controllers

| Controller | Outputs turn off below | Back on above | Flag |
| --- | --- | --- | --- |
| Systemcore (2027+, default) | 6.3 V | 7.5 V | `--platform systemcore` |
| roboRIO 2 | 6.75 V (default, configurable) | 7.5 V | `--platform roborio2` |
| roboRIO 1 | 6.3 V (fixed) | 7.5 V | `--platform roborio1` |

The controller keeps outputs off until voltage climbs back above 7.5 V, so a brownout event lasts until then, not just until voltage rises past the trip point. If your robot code changes the brownout level, pass it with `--threshold`. Systemcore's levels are still listed as in progress by FIRST, so check the latest docs each season.

The `.wpilog` format didn't change for 2027, and timestamps in the file are still in microseconds, so the same reader works for both controllers.

## Setup

1. Install Python 3 from python.org. On Windows, check **"Add Python to PATH"** during installation.
2. Download or clone this repo.

## Usage

**Interactive mode (menus):**

```
python FilterTemp.py match.wpilog
```

On Windows you can also drag a `.wpilog` file onto `Temp.bat`.

**Command-line mode:**

```
python FilterTemp.py match.wpilog --brownouts
python FilterTemp.py match.wpilog --max --filter /Robot/SuperSystem
python FilterTemp.py match.wpilog --brownouts --platform roborio2
python FilterTemp.py match.wpilog --brownouts --threshold 6.0
python FilterTemp.py match.wpilog --csv match_data.csv
```

Example brownout report:

```
BROWNOUTS (below 6.30V, restored above 7.50V)
  #1  t=1.000s to 1.300s (0.300s)  min 6.10V  [/Robot/SuperSystem/PowerDistribution/BatteryVoltage]
        /Robot/SuperSystem/Shooter/MotorCurrent: 90.0A
  Total: 1 brownout event(s)
```

## Getting logs off the robot

- **Systemcore:** logs are saved to the USB drive at `/u/logs` when one is plugged in. Otherwise they go to internal storage at `/home/systemcore/logs`. To download them, use AdvantageScope or WPILib's DataLogTool. In DataLogTool, connect to `robot.local` with username and password `systemcore`. Delete old logs regularly, because internal storage fills up.
- **roboRIO:** logs are saved to the USB drive, or to `/home/lvuser/logs`. To download them, use AdvantageScope or DataLogTool, and connect with username `lvuser`.

## How it works

A `.wpilog` file is a binary log. Every value the robot records is stored as a record with an entry ID, a timestamp in microseconds and raw bytes. The analyzer:

1. reads the file once, using WPILib's `datalog.py` reader to split it into records;
2. matches each entry ID to its name and type, then decodes the values (`double`, `float`, `int64`, `boolean`);
3. sorts each entry into a category (temperature, voltage, current, radio) based on its name;
4. scans the battery voltage for drops below the brownout level. Each event lasts until voltage climbs back above the restore level, because that's when the controller turns the motors back on.

## Tests

The tests build small synthetic `.wpilog` files with known values, including a planned brownout, and check that the analyzer reports them correctly.

```
pip install pytest
pytest
```

## Credits

`datalog.py` is the `.wpilog` reader from [WPILib](https://github.com/wpilibsuite/allwpilib). Copyright (c) FIRST and other WPILib contributors, and used under the WPILib BSD license. Everything else in this repo was written for Team 687.
