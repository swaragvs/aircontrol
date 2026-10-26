@echo off
setlocal
title AirControl APK Builder

REM Build AirControl Android APK using Docker (no Android SDK required on Windows).
REM Save this file in the project root beside package.json and Dockerfile.

set "PROJECT_DIR=%~dp0"
set "IMAGE_NAME=aircontrol-android-builder"
set "APK_PATH=%PROJECT_DIR%dist\app-debug.apk"
set "KEYSTORE_DIR=%PROJECT_DIR%.android-keys"

echo.
echo ==========================================
echo       AirControl Android APK Builder
echo ==========================================
echo Project: "%PROJECT_DIR%"
echo.

pushd "%PROJECT_DIR%" >nul
if not exist "%KEYSTORE_DIR%" mkdir "%KEYSTORE_DIR%"

REM Check that Docker Desktop / Linux engine is running.
docker info --format "{{.OSType}}" > "%TEMP%\aircontrol-docker-check.txt" 2>nul
if errorlevel 1 (
    echo ERROR: Docker is not running or is unavailable.
    echo Start Docker Desktop, wait until it is ready, then run this file again.
    del "%TEMP%\aircontrol-docker-check.txt" >nul 2>&1
    goto :fail
)

set /p DOCKER_OS=<"%TEMP%\aircontrol-docker-check.txt"
del "%TEMP%\aircontrol-docker-check.txt" >nul 2>&1
if /I not "%DOCKER_OS%"=="linux" (
    echo ERROR: Docker is using "%DOCKER_OS%" containers; Linux containers are required.
    goto :fail
)

REM Build the image only if it does not already exist.
docker image inspect "%IMAGE_NAME%" >nul 2>&1
if errorlevel 1 (
    echo Docker build image not found. Building it from the Dockerfile...
    if not exist "Dockerfile" (
        echo ERROR: Dockerfile not found in "%PROJECT_DIR%".
        goto :fail
    )
    docker build -t "%IMAGE_NAME%" .
    if errorlevel 1 (
        echo ERROR: Docker image build failed.
        goto :fail
    )
)

echo.
echo Building APK. The first build may take several minutes.
echo.

docker run --rm ^
  -v "%PROJECT_DIR%:/workspace" ^
  -v "%KEYSTORE_DIR%:/root/.android" ^
  -v aircontrol-gradle:/root/.gradle ^
  -w /workspace ^
  "%IMAGE_NAME%" ^
  bash -lc "npm ci && npm run build && npx cap sync android && cd android && chmod +x gradlew && ./gradlew assembleDebug --no-daemon --stacktrace && mkdir -p /workspace/dist && cp app/build/outputs/apk/debug/app-debug.apk /workspace/dist/app-debug.apk"

if errorlevel 1 (
    echo.
    echo ERROR: APK build failed. Review the error output above.
    goto :fail
)

if not exist "%APK_PATH%" (
    echo.
    echo ERROR: Build command finished, but the APK was not found:
    echo "%APK_PATH%"
    goto :fail
)

echo.
echo ==========================================
echo            BUILD SUCCESSFUL
echo ==========================================
echo APK: "%APK_PATH%"
for %%F in ("%APK_PATH%") do echo Size: %%~zF bytes
echo.
echo You can now transfer this APK to your Android phone.
popd
pause
exit /b 0

:fail
popd
echo.
pause
exit /b 1
