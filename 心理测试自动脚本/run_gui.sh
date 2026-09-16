#!/usr/bin/env bash
# 一键启动 GUI：自动准备依赖(仅首次)，自动补齐 Qt xcb 依赖库，然后打开窗口
set -e
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
mkdir -p pylibs/lib

# ---------- 1. Python 依赖 ----------
need_install=0
for mod in PySide6 Crypto requests; do
    if ! PYTHONPATH=pylibs "$PY" -c "import $mod" >/dev/null 2>&1; then
        need_install=1; break
    fi
done
if [ "$need_install" = 1 ]; then
    echo "[setup] 首次运行，安装依赖到 ./pylibs ..."
    "$PY" -m pip install -q --target pylibs --break-system-packages \
        requests pycryptodome PySide6 ddddocr \
        || "$PY" -m pip install -q --target pylibs requests pycryptodome PySide6 ddddocr
fi

# ---------- 2. Qt xcb 插件依赖 libxcb-cursor.so.0（Qt 6.5+ 必需）----------
if [ -z "$QT_QPA_PLATFORM" ] && ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
    if [ ! -f pylibs/lib/libxcb-cursor.so.0 ]; then
        echo "[setup] 系统缺 libxcb-cursor0, 自动下载补齐到 ./pylibs/lib ..."
        mkdir -p ext_tmp
        (curl -sSL -o ext_tmp/deb.deb \
            http://deb.debian.org/debian/pool/main/x/xcb-util-cursor/libxcb-cursor0_0.1.4-1_amd64.deb \
         || wget -q -O ext_tmp/deb.deb \
            http://deb.debian.org/debian/pool/main/x/xcb-util-cursor/libxcb-cursor0_0.1.4-1_amd64.deb)
        dpkg-deb -x ext_tmp/deb.deb ext_tmp/x
        find ext_tmp/x -name "*.so*" -exec cp -a {} pylibs/lib/ \;
        rm -rf ext_tmp
    fi
fi
export LD_LIBRARY_PATH="$(pwd)/pylibs/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# ---------- 3. 启动 ----------
echo "[launch] 启动 GUI..."
exec env PYTHONPATH=pylibs "$PY" main.py "$@"
