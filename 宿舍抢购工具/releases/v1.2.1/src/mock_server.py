# -*- coding: utf-8 -*-
"""
本地 mock API 服务器 —— 模拟上海建桥学院迎新系统后端, 用于本地冒烟测试。

功能:
  * 完整模拟抢购流程接口: login / get_gbdorm / timestamp / kaptcha / set_dorm / gbinfo_status
  * kaptcha 验证码由本地 PIL 生成(答案记录在内存), 验证 OCR -> 提交全链路
  * 提供调试接口 GET /api/_debug/captcha_answer 返回当前验证码答案(测试辅助)
  * 同时托管 mock_site/ 下的前端静态资源, 本地浏览器可打开页面

用法:
  python mock_server.py [--port 8765] [--open 2026-08-20 10:00:00]
默认开放时间为过去时间(立即开抢); 传 --open 可模拟未来开放等待场景。
"""
import argparse
import io
import json
import os
import random
import string
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE_DIR, "mock_site")

# 模拟数据: 与真实接口返回结构一致 (来自在线抓包)
DORM_INFO = {
    "college": "信息技术学院",
    "uhard": False,
    "img": [
        {"id": 23, "did": 6, "img": "statics/dorm/7-1.jpg", "del": False},
        {"id": 24, "did": 6, "img": "statics/dorm/7-2.jpg", "del": False},
        {"id": 25, "did": 6, "img": "statics/dorm/7-31.jpg", "del": False},
    ],
    "sex": "男",
    "sum": 30,
    "label": "新宿舍(信息技术学院)",
    "type": "2",
    "price": "7800",
    "slide": 23,
    "buysdt": "2026-08-20 10:00:00",
    "buyedt": "2026-08-20 15:00:00",
    "time": None,  # 运行时填充
    "value": 83,
    "status": True,
}
STU_INFO = {
    "uname": "张三", "depname": "信息技术学院", "majorname": "计算机科学与技术",
    "paydorm": "4800", "paystudy": "32000", "paywork": "1600", "dormname": "普通宿舍",
    "ustep": "17", "uenroll": "1", "uhard": "0",
}
CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 排除易混淆字符


class MockState:
    def __init__(self, open_dt):
        self.open_dt = open_dt
        self.captchas = {}           # sid -> 验证码答案 (按会话隔离, 支持多账号并发)
        self.order = None

    def set_captcha(self, ans, sid="default"):
        self.captchas[sid] = ans

    def check_captcha(self, ans, sid="default"):
        cur = self.captchas.get(sid)
        if cur is None:
            return False
        self.captchas.pop(sid, None)  # 验证码一次性
        return str(ans).upper() == str(cur).upper()


STATE = MockState("2020-01-01 00:00:00")  # 默认已开放


