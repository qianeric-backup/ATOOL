# -*- coding: utf-8 -*-
"""本地 mock 服务器: 复现心理测评平台全部关键接口, 供 GUI/headless 离线测试。

启动:
    python mock/mock_server.py [--port 8085]

特点:
- 响应保真: 直接回放抓取的原始报文(含站点特有的双层 JSON 编码)
- 状态仿真: SumitPaperInfo 后该量表 IsTest 翻转为已完成(持久化到 mock/mock_state.json)
- 登录放行: 任意账密+任意验证码均返回 Code=0, 不需要 ddddocr
"""
from __future__ import annotations

import json
import os
import re

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
DATA = HERE / "mock_data_writable" if False else HERE.parent / "mock_data"
STATE = HERE / "mock_state.json"
LOGIN_HTML = HERE.parent / "probe" / "login.html"

_lock = threading.Lock()


def _papers_allinfo() -> dict:
    """PaperID -> 原始响应文本"""
    out = {}
    for f in Path(DATA).glob("paper_allinfo_*.json"):
        m = re.match(r"paper_allinfo_([0-9a-f-]+)_(.+)\.json", f.name)
        if m:
            out[m.group(1)] = f.read_text(encoding="utf-8")
    return out


def _state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"submitted": {}, "sessions": {}}


def _save_state(s: dict):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def _publishtest_with_state(state: dict) -> str:
    raw = (Path(DATA) / "psytest_getpublishtest.json").read_text(encoding="utf-8")
    j = json.loads(raw)  # 外层已是普通 dict?  承载形式 文本里是 {"Code":0,...} 或 "{...}"
    if isinstance(j, str):
        j = json.loads(j)
    for pub in j.get("Data") or []:
        for it in pub.get("List") or []:
            pid = it.get("PaperID")
            rec = state["submitted"].get(pid)
            if rec:
                it["IsTest"] = 1
                it["IsCanTest"] = 0
    return json.dumps(json.dumps(j, ensure_ascii=False), ensure_ascii=False)


class Handler(BaseHTTPRequestHandler):
    server_version = "MockPsyServer/1.0"

    # ---------- 基础 ----------
    def _send(self, body: bytes, ctype="application/json; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _send_json_str(self, text: str):
        # 站点多数接口返回的是"字符串内嵌JSON"(双层编码), 直接回放原文
        self._send(text.encode("utf-8"))

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        out = {}
        for k, v in parse_qs(raw.decode("utf-8", "replace")).items():
            out[k] = v[0] if len(v) == 1 else v
        return out

    def log_message(self, fmt, *args):  # 简化日志
        sys.stderr.write("[mock] %s %s\n" % (self.headers.get("X-Mock", ""), fmt % args))

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/Home/Login"):
            html = LOGIN_HTML.read_text(encoding="utf-8") if LOGIN_HTML.exists() else DEFAULT_LOGIN
            self._send(html.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._send(b"mock", "text/plain", 200)

    # ---------- POST ----------
    def do_POST(self):
        u = urlparse(self.path)
        form = self._read_body()
        with _lock:
            state = _state()

            if u.path == "/Home/UserLogin":
                # 任意账密放行; 记录会话
                token = f"MOCK{os.urandom(6).hex()}"
                state["sessions"][token] = form.get("account", "?")
                _save_state(state)
                _resp(self, None,
                      {"Code": 0, "Message": "登录成功", "HomeUrl": "/Home/Index"},
                      set_cookie=f"ASP.NET_SessionId={token}")

            elif u.path == "/Home/CheckLogin":
                has = any(self.headers.get("Cookie", "").find(sid) >= 0
                          for sid in state["sessions"])
                _resp(self, None, {"Code": 1 if has else -1, "message": ""})

            elif u.path == "/Mine/GetMyInfo":
                _send_file(self, "mine_myinfo.json")

            elif u.path == "/PsyTest/GetPublishTest":
                self._send_json_str(_publishtest_with_state(state))

            elif u.path == "/PsyTest/GetPaperAllInfo":
                papers = _papers_allinfo()
                raw = papers.get(form.get("PaperID", ""))
                if raw:
                    self._send_json_str(raw)
                else:
                    _resp(self, None, {"Code": 1, "Message": "mock 无此量表数据 "
                                       + form.get("PaperID", "")})

            elif u.path == "/PsyTest/SumitPaperInfo":
                pid = form.get("PaperId", "")
                n_ans = form.get("TmpResult", "").count(";") or form.get("TmpResult", "").count("|") // 1
                state["submitted"][pid] = {
                    "start": form.get("StartDateTime"),
                    "end": form.get("EndDateTime"),
                    "answers": form.get("TmpResult", ""),
                }
                _save_state(state)
                _resp(self, None, {"Code": 0, "Message": "提交成功( MOCK )", "Data": []})
                sys.stderr.write(f"[mock] 收到提交 Paper={pid} TmpResult长度="
                                 f"{len(form.get('TmpResult',''))}\n")

            elif u.path == "/PsyTest/SaveTmpPaperInfo":
                state.setdefault("tmp", {})[form.get("PaperId", "")] = form.get("TmpResult", "")
                _save_state(state)
                _resp(self, None, {"Code": 0, "Message": "暂存成功"})

            elif u.path == "/PsyTest/GetGaugeClassifyInfo":
                _resp(self, None, {"Code": 0, "Message": "获取分页量表成功", "Data": []})

            else:
                _resp(self, None, {"Code": 0, "Message": "mock 默认放行: " + u.path})


def _resp(handler, _, payload: dict, set_cookie: str | None = None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie + "; Path=/")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except BrokenPipeError:
        pass


def _send_file(handler, name: str):
    p = Path(DATA) / name
    if p.exists():
        handler._send(p.read_bytes())
    else:
        _resp(handler, None, {"Code": 1, "Message": f"mock 缺数据文件 {name}"})


DEFAULT_LOGIN = """<!DOCTYPE html><html><head><title>登录</title></head><body>
<div class="mainbody">
<input id="log_txtusername"><input id="log_txtpassword" type="password">
<input id="log_txtYZM"><div id="code_box">Af3D</div>
<button onclick="Login()">登录</button></div>
<script src="/Scripts/jsencrypt.min.js"></script>
<script src="/Scripts/login.js"></script></body></html>"""


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8085)
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"[mock] 心理测评 mock 已启动: http://{a.host}:{a.port}")
    print(f"[mock] 数据目录: {DATA}")
    print(f"[mock] 接入方式: 工具站点地址填 http://{a.host}:{a.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
