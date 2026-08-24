# -*- coding: utf-8 -*-
"""
V0.0.9版本调整参数测试脚本
调整参数后重新测试
"""
import sys
import os
import time
import subprocess

def test_v009_adjusted():
    """测试V0.0.9版本（调整参数后）"""
    print("V0.0.9版本调整参数测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/v0.0.9/grab_dorm.exe"
    
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
    
    # 测试2: 调整参数演练模式
    print(f"\n{'='*80}")
    print("测试2: 调整参数演练模式")
    print(f"{'='*80}")
    
    try:
        # 调整参数：不使用--key参数，只使用基础参数
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
        
        print(f"执行时间: {execution_time:.3f}秒")
        print(f"返回码: {result.returncode}")
        
        if result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout:
            print(f"[OK] 演练模式成功")
            print(f"输出关键信息:")
            for line in result.stdout.split('\n'):
                if any(key in line for key in ['[LOGIN]', '[DORM]', '[TIME]', '[DRY-RUN]']):
                    print(f"  {line}")
            return True
        else:
            print(f"[FAIL] 演练模式失败")
            print(f"输出: {result.stdout[-500:]}")
            if result.stderr:
                print(f"错误: {result.stderr[-300:]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAIL] 演练超时")
        return False
    except Exception as e:
        print(f"[FAIL] 演练异常: {e}")
        return False

def main():
    """主函数"""
    print("V0.0.9版本调整参数测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v009_adjusted()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] V0.0.9版本调整参数测试成功")
        print("  - exe文件存在")
        print("  - 帮助信息正常")
        print("  - 调整参数后演练模式成功")
    else:
        print("[FAIL] V0.0.9版本调整参数测试失败")
    
    print("\n调整说明:")
    print("1. 移除--key参数（V0.0.9不支持）")
    print("2. 使用基础参数：--enrollid, --idcard, --dry-run, --no-ocr")
    print("3. 测试演练模式功能")

if __name__ == "__main__":
    main()