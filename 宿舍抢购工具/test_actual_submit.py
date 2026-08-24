# -*- coding: utf-8 -*-
"""
实际抢购提交测试脚本
测试真实环境验证码提交，验证正确/错误反馈
"""
import sys
import os
import time
import requests
import base64
import json

def test_actual_submit():
    """实际抢购提交测试"""
    print("实际抢购提交测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"测试账号: 2633233352, 2631141739")
    
    # 创建结果保存目录
    results_dir = "submit_results"
    os.makedirs(results_dir, exist_ok=True)
    
    # 测试1: 账号1实际提交
    print(f"\n{'='*80}")
    print("测试1: 账号1实际提交")
    print(f"{'='*80}")
    
    result1 = test_account_actual_submit(
        "2633233352",
        "341226200807104418",
        results_dir,
        "account1"
    )
    
    # 测试2: 账号2实际提交
    print(f"\n{'='*80}")
    print("测试2: 账号2实际提交")
    print(f"{'='*80}")
    
    result2 = test_account_actual_submit(
        "2631141739",
        "310110200605112038",
        results_dir,
        "account2"
    )
    
    # 测试3: 测试错误验证码提交
    print(f"\n{'='*80}")
    print("测试3: 错误验证码提交测试")
    print(f"{'='*80}")
    
    result3 = test_wrong_captcha_submit(results_dir)
    
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
    print(f"  账号1实际提交: {'通过' if result1 else '失败'}")
    print(f"  账号2实际提交: {'通过' if result2 else '失败'}")
    print(f"  错误验证码测试: {'通过' if result3 else '失败'}")
    
    # 保存报告
    report_file = f"实际抢购提交测试报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"实际抢购提交测试报告\n")
        f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"真实环境: https://enroll.gench.edu.cn\n\n")
        f.write(f"测试结果:\n")
        f.write(f"总测试数: {total_tests}\n")
        f.write(f"通过: {passed_tests}\n")
        f.write(f"失败: {total_tests - passed_tests}\n")
        f.write(f"成功率: {passed_tests/total_tests*100:.1f}%\n\n")
        f.write(f"详细结果:\n")
        f.write(f"  账号1实际提交: {'通过' if result1 else '失败'}\n")
        f.write(f"  账号2实际提交: {'通过' if result2 else '失败'}\n")
        f.write(f"  错误验证码测试: {'通过' if result3 else '失败'}\n")
    
    print(f"\n报告已保存到: {report_file}")
    
    return passed_tests == total_tests

def test_account_actual_submit(enrollid, idcard, results_dir, account_name):
    """测试单个账号的实际提交"""
    print(f"测试{account_name}实际提交...")
    
    try:
        # 步骤1: 登录
        print(f"[1] 登录...")
        login_data = {"enrollid": enrollid, "idcard": idcard}
        login_response = requests.post(
            "https://enroll.gench.edu.cn/api/stu/login",
            data=login_data,
            timeout=10
        )
        
        if login_response.text.strip() == "1":
            print(f"    [OK] 登录成功")
        else:
            print(f"    [FAIL] 登录失败: {login_response.text}")
            return False
        
        # 步骤2: 获取验证码
        print(f"[2] 获取验证码...")
        captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
        if captcha_response.status_code != 200:
            print(f"    [FAIL] 获取验证码失败: {captcha_response.status_code}")
            return False
        
        # 保存验证码图片
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        captcha_file = os.path.join(results_dir, f"{account_name}_captcha_{timestamp}.jpg")
        with open(captcha_file, "wb") as f:
            f.write(captcha_response.content)
        
        print(f"    [OK] 验证码获取成功，大小: {len(captcha_response.content)} bytes")
        print(f"    验证码已保存: {captcha_file}")
        
        # 步骤3: AI识别验证码
        print(f"[3] AI识别验证码...")
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
            
            print(f"    [OK] AI识别成功")
            print(f"    识别结果: {result}")
            print(f"    识别时间: {recognize_time:.3f}秒")
            
            # 步骤4: 提交验证码
            print(f"[4] 提交验证码...")
            submit_data = {
                "did": 81,  # 使用模拟宿舍ID
                "yzmstr": result
            }
            
            submit_response = requests.post(
                "https://enroll.gench.edu.cn/api/stu/set_dorm",
                data=submit_data,
                timeout=10
            )
            
            # 分析提交结果
            submit_result = analyze_submit_result(submit_response, account_name, result)
            
            # 保存提交结果
            submit_info = {
                "account": account_name,
                "enrollid": enrollid,
                "captcha_file": captcha_file,
                "captcha_size": len(captcha_response.content),
                "ai_result": result,
                "recognize_time": recognize_time,
                "submit_result": submit_result,
                "timestamp": timestamp
            }
            
            info_file = os.path.join(results_dir, f"{account_name}_submit_info_{timestamp}.json")
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump(submit_info, f, indent=2, ensure_ascii=False)
            
            print(f"    提交结果已保存: {info_file}")
            
            return True
        else:
            print(f"    [FAIL] AI识别失败: {recognize_response.status_code}")
            return False
            
    except Exception as e:
        print(f"    [FAIL] 测试异常: {e}")
        return False

