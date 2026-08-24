# -*- coding: utf-8 -*-
"""
实际环境速度测试脚本
只关注速度回显，不关注其他结果
"""
import sys
import os
import time
import subprocess
import json

def test_real_speed(exe_path, version_name, params, test_count=10):
    """测试实际环境速度"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本实际环境速度（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 测试命令
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
            
            # 只关注速度回显
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
                "execution_time": 60.0,
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
    
    print(f"\n{version_name}版本实际环境速度统计（{test_count}次测试）:")
    print(f"  参数: {params}")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    
    return summary

def run_real_speed_test():
    """运行实际环境速度测试"""
    print("实际环境速度测试（每个版本10次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: V0.0.9（默认参数 vs 优化参数）")
    print(f"测试次数: 每个参数配置10次")
    print(f"测试说明: 只关注速度回显，不关注其他结果")
    
    exe_path = "releases/v0.0.9/grab_dorm.exe"
    
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    # 测试参数配置
    param_configs = [
        {
            "name": "默认参数",
            "params": []
        },
        {
            "name": "激进优化",
            "params": ["--interval-ms", "50", "--ahead-ms", "100", "--max-retries", "1000"]
        },
        {
            "name": "平衡优化",
            "params": ["--interval-ms", "100", "--ahead-ms", "200", "--max-retries", "500"]
        },
        {
            "name": "保守优化",
            "params": ["--interval-ms", "150", "--ahead-ms", "250", "--max-retries", "300"]
        }
    ]
    
    all_results = {}
    
    for config in param_configs:
        print(f"\n测试{config['name']}:")
        summary = test_real_speed(exe_path, f"V0.0.9-{config['name']}", config['params'], test_count=10)
        all_results[config['name']] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("实际环境速度对比报告")
    print(f"{'='*80}")
    
    print(f"{'参数配置':<15} {'平均耗时':<15} {'最快耗时':<15} {'最慢耗时':<15}")
    print("-" * 60)
    
    for config_name, summary in all_results.items():
        print(f"{config_name:<15} {summary['avg_time']:.3f}秒{'':<10} {summary['min_time']:.3f}秒{'':<10} {summary['max_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"实际环境速度测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("实际环境速度测试（每个版本10次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_real_speed_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 实际环境速度测试完成")
        print("  - 测试了V0.0.9版本的4种参数配置")
        print("  - 每个配置测试了10次")
        print("  - 只关注速度回显，不关注其他结果")
    else:
        print("[FAIL] 实际环境速度测试失败")
    
    print("\n测试说明:")
    print("1. 只关注速度回显，不关注其他结果")
    print("2. 测试实际环境中的执行速度")
    print("3. 对比不同参数配置的性能差异")

if __name__ == "__main__":
    main()