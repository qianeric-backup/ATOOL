# -*- coding: utf-8 -*-
"""
V0.0.9c版本详细测试脚本
定位异常问题
"""
import sys
import os
import time
import subprocess
import json

def test_v009c_detailed():
    """详细测试V0.0.9c版本"""
    print("V0.0.9c版本详细测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/v0.0.9c/grab_dorm.exe"
    
    # 检查exe文件
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] exe文件存在: {exe_path}")
    print(f"    文件大小: {os.path.getsize(exe_path):,} bytes")
    
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
    
    # 测试2: 版本信息
    print(f"\n{'='*80}")
    print("测试2: 版本信息")
    print(f"{'='*80}")
    
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
    
    # 测试3: 多次测试版本信息（定位异常）
    print(f"\n{'='*80}")
    print("测试3: 多次测试版本信息（定位异常）")
    print(f"{'='*80}")
    
    results = []
    for i in range(10):
        print(f"\n第{i+1}次测试:")
        
        try:
            cmd = [exe_path, "--version"]
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            execution_time = time.time() - start_time
            
            test_result = {
                "test_id": i + 1,
                "execution_time": execution_time,
                "return_code": result.returncode,
                "output": result.stdout[:100] if result.stdout else "",
                "error": result.stderr[:100] if result.stderr else ""
            }
            
            results.append(test_result)
            
            print(f"    耗时: {execution_time:.3f}秒, 返回码: {result.returncode}")
            
            time.sleep(0.5)  # 等待0.5秒再进行下一次测试
            
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "return_code": -1,
                "output": "",
                "error": str(e)
            })
    
    # 分析异常
    print(f"\n{'='*80}")
    print("异常分析")
    print(f"{'='*80}")
    
    # 查找异常值
    execution_times = [r["execution_time"] for r in results]
    avg_time = sum(execution_times) / len(execution_times)
    max_time = max(execution_times)
    min_time = min(execution_times)
    
    print(f"平均耗时: {avg_time:.3f}秒")
    print(f"最快耗时: {min_time:.3f}秒")
    print(f"最慢耗时: {max_time:.3f}秒")
    print(f"耗时波动: {max_time - min_time:.3f}秒")
    
    # 查找异常测试
    abnormal_tests = []
    for r in results:
        if r["execution_time"] > avg_time * 1.5:  # 超过平均耗时1.5倍视为异常
            abnormal_tests.append(r)
    
    if abnormal_tests:
        print(f"\n发现{len(abnormal_tests)}个异常测试:")
        for test in abnormal_tests:
            print(f"  测试{test['test_id']}: 耗时{test['execution_time']:.3f}秒")
    else:
        print("\n未发现异常测试")
    
    return True

def main():
    """主函数"""
    print("V0.0.9c版本详细测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v009c_detailed()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] V0.0.9c版本详细测试完成")
        print("  - 帮助信息正常")
        print("  - 版本信息正常")
        print("  - 多次测试完成")
        print("  - 异常分析完成")
    else:
        print("[FAIL] V0.0.9c版本详细测试失败")
    
    print("\n异常问题分析:")
    print("1. 可能是首次启动或系统缓存问题")
    print("2. 可能是系统资源占用问题")
    print("3. 可能是网络连接问题")

if __name__ == "__main__":
    main()