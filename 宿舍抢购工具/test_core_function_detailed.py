# -*- coding: utf-8 -*-
"""
核心功能详细测试脚本
详细列出测试过程和结果
"""
import sys
import os
import time
import subprocess
import json

def test_version_detailed(exe_path, version_name, test_count=20):
    """详细测试单个版本的核心功能"""
    print(f"\n{'='*80}")
    print(f"详细测试{version_name}版本核心功能（{test_count}次测试）")
    print(f"{'='*80}")
    
    # 测试命令
    test_cmd = [exe_path, "--version"]
    print(f"测试命令: {' '.join(test_cmd)}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            start_time = time.time()
            
            result = subprocess.run(
                test_cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            execution_time = time.time() - start_time
            
            # 记录详细结果
            test_result = {
                "test_id": i + 1,
                "execution_time": execution_time,
                "return_code": result.returncode,
                "output": result.stdout[:200] if result.stdout else "",
                "error": result.stderr[:200] if result.stderr else "",
                "command": ' '.join(test_cmd)
            }
            
            results.append(test_result)
            
            print(f"    执行命令: {' '.join(test_cmd)}")
            print(f"    耗时: {execution_time:.3f}秒")
            print(f"    返回码: {result.returncode}")
            print(f"    输出: {result.stdout[:100]}...")
            
            time.sleep(0.3)  # 等待0.3秒再进行下一次测试
            
        except subprocess.TimeoutExpired:
            print(f"    [FAIL] 测试超时")
            results.append({
                "test_id": i + 1,
                "execution_time": 10.0,
                "return_code": -1,
                "output": "",
                "error": "测试超时",
                "command": ' '.join(test_cmd)
            })
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
            results.append({
                "test_id": i + 1,
                "execution_time": 0.0,
                "return_code": -1,
                "output": "",
                "error": str(e),
                "command": ' '.join(test_cmd)
            })
    
    # 详细统计
    total_time = sum(r["execution_time"] for r in results)
    avg_time = total_time / len(results) if results else 0
    
    summary = {
        "version": version_name,
        "test_count": test_count,
        "test_command": ' '.join(test_cmd),
        "total_time": total_time,
        "avg_time": avg_time,
        "min_time": min(r["execution_time"] for r in results),
        "max_time": max(r["execution_time"] for r in results),
        "results": results
    }
    
    print(f"\n{version_name}版本详细统计（{test_count}次测试）:")
    print(f"  测试命令: {' '.join(test_cmd)}")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    print(f"  耗时波动: {summary['max_time'] - summary['min_time']:.3f}秒")
    
    return summary

def run_detailed_test():
    """运行详细测试"""
    print("核心功能详细测试（每个版本20次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: V0.0.9, v1.1.0, v1.2.4, v1.2.6")
    print(f"测试次数: 每个版本20次")
    print(f"测试说明: 详细列出测试过程和结果")
    
    # 测试版本路径
    versions = [
        ("releases/v0.0.9/grab_dorm.exe", "V0.0.9"),
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
        
        # 详细测试该版本
        summary = test_version_detailed(exe_path, version_name, test_count=20)
        all_results[version_name] = summary
    
    # 生成详细对比报告
    print(f"\n{'='*80}")
    print("版本详细对比报告")
    print(f"{'='*80}")
    
    print(f"{'版本':<10} {'测试命令':<30} {'平均耗时':<15} {'最快耗时':<15} {'最慢耗时':<15}")
    print("-" * 90)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<10} {summary['test_command']:<30} {summary['avg_time']:.3f}秒{'':<10} {summary['min_time']:.3f}秒{'':<10} {summary['max_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"核心功能详细测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("核心功能详细测试（每个版本20次）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行详细测试
    results = run_detailed_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 核心功能详细测试完成")
        print("  - 测试了V0.0.9、v1.1.0、v1.2.4、v1.2.6版本")
        print("  - 每个版本测试了20次")
        print("  - 详细列出了测试过程和结果")
    else:
        print("[FAIL] 核心功能详细测试失败")
    
    print("\n测试说明:")
    print("1. 只测试--version命令的执行时间")
    print("2. 不包含登录、查询、校时等耗时")
    print("3. 测试程序启动和参数解析的耗时")
    print("4. 详细列出每次测试的命令、耗时、返回码")

if __name__ == "__main__":
    main()