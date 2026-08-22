# -*- coding: utf-8 -*-
"""
独立取指纹工具 —— 双击运行, 自动显示本机机器指纹, 一键复制, 复制后自动关闭。
用途: 分发给使用者, 让其在【自己的电脑】上运行并复制指纹, 发给授权方签发绑定KEY。
用法: 双击 fp_tool.exe 即可; 或命令行 fp_tool.exe [get-machine] 输出到控制台。
依赖: 仅 Python 标准库 (tkinter)。
"""
import sys
import tkinter as tk
from tkinter import ttk

import activation


def main():
    # 命令行模式: 输出指纹到控制台后退出
    if len(sys.argv) > 1 and sys.argv[1] in ("get-machine", "--get-machine", "fp"):
        print(activation.get_machine())
        return

    # 图形界面模式: 显示指纹 + 复制按钮
    app = tk.Tk()
    app.title("读取本机机器指纹")
    app.geometry("520x300")
    app.minsize(480, 240)
    app.configure(bg="#f5f5f5")

    pad = {"padx": 14, "pady": 10}
    frame = ttk.Frame(app, padding=14)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="请复制下方机器指纹，发送给授权方即可",
              foreground="#333", font=("", 11, "bold")).pack(anchor="w", **pad)

    fp = activation.get_machine()

    box = ttk.Frame(frame)
    box.pack(fill="x", expand=True, **pad)
    fp_var = tk.StringVar(value=fp)
    fp_entry = ttk.Entry(box, textvariable=fp_var, font=("Consolas", 11), state="readonly")
    fp_entry.pack(fill="x", padx=(0, 6), pady=6)

    status_var = tk.StringVar(value="点击下方按钮复制指纹")

    def copy():
        app.clipboard_clear()
        app.clipboard_append(fp)
        app.update()
        status_var.set("已复制到剪贴板! 可直接粘贴发给授权方")
        copy_btn.configure(text="✓ 已复制", state="disabled")
        app.after(400, app.destroy)  # 复制成功后自动关闭

    copy_btn = ttk.Button(box, text="复制指纹", command=copy)
    copy_btn.pack(pady=6)

    ttk.Label(frame, textvariable=status_var, foreground="#0a7d32").pack(anchor="w", **pad)

    ttk.Label(frame, text="提示: 指纹包含本机网卡地址与主机名，请在本机运行。",
              foreground="#999", font=("", 9)).pack(anchor="w", **pad)

    def on_close():
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
