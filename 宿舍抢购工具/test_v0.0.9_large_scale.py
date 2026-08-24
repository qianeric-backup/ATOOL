# -*- coding: utf-8 -*-
"""
V0.0.9版本调整参数大规模测试脚本
调整参数后进行20次测试
"""
import sys
import os
import time
import subprocess
import json

def test_v009_adjusted_large_scale():
    """测试V0.0.9版本（调整参数后，大规模测试）"""
    print("V0.0.9版本调整参数大规模测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    exe_path = "releases/v0.0.9/grab_dorm.exe"
    test_count = 20
    
    # 检查exe文件
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] exe文件存在: {exe_path}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 调整参数：不使用--key参数，只使用基础参数
            cmd = [
                exe_path,
                "--enrollid", "2633233352",
                "--idcard", "341226200807104418",
                "--dry-run",
                "--no-ocr"
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
        "version": "V0.0.9 (调整参数)",
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
    
    print(f"\nV0.0.9版本调整参数统计（{test_count}次测试）:")
    print(f"  成功率: {success_count}/{test_count} ({summary['success_rate']:.1f}%)")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  成功时平均耗时: {summary['success_avg_time']:.3f}秒")
    print(f"  失败时平均耗时: {summary['fail_avg_time']:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    print(f"  总重试次数: {total_retries}")
    print(f"  平均重试次数: {avg_retries:.2f}")
    
    # 保存详细结果
    report_file = f"V0.0.9调整参数测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return summary

def main():
    """主函数"""
    print("V0.0.9版本调整参数大规模测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_v009_adjusted_large_scale()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] V0.0.9版本调整参数大规模测试完成")
        print(f"  - 成功率: {result['success_rate']:.1f}%")
        print(f"  - 平均耗时: {result['avg_time']:.3f}秒")
        print(f"  - 测试次数: {result['test_count']}")
    else:
        print("[FAIL] V0.0.9版本调整参数大规模测试失败")
    
    print("\n调整说明:")
    print("1. 移除--key参数（V0.0.9不支持）")
    print("2. 使用基础参数：--enrollid, --idcard, --dry-run, --no-ocr")
    print("3. 测试演练模式功能")

if __name__ == "__main__":
    main()