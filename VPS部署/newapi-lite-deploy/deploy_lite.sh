#!/usr/bin/env bash
# =============================================================================
# deploy_lite.sh — new-api 轻量化套皮版 一键部署/重建/回滚（Docker）
#
# 背景：
#   本包包含改造完成的完整源码（web/dist 已含 Lite Skin 覆盖层 + index.html
#   引用 /lite-skin.css）。服务器不跑 bun/rsbuild（避免 1G 内存 OOM、不额外
#   占用磁盘），只做 Go 编译（Dockerfile.lite 多阶段）打包运行镜像。
#
# 用法（在解压后的源码目录执行，root 或 sudo docker 权限）：
#   ./deploy_lite.sh                 # 自动装 docker(如缺) + 构建镜像并替换容器
#   ./deploy_lite.sh --rebuild       # 强制重新构建（不跳过已有镜像）
#   ./deploy_lite.sh --restore       # 回滚：切回旧镜像 calciumion/new-api:latest
#   ./deploy_lite.sh --port 3000     # 指定对外端口（默认 3000）
#   ./deploy_lite.sh --data /data/new-api   # 数据卷目录（默认 /data/new-api）
#
# 安全：
#   - 数据卷（数据库 one-api.db）保持不变，替换容器不丢配置/渠道/令牌
#   - 旧镜像 calciumion/new-api:latest 保留，可随时 --restore 回滚
#   - 幂等：镜像已存在且未 --rebuild 时跳过构建
#   - Docker 缺失时自动安装（get.docker.com 官方脚本，仅 Ubuntu/Debian 系）
# =============================================================================
set -uo pipefail

IMAGE="new-api-lite:latest"
OLD_IMAGE="calciumion/new-api:latest"
CONTAINER="new-api"
PORT=3000
DATA_DIR=/data/new-api
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBUILD=0
RESTORE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)     PORT="$2";     shift 2 ;;
    --data)     DATA_DIR="$2"; shift 2 ;;
    --rebuild)  REBUILD=1;     shift ;;
    --restore)  RESTORE=1;     shift ;;
    -h|--help)
      echo "用法: $0 [--port N] [--data DIR] [--rebuild] [--restore]"
      echo ""
      echo "  默认行为: 自动安装 docker(如缺) → 构建 new-api-lite:latest → 替换容器 new-api"
      echo "  数据卷留存在 $DATA_DIR，配置/渠道/令牌不丢"
      exit 0 ;;
    *) echo "未知参数: $1 (用 --help 查看)"; exit 1 ;;
  esac
done

log(){ echo "[*] $*" ; }
err(){ echo "[!] $*" >&2 ; }

# ---------------------------------------------------------------------------
# 0a) Docker 安装（若已装则跳过；仅支持 Ubuntu/Debian 系自动安装）
# ---------------------------------------------------------------------------
install_docker(){
  if command -v docker >/dev/null 2>&1; then
    log "Docker 已安装: $(docker --version 2>/dev/null)"
    # 兼容 docker 未随开机启动的情况
    systemctl enable --now docker >/dev/null 2>&1
    return 0
  fi

  log "未检测到 Docker，尝试自动安装（get.docker.com 官方脚本，需 Ubuntu/Debian 系）..."
  if ! command -v curl >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
      log "缺少 curl，先安装 curl"
      apt-get update -y >/dev/null 2>&1
      apt-get install -y curl >/dev/null 2>&1 || { err "curl 安装失败"; return 1; }
    else
      err "缺少 curl 且非 apt 系系统，请手动安装 curl 与 docker"; return 1
    fi
  fi
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh || { err "下载官方安装脚本失败"; return 1; }
  sh /tmp/get-docker.sh || { err "Docker 自动安装失败，请手动安装（见 README）"; return 1; }
  rm -f /tmp/get-docker.sh

  systemctl enable --now docker >/dev/null 2>&1
  if ! command -v docker >/dev/null 2>&1 || ! systemctl is-active --quiet docker 2>/dev/null; then
    err "docker 安装完成但服务未运行，请手动 systemctl start docker 后重跑"; return 1
  fi
  log "docker 服务已运行"
}

