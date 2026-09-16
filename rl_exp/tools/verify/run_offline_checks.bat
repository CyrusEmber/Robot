@echo off
REM Offline verification suite: no Isaac Sim app needed, seconds to run.
REM The checks themselves (list, order, labels) live in offline_suite.py, which runs them
REM in parallel -- every check is its own interpreter and most of them pay a torch import
REM before their first assertion, so sequential meant paying it once per check.
REM Host paths (IsaacLab tree + venv python) are recorded in paths.yaml at the
REM repo root; ablation_harness\host_paths.py is the single reader and is
REM stdlib-only, so the PATH python can ask it. RL_PYTHON / RL_ISAAC_ROOT
REM override for one shell; without them the old env_isaaclab convention under
REM RL_ISAAC_ROOT is the fallback.
REM   from repo root: rl_exp\tools\verify\run_offline_checks.bat
REM   extra flags reach the runner: --jobs N, --verbose, --list, --self-test
setlocal enabledelayedexpansion
cd /d %~dp0..\..\..

set "PY=%RL_PYTHON%"
if not defined PY for /f "delims=" %%p in ('python ablation_harness\host_paths.py --python 2^>nul') do set "PY=%%p"
if not defined PY (
  if not defined RL_ISAAC_ROOT set "RL_ISAAC_ROOT=E:\IsaacLab"
  set "PY=!RL_ISAAC_ROOT!\env_isaaclab\Scripts\python.exe"
)
if exist "%PY%" goto pyok
echo WARN: paths.yaml gave no python and %PY% is absent -- falling back to PATH python
set "PY=python"
:pyok

"%PY%" rl_exp\tools\verify\offline_suite.py --python "%PY%" %*
if errorlevel 1 exit /b 1
exit /b 0
