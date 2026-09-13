@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   猫咪桌宠 - 一键生成 EXE
echo ========================================
echo.

taskkill /F /IM CatPet.exe >nul 2>nul

set "PYTHON_EXE="

where python >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE (
            "%%P" --version >nul 2>nul
            if not errorlevel 1 set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    where py >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
            if exist "%%P" set "PYTHON_EXE=%%P"
        )
    )
)

if not defined PYTHON_EXE (
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
        if not defined PYTHON_EXE if exist "%%~fD\python.exe" set "PYTHON_EXE=%%~fD\python.exe"
    )
)

if not defined PYTHON_EXE (
    echo [错误] 未找到可用的 Python 3。
    echo 请安装 Python 后重新运行，或把 python.exe 加入 PATH。
    pause
    exit /b 1
)

echo 使用 Python：%PYTHON_EXE%
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo [提示] 未安装 PyInstaller，正在尝试安装...
    "%PYTHON_EXE%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败。
        pause
        exit /b 1
    )
)

echo.
echo [1/2] 正在清理并打包...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm CatPet.spec
if errorlevel 1 (
    echo.
    echo [错误] EXE 打包失败，请查看上方错误信息。
    echo 建议在项目目录执行：
    echo "%PYTHON_EXE%" -m PyInstaller --clean --noconfirm CatPet.spec
    pause
    exit /b 1
)

if not exist "dist\CatPet.exe" (
    echo.
    echo [错误] 未找到 dist\CatPet.exe。
    pause
    exit /b 1
)

echo.
echo [2/2] 打包完成！
echo EXE 位置：%~dp0dist\CatPet.exe
echo.
start "" explorer "%~dp0dist"
pause
endlocal