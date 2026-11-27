@echo off
set "EXP_PYTHON=%RL_PYTHON%"
if not defined EXP_PYTHON if exist "%~dp0..\paths.yaml" (
    for /f "usebackq tokens=1,* delims=:" %%K in ("%~dp0..\paths.yaml") do (
        for /f "tokens=1" %%N in ("%%K") do (
            if /i "%%N"=="python" (
                for /f "tokens=1 delims=#" %%V in ("%%L") do (
                    set "EXP_RAW=%%V"
                    call :trim_value
                )
            )
        )
    )
)
if not defined EXP_PYTHON if defined VIRTUAL_ENV set "EXP_PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if defined EXP_PYTHON if exist "%EXP_PYTHON%" exit /b 0
echo Isaac Lab Python not found. Set python in paths.yaml, activate its environment, or set RL_PYTHON. 1>&2
exit /b 1

:trim_value
setlocal EnableDelayedExpansion
set "VAL=!EXP_RAW!"
:trim_left
if defined VAL if "!VAL:~0,1!"==" " (
    set "VAL=!VAL:~1!"
    goto :trim_left
)
:trim_right
if defined VAL if "!VAL:~-1!"==" " (
    set "VAL=!VAL:~0,-1!"
    goto :trim_right
)
if defined VAL (
    set "VAL=!VAL:"=!"
    set "FIRST=!VAL:~0,1!"
    set "LAST=!VAL:~-1!"
    if [!FIRST!]==['] if [!LAST!]==['] set "VAL=!VAL:~1,-1!"
)
if defined VAL (
    for /f "delims=" %%R in ("!VAL!") do (
        endlocal
        set "EXP_PYTHON=%%R"
        set "EXP_RAW="
        exit /b 0
    )
)
endlocal
set "EXP_PYTHON="
set "EXP_RAW="
exit /b 0
