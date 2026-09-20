#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建桥学院抢课助手（tkinter 原生 UI，桌面 exe）v0.3.4
================================================
双击 exe → 直接弹出 tkinter 主窗口（无需浏览器）。
功能：登录（Cookie）、实时状态、选课轮次、课程分页列表、
      抢课控制（预热/高频/成功即停）、运行日志、保活常驻。
v0.3.4 优化（前端 JS 全量端点还原 + live 探测，2026-09-13）：
  - 进入批次：GET /{sid}/turn/{turnId}/select 对齐前端时序（失败 15s 节流重试不阻塞开抢）
  - 容量预载改走 GET /simplest-lessons/{turnId}（单发轻量全量，失败回退 query-lesson 500）
  - 成功后 GET /selected-lessons/{turnId}/{sid} 拉真实已选清单二次确认
  - --predicate 选课预检：POST /add-predicate + /predicate-response 轮询（'ATTEND'=规则通过）
  - CLI --poll 批次监听修复（旧 %H 格式化冲突一进循环即 ValueError）+ 批次时间窗完整打印
v0.3.3 优化（live API 探测 + 时延实测，2026-09-12）：
  - cs_get/cs_post 改走共享 Session 连接池：单请求 91ms(握手) → 18ms(复用)，约 5 倍
  - smart_wait_until：预热末段 1s busy-spin，开抢抖动从 sleep 粒度(~15ms) → <2ms
  - 结果轮询自适应 0.4/0.8/1.5/2s（旧版固定先睡 2s，成功路径白等 1.5s+）
  - 容量预检纯时间节流 ≥5s + 开抢前 5s 宽限（旧版每 5 次一发，吞吐砍半）
  - add-request 超时收紧 (3,6)s；403 与 401 同步止损
  - CLI 抢前缓存课程 limitCount（直接 --targets 时满员检测曾形同虚设）
  - 节拍抖动改真随机；长等待中复校服务器时钟
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
import random
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
def _build_session() -> requests.Session:
    """v0.3.3: 共享会话 + 连接池。
    旧版 cs_get/cs_post 用模块级 requests.get/post —— 每次请求都完整重走
    TCP+TLS 握手（实测 100~300ms），抢课毫秒级竞争里这是最大延迟源。
    Session 复用 keep-alive 连接后，add-request 往返可压到 30~80ms。"""
    s = requests.Session()
    try:
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4, pool_maxsize=32, max_retries=0)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    except Exception:
        pass
    return s


