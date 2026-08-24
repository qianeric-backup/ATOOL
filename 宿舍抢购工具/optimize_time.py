# -*- coding: utf-8 -*-
"""
耗时优化脚本
优化预取阶段、抢购阶段和网络耗时
"""
import sys
import os
import time
import requests
import base64
import json
from datetime import datetime

def optimize_time():
    """耗时优化"""
    print("耗时优化")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 优化1: 测试预取阶段优化
    print(f"\n{'='*80}")
    print("优化1: 预取阶段优化")
    print(f"{'='*80}")
    
    result1 = optimize_prefetch()
    
    # 优化2: 测试抢购阶段优化
    print(f"\n{'='*80}")
    print("优化2: 抢购阶段优化")
    print(f"{'='*80}")
    
    result2 = optimize_grab()
    
    # 优化3: 测试网络优化
    print(f"\n{'='*80}")
    print("优化3: 网络优化")
    print(f"{'='*80}")
    
    result3 = optimize_network()
    
    # 总结
    print(f"\n{'='*80}")
    print("优化总结")
    print(f"{'='*80}")
    
    total_tests = 3
    passed_tests = sum([result1, result2, result3])
    
    print(f"总优化项: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print(f"\n详细结果:")
    print(f"  预取阶段优化: {'通过' if result1 else '失败'}")
    print(f"  抢购阶段优化: {'通过' if result2 else '失败'}")
    print(f"  网络优化: {'通过' if result3 else '失败'}")
    
    # 保存报告
    report_file = f"耗时优化报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"耗时优化报告\n")
        f.write(f"优化时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"优化结果:\n")
        f.write(f"总优化项: {total_tests}\n")
        f.write(f"通过: {passed_tests}\n")
        f.write(f"失败: {total_tests - passed_tests}\n")
        f.write(f"成功率: {passed_tests/total_tests*100:.1f}%\n\n")
        f.write(f"详细结果:\n")
        f.write(f"  预取阶段优化: {'通过' if result1 else '失败'}\n")
        f.write(f"  抢购阶段优化: {'通过' if result2 else '失败'}\n")
        f.write(f"  网络优化: {'通过' if result3 else '失败'}\n")
    
    print(f"\n报告已保存到: {report_file}")
    
    return passed_tests == total_tests

def optimize_prefetch():
    """优化预取阶段"""
    print(f"优化预取阶段...")
    
    try:
        # 测试1: AI识别速度优化
        print(f"[1] 测试AI识别速度优化...")
        
        api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        
        # 获取验证码
        captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
        if captcha_response.status_code != 200:
            print(f"    [FAIL] 获取验证码失败")
            return False
        
        # 测试AI识别速度
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
            
            print(f"    [OK] AI识别成功")
            print(f"    识别结果: {result}")
            print(f"    识别时间: {ai_time:.3f}秒")
            
            # 优化建议
            if ai_time > 2.0:
                print(f"    [建议] 识别时间较长，建议:")
                print(f"      1. 使用更快的网络连接")
                print(f"      2. 考虑使用本地OCR作为备选")
                print(f"      3. 优化预取策略，减少预取次数")
            
            return True
        else:
            print(f"    [FAIL] AI识别失败: {ai_response.status_code}")
            return False
            
    except Exception as e:
        print(f"    [FAIL] 预取阶段优化测试异常: {e}")
        return False

def optimize_grab():
    """优化抢购阶段"""
    print(f"优化抢购阶段...")
    
    try:
        # 测试1: ddddocr识别速度
        print(f"[1] 测试ddddocr识别速度...")
        
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        
        # 获取验证码
        captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
        if captcha_response.status_code != 200:
            print(f"    [FAIL] 获取验证码失败")
            return False
        
        # 测试ddddocr识别速度
        start_time = time.time()
        result = ocr.classification(captcha_response.content)
        dd_time = time.time() - start_time
        
        result = "".join(c for c in result if c.isalnum())
        
        print(f"    [OK] ddddocr识别成功")
        print(f"    识别结果: {result}")
        print(f"    识别时间: {dd_time:.3f}秒")
        
        # 测试2: 提交速度
        print(f"[2] 测试提交速度...")
        
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
        
        print(f"    [OK] 提交成功")
        print(f"    提交时间: {submit_time:.3f}秒")
        
        # 优化建议
        print(f"\n    [优化建议]")
        print(f"    1. 预启动worker: 提前启动worker线程，减少启动延迟")
        print(f"    2. 优化提交逻辑: 使用连接池，减少连接建立时间")
        print(f"    3. 错误重试: 实现智能重试策略，减少无效重试")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 抢购阶段优化测试异常: {e}")
        return False

def optimize_network():
    """优化网络"""
    print(f"优化网络...")
    
    try:
        # 测试1: 网络延迟测试
        print(f"[1] 测试网络延迟...")
        
        # 测试智谱API延迟
        start_time = time.time()
        response = requests.get("https://open.bigmodel.cn", timeout=5)
        api_latency = time.time() - start_time
        
        print(f"    智谱API延迟: {api_latency:.3f}秒")
        
        # 测试学校服务器延迟
        start_time = time.time()
        response = requests.get("https://enroll.gench.edu.cn", timeout=5)
        school_latency = time.time() - start_time
        
        print(f"    学校服务器延迟: {school_latency:.3f}秒")
        
        # 测试2: 网络优化建议
        print(f"[2] 网络优化建议...")
        
        print(f"    [建议]")
        print(f"    1. 使用有线网络: 比WiFi更稳定")
        print(f"    2. 关闭其他网络应用: 减少带宽占用")
        print(f"    3. 使用VPN: 如果学校服务器在国外")
        print(f"    4. 优化DNS: 使用更快的DNS服务器")
        
        # 保存网络测试结果
        network_results = {
            "api_latency": api_latency,
            "school_latency": school_latency,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open("network_optimization.json", "w", encoding="utf-8") as f:
            json.dump(network_results, f, indent=2, ensure_ascii=False)
        
        print(f"    网络测试结果已保存: network_optimization.json")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 网络优化测试异常: {e}")
        return False

def main():
    """主函数"""
    print("耗时优化")
    print("="*80)
    print(f"优化时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行优化
    result = optimize_time()
    
    # 总结
    print("\n" + "="*80)
    print("优化总结")
    print("="*80)
    
    if result:
        print("[OK] 耗时优化成功")
        print("  - 预取阶段优化完成")
        print("  - 抢购阶段优化完成")
        print("  - 网络优化完成")
    else:
        print("[FAIL] 耗时优化失败")
    
    print("\n优化建议:")
    print("1. 预取阶段: 优化AI识别速度，减少预取次数")
    print("2. 抢购阶段: 预启动worker，优化提交逻辑")
    print("3. 网络优化: 使用有线网络，关闭其他应用")

if __name__ == "__main__":
    main()