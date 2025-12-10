@echo off
REM EA ANALYSIS - DOUBLE CLICK TO START
REM No command line needed!

title EA Analysis - One Click Launcher

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Run the launcher
python EASY_START.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo.
    echo An error occurred. Please check the output above.
    pause
)
