#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上海建桥学院（my.gench.edu.cn / eams.gench.edu.cn）抢课辅助脚本
=====================================================================
真正的选课系统：**EAMS**（金智教务系统） https://eams.gench.edu.cn
入口（门户菜单"教务系统（新）"）：https://eams.gench.edu.cn/student/sso-login

本脚本把「需要人工操作」的步骤全部显式列出，等你完成后自动继续。

完整流程：
  1) 登录态获取（二选一）：
     A. 门户 Cookie 方式（可选）：
        你在浏览器登录门户后，复制整串 Cookie，
        用于验证门户会话/看菜单（选课本身在 EAMS）。
     B. EAMS 账密登录（**推荐**，真正的选课系统）：
        - 脚本自动 GET /student/login-salt 取盐
        - 密码 = SHA1(salt + '-' + 你的EAMS密码)   （前端 main.js 逆向确认）
        - POST /student/login，JSON 提交 username/password/captchaToken
        - EAMS 当前 NEED_CAPTCHA=null（无需验证码）；
          若失败次数触发 needCaptcha=true，会提示你人工过滑块后再试
  2) 登录态自动校验：脚本访问 EAMS 选课路径，确认不被 302 弹回登录页。
  3) 选课接口定位：登录后自动抓 EAMS 首页/菜单，列出与选课相关入口。
  4) 抢课（可选）：按你确认的目标课程与接口，高频提交选课请求。

用法：
  python 抢课脚本.py --eams-login             # EAMS 账密登录向导（人工输密码）
  python 抢课脚本.py --eams-login --check     # 登录后只探测，不抢课
  python 抢课脚本.py --eams-login --save      # 登录成功后保存 EAMS 会话 Cookie
  python 抢课脚本.py --eams-check             # 用已保存的 EAMS 会话探测
  python 抢课脚本.py --eams-login --selector-url <选课接口> \
                     --payload "courseId=123" --interval 0.5 --max 200

安全说明：
  - 密码只在内存中用于登录，不写入任何文件（会话 Cookie 可按需 --save 保存）
  - 抢课是写操作，必须你明确提供 --selector-url 和 --payload 才执行
  - 默认间隔 0.5s 且可调，避免对服务器造成过大压力
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse

import requests

BASE = "https://my.gench.edu.cn"
PORTAL = f"{BASE}/FAP5.Portal"
IDENTITY = f"{BASE}/FAP5.IdentityServer"
EAMS = "https://eams.gench.edu.cn"
EAMS_STUDENT = f"{EAMS}/student"
EAMS_CS_API = f"{EAMS}/course-selection-api/api/v1/student/course-select"  # 选课后端（逆向确认）
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")
FORM_CT = "application/x-www-form-urlencoded; charset=UTF-8"
JSON_CT = "application/json;charset=UTF-8"
SESS_FILE = "_eams_session.json"   # 可选：保存 EAMS 会话 Cookie（仅在使用 --save 时写入）


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def make_common_headers(referer: str = None, cookie: str = None, json_ct: bool = False) -> dict:
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
         "Accept": "application/json, text/plain, */*"}
    if referer:
        h["Referer"] = referer
    if cookie:
        h["Cookie"] = cookie
    if json_ct:
        h["Content-Type"] = JSON_CT
    return h