STATE = {
    "session": _build_session(),
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
    "semester_id": 0,   # 轮次所在的学期 id（query-lesson 载荷需要，从 open-turns 数据推导）
    "current_turn_id": None,   # v0.3.4: 当前抢课批次（成功后 selected-lessons 验证用）
    "predicate_enabled": False,  # v0.3.4: --predicate 选课预检开关（默认关，省一跳延迟）
    "_last_refresh_at": 0.0,   # v0.3.4: SESSION 现发 token 节流
}


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    STATE["rush_log"].append(line)
    del STATE["rush_log"][:-500]   # 封顶缓存（保留最新 500 条）
    STATE["_log_total"] = STATE.get("_log_total", 0) + 1   # 单调计数：GUI 游标以此对齐，封顶截断不再导致显示冻结
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
        r = STATE["session"].get(f"{CS_API}/getCurrentDateTime",
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


def smart_wait_until(target_ts, stop_fn=None, spin=1.0):
    """v0.3.3: 精确等到目标时间戳（本地时间轴）。
    远段用 0.5s 步长 sleep，最后 spin 秒 busy-spin ——
    time.sleep 粒度在 Linux ~1ms / Windows ~15ms，自旋把开抢抖动压到亚毫秒，
    避免"全班 sleep 到同一粒度再齐射"。stop_fn 返回 True 时提前退出（返回 False）。"""
    while True:
        remain = target_ts - time.time()
        if remain <= 0:
            return True
        if stop_fn is not None and stop_fn():
            return False
        if remain > spin:
            time.sleep(min(remain - spin, 0.5))
        # else: busy-spin（不再 sleep）


def eams_login(username: str, password: str):
    """直登选课服务（course-selection-api, v0.3 修正）。
    协议(逆向确认): GET /login-salt/{user} -> salt(uuid);
    password = SHA1(salt + "-" + 明文); POST /login {username,password,captchaToken,captcha}
    失败返回 needCaptcha=true + captchaToken, 需先取验证码图(login-captcha/{token})
    并人工识别后重提。成功 result==0 且 data.token 即选课 JWT。"""
    s = _build_session()
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
    s = _build_session()
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


def refresh_token_via_session():
    """v0.3.4: 凭 SESSION 门户会话到经典 EAMS 选课页现发新选课 token。
    GET /student/for-std/course-select 的页面内嵌
    `course-selection/?token=<JWT>`（服务端 Thymeleaf 渲染），解析即得新 JWT。
    成功更新 STATE["token"] 与 Cookie 并返回新 token；失败返回 None。"""
    sess = STATE.get("session")
    if not sess or not any(c.name == "SESSION" for c in sess.cookies):
        return None   # 无门户 SESSION，现发不了
    try:
        r = sess.get(f"{EAMS}/student/for-std/course-select",
                     headers={"User-Agent": UA, "Accept": "text/html"},
                     timeout=(5, 10), allow_redirects=True)
        m = re.search(r'course-selection/\?token=([A-Za-z0-9_.\-]+)', r.text)
        if not m:
            log("[!] SESSION 未能现发新 token（门户登录态可能已失效）")
            return None
        new_tok = m.group(1)
        if new_tok != STATE.get("token"):
            STATE["token"] = new_tok
            sess.cookies.set("cs-course-select-student-token", new_tok,
                             domain="eams.gench.edu.cn", path="/")
            exp = jwt_exp(new_tok)
            log("[√] 已凭 SESSION 现发新 token（有效期至 "
                f"{time.strftime('%m-%d %H:%M', time.localtime(exp)) if exp else '?'}）")
        return new_tok
    except Exception as e:
        log(f"token 现发失败：{e}")
        return None


def _request_with_refresh(method, path, payload=None, token=None,
                          timeout=15, json_ct=False):
    """v0.3.4: 统一请求入口 —— 401 时先凭 SESSION 现发新 token 重试一次
    （≥60s 节流，防风暴）；重试仍 401 才交还调用方止损。"""
    tok = token or STATE["token"]
    h = api_headers(tok, json_ct)
    sess = STATE["session"]
    if method == "GET":
        r = sess.get(CS_API + path, headers=h, timeout=timeout, allow_redirects=False)
    else:
        r = sess.post(CS_API + path, data=json.dumps(payload, ensure_ascii=False),
                      headers=h, timeout=timeout, allow_redirects=False)
    if (r.status_code == 401 and not token and not STATE.get("rush_stop")
            and time.time() - STATE.get("_last_refresh_at", 0) >= 60):
        STATE["_last_refresh_at"] = time.time()
        if refresh_token_via_session():
            h = api_headers(STATE["token"], json_ct)
            if method == "GET":
                r = sess.get(CS_API + path, headers=h, timeout=timeout,
                             allow_redirects=False)
            else:
                r = sess.post(CS_API + path,
                              data=json.dumps(payload, ensure_ascii=False),
                              headers=h, timeout=timeout, allow_redirects=False)
    return r


def cs_get(path, token=None, timeout=15):
    """v0.3.4: 走共享 Session + 401 自动现发重试（timeout 支持 (连接,读取) 元组）。"""
    return _request_with_refresh("GET", path, token=token, timeout=timeout)


def cs_post(path, payload, token=None, timeout=15):
    return _request_with_refresh("POST", path, payload=payload, token=token,
                                 timeout=timeout, json_ct=True)


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
        if r.status_code in (401, 403) or (r.status_code == 200 and not r.content):
            # v0.3.4: 401/403 空 body（Shiro 会话/JWT 失效）—— cs_get 已尝试现发,
            # 走到这里说明 SESSION 也失效, 明确提示
            log("[!] 会话被拒且 SESSION 现发失败 —— 请重新登录门户后复制完整 Cookie")
            return []
        d = r.json()
        if d.get("result") == 0:
            STATE["turns"] = d.get("data", [])
            # 从轮次对象推导 semesterId（query-lesson 载荷需要；多候选字段名防变更）
            if STATE["turns"]:
                t0 = STATE["turns"][0]
                for k in ("semesterAssoc", "semesterId", "semester"):
                    v = t0.get(k)
                    if isinstance(v, dict):
                        v = v.get("id")
                    if v:
                        try:
                            STATE["semester_id"] = int(v)
                        except (TypeError, ValueError):
                            continue   # 字段异常不拖垮整个轮次载入
                        break
                record_turn_history(STATE["turns"])   # v0.3.4: 见批即录（本地历史档案）
            log(f"开放轮次：{len(STATE['turns'])} 个")
            return STATE["turns"]
    except Exception as e:
        log(f"载入轮次失败：{e}")
    return []


def _history_file():
    """v0.3.4: 本地批次历史档案路径（脚本/exe 同目录，按学号分文件）。"""
    code = STATE.get("student_code") or "unknown"
    base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                           else __file__))
    return os.path.join(base, f"批次历史-{code}.json")


