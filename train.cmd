@echo off
setlocal DisableDelayedExpansion
call "%~dp0rl_exp\locomotion\find_python.cmd"
if errorlevel 1 exit /b 1
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%EXP_PYTHON%" -m rl_exp.locomotion.train %*
exit /b %ERRORLEVEL%