# ----------------------------------------------------------------------
# EAMS 登录（密码由人工输入，不落盘）
# ----------------------------------------------------------------------
def eams_login_wizard(save: bool = False) -> requests.Session:
    print("=" * 70)
    print("[需要您操作] EAMS（金智教务选课系统）账密登录")
    print("  选课系统: https://eams.gench.edu.cn/student/login")
    print("  账号: 学号/工号（如 2611999）")
    print("  密码: EAMS 独立密码（与门户密码可能不同；")
    print("         若你从未改过，试试初始密码或门户密码）")
    print("  说明: 密码仅在本次运行内存中使用，不写入文件；")
    print("        成功后可选 --save 保存 EAMS 会话 Cookie 供下次复用。")
    print("=" * 70)
    try:
        username = input("EAMS 学号: ").strip()
        password = input("EAMS 密码: ").strip()
    except EOFError:
        print("[!] 未读到输入（非交互环境请用 --eams-login 在终端里运行）。")
        sys.exit(1)
    if not (username and password):
        print("[!] 学号或密码为空，退出。")
        sys.exit(1)

    s = requests.Session()
    s.headers.update(make_common_headers(referer=f"{EAMS_STUDENT}/login"))
    s.headers.setdefault("Origin", EAMS)

    # 1) 取盐
    try:
        r = s.get(f"{EAMS_STUDENT}/login-salt", timeout=15)
        salt = r.text.strip()
        print(f"[*] 取盐成功: {salt[:8]}…")
    except Exception as e:
        print(f"[x] 取盐失败: {e}")
        sys.exit(2)

    # 2) SHA1(salt + '-' + 密码)
    enc = sha1(f"{salt}-{password}")

    # 3) POST /student/login
    try:
        r = s.post(f"{EAMS_STUDENT}/login",
                   data=json.dumps({"username": username, "password": enc, "captchaToken": ""}),
                   headers=make_common_headers(referer=f"{EAMS_STUDENT}/login", json_ct=True),
                   timeout=20)
        print(f"[*] HTTP {r.status_code}")
        data = {}
        try:
            data = r.json()
        except Exception:
            print("[*] 响应非JSON:", r.text[:300])
        print("[*] 响应:", json.dumps(data, ensure_ascii=False)[:300])
    except Exception as e:
        print(f"[x] 登录请求失败: {e}")
        sys.exit(2)

    if isinstance(data, dict) and data.get("result") is True:
        print("[√] EAMS 登录成功！会话 Cookie 已保存在内存 session。")
        if save:
            cookies = {c.name: c.value for c in s.cookies}
            with open(SESS_FILE, "w", encoding="utf-8") as f:
                json.dump({"cookies": cookies, "username": username}, f, ensure_ascii=False)
            print(f"[√] 已保存 EAMS 会话到 {SESS_FILE}（含敏感信息，注意删除）。")
        return s
    if isinstance(data, dict) and data.get("needCaptcha"):
        print("[x] EAMS 触发滑块验证码（失败次数过多或风控）。")
        print("    [需要您操作] 打开 https://eams.gench.edu.cn/student/login")
        print("    在浏览器里登录一次 EAMS（过滑块），登录成功后把")
        print("    eams.gench.edu.cn 域名的 Cookie 整串发给我，或手动填入下方：")
        try:
            ck = input("EAMS Cookie（可留空退出）: ").strip()
        except EOFError:
            ck = ""
        if ck:
            s2 = requests.Session()
            s2.headers.update(make_common_headers(referer=f"{EAMS_STUDENT}/login"))
            for part in ck.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    s2.cookies.set(k, v, domain="eams.gench.edu.cn", path="/")
            return s2
        sys.exit("未提供 EAMS 会话，退出。")
    print(f"[x] EAMS 登录失败: {data.get('message') if isinstance(data, dict) else r.text[:200]}")
    print("    [需要您操作] 确认 EAMS 密码正确（与门户密码可能不同）。")
    sys.exit(3)


