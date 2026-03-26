@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

REM Always switch to project root (one level above this script).
cd /d "%~dp0.."

echo ============================================================
echo   Stellaris Custom-GUI Editor - Windows Build Script
echo ============================================================
echo   Project root : %CD%
echo.

REM Check repository root.
if not exist "main.py" (
    echo [ERROR] main.py not found in: %CD%
    echo [ERROR] Please clone the full repository first.
    echo.
    echo   git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
    echo   cd Stellaris-Custom-GUI-Editor
    echo   build.bat
    echo.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in: %CD%
    echo [ERROR] The project directory is incomplete.
    pause
    exit /b 1
)

REM Detect Python interpreter with fallbacks:
REM 1) python in PATH
REM 2) py launcher default 3.x
REM 3) py launcher pinned 3.11
set "PY_CMD="
where python > nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"

if not defined PY_CMD (
    py -3 --version > nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py -3"
)

if not defined PY_CMD (
    py -3.11 --version > nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py -3.11"
)

if not defined PY_CMD (
    echo [ERROR] Python not found.
    echo [ERROR] Install Python 3.10+ OR install Python Launcher for Windows.
    echo [INFO] Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do set PY_VER=%%v
echo [OK] %PY_VER%  ^(via "%PY_CMD%"^)
echo.

echo [Step 1/5] Upgrading pip...
%PY_CMD% -m pip install --upgrade pip -q
if %errorlevel% neq 0 (
    echo [ERROR] pip upgrade failed.
    pause
    exit /b 1
)
echo [OK] pip ready
echo.

echo [Step 2/5] Installing dependencies...
%PY_CMD% -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    echo [INFO] Try this command for full logs:
    echo        %PY_CMD% -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

echo [Step 3/5] Installing PyInstaller...
%PY_CMD% -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller installation failed.
    pause
    exit /b 1
)
echo [OK] PyInstaller ready
echo.

echo [Step 4/5] Generating app icon...
%PY_CMD% packaging\create_icon.py
if %errorlevel% neq 0 (
    echo [WARNING] Icon generation failed, continue without custom icon.
)
echo.

echo [Step 5/5] Cleaning old build output...
if exist dist\StellarisGUIEditor rmdir /s /q dist\StellarisGUIEditor
if exist build\StellarisGUIEditor rmdir /s /q build\StellarisGUIEditor
echo [OK] Cleaned
echo.

echo [Build] Running PyInstaller...
%PY_CMD% -m PyInstaller StellarisGUIEditor.spec --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [Build] Copying runtime DLLs...
for /f "tokens=*" %%p in ('%PY_CMD% -c "import sys,os;print(os.path.dirname(sys.executable))"') do set PYDIR=%%p
for %%D in (vcruntime140.dll vcruntime140_1.dll python3.dll) do (
    if exist "%PYDIR%\%%D" (
        copy /y "%PYDIR%\%%D" "dist\StellarisGUIEditor\%%D" > nul
        copy /y "%PYDIR%\%%D" "dist\StellarisGUIEditor\_internal\%%D" > nul
        echo [OK] Bundled %%D
    )
)
echo.

echo [Pack] Creating ZIP...
set ZIP_NAME=StellarisCustomGUIEditor_Windows.zip
if exist "%ZIP_NAME%" del "%ZIP_NAME%"
powershell -NoLogo -NoProfile -Command "Compress-Archive -Path 'dist\StellarisGUIEditor' -DestinationPath '%ZIP_NAME%' -Force"
if exist "%ZIP_NAME%" (
    echo [OK] ZIP created: %ZIP_NAME%
) else (
    echo [WARNING] ZIP creation failed, compress dist\StellarisGUIEditor manually.
)
echo.

echo ============================================================
echo Build successful
echo EXE : dist\StellarisGUIEditor\StellarisGUIEditor.exe
echo ZIP : %ZIP_NAME%
echo ============================================================

start "" "dist\StellarisGUIEditor"
pause