def record_turn_history(turns):
    """v0.3.4: 把见到的批次合并进本地历史档案（服务端无历史批次接口，
    开放批次转瞬即逝 —— 本地落盘长期积累，--history 随时回看）。"""
    path = _history_file()
    try:
        try:
            store = json.load(open(path, encoding="utf-8"))
            if not isinstance(store, dict):
                store = {}
        except Exception:
            store = {}
        store.setdefault("student_code", STATE.get("student_code") or "")
        turns_map = store.setdefault("turns", {})
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        for t in turns or []:
            if not isinstance(t, dict) or t.get("id") is None:
                continue
            tid = str(t["id"])
            rec = turns_map.get(tid) or {}
            rec.setdefault("first_seen", now)
            rec["last_seen"] = now
            rec["seen_count"] = int(rec.get("seen_count", 0)) + 1
            for k, v in t.items():          # 原始字段全存（时间窗/名称/学期…）
                rec[k] = v
            turns_map[tid] = rec
        store["updated_at"] = now
        json.dump(store, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"批次历史落盘失败：{e}")


def show_turn_history(path=None):
    """v0.3.4: --history —— 打印本地积累的全部历史批次。
    path=None 时扫描脚本目录下所有 批次历史-*.json（多账号一起看）。"""
    if path:
        paths = [path]
    else:
        base = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                               else __file__))
        try:
            paths = [os.path.join(base, f) for f in os.listdir(base)
                     if f.startswith("批次历史-") and f.endswith(".json")]
        except Exception:
            paths = []
        if not paths:
            print("[i] 尚无批次历史 —— 批次开放并被脚本见到时自动落盘记录")
            return
    for p in paths:
        try:
            store = json.load(open(p, encoding="utf-8"))
        except Exception:
            print(f"[!] 档案损坏/不可读：{p}")
            continue
        turns_map = store.get("turns") or {}
        if not turns_map:
            print(f"[i] {p} 里还没有批次记录")
            continue
        print(f"== 批次历史（{store.get('student_code') or '?'}，共 {len(turns_map)} 个）==")
        order = sorted(turns_map.values(),
                       key=lambda r: r.get("first_seen", ""), reverse=True)
        for r in order:
            print(f"  - {describe_turn(r)}")
            print(f"      首见 {r.get('first_seen')}  末见 {r.get('last_seen')}  "
                  f"共见 {r.get('seen_count')} 次")
        print(f"[i] 档案：{p}")


def load_courses(turn_id, page=1, page_size=20, keyword="", teacher=""):
    if not STATE["token"] or not STATE["student_id"]:
        return {"ok": False, "message": "未登录/未获取学生ID"}
    # v0.3.2 逆向对齐（前端 getList 真实载荷）:
    #   必带 turnId/studentId/semesterId/pageNo/pageSize；默认 canSelect:true（只看可选课）
    if not STATE.get("semester_id"):
        STATE["semester_id"] = 0
    payload = {
        "turnId": int(turn_id),
        "studentId": int(STATE["student_id"]),
        "semesterId": int(STATE["semester_id"]),
        "pageNo": int(page),
        "pageSize": int(page_size),
        "canSelect": True,
    }
    if keyword:
        payload["lessonNameOrCode"] = keyword.strip()
        payload["courseNameOrCode"] = keyword.strip()
    # 教师名透传（GUI 不区分时留空即可；命令行 --teacher 可指定）
    if teacher:
        payload["teacherNameOrCode"] = teacher.strip()
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
    """std-count 实时容量。
    v0.3.2 逆向修正: 前端 changeStdCountMap 表明 data 是 {"lessonId": "已选数-重修数"} 字符串字典
    （"split('-')" 第一段=已选, 第二段=有重修占位时的重修数），不再是 {selectedCount/limitCount} 数组。
    limit 仍取 lesson 对象的 limitCount（调用方传入对比）；返回 (selected, limit) 或 None。"""
    try:
        r = cs_get(f"/std-count?lessonIds=" + str(lesson_id), token=token, timeout=8)
        d = r.json()
        if d.get("result") == 0 and isinstance(d.get("data"), dict):
            v = d["data"].get(str(lesson_id))
            if v is None:   # 键可能不是字符串 lessonId（int 键 JSON 后变字符串，双保险）
                for k, val in d["data"].items():
                    if str(k) == str(lesson_id):
                        v = val
                        break
            if v is not None:
                sel = int(str(v).split("-")[0] or 0)
                lesson = next((l for l in STATE.get("courses", [])
                               if str(l.get("id")) == str(lesson_id)), None) or {}
                return (sel, lesson.get("limitCount"))
    except Exception:
        pass
    return None


