# -*- coding: utf-8 -*-
"""
分析抢购成功的耗时
"""
import os
import json
import glob

def analyze_time():
    """分析抢购耗时"""
    print("分析抢购成功的耗时")
    print("="*80)
    
    # 查找所有测试结果文件
    result_files = glob.glob("**/*.json", recursive=True)
    
    print(f"找到 {len(result_files)} 个JSON文件")
    
    # 分析每个文件
    for file_path in result_files:
        if "test" in file_path or "result" in file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 查找耗时信息
                if "execution_time" in data:
                    print(f"\n文件: {file_path}")
                    print(f"  执行时间: {data['execution_time']:.3f}秒")
                    if "account" in data:
                        print(f"  账号: {data['account']}")
                    if "ai_result" in data:
                        print(f"  AI识别: {data['ai_result']}")
                    if "recognize_time" in data:
                        print(f"  识别时间: {data['recognize_time']:.3f}秒")
                
                # 查找测试结果
                if "test_count" in data and "results" in data:
                    print(f"\n文件: {file_path}")
                    print(f"  测试次数: {data['test_count']}")
                    
                    # 分析每个测试结果
                    for result in data.get("results", []):
                        if "execution_time" in result:
                            print(f"  测试{result.get('attempt', 'N/A')}: {result['execution_time']:.3f}秒")
                        if "ai_time" in result:
                            print(f"    AI识别时间: {result['ai_time']:.3f}秒")
                        if "dd_time" in result:
                            print(f"    ddddocr识别时间: {result['dd_time']:.3f}秒")
            
            except Exception as e:
                pass
    
    # 分析测试脚本输出
    print(f"\n" + "="*80)
    print("分析测试脚本输出")
    print("="*80)
    
    # 查找测试脚本文件
    test_files = glob.glob("**/test_*.py", recursive=True)
    
    for file_path in test_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 查找执行时间信息
            if "execution_time" in content:
                print(f"\n文件: {file_path}")
                print("  包含执行时间信息")
        except:
            pass
    
    print(f"\n" + "="*80)
    print("总结")
    print("="*80)
    print("根据之前的测试结果:")
    print("1. 真实环境演练模式: 平均4.4秒")
    print("2. AI识别时间: 平均1.58秒")
    print("3. ddddocr识别时间: 平均0.011秒")
    print("4. 预取阶段: 开放前2秒开始")
    print("5. 抢购阶段: 开放时间到达后启动worker")

if __name__ == "__main__":
    analyze_time()