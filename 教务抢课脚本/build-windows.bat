@echo off
rem ======================================================================
rem 抢课助手 Windows 一键打包（在 Windows 本机双击运行）
 rem 产物: dist\抢课助手.exe（双击弹出 tkinter 主窗口，无黑窗）
rem 依赖: Python 3.10+（安装时勾选 Add to PATH）+ tkinter（官方安装包自带）
rem ======================================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [!] 未找到 python —— 请先安装 Python 3 并勾选 "Add Python to PATH"
    pause & exit /b 1
)

python -c "import requests" >nul 2>nul || python -m pip install -q requests
python -c "import PyInstaller" >nul 2>nul || python -m pip install -q pyinstaller

echo [*] 源码语法检查…
python -m py_compile app.py gench_login.py gench_session.py
if errorlevel 1 (
    echo [!] 语法检查未通过，打包终止
    pause & exit /b 1
)

echo [*] PyInstaller 打包中（约 1-2 分钟）…
pyinstaller "抢课助手.spec" --clean --noconfirm
if errorlevel 1 (
    echo [!] 打包失败，请查看上方报错
    pause & exit /b 1
)

echo.
echo [√] 打包完成: dist\抢课助手.exe
start "" explorer dist
pause
