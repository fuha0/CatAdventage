@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem  Launch the cat from source, for debugging.
rem  All Chinese output comes from run_cat.py, so this file stays
rem  pure ASCII (a .bat that contains a Chinese path can be mangled
rem  by the console codepage).
rem
rem  Extra arguments are passed through, e.g.
rem     this launcher --fps 60
rem     this launcher --action wave
rem     this launcher --restart
rem  Full list:  python run_cat.py --help
rem ---------------------------------------------------------------

if not exist "%~dp0run_cat.py" (
    echo [ERROR] run_cat.py not found next to this file.
    pause
    exit /b 1
)

set "PYEXE="

rem Prefer a recent interpreter first: some Python installs ship without
rem tkinter, and the pet needs it. :probe keeps the first one that has it.
call :probe "%LocalAppData%\Programs\Python\Python314\python.exe"
call :probe "%LocalAppData%\Programs\Python\Python313\python.exe"
call :probe "%LocalAppData%\Programs\Python\Python312\python.exe"
call :probe "%ProgramFiles%\Python314\python.exe"
call :probe "%ProgramFiles%\Python313\python.exe"
call :probe "%ProgramFiles%\Python312\python.exe"

for /f "delims=" %%P in ('where python 2^>nul') do call :probe "%%P"

if not defined PYEXE (
    echo.
    echo [ERROR] No Python 3 with tkinter was found.
    echo         Install Python 3, tick "tcl/tk" in the installer, or
    echo         edit the :probe list above to point at your python.exe.
    echo.
    pause
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo Using Python: %PYEXE%
echo.

"%PYEXE%" "%~dp0run_cat.py" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [EXIT] run_cat.py returned %RC%
    pause
)

endlocal
exit /b %RC%

rem ---------------- helpers ----------------

:probe
if defined PYEXE exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import tkinter" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYEXE=%~1"
exit /b 0
