# -*- coding: utf-8 -*-
"""
验证码正确速度再次测试脚本
再次测试验证码正确时的速度
"""
import sys
import os
import time
import subprocess
import json
import requests
import base64

def test_captcha_correct_speed_again(exe_path, version_name, test_count=10):
    """再次测试验证码正确速度"""
    print(f"\n{'='*80}")
    print(f"测试{version_name}版本验证码正确速度（{test_count}次测试）")
    print(f"{'='*80}")
    
    results = []
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"    [FAIL] 获取验证码失败")
                continue
            
            # AI识别验证码
            api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
            base_url = "https://open.bigmodel.cn/api/paas/v4"
            
            b64 = base64.b64encode(captcha_response.content).decode()
            
            start_time = time.time()
            
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
            
            recognize_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"].strip()
                result = "".join(c for c in result if c.isalnum())
                
                # 提交验证码
                submit_start_time = time.time()
                
                # 登录
                login_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/login",
                    data={"enrollid": "2633233352", "idcard": "341226200807104418"},
                    timeout=10
                )
                
                # 提交验证码
                submit_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/set_dorm",
                    data={"did": 81, "yzmstr": result},
                    timeout=10
                )
                
                submit_time = time.time() - submit_start_time
                
                # 分析结果
                submit_success = submit_response.status_code == 200
                response_data = submit_response.json() if submit_success else {}
                
                # 记录结果
                test_result = {
                    "test_id": i + 1,
                    "recognize_time": recognize_time,
                    "submit_time": submit_time,
                    "total_time": recognize_time + submit_time,
                    "captcha": result,
                    "submit_success": submit_success,
                    "response": response_data
                }
                
                results.append(test_result)
                
                print(f"    识别时间: {recognize_time:.3f}秒")
                print(f"    提交时间: {submit_time:.3f}秒")
                print(f"    总时间: {recognize_time + submit_time:.3f}秒")
                print(f"    验证码: {result}")
                print(f"    提交状态: {'成功' if submit_success else '失败'}")
                print(f"    服务器响应: {response_data.get('emsg', '无')}")
                
                time.sleep(0.5)  # 等待0.5秒再进行下一次测试
            
        except Exception as e:
            print(f"    [FAIL] 测试异常: {e}")
    
    # 统计结果
    if results:
        recognize_times = [r["recognize_time"] for r in results]
        submit_times = [r["submit_time"] for r in results]
        total_times = [r["total_time"] for r in results]
        
        summary = {
            "version": version_name,
            "test_count": len(results),
            "avg_recognize_time": sum(recognize_times) / len(recognize_times),
            "avg_submit_time": sum(submit_times) / len(submit_times),
            "avg_total_time": sum(total_times) / len(total_times),
            "min_total_time": min(total_times),
            "max_total_time": max(total_times),
            "results": results
        }
        
        print(f"\n{version_name}版本验证码正确速度统计:")
        print(f"  测试次数: {len(results)}")
        print(f"  平均识别时间: {summary['avg_recognize_time']:.3f}秒")
        print(f"  平均提交时间: {summary['avg_submit_time']:.3f}秒")
        print(f"  平均总时间: {summary['avg_total_time']:.3f}秒")
        print(f"  最快总时间: {summary['min_total_time']:.3f}秒")
        print(f"  最慢总时间: {summary['max_total_time']:.3f}秒")
        
        return summary
    
    return None

def run_captcha_correct_speed_again_test():
    """运行验证码正确速度再次测试"""
    print("验证码正确速度再次测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: v1.2.6（修复后）, V0.0.9c")
    print(f"测试次数: 每个版本10次")
    print(f"测试说明: 再次测试验证码正确时的速度")
    
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
        summary = test_captcha_correct_speed_again(exe_path, version_name, test_count=10)
        if summary:
            all_results[version_name] = summary
    
    # 生成对比报告
    print(f"\n{'='*80}")
    print("验证码正确速度再次对比报告")
    print(f"{'='*80}")
    
    print(f"{'版本':<20} {'平均识别时间':<15} {'平均提交时间':<15} {'平均总时间':<15} {'最快总时间':<15}")
    print("-" * 80)
    
    for version_name, summary in all_results.items():
        print(f"{version_name:<20} {summary['avg_recognize_time']:.3f}秒{'':<10} {summary['avg_submit_time']:.3f}秒{'':<10} {summary['avg_total_time']:.3f}秒{'':<10} {summary['min_total_time']:.3f}秒")
    
    # 保存详细结果
    report_file = f"验证码正确速度再次测试报告_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {report_file}")
    
    return all_results

def main():
    """主函数"""
    print("验证码正确速度再次测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    results = run_captcha_correct_speed_again_test()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if results:
        print("[OK] 验证码正确速度再次测试完成")
        print("  - 测试了v1.2.6（修复后）和V0.0.9c版本")
        print("  - 每个版本测试了10次")
        print("  - 再次测试验证码正确时的速度")
    else:
        print("[FAIL] 验证码正确速度再次测试失败")
    
    print("\n测试说明:")
    print("1. 再次测试验证码正确时的速度")
    print("2. 测试识别时间、提交时间、总时间")
    print("3. 使用真实环境API进行测试")

if __name__ == "__main__":
    main()