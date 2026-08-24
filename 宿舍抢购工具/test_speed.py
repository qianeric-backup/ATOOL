# -*- coding: utf-8 -*-
"""
实际速度测试脚本
直接提交验证码测试速度，不关注回显结果
"""
import sys
import os
import time
import requests
import base64
import json

def test_speed():
    """测试速度"""
    print("实际速度测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试目标: 直接提交验证码测试速度，不关注回显结果")
    
    # 测试1: v1.2.5版本速度测试
    print(f"\n{'='*80}")
    print("测试1: v1.2.5版本速度测试")
    print(f"{'='*80}")
    
    result1 = test_v125_speed()
    
    # 测试2: v1.2.4版本速度对比
    print(f"\n{'='*80}")
    print("测试2: v1.2.4版本速度对比")
    print(f"{'='*80}")
    
    result2 = test_v124_speed()
    
    # 测试3: 速度对比分析
    print(f"\n{'='*80}")
    print("测试3: 速度对比分析")
    print(f"{'='*80}")
    
    result3 = analyze_speed()
    
    # 总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}")
    
    total_tests = 3
    passed_tests = sum([result1, result2, result3])
    
    print(f"总测试项: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print(f"\n详细结果:")
    print(f"  v1.2.5版本速度测试: {'通过' if result1 else '失败'}")
    print(f"  v1.2.4版本速度对比: {'通过' if result2 else '失败'}")
    print(f"  速度对比分析: {'通过' if result3 else '失败'}")
    
    # 保存报告
    report_file = f"速度测试报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"速度测试报告\n")
        f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"测试目标: 直接提交验证码测试速度，不关注回显结果\n\n")
        f.write(f"测试结果:\n")
        f.write(f"总测试项: {total_tests}\n")
        f.write(f"通过: {passed_tests}\n")
        f.write(f"失败: {total_tests - passed_tests}\n")
        f.write(f"成功率: {passed_tests/total_tests*100:.1f}%\n\n")
        f.write(f"详细结果:\n")
        f.write(f"  v1.2.5版本速度测试: {'通过' if result1 else '失败'}\n")
        f.write(f"  v1.2.4版本速度对比: {'通过' if result2 else '失败'}\n")
        f.write(f"  速度对比分析: {'通过' if result3 else '失败'}\n")
    
    print(f"\n报告已保存到: {report_file}")
    
    return passed_tests == total_tests

