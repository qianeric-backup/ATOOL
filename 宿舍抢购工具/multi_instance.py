# -*- coding: utf-8 -*-
"""
多开脚本
检测到有几个账密就开启几个窗口并让其开始抢购
"""
import sys
import os
import time
import subprocess
import json
import threading

def load_config():
    """加载多开配置"""
    config_file = "config_multi.json"
    if not os.path.exists(config_file):
        print(f"[FAIL] 配置文件不存在: {config_file}")
        return None
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    print(f"[OK] 配置文件加载成功: {config_file}")
    print(f"    账号数量: {len(config['accounts'])}")
    
    return config

def start_instance(account, settings, instance_id):
    """启动单个实例"""
    exe_path = "releases/v0.0.9/grab_dorm.exe"
    
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    # 构建命令
    cmd = [
        exe_path,
        "--enrollid", account["enrollid"],
        "--idcard", account["idcard"],
        "--dry-run",
        "--no-ocr"
    ]
    
    # 添加设置参数
    if "ahead_ms" in settings:
        cmd.extend(["--ahead-ms", str(settings["ahead_ms"])])
    if "max_retries" in settings:
        cmd.extend(["--max-retries", str(settings["max_retries"])])
    if "interval_ms" in settings:
        cmd.extend(["--interval-ms", str(settings["interval_ms"])])
    
    print(f"\n[实例{instance_id}] 启动{account['name']}")
    print(f"  账号: {account['enrollid']}")
    print(f"  命令: {' '.join(cmd)}")
    
    try:
        # 启动进程
        process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"  [OK] 进程已启动，PID: {process.pid}")
        
        # 等待进程完成
        stdout, stderr = process.communicate()
        
        print(f"  [OK] 进程已结束，返回码: {process.returncode}")
        
        if process.returncode == 0 and "[DRY-RUN] 演练结束" in stdout:
            print(f"  [OK] {account['name']}演练成功")
            return True
        else:
            print(f"  [FAIL] {account['name']}演练失败")
            if stderr:
                print(f"  错误: {stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"  [FAIL] 启动异常: {e}")
        return False

def run_multi_instance():
    """运行多开"""
    print("V0.0.9b 多开脚本")
    print("="*80)
    print(f"运行时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载配置
    config = load_config()
    if not config:
        return False
    
    accounts = config["accounts"]
    settings = config["settings"]
    
    print(f"检测到{len(accounts)}个账号:")
    for i, account in enumerate(accounts, 1):
        print(f"  {i}. {account['name']}: {account['enrollid']}")
    
    # 启动多开
    print(f"\n开始启动{len(accounts)}个实例...")
    
    threads = []
    results = []
    
    for i, account in enumerate(accounts, 1):
        # 创建线程启动实例
        thread = threading.Thread(
            target=lambda acc, idx: results.append(start_instance(acc, settings, idx)),
            args=(account, i)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 统计结果
    success_count = sum(results)
    total_count = len(results)
    
    print(f"\n{'='*80}")
    print("多开结果统计")
    print(f"{'='*80}")
    print(f"总实例数: {total_count}")
    print(f"成功数: {success_count}")
    print(f"失败数: {total_count - success_count}")
    print(f"成功率: {success_count/total_count*100:.1f}%")
    
    return success_count == total_count

def main():
    """主函数"""
    print("多开脚本")
    print("="*80)
    print(f"运行时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行多开
    result = run_multi_instance()
    
    # 总结
    print("\n" + "="*80)
    print("运行总结")
    print("="*80)
    
    if result:
        print("[OK] 多开脚本运行成功")
        print("  - 所有账号都成功启动")
        print("  - 所有实例都成功运行")
    else:
        print("[FAIL] 多开脚本运行失败")
        print("  - 部分账号启动失败")
        print("  - 部分实例运行失败")
    
    print("\n使用说明:")
    print("1. 编辑config_multi.json配置账号信息")
    print("2. 运行multi_instance.py启动多开")
    print("3. 每个账号会在独立窗口中运行")

if __name__ == "__main__":
    main()