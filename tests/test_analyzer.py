"""
Tests for the FRC Log Analyzer, using small synthetic .wpilog files.

Run:
    pip install pytest
    pytest
"""

import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import FilterTemp as analyzer  # noqa: E402
from make_test_log import LogWriter  # noqa: E402

BATTERY = "/Robot/SuperSystem/PowerDistribution/BatteryVoltage"
SHOOTER_TEMP = "/Robot/SuperSystem/Shooter/MotorTemp"
SHOOTER_AMPS = "/Robot/SuperSystem/Shooter/MotorCurrent"
INTAKE_AMPS = "/Robot/SuperSystem/Intake/MotorCurrent"
RADIO = "/Robot/RadioStatus/Connected"


@pytest.fixture
def match_log(tmp_path):
    """A 5-second match with one brownout from t=2.0s to t=2.4s."""
    w = LogWriter()
    w.start(BATTERY, "double")
    w.start(SHOOTER_TEMP, "double")
    w.start(SHOOTER_AMPS, "double")
    w.start(INTAKE_AMPS, "float")
    w.start(RADIO, "boolean")
    w.start("NT:/SmartDashboard/Ignored/Temp", "double")

    for i in range(51):  # every 0.1 s
        t = i * 0.1
        volts = 6.2 if 2.0 <= t <= 2.35 else 12.1
        w.append(BATTERY, t, volts)
        w.append(SHOOTER_TEMP, t, 30.0 + t * 2)       # rises to 40 C
        w.append(SHOOTER_AMPS, t, 95.0 if 1.95 <= t <= 2.35 else 20.0)
        w.append(INTAKE_AMPS, t, 40.0 if 1.95 <= t <= 2.35 else 5.0)
        w.append("NT:/SmartDashboard/Ignored/Temp", t, 999.0)
    w.append(RADIO, 0.0, True)
    w.append(RADIO, 3.0, False)
    w.append(RADIO, 3.5, True)

    path = tmp_path / "match.wpilog"
    w.save(path)
    return str(path)


def test_rejects_non_wpilog(tmp_path):
    bad = tmp_path / "bad.wpilog"
    bad.write_bytes(b"not a log")
    with pytest.raises(ValueError):
        analyzer.load_log(str(bad))


def test_reads_every_value(match_log):
    log = analyzer.load_log(match_log)
    assert len(log.series[BATTERY]) == 51
    assert log.series[RADIO] == [(0.0, True), (3.0, False), (3.5, True)]
    assert log.series[INTAKE_AMPS][0] == (0.0, pytest.approx(5.0))


def test_categories():
    assert analyzer.is_current(SHOOTER_AMPS)
    assert not analyzer.is_voltage(SHOOTER_AMPS)   # current is no longer counted as voltage
    assert analyzer.is_voltage(BATTERY)
    assert analyzer.is_temp(SHOOTER_TEMP)
    assert analyzer.is_battery_voltage(BATTERY)


def test_paths_and_subsystems(match_log):
    log = analyzer.load_log(match_log)
    assert analyzer.get_top_level_paths(log) == ["/Robot/RadioStatus", "/Robot/SuperSystem"]
    assert "/Robot/SuperSystem/Shooter" in analyzer.get_subsystems(log)


def test_detects_one_brownout(match_log):
    log = analyzer.load_log(match_log)
    events = analyzer.detect_brownouts(log)
    assert len(events) == 1
    event = events[0]
    assert event["start"] == pytest.approx(2.0)
    assert event["end"] == pytest.approx(2.4)
    assert event["min_volts"] == pytest.approx(6.2)


def test_brownout_reports_motor_currents(match_log):
    log = analyzer.load_log(match_log)
    top = analyzer.detect_brownouts(log)[0]["top_currents"]
    assert top[0] == (SHOOTER_AMPS, pytest.approx(95.0))
    assert top[1] == (INTAKE_AMPS, pytest.approx(40.0))


def test_threshold_is_adjustable(match_log):
    log = analyzer.load_log(match_log)
    assert analyzer.detect_brownouts(log, threshold=6.0) == []


def test_brownout_flag(tmp_path):
    w = LogWriter()
    w.start("/SystemStats/BrownedOut", "boolean")
    for t, value in [(0.0, False), (1.0, True), (1.5, False), (4.0, True)]:
        w.append("/SystemStats/BrownedOut", t, value)
    path = tmp_path / "flag.wpilog"
    w.save(path)
    events = analyzer.detect_brownouts(analyzer.load_log(str(path)))
    assert [(e["start"], e["end"]) for e in events] == [(1.0, 1.5), (4.0, 4.0)]


def test_no_brownouts_message(tmp_path, capsys):
    w = LogWriter()
    w.start(BATTERY, "double")
    for i, v in enumerate([12.5, 11.9, 9.8, 12.2]):
        w.append(BATTERY, i * 0.5, v)
    path = tmp_path / "clean.wpilog"
    w.save(path)
    analyzer.print_brownouts(analyzer.load_log(str(path)))
    assert "None. Lowest battery voltage: 9.80V" in capsys.readouterr().out


def test_max_report(match_log, capsys):
    analyzer.print_max(analyzer.load_log(match_log), [])
    out = capsys.readouterr().out
    assert "/Robot/SuperSystem/Shooter  max temp: 40.00°C  max current: 95.00A" in out
    assert "999" not in out  # NT: entries are skipped


def test_radio_report(match_log, capsys):
    analyzer.print_radio(analyzer.load_log(match_log), [])
    out = capsys.readouterr().out
    assert "t=3.000s  /Robot/RadioStatus/Connected = Disconnected" in out


def test_csv_export(match_log, tmp_path):
    out_path = tmp_path / "out.csv"
    analyzer.export_csv(analyzer.load_log(match_log), ["/Robot/SuperSystem/Shooter"], str(out_path))
    with open(out_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 102  # 51 temp + 51 current readings
    assert {r["kind"] for r in rows} == {"temp_c", "current_a"}


def test_command_line_mode(match_log, capsys):
    assert analyzer.main([match_log, "--brownouts"]) == 0
    out = capsys.readouterr().out
    assert "Total: 1 brownout event(s)" in out
