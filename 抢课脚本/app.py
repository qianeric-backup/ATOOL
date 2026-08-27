#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建桥学院抢课助手（桌面 exe + 本地 Web 页面）
============================================
点击 exe → 启动本地 Web 服务 → 打开浏览器页面。
所有人工操作变成输入框；选课数据自动载入；到点自动抢课；
配置可导入导出（导出含当前登录态 Cookie）。

后端：Python 标准库 http.server（无第三方 Web 框架依赖）
选课系统：EAMS（https://eams.gench.edu.cn）
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
EAMS = "https://eams.gench.edu.cn"
EAMS_STUDENT = f"{EAMS}/student"
CS_API = f"{EAMS}/course-selection-api/api/v1/student/course-select"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")
PORT = 8765

# 全局状态（单用户，桌面场景足够）
STATE = {
    "session": requests.Session(),          # EAMS 会话（登录后）
    "token": "",                            # cs-course-select-student-token JWT
    "session_cookie_str": "",               # 完整 EAMS 会话 Cookie 串（供导出配置）
    "student_id": "",                       # 内部 studentId（如 157302）
    "student_code": "",                     # 学号
    "turns": [],                            # 开放轮次
    "courses": [],                          # 可选课程列表
    "rush_running": False,
    "rush_thread": None,
    "rush_log": [],                         # 抢课日志（最近 N 条）
    "rush_stop": False,
}


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    STATE["rush_log"].append(line)
    STATE["rush_log"] = STATE["rush_log"][-500:]
    print(line)


def session_cookie_str(s: requests.Session) -> str:
    """把 requests.Session 的 Cookie 拼成标准 Cookie 串（供导出配置）。"""
    parts = []
    for c in s.cookies:
        parts.append(f"{c.name}={c.value}")
    return "; ".join(parts)


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def api_headers(token=None, json_ct=False):
    h = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01",
         "Referer": f"{EAMS}/course-selection/", "X-Requested-With": "XMLHttpRequest"}
    if token:
        h["Authorization"] = token
    if json_ct:
        h["Content-Type"] = "application/json;charset=UTF-8"
    return h


