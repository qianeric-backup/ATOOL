# -*- coding: utf-8 -*-
"""
激活校验模块 —— 给打包后的 exe 加"激活 KEY 才能使用"保护。

校验分层:
  1) 固定KEY   : 必须匹配内置主哈希 (SHA-256, 源码只存不可逆哈希, 不存明文)
  2) 机器码绑定: 若使用者在机器上生成的 KEY 是绑过机器码的,
                则 KEY 与该机器码绑定 (防止 KEY 跨机器拷贝).
                绑定KEY的派生种子为内置编码种子(非明文), 无需外部许可证即可校验.

激活方式:
  - CLI:  grab_dorm.exe --key "XXXX-...-XXXX"
  - GUI:  启动时输入 KEY
  - 授权方: 用 gui_key/generate_key.py 生成绑定KEY; 也可选配 license.key 覆盖内置种子

安全说明:
  - 固定KEY明文不以明文硬编码, 主哈希不可逆; 绑定KEY派生种子用 XOR+base64 编码内置,
    提高门槛(无法直接字符串搜到明文), 但仍属客户端可提取的密钥材料。
  - 可选: 放置 license.key(或 env GRAB_DORM_LICENSE) 可覆盖内置种子(更换密钥)。
  - 纯客户端保护只能提高门槛, 无法对抗顶级逆向, 根治需服务端授权。
"""
import hashlib
import os
import platform
import uuid

# ===== 固定KEY 的不可逆 SHA-256 (用于比对用户输入, 无法由此反推明文) =====
# sha256("RSO-QIANGSS-2026")
_MASTER_HASH = "9b29fa1a81eede50715c2eb757b66a3272b05270194b1347fa4278e3b8d69c23"

# ===== 内置的固定KEY种子 (XOR+base64 编码, 非明文; 供绑定KEY派生/校验) =====
#   seed = "RSO-QIANGSS-2026"
#   编码: xor(seed, _SEED_XKEY) 后 base64。可直接解码得到固定KEY明文。
_EMBED_MASTER = "ASJ9bSsiWGIADUdCPwtqHw=="
_SEED_XKEY = bytes([0x53, 0x71, 0x32, 0x40, 0x7A, 0x6B, 0x19, 0x2C,
                    0x47, 0x5E, 0x14, 0x6F, 0x0D, 0x3B, 0x58, 0x29])


def embedded_master() -> str:
    """解码内置的固定KEY种子(供绑定KEY派生/校验)。不依赖外部许可证文件。"""
    try:
        import base64
        raw = base64.b64decode(_EMBED_MASTER)
        dec = bytes((b ^ _SEED_XKEY[i % len(_SEED_XKEY)] for i, b in enumerate(raw)))
        return dec.decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _license_path() -> str:
    """返回许可证文件路径: 优先 env GRAB_DORM_LICENSE, 否则默认当前目录 license.key。"""
    return os.environ.get("GRAB_DORM_LICENSE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "license.key")


def load_license_key() -> str:
    """从外部许可证文件读取固定KEY明文。读不到返回空串。

    授权方通过 generate_key.py / 单独命令生成 license.key 并另行分发给使用者。
    """
    try:
        with open(_license_path(), "r", encoding="utf-8") as f:
            k = f.read().strip()
        return k
    except Exception:  # noqa: BLE001
        return ""


def machine_fingerprint() -> str:
    """返回相对稳定的机器标识指纹 (Windows: 网卡MAC + 主机名; 其它: uuid)。"""
    try:
        if platform.system() == "Windows":
            macs = []
            import subprocess
            out = subprocess.run(["getmac", "/fo", "csv", "/nh"],
                                 capture_output=True, text=True, timeout=5).stdout
            for line in out.strip().splitlines():
                parts = line.split('","')
                if len(parts) >= 2:
                    mac = parts[0].strip('"')
                    macs.append(mac)
            base = "|".join(sorted(macs)) or "no-mac"
            return base + "|" + (platform.node() or "host")
        return str(uuid.getnode()) + "|" + (platform.node() or "host")
    except Exception:  # noqa: BLE001
        try:
            return str(uuid.getnode())
        except Exception:  # noqa: BLE001
            return "unknown"


def fixed_key_ok(key: str) -> bool:
    """校验用户输入的KEY: 其 SHA-256 需等于内置主哈希(不可逆比对, 不落明文)。"""
    if not key:
        return False
    return _sha(key.strip()) == _MASTER_HASH


def _bound_master() -> str:
    """绑定KEY派生所需的固定KEY明文。
    默认使用内置编码种子(解码自 _EMBED_MASTER, 不依赖外部文件)。
    若存在外部许可证 license.key(或 env GRAB_DORM_LICENSE), 则优先用外部值(便于更换密钥)。
    """
    external = load_license_key()
    if external:
        return external
    return embedded_master()


def is_binding_key(key: str) -> bool:
    """判断是否为机器码绑定KEY(形如 固定-绑定段)。需要外部许可证提供前缀。"""
    master = _bound_master()
    if not master:
        return False
    k = key.strip()
    return k.startswith(master + "-") and len(k) > len(master) + 2


def bound_key_ok(key: str, machine: str) -> bool:
    """校验机器码绑定KEY是否匹配给定机器指纹。依赖许可证提供的固定KEY。"""
    master = _bound_master()
    if not master:
        return False
    k = key.strip()
    if not (k.startswith(master + "-") and len(k) > len(master) + 2):
        return False
    suffix = k[len(master) + 1:]
    return suffix == _sha(master + "::" + machine)[:32]


def validate(key: str) -> bool:
    """总校验: 固定KEY(哈希比对, 不依赖许可证) 或 (本机)机器码绑定KEY 任一通过即可。"""
    if not key:
        return False
    if fixed_key_ok(key):
        return True
    if bound_key_ok(key, machine_fingerprint()):
        return True
    return False


def generate_key(machine=None):
    """为授权机器生成绑定KEY (授权方使用)。
    不传 machine 或空 -> 返回通用固定KEY(取决于许可证文件是否存在)。
    传入 machine(使用者运行 get-machine 获取的指纹) -> 生成仅该机器有效的KEY。
    """
    master = _bound_master()
    if not machine:
        return master  # 固定KEY来自许可证, 未配置则空
    if not master:
        return ""
    suffix = _sha(master + "::" + machine)[:32]
    return f"{master}-{suffix}"


def get_machine():
    """供使用者在目标机器上运行以获取机器指纹, 授权方据此签发绑定KEY。"""
    return machine_fingerprint()


def require_activation(key, *, ask_fn=None):
    """统一的激活门卫: 校验 key; 若 key 无效且提供 ask_fn(用于GUI弹窗), 则调用 ask_fn 索取。
    返回校验通过的 key; 全部失败返回 None。"""
    try_key = (key or "").strip()
    # 先试给定的 key (CLI)
    if try_key and validate(try_key):
        return try_key
    # GUI/交互索取
    if ask_fn is not None:
        for _ in range(3):
            entered = ask_fn()
            if entered and validate(entered):
                return entered
    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "get-machine":
        print(f"本机机器指纹: {get_machine()}")
        sys.exit(0)
    print("激活模块使用:")
    print("  python activation.py get-machine   # 在目标机器取机器指纹, 用于签发绑定KEY")
    print("  python generate_key.py --machine <指纹>   # 授权方签发绑定KEY")
    print("  python generate_key.py --license   # 授权方生成 license.key (固定KEY材料)")