def _lesson_of(payload):
    try:
        return payload["requestMiddleDtos"][0]["lessonAssoc"]
    except Exception:
        return None


# ---------------- v0.3.4 新增（2026-09-13 前端 JS 全量还原的补充端点） ----------------

def enter_turn(turn_id, quiet=False):
    """进入批次：GET /{sid}/turn/{turnId}/select（前端进入选课页的第一调用，
    服务端可能在此时初始化该批次的选课会话）。幂等：成功后会话内缓存不再重进；
    失败只记日志、返回 False，调用方可稍后重试（不阻塞开抢）。"""
    if not STATE.get("student_id"):
        return False
    cache = STATE.setdefault("entered_turns", set())
    key = f"{STATE['student_id']}:{turn_id}"
    if key in cache:
        return True
    try:
        r = cs_get(f"/{STATE['student_id']}/turn/{turn_id}/select", timeout=(3, 6))
        if r.status_code == 200:
            d = r.json()
            if d.get("result") == 0:
                cache.add(key)
                if not quiet:
                    log(f"进入批次 turn={turn_id}: ok")
                return True
            if not quiet:
                log(f"进入批次 turn={turn_id}: {d.get('message')}")
        elif not quiet:
            log(f"进入批次 turn={turn_id}: HTTP {r.status_code}（忽略）")
    except Exception as e:
        if not quiet:
            log(f"进入批次异常：{e}（忽略）")
    return False


def preload_capacity_light(turn_id):
    """v0.3.4: 容量预载提速 —— 优先 GET /simplest-lessons/{turnId}（前端轻量列表，
    无分页/无查询载荷，单发拿全量）；失败回退 query-lesson page_size=500。
    返回缓存课程条数。"""
    try:
        r = cs_get(f"/simplest-lessons/{turn_id}", timeout=(3, 8))
        d = r.json()
        if d.get("result") == 0:
            data = d.get("data")
            lessons = data if isinstance(data, list) else (data or {}).get("lessons") or []
            if lessons:
                known = {str(l.get("id")): l for l in STATE.get("courses", [])}
                for l in lessons:
                    lid = str(l.get("id"))
                    if lid in known:
                        # 只补缺的字段，保留已加载的详情
                        for k, v in l.items():
                            known[lid].setdefault(k, v)
                    else:
                        known[lid] = l
                STATE["courses"] = list(known.values())
                log(f"容量缓存(simplest-lessons)：{len(lessons)} 条")
                return len(lessons)
    except Exception:
        pass
    try:
        r = load_courses(turn_id, page=1, page_size=500)
        return r.get("count", 0) if r.get("ok") else 0
    except Exception:
        return 0


def check_selected(turn_id):
    """v0.3.4: GET /selected-lessons/{turnId}/{sid} —— 成功后验证真实已选清单。"""
    try:
        r = cs_get(f"/selected-lessons/{turn_id}/{STATE['student_id']}", timeout=(3, 8))
        d = r.json()
        if d.get("result") == 0:
            data = d.get("data")
            lessons = data if isinstance(data, list) else (data or {}).get("lessons") or []
            names = []
            for l in lessons[:20]:
                c = l.get("course") or {}
                names.append(str(c.get("nameZh") or c.get("name") or l.get("id")))
            log(f"[√] 已选清单({len(lessons)})：{('、'.join(names)) if names else '空'}")
            return lessons
    except Exception as e:
        log(f"已选清单查询失败：{e}")
    return []


