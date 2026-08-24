# -*- coding: utf-8 -*-
"""
实际环境核心功能耗时测试脚本
只测试实际环境中的核心功能耗时
"""
import sys
import os
import time
import subprocess
import json

def test_real_core_time(exe_path, version_name, test_count=10):
    """测试实际环境核心功能耗时"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本实际环境核心功能耗时（{test_count}次测试）")
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
            ]
            
            # v1.2.6版本需要激活KEY
            if "v1.2.6" in version_name:
                cmd.append("--key")
                cmd.append("RSO-QIANGSS-2026")
            
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
                "return_code": result.returncode
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
                "return_code": -1
            })
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "success": False,
                "return_code": -1
            })
    
    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["execution_time"] for r in results)
    avg_time = total_time / len(results) if results else 0
    
    summary = {
        "version": version_name,
        "test_count": test_count,
        "success_count": success_count,
        "success_rate": success_count / test_count * 100,
        "total_time": total_time,
        "avg_time": avg_time,
        "min_time": min(r["execution_time"] for r in results),
        "max_time": max(r["execution_time"] for r in results),
        "results": results
    }
    
    print(f"\n{version_name}版本实际环境核心功能耗时统计（{test_count}次测试）:")
    print(f"  成功率: {success_count}/{test_count} ({summary['success_rate']:.1f}%)")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    
    return summary

def run_real_core_time_test():
    """运行实际环境核心功能耗时测试"""
    print("实际环境核心功能耗时测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.2.6（修复后）, V0.0.9c")
    print(f"测试次数: 每个版本10次")
    print(f"测试说明: 只测试实际环境中的核心功能耗时")
    
    # 测试版本路径
    versions = [
        ("releases/v1.2.6/grab_dorm_multi_account_v1.2.6.exe", "v1.2.6（修复后）"),
        ("releases/v0.0.9c/grab_dorm.exe", "V0.0.9c")
    ]
    
    all_results = {}
    
    for exe_path, version_name in versions:
        if not os.path.exists(exe_path):
            print(f"\n[FAIL] {version_name}版本exe文件不存在: {exe_path}")
            continue
        
        print(f"\n[OK] {version_name}版本exe文件存在: {exe_path}")
        
        # 测试该版本
        summary = test_real_core_time(exe_path, version_name, test_count=10)
        all_results[version_name] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("实际环境核心功能耗时对比报告")
    print(f"{'='*80}")
    
    print(f"{'版本':<20} {'成功率':<15} {'平均耗时':<15} {'最快耗时':<15} {'最慢耗时':<15}")
    print("-" * 80)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<20} {summary['success_rate']:.1f}%{'':<10} {summary['avg_time']:.3f}秒{'':<10} {summary['min_time']:.3f}秒{'':<10} {summary['max_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"实际环境核心功能耗时测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("实际环境核心功能耗时测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_real_core_time_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 实际环境核心功能耗时测试完成")
        print("  - 测试了v1.2.6（修复后）和V0.0.9c版本")
        print("  - 每个版本测试了10次")
        print("  - 只测试实际环境中的核心功能耗时")
    else:
        print("[FAIL] 实际环境核心功能耗时测试失败")
    
    print("\n测试说明:")
    print("1. 只测试实际环境中的核心功能耗时")
    print("2. 使用演练模式，不实际提交验证码")
    print("3. 测试登录、查询、校时等全流程")

if __name__ == "__main__":
    main()