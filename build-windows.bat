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

echo Step 3.5: 查找 OpenCV ffmpeg DLL 和系统 ffmpeg 可执行文件...
set "CV_FFMPEG_DLL="
set "SYSTEM_FFMPEG="
for /f "usebackq delims=" %%A in (`python -c "import cv2,glob,os; p=os.path.dirname(cv2.__file__); matches=glob.glob(os.path.join(p,'opencv_videoio_ffmpeg*.dll')); print(matches[0] if matches else '')"`) do set "CV_FFMPEG_DLL=%%A"
for /f "usebackq delims=" %%B in ('where ffmpeg 2^>nul ^| findstr /r /c:"ffmpeg\.exe"') do set "SYSTEM_FFMPEG=%%B"

if defined CV_FFMPEG_DLL (
    echo Found OpenCV ffmpeg DLL: %CV_FFMPEG_DLL%
) else (
    echo OpenCV ffmpeg DLL not found in cv2 package
)

if defined SYSTEM_FFMPEG (
    echo Found system ffmpeg: %SYSTEM_FFMPEG%
) else (
    echo System ffmpeg not found in PATH
)


echo Step 4: Starting packaging...
echo This may take a few minutes, please wait...
echo.

REM Run pyinstaller using rye
REM Note: recordings directory is created at runtime, no need to include it in the package
REM Note: OpenCV DLL files or ffmpeg.exe may need to be collected and included

if defined CV_FFMPEG_DLL (
    echo 包含 OpenCV ffmpeg DLL 到包中
    set "ADD_DLL=--add-binary=\"%CV_FFMPEG_DLL%:.\""
) else (
    set "ADD_DLL="
)

if defined SYSTEM_FFMPEG (
    echo 包含系统 ffmpeg 到包中
    set "ADD_FFMPEG=--add-binary=\"%SYSTEM_FFMPEG%:.\""
) else (
    set "ADD_FFMPEG="
)

echo 正在运行 PyInstaller...
echo Debug: CV_FFMPEG_DLL=%CV_FFMPEG_DLL%
echo Debug: SYSTEM_FFMPEG=%SYSTEM_FFMPEG%

if defined CV_FFMPEG_DLL if defined SYSTEM_FFMPEG (
    REM Use Python launcher to run PyInstaller programmatically (avoids CLI quoting issues)
    echo Calling Python launcher to run PyInstaller...
    set "CV_FFMPEG_DLL=%CV_FFMPEG_DLL%"
    set "SYSTEM_FFMPEG=%SYSTEM_FFMPEG%"
    rye run python tools\run_pyinstaller.py
) else if defined CV_FFMPEG_DLL (
    echo Calling Python launcher to run PyInstaller...
    set "CV_FFMPEG_DLL=%CV_FFMPEG_DLL%"
    rye run python tools\run_pyinstaller.py
) else if defined SYSTEM_FFMPEG (
    echo Calling Python launcher to run PyInstaller...
    set "SYSTEM_FFMPEG=%SYSTEM_FFMPEG%"
    rye run python tools\run_pyinstaller.py
) else (
    echo Calling Python launcher to run PyInstaller...
    rye run python tools\run_pyinstaller.py
)

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
