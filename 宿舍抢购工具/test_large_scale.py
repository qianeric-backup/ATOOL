# -*- coding: utf-8 -*-
"""
大规模测试脚本
每个版本进行20次测试
"""
import sys
import os
import time
import subprocess
import json

def test_version_large_scale(exe_path, version_name, test_count=20):
    """测试单个版本（大规模测试）"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本（{test_count}次测试）")
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
                "--key", "RSO-QIANGSS-2026"
            ]
            
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
            
            # 统计重试次数
            retry_count = result.stdout.count("[RETRY-") + result.stdout.count("[SMART-RETRY]")
            
            # 记录结果
            test_result = {
                "test_id": i + 1,
                "execution_time": execution_time,
                "success": success,
                "retry_count": retry_count,
                "return_code": result.returncode,
                "output": result.stdout[-500:] if result.stdout else "",
                "error": result.stderr[-300:] if result.stderr else ""
            }
            
            results.append(test_result)
            
            status = "成功" if success else "失败"
            print(f"    耗时: {execution_time:.3f}秒, 状态: {status}, 重试次数: {retry_count}")
            
            time.sleep(0.5)  # 等待0.5秒再进行下一次测试
            
        except subprocess.TimeoutExpired:
            print(f"    [FAIL] 测试超时")
            results.append({
                "test_id": i + 1,
                "execution_time": 60.0,
                "success": False,
                "retry_count": 0,
                "return_code": -1,
                "output": "",
                "error": "测试超时"
            })
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "success": False,
                "retry_count": 0,
                "return_code": -1,
                "output": "",
                "error": str(e)
            })
    
    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["execution_time"] for r in results)
    avg_time = total_time / len(results) if results else 0
    total_retries = sum(r["retry_count"] for r in results)
    avg_retries = total_retries / len(results) if results else 0
    
    # 计算时间统计
    success_times = [r["execution_time"] for r in results if r["success"]]
    fail_times = [r["execution_time"] for r in results if not r["success"]]
    
    summary = {
        "version": version_name,
        "test_count": test_count,
        "success_count": success_count,
        "success_rate": success_count / test_count * 100,
        "total_time": total_time,
        "avg_time": avg_time,
        "total_retries": total_retries,
        "avg_retries": avg_retries,
        "success_avg_time": sum(success_times) / len(success_times) if success_times else 0,
        "fail_avg_time": sum(fail_times) / len(fail_times) if fail_times else 0,
        "min_time": min(r["execution_time"] for r in results),
        "max_time": max(r["execution_time"] for r in results),
        "results": results
    }
    
    print(f"\n{version_name}版本统计（{test_count}次测试）:")
    print(f"  成功率: {success_count}/{test_count} ({summary['success_rate']:.1f}%)")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  成功时平均耗时: {summary['success_avg_time']:.3f}秒")
    print(f"  失败时平均耗时: {summary['fail_avg_time']:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    print(f"  总重试次数: {total_retries}")
    print(f"  平均重试次数: {avg_retries:.2f}")
    
    return summary

def run_large_scale_test():
    """运行大规模测试"""
    print("大规模测试（每个版本20次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.1.0, v1.2.4, v1.2.6")
    print(f"测试次数: 每个版本20次")
    print(f"测试账号: 2633233352")
    
    # 测试版本路径
    versions = [
        ("releases/v1.1.0/grab_dorm_multi_fixed_v1.1.0.exe", "v1.1.0"),
        ("releases/v1.2.4/grab_dorm_multi_account_v1.2.4.exe", "v1.2.4"),
        ("releases/v1.2.6/grab_dorm_multi_account_v1.2.6.exe", "v1.2.6")
    ]
    
    all_results = {}
    
    for exe_path, version_name in versions:
        if not os.path.exists(exe_path):
            print(f"\n[FAIL] {version_name}版本exe文件不存在: {exe_path}")
            continue
        
        print(f"\n[OK] {version_name}版本exe文件存在: {exe_path}")
        
        # 测试该版本
        summary = test_version_large_scale(exe_path, version_name, test_count=20)
        all_results[version_name] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("版本对比报告（大规模测试）")
    print(f"{'='*80}")
    
    print(f"{'版本':<10} {'成功率':<15} {'平均耗时':<15} {'成功平均耗时':<15} {'平均重试':<15}")
    print("-" * 70)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<10} {summary['success_rate']:.1f}%{'':<10} {summary['avg_time']:.3f}秒{'':<10} {summary['success_avg_time']:.3f}秒{'':<10} {summary['avg_retries']:.2f}")
    
    # 保存详细结果
    report_file = f"大规模测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("大规模测试（每个版本20次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_large_scale_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 大规模测试完成")
        print("  - 测试了v1.1.0、v1.2.4、v1.2.6版本")
        print("  - 每个版本测试了20次")
        print("  - 统计了成功率、耗时、重试次数")
    else:
        print("[FAIL] 大规模测试失败")
    
    print("\n测试说明:")
    print("1. 使用演练模式测试，不实际提交验证码")
    print("2. 统计执行时间、成功率、重试次数")
    print("3. 对比不同版本的性能差异")

if __name__ == "__main__":
    main()