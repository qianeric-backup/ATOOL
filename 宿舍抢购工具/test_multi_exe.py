# -*- coding: utf-8 -*-
"""
多开exe测试脚本
测试多开exe功能
"""
import sys
import os
import time
import subprocess

def test_multi_exe():
    """测试多开exe"""
    print("多开exe测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/multi_instance/multi_instance.exe"
    
    # 检查exe文件
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] exe文件存在: {exe_path}")
    
    # 测试1: 帮助信息
    print(f"\n{'='*80}")
    print("测试1: 帮助信息")
    print(f"{'='*80}")
    
    try:
        cmd = [exe_path, "--help"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"[OK] 帮助信息正常")
            print(f"帮助信息前200字符: {result.stdout[:200]}")
        else:
            print(f"[FAIL] 帮助信息异常")
            print(f"错误: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"[FAIL] 测试帮助信息异常: {e}")
        return False
    
    # 测试2: 运行多开
    print(f"\n{'='*80}")
    print("测试2: 运行多开")
    print(f"{'='*80}")
    
    try:
        cmd = [exe_path]
        print(f"命令: {' '.join(cmd)}")
        start_time = time.time()
        
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        execution_time = time.time() - start_time
        
        print(f"执行时间: {execution_time:.3f}秒")
        print(f"返回码: {result.returncode}")
        
        if result.returncode == 0:
            print(f"[OK] 多开exe运行成功")
            print(f"输出关键信息:")
            for line in result.stdout.split('\n'):
                if any(key in line for key in ['[OK]', '[FAIL]', '成功', '失败']):
                    print(f"  {line}")
            return True
        else:
            print(f"[FAIL] 多开exe运行失败")
            print(f"输出: {result.stdout[-500:]}")
            if result.stderr:
                print(f"错误: {result.stderr[-300:]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAIL] 运行超时")
        return False
    except Exception as e:
        print(f"[FAIL] 运行异常: {e}")
        return False

def main():
    """主函数"""
    print("多开exe测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_multi_exe()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] 多开exe测试成功")
        print("  - exe文件存在")
        print("  - 帮助信息正常")
        print("  - 多开功能正常")
    else:
        print("[FAIL] 多开exe测试失败")
    
    print("\n使用说明:")
    print("1. 进入releases/multi_instance目录")
    print("2. 编辑config_multi.json配置账号信息")
    print("3. 双击multi_instance.exe运行")

if __name__ == "__main__":
    main()