def run_predicate(turn_id, lesson_id):
    """v0.3.4: 选课预检（--predicate 开启；与 add-request 同构载荷）。
    POST /add-predicate → 轮询 /predicate-response/{sid}/{requestId}。
    前端语义：消息文本 'ATTEND' = 规则通过；其余 textZh = 规则拒绝原因。
    返回 (True, 'ATTEND')=通过 | (False, 原因)=被拒 | (None, msg)=未知。"""
    sid = STATE["student_id"]
    payload = {
        "studentAssoc": int(sid),
        "courseSelectTurnAssoc": int(turn_id),
        "requestMiddleDtos": [{"lessonAssoc": int(lesson_id), "virtualCost": 0,
                               "scheduleGroupAssoc": None}],
        "coursePackAssoc": None,
    }
    try:
        r = cs_post("/add-predicate", payload, timeout=(3, 6))
        if r.status_code != 200:
            return (None, f"HTTP {r.status_code}")
        d = r.json()
        if d.get("result") != 0:
            return (None, d.get("message") or "result!=0")
        rid = d.get("data")
        if isinstance(rid, dict):
            rid = rid.get("id") or rid.get("requestId")
        if rid is None:
            return (None, "未返回 requestId")
        for gap in (0.4, 0.8, 1.0, 1.5):
            time.sleep(gap)
            try:
                rr = cs_get(f"/predicate-response/{sid}/{rid}", timeout=(3, 6))
                rd = rr.json()
            except Exception:
                continue
            if rd.get("result") != 0:
                continue
            data = rd.get("data")
            if data is None:
                continue
            msgs = data.get("messages") if isinstance(data, dict) else None
            if isinstance(msgs, dict) and msgs:
                v = next(iter(msgs.values())) or {}
                text = v.get("textZh") or v.get("text") or ""
                return (text == "ATTEND", text or "空消息")
            if isinstance(data, dict):
                if data.get("success") is True:
                    return (True, "ATTEND")
                em = data.get("errorMessage") or {}
                text = em.get("textZh") or em.get("text") or "被拒"
                if data.get("resend"):
                    return (None, f"要求重发({text})")
                return (False, text)
            if isinstance(data, str):
                return (data == "ATTEND", data)
        return (None, "轮询超时")
    except Exception as e:
        return (None, f"异常 {e}")


def describe_turn(turn):
    """v0.3.4: 把批次(轮次)对象渲染成一行人话：名称 + 所有时间窗字段
    （selectDateTime/previewDateTime/dropDateTime 等，扁平或嵌套 dict 均可）。"""
    parts = [f"id={turn.get('id')}"]
    for k in ("name", "nameZh", "title"):
        if turn.get(k):
            parts.append(str(turn[k]))
            break

    def _walk(obj, prefix=""):
        out = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, dict):
                    out += _walk(v, key)
                elif any(t in key.lower() for t in ("time", "date")):
                    out.append(f"{key}={v}")
        return out

    parts += _walk(turn)
    return "  ".join(parts)


