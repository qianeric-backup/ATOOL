# -*- coding: utf-8 -*-
"""
多开GUI版本
带有图形界面的多开脚本
"""
import sys
import os
import time
import subprocess
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

class MultiInstanceGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("V0.0.9b 多开抢购工具")
        self.root.geometry("600x500")
        self.root.configure(bg="#f5f5f5")
        
        # 配置数据
        self.accounts = []
        self.settings = {
            "dtype": 2,
            "concurrency": 1,
            "ahead_ms": 300,
            "max_retries": 200,
            "interval_ms": 200
        }
        
        # 创建界面
        self.create_widgets()
        
        # 加载配置
        self.load_config()
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="V0.0.9 多开抢购工具", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 账号管理框架
        account_frame = ttk.LabelFrame(main_frame, text="账号管理", padding="10")
        account_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 账号列表
        self.account_listbox = tk.Listbox(account_frame, height=8, selectmode=tk.SINGLE)
        self.account_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 账号操作按钮
        btn_frame = ttk.Frame(account_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="添加账号", command=self.add_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="编辑账号", command=self.edit_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除账号", command=self.delete_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="导入账号", command=self.import_accounts).pack(side=tk.LEFT, padx=5)
        
        # 设置框架
        settings_frame = ttk.LabelFrame(main_frame, text="抢购设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 设置网格
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)
        
        # 提前毫秒数
        ttk.Label(settings_grid, text="提前毫秒数:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ahead_ms_var = tk.StringVar(value="300")
        ttk.Entry(settings_grid, textvariable=self.ahead_ms_var, width=10).grid(row=0, column=1, padx=5)
        
        # 最大重试次数
        ttk.Label(settings_grid, text="最大重试次数:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.max_retries_var = tk.StringVar(value="200")
        ttk.Entry(settings_grid, textvariable=self.max_retries_var, width=10).grid(row=0, column=3, padx=5)
        
        # 重试间隔
        ttk.Label(settings_grid, text="重试间隔(毫秒):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.interval_ms_var = tk.StringVar(value="200")
        ttk.Entry(settings_grid, textvariable=self.interval_ms_var, width=10).grid(row=1, column=1, padx=5)
        
        # 并发数
        ttk.Label(settings_grid, text="并发数:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.concurrency_var = tk.StringVar(value="1")
        ttk.Entry(settings_grid, textvariable=self.concurrency_var, width=10).grid(row=1, column=3, padx=5)
        
        # 操作按钮
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)
        
        ttk.Button(action_frame, text="开始抢购", command=self.start_grab).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="停止", command=self.stop_grab).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="加载配置", command=self.load_config).pack(side=tk.LEFT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(10, 0))
    
    def add_account(self):
        """添加账号"""
        # 创建添加账号窗口
        add_window = tk.Toplevel(self.root)
        add_window.title("添加账号")
        add_window.geometry("300x200")
        
        # 账号信息
        ttk.Label(add_window, text="录取通知书编号:").pack(pady=5)
        enrollid_entry = ttk.Entry(add_window, width=30)
        enrollid_entry.pack(pady=5)
        
        ttk.Label(add_window, text="身份证号:").pack(pady=5)
        idcard_entry = ttk.Entry(add_window, width=30)
        idcard_entry.pack(pady=5)
        
        ttk.Label(add_window, text="账号名称:").pack(pady=5)
        name_entry = ttk.Entry(add_window, width=30)
        name_entry.pack(pady=5)
        
        def save_account():
            enrollid = enrollid_entry.get().strip()
            idcard = idcard_entry.get().strip()
            name = name_entry.get().strip()
            
            if not enrollid or not idcard:
                messagebox.showerror("错误", "请输入录取通知书编号和身份证号")
                return
            
            account = {
                "enrollid": enrollid,
                "idcard": idcard,
                "name": name or f"账号{len(self.accounts)+1}"
            }
            
            self.accounts.append(account)
            self.update_account_list()
            add_window.destroy()
            
            self.status_var.set(f"已添加账号: {account['name']}")
        
        ttk.Button(add_window, text="保存", command=save_account).pack(pady=10)
    
    def edit_account(self):
        """编辑账号"""
        selected = self.account_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要编辑的账号")
            return
        
        index = selected[0]
        account = self.accounts[index]
        
        # 创建编辑账号窗口
        edit_window = tk.Toplevel(self.root)
        edit_window.title("编辑账号")
        edit_window.geometry("300x200")
        
        # 账号信息
        ttk.Label(edit_window, text="录取通知书编号:").pack(pady=5)
        enrollid_entry = ttk.Entry(edit_window, width=30)
        enrollid_entry.insert(0, account["enrollid"])
        enrollid_entry.pack(pady=5)
        
        ttk.Label(edit_window, text="身份证号:").pack(pady=5)
        idcard_entry = ttk.Entry(edit_window, width=30)
        idcard_entry.insert(0, account["idcard"])
        idcard_entry.pack(pady=5)
        
        ttk.Label(edit_window, text="账号名称:").pack(pady=5)
        name_entry = ttk.Entry(edit_window, width=30)
        name_entry.insert(0, account["name"])
        name_entry.pack(pady=5)
        
        def save_account():
            enrollid = enrollid_entry.get().strip()
            idcard = idcard_entry.get().strip()
            name = name_entry.get().strip()
            
            if not enrollid or not idcard:
                messagebox.showerror("错误", "请输入录取通知书编号和身份证号")
                return
            
            self.accounts[index] = {
                "enrollid": enrollid,
                "idcard": idcard,
                "name": name or account["name"]
            }
            
            self.update_account_list()
            edit_window.destroy()
            
            self.status_var.set(f"已更新账号: {self.accounts[index]['name']}")
        
        ttk.Button(edit_window, text="保存", command=save_account).pack(pady=10)
    
    def delete_account(self):
        """删除账号"""
        selected = self.account_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要删除的账号")
            return
        
        index = selected[0]
        account = self.accounts[index]
        
        if messagebox.askyesno("确认", f"确定要删除账号 {account['name']} 吗?"):
            del self.accounts[index]
            self.update_account_list()
            self.status_var.set(f"已删除账号: {account['name']}")
    
    def import_accounts(self):
        """导入账号"""
        file_path = filedialog.askopenfilename(
            title="选择账号文件",
            filetypes=[("文本文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            
            # 解析账号
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # 尝试不同的分隔符
                for sep in [",", "，", "\t", " "]:
                    if sep in line:
                        parts = [p.strip() for p in line.split(sep) if p.strip()]
                        break
                else:
                    parts = [line]
                
                if len(parts) >= 2:
                    account = {
                        "enrollid": parts[0],
                        "idcard": parts[1],
                        "name": parts[2] if len(parts) > 2 else f"账号{len(self.accounts)+1}"
                    }
                    self.accounts.append(account)
            
            self.update_account_list()
            self.status_var.set(f"已导入 {len(self.accounts)} 个账号")
            
        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {e}")
    
    def update_account_list(self):
        """更新账号列表"""
        self.account_listbox.delete(0, tk.END)
        for account in self.accounts:
            self.account_listbox.insert(tk.END, f"{account['name']}: {account['enrollid']}")
    
    def save_config(self):
        """保存配置"""
        config = {
            "accounts": self.accounts,
            "settings": {
                "dtype": 2,
                "concurrency": int(self.concurrency_var.get()),
                "ahead_ms": int(self.ahead_ms_var.get()),
                "max_retries": int(self.max_retries_var.get()),
                "interval_ms": int(self.interval_ms_var.get())
            }
        }
        
        file_path = filedialog.asksaveasfilename(
            title="保存配置",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")]
        )
        
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.status_var.set(f"配置已保存: {file_path}")
    
    def load_config(self):
        """加载配置"""
        file_path = filedialog.askopenfilename(
            title="加载配置",
            filetypes=[("JSON文件", "*.json")]
        )
        
        if not file_path:
            # 尝试加载默认配置
            default_path = "config_multi.json"
            if os.path.exists(default_path):
                file_path = default_path
            else:
                return
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.accounts = config.get("accounts", [])
            settings = config.get("settings", {})
            
            self.ahead_ms_var.set(str(settings.get("ahead_ms", 300)))
            self.max_retries_var.set(str(settings.get("max_retries", 200)))
            self.interval_ms_var.set(str(settings.get("interval_ms", 200)))
            self.concurrency_var.set(str(settings.get("concurrency", 1)))
            
            self.update_account_list()
            self.status_var.set(f"配置已加载: {file_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")
    
    def start_grab(self):
        """开始抢购"""
        if not self.accounts:
            messagebox.showwarning("警告", "请先添加账号")
            return
        
        self.status_var.set("开始抢购...")
        
        # 创建多开线程
        threads = []
        for i, account in enumerate(self.accounts, 1):
            thread = threading.Thread(
                target=self.run_instance,
                args=(account, i)
            )
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        def wait_threads():
            for thread in threads:
                thread.join()
            self.status_var.set("所有实例已完成")
        
        threading.Thread(target=wait_threads, daemon=True).start()
    
    def run_instance(self, account, instance_id):
        """运行单个实例"""
        exe_path = "releases/v0.0.9/grab_dorm.exe"
        
        if not os.path.exists(exe_path):
            self.status_var.set(f"[实例{instance_id}] exe文件不存在")
            return
        
        # 构建命令
        cmd = [
            exe_path,
            "--enrollid", account["enrollid"],
            "--idcard", account["idcard"],
            "--dry-run",
            "--no-ocr",
            "--ahead-ms", self.ahead_ms_var.get(),
            "--max-retries", self.max_retries_var.get(),
            "--interval-ms", self.interval_ms_var.get()
        ]
        
        self.status_var.set(f"[实例{instance_id}] 启动{account['name']}")
        
        try:
            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待进程完成
            stdout, stderr = process.communicate()
            
            if process.returncode == 0 and "[DRY-RUN] 演练结束" in stdout:
                self.status_var.set(f"[实例{instance_id}] {account['name']}演练成功")
            else:
                self.status_var.set(f"[实例{instance_id}] {account['name']}演练失败")
                
        except Exception as e:
            self.status_var.set(f"[实例{instance_id}] 启动异常: {e}")
    
    def stop_grab(self):
        """停止抢购"""
        self.status_var.set("停止抢购...")
        # 这里可以添加停止逻辑
        messagebox.showinfo("提示", "停止功能待实现")
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()

def main():
    """主函数"""
    app = MultiInstanceGUI()
    app.run()

if __name__ == "__main__":
    main()