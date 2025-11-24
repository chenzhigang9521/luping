@echo off
chcp 65001 >nul
REM Windows Packaging Script

echo ========================================
echo Screen Recorder Windows Packaging Tool
echo ========================================
echo.

REM Ensure we're in the project root directory
cd /d "%~dp0"

echo Step 1: Checking Rye installation...
rye --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Rye not found, please install Rye first
    echo Install command: irm https://rye-up.com/get ^| iex
    pause
    exit /b 1
)
echo Rye is installed
echo.

echo Step 2: Syncing dependencies...
rye sync
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to sync dependencies
    pause
    exit /b 1
)
echo Dependencies synced successfully
echo.

echo Step 3: Creating recordings directory...
if not exist "recordings" (
    mkdir recordings
    echo Created recordings directory
) else (
    echo Recordings directory already exists
)
echo.

echo Step 4: Starting packaging...
echo This may take a few minutes, please wait...
echo.

REM Run pyinstaller using rye
REM Note: recordings directory is created at runtime, no need to include it in the package
REM Note: OpenCV DLL files may need to be collected manually
rye run pyinstaller --clean --noconfirm --onefile ^
    --windowed ^
    --name="ScreenRecorder" ^
    --hidden-import pynput ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    --hidden-import pynput._util ^
    --hidden-import pynput._util.win32 ^
    --hidden-import cv2 ^
    --hidden-import cv2.cv2 ^
    --hidden-import numpy ^
    --hidden-import mss ^
    --collect-all cv2 ^
    luping\gui.py

set BUILD_RESULT=%ERRORLEVEL%

if %BUILD_RESULT% EQU 0 (
    echo.
    echo ========================================
    echo Packaging completed successfully!
    echo ========================================
    echo.
    echo Executable file location: dist\ScreenRecorder.exe
    echo.
    echo Notes:
    echo - You can distribute dist\ScreenRecorder.exe to users
    echo - First run may require administrator privileges (for screen recording)
    echo - Windows Defender may warn about unsigned app, choose "Run anyway"
    echo.
    echo You can now test the application by running dist\ScreenRecorder.exe
    echo.
    pause
    exit /b 0
) else (
    echo.
    echo ========================================
    echo Packaging failed!
    echo ========================================
    echo Please check the error messages above
    echo.
    pause
    exit /b 1
)