def _poll_add_drop(student_id, request_id, resend_payload, resend_left=2):
    """轮询 add-drop-response（v0.3: 结果含 success / errorMessage.text / resend）。
    resend=true 时前端会弹窗让用户重发 —— 这里自动重提（最多 resend_left 次）。
    v0.3.3: 自适应轮询间隔 0.4/0.8/1.5/2s…—— 多数结果 <1s 就绪，
    旧版固定先睡 2s，成功路径平均白等 1.5s+。"""
    gaps = (0.4, 0.8, 1.5, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
    for k, gap in enumerate(gaps, 1):
        if STATE["rush_stop"]:
            return
        time.sleep(gap)
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
                # v0.3.4: 拉真实已选清单二次确认（GET /selected-lessons/{turn}/{sid}）
                if STATE.get("current_turn_id"):
                    check_selected(STATE["current_turn_id"])
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
    容量预检 + 令牌过期/401 快速止损 + 节拍抖动。
    v0.3.3: 连接池预热 + 容量预检按时间节流(≥5s,不再每5次一发) +
    add-request 超时收紧(3,6)s + 403 同步止损 + 真随机抖动。"""
    n = int(student_id)
    payload = {
        "studentAssoc": n,
        "courseSelectTurnAssoc": int(turn_id),
        "requestMiddleDtos": [{"lessonAssoc": int(lesson_id),
                               "virtualCost": 0,
                               "scheduleGroupAssoc": None}],
        "coursePackAssoc": None,
    }
    limit_desc = "无限次" if max_times == 0 else f"最多{max_times}次"
    log(f"抢课开始：lessonId={lesson_id} turnId={turn_id} 间隔={interval}s {limit_desc}")
    STATE["rush_attempts"] = 0
    # 连接池预热：先打一发轻量请求把 TLS 会话建立好，
    # 开抢第一发 add-request 省掉 100~300ms 握手（实测时延差）
    try:
        STATE["session"].get(f"{CS_API}/getCurrentDateTime",
                             headers=api_headers(STATE["token"]),
                             timeout=(3, 5), allow_redirects=False)
    except Exception:
        pass
    STATE["current_turn_id"] = turn_id
    # v0.3.4: 进入批次（GET /{sid}/turn/{turnId}/select，前端进入选课页第一调用）；
    # 失败不阻塞开抢，循环内 15s 节流重试
    enter_ok = enter_turn(turn_id)
    enter_retry_at = 0.0 if enter_ok else time.time() + 15.0
    # v0.3.4: 可选预检（--predicate）：开抢前跑一发 add-predicate 提前暴露规则拒绝原因；
    # 被拒不终止（开抢瞬间规则窗口可能变化），仅提示
    if STATE.get("predicate_enabled"):
        ok, msg = run_predicate(turn_id, lesson_id)
        tag = "通过" if ok else ("被拒" if ok is False else "不确定")
        log(f"[预检] {tag}：{msg}")
    last_msg = ""
    repeat = 0
    backoff = 0.0          # 频控退避(秒)
    cap_checked_at = time.time()   # 容量预检节流（首查在开抢 5s 后，宽限期不打）
    cap_full_seen = 0      # 连续满员计数
    t_start = time.time()
    for i in itertools.count(1):
        if max_times and i > max_times:
            log("已达最大次数，停止")
            break
        STATE["rush_attempts"] = i
        if STATE["rush_stop"]:
            log("抢课已手动停止")
            break
        # 令牌过期/临近过期止损（v0.3.4: 先凭 SESSION 现发新 token, 失败才停止）
        exp = jwt_exp(STATE["token"])
        if exp and exp <= int(time.time()) + 10:
            if (time.time() - STATE.get("_last_refresh_at", 0) >= 60
                    and refresh_token_via_session()):
                STATE["_last_refresh_at"] = time.time()
                continue
            log("[!] 令牌已过期且 SESSION 现发失败 —— 请重新复制完整 Cookie（含 SESSION）")
            STATE["rush_last"] = "令牌过期"
            break
        # 容量预检（v0.3.3: 纯时间节流 ≥5s 一次；开抢后前 5s 宽限期跳过 ——
        # 旧版高频模式下每 5 次一发 std-count，等于把 add-request 吞吐砍半）
        if not enter_ok and time.time() >= enter_retry_at:
            enter_ok = enter_turn(turn_id, quiet=True)
            if not enter_ok:
                enter_retry_at = time.time() + 15.0
        if time.time() - cap_checked_at >= 5.0:
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
            r = cs_post("/add-request", payload, timeout=(3, 6))
            data = {}
            try:
                data = r.json()
            except Exception:
                pass
            msg = r.text[:120] if r.status_code != 200 else "result=" + str(data.get("result"))
            # 401/403 = 令牌失效（Shiro）, 立即止损
            if r.status_code in (401, 403):
                log(f"[!] {r.status_code} 令牌被拒 —— 已停止，请重新复制 Cookie 导入")
                STATE["rush_last"] = f"令牌被拒({r.status_code})"
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
            # 节拍抖动 ±25%（v0.3.3: 真随机；旧版 (i*常数)%100 是确定性序列，
            # 每次重跑节拍完全相同，容易再次与同节奏请求对齐）
            sleep_s = sleep_s * random.uniform(0.75, 1.25)
            time.sleep(sleep_s)
    STATE["rush_running"] = False
    log("抢课线程结束")




def start_rush(turn_id, lesson_id, interval, max_times):
    if STATE["rush_running"]:
        return {"ok": False, "message": "抢课已在运行"}
    if not STATE.get("student_id"):
        # 未取到内部学生 ID 时 worker 内 int("") 会抛异常、线程静默死亡且 rush_running 永挂 True
        return {"ok": False, "message": "未登录（缺 student_id）—— 请先导入 Cookie/登录并刷新轮次"}
    STATE["rush_stop"] = False
    STATE["rush_running"] = True
    STATE["rush_log"] = []
    STATE["_log_total"] = 0
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
        self._log_seen = 0   # 已显示到的全局日志序号（配合 _log_total 增量；start_rush 清空日志时归零重同步）
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
        # v0.3: 搜索框关键词进查询载荷（课程名/代码；teacherNameOrCode 由同框透传）
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
                now = time.time()   # target 已换算为本地轴（ts - offset），对比须同轴
                if target and target > now:
                    wait = max(0.0, target - now - pre)
                    log(f"轮次开抢时间 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(target + STATE.get('server_offset', 0)))}，预热 {pre} 秒，等待 {int(wait)} 秒")
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
                # v0.3.3: 到点前复校时钟 + 末段 1s 自旋（开抢抖动压到 <2ms）
                if time.time() - STATE.get("server_time_at", 0) > 120:
                    if get_server_time():
                        target = self._turn_start_target() or target
                        log(f"服务器时钟已复校（offset={round(STATE['server_offset'],1)}s）")
                if target and target > time.time():
                    smart_wait_until(target, stop_fn=lambda: STATE["rush_stop"])
                if STATE["rush_stop"]:
                    log("[预热] 已取消")
                    self._preheat = None
                    return
                res = start_rush(turn_id, lesson_id, interval, max_times)
                if not res.get("ok"):
                    log(f"[!] 启动抢课失败：{res.get('message')}")
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
            # 日志增量（单调度量对齐；修复旧版"len<游标→归零"在 500 条封顶截断后
            # len==游标 恒成立、新日志永不显示（GUI 日志冻结）且截断时整屏重复的问题）
            total = STATE.get("_log_total", 0)
            if total < self._log_seen:      # start_rush 已清空重置 → 重同步
                self._log_seen = 0
            new = total - self._log_seen
            if new > 0:
                for line in STATE["rush_log"][-new:]:
                    self.txt_log.insert("end", line + "\n")
                self._log_seen = total
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
                return ts - STATE.get("server_offset", 0)
            import datetime as _dt
            s = str(v).strip().replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S"):
                try:
                    ts = _dt.datetime.strptime(s, fmt).timestamp()
                    # smart_wait_until 走本地 time.time()，须换算到本地时间轴：
                    # offset = server - local（正=本地慢），本地轴目标 = 服务器墙钟epoch - offset。
                    # 旧版 +offset 会把时钟偏差翻倍 —— 本地慢 5s 时实际晚开抢 10s。
                    return ts - STATE.get("server_offset", 0)
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
    ap.add_argument("--search", default="", help="只预览课程不抢（配合 --turn-id）；@老师名=按教师搜")
    ap.add_argument("--prestart", type=int, default=5, help="轮次开抢前预热秒")
    ap.add_argument("--poll", type=int, default=0, help="轮次未开放时每 N 秒轮询(0=立即退出)")
    ap.add_argument("--predicate", action="store_true",
                    help="开抢前跑 add-predicate 预检，提前暴露规则拒绝原因（多约 1-2s）")
    ap.add_argument("--history", action="store_true",
                    help="显示本地积累的历史批次档案后退出（批次开放时自动落盘记录）")
    ap.add_argument("--turn-id", type=int, default=None, help="指定轮次 id(默认取第一个开放轮次)")
    args = ap.parse_args(argv)

    # v0.3.4: --history 无需登录 —— 无 cookie/config 时直接扫描全部档案
    if args.history and not (args.cookie or args.config):
        show_turn_history()
        return 0

    if not (args.cookie or args.config):
        print("[!] 需要 --cookie 或 --config")
        ap.print_help()
        return 1
    cookie = args.cookie or ""
    interval_ms = args.interval_ms
    max_times = args.max_times
    STATE["predicate_enabled"] = bool(args.predicate)
    if args.config:
        try:
            cfg = json.load(open(args.config, encoding="utf-8"))
        except Exception as e:
            print(f"[!] 配置读取失败: {e}")
            return 1
        cookie = cfg.get("cookie", "") or cookie
        interval_ms = int(cfg.get("interval", interval_ms))
        max_times = int(cfg.get("maxTimes", max_times))
    # v0.3.4: --history 显示本地批次历史档案（有 cookie 则定位本人档案，无则扫描全部）
    if args.history:
        if cookie and eams_set_cookie(cookie).get("ok"):
            show_turn_history(_history_file())
        else:
            show_turn_history()
        return 0
    res = eams_set_cookie(cookie if isinstance(cookie, str) else str(cookie))
    if not res.get("ok"):
        print(f"[!] Cookie 解析失败: {res.get('message')}")
        return 1
    get_server_time()   # CLI 也先校时：保证 prestart 等待/预热用服务器时间轴
    _exp = jwt_exp(STATE["token"])
    _left = f"{(_exp - int(time.time())) // 60} 分钟" if _exp else "未知"
    print(f"[*] 已载入: 学号={STATE.get('student_code')} token剩余={_left}")

    # 轮次: 可选轮询等待开放
    turns = load_turns()
    while not turns and args.poll:
        # v0.3.4 修复: 旧写法 "...%ds..." % poll 会把时间戳里的 %H 误当格式符 → ValueError
        print(f"{time.strftime('[%H:%M:%S]')} 无开放轮次，{args.poll}s 后再试…")
        time.sleep(args.poll)
        turns = load_turns()
    if not turns:
        print("[!] 当前无开放轮次（可加 --poll N 保持轮询）")
        return 0
    # v0.3.4: 批次出现即打印完整时间窗（含 preview/select/drop 全部时间字段）
    for t in turns:
        print(f"[*] 批次: {describe_turn(t)}")
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
    now = time.time()   # target 已换算到本地时间轴（ts - offset），对比须同轴
    if target and target > now and args.prestart > 0:
        wait = max(0, target - now - args.prestart)
        print(f"[*] 开抢时间 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(target + STATE.get('server_offset', 0)))}，"
              f"预热 {args.prestart}s，等待 {int(wait)}s")
        deadline = time.time() + wait
        while time.time() < deadline:
            time.sleep(min(1.0, max(0.0, deadline - time.time())))
        # v0.3.3: 到点前复校时钟（等待 >120s 时偏差可能已积累），
        # 然后末段 1s 自旋 —— 开抢抖动从 sleep 粒度(~15ms) 压到亚毫秒
        if time.time() - STATE.get("server_time_at", 0) > 120:
            if get_server_time():
                target = turn_start_target_ts(turn) or target
                print(f"[*] 时钟复校 offset={round(STATE['server_offset'], 1)}s")
        smart_wait_until(target, stop_fn=lambda: STATE["rush_stop"])

    # 预览搜索（不开抢）。支持 "关键词" 或 "@教师名" 前缀语法
    if args.search:
        kw = args.search
        teacher = ""
        if kw.startswith("@"):
            teacher, kw = kw[1:].strip(), ""   # 纯教师搜索
        r = load_courses(tid, page=1, page_size=20, keyword=kw, teacher=teacher)
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
    # v0.3.3: 抢前建课程 limit 缓存 —— 直接 --targets 时 STATE["courses"] 为空,
    # check_capacity 拿不到 limitCount，"满员自动停止"会形同虚设。
    # v0.3.4: 优先 simplest-lessons（单发轻量端点），失败自动回退 query-lesson(500)
    try:
        n_cached = preload_capacity_light(tid)
        if not n_cached:
            print("[!] 容量缓存为空（满员检测将依赖 std-count 实时值）")
    except Exception:
        pass
    interval = interval_ms / 1000.0
    print(f"[*] 开始抢课: {targets} 间隔{interval}s 最多{max_times}次"
          f"{'(无限)' if max_times == 0 else ''}，Ctrl+C 停止")
    STATE["rush_stop"] = False
    # v0.3.2: 多目标并行 —— 旧版顺序执行，第二目标要等第一目标结束才开始（高峰期等于放弃）。
    # 改为每个目标独立线程同时抢（共享 rush_stop 可一键停）。
    threads = []
    for ts in targets:
        t = threading.Thread(target=rush_worker, daemon=True,
                             args=(tid, int(ts), STATE["student_id"], interval, max_times))
        t.start()
        threads.append(t)
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        STATE["rush_stop"] = True
        print("\n[!] 已收到中断，停止抢课")
    for t in threads:
        t.join(timeout=5)
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