def eams_load_session() -> requests.Session:
    """从保存的会话文件加载 EAMS Cookie。"""
    if not os.path.exists(SESS_FILE):
        print(f"[x] 未找到会话文件 {SESS_FILE}，请先运行 --eams-login --save。")
        sys.exit(1)
    with open(SESS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    s = requests.Session()
    s.headers.update(make_common_headers(referer=f"{EAMS_STUDENT}/login"))
    for k, v in data.get("cookies", {}).items():
        s.cookies.set(k, v, domain="eams.gench.edu.cn", path="/")
    print(f"[*] 已从 {SESS_FILE} 加载 EAMS 会话（用户: {data.get('username')}）。")
    return s


def get_eams_cs_token(session_or_cookie: requests.Session = None, cookie_str: str = "") -> str:
    """从 session cookie / cookie 字符串中提取选课 JWT（cs-course-select-student-token）。"""
    if cookie_str:
        m = re.search(r"cs-course-select-student-token=([^;\\s]+)", cookie_str)
        if m:
            return m.group(1)
    if session_or_cookie is not None:
        for c in session_or_cookie.cookies:
            if c.name == "cs-course-select-student-token":
                return c.value
    return ""


def eams_cs_headers(token: str) -> dict:
    """选课 API 请求头：Authorization = JWT（前端 withCredentials=false，只靠 token）。"""
    return {
        "Authorization": token,
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{EAMS}/course-selection/",
        "X-Requested-With": "XMLHttpRequest",
    }


def eams_cs_get(s, path: str, token: str = "", timeout: int = 15):
    """GET 选课 API（自动带 token）。"""
    if not token:
        token = get_eams_cs_token(s)
    return requests.get(EAMS_CS_API + path, headers=eams_cs_headers(token),
                        timeout=timeout, allow_redirects=False)


def eams_cs_post(s, path: str, payload: dict, token: str = "", timeout: int = 15):
    """POST 选课 API（JSON）。"""
    if not token:
        token = get_eams_cs_token(s)
    h = eams_cs_headers(token)
    h["Content-Type"] = JSON_CT
    return requests.post(EAMS_CS_API + path, data=json.dumps(payload, ensure_ascii=False),
                         headers=h, timeout=timeout, allow_redirects=False)


def eams_cs_student_id(s, token: str = "") -> str:
    """从 GET /multiple-students 拿当前学生的内部 studentId（open-turns 参数需要内部ID而非学号）。"""
    if not token:
        token = get_eams_cs_token(s)
    r = eams_cs_get(s, "/multiple-students", token=token)
    try:
        data = r.json()
        if data.get("result") == 0:
            lst = data.get("data", [])
            if lst:
                sid = str(lst[0].get("id"))
                print(f"[*] 学生内部ID: {sid}（{lst[0].get('code')} "
                      f"{lst[0].get('person', {}).get('nameZh', '')}）")
                return sid
    except Exception:
        pass
    print(f"[!] 获取 studentId 失败: {r.status_code} {r.text[:150]}")
    return ""


def eams_cs_open_turns(s, student_id: str = "", token: str = "") -> list:
    """GET /open-turns/{studentId} —— 当前开放的选课轮次（studentId 必须内部ID）。"""
    if not token:
        token = get_eams_cs_token(s)
    if not student_id:
        student_id = eams_cs_student_id(s, token=token)
    if not student_id:
        return []
    r = eams_cs_get(s, f"/open-turns/{student_id}", token=token)
    try:
        data = r.json()
        if data.get("result") == 0:
            return data.get("data", [])
        print(f"[!] open-turns 返回异常: {r.text[:200]}")
    except Exception:
        print(f"[!] open-turns 响应非 JSON: {r.status_code} {r.text[:200]}")
    return []


def eams_check_session(s: requests.Session, verbose: bool = False) -> bool:
    """校验 EAMS 登录态：访问选课中心路径，302 弹回登录页则未登录。"""
    for p in ["/student/courseSelect/index", "/student/elective/index", "/student/"]:
        try:
            r = s.get(EAMS + p, timeout=15, allow_redirects=False)
            loc = r.headers.get("Location", "")
            if verbose:
                print(f"  {r.status_code} {p} -> {loc[:60]}")
            if r.status_code in (301, 302, 307, 308) and "/login" in loc:
                return False
        except Exception as e:
            if verbose:
                print(f"  ERR {p}: {e}")
    return True


# ----------------------------------------------------------------------
# EAMS 选课接口定位
# ----------------------------------------------------------------------
def eams_probe(s: requests.Session):
    print("\n== EAMS 选课入口探测 ==")
    paths = [
        "/student/", "/student/home", "/student/index",
        "/student/courseSelect/index", "/student/elective/index",
        "/student/coursePlan/index", "/student/teachingTask/index",
        "/student/courseTable/index", "/student/selectCourse",
    ]
    interesting = []
    for p in paths:
        try:
            r = s.get(EAMS + p, timeout=12, allow_redirects=False)
            loc = r.headers.get("Location", "")
            ct = r.headers.get("Content-Type", "")
            if r.status_code in (301, 302, 307, 308):
                print(f"  {r.status_code} {p} -> {loc[:70]}")
                if "/login" in loc:
                    continue
            elif r.status_code == 200:
                title = re.search(r"<title>(.*?)</title>", r.text, re.S)
                t = title.group(1).strip() if title else ""
                print(f"  {r.status_code} {p} ct={ct[:25]} title={t[:30]}")
                if "login" not in r.text.lower() or len(r.text) > 3000:
                    interesting.append((p, r.text))
        except Exception as e:
            print(f"  ERR {p}: {e}")

    print("\n页面内选课相关链接:")
    seen = set()
    for p, html in interesting:
        for m in re.finditer(r'(?:href|action)="([^"]*)"', html):
            u = m.group(1)
            if any(k in u.lower() for k in ["course", "select", "xk", "elect", "teach", "plan"]):
                if u not in seen:
                    seen.add(u)
                    print(f"  [{p}] {u}")
        for m in re.finditer(r"['\"]([^'\"]*(?:course|select|elect|teach)[^'\"]*)['\"]", html):
            u = m.group(1)
            if u.startswith("/") and u not in seen:
                seen.add(u)
                print(f"  [{p}] {u}")


# ----------------------------------------------------------------------
# 门户（可选）会话
# ----------------------------------------------------------------------
def make_session(cookie_str: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    if cookie_str:
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                s.cookies.set(k, v, domain="my.gench.edu.cn", path="/")
    return s


def check_portal_session(s: requests.Session, verbose: bool = False) -> bool:
    try:
        r = s.get(f"{PORTAL}/pc2.html?rnd=88943677", timeout=15, allow_redirects=False)
        loc = r.headers.get("Location", "")
        if verbose:
            print(f"  pc2.html -> {r.status_code} | Loc={loc[:80]}")
        if r.status_code in (301, 302, 307, 308) and "connect/authorize" in loc:
            return False
        if r.status_code == 200 and ("SignIn2" in r.text or "IdentityServer" in r.text):
            return False
        return True
    except Exception as e:
        if verbose:
            print(f"  ERR {e}")
        return False


# ----------------------------------------------------------------------
# 抢课（需用户明确指定课程与接口）
# ----------------------------------------------------------------------
def rush_course(s: requests.Session, course_id: str, interval: float,
                max_times: int, selector_url: str, payload: dict, json_payload: bool = False):
    print(f"\n== 开始抢课：课程 {course_id}，每 {interval}s 一次，最多 {max_times} 次 ==")
    print("[!] 这是写操作（提交选课请求），请确认目标课程与接口无误。")
    ok = 0
    for i in range(1, max_times + 1):
        try:
            if json_payload:
                r = s.post(selector_url, data=json.dumps(payload, ensure_ascii=False),
                           headers=make_common_headers(json_ct=True), timeout=15)
            else:
                r = s.post(selector_url,
                           data=urllib.parse.urlencode(payload),
                           headers={"Content-Type": FORM_CT, "User-Agent": UA},
                           timeout=15)
            print(f"[{i}] {r.status_code} {r.text[:150]}")
            data = {}
            try:
                data = r.json()
            except Exception:
                pass
            if r.status_code == 200 and (data.get("success") in (True, "true", 1)
                                         or data.get("result") is True):
                ok += 1
                if ok >= 1:
                    print("[√] 选课请求已成功返回，停止。")
                    break
        except Exception as e:
            print(f"[{i}] ERR {e}")
        if i < max_times:
            time.sleep(interval)
    print(f"完成：成功响应 {ok} 次（注：判定字段需按实际接口返回核对）。")


def parse_payload(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    return dict(urllib.parse.parse_qsl(text))


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="建桥学院抢课辅助脚本（含人工步骤向导，选课系统=EAMS）")
    ap.add_argument("--eams-login", action="store_true", help="EAMS 账密登录向导（人工输密码）")
    ap.add_argument("--save", action="store_true", help="EAMS 登录成功后保存会话 Cookie 到文件")
    ap.add_argument("--eams-check", action="store_true", help="用保存的 EAMS 会话探测选课入口")
    ap.add_argument("--cookie", help="门户 Cookie（仅用于门户会话校验/看菜单，选课仍需 EAMS）")
    ap.add_argument("--check", action="store_true", help="只校验登录态并探测定位，不做抢课")
    ap.add_argument("--course", help="目标课程号（用于日志，实际提交需 selector_url/payload）")
    ap.add_argument("--interval", type=float, default=0.5, help="抢课间隔秒数")
    ap.add_argument("--max", type=int, default=100, help="最多请求次数")
    ap.add_argument("--selector-url", help="选课提交接口 URL（EAMS 域名下）")
    ap.add_argument("--payload", help="选课请求体：a=b&c=d 或 JSON")
    ap.add_argument("--json-payload", action="store_true", help="payload 以 JSON 提交（EAMS 常见）")
    args = ap.parse_args()

    print("建桥学院抢课辅助脚本（选课系统 = EAMS）")
    print("选课入口: https://eams.gench.edu.cn/student/")
    print()

    # ---- 优先 EAMS 流程 ----
    if args.eams_login:
        s = eams_login_wizard(save=args.save)
        print("\n[*] 校验 EAMS 登录态…")
        if not eams_check_session(s, verbose=True):
            print("[x] EAMS 会话无效（仍被弹回登录页）。")
            sys.exit(2)
        print("[√] EAMS 登录态有效。")

        # [人工步骤] 检测选课轮次是否开放
        token = get_eams_cs_token(s)
        if token:
            turns = eams_cs_open_turns(s, token=token)
            if turns:
                print(f"[√] 当前有 {len(turns)} 个开放选课轮次：")
                for t in turns:
                    print(f"    turnId={t.get('id')} 名称={t.get('name') or t.get('nameZh')}")
            else:
                print("[!] 当前没有开放的选课轮次（open-turns 为空）。")
                print("    [需要您操作] 选课尚未开始或已结束；")
                print("    请在选课开放时段再运行本脚本，或确认选课时间后告诉我。")
        else:
            print("[!] EAMS 会话中没有 cs-course-select-student-token（选课 JWT）。")
            print("    [需要您操作] 请用浏览器打开选课页：")
            print(f"      {EAMS}/student/for-std/course-select")
            print("    确认能正常看到选课界面后，把 eams.gench.edu.cn 域名的 Cookie 发我，")
            print("    或按提示重新登录。")

        if args.check:
            eams_probe(s)
            print("\n[完成] --check 只做探测。下一步把探测到的选课接口 URL 和请求体发给我，")
            print("或按 `--selector-url/--payload/--course` 示例执行抢课。")
            return
        if not (args.selector_url and args.payload and args.course):
            print("\n[人工步骤] 抢课需要你确认目标课程与选课接口：")
            print("  方法：浏览器登录 EAMS 选课页（或脚本探测出的选课入口），")
            print("        F12 -> Network -> 点选课 -> 复制 POST 请求 URL 和请求体")
            print("  示例：")
            print("  python 抢课脚本.py --eams-login --save \\")
            print("      --course 12345 --selector-url \\")
            print("      \"https://eams.gench.edu.cn/course-selection-api/api/v1/student/course-select/add-request\" \\")
            print("      --payload '{\"studentAssoc\":157302,\"courseSelectTurnAssoc\":1,\"requestMiddleDtos\":[{\"lessonAssoc\":123}]}' \\")
            print("      --json-payload --interval 0.5 --max 200")
            sys.exit("\n未提供选课接口参数，按示例补充后运行。")
        payload = parse_payload(args.payload)
        rush_course(s, args.course, args.interval, args.max,
                    args.selector_url, payload, json_payload=args.json_payload)
        return

    if args.eams_check:
        s = eams_load_session()
        if not eams_check_session(s, verbose=True):
            print("[x] EAMS 会话失效，请重新 --eams-login。")
            sys.exit(2)
        eams_probe(s)
        print("\n[完成] EAMS 会话有效且已探测。")
        return

    # ---- 门户 Cookie（可选）----
    if args.cookie:
        print("[*] 使用门户 Cookie…")
        s = make_session(args.cookie)
        if not check_portal_session(s, verbose=True):
            print("[x] 门户 Cookie 无效（跳回登录页），选课需 EAMS 会话——请改用 --eams-login。")
            sys.exit(2)
        print("[√] 门户会话有效（注意：选课在 EAMS，本 Cookie 只用于门户）。")
        if args.check:
            print("\n[提示] 门户仅提供菜单；真正的选课入口在 eams.gench.edu.cn。")
            print("       请运行 `python 抢课脚本.py --eams-login --check` 获取选课接口。")
            return
        print("\n[提示] 抢课需 EAMS 会话，请运行 `python 抢课脚本.py --eams-login ...`。")
        return

    # ---- 无参数：交互总向导 ----
    print("选择登录方式（选课系统 = EAMS）：")
    print("  1) EAMS 账密登录（推荐，脚本自动 SHA1 加密，无需验证码）")
    print("  2) 门户 Cookie（只用于门户，选课仍需 EAMS）")
    print("  3) 加载已保存的 EAMS 会话文件")
    try:
        ch = input("输入 1 / 2 / 3：").strip()
    except EOFError:
        sys.exit("非交互环境请用 --eams-login / --eams-check 参数。")
    if ch == "1":
        s = eams_login_wizard(save=args.save)
        if args.check or not (args.selector_url and args.payload):
            eams_probe(s)
            print("\n[完成] 探测完成。抢课示例见 --help 顶部。")
        else:
            payload = parse_payload(args.payload)
            rush_course(s, args.course, args.interval, args.max,
                        args.selector_url, payload, json_payload=args.json_payload)
    elif ch == "2":
        print("\n[需要您操作] 粘贴门户 Cookie（整串，浏览器 F12 -> Network 复制）：")
        try:
            ck = input("Cookie: ").strip()
        except EOFError:
            sys.exit(1)
        s = make_session(ck)
        if check_portal_session(s, verbose=True):
            print("[√] 门户会话有效。但选课在 EAMS，请走方式1。")
        else:
            print("[x] 门户 Cookie 无效。")
    elif ch == "3":
        s = eams_load_session()
        if not eams_check_session(s, verbose=True):
            print("[x] EAMS 会话失效，请重新 --eams-login。")
        else:
            eams_probe(s)
    else:
        sys.exit("未知选择。")


if __name__ == "__main__":
    main()