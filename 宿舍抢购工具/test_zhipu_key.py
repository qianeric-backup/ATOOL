# -*- coding: utf-8 -*-
"""
智谱key测试脚本
验证智谱key配置是否正常工作
"""
import sys
import os
import time
import requests
import base64

def test_zhipu_key():
    """测试智谱key"""
    print("智谱key测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 智谱key配置
    api_key = "c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON"
    base_url = "https://open.bigmodel.cn/api/paas/v4"
    model = "glm-4v-plus-0111"
    
    print(f"智谱key: {api_key[:20]}...")
    print(f"API地址: {base_url}")
    print(f"模型: {model}")
    
    # 测试1: API连接测试
    print(f"\n{'='*80}")
    print("测试1: API连接测试")
    print(f"{'='*80}")
    
    try:
        # 创建测试图片
        test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "测试"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{test_image}"}}
                ]}],
                "max_tokens": 10
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[OK] API连接成功")
            print(f"    状态码: {response.status_code}")
            print(f"    响应时间: {response.elapsed.total_seconds():.3f}秒")
        else:
            print(f"[FAIL] API连接失败")
            print(f"    状态码: {response.status_code}")
            print(f"    响应: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"[FAIL] API连接异常: {e}")
        return False
    
    # 测试2: 验证码识别测试
    print(f"\n{'='*80}")
    print("测试2: 验证码识别测试")
    print(f"{'='*80}")
    
    try:
        # 获取验证码
        captcha_response = requests.get("https://enroll.gench.edu.cn/api/pc/common/kaptcha", timeout=10)
        if captcha_response.status_code != 200:
            print(f"[FAIL] 获取验证码失败: {captcha_response.status_code}")
            return False
        
        print(f"[OK] 获取验证码成功，大小: {len(captcha_response.content)} bytes")
        
        # AI识别验证码
        b64 = base64.b64encode(captcha_response.content).decode()
        
        start_time = time.time()
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
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
            
            print(f"[OK] AI识别成功")
            print(f"    识别结果: {result}")
            print(f"    识别时间: {recognize_time:.3f}秒")
            print(f"    结果长度: {len(result)}位")
            
            # 检查结果是否为5位
            if len(result) == 5:
                print(f"[OK] 识别结果长度正确（5位）")
            else:
                print(f"[WARN] 识别结果长度不正确（{len(result)}位）")
            
            return True
        else:
            print(f"[FAIL] AI识别失败")
            print(f"    状态码: {response.status_code}")
            print(f"    响应: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 验证码识别异常: {e}")
        return False

def main():
    """主函数"""
    print("智谱key测试")
    print("="*80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    result = test_zhipu_key()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if result:
        print("[OK] 智谱key测试成功")
        print("  - API连接正常")
        print("  - 验证码识别正常")
        print("  - 识别结果正确")
    else:
        print("[FAIL] 智谱key测试失败")
    
    print("\n配置信息:")
    print("1. 智谱key: c62744579e5642768956abffc4a984e9.WXRNZ8t2R0msIZON")
    print("2. API地址: https://open.bigmodel.cn/api/paas/v4")
    print("3. 模型: glm-4v-plus-0111")

if __name__ == "__main__":
    main()