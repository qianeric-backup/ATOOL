#!/usr/bin/env bash
# ======================================================================
# 抢课助手 Linux 启动器（双击/./ 均可运行）
# 用法:
#   ./抢课助手.sh                       → GUI 桌面版（需 python3-tk）
#   ./抢课助手.sh --cli --help          → CLI 无头模式（参数原样透传 app.py）
#   ./抢课助手.sh --cli --config 抢课配置.json --targets 1001,1002 --poll 10
# ======================================================================
set -u
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[!] 未找到 python3 —— 请先安装: sudo apt install -y python3 python3-pip"
    exit 1
fi

# --- 依赖自检: requests ---
if ! "$PY" -c "import requests" >/dev/null 2>&1; then
    echo "[*] 缺少 requests，尝试 pip 安装…"
    "$PY" -m pip install --user -q requests \
        || { echo "[!] pip 安装失败，请手动执行: pip3 install requests"; exit 1; }
    echo "[*] requests 安装完成"
fi

# --- 依赖自检: tkinter（GUI 必需；--cli 可无）---
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    case " $* " in
        *" --cli "*)
            echo "[i] 未装 tkinter，直接使用 CLI 模式" ;;
        *)
            echo "[!] GUI 版需要 tkinter:   sudo apt install -y python3-tk"
            echo "[i] 无显示器/服务器请用 CLI:  $0 --cli --help"
            exit 1 ;;
    esac
fi

# --- 启动（所有参数透传 app.py）---
exec "$PY" app.py "$@"
