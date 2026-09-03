#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建桥学院抢课助手（tkinter 原生 UI，桌面 exe）v0.3.0
================================================
双击 exe → 直接弹出 tkinter 主窗口（无需浏览器）。
功能：登录（Cookie）、实时状态、选课轮次、课程分页列表、
      抢课控制（预热/高频/成功即停）、运行日志、保活常驻。
v0.3.0 优化（基于 course-selection-api 逆向确认）：
  - add-request 响应 data 即 requestId（原按 data.id 解析会取空, 轮询失联）已修正
  - add-drop-response 轮询 10×2s + resend 自动重提（前端会要求重发, 现自动处理）
  - 频控(RequestLimitException)自适应退避 3→30s + 请求节拍 ±25% 抖动
  - /std-count 容量预检：满员低频等待, 连续满员自动停止, 不再空转狂打
  - 令牌过期/401 立即止损并提示重新导入 Cookie
  - 登录协议改为 course-selection-api（login-salt+login, SHA1(salt-明文), needCaptcha 流程）
  - 课程搜索框接线（lessonNameOrCode/courseNameOrCode）
  - 开抢前服务器时钟复校（>2min 未校准自动重校）
后端复用 app.py 的 EAMS 逻辑（纯本地解析 + 网络调用分离）。
"""
import base64
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time

import requests

# GUI 依赖（tkinter）Linux 下可能未装 → 优雅降级到 CLI 模式
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    TK_OK = True
except Exception:
    tk = ttk = messagebox = scrolledtext = None
    TK_OK = False

# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
EAMS = "https://eams.gench.edu.cn"
EAMS_STUDENT = f"{EAMS}/student"
CS_API = f"{EAMS}/course-selection-api/api/v1/student/course-select"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")

# 全局状态（单用户，桌面场景足够）
STATE = {
    "session": requests.Session(),
    "token": "",
    "session_cookie_str": "",
    "student_id": "",
    "student_code": "",
    "turns": [],
    "courses": [],
    "rush_running": False,
    "rush_thread": None,
    "rush_log": [],
    "rush_stop": False,
    "server_offset": 0.0,
    "server_time_at": 0.0,
    "rush_attempts": 0,
    "rush_last": "",
    "course_total": 0,
    "course_page": 1,
}


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    STATE["rush_log"].append(line)
    STATE["rush_log"] = STATE["rush_log"][-500:]
    print(line)


def session_cookie_str(s: requests.Session) -> str:
    parts = []
    for c in s.cookies:
        parts.append(f"{c.name}={c.value}")
    return "; ".join(parts)


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def api_headers(token=None, json_ct=False):
    h = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01",
         "Origin": EAMS, "Referer": f"{EAMS}/course-selection/",
         "X-Requested-With": "XMLHttpRequest"}
    if token:
        h["Authorization"] = token
    if json_ct:
        h["Content-Type"] = "application/json;charset=UTF-8"
    return h


# Linux 适配: 中文字体回退（Windows 的微软雅黑在 Linux 无 → 按可用字体挑选）
# 注意: tk.font.families() 必须在创建 root 窗口后调用（实测教训），
#       所以模块期只给默认值, TkApp.__init__ 里再真正挑选。
UI_FONT = ("TkDefaultFont", 9)


def _pick_ui_font():
    """在 Tk root 建立后调用: 依可用家族选中文字体（含 Serif 兜底）。"""
    global UI_FONT
    try:
        import tkinter.font  # 显式导入子模块（tk.font 属性不会自动出现）
        fams = set(x.lower() for x in tk.font.families())
    except Exception:
        return
    for f in ("microsoft yahei", "noto sans cjk sc", "noto sans sc",
              "wenquanyi zen hei", "source han sans sc", "pingfang sc",
              "noto serif cjk sc", "dejavu sans"):
        if f in fams:
            UI_FONT = (f, 9)
            return
    for fam in fams:  # 通用兜底: 任意 CJK 家族
        if any(k in fam for k in ("cjk", "wenquanyi", "han")):
            UI_FONT = (fam, 9)
            return
    # Tk 枚举不到 .ttc 集合字体(实测) → 用 fc-match 找系统 CJK 并验证 Tk 真的采纳
    fam = _fc_probe_cjk()
    if fam:
        UI_FONT = (fam, 9)


def _fc_probe_cjk():
    """fc-match 找系统级 CJK 字体, 并确认 Tk 渲染确有差异才采用。
    （实测: 本机 TkDefaultFont 的 actual family 就是 Noto Sans CJK SC ——
      fontconfig 默认已解析到 CJK, 此时保持默认即最优。）"""
    try:
        import subprocess
        import tkinter.font
        try:
            d_fam = tkinter.font.Font(family="TkDefaultFont", size=12).actual("family")
            if any(k in (d_fam or "").lower() for k in
                   ("cjk", "wenquanyi", "han", "hei", "song", "kai", "ming")):
                return None   # 默认字体本身就是 CJK → 无需替换
        except Exception:
            pass
        for cand in ("Noto Sans CJK SC", "Noto Sans CJK JP",
                     "WenQuanYi Zen Hei", "Noto Serif CJK SC"):
            r = subprocess.run(["fc-match", "--format=%{family}", cand],
                               capture_output=True, text=True, timeout=3)
            fam = (r.stdout or "").strip()
            if not fam or not any(k in fam.lower() for k in ("cjk", "wenquanyi", "han")):
                continue
            f1 = tkinter.font.Font(family=fam, size=12)
            f2 = tkinter.font.Font(family="TkDefaultFont", size=12)
            if f1.actual("family").lower() == fam.lower() or \
               f1.measure("中文测试") != f2.measure("中文测试"):
                return fam    # Tk 确实按该家族渲染 → 采纳
    except Exception:
        pass
    return None


def jwt_exp(token: str):
    if not token:
        return None
    for mod in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            seg = token.strip().strip('"').strip("'").split(".")[1]
            seg += "=" * (-len(seg) % 4)
            payload = json.loads(mod(seg.encode("utf-8")))
            exp = int(payload.get("exp", 0))
            if exp:
                return exp
        except Exception:
            continue
    return None


def get_server_time():
    try:
        r = requests.get(f"{CS_API}/getCurrentDateTime",
                         headers=api_headers(STATE["token"]), timeout=8,
                         allow_redirects=False)
        d = r.json()
        if d.get("result") == 0 and d.get("data"):
            st = str(d["data"])
            import datetime
            try:
                server_ts = datetime.datetime.strptime(st, "%Y-%m-%d %H:%M:%S").timestamp()
                local_ts = time.time()
                STATE["server_offset"] = server_ts - local_ts
                STATE["server_time_at"] = local_ts   # v0.3: 校准时间戳(供开抢前复校)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def eams_login(username: str, password: str):
    """直登选课服务（course-selection-api, v0.3 修正）。
    协议(逆向确认): GET /login-salt/{user} -> salt(uuid);
    password = SHA1(salt + "-" + 明文); POST /login {username,password,captchaToken,captcha}
    失败返回 needCaptcha=true + captchaToken, 需先取验证码图(login-captcha/{token})
    并人工识别后重提。成功 result==0 且 data.token 即选课 JWT。"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS}/course-selection/",
                      "Origin": EAMS})
    try:
        r = s.get(f"{CS_API}/login-salt/{username}", timeout=15,
                  headers=api_headers(), allow_redirects=False)
        b = r.json()
        salt = (b or {}).get("data")
    except Exception as e:
        return {"ok": False, "message": f"取盐失败：{e}"}
    if not salt:
        return {"ok": False, "message": f"取盐失败：{b or r.status_code}"}
    enc = sha1(f"{salt}-{password}")
    try:
        r = s.post(f"{CS_API}/login",
                   data=json.dumps({"username": username, "password": enc,
                                    "captchaToken": "", "captcha": ""}),
                   headers=api_headers(json_ct=True), timeout=20, allow_redirects=False)
        data = r.json()
    except Exception as e:
        return {"ok": False, "message": f"登录请求失败：{e}"}
    if data.get("result") == 0 and data.get("data", {}).get("token"):
        tok = data["data"]["token"]
        STATE["session"] = s
        STATE["session_cookie_str"] = session_cookie_str(s)
        STATE["token"] = tok
        STATE["student_code"] = username
        log(f"直登成功：{username}（token {tok[:20]}...）")
        return {"ok": True, "has_token": True, "message": "直登成功"}
    if data.get("data", {}).get("needCaptcha"):
        ct = data["data"].get("captchaToken", "")
        return {"ok": False, "need_captcha": True, "captcha_token": ct,
                "message": "凭据不匹配/需验证码（captchaToken=%s）。"
                           "请在浏览器登录选课页后复制 Cookie 粘贴导入。" % ct}
    return {"ok": False, "message": (data.get("message") or "登录失败")[:200]}


