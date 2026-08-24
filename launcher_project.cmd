@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion Doc to PDF - English

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "CORE_DIR=%BASE_DIR%\system_core"
set "INSTALL_DIR=%BASE_DIR%\install"
set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\project_menu_en.txt"
set "RES_FILE=%RUNTIME_DIR%\project_menu_en_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
del /q "%MENU_FILE%" "%RES_FILE%" >nul 2>nul

call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON

call :RESOLVE_FZF
if errorlevel 1 (
  set "MENU_MODE=CMD fallback"
) else (
  set "MENU_MODE=FZF"
)

:MAIN
cls
echo ======================================================================
echo   AUDION DOC TO PDF - PROJECT LAUNCHER
echo ======================================================================
echo Root:      %BASE_DIR%
echo Python:    %PYTHON_CMD% %PYTHON_ARGS%
echo Menu mode: %MENU_MODE%
echo.

if /I "%AUDION_AUTO_EXIT%"=="1" (
  call :WRITE_MENU
  echo [INFO] AUDION_AUTO_EXIT=1
  exit /b 0
)

if defined FZF_CMD goto FZF_MENU
goto FALLBACK_MENU

:WRITE_MENU
> "%MENU_FILE%" echo [01] BATCH CONVERT INPUT TO PDF (RECURSIVE)  ^| batch_recursive ^| convert input with subfolders
>>"%MENU_FILE%" echo [02] CONVERT ONE OFFICE FILE TO PDF          ^| file_one        ^| prompt for file path
>>"%MENU_FILE%" echo [03] CROP POWERPOINT PDFS TO EXACT 16:9      ^| crop_pptx       ^| output only
>>"%MENU_FILE%" echo [04] SHOW PROJECT INFO                       ^| info            ^| settings and supported formats
>>"%MENU_FILE%" echo [05] RUN ENV DOCTOR                          ^| doctor          ^| validate runtime and Office COM
>>"%MENU_FILE%" echo [06] OPEN GUI SHELL                          ^| gui_shell       ^| NiceGUI local shell
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [07] OPEN INPUT FOLDER                       ^| open_input      ^| explorer
>>"%MENU_FILE%" echo [08] OPEN OUTPUT FOLDER                      ^| open_output     ^| explorer
>>"%MENU_FILE%" echo [09] OPEN LOGS FOLDER                        ^| open_logs       ^| explorer
>>"%MENU_FILE%" echo [10] OPEN GITHUB DOCS                        ^| open_github     ^| explorer
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [12] BUILD PORTABLE ENV                      ^| build_env       ^| install builder
>>"%MENU_FILE%" echo [13] VERIFY PORTABLE ENV                     ^| verify_env      ^| doctor wrapper
>>"%MENU_FILE%" echo [14] TOOLS LAUNCHER                          ^| tools           ^| service menu
>>"%MENU_FILE%" echo [15] RUSSIAN PROJECT LAUNCHER                ^| launcher_ru     ^| switch to Russian
>>"%MENU_FILE%" echo [00] EXIT                                    ^| exit            ^| close
goto :eof

:FZF_MENU
call :WRITE_MENU
type "%MENU_FILE%" | "%FZF_CMD%" --prompt="audion@doc-to-pdf [PROJECT-EN] > " --pointer=">" --header="Pick an action:" --layout=reverse --border="rounded" --info=hidden --margin=1,2 > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW

