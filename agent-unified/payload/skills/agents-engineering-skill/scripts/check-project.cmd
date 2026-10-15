@echo off
python -c "import sys; raise SystemExit(sys.version_info[0] != 3)" >nul 2>nul
if errorlevel 1 goto pylauncher
python "%~dp0check_project.py" %*
exit /b %ERRORLEVEL%

:pylauncher
py -3 -c "import sys; raise SystemExit(sys.version_info[0] != 3)" >nul 2>nul
if errorlevel 1 goto bundled
py -3 "%~dp0check_project.py" %*
exit /b %ERRORLEVEL%

:bundled
if not exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto missing
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "%~dp0check_project.py" %*
exit /b %ERRORLEVEL%

:missing
echo Python 3 was not found. Install Python 3 or pass check_project.py to an available interpreter. 1>&2
exit /b 2
