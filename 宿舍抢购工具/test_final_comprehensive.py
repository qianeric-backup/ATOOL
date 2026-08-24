# -*- coding: utf-8 -*-
"""
最终全面测试脚本
全面测试v1.2.6（修复后）和V0.0.9c版本
"""
import sys
import os
import time
import subprocess
import json
import requests
import base64

def test_final_comprehensive(exe_path, version_name, test_count=10):
    """最终全面测试"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本（最终全面测试）（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 测试1: 核心功能耗时
            cmd = [exe_path, "--version"]
            if "v1.2.6" in version_name:
                cmd.extend(["--key", "RSO-QIANGSS-2026"])
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            core_time = time.time() - start_time
            
            # 测试2: 实际环境耗时
            cmd_real = [
                exe_path,
                "--enrollid", "2633233352",
                "--idcard", "341226200807104418",
                "--dry-run",
                "--no-ocr"
            ]
            if "v1.2.6" in version_name:
                cmd_real.extend(["--key", "RSO-QIANGSS-2026"])
            
            start_time = time.time()
            result_real = subprocess.run(cmd_real, capture_output=True, text=True, timeout=60)
            real_time = time.time() - start_time
            real_success = result_real.returncode == 0 and "[DRY-RUN] 演练结束" in result_real.stdout
            
            # 测试3: 验证码正确速度
            captcha_start = time.time()
            
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code == 200:
                # AI识别
                api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
                base_url = "https://open.bigmodel.cn/api/paas/v4"
                b64 = base64.b64encode(captcha_response.content).decode()
                
                recognize_start = time.time()
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "glm-4v-plus-0111",
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": "识别图片中的5位验证码。只输出5个字符。"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                        ]}],
                        "max_tokens": 10,
                        "temperature": 0
                    },
                    timeout=15
                )
                recognize_time = time.time() - recognize_start
                
                if response.status_code == 200:
                    captcha = response.json()["choices"][0]["message"]["content"].strip()
                    captcha = "".join(c for c in captcha if c.isalnum())
                    
                    # 提交验证码
                    submit_start = time.time()
                    login_response = requests.post("https://enroll.gench.edu.cn/api/stu/login", data={"enrollid": "2633233352", "idcard": "341226200807104418"}, timeout=10)
                    submit_response = requests.post("https://enroll.gench.edu.cn/api/stu/set_dorm", data={"did": 81, "yzmstr": captcha}, timeout=10)
                    submit_time = time.time() - submit_start
                    total_captcha_time = recognize_time + submit_time
                else:
                    recognize_time = 0
                    submit_time = 0
                    total_captcha_time = 0
                    captcha = ""
            else:
                recognize_time = 0
                submit_time = 0
                total_captcha_time = 0
                captcha = ""
            
            # 记录结果
            test_result = {
                "test_id": i + 1,
                "core_time": core_time,
                "real_time": real_time,
                "real_success": real_success,
                "recognize_time": recognize_time,
                "submit_time": submit_time,
                "total_captcha_time": total_captcha_time,
                "captcha": captcha
            }
            
            results.append(test_result)
            
            print(f"    核心耗时: {core_time:.3f}秒")
            print(f"    实际耗时: {real_time:.3f}秒")
            print(f"    验证码耗时: {total_captcha_time:.3f}秒")
            
            time.sleep(0.5)  # 等待0.5秒再进行下一次测试
            
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
    
    # 统计结果
    if results:
        core_times = [r["core_time"] for r in results]
        real_times = [r["real_time"] for r in results]
        captcha_times = [r["total_captcha_time"] for r in results]
        
        summary = {
            "version": version_name,
            "test_count": len(results),
            "avg_core_time": sum(core_times) / len(core_times),
            "avg_real_time": sum(real_times) / len(real_times),
            "avg_captcha_time": sum(captcha_times) / len(captcha_times),
            "min_captcha_time": min(captcha_times),
            "max_captcha_time": max(captcha_times),
            "results": results
        }
        
        print(f"\n{version_name}版本最终全面测试统计:")
        print(f"  测试次数: {len(results)}")
        print(f"  平均核心耗时: {summary['avg_core_time']:.3f}秒")
        print(f"  平均实际耗时: {summary['avg_real_time']:.3f}秒")
        print(f"  平均验证码耗时: {summary['avg_captcha_time']:.3f}秒")
        print(f"  最快验证码耗时: {summary['min_captcha_time']:.3f}秒")
        print(f"  最慢验证码耗时: {summary['max_captcha_time']:.3f}秒")
        
        return summary
    
    return None

def run_final_comprehensive_test():
    """运行最终全面测试"""
    print("最终全面测试（v1.2.6修复后 vs V0.0.9c）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.2.6（修复后）, V0.0.9c")
    print(f"测试次数: 每个版本10次")
    print(f"测试说明: 全面测试核心耗时、实际耗时、验证码耗时")
    
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
        summary = test_final_comprehensive(exe_path, version_name, test_count=10)
        if summary:
            all_results[version_name] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("最终全面测试对比报告")
    print(f"{'='*80}")
    
    print(f"{'版本':<20} {'平均核心耗时':<15} {'平均实际耗时':<15} {'平均验证码耗时':<15} {'最快验证码耗时':<15}")
    print("-" * 80)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<20} {summary['avg_core_time']:.3f}秒{'':<10} {summary['avg_real_time']:.3f}秒{'':<10} {summary['avg_captcha_time']:.3f}秒{'':<10} {summary['min_captcha_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"最终全面测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("最终全面测试（v1.2.6修复后 vs V0.0.9c）")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_final_comprehensive_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 最终全面测试完成")
        print("  - 测试了v1.2.6（修复后）和V0.0.9c版本")
        print("  - 每个版本测试了10次")
        print("  - 全面测试了核心耗时、实际耗时、验证码耗时")
    else:
        print("[FAIL] 最终全面测试失败")
    
    print("\n测试说明:")
    print("1. 全面测试核心耗时、实际耗时、验证码耗时")
    print("2. 测试v1.2.6（修复后）和V0.0.9c版本")
    print("3. 使用真实环境API进行测试")

if __name__ == "__main__":
    main()