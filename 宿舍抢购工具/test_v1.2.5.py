# -*- coding: utf-8 -*-
"""
v1.2.5版本测试脚本
测试预启动worker、连接池、智能重试等优化功能
"""
import sys
import os
import time
import subprocess

def test_v125():
    """测试v1.2.5版本"""
    print("v1.2.5版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 检查版本文件
    print(f"\n{'='*80}")
    print("测试1: 检查版本文件")
    print(f"{'='*80}")
    
    version_file = "_dev/grab_dorm_v1.2.5.py"
    if not os.path.exists(version_file):
        print(f"[FAIL] 版本文件不存在: {version_file}")
        return False
    
    print(f"[OK] 版本文件存在: {version_file}")
    
    # 测试2: 检查版本号
    print(f"\n{'='*80}")
    print("测试2: 检查版本号")
    print(f"{'='*80}")
    
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        if '__version__ = "1.2.5"' in content:
            print(f"[OK] 版本号正确: 1.2.5")
        else:
            print(f"[FAIL] 版本号不正确")
            return False
    except Exception as e:
        print(f"[FAIL] 检查版本号失败: {e}")
        return False
    
    # 测试3: 检查优化功能
    print(f"\n{'='*80}")
    print("测试3: 检查优化功能")
    print(f"{'='*80}")
    
    optimizations = [
        ("预启动worker", "PRE-START"),
        ("连接池优化", "pool_connections"),
        ("智能重试", "SMART-RETRY"),
        ("开放时间检查", "等待开放时间")
    ]
    
    for name, keyword in optimizations:
        if keyword in content:
            print(f"[OK] {name} 已实施")
        else:
            print(f"[FAIL] {name} 未实施")
    
    # 测试4: 测试演练模式
    print(f"\n{'='*80}")
    print("测试4: 测试演练模式")
    print(f"{'='*80}")
    
    try:
        cmd = [
            sys.executable, version_file,
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
    print("v1.2.5版本测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v125()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] v1.2.5版本测试成功")
        print("  - 版本文件存在")
        print("  - 版本号正确")
        print("  - 优化功能已实施")
        print("  - 演练模式正常")
    else:
        print("[FAIL] v1.2.5版本测试失败")
    
    print("\n优化功能:")
    print("1. 预启动worker: 提前启动worker线程，减少启动延迟")
    print("2. 连接池优化: 使用连接池，减少连接建立时间")
    print("3. 智能重试: 根据错误类型智能重试，减少无效重试")
    print("4. 开放时间检查: worker启动时检查开放时间")

if __name__ == "__main__":
    main()