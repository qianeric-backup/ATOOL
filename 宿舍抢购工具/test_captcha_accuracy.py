# -*- coding: utf-8 -*-
"""
验证码识别准确性测试
增加测试次数，验证账号2验证码识别错误问题
"""
import sys
import os
import time
import requests
import base64
import json
from datetime import datetime

def test_captcha_accuracy():
    """验证码识别准确性测试"""
    print("验证码识别准确性测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"重点测试: 账号2验证码识别准确性")
    
    # 创建结果保存目录
    results_dir = "captcha_accuracy_test"
    os.makedirs(results_dir, exist_ok=True)
    
    # 测试1: 账号2多次验证码识别测试
    print(f"\n{'='*80}")
    print("测试1: 账号2多次验证码识别测试（10次）")
    print(f"{'='*80}")
    
    result1 = test_account2_multiple_captchas(results_dir)
    
    # 测试2: AI vs ddddocr对比测试
    print(f"\n{'='*80}")
    print("测试2: AI vs ddddocr对比测试")
    print(f"{'='*80}")
    
    result2 = test_ai_vs_ddddocr(results_dir)
    
    # 测试3: 错误验证码分析
    print(f"\n{'='*80}")
    print("测试3: 错误验证码分析")
    print(f"{'='*80}")
    
    result3 = test_wrong_captcha_analysis(results_dir)
    
    # 总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}")
    
    total_tests = 3
    passed_tests = sum([result1, result2, result3])
    
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print(f"\n详细结果:")
    print(f"  账号2多次测试: {'通过' if result1 else '失败'}")
    print(f"  AI vs ddddocr对比: {'通过' if result2 else '失败'}")
    print(f"  错误验证码分析: {'通过' if result3 else '失败'}")
    
    # 保存报告
    report_file = f"验证码识别准确性测试报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"验证码识别准确性测试报告\n")
        f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"真实环境: https://enroll.gench.edu.cn\n")
        f.write(f"重点测试: 账号2验证码识别准确性\n\n")
        f.write(f"测试结果:\n")
        f.write(f"总测试数: {total_tests}\n")
        f.write(f"通过: {passed_tests}\n")
        f.write(f"失败: {total_tests - passed_tests}\n")
        f.write(f"成功率: {passed_tests/total_tests*100:.1f}%\n\n")
        f.write(f"详细结果:\n")
        f.write(f"  账号2多次测试: {'通过' if result1 else '失败'}\n")
        f.write(f"  AI vs ddddocr对比: {'通过' if result2 else '失败'}\n")
        f.write(f"  错误验证码分析: {'通过' if result3 else '失败'}\n")
    
    print(f"\n报告已保存到: {report_file}")
    
    return passed_tests == total_tests