if /I "%RAW%"=="batch_recursive" goto BATCH_RECURSIVE
if /I "%RAW%"=="file_one" goto FILE_ONE
if /I "%RAW%"=="crop_pptx" goto CROP_PPTX
if /I "%RAW%"=="info" goto INFO
if /I "%RAW%"=="doctor" goto DOCTOR
if /I "%RAW%"=="gui_shell" goto GUI_SHELL
if /I "%RAW%"=="open_input" goto OPEN_INPUT
if /I "%RAW%"=="open_output" goto OPEN_OUTPUT
if /I "%RAW%"=="open_logs" goto OPEN_LOGS
if /I "%RAW%"=="open_github" goto OPEN_GITHUB
if /I "%RAW%"=="build_env" goto BUILD_ENV
if /I "%RAW%"=="verify_env" goto VERIFY_ENV
if /I "%RAW%"=="tools" goto TOOLS
if /I "%RAW%"=="launcher_ru" goto LAUNCHER_RU
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:FALLBACK_MENU
echo [1] Batch convert input to PDF (recursive)
echo [2] Convert one Office file to PDF
echo [3] Crop PowerPoint PDFs to exact 16:9
echo [4] Show project info
echo [5] Run environment doctor
echo [G] Open GUI shell
echo [6] Open input folder
echo [7] Open output folder
echo [8] Open logs folder
echo [A] Open GitHub docs
echo [B] Build portable env
echo [C] Verify portable env
echo [T] Tools launcher
echo [R] Russian project launcher
echo [0] Exit
echo.
choice /C 12345G678ABCTR0 /N /M "Select: "
if errorlevel 15 exit /b 0
if errorlevel 14 goto LAUNCHER_RU
if errorlevel 13 goto TOOLS
if errorlevel 12 goto VERIFY_ENV
if errorlevel 11 goto BUILD_ENV
if errorlevel 10 goto OPEN_GITHUB
if errorlevel 9 goto OPEN_LOGS
if errorlevel 8 goto OPEN_OUTPUT
if errorlevel 7 goto OPEN_INPUT
if errorlevel 6 goto GUI_SHELL
if errorlevel 5 goto DOCTOR
if errorlevel 4 goto INFO
if errorlevel 3 goto CROP_PPTX
if errorlevel 2 goto FILE_ONE
if errorlevel 1 goto BATCH_RECURSIVE
goto MAIN

:BATCH_RECURSIVE
call :RUNPY "%CORE_DIR%\main.py" batch --recursive
if not defined AUDION_NO_PAUSE pause
goto MAIN

:FILE_ONE
set "SRC_PATH="
echo.
set /p SRC_PATH=Office file path: 
if not defined SRC_PATH goto MAIN
call :RUNPY "%CORE_DIR%\main.py" file --input "%SRC_PATH%"
if not defined AUDION_NO_PAUSE pause
goto MAIN

:CROP_PPTX
call :RUNPY "%CORE_DIR%\main.py" crop-pptx
if not defined AUDION_NO_PAUSE pause
goto MAIN

:INFO
call :RUNPY "%CORE_DIR%\main.py" info
if not defined AUDION_NO_PAUSE pause
goto MAIN

:DOCTOR
call :RUNPY "%CORE_DIR%\doctor.py"
if not defined AUDION_NO_PAUSE pause
goto MAIN

:GUI_SHELL
call "%BASE_DIR%\launcher_gui.cmd"
goto MAIN

:OPEN_INPUT
start "" explorer "%BASE_DIR%\input"
goto MAIN

:OPEN_OUTPUT
start "" explorer "%BASE_DIR%\output"
goto MAIN

:OPEN_LOGS
start "" explorer "%BASE_DIR%\logs"
goto MAIN

:OPEN_GITHUB
if not exist "%BASE_DIR%\GitHub" mkdir "%BASE_DIR%\GitHub" >nul 2>nul
start "" explorer "%BASE_DIR%\GitHub"
goto MAIN

:BUILD_ENV
call "%INSTALL_DIR%\Build_Portable_Env_Build.cmd"
goto MAIN

:VERIFY_ENV
call "%INSTALL_DIR%\verify_portable_env.cmd"
goto MAIN

:TOOLS
call "%BASE_DIR%\launcher_tools.cmd"
goto MAIN

:LAUNCHER_RU
if exist "%BASE_DIR%\launcher_project_ru.cmd" call "%BASE_DIR%\launcher_project_ru.cmd"
goto MAIN

:NO_PYTHON
cls
echo [ERROR] Python runtime was not resolved.
echo.
echo Supported locations:
echo   runtime\python.exe
echo   runtime\python\python.exe
echo   py -3.12
echo   python
echo.
echo Use builder_main.cmd or install\Build_Portable_Env_Build.cmd
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

if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  goto PY_OK
)

if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  goto PY_OK
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  goto PY_OK
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
  goto PY_OK
)

exit /b 1

:PY_OK
exit /b 0

:RESOLVE_FZF
set "FZF_CMD="
if /I "%AUDION_DISABLE_FZF%"=="1" exit /b 1
if exist "%CORE_DIR%\fzf.exe" (
  set "FZF_CMD=%CORE_DIR%\fzf.exe"
  exit /b 0
)
where fzf.exe >nul 2>nul
if not errorlevel 1 (
  set "FZF_CMD=fzf"
  exit /b 0
)
exit /b 1

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
