# -*- coding: utf-8 -*-
"""
V0.0.9c版本简单多开测试脚本
测试多个V0.0.9c实例同时运行
"""
import sys
import os
import time
import subprocess
import threading
import json
from datetime import datetime

def test_single_instance(account, instance_id, results_list, lock):
    """测试单个实例"""
    exe_path = "releases/v0.0.9c/grab_dorm.exe"
    
    print(f"[实例{instance_id}] 启动测试 - 账号: {account['name']}")
    
    # 构建命令
    cmd = [
        exe_path,
        "--enrollid", account["enrollid"],
        "--idcard", account["idcard"],
        "--dry-run",
        "--no-ocr"
    ]
    
    start_time = time.time()
    
    try:
        # 启动进程
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
            "instance_id": instance_id,
            "account": account["name"],
            "enrollid": account["enrollid"],
            "execution_time": execution_time,
            "success": success,
            "return_code": result.returncode,
            "start_time": start_time,
            "end_time": time.time()
        }
        
        with lock:
            results_list.append(test_result)
        
        status = "成功" if success else "失败"
        print(f"[实例{instance_id}] 测试完成 - 耗时: {execution_time:.3f}秒, 状态: {status}")
        
        # 输出关键日志
        if result.stdout:
            for line in result.stdout.split('\n'):
                if any(key in line for key in ['[LOGIN]', '[DORM]', '[TIME]', '[DRY-RUN]']):
                    print(f"  [实例{instance_id}] {line}")
        
        return success
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        print(f"[实例{instance_id}] 测试超时 ({execution_time:.3f}秒)")
        
        with lock:
            results_list.append({
                "instance_id": instance_id,
                "account": account["name"],
                "enrollid": account["enrollid"],
                "execution_time": execution_time,
                "success": False,
                "return_code": -1,
                "start_time": start_time,
                "end_time": time.time(),
                "error": "超时"
            })
        
        return False
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"[实例{instance_id}] 测试异常: {e}")
        
        with lock:
            results_list.append({
                "instance_id": instance_id,
                "account": account["name"],
                "enrollid": account["enrollid"],
                "execution_time": execution_time,
                "success": False,
                "return_code": -1,
                "start_time": start_time,
                "end_time": time.time(),
                "error": str(e)
            })
        
        return False

def main():
    """主函数"""
    print("V0.0.9c版本简单多开测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试版本: V0.0.9c")
    
    # 检查exe文件
    exe_path = "releases/v0.0.9c/grab_dorm.exe"
    if not os.path.exists(exe_path):
        print(f"[FAIL] exe文件不存在: {exe_path}")
        return
    
    print(f"[OK] exe文件存在: {exe_path}")
    print(f"    文件大小: {os.path.getsize(exe_path):,} bytes")
    
    # 测试账号
    accounts = [
        {
            "enrollid": "2633233352",
            "idcard": "341226200807104418",
            "name": "账号1"
        },
        {
            "enrollid": "2631141739",
            "idcard": "310110200605112038",
            "name": "账号2"
        }
    ]
    
    # 共享结果列表
    results = []
    lock = threading.Lock()
    
    # 测试轮数
    test_rounds = 2
    
    for round_num in range(test_rounds):
        print(f"\n{'='*80}")
        print(f"第{round_num + 1}轮测试开始")
        print(f"{'='*80}")
        
        # 创建线程
        threads = []
        for i, account in enumerate(accounts, 1):
            instance_id = f"{round_num + 1}-{i}"
            thread = threading.Thread(
                target=test_single_instance,
                args=(account, instance_id, results, lock),
                name=f"实例{instance_id}"
            )
            threads.append(thread)
        
        # 同时启动所有实例
        print(f"同时启动{len(threads)}个实例...")
        start_time = time.time()
        
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        round_time = time.time() - start_time
        print(f"第{round_num + 1}轮测试完成，耗时: {round_time:.3f}秒")
        
        # 等待一段时间再进行下一轮
        if round_num < test_rounds - 1:
            print("等待2秒后进行下一轮测试...")
            time.sleep(2)
    
    # 生成报告
    print(f"\n{'='*80}")
    print("测试报告")
    print(f"{'='*80}")
    
    # 统计结果
    total_tests = len(results)
    success_count = sum(1 for r in results if r["success"])
    failed_count = total_tests - success_count
    
    # 计算时间统计
    execution_times = [r["execution_time"] for r in results]
    avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
    min_time = min(execution_times) if execution_times else 0
    max_time = max(execution_times) if execution_times else 0
    
    # 检查并发冲突
    overlaps = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            # 检查时间重叠
            if (results[i]["start_time"] < results[j]["end_time"] and 
                results[j]["start_time"] < results[i]["end_time"]):
                overlaps.append((i, j))
    
    # 输出统计信息
    print(f"总测试数: {total_tests}")
    print(f"成功数: {success_count}")
    print(f"失败数: {failed_count}")
    print(f"成功率: {success_count/total_tests*100:.1f}%")
    print(f"平均耗时: {avg_time:.3f}秒")
    print(f"最快耗时: {min_time:.3f}秒")
    print(f"最慢耗时: {max_time:.3f}秒")
    print(f"耗时波动: {max_time - min_time:.3f}秒")
    
    # 输出冲突分析
    print(f"\n冲突分析:")
    print(f"时间重叠对数: {len(overlaps)}")
    
    if overlaps:
        print("发现时间重叠（可能表示并发执行）:")
        for i, j in overlaps[:5]:  # 只显示前5个
            print(f"  实例{i+1} ({results[i]['account']}) 与 实例{j+1} ({results[j]['account']})")
    else:
        print("未发现时间重叠")
    
    # 输出详细结果
    print(f"\n详细结果:")
    for result in results:
        status = "成功" if result["success"] else "失败"
        print(f"  实例{result['instance_id']} ({result['account']}): "
              f"耗时{result['execution_time']:.3f}秒, 状态{status}")
    
    # 保存详细报告
    report_file = f"V0.0.9c简单多开测试报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        "test_info": {
            "version": "V0.0.9c",
            "test_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_tests": total_tests,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count/total_tests*100
        },
        "time_stats": {
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "time_variance": max_time - min_time
        },
        "conflict_analysis": {
            "overlap_count": len(overlaps),
            "overlaps": overlaps[:10]  # 只保存前10个
        },
        "detailed_results": results
    }
    
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"\n详细报告已保存到: {report_file}")
    except Exception as e:
        print(f"保存报告失败: {e}")
    
    # 输出结论
    print(f"\n结论:")
    if failed_count == 0:
        print("✓ 所有实例都成功运行，未发现明显冲突")
    else:
        print(f"✗ 有{failed_count}个实例失败，可能存在冲突或资源竞争")
    
    if len(overlaps) > 0:
        print(f"✓ 发现{len(overlaps)}对时间重叠，表示实例确实在并发执行")
    else:
        print("✗ 未发现时间重叠，实例可能是顺序执行")

if __name__ == "__main__":
    main()