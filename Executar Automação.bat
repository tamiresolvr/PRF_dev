@echo off
title Automacao PRF

echo ==========================================
echo         AUTOMACAO PRF
echo ==========================================
echo.

cd /d "%~dp0"

.venv\Scripts\python.exe main.py

echo.
echo ==========================================
echo     EXECUCAO FINALIZADA
echo ==========================================
pause