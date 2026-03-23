@echo off
title ADAS Modular System
echo ==========================================
echo   ADAS Modular System - Module Launcher
echo ==========================================
echo.
echo Select a module to run:
echo   1. FCW  - Forward Collision Warning
echo   2. BSD  - Lane Assist + Blind Spot Detection
echo   3. EVP  - Emergency Vehicle Preemption
echo   4. Exit
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" goto fcw
if "%choice%"=="2" goto bsd
if "%choice%"=="3" goto evp
if "%choice%"=="4" goto end

echo Invalid choice.
pause
goto end

:fcw
echo.
echo Select FCW input:
echo   1. Video file (videos/new1.mp4)
echo   2. Webcam
set /p src="Enter choice (1-2): "
if "%src%"=="1" (
    python -m fcw.main --source videos/new1.mp4
) else (
    python -m fcw.main --source 0
)
pause
goto end

:bsd
echo.
echo Select Lane Assist input:
echo   1. Video file (videos/new.mp4)
echo   2. Webcam
set /p src="Enter choice (1-2): "
if "%src%"=="1" (
    python -m lane_assist.main --source videos/new.mp4
) else (
    python -m lane_assist.main --source 0
)
pause
goto end

:evp
echo.
echo Select EVP input:
echo   1. Video file (videos/video_demo.mp4)
echo   2. Webcam (with microphone)
set /p src="Enter choice (1-2): "
if "%src%"=="1" (
    python -m emergency_preemption.main --source videos/video_demo.mp4
) else (
    python -m emergency_preemption.main --source 0 --microphone
)
pause
goto end

:end