def eams_set_cookie(cookie_str: str):
    """纯本地解析 Cookie（零网络），必须含 cs-course-select-student-token。
    studentId 由 load_turns 按需获取。"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS})
    # 换 Cookie 即换身份：必须清掉上一账号的 student_id/轮次/课程缓存，
    # 否则 load_turns 会沿用旧账号内部 ID —— 以旧账号身份抢课/查询（实测脏数据坑）
    STATE["student_id"] = ""
    STATE["student_code"] = ""
    STATE["turns"] = []
    STATE["courses"] = []
    STATE["course_total"] = 0
    STATE["course_page"] = 1
    token = ""
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            s.cookies.set(k, v, domain="eams.gench.edu.cn", path="/")
            if k.strip() == "cs-course-select-student-token":
                token = v.strip().strip('"').strip("'")
    STATE["session"] = s
    STATE["session_cookie_str"] = "; ".join(
        f"{c.name}={c.value}" for c in s.cookies)
    if not token:
        return {"ok": False,
                "message": "Cookie 缺少 cs-course-select-student-token（选课 token）。"
                           "请在浏览器打开选课页后按 F12 → Network → 复制包含该 token 的完整 cookie 整行。"}
    STATE["token"] = token
    code = ""
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p.encode("utf-8")))
        code = str(payload.get("username") or "")
    except Exception:
        pass
    if code:
        STATE["student_code"] = code
    log(f"Cookie 已解析：学号 {code or '未知'}")
    return {"ok": True, "student_code": code or "",
            "note": "Cookie 已解析；刷新轮次/课程时自动校验并获取学生信息"}


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
    if not STATE["token"]:
        return []
    if not STATE["student_id"]:
        try:
            r = cs_get("/multiple-students")
            d = r.json()
            if d.get("result") == 0 and d.get("data"):
                STATE["student_id"] = str(d["data"][0]["id"])
                STATE["student_code"] = d["data"][0].get("code") or STATE["student_code"]
                log(f"学生信息：{STATE['student_code']}（内部ID {STATE['student_id']}）")
        except Exception:
            return []
    try:
        r = cs_get(f"/open-turns/{STATE['student_id']}")
        d = r.json()
        if d.get("result") == 0:
            STATE["turns"] = d.get("data", [])
            log(f"开放轮次：{len(STATE['turns'])} 个")
            return STATE["turns"]
    except Exception as e:
        log(f"载入轮次失败：{e}")
    return []


def load_courses(turn_id, page=1, page_size=20, keyword=""):
    if not STATE["token"] or not STATE["student_id"]:
        return {"ok": False, "message": "未登录/未获取学生ID"}
    payload = {"pageNo": int(page), "pageSize": int(page_size)}
    # v0.3: 搜索框接线 —— 关键词同时匹配课程名与授课代码
    if keyword:
        payload["lessonNameOrCode"] = keyword.strip()
        payload["courseNameOrCode"] = keyword.strip()
    try:
        r = cs_post(f"/query-lesson/{STATE['student_id']}/{turn_id}", payload)
        d = r.json()
        if d.get("result") == 0:
            data = d.get("data", {}) or {}
            lessons = data.get("lessons", []) or []
            page_info = data.get("pageInfo", {}) or {}
            total = int(page_info.get("totalRows", 0) or 0)
            STATE["courses"] = lessons
            STATE["course_total"] = total
            STATE["course_page"] = int(page)
            log(f"可选课程：第{page}页 {len(lessons)} 条 / 共 {total} 条")
            return {"ok": True, "count": len(lessons), "total": total,
                    "page": int(page), "totalPages": int(page_info.get("totalPages", 1) or 1),
                    "courses": lessons}
        return {"ok": False, "message": d.get("message", "查询失败")}
    except Exception as e:
        return {"ok": False, "message": f"查询异常：{e}"}


def check_capacity(lesson_id, token=None):
    """std-count 实时容量: 返回 (selected, limit) 或 None(接口失败/课程不在本轮)"""
    try:
        r = cs_get(f"/std-count?lessonIds=" + str(lesson_id), token=token, timeout=8)
        d = r.json()
        if d.get("result") == 0 and isinstance(d.get("data"), list):
            for it in d["data"]:
                if isinstance(it, dict) and str(it.get("lessonId") or it.get("id")) == str(lesson_id):
                    return (it.get("selectedCount"), it.get("limitCount"))
    except Exception:
        pass
    return None


def _lesson_of(payload):
    try:
        return payload["requestMiddleDtos"][0]["lessonAssoc"]
    except Exception:
        return None


def _poll_add_drop(student_id, request_id, resend_payload, resend_left=2):
    """轮询 add-drop-response（v0.3: 结果含 success / errorMessage.text / resend）。
    resend=true 时前端会弹窗让用户重发 —— 这里自动重提（最多 resend_left 次）。"""
    for k in range(1, 11):
        if STATE["rush_stop"]:
            return
        time.sleep(2)
        try:
            result = cs_get(f"/add-drop-response/{student_id}/{request_id}")
            rd = result.json()
            if rd.get("result") != 0:
                log(f"[轮询{k}] result={rd.get('result')} {rd.get('message')}")
                continue
            rr = rd.get("data") or {}
            if rr.get("success") is True:
                log(f"[√] 选课成功：{json.dumps(rr, ensure_ascii=False)[:260]}")
                STATE["rush_last"] = "选课成功"
                return True
            if rr.get("success") is False:
                text = (rr.get("errorMessage", {}) or {}).get("text", "被拒")
                if rr.get("resend") and resend_left > 0:
                    log(f"[重发] 服务端要求重提（{text[:80]}），自动重提剩余{resend_left}次")
                    STATE["rush_last"] = f"重提 {text[:40]}"
                    try:
                        rr2 = cs_post("/add-request", resend_payload)
                        d2 = rr2.json()
                        rid2 = d2.get("data") if d2.get("result") == 0 else None
                        if isinstance(rid2, dict):
                            rid2 = rid2.get("id") or rid2.get("requestId")
                        if isinstance(rid2, list):
                            rid2 = None
                        if rid2 is not None:
                            log(f"[重发] 新 requestId={rid2}")
                            return _poll_add_drop(student_id, rid2, resend_payload,
                                                  resend_left - 1)
                    except Exception as e:
                        log(f"[重发] 失败：{e}")
                    return False
                log(f"[x] 选课被拒：{text[:160]}")
                STATE["rush_last"] = f"被拒 {text[:60]}"
                return False
            if k % 3 == 0:
                log(f"[轮询{k}] 处理中…")
        except Exception:
            pass
    log("[!] 轮询超时（10×2s），请求可能仍在后台处理")
    return None


def rush_worker(turn_id, lesson_id, student_id, interval, max_times):
    """抢课主循环(v0.3): requestId解析修正 + resend自动重提 + 频控自适应退避 +
    容量预检 + 令牌过期/401 快速止损 + 节拍抖动。"""
    n = int(student_id)
    payload = {
        "studentAssoc": n,
        "courseSelectTurnAssoc": int(turn_id),
        "requestMiddleDtos": [{"lessonAssoc": int(lesson_id),
                               "virtualCost": "",
                               "scheduleGroupAssoc": None}],
        "coursePackAssoc": None,
    }
    limit_desc = "无限次" if max_times == 0 else f"最多{max_times}次"
    log(f"抢课开始：lessonId={lesson_id} turnId={turn_id} 间隔={interval}s {limit_desc}")
    STATE["rush_attempts"] = 0
    last_msg = ""
    repeat = 0
    backoff = 0.0          # 频控退避(秒)
    cap_checked_at = 0.0   # 容量预检节流
    cap_full_seen = 0      # 连续满员计数
    for i in itertools.count(1):
        if max_times and i > max_times:
            log("已达最大次数，停止")
            break
        STATE["rush_attempts"] = i
        if STATE["rush_stop"]:
            log("抢课已手动停止")
            break
        # 令牌过期/临近过期止损
        exp = jwt_exp(STATE["token"])
        if exp and exp <= int(time.time()) + 10:
            log("[!] 令牌已过期，停止抢课 —— 请重新复制 Cookie 导入")
            STATE["rush_last"] = "令牌过期"
            break
        # 容量预检（高频模式每5次/低频每15s一次; 满员则低频等待不空转狂打）
        if interval >= 3 or i % 5 == 0 or time.time() - cap_checked_at > 15:
            cap_checked_at = time.time()
            cap = check_capacity(lesson_id)
            if cap and cap[0] is not None:
                sel, lim = cap
                if lim is not None and sel >= lim:
                    cap_full_seen += 1
                    log(f"[容量] {sel}/{lim} 已满（连续{cap_full_seen}次），低频等待…")
                    if cap_full_seen >= 8:
                        log("[!] 长时间满员，自动停止（可稍后手动再开）")
                        STATE["rush_last"] = "满员停止"
                        break
                    time.sleep(6.0)
                    continue
                cap_full_seen = 0
        try:
            r = cs_post("/add-request", payload)
            data = {}
            try:
                data = r.json()
            except Exception:
                pass
            msg = r.text[:120] if r.status_code != 200 else "result=" + str(data.get("result"))
            # 401 = 令牌失效（Shiro）, 立即止损
            if r.status_code == 401:
                log("[!] 401 令牌被拒 —— 已停止，请重新复制 Cookie 导入")
                STATE["rush_last"] = "令牌被拒(401)"
                break
            if msg == last_msg:
                repeat += 1
                if repeat % 10 == 0:
                    log(f"[{i}] 持续 {msg}")
            else:
                log(f"[{i}] {msg}")
                last_msg = msg
                repeat = 0
            if r.status_code == 200 and data.get("result") == 0:
                request_id = data.get("data")
                # v0.3 修正: add-request 响应 data 即 requestId(纯值); 兼容对象形态
                if isinstance(request_id, dict):
                    request_id = request_id.get("id") or request_id.get("requestId")
                log(f"[成功提交] 第{i}次 result=0 requestId={request_id}")
                STATE["rush_last"] = "提交成功，等待结果"
                if request_id is not None:
                    _poll_add_drop(n, request_id, payload, resend_left=2)
                    break
                # 理论不发生: result=0 但没拿到 requestId → 稍候重试而不是放弃
                log("[?] 未拿到 requestId，稍候重试")
                sleep_s = 2.0
            else:
                sleep_s = interval
            txt_low = (msg or "").lower()
            if r.status_code in (429, 503) or any(k in txt_low for k in
                    ["频繁", "稍后", "风控", "too many", "busy", "休息", "访问太"]):
                backoff = min(30.0, (backoff or 3.0) * 2)   # 3→6→12→24→30
                log(f"[频控] 退避 {backoff:.0f}s")
                sleep_s = backoff
            elif any(k in txt_low for k in ["未到", "未开", "不在", "not open",
                                            "未开始", "还未", "未在"]):
                sleep_s = max(0.3, interval)
            else:
                backoff = 0.0
        except Exception as e:
            msg = f"异常 {e}"
            if msg == last_msg:
                repeat += 1
                if repeat % 10 == 0:
                    log(f"[{i}] 持续异常 {e}")
            else:
                log(f"[{i}] 异常：{e}")
                last_msg = msg
                repeat = 0
            sleep_s = max(interval, 1.0)
        if not (max_times and i >= max_times):
            # 节拍抖动 ±25%: 避免与全校抢课请求撞在整齐节拍上
            sleep_s = sleep_s * (0.75 + 0.5 * ((i * 2654435761) % 100) / 100.0)
            time.sleep(sleep_s)
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
# tkinter 主窗口（完整 UI，无需浏览器）
# ----------------------------------------------------------------------
class TkApp:
    def __init__(self):
        self.root = tk.Tk()
        _pick_ui_font()   # Linux 适配: root 建立后才能枚举字体
        self.root.title(f"抢课助手 (PID {os.getpid()}) - 建桥学院抢课助手")
        self.root.geometry("780x720")
        self.root.minsize(700, 640)
        self.course_page = 1
        self.course_total_pages = 1
        self._log_pos = 0   # rush_log 增量游标（start_rush 清空日志时归零重同步）
        self._preheat = None  # 预热线程句柄（可取消，防重复开抢）
        self._build()
        self._refresh_loop()

    # ---------- UI 构建 ----------
    def _build(self):
        pad = {"padx": 8, "pady": 3}
        # 顶部状态条
        top = tk.Frame(self.root, bg="#eef4ff")
        top.pack(fill="x", **pad)
        self.l_port = tk.Label(top, text="实例: -", bg="#eef4ff", font=UI_FONT)
        self.l_port.pack(side="left", **pad)
        tk.Button(top, text="新开窗口", command=self.open_new_window,
                  bg="#eef4ff", relief="flat", font=UI_FONT,
                  cursor="hand2").pack(side="left", **pad)
        self.l_login = tk.Label(top, text="登录: 未登录", bg="#eef4ff", font=UI_FONT)
        self.l_login.pack(side="left", **pad)
        self.l_token = tk.Label(top, text="token: -", bg="#eef4ff", font=UI_FONT)
        self.l_token.pack(side="left", **pad)
        self.l_srv = tk.Label(top, text="服务器时间: -", bg="#eef4ff", font=UI_FONT)
        self.l_srv.pack(side="right", **pad)

        # 登录区
        login_f = tk.LabelFrame(self.root, text="1. 登录（粘贴 Cookie）", padx=8, pady=6)
        login_f.pack(fill="x", **pad)
        tk.Label(login_f, text="Cookie（整行）").grid(row=0, column=0, sticky="e", padx=4)
        self.e_cookie = tk.Entry(login_f, width=72)
        self.e_cookie.grid(row=0, column=1, sticky="we", padx=4)
        tk.Button(login_f, text="Cookie 登录", command=self.do_cookie).grid(row=0, column=2, padx=6)
        tk.Button(login_f, text="导入配置", command=self.import_config).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        tk.Button(login_f, text="导出配置", command=self.export_config).grid(row=1, column=2, sticky="w", padx=6, pady=2)
        tk.Label(login_f, text="导入/导出文件含 Cookie、预热、间隔、次数", fg="#888").grid(row=2, column=1, columnspan=2, sticky="w", padx=4)
        login_f.columnconfigure(1, weight=1)

        # 轮次区
        turn_f = tk.LabelFrame(self.root, text="2. 选课轮次", padx=8, pady=6)
        turn_f.pack(fill="x", **pad)
        tk.Label(turn_f, text="轮次").grid(row=0, column=0, sticky="e", padx=4)
        self.cb_turn = ttk.Combobox(turn_f, state="readonly", width=46)
        self.cb_turn.grid(row=0, column=1, padx=4)
        tk.Button(turn_f, text="刷新轮次", command=self.refresh_turns).grid(row=0, column=2, padx=6)
        self.l_turn_hint = tk.Label(turn_f, text="", fg="#666")
        self.l_turn_hint.grid(row=0, column=3, padx=4)

        # 课程区
        course_f = tk.LabelFrame(self.root, text="3. 目标课程（点击列表选择）", padx=8, pady=6)
        course_f.pack(fill="both", expand=True, **pad)
        bar = tk.Frame(course_f)
        bar.pack(fill="x")
        tk.Label(bar, text="搜索").pack(side="left", padx=4)
        self.e_search = tk.Entry(bar, width=24)
        self.e_search.pack(side="left", padx=4)
        tk.Button(bar, text="载入课程", command=self.load_courses).pack(side="left", padx=6)
        tk.Button(bar, text="刷新", command=lambda: self.load_courses(self.course_page)).pack(side="left", padx=4)
        self.l_course_info = tk.Label(bar, text="", fg="#666")
        self.l_course_info.pack(side="right", padx=4)
        # 课程表格（Treeview）
        cols = ("lessonId", "code", "name", "credits", "teachers", "time", "remain")
        self.tv = ttk.Treeview(course_f, columns=cols, show="headings", height=10)
        widths = {"lessonId": 60, "code": 70, "name": 160, "credits": 50,
                  "teachers": 90, "time": 180, "remain": 80}
        for c in cols:
            self.tv.heading(c, text={"lessonId": "ID", "code": "代码", "name": "课程名",
                                     "credits": "学分", "teachers": "教师",
                                     "time": "时间地点", "remain": "余量"}[c])
            self.tv.column(c, width=widths[c], anchor="w" if c in ("name", "teachers", "time") else "center")
        self.tv.pack(fill="both", expand=True, padx=4, pady=4)
        self.tv.bind("<<TreeviewSelect>>", self.on_select)
        # 分页
        pg = tk.Frame(course_f)
        pg.pack(fill="x")
        tk.Button(pg, text="上一页", command=self.prev_page).pack(side="left", padx=4)
        self.l_pg = tk.Label(pg, text="第 1/1 页", fg="#666")
        self.l_pg.pack(side="left", padx=8)
        tk.Button(pg, text="下一页", command=self.next_page).pack(side="left", padx=4)
        self.l_sel = tk.Label(pg, text="已选: -", fg="#4a7bff")
        self.l_sel.pack(side="right", padx=8)

        # 抢课控制
        rush_f = tk.LabelFrame(self.root, text="4. 抢课控制", padx=8, pady=6)
        rush_f.pack(fill="x", **pad)
        tk.Label(rush_f, text="预热(秒)").grid(row=0, column=0, sticky="e", padx=4)
        self.e_pre = tk.Entry(rush_f, width=6)
        self.e_pre.grid(row=0, column=1, padx=4)
        self.e_pre.insert(0, "5")
        tk.Label(rush_f, text="间隔(毫秒)").grid(row=1, column=0, sticky="e", padx=4)
        self.e_iv = tk.Entry(rush_f, width=6)
        self.e_iv.grid(row=1, column=1, sticky="w", padx=4)
        self.e_iv.insert(0, "200")
        tk.Label(rush_f, text="最多次数(0=无限)").grid(row=1, column=2, sticky="e", padx=8)
        self.e_max = tk.Entry(rush_f, width=8)
        self.e_max.grid(row=1, column=3, sticky="w", padx=4)
        self.e_max.insert(0, "0")
        tk.Button(rush_f, text="开始抢课", command=self.do_rush).grid(row=0, column=4, rowspan=2, padx=10)
        tk.Button(rush_f, text="停止", command=self.stop_rush).grid(row=0, column=5, rowspan=2, padx=6)
        self.l_rush = tk.Label(rush_f, text="未开始", fg="#666")
        self.l_rush.grid(row=2, column=1, columnspan=4, sticky="w", padx=4)

        # 日志
        log_f = tk.LabelFrame(self.root, text="运行日志", padx=8, pady=6)
        log_f.pack(fill="both", expand=True, **pad)
        self.txt_log = scrolledtext.ScrolledText(log_f, height=8, font=("Consolas", 9),
                                                  bg="#1c2333", fg="#d7dce8")
        self.txt_log.pack(fill="both", expand=True)

    # ---------- 后端交互 ----------
    def open_new_window(self):
        """多开：启动一个新的抢课助手实例窗口（独立进程、独立登录/抢课）。"""
        self.root.after(10, open_new_window_process)

    def do_cookie(self):
        ck = self.e_cookie.get().strip()
        if not ck:
            messagebox.showwarning("提示", "请粘贴完整 Cookie")
            return
        res = eams_set_cookie(ck)
        if res.get("ok"):
            messagebox.showinfo("成功", res.get("note", "登录成功"))
            self.refresh_turns()
        else:
            messagebox.showerror("失败", res.get("message", "解析失败"))

    def import_config(self):
        from tkinter import filedialog
        f = filedialog.askopenfilename(title="选择配置文件",
                                       filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not f:
            return
        try:
            cfg = json.load(open(f, encoding="utf-8"))
            if cfg.get("cookie"):
                self.e_cookie.delete(0, "end")
                self.e_cookie.insert(0, cfg["cookie"])
            if cfg.get("preStart"):
                self.e_pre.delete(0, "end")
                self.e_pre.insert(0, str(cfg["preStart"]))
            if cfg.get("interval"):
                self.e_iv.delete(0, "end")
                self.e_iv.insert(0, str(cfg["interval"]))
            if cfg.get("maxTimes") is not None and str(cfg["maxTimes"]) != "":
                self.e_max.delete(0, "end")
                self.e_max.insert(0, str(cfg["maxTimes"]))
            messagebox.showinfo("导入成功", "配置已导入（Cookie/预热/间隔/次数）")
            if cfg.get("cookie"):
                res = eams_set_cookie(cfg["cookie"])
                if res.get("ok"):
                    self.refresh_turns()
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def export_config(self):
        from tkinter import filedialog
        # 文件名带当前学号，便于多账号区分；学号未解析时回退默认名
        code = re.sub(r'[\\/:*?"<>|]', "_", STATE.get("student_code") or "")
        name = f"抢课配置-{code}.json" if code else "抢课配置.json"
        f = filedialog.asksaveasfilename(title="导出配置", defaultextension=".json",
                                         filetypes=[("JSON", "*.json")],
                                         initialfile=name)
        if not f:
            return
        cfg = {
            "cookie": STATE.get("session_cookie_str") or self.e_cookie.get().strip(),
            "preStart": self.e_pre.get().strip(),
            "interval": self.e_iv.get().strip(),
            "maxTimes": self.e_max.get().strip(),
        }
        try:
            json.dump(cfg, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"已导出到\n{f}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def refresh_turns(self):
        turns = load_turns()
        self.cb_turn["values"] = [f"{t.get('name') or t.get('nameZh') or '轮次'} (id={t.get('id')})" for t in turns]
        if turns:
            self.cb_turn.current(0)
            self.l_turn_hint.config(text=f"{len(turns)} 个开放", fg="#67c23a")
            self.load_courses()
        else:
            self.l_turn_hint.config(text="未开放（选课未开始）", fg="#f56c6c")

    def _turn_id(self):
        idx = self.cb_turn.current()
        if idx < 0:
            return None
        t = STATE["turns"][idx]
        return t.get("id")

    def load_courses(self, page=None):
        turn_id = self._turn_id()
        if turn_id is None:
            messagebox.showwarning("提示", "请先刷新轮次并选择")
            return
        if page:
            self.course_page = page
        # v0.3: 搜索框关键词进查询载荷
        res = load_courses(turn_id, self.course_page,
                           keyword=self.e_search.get().strip())
        if res.get("ok"):
            self.course_total_pages = res.get("totalPages", 1)
            self._fill_courses(res["courses"])
            self.l_course_info.config(
                text=f"第{res.get('page')}/{self.course_total_pages}页 共{res.get('total')}门")
            self.l_pg.config(text=f"第 {self.course_page}/{self.course_total_pages} 页")
        else:
            messagebox.showerror("载入失败", res.get("message", ""))

    def _fill_courses(self, lessons):
        self.tv.delete(*self.tv.get_children())
        for l in lessons:
            c = l.get("course") or l.get("courseDto") or {}
            teachers = "、".join(x.get("name") or x.get("nameZh") or ""
                                 for x in (l.get("teachers") or [])) or l.get("teacherName") or ""
            remain = f"{l.get('selectedCount', '?')}/{l.get('limitCount', '?')}"
            self.tv.insert("", "end", values=(
                l.get("id"), c.get("code") or l.get("code") or "",
                c.get("nameZh") or c.get("name") or l.get("nameZh") or "",
                l.get("credits", ""),
                teachers,
                l.get("timeAndPlace") or l.get("dateTimePlace") or l.get("classTime") or "",
                remain))

    def on_select(self, _event=None):
        sel = self.tv.selection()
        if sel:
            item = self.tv.item(sel[0])
            vals = item["values"]
            self.l_sel.config(text=f"已选: {vals[1]} {vals[2]}（ID {vals[0]}）")

    def prev_page(self):
        if self.course_page > 1:
            self.load_courses(self.course_page - 1)

    def next_page(self):
        if self.course_page < self.course_total_pages:
            self.load_courses(self.course_page + 1)

    def _turn_start_target(self):
        """返回所选轮次的开抢时间戳（服务器时间轴），无有效时间返回 None。"""
        idx = self.cb_turn.current()
        if idx < 0:
            return None
        return turn_start_target_ts(STATE["turns"][idx])

    def do_rush(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择目标课程")
            return
        item = self.tv.item(sel[0])
        lesson_id = item["values"][0]
        turn_id = self._turn_id()
        if turn_id is None:
            messagebox.showwarning("提示", "请先选择轮次")
            return
        try:
            interval = float(self.e_iv.get() or 200) / 1000.0
            max_times = int(self.e_max.get() or 0)   # 0 = 无限次直到成功/手动停
            pre = int(self.e_pre.get() or 5)
        except ValueError:
            messagebox.showerror("参数错误", "间隔/次数/预热必须是数字")
            return
        if interval <= 0:
            messagebox.showerror("参数错误", "间隔必须大于 0")
            return
        if max_times < 0 or pre < 0:
            messagebox.showerror("参数错误", "次数/预热不能为负数")
            return
        if STATE["rush_running"] or self._preheat is not None:
            messagebox.showinfo("提示", "抢课已在运行/预热中，请勿重复启动")
            return
        STATE["rush_stop"] = False   # 复位上次停止残留，否则预热会立即被误判为取消
        # v0.3: 校准超过2分钟则开抢前复校服务器时钟(抢到点误差<1s)
        if time.time() - STATE.get("server_time_at", 0) > 120:
            if get_server_time():
                log(f"服务器时钟已复校（offset={round(STATE['server_offset'],1)}s）")
        # 自动取轮次开抢时间点，提前“预热”秒开始抢课。
        # 预热改为可取消线程：stop_rush 置 rush_stop 后到点不再开抢；
        # 且同一时刻只允许一个预热线程（旧版 Timer 叠加会重复开抢）。
        def _preheat_job():
            try:
                target = self._turn_start_target()
                now = time.time() + STATE.get("server_offset", 0)
                if target and target > now:
                    wait = max(0.0, target - now - pre)
                    log(f"轮次开抢时间 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(target))}，预热 {pre} 秒，等待 {int(wait)} 秒")
                    deadline = time.time() + wait
                    while time.time() < deadline and not STATE["rush_stop"]:
                        time.sleep(min(0.5, max(0.0, deadline - time.time())))
                    if STATE["rush_stop"]:
                        log("[预热] 已取消")
                        self._preheat = None
                        return
                else:
                    log("轮次无开抢时间或已到点，立即开抢")
                if STATE["rush_stop"]:
                    log("[预热] 已取消")
                    self._preheat = None
                    return
                start_rush(turn_id, lesson_id, interval, max_times)
            finally:
                self._preheat = None
        self._preheat = threading.Thread(target=_preheat_job, daemon=True)
        self._preheat.start()
        self.l_rush.config(text="已启动抢课线程" if pre <= 0 else f"预热中（{pre}s 内开抢，可点停止取消）",
                           fg="#4a7bff")

    def stop_rush(self):
        STATE["rush_stop"] = True
        log("已请求停止")
        self.l_rush.config(text="已停止", fg="#f56c6c")

    # ---------- 实时刷新 ----------
    def _refresh_loop(self):
        try:
            exp = jwt_exp(STATE["token"])
            left = (exp - int(time.time())) if exp else 0
            self.l_port.config(text=f"实例: PID {os.getpid()}")
            self.l_login.config(text=f"登录: {STATE.get('student_code') or '未登录'}")
            if left > 0:
                self.l_token.config(text=f"token: 剩余 {int(left//3600)}小时{int(left%3600//60)}分")
            else:
                self.l_token.config(text="token: 无/未提供")
            self.l_srv.config(text=f"服务器时间: {time.strftime('%H:%M:%S', time.localtime(time.time() + STATE.get('server_offset', 0)))}（校准 {round(STATE.get('server_offset',0),1)}s）")
            rush = "运行中" if STATE["rush_running"] else (
                "预热中" if self._preheat is not None else "未开始")
            self.l_rush.config(text=f"{rush}（已提交 {STATE['rush_attempts']} 次，最近: {STATE['rush_last'] or '-'}）")
            # 日志增量（位置游标；start_rush 清空 rush_log 会使缓冲短于游标 → 归零重同步，
            # 修复旧版"文本框行数当下标"在清空/截断后新日志永不显示的问题）
            if len(STATE["rush_log"]) < self._log_pos:
                self._log_pos = 0
            for line in STATE["rush_log"][self._log_pos:]:
                self.txt_log.insert("end", line + "\n")
            self._log_pos = len(STATE["rush_log"])
            self.txt_log.see("end")
        except Exception:
            pass
        self.root.after(1500, self._refresh_loop)

    def run(self):
        self.root.mainloop()


def turn_start_target_ts(turn):
    """模块级：返回所选轮次的开抢时间戳（服务器时间轴），无有效时间返回 None。
    （Linux CLI 与 GUI 共用）"""
    for key in ("startTime", "openTime", "beginTime",
                "startTimeStr", "openTimeStr", "beginTimeStr"):
        v = turn.get(key)
        if v in (None, ""):
            continue
        try:
            if isinstance(v, (int, float)):
                ts = float(v)
                if ts > 1e12:  # 毫秒时间戳
                    ts /= 1000.0
                return ts + STATE.get("server_offset", 0)
            import datetime as _dt
            s = str(v).strip().replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S"):
                try:
                    ts = _dt.datetime.strptime(s, fmt).timestamp()
                    return ts + STATE.get("server_offset", 0)
                except ValueError:
                    continue
        except Exception:
            continue
    return None


def cli_main(argv=None):
    """Linux/无头 CLI 版（无需 tkinter）：Cookie/配置载入 → 轮次 → 开抢。
    python3 app.py --cli --config 配置.json --targets 1001,1002
    """
    import argparse
    argv = [a for a in (argv if argv is not None else sys.argv[1:]) if a != "--cli"]
    ap = argparse.ArgumentParser(prog="抢课助手", description="建桥抢课助手 Linux CLI 版")
    ap.add_argument("--cookie", help="浏览器复制整串 Cookie（须含 cs-course-select-student-token）")
    ap.add_argument("--config", help="导出的 JSON 配置（含 cookie/preStart/interval/maxTimes）")
    ap.add_argument("--interval-ms", type=int, default=200, help="抢课间隔毫秒(默认200)")
    ap.add_argument("--max-times", type=int, default=0, help="最多抢 N 次(0=无限)")
    ap.add_argument("--targets", default="", help="要抢的课程 lessonId，逗号分隔")
    ap.add_argument("--search", default="", help="只预览课程时不抢（配合 --turn-id）")
    ap.add_argument("--prestart", type=int, default=5, help="轮次开抢前预热秒")
    ap.add_argument("--poll", type=int, default=0, help="轮次未开放时每 N 秒轮询(0=立即退出)")
    ap.add_argument("--turn-id", type=int, default=None, help="指定轮次 id(默认取第一个开放轮次)")
    args = ap.parse_args(argv)

    if not (args.cookie or args.config):
        print("[!] 需要 --cookie 或 --config")
        ap.print_help()
        return 1
    cookie = args.cookie or ""
    interval_ms = args.interval_ms
    max_times = args.max_times
    if args.config:
        try:
            cfg = json.load(open(args.config, encoding="utf-8"))
        except Exception as e:
            print(f"[!] 配置读取失败: {e}")
            return 1
        cookie = cfg.get("cookie", "") or cookie
        interval_ms = int(cfg.get("interval", interval_ms))
        max_times = int(cfg.get("maxTimes", max_times))
    res = eams_set_cookie(cookie if isinstance(cookie, str) else str(cookie))
    if not res.get("ok"):
        print(f"[!] Cookie 解析失败: {res.get('message')}")
        return 1
    get_server_time()   # CLI 也先校时：保证 prestart 等待/预热用服务器时间轴
    print(f"[*] 已载入: 学号={STATE.get('student_code')} token剩余="
          f"{(jwt_exp(STATE['token']) - int(time.time())) // 60} 分钟")

    # 轮次: 可选轮询等待开放
    turns = load_turns()
    while not turns and args.poll:
        print(time.strftime("[%H:%M:%S] 无开放轮次，%ds 后再试…" % args.poll))
        time.sleep(args.poll)
        turns = load_turns()
    if not turns:
        print("[!] 当前无开放轮次（可加 --poll N 保持轮询）")
        return 0
    turn = None
    if args.turn_id:
        turn = next((t for t in turns if t.get("id") == args.turn_id), None)
        if turn is None:
            print(f"[!] 未找到轮次 id={args.turn_id}，开放轮次: {[t.get('id') for t in turns]}")
            return 1
    else:
        turn = turns[0]
    tid = turn.get("id")
    print(f"[*] 使用轮次: {turn.get('name')} (id={tid})")

    # 开抢时间点预热（可选）
    target = turn_start_target_ts(turn)
    now = time.time() + STATE.get("server_offset", 0)
    if target and target > now and args.prestart > 0:
        wait = max(0, target - now - args.prestart)
        print(f"[*] 开抢时间 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(target))}，"
              f"预热 {args.prestart}s，等待 {int(wait)}s")
        time.sleep(wait)

    # 预览搜索（不开抢）
    if args.search:
        r = load_courses(tid, page=1, page_size=20, keyword=args.search)
        for l in (r.get("courses") or []):
            c = l.get("course") or {}
            print(f"  lesson={l.get('id')} {c.get('code')} {c.get('nameZh') or c.get('name')} "
                  f"余量 {l.get('selectedCount')}/{l.get('limitCount')}")
        print("[*] 预览完成；要开抢请用 --targets <lessonId>")
        return 0

    targets = [x.strip() for x in args.targets.split(",") if x.strip().isdigit()]
    if not targets:
        print("[!] 未指定目标（--targets 1001,1002）")
        return 1
    interval = interval_ms / 1000.0
    print(f"[*] 开始抢课: {targets} 间隔{interval}s 最多{max_times}次"
          f"{'(无限)' if max_times == 0 else ''}，Ctrl+C 停止")
    try:
        for ts in targets:
            if STATE["rush_stop"]:
                break
            rush_worker(tid, int(ts), STATE["student_id"], interval, max_times)
    except KeyboardInterrupt:
        STATE["rush_stop"] = True
        print("\n[!] 已收到中断，停止抢课")
    return 0


def main():
    if "--cli" in sys.argv[1:]:
        raise SystemExit(cli_main(sys.argv[1:]))
    if not TK_OK:
        print("[!] tkinter 不可用 —— GUI 版需要 python3-tk")
        print("    Debian/Ubuntu:  sudo apt install python3-tk")
        print("    改用 CLI 模式:  python3 app.py --cli --help")
        raise SystemExit(1)
    # 只跑 tkinter 主窗（无需浏览器/HTTP）
    app = TkApp()
    app.run()


def open_new_window_process():
    """多开入口：另起一个独立进程窗口。"""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = []
    else:
        exe = sys.executable
        params = [os.path.abspath(__file__)]
    log("新开窗口（独立实例）…")
    # Linux 适配: creationflags 仅 Windows 支持
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([exe, *params], **kwargs)


if __name__ == "__main__":
    main()
