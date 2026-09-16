#!/usr/bin/env python3
"""Gench 公选课平台选课 GUI (tkinter)
依赖: pip3 install requests
运行: python3 gench_enroll_gui.py
"""
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from gench_enroll import GenchClient, items_of, UA, EnrollmentForbidden, ChangeLogger

def app_dir() -> str:
    """打包 exe 后取 exe 所在目录, 脚本运行取脚本目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HERE = app_dir()

# 选课列表的列定义: (列名, 权重拉伸, 宽度, 值提取函数)
# 字段名为逆向实测: classPlan.schedureText/scheduleText, teacherNames, capacityMax, enrolledCount
def _course_of(p): return p.get("course") or p

def _col(field, *alts):
    def fn(p):
        for f in (field,) + alts:
            v = p.get(f)
            if v not in (None, ""):
                return v
            v = _course_of(p).get(f)
            if v not in (None, ""):
                return v
        return ""
    return fn

COURSE_COLUMNS = [
    ("#",            0,   40,  None),   # 行号运行时填充
    ("课程名称",      2,  170,  _col("name")),
    ("教师",          0,   85,  _col("teacherNames", "teacher", "teachers")),
    ("余量",          0,   55,  lambda p: _seat(p)),
    ("人数",          0,   80,  lambda p: f"{_full(p) if _full(p) is not None else '?'}/{_cap(p) if _cap(p) else '?'}"),
    ("学分",          0,   50,  _col("credit")),
    ("上课时间",       2,  170,  _col("scheduleText", "schedule", "classTime", "timeSlot")),
    ("班号",          0,   60,  _col("classNo")),
    ("课程代码",      0,   85,  _col("courseCode")),
    ("精品",          0,   45,  lambda p: "★" if (_course_of(p).get("isHighQualityPublicElective") or p.get("isHighQualityPublicElective")) else ""),
    ("开课学院",      1,  120,  _col("managementDepartmentName")),
    ("评分",          0,   55,  lambda p: _col("avgScore")(p) or ""),
    ("classPlanId",  0,  270,  lambda p: str(p.get("id") or "")),
]

def _full(p): return p.get("enrolledCount")
def _cap(p):  return p.get("capacityMax", p.get("capacity"))
def _seat(p):
    f, c = _full(p), _cap(p)
    if c in (None, "", 0) or f is None:
        return "?"
    return max(0, int(c) - int(f))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Gench 公选课助手")
        root.geometry("1050x680")

        self.client: GenchClient | None = None
        self.terms: list = []
        self.batches: list = []
        self.plans: list = []          # 当前课程列表缓存
        self.plan_key_map: dict = {}  # iid -> 原始 dict       # iid -> 原始 dict
        self.config = self._load_config()
        self.task_queue: list = []     # 定时抢课任务 [{time_str, plan_id, ...}]
        self.snipe_thread = None
        self.snipe_stop = threading.Event()
        self.elig_monitor_stop = threading.Event()
        self.elig_ok = None  # None=未知 True/False
        self.changelog = ChangeLogger()
        self.elig_interval = tk.DoubleVar(value=float(self.config.get("elig_interval", 5.0)))
        self.batch_watch_stop = threading.Event()

        self._build_ui()
        cookie = self.config.get("cookie", "")
        if cookie:
            self.txt_cookie.insert("1.0", cookie)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick_clock()
        threading.Thread(target=self._batch_watch_loop, daemon=True).start()

    def _batch_watch_loop(self):
        """后台: 每60s快照 enrollment-batches, 新建/改动的未开始批次 -> 提示+日志,
        且自动把开抢时间写入队列(如果用户没手动设置)"""
        seen, armed = {}, {}
        last_log = 0
        while not self.batch_watch_stop.is_set():
            try:
                page = self.changelog and self._watch_snapshot(seen)
                if page:
                    for b, st_t in page:
                        key = b["id"]
                        armed.setdefault(key, False)
                        if not armed[key]:
                            armed[key] = True
                            name = b.get('name', '')
                            fire_iso = b.get('enrollDropStartAt', '')
                            self._log(f"👀 发现未开始批次: {name} 开抢 {fire_iso} "
                                      f"(还有 {(st_t-time.time())/60:.0f} 分钟) — 已计入守候")
                        fk = "fired_" + key
                        if st_t - time.time() <= 60 and not armed.get(fk):
                            # 开抢前60秒: 蜂铃+提示; 到点后自动启动定时抢(基于服务器偏移)
                            armed["fired_" + key] = True
                            self._log(f"🚀 批次 [{b.get('name')}] 60秒倒计时, 准备开抢!")
                            threading.Thread(target=self._fire_at, args=(st_t, b), daemon=True).start()
            except Exception as e:
                now = time.time()
                if now - last_log > 300:
                    self._log(f"批次监控异常: {e}")
                    last_log = now
            self.batch_watch_stop.wait(60)

    def _fire_at(self, fire_ts, batch):
        """到点: 提前 early_sec 连发队列任务 (即使资格未开也先打, 若资格突然翻开立即全速)"""
        try:
            c = self._mk_client()
        except Exception as e:
            self._log(f"❌ {e}"); return
        early = max(0.2, float(self.var_early.get()))
        while self._now() < fire_ts - early:
            time.sleep(min(0.5, max(0.02, (fire_ts - early) - self._now())))
        self._log(f"⏰ 开抢点已到({batch.get('name')}), 连发队列选课!")
        ids = [str(v[2]) for v in (self.tvq.item(i, 'values') for i in self.tvq.get_children())]
        got = set()
        round_n = 0
        while round_n < 30 and not self.snipe_stop.is_set():
            round_n += 1
            for pid in ids:
                if pid in got:
                    continue
                try:
                    c.enroll(pid)
                    got.add(pid)
                    self._log(f"✅ 抢到 ({pid})")
                    self.root.after(0, lambda p=pid: self._mark_task_status(p, "已抢到"))
                    if self.var_once.get():
                        return
                except EnrollmentForbidden:
                    # 资格拒绝 -> 不空转打爆服务器; 每30s探测一次资格, 放开立即继续连发
                    if round_n == 1:
                        self._log("⛔ 资格未开, 转10s节奏守候(资格放开即全速)")
                    time.sleep(10)
                    break
                except Exception:
                    pass
        self._log("批次抢收尾完成")

    def _mark_task_status(self, pid, status="已抢到"):
        for iid in self.tvq.get_children():
            if str(self.tvq.item(iid, "values")[2]) == pid:
                self.tvq.set(iid, "status", status)

    def _watch_snapshot(self, seen):
        """单次批次快照, 返回 [(batch, fire_ts), ...] 未开始的"""
        from datetime import datetime as dt
        out = []
        try:
            c = self._mk_client()
            page = c.all_batches(size=50)
            items = page.get("items", []) if isinstance(page, dict) else (page or [])
            for b in items:
                cur = {k: b.get(k) for k in ("name", "academicYearTermId",
                                             "enrollDropStartAt", "enrollDropEndAt",
                                             "dropOnlyStartAt", "dropOnlyEndAt")}
                self.changelog.snapshot(f"batch.{b['id']}", cur)
                try:
                    st = dt.fromisoformat(cur["enrollDropStartAt"]).timestamp()
                except Exception:
                    continue
                if st > time.time():
                    out.append((b, st))
        except Exception as e:
            raise e
        return out

    def _tick_clock(self):
        try:
            self.lbl_clock.configure(
                text=f"服务器时间≈ {datetime.fromtimestamp(self._now()):%H:%M:%S}  (偏移 {self.var_offset.get():+.1f}s, 提前抢 {self.var_early.get()}s)")
        except Exception:
            pass
        self.root.after(1000, self._tick_clock)

    # ============ UI ============
    def _build_ui(self):
        top = ttk.Frame(self.root); top.pack(fill=tk.X, padx=8, pady=6)

        # Cookie 行
        ttk.Label(top, text="Cookie:").pack(side=tk.LEFT)
        self.txt_cookie = tk.Text(top, height=3, width=60, wrap="char")
        self.txt_cookie.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(top, text="测试连接", command=self._test_conn).pack(side=tk.LEFT, pady=2)
        mb = ttk.Menubutton(top, text="配置 ▾")
        menu = tk.Menu(mb, tearoff=0)
        menu.add_command(label="导出配置…", command=self._export_cfg)
        menu.add_command(label="导入配置…", command=self._import_cfg)
        menu.add_separator()
        menu.add_command(label="保存 Cookie 到配置", command=self._save_cookie_cfg)
        mb.configure(menu=menu); mb.pack(side=tk.LEFT)

        # 批次/学期 行
        row2 = ttk.Frame(self.root); row2.pack(fill=tk.X, padx=8)
        ttk.Label(row2, text="学期:").pack(side=tk.LEFT)
        self.cmb_term = ttk.Combobox(row2, width=30, state="readonly")
        self.cmb_term.pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="批次:").pack(side=tk.LEFT)
        self.cmb_batch = ttk.Combobox(row2, width=30, state="readonly")
        self.cmb_batch.pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="刷新批次", command=self._refresh_batches).pack(side=tk.LEFT)
        ttk.Button(row2, text="查询课程", command=self._query_courses).pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="关键词:").pack(side=tk.LEFT, padx=(10, 0))
        self.ent_kw = tk.Entry(row2, width=16); self.ent_kw.pack(side=tk.LEFT)
        self.lbl_elig = ttk.Label(row2, text="资格: ?", foreground="#888")
        self.lbl_elig.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(row2, text="查资格", command=self._check_eligibility).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="监控资格", command=self._toggle_elig_monitor).pack(side=tk.LEFT)
        ttk.Label(row2, text="监控间隔s:").pack(side=tk.LEFT, padx=(4, 0))
        ttk.Spinbox(row2, from_=1, to=120, increment=1, width=5,
                    textvariable=self.elig_interval).pack(side=tk.LEFT)

        # 策略区
        st = ttk.LabelFrame(self.root, text="抢课策略")
        st.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(st, text="轮询间隔(s):").grid(row=0, column=0, sticky=tk.W)
        self.var_interval = tk.DoubleVar(value=float(self.config.get("interval", 2.0)))
        ttk.Spinbox(st, from_=0.2, to=60, increment=0.2, width=7,
                    textvariable=self.var_interval).grid(row=0, column=1)
        ttk.Label(st, text="提前抢(s):").grid(row=0, column=2, sticky=tk.W, padx=(12, 0))
        self.var_early = tk.DoubleVar(value=float(self.config.get("early_sec", 0.5)))
        ttk.Spinbox(st, from_=-30, to=30, increment=0.1, width=7,
                    textvariable=self.var_early).grid(row=0, column=3)
        ttk.Label(st, text="本地钟差修正(s):").grid(row=0, column=4, sticky=tk.W, padx=(12, 0))
        self.var_offset = tk.DoubleVar(value=float(self.config.get("srv_offset", 0.0)))
        ttk.Spinbox(st, from_=-60, to=60, increment=0.1, width=7,
                    textvariable=self.var_offset).grid(row=0, column=5)
        self.var_check_first = tk.BooleanVar(value=bool(self.config.get("check_first", False)))
        ttk.Checkbutton(st, text="抢前先 check(可能更慢)",
                        variable=self.var_check_first).grid(row=0, column=6, padx=8)
        self.var_once = tk.BooleanVar(value=bool(self.config.get("once", True)))
        ttk.Checkbutton(st, text="抢到一门即停", variable=self.var_once).grid(row=0, column=7)
        ttk.Button(st, text="校准本地时间", command=self._calibrate).grid(row=0, column=8, padx=8)
        self.lbl_clock = ttk.Label(st, text=f"本地时间 {datetime.now():%H:%M:%S}  (偏移 {self.var_offset.get():+.1f}s)")
        self.lbl_clock.grid(row=1, column=0, columnspan=9, sticky=tk.W)

        # 课程列表
        lf = ttk.LabelFrame(self.root, text="开放课程列表");
        lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        cols = [c[0] for c in COURSE_COLUMNS]
        self.tv = ttk.Treeview(lf, columns=cols, show="headings")
        for name, weight, width, _ in COURSE_COLUMNS:
            self.tv.heading(name, text=name)
            stretch = "yes" if weight else "no"
            self.tv.column(name, width=width, stretch=stretch)
        vs = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        self.tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vs.pack(side=tk.LEFT, fill=tk.Y)
        self.tv.bind("<Double-1>", self._on_dbl)
        for c in cols:
            self.tv.heading(c, command=lambda cc=c: self._sort_tv(c))
        bar = ttk.Frame(lf); bar.pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(bar, text="加入\n抢课队列", width=9, command=self._add_task).pack(pady=2)
        ttk.Button(bar, text="移除\n所选任务", width=9, command=self._del_task).pack(pady=2)
        ttk.Button(bar, text="立即抢\n所选", width=9, command=self._snipe_now).pack(pady=2)

        # 抢课任务列表
        tf = ttk.LabelFrame(self.root, text="抢课队列 (开抢时间格式 HH:MM:SS)")
        tf.pack(fill=tk.X, padx=8, pady=4)
        top_q = ttk.Frame(tf); top_q.pack(fill=tk.X)
        ttk.Label(top_q, text="新任务开抢时间:").pack(side=tk.LEFT)
        self.ent_fire = tk.Entry(top_q, width=12)
        self.ent_fire.insert(0, "08:00:00")
        self.ent_fire.pack(side=tk.LEFT, padx=4)
        self.tvq = ttk.Treeview(tf, columns=("time", "course", "plan", "status", "cid"), show="headings", height=5)
        for n, w, txt in (("time", 130, "开抢时间"), ("course", 200, "课程"),
                          ("plan", 260, "classPlanId"), ("status", 110, "状态"),
                          ("cid", 0, "courseId")):
            self.tvq.heading(n, text=txt)
            self.tvq.column(n, width=w, stretch=(n != "cid"))
            if n == "cid":
                self.tvq.column(n, minwidth=0, width=0)
        self.tvq.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        qs = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.tvq.yview)
        qs.configure(command=self.tvq.yview); qs.pack(side=tk.LEFT, fill=tk.Y)
        self.tvq.configure(yscrollcommand=qs.set)
        qb = ttk.Frame(tf); qb.pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(qb, text="从列表\n添加", width=8, command=self._add_task).pack(pady=2)
        ttk.Button(qb, text="删除\n所选", width=8, command=self._del_task).pack(pady=2)
        ttk.Button(qb, text="启动\n定时抢", width=8, command=self._start_snipe).pack(pady=2)
        ttk.Button(qb, text="停止", width=8, command=self._stop_snipe).pack(pady=2)
        ttk.Button(qb, text="预约开抢", width=8, command=self._arm_at_border).pack(pady=2)

        # 日志
        self.log = tk.Text(self.root, height=7, state=tk.DISABLED)
        self.log.pack(fill=tk.X, padx=8, pady=4)
    def _log(self, msg: str):
        def f():
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, f"[{datetime.now():%H:%M:%S}] {msg}\n")
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)
        self.root.after(0, f)

    # ============ 配置导入/导出 ============
    def _cfg_dict(self) -> dict:
        return {
            "cookie": self.txt_cookie.get("1.0", tk.END).strip(),
            "interval": self.var_interval.get(),
            "early_sec": self.var_early.get(),
            "srv_offset": self.var_offset.get(),
            "check_first": self.var_check_first.get(),
            "once": self.var_once.get(),
            "tasks": [
                {"fire_time": self.tvq.item(i, "values")[0],
                 "course": self.tvq.item(i, "values")[1],
                 "plan_id": self.tvq.item(i, "values")[2],
                 "course_id": self.tvq.item(i, "values")[4] if len(self.tvq.item(i, "values")) > 4 else ""}
                for i in self.tvq.get_children()
            ],
            "last_plan_ids": [self.plan_key(p) for p in self.plans[:200]],
        }

    def _export_cfg(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", initialfile="gench_config.json",
                                         filetypes=[("JSON 配置", "*.json")])
        if not f:
            return
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(self._cfg_dict(), fh, ensure_ascii=False, indent=2)
        self._log(f"配置已导出: {f}")

    def _import_cfg(self):
        f = filedialog.askopenfilename(filetypes=[("JSON 配置", "*.json")])
        if not f:
            return
        try:
            cfg = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("导入失败", str(e)); return
        self.txt_cookie.delete("1.0", tk.END)
        self.txt_cookie.insert("1.0", cfg.get("cookie", ""))
        self.var_interval.set(cfg.get("interval", 2.0))
        self.var_early.set(cfg.get("early_sec", 0.5))
        self.var_offset.set(cfg.get("srv_offset", 0.0))
        self.var_check_first.set(cfg.get("check_first", False))
        self.var_once.set(cfg.get("once", True))
        for i in self.tvq.get_children():
            self.tvq.delete(i)
        for t in cfg.get("tasks", []):
            self.tvq.insert("", tk.END, values=(t["fire_time"], t.get("course", ""),
                                                t["plan_id"], "待触发", t.get("course_id", "")))
        self._save_cookie_cfg(silent=True)
        self._log(f"配置已导入: {f}")

    def _save_cookie_cfg(self, silent=False):
        self._persist_config()
        if not silent:
            self._log("Cookie 已保存到配置文件")

    def _load_config(self) -> dict:
        try:
            return json.load(open(self._cfg_path(), encoding="utf-8"))
        except Exception:
            return {}

    def _cfg_path(self):
        return os.path.join(HERE, "gench_config.json")

    def _persist_config(self):
        try:
            with open(self._cfg_path(), "w", encoding="utf-8") as fh:
                json.dump(self._cfg_dict(), fh, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"配置保存失败: {e}")

    def _on_close(self):
        self.snipe_stop.set()
        self._persist_config()
        self.root.destroy()

    # ============ 连接 / 数据 ============
    def _mk_client(self) -> GenchClient:
        cookie = self.txt_cookie.get("1.0", tk.END).strip()
        if not cookie:
            raise RuntimeError("请先粘贴浏览器 Cookie")
        return GenchClient(cookie)

    def _test_conn(self):
        def run():
            try:
                c = self._mk_client()
                c.req("GET", "student/class-plans/open", params={"pageIndex": 1, "pageSize": 1})
                self._log("✅ Cookie 有效, 登录态正常")
                self._persist_config()
            except Exception as e:
                self._log(f"❌ 连接失败: {e}")
        threading.Thread(target=run, daemon=True).start()

    # ============ 选课资格 ============
    def _update_elig_label(self, ok, msg=""):
        self.elig_ok = ok
        if ok:
            self.lbl_elig.configure(text="资格: ✅ 可选课", foreground="#1b7f3b")
        elif ok is False:
            self.lbl_elig.configure(text=f"资格: ⛔ {msg[:24]}", foreground="#b3261e")
        else:
            self.lbl_elig.configure(text="资格: ?", foreground="#888")

    def _check_eligibility(self):
        def run():
            c = None
            try:
                c = self._mk_client()
                d = c.eligibility()
            except Exception as e:
                self._log(f"资格查询失败: {e}")
                self.root.after(0, lambda: self._update_elig_label(None))
                return
            if d.get("canEnroll") is False:
                msg0 = d.get("message") or d.get("msg") or "无资格"
                code = d.get("code", "")
                self._log(f"⛔ 无选课资格 [{code}]: {msg0}")
                self.root.after(0, lambda: self._update_elig_label(False, msg0))
            else:
                self._log("✅ 选课资格已通过")
                self.root.after(0, lambda: self._update_elig_label(True))
        threading.Thread(target=run, daemon=True).start()

    def _toggle_elig_monitor(self):
        if self.elig_monitor_stop.is_set() or not getattr(self, "elig_thread", None) or \
                not self.elig_thread.is_alive():
            self.elig_monitor_stop.clear()
            self.elig_thread = threading.Thread(target=self._elig_monitor_loop, daemon=True)
            self.elig_thread.start()
            self._log("开始监控选课资格 (每30s探测, 放开即响铃+自动刷新批次)")
        else:
            self.elig_monitor_stop.set()
            self._log("资格监控已停止")

    def _elig_monitor_loop(self):
        beep = lambda: self.root.after(0, lambda: self.root.bell())
        miss = 0
        while not self.elig_monitor_stop.is_set():
            try:
                d = self._mk_client().eligibility()
                can = d.get("canEnroll")
                changed = self.changelog.snapshot("eligibility.canEnroll", can)
                if can is False:
                    miss += 1
                    if changed or miss % 6 == 1:
                        self._log(f"· 资格未放开 [{d.get('code')}]: {d.get('message')}")
                    self.root.after(0, lambda: self._update_elig_label(
                        False, d.get('message', '')))
                    for _ in range(5):
                        beep()
                        time.sleep(0.4)
                    self._log("🎉 选课资格已放开! 请立即刷新批次并抢课!")
                    self.root.after(0, lambda: self._update_elig_label(True))
                    self.root.after(0, self._refresh_batches)
                    # 放开后可自动启动定时抢(若队列有任务)
                    if self._queue_has_tasks():
                        self.root.after(0, self._start_snipe)
                    return
            except Exception as e:
                self._log(f"监控探测异常: {e}")
            self.elig_monitor_stop.wait(30)

    def _queue_has_tasks(self) -> bool:
        return bool(self.tvq.get_children())

    def _refresh_batches(self):
        def run():
            try:
                c = self._mk_client()
                self.terms = items_of(c.req("GET", "academic-year-terms",
                                            params={"pageSize": 50}))
                self.batches = c.active_batches()
                def fill():
                    self.cmb_term["values"] = [
                        f"{t.get('academicYear')}-{t.get('termCode')} ({t['id'][:8]}…)"
                        for t in self.terms]
                    a = [f"{b.get('name')} ({b['id'][:8]}…)" for b in self.batches]
                    self.cmb_batch["values"] = a
                    if self.batches:
                        self.cmb_batch.current(0)
                    elif self.terms:
                        self.cmb_term.current(0)
                self.root.after(0, fill)
                self._log(f"批次 {len(self.batches)} 个 (active), 学期 {len(self.terms)} 个")
            except Exception as e:
                self._log(f"刷新失败: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _sel_term_batch(self):
        term_id = batch_id = None
        vt = self.cmb_term.get(); vb = self.cmb_batch.get()
        if vb:
            for b in self.batches:
                if b["id"][:8] in vb:
                    batch_id, term_id = b["id"], b["academicYearTermId"]
                    break
        if not term_id and vt:
            for t in self.terms:
                if t["id"][:8] in vt:
                    term_id = t["id"]; break
        return term_id, batch_id

    def _query_courses(self):
        def run():
            try:
                c = self._mk_client()
                term_id, batch_id = self._sel_term_batch()
                if not term_id:
                    self._log("请先选择学期或批次"); return
                page = c.open_plans(term_id, batch_id,
                                    keyword=self.ent_kw.get().strip() or None, size=100)
                plans = items_of(page)
                self.plans = plans
                def fill():
                    self.tv.delete(*self.tv.get_children())
                    self.plan_key_map = {}
                    for i, p in enumerate(plans):
                        vals = []
                        for name, _, _, fn in COURSE_COLUMNS:
                            v = fn(p)
                            vals.append(i if name == "#" else v)
                        iid = self.tv.insert("", tk.END, values=vals)
                        self.plan_key_map[iid] = p
                    self._log(f"查询到 {len(plans)} 门课程 (关键词={self.ent_kw.get() or '无'})")
                self.root.after(0, fill)
            except Exception as e:
                self._log(f"查询失败: {e}")
        threading.Thread(target=run, daemon=True).start()

    def plan_key(self, p) -> str:
        return str(p.get("id") or (p.get("courseId"), p.get("classPlanId")))

    def _on_dbl(self, e):
        self._add_task()

    def _sort_tv(self, col: str):
        """点击表头排序(数字列按数值)"""
        items = [(self.tv.set(i, col), i) for i in self.tv.get_children()]
        def key(v):
            s = v[0]
            try:
                return (0, float(str(s).replace("★", "9")))
            except (TypeError, ValueError):
                return (1, str(s))
        items.sort(key=key, reverse=self._sort_desc.get(col, False))
        self._sort_desc[col] = not self._sort_desc.get(col, False)
        for k, (_, i) in enumerate(items):
            self.tv.move(i, "", k)
            self.tv.set(i, "#", k)  # 同步行号
    _sort_desc: dict = {}

    def _selected_plans(self):
        out = []
        for iid in self.tv.selection():
            p = self.plan_key_map.get(iid)
            if p:
                out.append(p)
        return out

    # ============ 抢课队列 ============
    def _add_task(self):
        plans = self._selected_plans()
        if not plans:
            self._log("请先在课程列表中勾选(单击选中)一行"); return
        for p in plans:
            name = _course_of(p).get("name") or ""
            fire = self.ent_fire.get().strip() if hasattr(self, "ent_fire") else ""
            self.tvq.insert("", tk.END, values=(fire, name, self.plan_key(p), "待设定", p.get("courseId") or ""))
            self._log(f"已加入队列: {name} ({self.plan_key(p)})")

    def _del_task(self):
        for iid in self.tvq.selection():
            self.tvq.delete(iid)

    def _snipe_now(self):
        plans = self._selected_plans()
        if not plans:
            self._log("请先选择课程"); return
        threading.Thread(target=self._snipe_run, args=(plans, None), daemon=True).start()

    def _make_client_standalone(self):
        """后台线程中独立建 client, 不依赖 self.client"""
        return self._mk_client()

    def _snipe_run(self, plans, fire_at):
        try:
            c = self._make_client_standalone()
        except Exception as e:
            self._log(f"❌ {e}"); return
        self._snipe_loop(c, plans, fire_at)

    def _start_snipe(self):
        if self.snipe_thread and self.snipe_thread.is_alive():
            messagebox.showinfo("提示", "定时抢课已在运行"); return
        tasks = []
        for iid in self.tvq.get_children():
            vals = self.tvq.item(iid, "values")
            tasks.append({"time_str": str(vals[0]), "course": str(vals[1]),
                          "plan_id": str(vals[2]), "course_id": str(vals[4]) if len(vals) > 4 else ""})
        tasks = [t for t in tasks if t["time_str"]]
        if not tasks:
            messagebox.showwarning("提示", "请在队列中设置开抢时间(格式 HH:MM:SS)")
            return
        self.snipe_stop.clear()
        self.snipe_thread = threading.Thread(target=self._timed_snipe, args=(tasks,), daemon=True)
        self.snipe_thread.start()
        self._log(f"定时抢课启动: {len(tasks)} 个任务")

    def _stop_snipe(self):
        self.snipe_stop.set()
        self._log("停止信号已发送")

    def _arm_at_border(self):
        """开抢守候: 自定义倒计时到目标时刻(默认 12:00), 提前10s把资格监控切到1s,
        放开瞬间自动加入队列抢课"""
        t = self.ent_fire.get().strip() or "12:00:00"
        target = self._parse_time(t)
        if target is None:
            messagebox.showerror("时间错误", f"无法解析 {t}, 使用 HH:MM:SS"); return
        def run():
            self.changelog.snapshot("arm_at", t)
            self._log(f"⏰ 已预约开抢 {t}: 等待中, 12:00 前10s自动加速资格探测至1s…")
            while self._now() < target - 10 and not self.snipe_stop.is_set():
                time.sleep(min(2.0, max(0.05, target - self._now())))
            # 最后10秒: 高频资格探测 + 行政批次 active 轮询
            self._log("⚡ 最后10秒, 高频探测资格+激活批次…")
            prev_can = None
            while self._now() < target + 120 and not self.snipe_stop.is_set():
                try:
                    d = self._mk_client().eligibility()
                    can = d.get("canEnroll")
                    self.changelog.snapshot("eligibility.canEnroll", can)
                    if can and prev_can is False:
                        self._log(f"🎉 {datetime.fromtimestamp(time.time()):%H:%M:%S} 资格放开!")
                        self.root.after(0, lambda: self._update_elig_label(True))
                        for _ in range(6):
                            self.root.bell(); time.sleep(0.3)
                        self.root.after(0, self._refresh_batches)
                        if self._queue_has_tasks():
                            self.root.after(0, self._start_snipe)
                        return
                    prev_can = can
                except Exception:
                    pass
                time.sleep(1.0)
        threading.Thread(target=run, daemon=True).start()

    # ============ 抢课核心 ============
    def _now(self) -> float:
        """本地时间+偏移修正 = 估算的北京时间"""
        return time.time() + self.var_offset.get()

    def _calibrate(self):
        """用服务器 Date 头校准本地时钟偏移"""
        def run():
            try:
                import requests as rq
                r = rq.head("https://my.gench.edu.cn/Gench.PublicElectivePlatform/pc.html",
                            timeout=10, headers={"User-Agent": UA})
                srv = datetime.strptime(r.headers["Date"], "%a, %d %b %Y %H:%M:%S GMT")
                import calendar
                ts_srv = calendar.timegm(srv.timetuple())
                off = ts_srv - time.time()
                self.root.after(0, lambda o=round(off, 1): self.var_offset.set(o))
                self._log(f"校准完成: 服务器比本地 {off:+.1f}s, 已应用到偏移")
            except Exception as e:
                self._log(f"校准失败: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _snipe_one(self, c, plan_id, course_id=""):
        """对单个 classPlanId 发起选课, 返回 (ok, msg)"""
        try:
            if self.var_check_first.get():
                try:
                    c.check(course_id, plan_id)
                except Exception as e:
                    self._log(f"check({plan_id}): {e}")
            c.enroll(plan_id)
            return True, "成功"
        except EnrollmentForbidden as e:
            return False, f"⛔ 资格被拒: {e}"
        except Exception as e:
            return False, str(e)

    def _snipe_loop(self, c, plans, fire_at=None):
        """抢占循环: 直接对目标教学班轮询 POST 选课(不依赖列表接口, 最大化开抢成功率)"""
        ids = [(p, self.plan_key(p), _course_of(p).get("name")) for p in plans]
        interval = max(0.15, float(self.var_interval.get()))
        once = self.var_once.get()
        self.snipe_stop.clear()
        if fire_at:
            self._log(f"等待开抢时刻 {datetime.fromtimestamp(fire_at):%H:%M:%S} …")
            while self._now() < fire_at and not self.snipe_stop.is_set():
                remain = fire_at - self._now()
                if remain > 5:
                    time.sleep(min(1.0, remain / 4))
                else:
                    time.sleep(0.02)
        self._log("🚀 开始抢课")
        deadline = time.time() + 30 * 60
        got = set()
        while not self.snipe_stop.is_set() and time.time() < deadline:
            for p, pid, name in ids:
                if pid in got:
                    continue
                ok, msg = self._snipe_one(c, pid, str(p.get("courseId") or (p.get("course") or {}).get("id") or ""))
                if ok:
                    self._log(f"✅ 抢到: {name} ({pid})")
                    got.add(pid)
                    for iid in self.tvq.get_children():
                        if str(self.tvq.item(iid, "values")[2]) == pid:
                            self.root.after(0, lambda i=iid: self.tvq.set(i, "status", "已抢到"))
                else:
                    self._log(f"· {name} ({pid}) {msg}")
            if once and got:
                break
            time.sleep(interval)
        if not got:
            self._log("抢课结束(未抢到/超时)")

    def _timed_snipe(self, tasks):
        """按队列时间触发: 提前 early_sec 秒开始连续 POST"""
        self.client = None
        try:
            self.client = self._mk_client()
        except Exception as e:
            self._log(f"❌ {e}"); return
        pending = sorted(tasks, key=lambda t: t["time_str"])
        for t in pending:
            if self.snipe_stop.is_set():
                break
            fire = self._parse_time(t["time_str"])
            if fire is None:
                self._log(f"时间格式错误: {t['time_str']} (使用 HH:MM:SS)"); continue
            early = float(self.var_early.get())
            fire_ts = fire - early
            self._log(f"任务 [{t['course']}] 计划 {t['time_str']} (提前 {early}s, Fire={fire_ts%86400:.0f}s 点)")
            while self._now() < fire_ts and not self.snipe_stop.is_set():
                remain = fire_ts - self._now()
                time.sleep(min(1.0, max(0.02, remain / 4)))
            if self.snipe_stop.is_set():
                break
            ok, msg = self._snipe_one(self.client, t["plan_id"], t.get("course_id", ""))
            if ok:
                self._log(f"✅ 定时抢到: {t['course']} ({t['plan_id']})")
                for iid in self.tvq.get_children():
                    if str(self.tvq.item(iid, "values")[2]) == t["plan_id"]:
                        self.root.after(0, lambda i=iid: self.tvq.set(i, "status", "已抢到"))
                if self.var_once.get():
                    return
            else:
                self._log(f"❌ {t['course']}: {msg}, 进入补救轮询")
                # 补救: 间隔重试最多 20 次
                for _ in range(20):
                    if self.snipe_stop.is_set():
                        return
                    time.sleep(max(0.2, self.var_interval.get()))
                    ok2, msg2 = self._snipe_one(self.client, t["plan_id"], t.get("course_id", ""))
                    if ok2:
                        self._log(f"✅ 补抢成功: {t['course']}")
                        if self.var_once.get():
                            return
                        break

    def _parse_time(self, s):
        try:
            hh, mm, ss = [int(x) for x in s.split(":")]
            today = datetime.now()
            dt = today.replace(hour=hh, minute=mm, second=ss, microsecond=0)
            ts = time.mktime(dt.timetuple())
            if ts < time.time() - 5:
                ts += 86400  # 已过点算明天
            return ts
        except Exception:
            return None


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
