# -*- coding: utf-8 -*-
"""
V0.0.9c版本缩小间隔提速测试脚本
测试V0.0.9c版本通过缩小间隔来提速的效果
"""
import sys
import os
import time
import subprocess
import json

def test_v009c_interval(exe_path, params, test_count=10):
    """测试V0.0.9c版本间隔优化"""
    print(f"\n{'='*80}")
    print(f"测试V0.0.9c版本间隔优化（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 测试命令（使用演练模式）
            cmd = [
                exe_path,
                "--enrollid", "2633233352",
                "--idcard", "341226200807104418",
                "--dry-run",
                "--no-ocr"
            ] + params
            
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            execution_time = time.time() - start_time
            
            # 分析结果
            success = result.returncode == 0 and "[DRY-RUN] 演练结束" in result.stdout
            
            # 记录结果
            test_result = {
                "test_id": i + 1,
                "execution_time": execution_time,
                "success": success,
                "return_code": result.returncode,
                "params": params
            }
            
            results.append(test_result)
            
            status = "成功" if success else "失败"
            print(f"    耗时: {execution_time:.3f}秒, 状态: {status}")
            
            time.sleep(0.3)  # 等待0.3秒再进行下一次测试
            
        except subprocess.TimeoutExpired:
            print(f"    [FAIL] 测试超时")
            results.append({
                "test_id": i + 1,
                "execution_time": 60.0,
                "success": False,
                "return_code": -1,
                "params": params
            })
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "success": False,
                "return_code": -1,
                "params": params
            })
    
    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["execution_time"] for r in results)
    avg_time = total_time / len(results) if results else 0
    
    summary = {
        "params": params,
        "test_count": test_count,
        "success_count": success_count,
        "success_rate": success_count / test_count * 100,
        "total_time": total_time,
        "avg_time": avg_time,
        "min_time": min(r["execution_time"] for r in results),
        "max_time": max(r["execution_time"] for r in results),
        "results": results
    }
    
    print(f"\nV0.0.9c版本间隔优化统计（{test_count}次测试）:")
    print(f"  参数: {params}")
    print(f"  成功率: {success_count}/{test_count} ({summary['success_rate']:.1f}%)")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    
    return summary

def run_v009c_interval_optimization_test():
    """运行V0.0.9c版本缩小间隔提速测试"""
    print("V0.0.9c版本缩小间隔提速测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: V0.0.9c")
    print(f"测试次数: 每个间隔配置10次")
    print(f"测试说明: 测试V0.0.9c版本通过缩小间隔来提速的效果")
    
    exe_path = "releases/v0.0.9c/grab_dorm.exe"
    
    if not os.path.exists(exe_path):
        print(f"[FAIL] V0.0.9c版本exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] V0.0.9c版本exe文件存在: {exe_path}")
    
    # 测试不同的间隔配置
    interval_configs = [
        {
            "name": "默认间隔",
            "params": []
        },
        {
            "name": "缩小间隔（100ms）",
            "params": ["--interval-ms", "100"]
        },
        {
            "name": "缩小间隔（50ms）",
            "params": ["--interval-ms", "50"]
        },
        {
            "name": "缩小间隔（25ms）",
            "params": ["--interval-ms", "25"]
        },
        {
            "name": "缩小间隔（10ms）",
            "params": ["--interval-ms", "10"]
        }
    ]
    
    all_results = {}
    
    for config in interval_configs:
        print(f"\n测试{config['name']}:")
        summary = test_v009c_interval(exe_path, config['params'], test_count=10)
        all_results[config['name']] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("V0.0.9c版本间隔优化对比报告")
    print(f"{'='*80}")
    
    print(f"{'配置名称':<20} {'平均耗时':<15} {'最快耗时':<15} {'最慢耗时':<15} {'成功率':<15}")
    print("-" * 80)
    
    for config_name, summary in all_results.items():
        print(f"{config_name:<20} {summary['avg_time']:.3f}秒{'':<10} {summary['min_time']:.3f}秒{'':<10} {summary['max_time']:.3f}秒{'':<10} {summary['success_rate']:.1f}%")
    
    # 保存详细结果
    report_file = f"V0.0.9c版本间隔优化测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("V0.0.9c版本缩小间隔提速测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_v009c_interval_optimization_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] V0.0.9c版本缩小间隔提速测试完成")
        print("  - 测试了5种不同的间隔配置")
        print("  - 每个配置测试了10次")
        print("  - 对比了不同间隔配置的性能差异")
    else:
        print("[FAIL] V0.0.9c版本缩小间隔提速测试失败")
    
    print("\n测试说明:")
    print("1. 测试V0.0.9c版本通过缩小间隔来提速的效果")
    print("2. 测试不同的间隔配置：默认、100ms、50ms、25ms、10ms")
    print("3. 对比不同间隔配置的性能差异")

if __name__ == "__main__":
    main()