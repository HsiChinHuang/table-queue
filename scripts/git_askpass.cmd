@echo off
REM GIT_ASKPASS helper for Windows.
REM
REM Git invokes this script with a prompt string as the first argument.
REM We respond based on whether the prompt asks for username or password.
REM
REM The API_TOKEN environment variable is injected by the Launcher
REM (see launcher/index.ts). This script does NOT read .env.

setlocal enabledelayedexpansion
set "PROMPT=%~1"

echo !PROMPT! | findstr /I /C:"Username" >nul
if !errorlevel! equ 0 (
  echo x-access-token
  exit /b 0
)

echo !PROMPT! | findstr /I /C:"Password" >nul
if !errorlevel! equ 0 (
  if "!API_TOKEN!"=="" (
    echo ERROR: API_TOKEN is not set in the environment 1>&2
    exit /b 1
  )
  echo !API_TOKEN!
  exit /b 0
)

echo ERROR: unrecognized prompt: !PROMPT! 1>&2
exit /b 1