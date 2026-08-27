#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建桥学院抢课助手（tkinter 原生 UI，桌面 exe）
============================================
双击 exe → 直接弹出 tkinter 主窗口（无需浏览器）。
功能：登录（Cookie/账密）、实时状态、选课轮次、课程分页列表、
      抢课控制（预热/高频/成功即停）、运行日志、保活常驻。
后端复用 app.py 的 EAMS 逻辑（纯本地解析 + 网络调用分离）。
"""
import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
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
    "rush_attempts": 0,
    "rush_last": "",
    "course_total": 0,
    "course_page": 1,
    "port": 0,
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
         "Referer": f"{EAMS}/course-selection/", "X-Requested-With": "XMLHttpRequest"}
    if token:
        h["Authorization"] = token
    if json_ct:
        h["Content-Type"] = "application/json;charset=UTF-8"
    return h


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
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def eams_login(username: str, password: str):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS})
    try:
        r = s.get(f"{EAMS_STUDENT}/login-salt", timeout=15)
        salt = r.text.strip()
    except Exception as e:
        return {"ok": False, "message": f"取盐失败：{e}"}
    enc = sha1(f"{salt}-{password}")
    try:
        r = s.post(f"{EAMS_STUDENT}/login",
                   data=json.dumps({"username": username, "password": enc, "captchaToken": ""}),
                   headers={**api_headers(), "Content-Type": "application/json;charset=UTF-8",
                            "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS},
                   timeout=20)
        data = r.json()
    except Exception as e:
        return {"ok": False, "message": f"登录请求失败：{e}"}
    if data.get("result") is True:
        STATE["session"] = s
        STATE["session_cookie_str"] = session_cookie_str(s)
        STATE["student_code"] = username
        log(f"EAMS 账密登录成功：{username}")
        return {"ok": True, "has_token": False,
                "message": "账密登录成功，请用浏览器 Cookie 提供选课 token"}
    if data.get("needCaptcha"):
        return {"ok": False, "need_captcha": True,
                "message": "触发滑块验证码，请在浏览器登录后复制 Cookie 粘贴进来"}
    return {"ok": False, "message": data.get("message", "登录失败")}


def eams_set_cookie(cookie_str: str):
    """纯本地解析 Cookie（零网络），必须含 cs-course-select-student-token。
    studentId 由 load_turns 按需获取。"""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"{EAMS_STUDENT}/login", "Origin": EAMS})
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
                STATE["student_code"] = d["data"][0]["code"]
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


def load_courses(turn_id, page=1, page_size=20):
    if not STATE["token"] or not STATE["student_id"]:
        return {"ok": False, "message": "未登录/未获取学生ID"}
    payload = {"pageNo": int(page), "pageSize": int(page_size)}
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


def rush_worker(turn_id, lesson_id, student_id, interval, max_times):
    payload = {
        "studentAssoc": int(student_id),
        "courseSelectTurnAssoc": int(turn_id),
        "requestMiddleDtos": [{"lessonAssoc": int(lesson_id),
                               "virtualCost": "",
                               "scheduleGroupAssoc": None}],
        "coursePackAssoc": None,
    }
    log(f"抢课开始：lessonId={lesson_id} turnId={turn_id} 间隔={interval}s 最多{max_times}次")
    STATE["rush_attempts"] = 0
    last_msg = ""
    repeat = 0
    for i in range(1, max_times + 1):
        STATE["rush_attempts"] = i
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
            msg = r.text[:120] if r.status_code != 200 else "result=" + str(data.get("result"))
            if msg == last_msg:
                repeat += 1
                if repeat % 10 == 0:
                    log(f"[{i}] 持续 {msg}")
            else:
                log(f"[{i}] {msg}")
                last_msg = msg
                repeat = 0
            if r.status_code == 200 and data.get("result") == 0:
                log(f"[成功] 第{i}次提交成功 result=0")
                STATE["rush_last"] = "提交成功，等待结果"
                for _ in range(5):
                    if STATE["rush_stop"]:
                        break
                    time.sleep(2)
                    try:
                        result = cs_get(f"/add-drop-response/{student_id}/{data.get('data', {}).get('id', '')}")
                        rd = result.json()
                        rr = rd.get("data", {})
                        if rr.get("success") is True:
                            log(f"[√] 选课成功：{json.dumps(rr, ensure_ascii=False)[:200]}")
                            STATE["rush_last"] = "选课成功"
                            break
                        elif rr.get("success") is False:
                            msg = rr.get("errorMessage", {}).get("text", "被拒")
                            log(f"[x] 选课被拒：{msg}")
                            STATE["rush_last"] = f"被拒 {msg}"
                            break
                    except Exception:
                        pass
                break
            sleep_s = interval
            txt_low = (msg or "").lower()
            if r.status_code in (429, 503):
                sleep_s = 5.0
            elif any(k in txt_low for k in ["频繁", "稍后", "风控", "too many", "busy"]):
                sleep_s = 5.0
            elif any(k in txt_low for k in ["未到", "未开", "不在", "not open", "未开始", "还未"]):
                sleep_s = max(0.3, interval)
        except Exception as e:
            msg = f"异常 {e}"
            if msg == last_msg:
                repeat += 1
                if repeat % 10 == 0:
                    log(f"[{i}] 持续异常 {e}")
            else:
                log(f"[{i}] 异常：{e}")
                last_msg = msg
            sleep_s = max(interval, 1.0)
        if i < max_times:
            time.sleep(sleep_s)
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
# tkinter 主窗口（完整 UI，无需浏览器）
# ----------------------------------------------------------------------
class TkApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("建桥学院抢课助手")
        self.root.geometry("780x720")
        self.root.minsize(700, 640)
        self.course_page = 1
        self.course_total_pages = 1
        self._build()
        self._refresh_loop()

    # ---------- UI 构建 ----------
    def _build(self):
        pad = {"padx": 8, "pady": 3}
        # 顶部状态条
        top = tk.Frame(self.root, bg="#eef4ff")
        top.pack(fill="x", **pad)
        self.l_port = tk.Label(top, text="实例: -", bg="#eef4ff", font=("Microsoft YaHei", 9))
        self.l_port.pack(side="left", **pad)
        self.l_login = tk.Label(top, text="登录: 未登录", bg="#eef4ff", font=("Microsoft YaHei", 9))
        self.l_login.pack(side="left", **pad)
        self.l_token = tk.Label(top, text="token: -", bg="#eef4ff", font=("Microsoft YaHei", 9))
        self.l_token.pack(side="left", **pad)
        self.l_srv = tk.Label(top, text="服务器时间: -", bg="#eef4ff", font=("Microsoft YaHei", 9))
        self.l_srv.pack(side="right", **pad)

        # 登录区
        login_f = tk.LabelFrame(self.root, text="1. 登录（EAMS）", padx=8, pady=6)
        login_f.pack(fill="x", **pad)
        tk.Label(login_f, text="学号").grid(row=0, column=0, sticky="e", padx=4)
        self.e_user = tk.Entry(login_f, width=22)
        self.e_user.grid(row=0, column=1, padx=4)
        tk.Label(login_f, text="密码").grid(row=0, column=2, sticky="e", padx=8)
        self.e_pwd = tk.Entry(login_f, width=18, show="*")
        self.e_pwd.grid(row=0, column=3, padx=4)
        tk.Button(login_f, text="账密登录", command=self.do_login).grid(row=0, column=4, padx=6)
        tk.Label(login_f, text="Cookie（整行）").grid(row=1, column=0, sticky="e", padx=4)
        self.e_cookie = tk.Entry(login_f, width=64)
        self.e_cookie.grid(row=1, column=1, columnspan=3, sticky="we", padx=4)
        tk.Button(login_f, text="Cookie 登录", command=self.do_cookie).grid(row=1, column=4, padx=6)
        login_f.columnconfigure(1, weight=1)
        login_f.columnconfigure(3, weight=1)

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
        tk.Label(rush_f, text="开抢时间").grid(row=0, column=0, sticky="e", padx=4)
        self.e_time = tk.Entry(rush_f, width=20)
        self.e_time.grid(row=0, column=1, padx=4)
        self.e_time.insert(0, "留空=立即，格式 2026-08-27 22:00:00")
        tk.Label(rush_f, text="预热(秒)").grid(row=0, column=2, sticky="e", padx=8)
        self.e_pre = tk.Entry(rush_f, width=6)
        self.e_pre.grid(row=0, column=3, padx=4)
        self.e_pre.insert(0, "5")
        tk.Label(rush_f, text="间隔(秒)").grid(row=1, column=0, sticky="e", padx=4)
        self.e_iv = tk.Entry(rush_f, width=6)
        self.e_iv.grid(row=1, column=1, sticky="w", padx=4)
        self.e_iv.insert(0, "0.3")
        tk.Label(rush_f, text="最多次数").grid(row=1, column=2, sticky="e", padx=8)
        self.e_max = tk.Entry(rush_f, width=8)
        self.e_max.grid(row=1, column=3, sticky="w", padx=4)
        self.e_max.insert(0, "300")
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

    def do_login(self):
        u = self.e_user.get().strip()
        p = self.e_pwd.get()
        if not (u and p):
            messagebox.showwarning("提示", "请输入学号和密码")
            return
        res = eams_login(u, p)
        if res.get("ok"):
            messagebox.showinfo("成功", res.get("message", "登录成功"))
        else:
            messagebox.showerror("失败", res.get("message", "登录失败"))

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
        res = load_courses(turn_id, self.course_page)
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
        interval = float(self.e_iv.get() or 0.3)
        max_times = int(self.e_max.get() or 300)
        pre = int(self.e_pre.get() or 5)
        # 开抢时间：留空=立即；否则预热后自动开始
        t_str = self.e_time.get().strip()
        target = 0
        if t_str and "留空" not in t_str:
            try:
                import datetime as _dt
                target = _dt.datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S").timestamp()
            except Exception:
                messagebox.showerror("错误", "开抢时间格式应为 2026-08-27 22:00:00")
                return
        now = time.time() + STATE.get("server_offset", 0)
        if target and target > now:
            wait = max(0, target - now - pre)
            log(f"预定 {t_str} 开抢，预热 {pre} 秒，等待 {int(wait)} 秒")
            threading.Timer(wait, lambda: start_rush(turn_id, lesson_id, interval, max_times)).start()
        else:
            start_rush(turn_id, lesson_id, interval, max_times)
        self.l_rush.config(text="已启动抢课线程", fg="#4a7bff")

    def stop_rush(self):
        STATE["rush_stop"] = True
        log("已请求停止")
        self.l_rush.config(text="已停止", fg="#f56c6c")

    # ---------- 实时刷新 ----------
    def _refresh_loop(self):
        try:
            exp = jwt_exp(STATE["token"])
            left = (exp - int(time.time())) if exp else 0
            self.l_port.config(text=f"实例: 端口 {STATE.get('port', 0)}")
            self.l_login.config(text=f"登录: {STATE.get('student_code') or '未登录'}")
            if left > 0:
                self.l_token.config(text=f"token: 剩余 {int(left//3600)}小时{int(left%3600//60)}分")
            else:
                self.l_token.config(text="token: 无/未提供")
            self.l_srv.config(text=f"服务器时间: {time.strftime('%H:%M:%S')}（校准 {round(STATE.get('server_offset',0),1)}s）")
            rush = "运行中" if STATE["rush_running"] else "未开始"
            self.l_rush.config(text=f"{rush}（已提交 {STATE['rush_attempts']} 次，最近: {STATE['rush_last'] or '-'}）")
            # 日志增量
            cur = len(self.txt_log.get("1.0", "end").splitlines()) - 1
            for line in STATE["rush_log"][cur:]:
                self.txt_log.insert("end", line + "\n")
            self.txt_log.see("end")
        except Exception:
            pass
        self.root.after(1500, self._refresh_loop)

    def run(self):
        self.root.mainloop()


def main():
    # 动态端口
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
    STATE["port"] = port
    # 只跑 tkinter 主窗（无需浏览器/HTTP；如需旧 web 页面可另开）
    app = TkApp()
    app.run()


if __name__ == "__main__":
    main()
