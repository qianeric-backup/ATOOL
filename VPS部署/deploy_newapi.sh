#!/usr/bin/env bash
# =============================================================================
# deploy_newapi.sh — 一键自动部署 new-api（Codex 中转站），Docker 容器方式
#
# 用法（root 执行）：
#   ./deploy_newapi.sh [OPTIONS]
#   OPTIONS:
#     --port <端口>        对外端口，默认 3000
#     --data <目录>        数据持久化目录，默认 /data/new-api
#     --image <镜像:tag>   new-api 镜像，默认 calciumion/new-api:latest
#     --tz <时区>          容器时区，默认 Asia/Shanghai
#     --recreate           已存在同名容器则先删除重建（默认保留/跳过）
#
# 安全：脚本幂等——Docker 已装则跳过安装；容器已存在且未指定 --recreate 则只做健康检查。
# 依赖：curl、bash（Ubuntu/Debian 自带）
# =============================================================================
set -uo pipefail

PORT=3000
DATA_DIR=/data/new-api
IMAGE="calciumion/new-api:latest"
TZ_VAL="Asia/Shanghai"
RECREATE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)     PORT="$2";     shift 2 ;;
    --data)     DATA_DIR="$2"; shift 2 ;;
    --image)    IMAGE="$2";    shift 2 ;;
    --tz)       TZ_VAL="$2";   shift 2 ;;
    --recreate) RECREATE=1;    shift ;;
    -h|--help)
      echo "用法: $0 [--port N] [--data DIR] [--image IMG] [--tz TZ] [--recreate]"
      exit 0 ;;
    *) echo "未知参数: $1 (用 --help 查看)"; exit 1 ;;
  esac
done

log(){ echo "[*] $*" ; }
err(){ echo "[!] $*" >&2 ; }

# ---------------------------------------------------------------------------
# 1) Docker 安装（若已装则跳过）
# ---------------------------------------------------------------------------
install_docker(){
  if command -v docker >/dev/null 2>&1; then
    log "Docker 已安装: $(docker --version 2>/dev/null)"
  else
    log "未检测到 Docker，开始安装..."
    if ! command -v curl >/dev/null 2>&1; then
      err "需要 curl（apt-get -y install curl）"; return 1
    fi
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh || { err "下载官方安装脚本失败"; return 1; }
    sh /tmp/get-docker.sh || { err "Docker 安装失败"; return 1; }
    rm -f /tmp/get-docker.sh
  fi
  systemctl enable --now docker >/dev/null 2>&1
  if ! systemctl is-active --quiet docker; then
    err "docker 服务未运行"; return 1
  fi
  log "docker 服务已运行"
}

# ---------------------------------------------------------------------------
# 2) 确保数据目录
# ---------------------------------------------------------------------------
mkdir -p "$DATA_DIR" || { err "无法创建数据目录 $DATA_DIR"; exit 1; }

# ---------------------------------------------------------------------------
# 3) 容器存在性处理
# ---------------------------------------------------------------------------
handle_existing(){
  if docker inspect new-api >/dev/null 2>&1; then
    if [[ "$RECREATE" == "1" ]]; then
      log "删除旧容器重建 (容器已存在)"
      docker rm -f new-api >/dev/null 2>&1
    else
      log "同名容器 new-api 已存在，跳过创建（如需重建加 --recreate）"
      return 1
    fi
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 4) 拉取并运行 new-api
# ---------------------------------------------------------------------------
run_container(){
  log "拉取镜像 $IMAGE（首次可能较慢）"
  docker pull "$IMAGE" >/dev/null || { err "镜像拉取失败"; exit 1; }
  log "启动容器 new-api (端口 $PORT)"
  docker run -d --name new-api --restart always \
      -p "$PORT:3000" \
      -e TZ="$TZ_VAL" \
      -v "$DATA_DIR:/data" \
      "$IMAGE" >/dev/null || { err "容器启动失败"; exit 1; }
}

# ---------------------------------------------------------------------------
# 5) 健康检查 + 输出
# ---------------------------------------------------------------------------
health_check(){
  log "等待 new-api 就绪..."
  local PUBLIC_IP=""
  PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null)
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" 2>/dev/null || echo 000)
    if [[ "$code" == "200" ]]; then
      echo ""
      echo "=============================================="
      echo "  new-api (Codex 中转站) 部署成功"
      echo "  本机:  http://127.0.0.1:$PORT"
      echo "  公网:  http://${PUBLIC_IP:-<服务器IP>}:$PORT"
      echo "  数据目录: $DATA_DIR"
      echo "  查看日志: docker logs -f new-api"
      echo "=============================================="
      return 0
    fi
    sleep 2
  done
  err "new-api 在 $((30*2)) 秒内未就绪，请查看: docker logs --tail 50 new-api"
  return 1
}

# ---------------------------------------------------------------------------
install_docker || exit 1
if handle_existing; then
  run_container
fi
health_check || exit 1
