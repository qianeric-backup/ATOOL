#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deploy_3xui.py — 按本环境验证过的做法，在全新 Ubuntu/Dev 服务器上一键部署 3X-UI + VLESS+Reality，
并生成 N 个客户端各自的 Clash 订阅地址。

依赖：curl、python3（目标服务器上需可用，均为系统自带）。
用法（在目标服务器上以 root 运行）：
    python3 deploy_3xui.py --ip <公网IP> [--clients 3] [--user admin] [--password xxxx]
  说明：
    --ip       必填，服务器公网 IP（用于订阅/节点地址）
    --clients  客户端数量，默认 3
    --user / --password  面板账号密码（不传则读取 3x-ui 安装结果 /etc/x-ui/install-result.env）
    --reinstall 强制重装 3x-ui（默认检测到已安装则跳过安装，仅做配置）

关键修复点（与本环境一致的踩坑结论）：
  1) Reality dest/SNI 使用 www.apple.com:443（www.microsoft.com 会导致 REALITY invalid handshake）
  2) realitySettings.minClientVer 显式设为 "1.0.0"，否则 xray 默认 26.3.27 拒绝 Mihomo 等客户端
  3) realitySettings 顶层放 publicKey（让 base64/vless 链接带 pbk），且加 settings 子对象
     {publicKey, fingerprint:"chrome", spiderX:"/"}（3x-ui 的 Clash 渲染依此输出 public-key）
  4) 入站 shareAddrStrategy=custom、shareAddr=<公网IP>，避免链接出现 localhost
  5) 启用 subClashEnable + subClashAutoDetect，让 /clash/<subId> 返回 YAML
"""
import argparse, base64, hashlib, http.cookiejar, json, os, random, string
import subprocess, sys, time, urllib.error, urllib.request

# ---------------------------------------------------------------------------
# 配置常量（可按需修改）
# ---------------------------------------------------------------------------
DEST = "www.apple.com:443"          # Reality dest（伪装目标）
DEST_SNI = ["www.apple.com"]        # serverNames
FINGERPRINT = "chrome"
SHORT_IDS = ["0123456789abcdef"]
SPIDER_X = "/"
FLOW = "xtls-rprx-vision"
MIN_CLIENT_VER = "1.0.0"

INSTALL_SCRIPT_URL = "https://raw.githubusercontent.com/MHSanaei/3x-ui/master/install.sh"
RESULT_FILE = "/etc/x-ui/install-result.env"
XUI_BIN = "/usr/local/x-ui/x-ui"
XRAY_BIN = "/usr/local/x-ui/bin/xray-linux-amd64"


def log(msg):
    print("[*] " + msg, flush=True)


def sh(cmd, timeout=600):
    """Run a shell command; return (rc, stdout)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except FileNotFoundError:
        return -1, "no such file or binary"
    except subprocess.TimeoutExpired:
        return -2, "timeout"


def run(cmd, timeout=600):
    rc, out = sh(cmd, timeout)
    if rc != 0:
        log("![cmd] rc=%d: %s" % (rc, cmd))
    return rc, out


# ---------------------------------------------------------------------------
# 安装 3X-UI（非交互）
# ---------------------------------------------------------------------------
def install_panel(force=False):
    # 若已安装且不强制，直接跳过
    rc, _ = sh("command -v %s" % XUI_BIN, 10)
    if rc == 0 and not force:
        log("3x-ui 已存在，跳过安装")
        return True
    log("下载 3x-ui 官方安装脚本")
    rc, _ = run("curl -fsSL --connect-timeout 20 '%s' -o /root/3xui-install.sh && chmod +x /root/3xui-install.sh" % INSTALL_SCRIPT_URL, 120)
    if rc != 0:
        log("下载安装脚本失败（可能是 GitHub raw 限流，稍后重试即可）")
        return False
    log("以非交互模式安装 3x-ui")
    rc, out = run("XUI_NONINTERACTIVE=1 NONINTERACTIVE=1 bash /root/3xui-install.sh", 1800)
    if rc != 0:
        log("面板安装失败")
        return False
    return True


def read_install_credential(user_arg, pass_arg):
    """优先用命令行参数；否则读 install-result.env。返回 (用户, 密码)。"""
    if user_arg and pass_arg:
        return user_arg, pass_arg
    cred = {"XUI_USERNAME": None, "XUI_PASSWORD": None}
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    cred[k.strip()] = v.strip().strip("'").strip('"')
    if user_arg:
        cred["XUI_USERNAME"] = user_arg
    if pass_arg:
        cred["XUI_PASSWORD"] = pass_arg
    if not cred["XUI_USERNAME"] or not cred["XUI_PASSWORD"]:
        # 回退到面板默认（某些版本默认 admin/admin）
        cred = {"XUI_USERNAME": "admin", "XUI_PASSWORD": "admin"}
        log("未读取到账密，使用默认 admin/admin（若不对请用 --user/--password 指定）")
    return cred["XUI_USERNAME"], cred["XUI_PASSWORD"]


