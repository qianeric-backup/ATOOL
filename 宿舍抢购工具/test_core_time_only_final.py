# -*- coding: utf-8 -*-
"""
核心功能耗时测试脚本（最终版）
只测试核心功能耗时，不包含登录、查询、校时等
"""
import sys
import os
import time
import subprocess
import json

def test_core_time_only(exe_path, version_name, params, test_count=20):
    """测试核心功能耗时"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本核心功能耗时（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 测试命令（只测试--version，最核心功能）
            cmd = [exe_path, "--version"] + params
            
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            execution_time = time.time() - start_time
            
            # 记录结果
            test_result = {
                "test_id": i + 1,
                "execution_time": execution_time,
                "return_code": result.returncode,
                "params": params
            }
            
            results.append(test_result)
            
            print(f"    耗时: {execution_time:.3f}秒, 返回码: {result.returncode}")
            
            time.sleep(0.3)  # 等待0.3秒再进行下一次测试
            
        except subprocess.TimeoutExpired:
            print(f"    [FAIL] 测试超时")
            results.append({
                "test_id": i + 1,
                "execution_time": 10.0,
                "return_code": -1,
                "params": params
            })
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "return_code": -1,
                "params": params
            })
    
    # 统计结果
    total_time = sum(r["execution_time"] for r in results)
    avg_time = total_time / len(results) if results else 0
    
    summary = {
        "version": version_name,
        "params": params,
        "test_count": test_count,
        "total_time": total_time,
        "avg_time": avg_time,
        "min_time": min(r["execution_time"] for r in results),
        "max_time": max(r["execution_time"] for r in results),
        "results": results
    }
    
    print(f"\n{version_name}版本核心功能耗时统计（{test_count}次测试）:")
    print(f"  参数: {params}")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    print(f"  耗时波动: {summary['max_time'] - summary['min_time']:.3f}秒")
    
    return summary

def run_core_time_only_test():
    """运行核心功能耗时测试"""
    print("核心功能耗时测试（最终版）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.2.6（修复后）, V0.0.9c")
    print(f"测试次数: 每个版本20次")
    print(f"测试说明: 只测试--version命令，最核心功能")
    
    # 测试版本路径和参数
    versions = [
        {
            "name": "v1.2.6（修复后）",
            "path": "releases/v1.2.6/grab_dorm_multi_account_v1.2.6.exe",
            "params": ["--key", "RSO-QIANGSS-2026"]
        },
        {
            "name": "V0.0.9c",
            "path": "releases/v0.0.9c/grab_dorm.exe",
            "params": []
        }
    ]
    
    all_results = {}
    
    for version in versions:
        if not os.path.exists(version["path"]):
            print(f"\n[FAIL] {version['name']}版本exe文件不存在: {version['path']}")
            continue
        
        print(f"\n[OK] {version['name']}版本exe文件存在: {version['path']}")
        
        # 测试该版本
        summary = test_core_time_only(version["path"], version["name"], version["params"], test_count=20)
        all_results[version["name"]] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("核心功能耗时对比报告")
    print(f"{'='*80}")
    
    print(f"{'版本':<20} {'平均耗时':<15} {'最快耗时':<15} {'最慢耗时':<15} {'耗时波动':<15}")
    print("-" * 80)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<20} {summary['avg_time']:.3f}秒{'':<10} {summary['min_time']:.3f}秒{'':<10} {summary['max_time']:.3f}秒{'':<10} {summary['max_time'] - summary['min_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"核心功能耗时测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("核心功能耗时测试（最终版）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_core_time_only_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 核心功能耗时测试完成")
        print("  - 测试了v1.2.6（修复后）和V0.0.9c版本")
        print("  - 每个版本测试了20次")
        print("  - 只测试--version命令，最核心功能")
    else:
        print("[FAIL] 核心功能耗时测试失败")
    
    print("\n测试说明:")
    print("1. 只测试--version命令的执行时间")
    print("2. 不包含登录、查询、校时等耗时")
    print("3. 测试程序启动和参数解析的耗时")

if __name__ == "__main__":
    main()