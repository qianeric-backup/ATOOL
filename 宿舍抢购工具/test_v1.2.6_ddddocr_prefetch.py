# -*- coding: utf-8 -*-
"""
v1.2.6版本降级为ddddocr预取测试脚本
测试v1.2.6版本降级为ddddocr预取的性能
"""
import sys
import os
import time
import subprocess
import json
import requests
import base64

def test_v126_ddddocr_prefetch(exe_path, version_name, test_count=10):
    """测试v1.2.6版本降级为ddddocr预取"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本降级为ddddocr预取（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 测试命令（使用演练模式，禁用AI）
            cmd = [
                exe_path,
                "--enrollid", "2633233352",
                "--idcard", "341226200807104418",
                "--dry-run",
                "--no-ai",  # 禁用AI，只使用ddddocr
                "--no-ocr"  # 禁用OCR识别
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
    
    print(f"\n{version_name}版本降级为ddddocr预取统计（{test_count}次测试）:")
    print(f"  成功率: {success_count}/{test_count} ({summary['success_rate']:.1f}%)")
    print(f"  平均耗时: {avg_time:.3f}秒")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  最快耗时: {summary['min_time']:.3f}秒")
    print(f"  最慢耗时: {summary['max_time']:.3f}秒")
    
    return summary

def run_v126_ddddocr_prefetch_test():
    """运行v1.2.6版本降级为ddddocr预取测试"""
    print("v1.2.6版本降级为ddddocr预取测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.2.6（修复后）降级为ddddocr预取")
    print(f"测试次数: 10次")
    print(f"测试说明: 测试v1.2.6版本降级为ddddocr预取的性能")
    
    # 测试版本路径
    exe_path = "releases/v1.2.6/grab_dorm_multi_account_v1.2.6.exe"
    
    if not os.path.exists(exe_path):
        print(f"[FAIL] v1.2.6版本exe文件不存在: {exe_path}")
        return False
    
    print(f"[OK] v1.2.6版本exe文件存在: {exe_path}")
    
    # 测试降级为ddddocr预取
    summary = test_v126_ddddocr_prefetch(exe_path, "v1.2.6（降级为ddddocr预取）", test_count=10)
    
    # 保存详细结果
    report_file = f"v1.2.6降级为ddddocr预取测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return summary

def main():
    """主函数"""
    print("v1.2.6版本降级为ddddocr预取测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = run_v126_ddddocr_prefetch_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] v1.2.6版本降级为ddddocr预取测试完成")
        print(f"  - 成功率: {result['success_rate']:.1f}%")
        print(f"  - 平均耗时: {result['avg_time']:.3f}秒")
        print(f"  - 测试次数: {result['test_count']}")
    else:
        print("[FAIL] v1.2.6版本降级为ddddocr预取测试失败")
    
    print("\n测试说明:")
    print("1. 测试v1.2.6版本降级为ddddocr预取的性能")
    print("2. 使用--no-ai参数禁用AI，只使用ddddocr")
    print("3. 测试降级后的性能表现")

if __name__ == "__main__":
    main()