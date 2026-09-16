# Windows 一键打包脚本 —— 在 Windows 电脑上双击或在 cmd 运行
# 产生: dist\Gench选课助手.exe (单文件 GUI)
@echo off
cd /d %~dp0
where python >nul 2>nul || (
  echo 请先安装 Python 3.8+: https://www.python.org/downloads/ (勾选 Add to PATH)
  pause & exit /b 1
)
python -m pip install --quiet requests pyinstaller || goto :err
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Gench选课助手" gench_enroll_gui.py || goto :err
echo.
echo ✅ 完成: dist\Gench选课助手.exe
pause & exit /b 0
:err
echo ❌ 打包失败, 请截图报错信息
pause
