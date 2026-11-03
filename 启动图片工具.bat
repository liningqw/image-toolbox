@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m imgtool.gui
) else (
    echo Python virtual environment not found. Please follow README.md to install dependencies.
    pause
)