# ----------------------------------------------------------------------
# EAMS 操作
# ----------------------------------------------------------------------
def ensure_token():
    """确保有有效的选课 token。
    策略：若 STATE["token"] 有效则直接用；否则用 SESSION Cookie 访问选课页自动换取。
    返回 True/False。
    """
    if STATE["token"]:
        try:
            r = requests.get(f"{CS_API}/multiple-students",
                             headers=api_headers(STATE["token"]), timeout=12,
                             allow_redirects=False)
            d = r.json()
            if d.get("result") == 0 and d.get("data"):
                STATE["student_id"] = str(d["data"][0]["id"])
                STATE["student_code"] = d["data"][0]["code"]
                return True
        except Exception:
            pass
    s = STATE["session"]
    try:
        r = s.get(f"{EAMS_STUDENT}/for-std/course-select", timeout=15, allow_redirects=False)
        if r.status_code in (301, 302, 307, 308):
            log("无法自动换取 token（SESSION 失效或未登录）")
            return False
        html = r.text
        token = ""
        m = re.search(r"course-selection/\?token=([^\"'\s]+)", html)
        if m:
            token = m.group(1)
        else:
            setck = r.headers.get("Set-Cookie", "")
            m2 = re.search(r"cs-course-select-student-token=([^;]+)", setck)
            if m2:
                token = m2.group(1)
            else:
                m3 = re.search(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", html)
                if m3:
                    token = m3.group(0)
        if not token:
            log("选课页内未发现 token 线索")
            return False
        STATE["token"] = token
        log("已自动换取选课 token")
        r2 = requests.get(f"{CS_API}/multiple-students", headers=api_headers(token), timeout=12,
                          allow_redirects=False)
        d2 = r2.json()
        if d2.get("result") == 0 and d2.get("data"):
            STATE["student_id"] = str(d2["data"][0]["id"])
            STATE["student_code"] = d2["data"][0]["code"]
            return True
    except Exception as e:
        log(f"自动换取 token 异常：{e}")
    return False


def eams_login(username: str, password: str):
    """EAMS 账密登录：取盐 → SHA1 → POST /student/login"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS})
    r = s.get(f"{EAMS_STUDENT}/login-salt", timeout=15)
    salt = r.text.strip()
    enc = sha1(f"{salt}-{password}")
    r = s.post(f"{EAMS_STUDENT}/login",
               data=json.dumps({"username": username, "password": enc, "captchaToken": ""}),
               headers={**api_headers(), "Content-Type": "application/json;charset=UTF-8",
                        "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS},
               timeout=20)
    data = r.json()
    if data.get("result") is True:
        STATE["session"] = s
        STATE["session_cookie_str"] = session_cookie_str(s)
        STATE["student_code"] = username
        ok = ensure_token()
        log(f"EAMS 登录成功：{username}（token {'已获取' if ok else '待 Cookie 补充'}）")
        return {"ok": True, "has_token": ok}
    if data.get("needCaptcha"):
        return {"ok": False, "need_captcha": True,
                "message": "触发滑块验证码，请在浏览器里登录一次 EAMS 后把 Cookie 粘贴进来"}
    return {"ok": False, "message": data.get("message", "登录失败")}


def eams_set_cookie(cookie_str: str):
    """用浏览器 EAMS Cookie 建立会话。
    只要 Cookie 在 EAMS 会话内有效（SESSION 或 token 任一有效）即可，
    后续步骤（轮次/课程/抢课）自动运行；token 缺失自动换取。
    """
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS})
    token = ""
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            s.cookies.set(k, v, domain="eams.gench.edu.cn", path="/")
            if k == "cs-course-select-student-token":
                token = v
    STATE["session"] = s
    STATE["session_cookie_str"] = "; ".join(
        f"{c.name}={c.value}" for c in s.cookies)
    if token:
        STATE["token"] = token
    ok = ensure_token()
    if ok:
        log(f"Cookie 有效（已获取选课 token）：{STATE['student_code']}（内部ID {STATE['student_id']}）")
        return {"ok": True, "student_code": STATE["student_code"],
                "student_id": STATE["student_id"],
                "note": "Cookie 已生效，轮次/课程/抢课可直接运行"}
    try:
        r = s.get(f"{EAMS_STUDENT}/", timeout=12, allow_redirects=False)
        if r.status_code in (301, 302, 307, 308):
            return {"ok": False, "message": "Cookie 已失效（SESSION 过期），请重新在浏览器登录 EAMS 后复制最新 Cookie"}
    except Exception as e:
        return {"ok": False, "message": f"Cookie 校验异常：{e}"}
    return {"ok": False, "message": "Cookie 中无有效登录态（SESSION 或 token），请重新复制"}


def cs_get(path, token=None, timeout=15):
    token = token or STATE["token"]
    return requests.get(CS_API + path, headers=api_headers(token), timeout=timeout,
                        allow_redirects=False)


def cs_post(path, payload, token=None, timeout=15):
    token = token or STATE["token"]
    h = api_headers(token, json_ct=True)
    return requests.post(CS_API + path, data=json.dumps(payload, ensure_ascii=False),
                         headers=h, timeout=timeout, allow_redirects=False)


def load_turns():
    """载入开放选课轮次；顺带确保 student_id 已获取"""
    if not STATE["token"]:
        return []
    if not STATE["student_id"]:
        r = cs_get("/multiple-students")
        try:
            d = r.json()
            if d.get("result") == 0 and d.get("data"):
                STATE["student_id"] = str(d["data"][0]["id"])
                STATE["student_code"] = d["data"][0]["code"]
        except Exception:
            return []
    r = cs_get(f"/open-turns/{STATE['student_id']}")
    try:
        d = r.json()
        if d.get("result") == 0:
            STATE["turns"] = d.get("data", [])
            log(f"开放轮次：{len(STATE['turns'])} 个")
            return STATE["turns"]
    except Exception as e:
        log(f"载入轮次失败：{e}")
    return []


def load_courses(turn_id):
    """载入某轮次的可选课程（query-lesson 返回 lessons）"""
    if not STATE["token"] or not STATE["student_id"]:
        return {"ok": False, "message": "未登录"}
    payload = {}
    r = cs_post(f"/query-lesson/{STATE['student_id']}/{turn_id}", payload)
    try:
        d = r.json()
        if d.get("result") == 0:
            lessons = d.get("data", {}).get("lessons", []) or d.get("data", [])
            STATE["courses"] = lessons
            log(f"可选课程：{len(lessons)} 条")
            return {"ok": True, "count": len(lessons), "courses": lessons}
        return {"ok": False, "message": d.get("message", "查询失败")}
    except Exception as e:
        return {"ok": False, "message": f"查询异常：{e}"}


# ----------------------------------------------------------------------
# 抢课线程
# ----------------------------------------------------------------------
def rush_worker(turn_id, lesson_id, student_id, interval, max_times):
    """高频提交 add-request 直到成功/停止/次数用尽"""
    payload = {
        "studentAssoc": int(student_id),
        "courseSelectTurnAssoc": int(turn_id),
        "requestMiddleDtos": [{"lessonAssoc": int(lesson_id),
                               "virtualCost": "",
                               "scheduleGroupAssoc": None}],
        "coursePackAssoc": None,
    }
    log(f"抢课开始：lessonId={lesson_id} turnId={turn_id} 间隔={interval}s 最多{max_times}次")
    for i in range(1, max_times + 1):
        if STATE["rush_stop"]:
            log("抢课已手动停止")
            break
        try:
            r = cs_post("/add-request", payload)
            data = {}
            try:
                data = r.json()
            except Exception:
                pass
            if r.status_code == 200 and data.get("result") == 0:
                log(f"[成功] 第{i}次提交成功 result=0")
                for _ in range(5):
                    if STATE["rush_stop"]:
                        break
                    time.sleep(2)
                    result = cs_get(f"/add-drop-response/{student_id}/{data.get('data', {}).get('id', '')}")
                    try:
                        rd = result.json()
                        rr = rd.get("data", {})
                        if rr.get("success") is True:
                            log(f"[√] 选课成功：{json.dumps(rr, ensure_ascii=False)[:200]}")
                            break
                        elif rr.get("success") is False:
                            log(f"[x] 选课被拒：{rr.get('errorMessage', {}).get('text', '')}")
                            break
                    except Exception:
                        pass
                break
            elif r.status_code == 200:
                log(f"[{i}] 提交未成功：{r.text[:120]}")
            else:
                log(f"[{i}] HTTP {r.status_code} {r.text[:120]}")
        except Exception as e:
            log(f"[{i}] 异常：{e}")
        if i < max_times:
            time.sleep(interval)
        else:
            log("已达最大次数，停止")
    STATE["rush_running"] = False
    log("抢课线程结束")


def start_rush(turn_id, lesson_id, interval, max_times):
    if STATE["rush_running"]:
        return {"ok": False, "message": "抢课已在运行"}
    STATE["rush_stop"] = False
    STATE["rush_running"] = True
    STATE["rush_log"] = []
    t = threading.Thread(target=rush_worker,
                         args=(turn_id, lesson_id, STATE["student_id"], interval, max_times),
                         daemon=True)
    t.start()
    return {"ok": True}


# ----------------------------------------------------------------------
# 本地 Web 服务
# ----------------------------------------------------------------------
WEB_DIR = None


def resolve_web_dir():
    global WEB_DIR
    if WEB_DIR:
        return WEB_DIR
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "web")
    if os.path.isdir(d):
        WEB_DIR = d
        return d
    return base


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        d = resolve_web_dir()
        full = os.path.join(d, path.lstrip("/"))
        if not os.path.isfile(full) or ".." in path:
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1]
        ct = {"html": "text/html; charset=utf-8", "js": "application/javascript; charset=utf-8",
              "css": "text/css; charset=utf-8"}.get(ext.lstrip("."), "application/octet-stream")
        body = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            self._send_file("/index.html")
        elif p == "/api/status":
            self._send_json({
                "ok": True,
                "logged_in": bool(STATE["token"]),
                "student_code": STATE["student_code"],
                "student_id": STATE["student_id"],
                "turns": STATE["turns"],
                "course_count": len(STATE["courses"]),
                "rush_running": STATE["rush_running"],
                "rush_log": STATE["rush_log"],
            })
        elif p == "/api/turns":
            turns = load_turns()
            self._send_json({"ok": True, "turns": turns})
        elif p == "/api/export":
            self._send_json({
                "ok": True,
                "session_cookie_str": STATE["session_cookie_str"],
                "token": STATE["token"],
                "student_code": STATE["student_code"],
                "student_id": STATE["student_id"],
                "turns": STATE["turns"],
            })
        else:
            self._send_file(p)

    def do_POST(self):
        p = self.path.split("?")[0]
        body = self._read_json_body()
        if p == "/api/login":
            if body.get("cookie"):
                res = eams_set_cookie(body["cookie"])
            else:
                res = eams_login(body.get("username", ""), body.get("password", ""))
            self._send_json(res)
        elif p == "/api/turns":
            self._send_json({"ok": True, "turns": load_turns()})
        elif p == "/api/courses":
            turn_id = body.get("turnId") or (STATE["turns"][0]["id"] if STATE["turns"] else "")
            self._send_json(load_courses(turn_id))
        elif p == "/api/rush/start":
            res = start_rush(body.get("turnId"), body.get("lessonId"),
                             float(body.get("interval", 0.5)), int(body.get("maxTimes", 200)))
            self._send_json(res)
        elif p == "/api/rush/stop":
            STATE["rush_stop"] = True
            self._send_json({"ok": True})
        elif p == "/api/log":
            self._send_json({"ok": True, "rush_log": STATE["rush_log"]})
        else:
            self._send_json({"ok": False, "message": "未知 API"}, 404)


def main():
    resolve_web_dir()
    # 动态分配空闲端口：从 8765 起递增，使每个实例独立端口（支持多开）
    import socket
    port = PORT
    for _ in range(100):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            s.close()
            break
        except OSError:
            port += 1
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"抢课助手已启动：{url}")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
