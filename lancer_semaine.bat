@echo off
cd /d "%~dp0"
python run_weekly.py
if errorlevel 1 (echo. & echo ERREUR - lire le message ci-dessus.) else (start "" "output\dashboard.html")
pause
