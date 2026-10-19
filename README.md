# FRC Log Analyzer

A Python tool for FRC teams that reads `.wpilog` match logs from the roboRIO and reports motor temperatures, voltages, currents and radio dropouts. It was built for Team 687 Nerd Herd so that pit crew can check the robot's health between matches.

## What it does

- **Max values.** It reports the peak temperature and voltage for each subsystem.
- **Full data.** It prints every reading, sorted by timestamp.
- **Radio status.** It shows each time the robot radio connected or disconnected.
- **Filters.** You can narrow the output to `/Robot/SuperSystem`, `/Robot/SwerveDrive`, `/Robot/RadioStatus` or a single subsystem.

## Usage

1. Install Python 3 from python.org. On Windows, check **"Add Python to PATH"** during installation.
2. Run `python FilterTemp.py` and drag your `.wpilog` file into the terminal.

## Credits

`datalog.py` is the `.wpilog` reader from [WPILib](https://github.com/wpilibsuite/allwpilib). Copyright (c) FIRST and other WPILib contributors, and used under the WPILib BSD license. Everything else in this repo was written for Team 687.
