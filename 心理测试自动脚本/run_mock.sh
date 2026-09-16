#!/usr/bin/env bash
# 启动本地 mock 服务器(端口18085)，并在 GUI 中自动指向它（离线测试模式）
# 选项: ./run_mock.sh --no-gui   只启动 mock 不开界面
set -e
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if ! "$PY" -c "import requests" >/dev/null 2>&1; then HOOK="PYTHONPATH=pylibs"; fi

LOG=mock/mock_server.log
echo "[mock] 启动心理测评 mock 站点(127.0.0.1:18085) ... 日志: $LOG"
"$PY" mock/mock_server.py --host 127.0.0.1 --port 18085 >"$LOG" 2>&1 &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null || true' EXIT
sleep 1.2

if ! curl -s -m 3 -X POST http://127.0.0.1:18085/Home/CheckLogin >/dev/null; then
    echo "[mock] 启动失败, 查看日志:"; tail -5 "$LOG"; exit 1
fi
echo "[mock] ready: http://127.0.0.1:18085  (任意账密可登录, UPI 默认待测试)"

if [ "$1" = "--no-gui" ]; then
    echo "[mock] --no-gui: 后台运行 mock (PID $MOCK_PID), 界面稍后自行打开时":
    echo "  QT_QPA_PLATFORM= 环境下: SITE_ADDRESS=http://127.0.0.1:18085 ./run_gui.sh"
    wait $MOCK_PID
else
    # GUI 默认站点写进 profile, 打开即指向 mock
    SITE=http://127.0.0.1:18085 "$PY" main.py
fi
