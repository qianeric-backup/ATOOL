# -*- coding: utf-8 -*-
"""
图形界面版 KEY 签发工具 —— 上海建桥学院 抢宿舍软件授权工具
功能(可视化操作, 附复制按钮):
  1. 取本机指纹    : 复制使用者机器指纹, 发给授权方签发
  2. 签发绑定KEY   : 粘贴使用者指纹 -> 生成仅该机器有效的KEY
  3. 固定KEY       : 签发材料。可在 ③ 栏手动输入固定KEY，或点"从许可证加载"读 license.key
只依赖 Python 标准库 tkinter。打包为 gui_key.exe 免安装使用。

注意(加固后沿用新机制):
  - 固定KEY不内置在代码/exe 里。
  - 授权方可在界面 ③ 栏直接输入固定KEY明文签发（仅在内存、不落盘）；
    或先用 generate_key.py --license "固定KEY" 生成 license.key，然后点"从许可证加载"。
  - 输入框密码显示(●)，需要复制时点"复制"。
"""
import sys
import tkinter as tk
from tkinter import ttk

import activation


class KeyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("抢宿舍软件 授权KEY签发工具")
        self.geometry("560x400")
        self.minsize(520, 340)
        self.configure(bg="#f5f5f5")
        self._build_ui()
        self._refresh_machine()  # 启动即取并填入本机指纹(不依赖主循环)

    # ---------- 界面 ----------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        # 栏目1: 本机指纹
        sec1 = ttk.LabelFrame(main, text="① 取本机机器指纹（复制给授权方）")
        sec1.grid(row=0, column=0, columnspan=2, sticky="we", **pad)
        self.machine_var = tk.StringVar()
        ttk.Entry(sec1, textvariable=self.machine_var, width=45).grid(row=0, column=0, sticky="we", padx=8, pady=6)
        self.refresh_btn = ttk.Button(sec1, text="取本机指纹", command=self._refresh_machine)
        self.refresh_btn.grid(row=0, column=1, padx=4)
        self.copy_machine_btn = ttk.Button(sec1, text="复制", command=lambda: self._copy(self.machine_var.get()))
        self.copy_machine_btn.grid(row=0, column=2, padx=4, sticky="e")

        # 栏目2: 签发绑定KEY
        sec2 = ttk.LabelFrame(main, text="② 签发「机器绑定 KEY」（粘贴对方机器指纹）")
        sec2.grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        self.target_var = tk.StringVar()
        ttk.Entry(sec2, textvariable=self.target_var, width=45).grid(row=0, column=0, sticky="we", padx=8, pady=6)
        self.gen_btn = ttk.Button(sec2, text="签发绑定KEY", command=self._gen_bound)
        self.gen_btn.grid(row=0, column=1, padx=4)
        self.bound_result_var = tk.StringVar(value="（生成的KEY会显示在这里）")
        ttk.Label(sec2, textvariable=self.bound_result_var, foreground="#0a7d32", wraplength=430).grid(
            row=1, column=0, columnspan=3, sticky="w", padx=8)

        # 栏目3: 固定KEY(签发材料)
        sec3 = ttk.LabelFrame(main, text="③ 固定 KEY（签发材料：可手动输入，或从许可证加载）")
        sec3.grid(row=2, column=0, columnspan=2, sticky="we", **pad)
        self.fixed_var = tk.StringVar()
        self.fixed_entry = ttk.Entry(sec3, textvariable=self.fixed_var, width=45, show="●")
        self.fixed_entry.grid(row=0, column=0, sticky="we", padx=8, pady=6)
        self.load_lic_btn = ttk.Button(sec3, text="从许可证加载", command=self._load_from_license)
        self.load_lic_btn.grid(row=0, column=1, padx=4)
        self.copy_fixed_btn = ttk.Button(sec3, text="复制", command=lambda: self._copy(self.fixed_var.get()))
        self.copy_fixed_btn.grid(row=0, column=2, padx=4, sticky="e")

        # 栏目4: 复制绑定KEY
        copy_row = ttk.Frame(main)
        copy_row.grid(row=3, column=0, columnspan=2, sticky="we", **pad)
        self.copy_bound_btn = ttk.Button(copy_row, text="复制刚签发的绑定KEY",
                                         command=lambda: self._copy(self.bound_result_var.get()))
        self.copy_bound_btn.pack(side="left")

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(main, textvariable=self.status_var, foreground="#555").grid(
            row=4, column=0, columnspan=2, sticky="w", **pad)

        for col in (0,):
            sec1.columnconfigure(col, weight=1)
            sec2.columnconfigure(col, weight=1)
            sec3.columnconfigure(col, weight=1)
        main.columnconfigure(0, weight=1)

    # ---------- 逻辑 ----------
    def _refresh_machine(self):
        fp = activation.get_machine()
        self.machine_var.set(fp)
        self.status_var.set("已取本机指纹，可复制")

    def _master_seed(self):
        """取授权方固定KEY明文(签发材料)：优先 GUI 输入，其次 license.key/env。"""
        manual = self.fixed_var.get().strip()
        if manual:
            return manual
        return activation._bound_master()

    def _gen_bound(self):
        t = self.target_var.get().strip()
        if not t:
            self.status_var.set("请先粘贴对方机器指纹")
            return
        master = self._master_seed()
        if not master:
            self.bound_result_var.set("（未找到固定KEY材料）")
            self.status_var.set("未找到固定KEY: 请在 ③ 栏手动输入固定KEY, 或点\"从许可证加载\"读 license.key")
            return
        # 由授权方固定KEY明文派生绑定KEY (与客户端 bound_key_ok 判别一致)
        suffix = activation._sha(master + "::" + t)[:32]
        k = "{}-{}".format(master, suffix)
        self.bound_result_var.set(k)
        # 同步回填到固定KEY输入框, 方便复制
        if not self.fixed_var.get().strip():
            self.fixed_var.set(master)
        self.status_var.set("已生成绑定KEY，可复制")

    def _load_from_license(self):
        """从 license.key / env 读取固定KEY 并填入输入框。"""
        master = activation._bound_master()
        if master:
            self.fixed_var.set(master)
            self.status_var.set("已从许可证加载固定KEY，可签发")
        else:
            self.fixed_var.set("")
            self.status_var.set("未找到许可文件: 请在 ③ 栏手动输入固定KEY")

    def _copy(self, text):
        if not text:
            self.status_var.set("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # 保持剪贴板
        self.status_var.set(f"已复制: {text[:40]}{'...' if len(text) > 40 else ''}")

    def _on_close(self):
        self.destroy()


def main():
    app = KeyGUI()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
