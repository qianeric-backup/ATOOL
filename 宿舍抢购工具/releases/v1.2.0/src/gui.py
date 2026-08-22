# -*- coding: utf-8 -*-
"""
图形界面 (tkinter) —— 上海建桥学院 智能化宿舍自动竞选 (多账号版)
功能:
  * 支持一次为多个账号抢购: 每行一个账号 (录取通知书编号,身份证号), 可导入 txt/csv 文件
  * 每个账号独立会话并发抢购, 日志按账号前缀区分
  * 无限重试直到成功, 成功后自动监控订单, 订单丢失自动重新抢购
版本: 1.2.0 (对应 grab_dorm.__version__)
依赖: 仅 Python 标准库 (tkinter 随 Python 自带)。
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from grab_dorm import (DormGrabber, CaptchaOcr, API_BASE,
                       auto_config_path, load_config)


class TextRedirector:
    """把 print 输出重定向到线程安全队列; 每个线程可带独立前缀(账号标识)。"""

    def __init__(self, q):
        self.q = q
        self._tl = threading.local()

    def write(self, msg):
        tag = getattr(self._tl, "tag", "")
        self.q.put(f"{tag}{msg}")

    def flush(self):
        pass


class GrabGUI(tk.Tk):
    def __init__(self, api_base=None):
        super().__init__()
        self.title("上海建桥学院 智能化宿舍自动竞选 (多账号) v1.2.0")
        self.geometry("700x640")
        self.minsize(620, 560)
        self.configure(bg="#f5f5f5")
        self.api_base = api_base or API_BASE

        self.log_q = queue.Queue()
        self.grabbers = []          # 所有账号的 DormGrabber
        self.worker_threads = []
        self.stop_flag = threading.Event()
        self._ok_count = 0
        self._total = 0
        self._build_ui()
        self._prefill_config()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 界面 ----------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        # 激活 KEY
        ttk.Label(main, text="激活 KEY:").grid(row=0, column=0, sticky="e", **pad)
        self.key_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.key_var, width=36, show="●").grid(row=0, column=1, sticky="we", **pad)

        # 账号列表
        ttk.Label(main, text="抢购账号 (每行一个):").grid(row=1, column=0, sticky="ne", **pad)
        acc_frame = ttk.Frame(main)
        acc_frame.grid(row=1, column=1, sticky="nsew", **pad)
        self.acc_text = tk.Text(acc_frame, height=5, wrap="none",
                                font=("Consolas", 9), undo=True)
        acc_sb = ttk.Scrollbar(acc_frame, command=self.acc_text.yview)
        self.acc_text.configure(yscrollcommand=acc_sb.set)
        self.acc_text.pack(side="left", fill="both", expand=True)
        acc_sb.pack(side="right", fill="y")
        ttk.Label(main, text="格式: 录取通知书编号,身份证号\n(可加 # 注释行; 逗号/空格分隔)",
                  foreground="#888", justify="left").grid(row=2, column=1, sticky="w", **pad)
        self.import_btn = ttk.Button(main, text="导入账号文件(.txt/.csv)", command=self._import_accounts)
        self.import_btn.grid(row=1, column=2, sticky="n", **pad)

        # 宿舍类型
        ttk.Label(main, text="宿舍类型:").grid(row=3, column=0, sticky="e", **pad)
        self.dtype_var = tk.IntVar(value=2)
        dtype_frame = ttk.Frame(main)
        dtype_frame.grid(row=3, column=1, sticky="w", **pad)
        ttk.Radiobutton(dtype_frame, text="新宿舍(智能宿舍)", variable=self.dtype_var, value=2).pack(side="left")
        ttk.Radiobutton(dtype_frame, text="公费宿舍", variable=self.dtype_var, value=1).pack(side="left", padx=(12, 0))

        # 参数行
        ttk.Label(main, text="提前开抢(ms):").grid(row=4, column=0, sticky="e", **pad)
        self.ahead_var = tk.StringVar(value="300")
        ttk.Entry(main, textvariable=self.ahead_var, width=8).grid(row=4, column=1, sticky="w", **pad)
        ttk.Label(main, text="重试间隔(ms):").grid(row=5, column=0, sticky="e", **pad)
        self.interval_var = tk.StringVar(value="200")
        ttk.Entry(main, textvariable=self.interval_var, width=8).grid(row=5, column=1, sticky="w", **pad)

        self.forever_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main, text="无限重试直到抢到, 成功后持续监控订单(丢失自动重抢)",
                        variable=self.forever_var).grid(row=6, column=1, sticky="w", **pad)

        # 按钮行
        btn_row = ttk.Frame(main)
        btn_row.grid(row=7, column=0, columnspan=3, pady=8)
        self.start_btn = ttk.Button(btn_row, text="开始抢购", command=self._start)
        self.start_btn.pack(side="left", padx=6)
        self.stop_btn = ttk.Button(btn_row, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.dry_btn = ttk.Button(btn_row, text="演练(只测试,不下单)", command=self._dry_run)
        self.dry_btn.pack(side="left", padx=6)

        # 日志区
        log_frame = ttk.LabelFrame(main, text="运行日志 (多账号并发, 按 [账号] 前缀区分)")
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 4))
        main.rowconfigure(8, weight=1)
        main.columnconfigure(1, weight=1)
        self.log_text = tk.Text(log_frame, height=14, wrap="word",
                                font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                                insertbackground="#d4d4d4")
        sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        sb.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪: 输入/导入账号后点击 [开始抢购]")
        ttk.Label(main, textvariable=self.status_var, foreground="#555").grid(
            row=9, column=0, columnspan=3, sticky="w", **pad)

    # ---------- 数据 ----------
    def _prefill_config(self):
        try:
            path = auto_config_path()
            if path:
                cfg = load_config(path)
                if cfg.get("enrollid"):
                    self.acc_text.insert("1.0", f"{cfg['enrollid']},{cfg.get('idcard', '')}\n")
                    self.log(f"[CONFIG] 已从 {path} 预填账号\n")
        except Exception as e:  # noqa: BLE001
            self.log(f"[CONFIG] 读取配置文件失败: {e}\n")

    def _import_accounts(self):
        path = filedialog.askopenfilename(
            title="选择账号文件", filetypes=[("文本/CSV", "*.txt *.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
            if self.acc_text.get("1.0", "end").strip():
                content = "\n" + content
            self.acc_text.insert("end", content)
            self.log(f"[IMPORT] 已导入账号文件: {path}\n")
        except Exception as e:  # noqa: BLE001
            self.log(f"[IMPORT] 导入失败: {e}\n")

    def _parse_accounts(self):
        """解析账号文本 -> [(enrollid, idcard), ...]; 每行 学号,身份证号 或 学号 身份证; # 注释跳过。"""
        accounts = []
        for line in self.acc_text.get("1.0", "end").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sep in (",", "，", "\t", " "):
                if sep in line:
                    parts = [p.strip() for p in line.split(sep) if p.strip()]
                    break
            else:
                parts = [line]
            if len(parts) >= 2:
                accounts.append((parts[0], parts[1]))
            else:
                self.log(f"[WARN] 跳过无法解析的账号行: {line}\n")
        return accounts

    # ---------- 日志 ----------
    def log(self, msg):
        self.log_text.insert("end", msg)
        self.log_text.see("end")

    def _poll_logs(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_logs)

    def _set_status(self, text):
        self.after(0, lambda: self.status_var.set(text))

    # ---------- 动作 ----------
    def _collect_common(self):
        try:
            ahead = max(0, int(self.ahead_var.get().strip() or 300))
            interval = max(10, int(self.interval_var.get().strip() or 200))
        except ValueError:
            raise ValueError("提前开抢/重试间隔必须是整数(毫秒)")
        return ahead, interval

    def _run_grab(self, dry_run=False):
        # ===== 激活门卫 =====
        import activation
        if not activation.validate(self.key_var.get()):
            self.status_var.set("激活KEY无效, 无法开始")
            self.log("[ACTIVATION] 激活KEY无效或未填写。请从授权方获取有效KEY后重试。\n")
            return
        self.log("[ACTIVATION] 激活校验通过\n")

        accounts = self._parse_accounts()
        if not accounts:
            self.status_var.set("没有可用的账号, 请先输入或导入")
            self.log("[ERROR] 未解析到任何账号\n")
            return
        try:
            ahead, interval = self._collect_common()
        except ValueError as e:
            self.status_var.set(f"输入有误: {e}")
            self.log(f"[ERROR] {e}\n")
            return

        forever = self.forever_var.get()
        dtype = self.dtype_var.get()
        self._total = len(accounts)
        self._ok_count = 0
        self.stop_flag.clear()
        self.grabbers = []

        # 重定向 stdout -> 日志区 (带线程前缀)
        self._orig_stdout, self._orig_stderr = sys.stdout, sys.stderr
        redirector = TextRedirector(self.log_q)
        sys.stdout = sys.stderr = redirector

        shared_ocr = CaptchaOcr(auto=True,
                                save_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha"))

        def worker(acc):
            enrollid, idcard = acc
            short = enrollid[-4:] if len(enrollid) >= 4 else enrollid
            redirector._tl.tag = f"[{short}] "
            g = DormGrabber(
                enrollid=enrollid, idcard=idcard,
                dtype=dtype, ocr=shared_ocr,
                ahead_ms=ahead, interval_ms=interval,
                max_retries=None if forever else 200,
                api_base=self.api_base,
            )
            self.grabbers.append(g)
            try:
                info = g.run(dry_run=dry_run, monitor=False)
                if info and not dry_run:
                    self._ok_count += 1
            except Exception as e:  # noqa: BLE001
                print(f"[FATAL] {e}")
            finally:
                redirector._tl.tag = ""
                self._set_status(f"进度: {self._ok_count}/{self._total} 个账号成功")

        def run_all():
            try:
                threads = []
                for acc in accounts:
                    if self.stop_flag.is_set():
                        break
                    t = threading.Thread(target=worker, args=(acc,), daemon=True)
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
            finally:
                sys.stdout, sys.stderr = self._orig_stdout, self._orig_stderr
                self._finish()

        self.worker_threads = [threading.Thread(target=run_all, daemon=True)]
        self.worker_threads[0].start()
        self.start_btn.configure(state="disabled")
        self.dry_btn.configure(state="disabled")
        self.import_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_status(f"已启动: {len(accounts)} 个账号, 后台运行中...")

    def _start(self):
        self._run_grab(dry_run=False)

    def _dry_run(self):
        self._run_grab(dry_run=True)

    def _stop(self):
        self.status_var.set("正在停止...")
        self.stop_flag.set()
        for g in self.grabbers:
            g._stop.set()
        self.log("[STOP] 已发送停止信号(所有账号)\n")

    def _finish(self):
        self.start_btn.configure(state="normal")
        self.dry_btn.configure(state="normal")
        self.import_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if self.stop_flag.is_set():
            self.status_var.set(f"已停止 (成功 {self._ok_count}/{self._total})")
        else:
            self.status_var.set(f"运行结束 (成功 {self._ok_count}/{self._total})")

    def _on_close(self):
        self.stop_flag.set()
        for g in self.grabbers:
            g._stop.set()
        self.destroy()


def main():
    app = GrabGUI()
    app.after(100, app._poll_logs)
    app.mainloop()


if __name__ == "__main__":
    main()
