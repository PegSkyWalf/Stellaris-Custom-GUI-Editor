@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

:: ============================================================
:: Stellaris Custom-GUI Editor - Windows Build Script
:: ============================================================
:: This script can be run from anywhere.
:: It always changes to the project root before doing anything.
:: ============================================================

:: Always switch to project root (one level above this script)
cd /d "%~dp0.."

echo ============================================================
echo   Stellaris Custom-GUI Editor - Windows Build Script
echo ============================================================
echo   Project root : %CD%
echo.

:: Sanity check: make sure we are in the right directory
if not exist "main.py" (
    echo [ERROR] main.py not found in: %CD%
    echo.
    echo   This usually means you downloaded only the build script
    echo   instead of cloning the entire repository.
    echo.
    echo   Please clone the full repository first:
    echo     git clone https://github.com/PegSkyWalf/Stellaris-Custom-GUI-Editor.git
    echo     cd Stellaris-Custom-GUI-Editor
    echo     packaging\build_windows.bat
    echo.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in: %CD%
    echo   The project directory seems incomplete. Please re-clone the repository.
    pause
    exit /b 1
)

:: Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo.
    echo   Please install Python 3.10 or higher:
    echo     https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During installation, check "Add Python to PATH"
    echo   Then close and reopen this window before trying again.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] %PY_VER%
echo.

:: Step 1: Upgrade pip silently
echo [Step 1/5] Upgrading pip...
python -m pip install --upgrade pip -q 2>nul
echo [OK] pip ready
echo.

:: Step 2: Install dependencies
echo [Step 2/5] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    echo.
    echo   Possible causes:
    echo     - No internet connection
    echo     - A package is not compatible with your Python version
    echo.
    echo   Try running manually to see details:
    echo     python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

:: Step 3: Install PyInstaller
echo [Step 3/5] Installing PyInstaller...
python -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)
echo [OK] PyInstaller ready
echo.

:: Step 4: Generate app icon
echo [Step 4/5] Generating app icon...
python packaging\create_icon.py 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Icon generation failed - using default system icon.
)
echo.

:: Step 5: Clean old build artifacts
echo   Cleaning old build output...
if exist dist\StellarisGUIEditor  rmdir /s /q dist\StellarisGUIEditor
if exist build\StellarisGUIEditor rmdir /s /q build\StellarisGUIEditor
echo [OK] Cleaned
echo.

:: Step 6: Run PyInstaller
echo [Step 5/5] Building executable (this may take 1-5 minutes)...
echo.
python -m PyInstaller StellarisGUIEditor.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed.
    echo.
    echo   Common causes and fixes:
    echo     1. Antivirus blocked the build -> temporarily disable antivirus and retry
    echo     2. A Python package is missing -> run: python -m pip install -r requirements.txt
    echo     3. PyInstaller version issue   -> run: python -m pip install --upgrade pyinstaller
    echo.
    pause
    exit /b 1
)

:: Post-build: copy VC++ runtime DLLs to BOTH the EXE root folder AND _internal
::
:: WHY: PyInstaller 6.x bootloader calls LoadLibrary("_internal\python313.dll").
:: At that moment Windows searches: known DLLs → System32 → *the EXE's own folder*.
:: It does NOT yet search _internal\. So vcruntime140.dll must be next to the .exe.
:: We also put them in _internal for completeness.
echo   Copying Visual C++ runtime DLLs (needed for click-to-run compatibility)...
for /f "tokens=*" %%p in ('python -c "import sys,os;print(os.path.dirname(sys.executable))"') do set PYDIR=%%p
for %%D in (vcruntime140.dll vcruntime140_1.dll python3.dll) do (
    if exist "%PYDIR%\%%D" (
        copy /y "%PYDIR%\%%D" "dist\StellarisGUIEditor\%%D"         > nul
        copy /y "%PYDIR%\%%D" "dist\StellarisGUIEditor\_internal\%%D" > nul
        echo [OK] Bundled: %%D
    )
)
echo.

echo ============================================================
echo   Build successful!
echo.
echo   Output folder : dist\StellarisGUIEditor\
echo   Executable    : dist\StellarisGUIEditor\StellarisGUIEditor.exe
echo.
echo   HOW TO DISTRIBUTE:
echo     The ZIP below contains everything - share it with users.
echo     Users must EXTRACT the ZIP before running the EXE.
echo     Do NOT share only the .exe file - it requires the _internal folder.
echo ============================================================
echo.

:: Auto-create distribution ZIP
echo   Creating distribution ZIP...
set ZIP_NAME=StellarisCustomGUIEditor_Windows.zip
if exist "%ZIP_NAME%" del "%ZIP_NAME%"
powershell -nologo -noprofile -command ^
  "Compress-Archive -Path 'dist\StellarisGUIEditor' -DestinationPath '%ZIP_NAME%' -Force" 2>nul
if exist "%ZIP_NAME%" (
    echo [OK] ZIP created: %ZIP_NAME%
    echo   Upload this file to GitHub Releases and share with users.
) else (
    echo [INFO] Auto-ZIP failed. Compress dist\StellarisGUIEditor\ manually.
)
echo.

:: Open output folder
start "" "dist\StellarisGUIEditor"

pause
