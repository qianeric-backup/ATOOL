# -*- coding: utf-8 -*-
"""
分析ddddocr多正确识别的两张验证码
"""
import os
import json

def main():
    print("分析ddddocr多正确识别的两张验证码")
    print("="*80)
    
    # 读取测试结果
    results_file = "ai_vs_ddddocr_full_test/full_comparison_results.json"
    if not os.path.exists(results_file):
        print(f"[FAIL] 测试结果文件不存在: {results_file}")
        return
    
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    results = data.get("results", [])
    
    print(f"总测试次数: {len(results)}")
    
    # 找出不一致的测试
    inconsistent_tests = [r for r in results if not r.get("match", True)]
    
    print(f"不一致测试次数: {len(inconsistent_tests)}")
    
    # 分析每个不一致测试
    print(f"\n不一致测试详细分析:")
    for test in inconsistent_tests:
        attempt = test.get("attempt")
        ai_result = test.get("ai_result")
        dd_result = test.get("dd_result")
        captcha_file = test.get("captcha_file")
        
        print(f"\n测试{attempt}:")
        print(f"  AI识别: {ai_result}")
        print(f"  ddddocr识别: {dd_result}")
        print(f"  验证码图片: {captcha_file}")
        
        # 分析差异
        if len(dd_result) > len(ai_result):
            print(f"  差异: ddddocr多识别了{len(dd_result) - len(ai_result)}个字符")
        elif len(dd_result) < len(ai_result):
            print(f"  差异: AI多识别了{len(ai_result) - len(dd_result)}个字符")
        else:
            print(f"  差异: 字符内容不同")
    
    # 找出ddddocr可能更正确的情况
    print(f"\n" + "="*80)
    print("ddddocr可能更正确的情况分析:")
    print(f"="*80)
    
    for test in inconsistent_tests:
        attempt = test.get("attempt")
        ai_result = test.get("ai_result")
        dd_result = test.get("dd_result")
        
        # 分析字符长度
        if len(dd_result) == 5 and len(ai_result) != 5:
            print(f"\n测试{attempt}: ddddocr识别为5位，可能更正确")
            print(f"  AI: {ai_result} ({len(ai_result)}位)")
            print(f"  ddddocr: {dd_result} ({len(dd_result)}位)")
        elif len(dd_result) == 5 and len(ai_result) == 5:
            # 检查字符差异
            diff_count = sum(1 for a, d in zip(ai_result, dd_result) if a != d)
            if diff_count == 1:
                print(f"\n测试{attempt}: 只有一个字符差异，可能ddddocr更正确")
                print(f"  AI: {ai_result}")
                print(f"  ddddocr: {dd_result}")
                print(f"  差异字符位置: ", end="")
                for i, (a, d) in enumerate(zip(ai_result, dd_result)):
                    if a != d:
                        print(f"第{i+1}位: '{a}' vs '{d}'", end=" ")
                print()
    
    print(f"\n" + "="*80)
    print("结论:")
    print(f"="*80)
    print("1. ddddocr在字符数量识别上更准确（总是5位）")
    print("2. AI有时识别为4位或6位字符")
    print("3. 在字符内容上，两者各有优劣")
    print("4. 建议：预取阶段使用AI，实时抢购使用ddddocr")

if __name__ == "__main__":
    main()