def test_v125_speed():
    """测试v1.2.5版本速度"""
    print(f"测试v1.2.5版本速度...")
    
    try:
        # 登录
        login_data = {"enrollid": "2633233352", "idcard": "341226200807104418"}
        login_response = requests.post(
            "https://enroll.gench.edu.cn/api/stu/login",
            data=login_data,
            timeout=10
        )
        
        if login_response.text.strip() != "1":
            print(f"    [FAIL] 登录失败")
            return False
        
        print(f"    [OK] 登录成功")
        
        # 测试10次提交速度
        test_count = 10
        times = []
        
        for i in range(test_count):
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"    [FAIL] 获取验证码失败")
                continue
            
            # AI识别
            api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
            base_url = "https://open.bigmodel.cn/api/paas/v4"
            
            b64 = base64.b64encode(captcha_response.content).decode()
            
            start_time = time.time()
            ai_response = requests.post(
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
            
            ai_time = time.time() - start_time
            
            if ai_response.status_code == 200:
                result = ai_response.json()["choices"][0]["message"]["content"].strip()
                result = "".join(c for c in result if c.isalnum())
                
                # 提交验证码
                submit_data = {
                    "did": 81,
                    "yzmstr": result
                }
                
                start_time = time.time()
                submit_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/set_dorm",
                    data=submit_data,
                    timeout=10
                )
                submit_time = time.time() - start_time
                
                total_time = ai_time + submit_time
                times.append(total_time)
                
                print(f"    测试{i+1}: AI识别 {ai_time:.3f}s + 提交 {submit_time:.3f}s = 总耗时 {total_time:.3f}s")
            
            time.sleep(0.5)
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"\n    v1.2.5版本速度统计:")
            print(f"    平均耗时: {avg_time:.3f}秒")
            print(f"    最快耗时: {min_time:.3f}秒")
            print(f"    最慢耗时: {max_time:.3f}秒")
            print(f"    测试次数: {len(times)}")
            
            # 保存结果
            results = {
                "version": "v1.2.5",
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "test_count": len(times),
                "times": times
            }
            
            with open("v1.2.5_speed_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"    [FAIL] v1.2.5版本速度测试异常: {e}")
        return False

def test_v124_speed():
    """测试v1.2.4版本速度"""
    print(f"测试v1.2.4版本速度...")
    
    try:
        # 登录
        login_data = {"enrollid": "2633233352", "idcard": "341226200807104418"}
        login_response = requests.post(
            "https://enroll.gench.edu.cn/api/stu/login",
            data=login_data,
            timeout=10
        )
        
        if login_response.text.strip() != "1":
            print(f"    [FAIL] 登录失败")
            return False
        
        print(f"    [OK] 登录成功")
        
        # 测试10次提交速度
        test_count = 10
        times = []
        
        for i in range(test_count):
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"    [FAIL] 获取验证码失败")
                continue
            
            # AI识别
            api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
            base_url = "https://open.bigmodel.cn/api/paas/v4"
            
            b64 = base64.b64encode(captcha_response.content).decode()
            
            start_time = time.time()
            ai_response = requests.post(
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
            
            ai_time = time.time() - start_time
            
            if ai_response.status_code == 200:
                result = ai_response.json()["choices"][0]["message"]["content"].strip()
                result = "".join(c for c in result if c.isalnum())
                
                # 提交验证码
                submit_data = {
                    "did": 81,
                    "yzmstr": result
                }
                
                start_time = time.time()
                submit_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/set_dorm",
                    data=submit_data,
                    timeout=10
                )
                submit_time = time.time() - start_time
                
                total_time = ai_time + submit_time
                times.append(total_time)
                
                print(f"    测试{i+1}: AI识别 {ai_time:.3f}s + 提交 {submit_time:.3f}s = 总耗时 {total_time:.3f}s")
            
            time.sleep(0.5)
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"\n    v1.2.4版本速度统计:")
            print(f"    平均耗时: {avg_time:.3f}秒")
            print(f"    最快耗时: {min_time:.3f}秒")
            print(f"    最慢耗时: {max_time:.3f}秒")
            print(f"    测试次数: {len(times)}")
            
            # 保存结果
            results = {
                "version": "v1.2.4",
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "test_count": len(times),
                "times": times
            }
            
            with open("v1.2.4_speed_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"    [FAIL] v1.2.4版本速度测试异常: {e}")
        return False

def analyze_speed():
    """分析速度对比"""
    print(f"分析速度对比...")
    
    try:
        # 读取v1.2.5结果
        if os.path.exists("v1.2.5_speed_results.json"):
            with open("v1.2.5_speed_results.json", "r", encoding="utf-8") as f:
                v125_results = json.load(f)
        else:
            print(f"    [FAIL] v1.2.5结果文件不存在")
            return False
        
        # 读取v1.2.4结果
        if os.path.exists("v1.2.4_speed_results.json"):
            with open("v1.2.4_speed_results.json", "r", encoding="utf-8") as f:
                v124_results = json.load(f)
        else:
            print(f"    [FAIL] v1.2.4结果文件不存在")
            return False
        
        # 对比分析
        print(f"\n    速度对比分析:")
        print(f"    v1.2.5版本平均耗时: {v125_results['avg_time']:.3f}秒")
        print(f"    v1.2.4版本平均耗时: {v124_results['avg_time']:.3f}秒")
        
        speed_improvement = v124_results['avg_time'] - v125_results['avg_time']
        improvement_ratio = speed_improvement / v124_results['avg_time'] * 100
        
        print(f"    速度提升: {speed_improvement:.3f}秒 ({improvement_ratio:.1f}%)")
        
        # 保存对比结果
        comparison = {
            "v1.2.5": v125_results,
            "v1.2.4": v124_results,
            "speed_improvement": speed_improvement,
            "improvement_ratio": improvement_ratio
        }
        
        with open("speed_comparison.json", "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        
        print(f"    对比结果已保存: speed_comparison.json")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 速度对比分析异常: {e}")
        return False

def main():
    """主函数"""
    print("实际速度测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试目标: 直接提交验证码测试速度，不关注回显结果")
    
    # 运行测试
    result = test_speed()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] 速度测试成功")
        print("  - v1.2.5版本速度测试完成")
        print("  - v1.2.4版本速度对比完成")
        print("  - 速度对比分析完成")
    else:
        print("[FAIL] 速度测试失败")
    
    print("\n测试说明:")
    print("1. 直接提交验证码测试速度")
    print("2. 不关注回显结果（系统异常等）")
    print("3. 只关注耗时数据")

if __name__ == "__main__":
    main()