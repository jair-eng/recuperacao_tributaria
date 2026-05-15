@echo off
setlocal
title SPED Creditos - Start
cls

echo ==========================================
echo   RECUPERACAO DE CREDITOS TRIBUTARIO - START
echo ==========================================
echo.

cd /d "%~dp0"

set "PY=.venv_tributario\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERRO] Nao encontrei %PY%
    pause
    exit /b 1
)

echo [OK] Python da venv encontrado
echo.

REM =========================
REM 1. Instalar dependencias
REM =========================
if exist "requirements.txt" (
    echo [INFO] Instalando dependencias...
    "%PY%" -m pip install -r requirements.txt
    echo.
)

REM =========================
REM 2. Abrir Swagger
REM =========================
echo [INFO] Abrindo Swagger...
start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000/docs"

REM =========================
REM 3. Subir Frontend
REM =========================
echo [INFO] Subindo Frontend...
start "" "%PY%" -m streamlit run frontend/app.py


REM =========================
REM 4. Subir API (janela principal)
REM =========================
echo [INFO] Subindo API...
echo [INFO] CTRL+C para parar
echo.

"%PY%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause