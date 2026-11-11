@echo off
cd /d "%~dp0"
python run_kingdom.py
if errorlevel 1 (echo. & echo ERREUR - lire le message ci-dessus.) else (start "" "output\kingdom\dashboard.html")
pause
