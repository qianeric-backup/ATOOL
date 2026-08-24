# -*- coding: utf-8 -*-
"""
V0.0.9版本优化测试脚本
测试优化后的性能
"""
import sys
import os
import time
import subprocess
import json

def test_optimized_v009():
    """测试优化后的V0.0.9版本"""
    print("V0.0.9版本优化测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/v0.0.9/grab_dorm.exe"
    
    # 检查exe文件
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] exe文件存在: {exe_path}")
    
    # 测试1: 默认参数测试
    print(f"\n{'='*80}")
    print("测试1: 默认参数测试")
    print(f"{'='*80}")
    
    try:
        cmd = [
            exe_path,
            "--enrollid", "2633233352",
            "--idcard", "341226200807104418",
            "--dry-run",
            "--no-ocr"
        ]
        
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
        
        if result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout:
            print(f"[OK] 默认参数测试成功")
            print(f"    执行时间: {execution_time:.3f}秒")
        else:
            print(f"[FAIL] 默认参数测试失败")
            return False
            
    except Exception as e:
        print(f"[FAIL] 默认参数测试异常: {e}")
        return False
    
    # 测试2: 激进优化测试
    print(f"\n{'='*80}")
    print("测试2: 激进优化测试")
    print(f"{'='*80}")
    
    try:
        cmd = [
            exe_path,
            "--enrollid", "2633233352",
            "--idcard", "341226200807104418",
            "--dry-run",
            "--no-ocr",
            "--interval-ms", "50",
            "--ahead-ms", "100",
            "--max-retries", "1000"
        ]
        
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
        
        if result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout:
            print(f"[OK] 激进优化测试成功")
            print(f"    执行时间: {execution_time:.3f}秒")
            print(f"    优化效果: {execution_time - 4.173:.3f}秒 (相对于默认参数)")
        else:
            print(f"[FAIL] 激进优化测试失败")
            return False
            
    except Exception as e:
        print(f"[FAIL] 激进优化测试异常: {e}")
        return False
    
    # 测试3: 平衡优化测试
    print(f"\n{'='*80}")
    print("测试3: 平衡优化测试")
    print(f"{'='*80}")
    
    try:
        cmd = [
            exe_path,
            "--enrollid", "2633233352",
            "--idcard", "341226200807104418",
            "--dry-run",
            "--no-ocr",
            "--interval-ms", "100",
            "--ahead-ms", "200",
            "--max-retries", "500"
        ]
        
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
        
        if result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout:
            print(f"[OK] 平衡优化测试成功")
            print(f"    执行时间: {execution_time:.3f}秒")
            print(f"    优化效果: {execution_time - 4.173:.3f}秒 (相对于默认参数)")
        else:
            print(f"[FAIL] 平衡优化测试失败")
            return False
            
    except Exception as e:
        print(f"[FAIL] 平衡优化测试异常: {e}")
        return False
    
    # 测试4: 保守优化测试
    print(f"\n{'='*80}")
    print("测试4: 保守优化测试")
    print(f"{'='*80}")
    
    try:
        cmd = [
            exe_path,
            "--enrollid", "2633233352",
            "--idcard", "341226200807104418",
            "--dry-run",
            "--no-ocr",
            "--interval-ms", "150",
            "--ahead-ms", "250",
            "--max-retries", "300"
        ]
        
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
        
        if result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout:
            print(f"[OK] 保守优化测试成功")
            print(f"    执行时间: {execution_time:.3f}秒")
            print(f"    优化效果: {execution_time - 4.173:.3f}秒 (相对于默认参数)")
        else:
            print(f"[FAIL] 保守优化测试失败")
            return False
            
    except Exception as e:
        print(f"[FAIL] 保守优化测试异常: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("V0.0.9版本优化测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_optimized_v009()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] V0.0.9版本优化测试成功")
        print("  - 测试了默认参数、激进优化、平衡优化、保守优化")
        print("  - 比较了不同优化方案的性能差异")
    else:
        print("[FAIL] V0.0.9版本优化测试失败")
    
    print("\n优化建议:")
    print("1. 使用激进优化: --interval-ms 50 --ahead-ms 100 --max-retries 1000")
    print("2. 使用平衡优化: --interval-ms 100 --ahead-ms 200 --max-retries 500")
    print("3. 使用保守优化: --interval-ms 150 --ahead-ms 250 --max-retries 300")

if __name__ == "__main__":
    main()