def _load_font(size):
    """加载系统粗体字体; 找不到则回退默认字体。"""
    from PIL import ImageFont
    for cand in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\timesbd.ttf",
                 r"C:\Windows\Fonts\Arial.ttf", r"C:\Windows\Fonts\consolab.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def gen_captcha():
    """PIL 生成 5 位验证码 JPEG (粗体+轻微旋转+细干扰线, 模拟 kaptcha 风格), 返回 (bytes, answer)。"""
    from PIL import Image, ImageDraw, ImageFont
    ans = "".join(random.choice(CAPTCHA_CHARS) for _ in range(5))
    w, h = 186, 60          # 宽度给足, 避免最后一个字符旋转后被裁剪
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # 细而浅的干扰线
    for _ in range(3):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        draw.line([(x1, y1), (x2, y2)], fill=(random.randint(160, 205),) * 3, width=1)
    # 深色粗体字符, 单字符旋转后粘贴 (kaptcha 风格)
    font = _load_font(32)
    cell_w, cell_h = 36, 46   # 单字符画布, 容纳 ±15° 旋转
    step = 33
    for i, ch in enumerate(ans):
        tmp = Image.new("L", (cell_w, cell_h), 255)
        td = ImageDraw.Draw(tmp)
        td.text((0, 0), ch, font=font, fill=random.randint(30, 90))
        tmp = tmp.rotate(random.randint(-12, 12), expand=True, fillcolor=255)
        x = 8 + i * step
        y = random.randint(2, 8)
        img.paste(Image.merge("RGB", (tmp, tmp, tmp)), (x, y))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), ans


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"[mock] {self.command} {self.path} -> {fmt % args}")

    # ---------- 工具 ----------
    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
            ctype = "application/json; charset=utf-8"
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(ln) if ln else b""
        return parse_qs(raw.decode("utf-8"))

    def _session_id(self, issue=False):
        """从 Cookie 取 JSESSIONID 作为会话标识; issue=True 且无 cookie 时生成新会话。"""
        import uuid
        sid = None
        ck = self.headers.get("Cookie") or ""
        for part in ck.split(";"):
            part = part.strip()
            if part.lower().startswith("jsessionid="):
                sid = part.split("=", 1)[1]
                break
        if sid is None and issue:
            sid = "mock-" + uuid.uuid4().hex[:12]
            self._pending_sid = sid
            self.send_header("Set-Cookie", f"JSESSIONID={sid}; Path=/")
        return sid or "default"

    # ---------- 路由 ----------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/stu/timestamp":
            self._send(200, str(int(time.time() * 1000)))
        elif path == "/api/pc/common/kaptcha":
            data, ans = gen_captcha()
            STATE.set_captcha(ans, self._session_id())
            self._send(200, data, "image/jpeg")
        elif path == "/api/_debug/captcha_answer":
            self._send(200, {"answer": STATE.captchas.get(self._session_id())})
        elif path == "/api/_debug/order":
            self._send(200, {"order": STATE.order})
        elif path == "/api/_debug/reset":
            STATE.order = None
            self._send(200, {"reset": True})
        elif path.startswith("/api/"):
            self._send(404, {"suc": False, "emsg": f"mock 未实现 GET {path}"})
        else:
            self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        if path == "/api/stu/login":
            enrollid = (body.get("enrollid") or [""])[0]
            idcard = (body.get("idcard") or [""])[0]
            if enrollid and idcard and enrollid != "fail":
                self.send_response(200)
                sid = self._session_id(issue=True)  # 每个账号独立会话 -> 独立验证码
                self.send_header("Content-Length", "1")
                self.end_headers()
                self.wfile.write(b"1")
            else:
                self._send(200, "fail")
        elif path == "/api/stu/get_gbdorm":
            info = dict(DORM_INFO)
            info["time"] = int(time.time() * 1000)
            self._send(200, [info])
        elif path == "/api/stu/get_stuvo":
            self._send(200, dict(STU_INFO))
        elif path == "/api/stu/get_studentbasic":
            self._send(200, {"id": 123, "enrollid": "2631141739", "uname": "张三"})
        elif path == "/api/stu/gbinfo_status":
            self._send(200, [STATE.order] if STATE.order else [])
        elif path == "/api/stu/if_gborder":
            self._send(200, {"uname": "张三", "udorm": 1, "usex": "男",
                             "gbpayend": False, "enrollid": "2631141739",
                             "depname": "信息技术学院", "order": 1 if STATE.order else 0})
        elif path == "/api/stu/set_dorm":
            did = (body.get("did") or [""])[0]
            yzm = (body.get("yzmstr") or [""])[0]
            if not STATE.check_captcha(yzm, self._session_id()):
                self._send(200, {"suc": False, "msg": None, "emsg": "验证码错误", "code": 505, "data": "", "ct": int(time.time())})
                return
            # 模拟时间未开放
            if STATE.open_dt:
                try:
                    open_ts = time.mktime(time.strptime(STATE.open_dt, "%Y-%m-%d %H:%M:%S"))
                    if time.time() < open_ts:
                        self._send(200, {"suc": False, "msg": None, "emsg": "当前时间暂未开放", "code": 507, "data": "", "ct": int(time.time())})
                        return
                except ValueError:
                    pass
            STATE.order = {"dormid": int(did), "action": "下单", "price": "7800"}
            self._send(200, {"suc": True, "msg": None, "emsg": None, "code": 0,
                             "data": "", "ct": int(time.time())})
        elif path == "/api/stu/loginout":
            self._send(200, "1")
        else:
            self._send(404, {"suc": False, "emsg": f"mock 未实现 POST {path}"})

    # ---------- 静态文件 (mock_site/) ----------
    def _serve_static(self, path):
        # /yu/xxx -> mock_site/xxx ; 缺省返回 login.html (SPA 壳)
        if path in ("/", "/yu", "/yu/"):
            path = "/login.html"
        elif path.startswith("/yu/"):
            path = path[len("/yu/"):]
        else:
            path = path.lstrip("/")
        fp = os.path.join(SITE_DIR, path)
        if not os.path.isfile(fp):
            fp = os.path.join(SITE_DIR, "login.html")
        ext = os.path.splitext(fp)[1].lower()
        ctype = {"html": "text/html; charset=utf-8", "js": "application/javascript; charset=utf-8",
                 "css": "text/css; charset=utf-8", "png": "image/png", "jpg": "image/jpeg",
                 "jpeg": "image/jpeg", "ico": "image/x-icon"}.get(ext, "application/octet-stream")
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype)


def main():
    ap = argparse.ArgumentParser(description="本地 mock 服务器 (迎新系统后端模拟)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", default=None,
                    help="模拟开放时间 'YYYY-MM-DD HH:MM:SS' (默认过去时间=立即开放)")
    args = ap.parse_args()
    if args.open:
        STATE.open_dt = args.open
        # 同步对外返回的开放/截止时间, 让抢购脚本与 mock 放行逻辑一致
        DORM_INFO["buysdt"] = args.open
        import datetime
        DORM_INFO["buyedt"] = (datetime.datetime.strptime(args.open, "%Y-%m-%d %H:%M:%S")
                               + datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[mock] 服务器已启动: http://127.0.0.1:{args.port}")
    print(f"[mock] 模拟开放时间: {STATE.open_dt} | 验证码调试: /api/_debug/captcha_answer")
    print(f"[mock] 前端页面: http://127.0.0.1:{args.port}/yu/mp/dorm_buy_two")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock] 已停止")


if __name__ == "__main__":
    main()
