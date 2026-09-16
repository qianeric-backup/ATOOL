#!/bin/bash
# Gench 选课助手 —— Linux 一键启动器
# 自动检测依赖并构建/启动 GUI; 无 GUI 环境时提供 CLI 模式
set -e
cd "$(dirname "$0")"

PY="python3"
"$PY" -c "import sys; assert sys.version_info >= (3, 8)" || { echo "需要 Python >= 3.8"; exit 1; }
$PY -c "import requests" 2>/dev/null || $PY -m pip install --user --break-system-packages requests
$PY -c "import tkinter" 2>/dev/null || {
    echo "警告: 无 tkinter (GUI 不可用), 改用 CLI 模式"
    exec $PY gench_enroll.py "$@"
}

# 打包好的单文件存在则优先使用 (更快, 无需源码)
if [ -x "$(dirname "$0")/Gench选课助手" ]; then
    exec "./Gench选课助手" "$@"
fi

# 有显示环境 → GUI; 否则 CLI
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    exec $PY gench_enroll_gui.py "$@"
else
    echo "未检测到显示环境, 进入 CLI 模式"
    exec $PY gench_enroll.py "$@"
fi
