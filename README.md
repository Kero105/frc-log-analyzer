# FRC Log Analyzer

A Python tool for FRC teams that reads `.wpilog` match logs from the roboRIO and reports motor temperatures, voltages, currents, radio dropouts and brownouts. It was built for Team 687 Nerd Herd so that pit crew can check the robot's health between matches.

## What it does

- **Brownout detection.** It finds every point where battery voltage dropped below the brownout threshold (6.8 V by default) and reports how long each drop lasted and how low the voltage went. It also lists the motors drawing the most current at that moment, which shows what caused the drop.
- **Max values.** It reports the peak temperature, voltage and current for each subsystem.
- **Full data.** It prints every reading, sorted by timestamp.
- **Radio status.** It shows each time the robot radio connected or disconnected.
- **CSV export.** It saves readings to a spreadsheet so you can graph them.
- **Filters.** You can narrow the output to `/Robot/SuperSystem`, `/Robot/SwerveDrive`, `/Robot/RadioStatus` or a single subsystem.

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
python FilterTemp.py match.wpilog --brownouts --threshold 6.75
python FilterTemp.py match.wpilog --csv match_data.csv
```

Example brownout report:

```
BROWNOUTS (threshold 6.80V)
  #1  t=1.000s to 1.200s (0.200s)  min 6.40V  [/Robot/SuperSystem/PowerDistribution/BatteryVoltage]
        /Robot/SuperSystem/Shooter/MotorCurrent: 90.0A
  Total: 1 brownout event(s)
```

## How it works

A `.wpilog` file is a binary log. Every value the robot records is stored as a record with an entry ID, a timestamp in microseconds and raw bytes. The analyzer:

1. reads the file once, using WPILib's `datalog.py` reader to split it into records;
2. matches each entry ID to its name and type, then decodes the values (`double`, `float`, `int64`, `boolean`);
3. sorts each entry into a category (temperature, voltage, current, radio) based on its name;
4. scans the battery voltage for drops below the threshold and groups consecutive low readings into brownout events.

## Tests

The tests build small synthetic `.wpilog` files with known values, including a planned brownout, and check that the analyzer reports them correctly.

```
pip install pytest
pytest
```

## Credits

`datalog.py` is the `.wpilog` reader from [WPILib](https://github.com/wpilibsuite/allwpilib). Copyright (c) FIRST and other WPILib contributors, and used under the WPILib BSD license. Everything else in this repo was written for Team 687.
