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

echo [13/13] v12 height-ring noise model (conditions / scopes / outliers / c_k / mid redraw)
"%PY%" rl_exp\tools\verify\test_v12_noise.py || goto :fail

echo [14/14] pre-kit pxr leak gate (P001/P003: env cfg import chain must stay pxr-clean)
"%PY%" rl_exp\tools\verify\check_pxr_leak.py || goto :fail

echo [15/15] curriculum resume state (roundtrip / fingerprint / hard-abort / hook)
"%PY%" rl_exp\tools\verify\test_resume_state.py || goto :fail

echo [16] tb_scalars record sampling (max_points / first+last / CLI resample)
"%PY%" rl_exp\tools\verify\test_dump_tb_sampling.py || goto :fail

echo [17] v13 symmetric tracking kernel (miki wired / EP gone / v5+v10 frozen)
"%PY%" rl_exp\tools\verify\check_reward_v13.py || goto :fail

echo [18] v14 front-plant/roll fall gate (predicate / dwell / wiring / v13 frozen)
"%PY%" rl_exp\tools\verify\check_terminations_v14.py || goto :fail

echo [19] acceptance metrics (yaw frame / abs sideslip / per-frame MAE / kernel frame contract)
"%PY%" rl_exp\tools\verify\test_acceptance_metrics.py || goto :fail

echo [20] eval frame contract v2 (terminal frame closes the fall window / v1 truncation)
"%PY%" rl_exp\tools\verify\test_eval_frame_v2.py || goto :fail

echo [21] configclass field surface (params_version field vs to_dict vs own_fields)
"%PY%" rl_exp\tools\verify\check_configclass_fields.py || goto :fail

echo [22] configclass field-surface gate falsifier (each drift must still fire)
"%PY%" rl_exp\tools\verify\test_configclass_fields_gate.py || goto :fail

echo [23] config snapshot serializer (order / floats / identities / paths / digest)
"%PY%" rl_exp\tools\verify\test_cfg_snapshot.py || goto :fail

echo [24] recipe golden lock (per-line entries vs versions\^<line^>\cfg_lock.json, shared baselines)
"%PY%" rl_exp\tools\verify\check_cfg_lock.py || goto :fail

echo [25] recipe golden gate falsifier (each drift must still fire)
"%PY%" rl_exp\tools\verify\test_cfg_lock_gate.py || goto :fail

echo [26] run manifest (T0/T1 record, checkpoint infos, external index, --verify)
"%PY%" rl_exp\tools\verify\test_run_manifest.py || goto :fail

echo [27] isolation rebuild gate (material capture/refusal, sources, missing-file negative test)
"%PY%" rl_exp\tools\verify\test_rebuild_gate.py || goto :fail

echo [28] recipe line discovery (yaml/lock convention, refusals must fire)
"%PY%" rl_exp\tools\verify\test_recipe_lines.py || goto :fail

echo [29] recipe line lifecycle (identity / retirement evidence / announced notice period)
"%PY%" rl_exp\tools\verify\check_recipe_registry.py || goto :fail

echo [30] recipe lifecycle gate falsifier (each refusal must still fire)
"%PY%" rl_exp\tools\verify\test_recipe_registry_gate.py || goto :fail

echo [31] recipe identity map (task id to recipe, revision to entries, vs registration + built configs)
"%PY%" rl_exp\tools\verify\check_recipe_map.py --bind-config || goto :fail

echo [32] recipe map gate falsifier (each refusal must still fire)
"%PY%" rl_exp\tools\verify\test_recipe_map_gate.py || goto :fail

echo ALL_OFFLINE_CHECKS_PASSED
exit /b 0

:fail
echo OFFLINE_CHECK_FAILED
exit /b 1
