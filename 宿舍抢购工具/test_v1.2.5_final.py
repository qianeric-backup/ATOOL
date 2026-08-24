# -*- coding: utf-8 -*-
"""
v1.2.5版本最终测试
测试所有优化功能是否正常工作
"""
import sys
import os
import time
import subprocess

def test_v125_final():
    """v1.2.5版本最终测试"""
    print("v1.2.5版本最终测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 检查主文件版本
    print(f"\n{'='*80}")
    print("测试1: 检查主文件版本")
    print(f"{'='*80}")
    
    try:
        with open("_dev/grab_dorm.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        if '__version__ = "1.2.5"' in content:
            print(f"[OK] 主文件版本正确: 1.2.5")
        else:
            print(f"[FAIL] 主文件版本不正确")
            return False
    except Exception as e:
        print(f"[FAIL] 检查主文件版本失败: {e}")
        return False
    
    # 测试2: 检查优化功能
    print(f"\n{'='*80}")
    print("测试2: 检查优化功能")
    print(f"{'='*80}")
    
    optimizations = [
        ("预启动worker", "PRE-START"),
        ("连接池优化", "pool_connections"),
        ("智能重试", "SMART-RETRY"),
        ("开放时间检查", "等待开放时间")
    ]
    
    all_optimizations_ok = True
    for name, keyword in optimizations:
        if keyword in content:
            print(f"[OK] {name} 已实施")
        else:
            print(f"[FAIL] {name} 未实施")
            all_optimizations_ok = False
    
    if not all_optimizations_ok:
        return False
    
    # 测试3: 测试演练模式
    print(f"\n{'='*80}")
    print("测试3: 测试演练模式")
    print(f"{'='*80}")
    
    try:
        cmd = [
            sys.executable, "_dev/grab_dorm.py",
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
                if any(key in line for key in ['[LOGIN]', '[DORM]', '[TIME]', '[DRY-RUN]', '[PRE-START]', '[SMART-RETRY]']):
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
    print("v1.2.5版本最终测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v125_final()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] v1.2.5版本最终测试成功")
        print("  - 主文件版本正确: 1.2.5")
        print("  - 所有优化功能已实施")
        print("  - 演练模式正常工作")
    else:
        print("[FAIL] v1.2.5版本最终测试失败")
    
    print("\n已实施的优化:")
    print("1. 预启动worker: 提前启动worker线程，减少启动延迟")
    print("2. 连接池优化: 使用连接池，减少连接建立时间")
    print("3. 智能重试: 根据错误类型智能重试，减少无效重试")
    print("4. 开放时间检查: worker启动时检查开放时间，避免提前提交")

if __name__ == "__main__":
    main()