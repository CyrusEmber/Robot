@echo off
setlocal DisableDelayedExpansion

set "EVAL_PYTHON=%RL_PYTHON%"
if not defined EVAL_PYTHON if defined VIRTUAL_ENV set "EVAL_PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined EVAL_PYTHON for /f "delims=" %%P in ('python "%~dp0ablation_harness\host_paths.py" --python 2^>nul') do set "EVAL_PYTHON=%%P"

if not defined EVAL_PYTHON goto :missing_python
if not exist "%EVAL_PYTHON%" goto :missing_python
if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0"
)
"%EVAL_PYTHON%" -m ablation_harness.evaluate %*
exit /b %ERRORLEVEL%

:missing_python
echo Isaac Lab Python not found. Activate its environment or set RL_PYTHON to its python.exe. 1>&2
exit /b 1
