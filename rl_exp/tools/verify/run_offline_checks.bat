@echo off
REM Offline verification suite: no Isaac Sim app needed, seconds to run.
REM Host paths (IsaacLab tree + venv python) are recorded in paths.yaml at the
REM repo root; ablation_harness\host_paths.py is the single reader and is
REM stdlib-only, so the PATH python can ask it. RL_PYTHON / RL_ISAAC_ROOT
REM override for one shell; without them the old env_isaaclab convention under
REM RL_ISAAC_ROOT is the fallback.
REM   from repo root: rl_exp\tools\verify\run_offline_checks.bat
setlocal enabledelayedexpansion
cd /d %~dp0..\..\..

set "PY=%RL_PYTHON%"
if not defined PY for /f "delims=" %%p in ('python ablation_harness\host_paths.py --python 2^>nul') do set "PY=%%p"
if not defined PY (
  if not defined RL_ISAAC_ROOT set "RL_ISAAC_ROOT=E:\IsaacLab"
  set "PY=!RL_ISAAC_ROOT!\env_isaaclab\Scripts\python.exe"
)
if exist "%PY%" goto pyok
echo WARN: paths.yaml gave no python and %PY% is absent - falling back to PATH python
set "PY=python"
:pyok

echo [1/11] framework pin check (IsaacLab internals + pinned SHA)
"%PY%" rl_exp\tools\verify\framework_pin_check.py || goto :fail

echo [2/11] freeze contracts (DR/wiring + robot block parity, DR lists, PLAY coverage, asset contract + locks)
"%PY%" rl_exp\tools\verify\check_dr_parity.py --strict || goto :fail

echo [3/11] recovery vectorization parity
"%PY%" rl_exp\tools\verify\test_recovery_parity.py || goto :fail

echo [4/11] staged curriculum offline test
"%PY%" rl_exp\tools\verify\test_staged_curriculum.py || goto :fail

echo [5/11] teacher split-encoder networks (forward/gradient/export/transfer)
"%PY%" rl_exp\tools\verify\test_teacher_networks.py || goto :fail

echo [6/11] student belief networks (GRU/gate/decoder/load_from_teacher)
"%PY%" rl_exp\tools\verify\test_student_networks.py || goto :fail

echo [7/11] v3 curriculum + ring pattern (c_k math, tilt predicate, geometry)
"%PY%" rl_exp\tools\verify\test_v3_curriculum.py || goto :fail

echo [8/11] obs layout gate (group names, term order, c_k step consistency)
"%PY%" rl_exp\tools\verify\check_obs_layout.py || goto :fail

echo [9/11] v5 anti-collapse rewards (linear tracking / slip / belly / c_k scaling)
"%PY%" rl_exp\tools\verify\test_v5_rewards.py || goto :fail

echo [10/11] v5.3 SIR terrain curriculum (band / resample / walk clamp / replay / throttle)
"%PY%" rl_exp\tools\verify\test_v5_terrain_sir.py || goto :fail

echo [11/11] v11 joint SIR terrain curriculum (param grid / Eq.2-3-7 / fallback / walk / command)
"%PY%" rl_exp\tools\verify\test_joint_sir.py || goto :fail

echo [12/12] version-record completeness (four-piece set / FAMILY row / FILEMAP row)
"%PY%" rl_exp\tools\verify\check_version_docs.py || goto :fail

echo ALL_OFFLINE_CHECKS_PASSED
exit /b 0

:fail
echo OFFLINE_CHECK_FAILED
exit /b 1
