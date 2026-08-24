# -*- coding: utf-8 -*-
"""
V0.0.9b版本测试脚本
测试更新后的版本
"""
import sys
import os
import time
import subprocess
import json

def test_v009b():
    """测试V0.0.9b版本"""
    print("V0.0.9b版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 检查配置文件版本
    print(f"\n{'='*80}")
    print("测试1: 检查配置文件版本")
    print(f"{'='*80}")
    
    try:
        with open("config_multi.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        if config.get("version") == "V0.0.9b":
            print(f"[OK] 配置文件版本正确: V0.0.9b")
        else:
            print(f"[FAIL] 配置文件版本不正确: {config.get('version')}")
            return False
    except Exception as e:
        print(f"[FAIL] 配置文件读取失败: {e}")
        return False
    
    # 测试2: 检查多开脚本版本
    print(f"\n{'='*80}")
    print("测试2: 检查多开脚本版本")
    print(f"{'='*80}")
    
    try:
        with open("multi_instance.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "V0.0.9b" in content:
            print(f"[OK] 多开脚本版本正确: V0.0.9b")
        else:
            print(f"[FAIL] 多开脚本版本不正确")
            return False
    except Exception as e:
        print(f"[FAIL] 多开脚本读取失败: {e}")
        return False
    
    # 测试3: 检查GUI版本
    print(f"\n{'='*80}")
    print("测试3: 检查GUI版本")
    print(f"{'='*80}")
    
    try:
        with open("multi_instance_gui.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "V0.0.9b" in content:
            print(f"[OK] GUI版本正确: V0.0.9b")
        else:
            print(f"[FAIL] GUI版本不正确")
            return False
    except Exception as e:
        print(f"[FAIL] GUI版本读取失败: {e}")
        return False
    
    # 测试4: 测试多开功能
    print(f"\n{'='*80}")
    print("测试4: 测试多开功能")
    print(f"{'='*80}")
    
    try:
        cmd = ["python", "multi_instance.py"]
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and "V0.0.9b" in result.stdout:
            print(f"[OK] 多开功能测试成功")
            return True
        else:
            print(f"[FAIL] 多开功能测试失败")
            print(f"输出: {result.stdout[-300:]}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 多开功能测试异常: {e}")
        return False

def main():
    """主函数"""
    print("V0.0.9b版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v009b()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] V0.0.9b版本测试成功")
        print("  - 配置文件版本正确")
        print("  - 多开脚本版本正确")
        print("  - GUI版本正确")
        print("  - 多开功能正常")
    else:
        print("[FAIL] V0.0.9b版本测试失败")
    
    print("\n版本信息:")
    print("1. 版本号: V0.0.9b")
    print("2. 更新时间: 2026-08-23")
    print("3. 更新内容: 版本号更新")

if __name__ == "__main__":
    main()