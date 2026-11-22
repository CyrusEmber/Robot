@echo off
setlocal DisableDelayedExpansion

set "TRAIN_PYTHON=%RL_PYTHON%"
if not defined TRAIN_PYTHON if defined VIRTUAL_ENV set "TRAIN_PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined TRAIN_PYTHON for /f "delims=" %%P in ('python "%~dp0ablation_harness\host_paths.py" --python 2^>nul') do set "TRAIN_PYTHON=%%P"

if not defined TRAIN_PYTHON goto :missing_python
if not exist "%TRAIN_PYTHON%" goto :missing_python
if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0"
)
"%TRAIN_PYTHON%" -m rl_exp.locomotion.train %*
exit /b %ERRORLEVEL%

:missing_python
echo Isaac Lab Python not found. Activate its environment or set RL_PYTHON to its python.exe. 1>&2
exit /b 1
