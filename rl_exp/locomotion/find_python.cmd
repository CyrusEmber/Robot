@echo off
set "EXP_PYTHON=%RL_PYTHON%"
if not defined EXP_PYTHON if defined VIRTUAL_ENV set "EXP_PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined EXP_PYTHON if exist "%~dp0..\..\paths.yaml" (
    for /f "usebackq tokens=1,* delims=:" %%K in ("%~dp0..\..\paths.yaml") do (
        if "%%K"=="python" for /f "tokens=*" %%P in ("%%L") do set "EXP_PYTHON=%%~P"
    )
)
if defined EXP_PYTHON if exist "%EXP_PYTHON%" exit /b 0
echo Isaac Lab Python not found. Set python in paths.yaml, activate its environment, or set RL_PYTHON. 1>&2
exit /b 1