# ---------------------------------------------------------------------------
# 0b) 前置检查：源码目录、dist/lite-skin（需在 docker 安装后做，便于后续构建）
# ---------------------------------------------------------------------------
preflight(){
  [[ -f "$SRC_DIR/Dockerfile.lite" ]] || { err "缺少 Dockerfile.lite（请在源码目录运行）"; exit 1; }
  [[ -f "$SRC_DIR/web/dist/lite-skin.css" ]] || { err "缺少 web/dist/lite-skin.css（前端 dist 未就位）"; exit 1; }
  [[ -f "$SRC_DIR/web/dist/index.html" ]] && grep -q 'lite-skin.css' "$SRC_DIR/web/dist/index.html" \
    || { err "index.html 未引用 lite-skin.css（dist 版本不对）"; exit 1; }
  log "前置检查通过（dist 含 Lite Skin）"
}

# ---------------------------------------------------------------------------
# 1) 构建镜像（幂等）
# ---------------------------------------------------------------------------
build_image(){
  if docker image inspect "$IMAGE" >/dev/null 2>&1 && [[ "$REBUILD" == "0" ]]; then
    log "镜像 $IMAGE 已存在，跳过构建（如需重建加 --rebuild）"
    return 0
  fi
  if [[ "$RESTORE" == "1" ]]; then
    return 0
  fi
  log "构建镜像 $IMAGE（仅 Go 编译，不在服务器跑 bun，避免内存不足）..."
  docker build -f "$SRC_DIR/Dockerfile.lite" -t "$IMAGE" "$SRC_DIR" || { err "构建失败，见日志"; exit 1; }
  log "镜像构建完成: $IMAGE"
}

# ---------------------------------------------------------------------------
# 2) 替换容器（保留数据卷）
# ---------------------------------------------------------------------------
replace_container(){
  local IMG="$IMAGE"
  if [[ "$RESTORE" == "1" ]]; then
    IMG="$OLD_IMAGE"
    docker image inspect "$IMG" >/dev/null 2>&1 || { err "旧镜像 $IMG 不存在，无法回滚"; exit 1; }
    log "回滚到旧镜像 $IMG ..."
  fi

  log "停止/移除旧容器（数据卷 $DATA_DIR 保留）..."
  docker stop "$CONTAINER" >/dev/null 2>&1
  docker rm "$CONTAINER" >/dev/null 2>&1

  log "启动容器 $CONTAINER（镜像 $IMG，端口 $PORT）..."
  docker run -d --name "$CONTAINER" --restart always \
    -p "$PORT:3000" \
    -e TZ=Asia/Shanghai \
    -v "$DATA_DIR:/data" \
    "$IMG" >/dev/null || { err "容器启动失败"; exit 1; }
}

# ---------------------------------------------------------------------------
# 3) 健康检查 + 输出
# ---------------------------------------------------------------------------
health_check(){
  log "等待 new-api 就绪..."
  local PUBLIC_IP=""
  PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null)
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || echo 000)
    if [[ "$code" == "200" ]]; then
      # 验证 lite-skin 已上线（回滚时该项允许缺失）
      lite=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/lite-skin.css" 2>/dev/null)
      echo ""
      echo "=============================================="
      echo "  new-api 部署完成"
      echo "  镜像: $(docker inspect -f '{{.Image}}' "$CONTAINER" 2>/dev/null | cut -c1-12)"
      echo "  皮肤: ${lite:-000} (lite-skin.css, 200=轻量化皮肤生效)"
      echo "  本机:  http://127.0.0.1:$PORT"
      echo "  公网:  http://${PUBLIC_IP:-<服务器IP>}:$PORT"
      echo "  数据目录: $DATA_DIR"
      echo "  回滚:   ./deploy_lite.sh --restore"
      echo "  日志:   docker logs -f $CONTAINER"
      echo "=============================================="
      return 0
    fi
    sleep 2
  done
  err "new-api 在 $((30*2)) 秒内未就绪，请查看: docker logs --tail 50 $CONTAINER"
  return 1
}

install_docker || exit 1
preflight
build_image
replace_container
health_check || exit 1