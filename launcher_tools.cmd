@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Doc to PDF - Tools Launcher

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "CORE_DIR=%BASE_DIR%\system_core"
set "INSTALL_DIR=%BASE_DIR%\install"
set "GITHUB_DIR=%BASE_DIR%\GitHub"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\tools_menu.txt"
set "RES_FILE=%RUNTIME_DIR%\tools_menu_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
del /q "%MENU_FILE%" "%RES_FILE%" >nul 2>nul

call :RESOLVE_PYTHON
call :RESOLVE_FZF

:MAIN
cls
echo ======================================================================
echo   AUDION DOC TO PDF - TOOLS / SERVICE / RELEASE
echo ======================================================================
if defined PYTHON_AVAILABLE (
  echo Python: %PYTHON_CMD% %PYTHON_ARGS%
) else (
  echo Python: not resolved
)
echo.

if /I "%AUDION_AUTO_EXIT%"=="1" (
  call :WRITE_MENU
  echo [INFO] AUDION_AUTO_EXIT=1
  exit /b 0
)

if defined FZF_CMD goto FZF_MENU
goto FALLBACK_MENU

:WRITE_MENU
> "%MENU_FILE%" echo [01] RUN ENV DOCTOR                 ^| doctor        ^| validate runtime and Office COM
>>"%MENU_FILE%" echo [02] SHOW PROJECT INFO              ^| info          ^| system_core\main.py info
>>"%MENU_FILE%" echo [03] VERIFY PORTABLE ENV            ^| verify_env    ^| install\verify_portable_env.cmd
>>"%MENU_FILE%" echo [04] UPDATE FZF                     ^| update_fzf    ^| download latest fzf.exe
>>"%MENU_FILE%" echo [05] MAKE RELEASE ARCHIVE           ^| make_release  ^| package current project
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [06] OPEN system_core               ^| open_core     ^| explorer
>>"%MENU_FILE%" echo [07] OPEN install                   ^| open_install  ^| explorer
>>"%MENU_FILE%" echo [08] OPEN config                    ^| open_config   ^| explorer
>>"%MENU_FILE%" echo [09] OPEN GitHub                    ^| open_github   ^| explorer
>>"%MENU_FILE%" echo [10] OPEN wheelhouse                ^| open_wheels   ^| explorer
>>"%MENU_FILE%" echo [11] OPEN release                   ^| open_release  ^| explorer
>>"%MENU_FILE%" echo [00] BACK                           ^| back          ^| return
goto :eof

:FZF_MENU
call :WRITE_MENU
type "%MENU_FILE%" | "%FZF_CMD%" --prompt="audion@doc-to-pdf [TOOLS] > " --pointer=">" --header="Pick tool:" --layout=reverse --border="rounded" --info=hidden --margin=1,2 > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW

if /I "%RAW%"=="doctor" goto DOCTOR
if /I "%RAW%"=="info" goto INFO
if /I "%RAW%"=="verify_env" goto VERIFY_ENV
if /I "%RAW%"=="update_fzf" goto UPDATE_FZF
if /I "%RAW%"=="make_release" goto MAKE_RELEASE
if /I "%RAW%"=="open_core" goto OPEN_CORE
if /I "%RAW%"=="open_install" goto OPEN_INSTALL
if /I "%RAW%"=="open_config" goto OPEN_CONFIG
if /I "%RAW%"=="open_github" goto OPEN_GITHUB
if /I "%RAW%"=="open_wheels" goto OPEN_WHEELS
if /I "%RAW%"=="open_release" goto OPEN_RELEASE
if /I "%RAW%"=="back" exit /b 0
goto MAIN

:FALLBACK_MENU
echo [1] Run env doctor
echo [2] Show project info
echo [3] Verify portable env
echo [4] Update fzf
echo [5] Make release archive
echo [6] Open system_core
echo [7] Open install
echo [8] Open config
echo [9] Open GitHub
echo [A] Open wheelhouse
echo [B] Open release
echo [0] Back
echo.
choice /C 123456789AB0 /N /M "Select: "
if errorlevel 12 exit /b 0
if errorlevel 11 goto OPEN_RELEASE
if errorlevel 10 goto OPEN_WHEELS
if errorlevel 9 goto OPEN_GITHUB
if errorlevel 8 goto OPEN_CONFIG
if errorlevel 7 goto OPEN_INSTALL
if errorlevel 6 goto OPEN_CORE
if errorlevel 5 goto MAKE_RELEASE
if errorlevel 4 goto UPDATE_FZF
if errorlevel 3 goto VERIFY_ENV
if errorlevel 2 goto INFO
if errorlevel 1 goto DOCTOR
goto MAIN

