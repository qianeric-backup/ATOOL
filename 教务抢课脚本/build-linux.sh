#!/usr/bin/env bash
# ======================================================================
# 抢课助手 Linux 一键打包
# 产物: dist/抢课助手（GUI/CLI 双模式可执行文件，可直接拷到同架构机器）
# 依赖: python3 + pip（脚本自动装 pyinstaller/requests）；GUI 需本机 tkinter
# ======================================================================
set -e
cd "$(dirname "$(readlink -f "$0")")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || { echo "[!] 未找到 python3"; exit 1; }

"$PY" -c "import requests" >/dev/null 2>&1 || "$PY" -m pip install --user -q requests
"$PY" -c "import PyInstaller" >/dev/null 2>&1 || "$PY" -m pip install --user -q pyinstaller

if "$PY" -c "import tkinter" >/dev/null 2>&1; then
    echo "[*] tkinter 可用 → 打包 GUI+CLI 双模式"
else
    echo "[i] 未装 tkinter → 产物仅 CLI 可用（GUI 会提示安装 python3-tk）"
fi

echo "[*] 源码语法检查…"
"$PY" -m py_compile app.py gench_login.py gench_session.py

echo "[*] PyInstaller 打包中…"
"$PY" -m PyInstaller "抢课助手.spec" --clean --noconfirm

echo "[*] CLI 冒烟自检…"
./dist/抢课助手 --cli --help | head -3

echo
echo "[√] 打包完成: dist/抢课助手 ($(du -h dist/抢课助手 | cut -f1))"
