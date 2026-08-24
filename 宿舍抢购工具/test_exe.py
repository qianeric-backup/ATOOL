# -*- coding: utf-8 -*-
"""
测试打包后的exe文件
"""
import os
import subprocess
import time

def test_exe():
    """测试exe文件"""
    print("测试打包后的exe文件")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/v1.2.6/grab_dorm.exe"
    
    # 检查exe文件是否存在
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] exe文件存在: {exe_path}")
    
    # 测试exe文件帮助信息
    print(f"\n测试exe文件帮助信息...")
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
    
    # 测试exe文件版本信息
    print(f"\n测试exe文件版本信息...")
    try:
        cmd = [exe_path, "--version"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"[OK] 版本信息: {result.stdout.strip()}")
        else:
            print(f"[FAIL] 版本信息异常")
            print(f"错误: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"[FAIL] 测试版本信息异常: {e}")
        return False
    
    # 测试exe文件演练模式
    print(f"\n测试exe文件演练模式...")
    try:
        cmd = [
            exe_path,
            "--enrollid", "2633233352",
            "--idcard", "341226200807104418",
            "--dry-run",
            "--no-ocr",
            "--no-ai",
            "--key", "RSO-QIANGSS-2026"
        ]
        
        print(f"命令: {' '.join(cmd)}")
        start_time = time.time()
        
        result = subprocess.run(
            cmd,
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
                if any(key in line for key in ['[LOGIN]', '[DORM]', '[TIME]', '[DRY-RUN]', '[START]', '[SMART-RETRY]']):
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
    print("测试打包后的exe文件")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_exe()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] exe文件测试成功")
        print("  - exe文件存在")
        print("  - 帮助信息正常")
        print("  - 版本信息正常")
        print("  - 演练模式正常")
    else:
        print("[FAIL] exe文件测试失败")
    
    print("\n使用说明:")
    print("1. 进入releases/v1.2.6目录")
    print("2. 双击grab_dorm.exe运行")
    print("3. 或者使用命令行: grab_dorm.exe --config config.json")

if __name__ == "__main__":
    main()