:DOCTOR
call :REQUIRE_PYTHON || goto MAIN
call :RUNPY "%CORE_DIR%\doctor.py"
if not defined AUDION_NO_PAUSE pause
goto MAIN

:INFO
call :REQUIRE_PYTHON || goto MAIN
call :RUNPY "%CORE_DIR%\main.py" info
if not defined AUDION_NO_PAUSE pause
goto MAIN

:VERIFY_ENV
call "%INSTALL_DIR%\verify_portable_env.cmd"
goto MAIN

:UPDATE_FZF
call "%INSTALL_DIR%\launcher-tools-update_fzf.cmd"
goto MAIN

:MAKE_RELEASE
call "%INSTALL_DIR%\make_release_archive.cmd"
goto MAIN

:OPEN_CORE
start "" explorer "%CORE_DIR%"
goto MAIN

:OPEN_INSTALL
start "" explorer "%INSTALL_DIR%"
goto MAIN

:OPEN_CONFIG
start "" explorer "%BASE_DIR%\config"
goto MAIN

:OPEN_GITHUB
if not exist "%GITHUB_DIR%" mkdir "%GITHUB_DIR%" >nul 2>nul
start "" explorer "%GITHUB_DIR%"
goto MAIN

:OPEN_WHEELS
start "" explorer "%BASE_DIR%\wheelhouse"
goto MAIN

:OPEN_RELEASE
start "" explorer "%BASE_DIR%\release"
goto MAIN

:REQUIRE_PYTHON
if defined PYTHON_AVAILABLE exit /b 0
echo [ERROR] Python runtime was not resolved.
if not defined AUDION_NO_PAUSE pause
exit /b 1

:RUNPY
set "TARGET=%~1"
if not exist "%TARGET%" (
  echo [ERROR] Script not found:
  echo %TARGET%
  goto :eof
)
set "ARG1=%2"
set "ARG2=%3"
set "ARG3=%4"
set "ARG4=%5"
set "ARG5=%6"
set "ARG6=%7"
set "ARG7=%8"
set "ARG8=%9"
"%PYTHON_CMD%" %PYTHON_ARGS% "%TARGET%" %ARG1% %ARG2% %ARG3% %ARG4% %ARG5% %ARG6% %ARG7% %ARG8%
goto :eof

:RESOLVE_PYTHON
set "PYTHON_CMD="
set "PYTHON_ARGS="
set "PYTHON_AVAILABLE="
if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  set "PYTHON_AVAILABLE=1"
  goto :eof
)
if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  set "PYTHON_AVAILABLE=1"
  goto :eof
)
py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  set "PYTHON_AVAILABLE=1"
  goto :eof
)
where python.exe >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  set "PYTHON_AVAILABLE=1"
  goto :eof
)
goto :eof

:RESOLVE_FZF
set "FZF_CMD="
if /I "%AUDION_DISABLE_FZF%"=="1" goto :eof
if exist "%CORE_DIR%\fzf.exe" (
  set "FZF_CMD=%CORE_DIR%\fzf.exe"
  goto :eof
)
where fzf.exe >nul 2>nul
if not errorlevel 1 (
  set "FZF_CMD=fzf"
  goto :eof
)
goto :eof

:TRIM
set "_TMP=!%~1!"
for /f "tokens=* delims= " %%z in ("!_TMP!") do set "_TMP=%%z"
:TRIM_R
if not defined _TMP goto TRIM_DONE
if not "!_TMP:~-1!"==" " goto TRIM_DONE
set "_TMP=!_TMP:~0,-1!"
goto TRIM_R
:TRIM_DONE
set "%~1=!_TMP!"
goto :eof