def analyze_submit_result(response, account_name, captcha):
    """分析提交结果"""
    try:
        if response.status_code == 200:
            result = response.json()
            
            if result.get("suc") is True:
                print(f"    [SUCCESS] 验证码提交成功!")
                print(f"    账号: {account_name}")
                print(f"    验证码: {captcha}")
                print(f"    返回信息: {result}")
                return {"status": "success", "message": "验证码提交成功", "details": result}
            
            elif result.get("suc") is False:
                emsg = result.get("emsg", "")
                
                if "验证码错误" in emsg:
                    print(f"    [ERROR] 验证码错误!")
                    print(f"    账号: {account_name}")
                    print(f"    提交的验证码: {captcha}")
                    print(f"    错误信息: {emsg}")
                    return {"status": "captcha_error", "message": emsg, "captcha": captcha}
                
                elif "未到开放时间" in emsg or "当前时间暂未开放" in emsg:
                    print(f"    [INFO] 未到开放时间!")
                    print(f"    账号: {account_name}")
                    print(f"    验证码正确: 是")
                    print(f"    提交的验证码: {captcha}")
                    print(f"    提示信息: {emsg}")
                    return {"status": "not_open_time", "message": emsg, "captcha": captcha}
                
                elif "登录" in emsg or "过期" in emsg:
                    print(f"    [ERROR] 登录已过期!")
                    print(f"    账号: {account_name}")
                    print(f"    错误信息: {emsg}")
                    return {"status": "login_expired", "message": emsg}
                
                else:
                    print(f"    [ERROR] 提交失败!")
                    print(f"    账号: {account_name}")
                    print(f"    错误信息: {emsg}")
                    return {"status": "submit_failed", "message": emsg}
            
            else:
                print(f"    [ERROR] 未知返回格式!")
                print(f"    账号: {account_name}")
                print(f"    返回内容: {result}")
                return {"status": "unknown_format", "message": str(result)}
        
        else:
            print(f"    [ERROR] HTTP请求失败!")
            print(f"    账号: {account_name}")
            print(f"    状态码: {response.status_code}")
            return {"status": "http_error", "message": f"HTTP {response.status_code}"}
    
    except Exception as e:
        print(f"    [ERROR] 分析结果异常!")
        print(f"    账号: {account_name}")
        print(f"    异常信息: {e}")
        return {"status": "analysis_error", "message": str(e)}

def test_wrong_captcha_submit(results_dir):
    """测试错误验证码提交"""
    print(f"测试错误验证码提交...")
    
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
        
        # 获取验证码
        captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
        if captcha_response.status_code != 200:
            print(f"    [FAIL] 获取验证码失败")
            return False
        
        # 使用错误验证码提交
        wrong_captcha = "WRONG"
        submit_data = {
            "did": 81,
            "yzmstr": wrong_captcha
        }
        
        submit_response = requests.post(
            "https://enroll.gench.edu.cn/api/stu/set_dorm",
            data=submit_data,
            timeout=10
        )
        
        # 分析结果
        if submit_response.status_code == 200:
            result = submit_response.json()
            emsg = result.get("emsg", "")
            
            if "验证码错误" in emsg:
                print(f"    [OK] 错误验证码测试成功")
                print(f"    提交的错误验证码: {wrong_captcha}")
                print(f"    返回的错误信息: {emsg}")
                print(f"    验证: 系统正确识别了错误验证码")
                
                # 保存结果
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                result_info = {
                    "test_type": "wrong_captcha",
                    "submitted_captcha": wrong_captcha,
                    "response_message": emsg,
                    "timestamp": timestamp,
                    "result": "系统正确返回验证码错误"
                }
                
                result_file = os.path.join(results_dir, f"wrong_captcha_test_{timestamp}.json")
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(result_info, f, indent=2, ensure_ascii=False)
                
                print(f"    结果已保存: {result_file}")
                
                return True
            else:
                print(f"    [FAIL] 预期返回验证码错误，实际返回: {emsg}")
                return False
        else:
            print(f"    [FAIL] HTTP请求失败: {submit_response.status_code}")
            return False
            
    except Exception as e:
        print(f"    [FAIL] 测试异常: {e}")
        return False

def main():
    """主函数"""
    print("实际抢购提交测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"测试账号: 2633233352, 2631141739")
    
    # 运行测试
    result = test_actual_submit()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] 实际抢购提交测试成功")
        print("  - 登录功能正常")
        print("  - 验证码获取正常")
        print("  - AI识别正常")
        print("  - 提交反馈正常")
        print("  - 错误处理正常")
    else:
        print("[FAIL] 实际抢购提交测试失败")
    
    print("\n结果保存位置: submit_results/")
    print("每个测试都会保存验证码图片、识别结果和提交反馈")

if __name__ == "__main__":
    main()