# ---------------------------------------------------------------------------
# 面板 API 客户端（CSRF + Cookie）
# ---------------------------------------------------------------------------
class Panel:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.csrf = None

    def _req(self, method, path, data=None, csrf=True):
        url = self.base + path
        hd = {"Content-Type": "application/json", "Accept": "application/json"}
        if csrf and self.csrf:
            hd["X-CSRF-Token"] = self.csrf
        body = json.dumps(data) if data is not None else None
        req = urllib.request.Request(url, data=body.encode() if body else None, headers=hd, method=method)
        try:
            r = self.op.open(req, timeout=30)
            return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""

    def get(self, path, csrf=True):
        return self._req("GET", path, csrf=csrf)

    def post(self, path, data=None, csrf=True):
        return self._req("POST", path, data, csrf=csrf)

    def login(self, user, pwd):
        resp = self.get("/csrf-token")
        try:
            self.csrf = json.loads(resp)["obj"]
        except Exception:
            self.csrf = None
        r = self.post("/login", {"username": user, "password": pwd})
        return '"success":true' in r

    def restartXray(self):
        return self.post("/panel/api/server/restartXrayService", {})

    def restartPanel(self):
        return self.post("/panel/api/setting/restartPanel", {})


def get_web_base_path():
    """从数据库读取 webBasePath，若失败则空（默认 /panel/ 或 /）。"""
    try:
        rc, out = sh("sqlite3 /etc/x-ui/x-ui.db \"SELECT value FROM settings WHERE key='webBasePath';\"", 10)
        if rc == 0:
            return out.strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# 构造 VLESS+Reality 入站 JSON（含踩坑修复点）
# ---------------------------------------------------------------------------
def build_inbound(port, remark, public_key, private_key):
    settings = {
        "clients": [],
        "decryption": "none",
        "fallbacks": [],
    }
    stream = {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
            "show": False,
            "dest": DEST,
            "xver": 0,
            "serverNames": DEST_SNI,
            "privateKey": private_key,
            "publicKey": public_key,          # 顶层公钥 -> vless 链接带 pbk
            "shortIds": SHORT_IDS,
            "spiderX": SPIDER_X,
            "minClientVer": MIN_CLIENT_VER,    # 兼容 Mihomo 等旧客户端
            # 3x-ui Clash 渲染依赖的 settings 子对象（否则 YAML 缺 public-key）
            "settings": {"publicKey": public_key, "fingerprint": FINGERPRINT, "spiderX": SPIDER_X},
        },
        "tcpSettings": {"acceptProxyProtocol": False, "header": {"type": "none"}},
    }
    sniffing = {"enabled": True, "destOverride": ["http", "tls", "quic"], "metadataOnly": False}
    return {
        "remark": remark,
        "port": port,
        "protocol": "vless",
        "tag": "inbound-%d-tcp" % port,
        "settings": json.dumps(settings),
        "streamSettings": json.dumps(stream),
        "sniffing": json.dumps(sniffing),
        "enable": True,
    }


def rand_port():
    while True:
        p = random.randint(30000, 60000)
        rc, _ = sh("ss -tlnp | grep ':%d ' >/dev/null" % p, 10)
        if rc != 0:  # 端口未被占用
            return p


def gen_keypair(p):
    """生成 Reality 密钥对。优先用面板 API；失败则用 xray x25519。返回 (private, public)。"""
    try:
        resp = p.get("/panel/api/server/getNewX25519Cert")
        obj = json.loads(resp).get("obj", {})
        if obj.get("privateKey") and obj.get("publicKey"):
            return obj["privateKey"], obj["publicKey"]
    except Exception:
        pass
    b, out = run("%s x25519 2>/dev/null | head -20" % XRAY_BIN, 30)
    priv = pub = ""
    for line in out.splitlines():
        if line.startswith("PrivateKey:"):
            priv = line.split(":", 1)[1].strip()
        if line.startswith("Password (PublicKey):"):
            pub = line.split(":", 1)[1].strip()
    if priv and pub:
        return priv, pub
    return None, None


