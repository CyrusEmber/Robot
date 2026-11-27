@echo off
setlocal DisableDelayedExpansion
call "%~dp0locomotion\find_python.cmd"
if errorlevel 1 exit /b 1
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%EXP_PYTHON%" -m locomotion.train %*
exit /b %ERRORLEVEL%