def test_account2_multiple_captchas(results_dir):
    """测试账号2多次验证码识别"""
    print(f"测试账号2多次验证码识别...")
    
    try:
        # 登录账号2
        login_data = {"enrollid": "2631141739", "idcard": "310110200605112038"}
        login_response = requests.post(
            "https://enroll.gench.edu.cn/api/stu/login",
            data=login_data,
            timeout=10
        )
        
        if login_response.text.strip() != "1":
            print(f"    [FAIL] 登录失败")
            return False
        
        print(f"    [OK] 登录成功")
        
        # 多次获取验证码并识别
        test_count = 10
        results = []
        
        for i in range(test_count):
            print(f"\n    第{i+1}次测试:")
            
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"      [FAIL] 获取验证码失败")
                continue
            
            # 保存验证码图片
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            captcha_file = os.path.join(results_dir, f"account2_captcha_{i+1}_{timestamp}.jpg")
            with open(captcha_file, "wb") as f:
                f.write(captcha_response.content)
            
            # AI识别
            api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
            base_url = "https://open.bigmodel.cn/api/paas/v4"
            
            b64 = base64.b64encode(captcha_response.content).decode()
            
            start_time = time.time()
            recognize_response = requests.post(
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
            
            if recognize_response.status_code == 200:
                result = recognize_response.json()["choices"][0]["message"]["content"].strip()
                result = "".join(c for c in result if c.isalnum())
                
                print(f"      AI识别: {result} ({recognize_time:.3f}s)")
                
                # 提交验证码查看反馈
                submit_data = {
                    "did": 83,
                    "yzmstr": result
                }
                
                submit_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/set_dorm",
                    data=submit_data,
                    timeout=10
                )
                
                # 分析反馈
                feedback = analyze_feedback(submit_response, result)
                print(f"      服务器反馈: {feedback}")
                
                results.append({
                    "attempt": i+1,
                    "captcha_file": captcha_file,
                    "ai_result": result,
                    "recognize_time": recognize_time,
                    "feedback": feedback,
                    "captcha_size": len(captcha_response.content)
                })
            
            time.sleep(0.5)
        
        # 保存测试结果
        results_file = os.path.join(results_dir, "account2_multiple_test_results.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "test_count": test_count,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        # 分析结果
        print(f"\n    测试结果分析:")
        print(f"    总测试次数: {len(results)}")
        
        if results:
            # 统计反馈类型
            feedback_counts = {}
            for r in results:
                feedback = r["feedback"]
                feedback_counts[feedback] = feedback_counts.get(feedback, 0) + 1
            
            for feedback, count in feedback_counts.items():
                print(f"    {feedback}: {count}次")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 测试异常: {e}")
        return False

def analyze_feedback(response, captcha):
    """分析服务器反馈"""
    try:
        if response.status_code == 200:
            result = response.json()
            emsg = result.get("emsg", "")
            
            if "验证码错误" in emsg:
                return "验证码错误"
            elif "未到开放时间" in emsg or "当前时间暂未开放" in emsg:
                return "未到开放时间（验证码正确）"
            elif "系统异常" in emsg:
                return "系统异常"
            elif "登录" in emsg or "过期" in emsg:
                return "登录已过期"
            else:
                return f"其他: {emsg}"
        else:
            return f"HTTP错误: {response.status_code}"
    except Exception as e:
        return f"分析异常: {e}"

def test_ai_vs_ddddocr(results_dir):
    """测试AI vs ddddocr对比"""
    print(f"测试AI vs ddddocr对比...")
    
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
        
        # 对比测试5次
        test_count = 5
        results = []
        
        for i in range(test_count):
            print(f"\n    第{i+1}次对比测试:")
            
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"      [FAIL] 获取验证码失败")
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
                ai_result = ai_response.json()["choices"][0]["message"]["content"].strip()
                ai_result = "".join(c for c in ai_result if c.isalnum())
                
                # ddddocr识别
                import ddddocr
                ocr = ddddocr.DdddOcr(show_ad=False)
                
                start_time = time.time()
                dd_result = ocr.classification(captcha_response.content)
                dd_time = time.time() - start_time
                
                dd_result = "".join(c for c in dd_result if c.isalnum())
                
                print(f"      AI: {ai_result} ({ai_time:.3f}s)")
                print(f"      ddddocr: {dd_result} ({dd_time:.3f}s)")
                
                # 对比结果
                if ai_result.upper() == dd_result.upper():
                    print(f"      结果: 一致")
                    match = True
                else:
                    print(f"      结果: 不一致")
                    match = False
                
                results.append({
                    "attempt": i+1,
                    "ai_result": ai_result,
                    "dd_result": dd_result,
                    "ai_time": ai_time,
                    "dd_time": dd_time,
                    "match": match
                })
            
            time.sleep(0.5)
        
        # 保存对比结果
        results_file = os.path.join(results_dir, "ai_vs_ddddocr_results.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "test_count": test_count,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        # 分析结果
        print(f"\n    对比结果分析:")
        print(f"    总测试次数: {len(results)}")
        
        if results:
            match_count = sum(1 for r in results if r["match"])
            print(f"    一致次数: {match_count}")
            print(f"    不一致次数: {len(results) - match_count}")
            print(f"    一致率: {match_count/len(results)*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 对比测试异常: {e}")
        return False

def test_wrong_captcha_analysis(results_dir):
    """测试错误验证码分析"""
    print(f"测试错误验证码分析...")
    
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
        
        # 测试不同类型的错误验证码
        wrong_captchas = [
            "WRONG",      # 完全错误
            "12345",      # 纯数字
            "ABCDE",      # 纯字母
            "AB12",       # 4位（长度错误）
            "ABCDEF",     # 6位（长度错误）
        ]
        
        results = []
        
        for wrong_captcha in wrong_captchas:
            print(f"\n    测试错误验证码: {wrong_captcha}")
            
            submit_data = {
                "did": 81,
                "yzmstr": wrong_captcha
            }
            
            submit_response = requests.post(
                "https://enroll.gench.edu.cn/api/stu/set_dorm",
                data=submit_data,
                timeout=10
            )
            
            feedback = analyze_feedback(submit_response, wrong_captcha)
            print(f"      反馈: {feedback}")
            
            results.append({
                "wrong_captcha": wrong_captcha,
                "feedback": feedback
            })
        
        # 保存分析结果
        results_file = os.path.join(results_dir, "wrong_captcha_analysis.json")
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        # 分析结果
        print(f"\n    错误验证码分析结果:")
        for r in results:
            print(f"    {r['wrong_captcha']}: {r['feedback']}")
        
        return True
        
    except Exception as e:
        print(f"    [FAIL] 错误验证码分析异常: {e}")
        return False

def main():
    """主函数"""
    print("验证码识别准确性测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"重点测试: 账号2验证码识别准确性")
    
    # 运行测试
    result = test_captcha_accuracy()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] 验证码识别准确性测试成功")
        print("  - 账号2多次测试完成")
        print("  - AI vs ddddocr对比完成")
        print("  - 错误验证码分析完成")
    else:
        print("[FAIL] 验证码识别准确性测试失败")
    
    print("\n结果保存位置: captcha_accuracy_test/")
    print("包含验证码图片、识别结果和分析数据")

if __name__ == "__main__":
    main()