def add_dummy_then_update_share(p, inbound_id, public_ip):
    """把入站地址改为 custom 公网 IP（避免链接出 localhost）。"""
    resp = p.get("/panel/api/inbounds/get/%d" % inbound_id)
    try:
        obj = json.loads(resp)["obj"]
    except Exception:
        return
    obj["shareAddrStrategy"] = "custom"
    obj["shareAddr"] = public_ip
    p.post("/panel/api/inbounds/update/%d" % inbound_id, obj)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="3X-UI + VLESS+Reality 一键部署")
    ap.add_argument("--ip", required=True, help="服务器公网 IP")
    ap.add_argument("--clients", type=int, default=3, help="客户端数量")
    ap.add_argument("--user", default="", help="面板用户名")
    ap.add_argument("--password", default="", help="面板密码")
    ap.add_argument("--reinstall", action="store_true", help="强制重装 3x-ui")
    args = ap.parse_args()
    public_ip = args.ip

    if os.geteuid() != 0:
        log("请用 root 运行")
        sys.exit(1)

    # 0) 安装 3x-ui
    if not install_panel(args.reinstall):
        sys.exit(1)

    user, pwd = read_install_credential(args.user, args.password)
    # 等待面板就绪
    log("等待面板启动...")
    for i in range(30):
        rc, _ = sh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:52590/ 2>/dev/null | grep -E '200|401|403' >/dev/null", 10)
        if rc == 0:
            break
        time.sleep(2)

    # 1) 登录面板
    wbp = get_web_base_path()
    base = "http://127.0.0.1:52590" + (wbp if wbp else "/")
    p = Panel(base)
    if not p.login(user, pwd):
        log("面板登录失败：账号 %s（请核对 --user/--password 或 install-result.env）" % user)
        sys.exit(1)
    log("面板登录成功。")

    # 2) 生成 Reality 密钥
    priv, pub = gen_keypair(p)
    if not priv:
        log("无法生成 Reality 密钥（xray 未就绪，稍后重试）")
        sys.exit(1)
    log("生成 Reality 密钥对成功。")

    # 3) 创建 VLESS+Reality 入站
    port = rand_port()
    remark = "vless-reality"
    body = build_inbound(port, remark, pub, priv)
    resp = p.post("/panel/api/inbounds/add", body)
    try:
        obj = json.loads(resp).get("obj", {})
        inbound_id = obj.get("id")
    except Exception:
        print(resp)
        inbound_id = None
    if not inbound_id:
        log("创建入站失败：%s" % resp[:300])
        sys.exit(1)
    log("已创建入站 id=%s port=%d" % (inbound_id, port))

    # 4) set shareAddr = 公网 IP
    add_dummy_then_update_share(p, inbound_id, public_ip)
    log("入站地址已设为 %s" % public_ip)

    # 5) 创建 N 个客户端，各自 uuid + subId
    created = []
    for i in range(1, args.clients + 1):
        email = "c%d" % i
        uuid = str(uuid_gen())
        subid = subid_gen()
        body = {
            "client": {"email": email, "uuid": uuid, "subId": subid,
                       "flow": FLOW, "enable": True},
            "inboundIds": [inbound_id],
        }
        resp = p.post("/panel/api/clients/add", body)
        if '"success":true' in resp:
            # 读取该邮箱在面板中的真实 uuid（面板可能用自己生成的 uuid）
            real_uuid = uuid
            try:
                gr = p.get("/panel/api/clients/get/%s" % email)
                real_uuid = json.loads(gr)["obj"]["client"].get("uuid", uuid)
            except Exception:
                pass
            created.append({"email": email, "subId": subid, "uuid": real_uuid})
            log("客户端 %s 已添加 (subId=%s uuid=%s)" % (email, subid, real_uuid))
        else:
            log("客户端 %s 添加失败：%s" % (email, resp[:200]))
    if not created:
        log("无可用的客户端，退出")
        sys.exit(1)

    # 6) 启用 Clash 订阅 + 自动检测
    resp = p.post("/panel/api/setting/all", {})
    try:
        settings = json.loads(resp)["obj"]
    except Exception as e:
        settings = {}
        log("读取设置失败：%s" % str(e))
    settings["subClashEnable"] = True
    settings["subClashAutoDetect"] = True
    p.post("/panel/api/setting/update", settings)
    log("已启用 Clash 订阅 (subClashEnable + subClashAutoDetect)。")

    # 7) 重启 xray 生效（Clash 订阅变更也最好重启面板）
    p.restartXray()
    p.restartPanel()
    log("已重启 xray 与面板，等待生效...")
    time.sleep(8)

    # 8) 输出三份（或多份）Clash 订阅
    print("\n" + "=" * 60)
    print("部署完成。对外节点：%s:%d  VLESS+Reality (%s)" % (public_ip, port, DEST))
    print("面板：http://%s:%s/  账号：%s" % (public_ip, "52590", user))
    print("=" * 60)
    for c in created:
        url = "http://%s:2096/clash/%s" % (public_ip, c["subId"])
        print("\n 用户(%s)  uuid=%s" % (c["email"], c["uuid"]))
        print("   Clash 订阅: %s" % url)


def uuid_gen():
    import uuid as _uuid
    return _uuid.uuid4()


def subid_gen():
    return hashlib.sha256(os.urandom(16)).hexdigest()[:10]


if __name__ == "__main__":
    main()
