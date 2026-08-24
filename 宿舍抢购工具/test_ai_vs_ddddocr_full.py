# -*- coding: utf-8 -*-
"""
AI vs ddddocr 完整对比测试
保存所有验证码图片，增加测试次数到20次
"""
import sys
import os
import time
import requests
import base64
import json
from PIL import Image
import io

def test_ai_vs_ddddocr_full():
    """AI vs ddddocr 完整对比测试"""
    print("AI vs ddddocr 完整对比测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"测试次数: 20次")
    
    # 创建结果保存目录
    results_dir = "ai_vs_ddddocr_full_test"
    os.makedirs(results_dir, exist_ok=True)
    
    # 登录
    print(f"\n登录测试账号...")
    login_data = {"enrollid": "2633233352", "idcard": "341226200807104418"}
    login_response = requests.post(
        "https://enroll.gench.edu.cn/api/stu/login",
        data=login_data,
        timeout=10
    )
    
    if login_response.text.strip() != "1":
        print(f"[FAIL] 登录失败")
        return False
    
    print(f"[OK] 登录成功")
    
    # 测试20次
    test_count = 20
    results = []
    
    print(f"\n开始{test_count}次对比测试...")
    
    for i in range(test_count):
        print(f"\n第{i+1}次测试:")
        
        try:
            # 获取验证码
            captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
            if captcha_response.status_code != 200:
                print(f"  [FAIL] 获取验证码失败")
                continue
            
            # 保存验证码图片
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            captcha_file = os.path.join(results_dir, f"captcha_{i+1}_{timestamp}.jpg")
            with open(captcha_file, "wb") as f:
                f.write(captcha_response.content)
            
            print(f"  验证码图片已保存: {captcha_file}")
            
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
                
                print(f"  AI: {ai_result} ({ai_time:.3f}s)")
                print(f"  ddddocr: {dd_result} ({dd_time:.3f}s)")
                
                # 对比结果
                if ai_result.upper() == dd_result.upper():
                    print(f"  结果: 一致")
                    match = True
                else:
                    print(f"  结果: 不一致")
                    match = False
                
                # 提交验证码查看反馈
                submit_data = {
                    "did": 81,
                    "yzmstr": ai_result
                }
                
                submit_response = requests.post(
                    "https://enroll.gench.edu.cn/api/stu/set_dorm",
                    data=submit_data,
                    timeout=10
                )
                
                # 分析反馈
                feedback = analyze_feedback(submit_response, ai_result)
                print(f"  服务器反馈: {feedback}")
                
                results.append({
                    "attempt": i+1,
                    "captcha_file": captcha_file,
                    "ai_result": ai_result,
                    "dd_result": dd_result,
                    "ai_time": ai_time,
                    "dd_time": dd_time,
                    "match": match,
                    "feedback": feedback,
                    "captcha_size": len(captcha_response.content)
                })
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  [FAIL] 测试异常: {e}")
    
    # 保存测试结果
    results_file = os.path.join(results_dir, "full_comparison_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "test_count": test_count,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    # 分析结果
    print(f"\n{'='*80}")
    print("测试结果分析")
    print(f"{'='*80}")
    
    print(f"总测试次数: {len(results)}")
    
    if results:
        # 统计一致率
        match_count = sum(1 for r in results if r["match"])
        print(f"一致次数: {match_count}")
        print(f"不一致次数: {len(results) - match_count}")
        print(f"一致率: {match_count/len(results)*100:.1f}%")
        
        # 统计AI识别准确性（通过服务器反馈）
        correct_count = 0
        for r in results:
            if "未到开放时间" in r["feedback"]:
                correct_count += 1
        
        print(f"\nAI识别准确性分析:")
        print(f"识别正确（服务器反馈'未到开放时间'）: {correct_count}次")
        print(f"识别错误（服务器反馈其他）: {len(results) - correct_count}次")
        print(f"AI识别准确率: {correct_count/len(results)*100:.1f}%")
        
        # 统计服务器反馈
        feedback_counts = {}
        for r in results:
            feedback = r["feedback"]
            feedback_counts[feedback] = feedback_counts.get(feedback, 0) + 1
        
        print(f"\n服务器反馈统计:")
        for feedback, count in feedback_counts.items():
            print(f"  {feedback}: {count}次")
    
    return True

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

def main():
    """主函数"""
    print("AI vs ddddocr 完整对比测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"真实环境: https://enroll.gench.edu.cn")
    print(f"测试次数: 20次")
    
    # 运行测试
    result = test_ai_vs_ddddocr_full()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] AI vs ddddocr 完整对比测试成功")
        print("  - 20次测试完成")
        print("  - 所有验证码图片已保存")
        print("  - 识别结果已保存")
        print("  - 服务器反馈已记录")
    else:
        print("[FAIL] AI vs ddddocr 完整对比测试失败")
    
    print("\n结果保存位置: ai_vs_ddddocr_full_test/")
    print("包含所有验证码图片、识别结果和分析数据")

if __name__ == "__main__":
    main()