@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

:: Change to project root (one level above this script's location)
cd /d "%~dp0.."

echo ============================================================
echo   Stellaris GUI Editor - Windows Build Script
echo ============================================================
echo Working directory: %CD%
echo.

:: Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10 or higher.
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] %PY_VER%
echo.

:: Step 1: Install dependencies
echo [Step 1/5] Installing dependencies...
python -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo [ERROR] pip upgrade failed. Check your network connection.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed. See output above.
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

:: Step 2: Install PyInstaller
echo [Step 2/5] Installing PyInstaller...
python -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller installation failed.
    pause
    exit /b 1
)
echo [OK] PyInstaller ready
echo.

:: Step 3: Generate app icon
echo [Step 3/5] Generating app icon...
python packaging\create_icon.py
if %errorlevel% neq 0 (
    echo [WARNING] Icon generation failed. Using default system icon.
)
echo.

:: Step 4: Clean old build
echo [Step 4/5] Cleaning old build output...
if exist dist\StellarisGUIEditor (
    rmdir /s /q dist\StellarisGUIEditor
)
if exist build\StellarisGUIEditor (
    rmdir /s /q build\StellarisGUIEditor
)
echo [OK] Old build cleaned
echo.

:: Step 5: Run PyInstaller
echo [Step 5/5] Packaging (this may take 1-5 minutes)...
echo.
python -m PyInstaller StellarisGUIEditor.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed! See output above for details.
    echo         Common causes:
    echo           - A required Python package is not installed
    echo           - pydds dds_sys.pyd path issue
    echo           - Antivirus blocking the build (try disabling it temporarily)
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Build successful!
echo   Output: dist\StellarisGUIEditor\
echo   Executable: dist\StellarisGUIEditor\StellarisGUIEditor.exe
echo.
echo   Compress the entire dist\StellarisGUIEditor\ folder to ZIP for distribution.
echo ============================================================
echo.

:: Open dist folder
start "" "dist\StellarisGUIEditor"

pause
