@echo off
SET LOG_PATH=%~1

IF "%LOG_PATH%"=="" (
    echo No log file provided. Drag a .wpilog onto this file, or edit LOG_PATH.
    pause
    exit /b 1
)

echo Reading temperatures from: %LOG_PATH%
python "%~dp0FilterTemp.py" "%LOG_PATH%"
pause