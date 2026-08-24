@echo off
chcp 65001 >nul
setlocal EnableExtensions

title Audion Doc to PDF - Make Release Archive

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%A in ("%SCRIPT_DIR%\..") do set "ROOT=%%~fA"
for %%A in ("%ROOT%") do set "PROJECT_NAME=%%~nxA"

set "RELEASE_DIR=%ROOT%\release"
set "STAGE_PARENT=%RELEASE_DIR%\_stage"
set "STAGE_PROJECT=%STAGE_PARENT%\%PROJECT_NAME%"
set "ARCHIVE=%RELEASE_DIR%\%PROJECT_NAME%_portable.zip"
set "CMD_ENCODING=%ROOT%\install\Check-CmdEncoding.cmd"

if not exist "%RELEASE_DIR%\" mkdir "%RELEASE_DIR%" >nul 2>nul
if exist "%STAGE_PROJECT%\" rd /s /q "%STAGE_PROJECT%" >nul 2>nul
if not exist "%STAGE_PARENT%\" mkdir "%STAGE_PARENT%" >nul 2>nul

echo ======================================================================
echo   AUDION DOC TO PDF - MAKE RELEASE ARCHIVE
echo ======================================================================
echo Root:    %ROOT%
echo Stage:   %STAGE_PROJECT%
echo Target:  %ARCHIVE%
echo.

echo [0/5] Normalizing project CMD files...
call "%CMD_ENCODING%" -Fix
if errorlevel 1 goto ERR_CMD_ENCODING

echo [1/5] Staging release contents...
robocopy "%ROOT%" "%STAGE_PROJECT%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD "%ROOT%\.git" "%ROOT%\release" "%ROOT%\.venv" "%ROOT%\.venv_latest" "%ROOT%\venv" "%ROOT%\._runtime" "%ROOT%\__pycache__" "%ROOT%\.pytest_cache" "%ROOT%\.mypy_cache" "%ROOT%\.ruff_cache" /XF "%ROOT%\api_key.txt" "%ROOT%\api_key_openai.txt" >nul
set "RC=%errorlevel%"
if %RC% GEQ 8 goto ERR_STAGE

echo [2/5] Pruning generated work folders from stage...
call :CLEAR_USER_DIR "%STAGE_PROJECT%\input"
call :CLEAR_USER_DIR "%STAGE_PROJECT%\output"
call :CLEAR_MANAGED_DIR "%STAGE_PROJECT%\logs"
call :CLEAR_MANAGED_DIR "%STAGE_PROJECT%\report"
call :CLEAR_MANAGED_DIR "%STAGE_PROJECT%\workspace"

echo [3/5] Checking staged CMD file encoding...
call "%STAGE_PROJECT%\install\Check-CmdEncoding.cmd"
if errorlevel 1 goto ERR_CMD_ENCODING

echo [4/5] Building final ZIP archive...
where tar.exe >nul 2>nul
if errorlevel 1 goto ERR_ARCHIVE
if exist "%ARCHIVE%" del /f /q "%ARCHIVE%" >nul 2>nul
pushd "%STAGE_PARENT%" >nul
tar.exe -a -cf "%ARCHIVE%" "%PROJECT_NAME%"
set "RC=%errorlevel%"
popd >nul
if not "%RC%"=="0" goto ERR_ARCHIVE

echo [5/5] Release archive created successfully.
echo.
echo Manual review before upload:
echo   - Open the ZIP and inspect top-level contents
echo   - Verify no secrets or private configs are present
echo   - Verify launchers start and the main workflow passes smoke test
echo   - Archive: %ARCHIVE%
echo.
if not defined AUDION_NO_PAUSE pause
exit /b 0

:CLEAR_MANAGED_DIR
if not exist "%~1\" mkdir "%~1" >nul 2>nul
for /d %%D in ("%~1\*") do if exist "%%~fD\" rd /s /q "%%~fD" >nul 2>nul
for %%F in ("%~1\*") do if exist "%%~fF" if /I not "%%~nxF"==".gitkeep" del /f /q "%%~fF" >nul 2>nul
goto :eof

:CLEAR_USER_DIR
if not exist "%~1\" mkdir "%~1" >nul 2>nul
for /d %%D in ("%~1\*") do if exist "%%~fD\" rd /s /q "%%~fD" >nul 2>nul
for %%F in ("%~1\*") do if exist "%%~fF" del /f /q "%%~fF" >nul 2>nul
goto :eof

:ERR_STAGE
echo.
echo [ERROR] Failed to stage release contents.
if not defined AUDION_NO_PAUSE pause
exit /b 1

:ERR_ARCHIVE
echo.
echo [ERROR] Failed to create release archive.
echo Verify tar.exe availability and release folder permissions.
if not defined AUDION_NO_PAUSE pause
exit /b 1

:ERR_CMD_ENCODING
echo.
echo [ERROR] CMD encoding check failed.
echo Fix project launchers before building or publishing a release.
if not defined AUDION_NO_PAUSE pause
exit /b 1
