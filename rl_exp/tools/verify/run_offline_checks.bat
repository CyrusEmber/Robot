@echo off
REM Offline verification suite: no Isaac Sim app needed, seconds to run.
REM Run with the IsaacLab venv python on PATH. Use after ANY change to
REM tasks/*.py, ablation_harness/* or the DR/protocol contracts, and before
REM committing (see skill git-auto-sync).
REM   from repo root: lizard_exp\tools\verify\run_offline_checks.bat
setlocal
cd /d %~dp0..\..\..

echo [1/4] framework pin check (IsaacLab internals + pinned SHA)
python lizard_exp\tools\verify\framework_pin_check.py || goto :fail

echo [2/4] freeze contracts (DR/wiring + robot block parity, DR lists, PLAY coverage, asset contract + locks)
python lizard_exp\tools\verify\check_dr_parity.py --strict || goto :fail

echo [3/4] recovery vectorization parity
python lizard_exp\tools\verify\test_recovery_parity.py || goto :fail

echo [4/4] staged curriculum offline test
python lizard_exp\tools\verify\test_staged_curriculum.py || goto :fail

echo ALL_OFFLINE_CHECKS_PASSED
exit /b 0

:fail
echo OFFLINE_CHECK_FAILED
exit /b 1
