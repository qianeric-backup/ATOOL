# -*- coding: utf-8 -*-
"""
GUI版本测试脚本
测试GUI版本功能
"""
import sys
import os
import time
import subprocess

def test_gui_version():
    """测试GUI版本"""
    print("GUI版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 检查文件是否存在
    print(f"\n{'='*80}")
    print("测试1: 检查文件是否存在")
    print(f"{'='*80}")
    
    files = [
        "multi_instance_gui.py",
        "multi_instance.py",
        "config_multi.json"
    ]
    
    for file in files:
        if os.path.exists(file):
            print(f"[OK] 文件存在: {file}")
        else:
            print(f"[FAIL] 文件不存在: {file}")
            return False
    
    # 测试2: 检查依赖
    print(f"\n{'='*80}")
    print("测试2: 检查依赖")
    print(f"{'='*80}")
    
    try:
        import tkinter
        print("[OK] tkinter模块可用")
    except ImportError:
        print("[FAIL] tkinter模块不可用")
        return False
    
    # 测试3: 检查配置文件
    print(f"\n{'='*80}")
    print("测试3: 检查配置文件")
    print(f"{'='*80}")
    
    try:
        with open("config_multi.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        if "accounts" in config and len(config["accounts"]) > 0:
            print(f"[OK] 配置文件有效，包含{len(config['accounts'])}个账号")
        else:
            print("[FAIL] 配置文件无效")
            return False
    except Exception as e:
        print(f"[FAIL] 配置文件读取失败: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("GUI版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_gui_version()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] GUI版本测试成功")
        print("  - 文件存在")
        print("  - 依赖可用")
        print("  - 配置有效")
    else:
        print("[FAIL] GUI版本测试失败")
    
    print("\n使用说明:")
    print("1. 运行python multi_instance_gui.py启动GUI")
    print("2. 在GUI中添加账号信息")
    print("3. 点击开始抢购")

if __name__ == "__main__":
    import json
    main()