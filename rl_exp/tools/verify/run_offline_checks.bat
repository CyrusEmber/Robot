@echo off
REM Offline verification suite: no Isaac Sim app needed, seconds to run.
REM Self-locating (the junction layout that auto-detection relied on died
REM with G2): resolves the IsaacLab root and its venv python on its own.
REM RL_ISAAC_ROOT env var overrides the default machine layout (G3 harness
REM parameterization reuses the same variable name).
REM   from repo root: rl_exp\tools\verify\run_offline_checks.bat
setlocal
cd /d %~dp0..\..\..

if not defined RL_ISAAC_ROOT set "RL_ISAAC_ROOT=E:\IsaacLab"
set "PY=%RL_ISAAC_ROOT%\env_isaaclab\Scripts\python.exe"
if exist "%PY%" goto pyok
echo WARN: venv python not found at %PY% - falling back to PATH python
set "PY=python"
:pyok

echo [1/4] framework pin check (IsaacLab internals + pinned SHA)
"%PY%" rl_exp\tools\verify\framework_pin_check.py || goto :fail

echo [2/4] freeze contracts (DR/wiring + robot block parity, DR lists, PLAY coverage, asset contract + locks)
"%PY%" rl_exp\tools\verify\check_dr_parity.py --strict || goto :fail

echo [3/4] recovery vectorization parity
"%PY%" rl_exp\tools\verify\test_recovery_parity.py || goto :fail

echo [4/4] staged curriculum offline test
"%PY%" rl_exp\tools\verify\test_staged_curriculum.py || goto :fail

echo ALL_OFFLINE_CHECKS_PASSED
exit /b 0

:fail
echo OFFLINE_CHECK_FAILED
exit /b 1
