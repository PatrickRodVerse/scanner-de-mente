@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -X utf8 -m lab.ui --open --graphify-python "C:\Python314\python.exe"
if errorlevel 1 pause
