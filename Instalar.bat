@echo off
title Instalacao Automacao PRF

echo ==========================================
echo        INSTALANDO AUTOMACAO PRF
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/5] Criando ambiente virtual...
python -m venv .venv

echo.
echo [2/5] Ativando ambiente virtual...
call .venv\Scripts\activate

echo.
echo [3/5] Atualizando ferramentas...
python -m pip install --upgrade pip setuptools wheel

echo.
echo [4/5] Instalando bibliotecas...
pip install requests python-dotenv unidecode playwright

echo.
echo [5/5] Instalando navegador Chromium...
playwright install chromium

echo.
echo ==========================================
echo      INSTALACAO CONCLUIDA COM SUCESSO!
echo ==========================================
echo.

pause