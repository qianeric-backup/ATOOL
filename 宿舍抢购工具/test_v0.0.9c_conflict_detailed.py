# -*- coding: utf-8 -*-
"""
V0.0.9c版本详细多开冲突测试脚本
测试多个V0.0.9c实例同时运行是否会有冲突
"""
import sys
import os
import time
import subprocess
import threading
import json
import tempfile
from datetime import datetime

class ConflictTester:
    def __init__(self):
        self.exe_path = "releases/v0.0.9c/grab_dorm.exe"
        self.results = []
        self.lock = threading.Lock()
        self.temp_files = []  # 临时文件列表
        
    def log(self, message, instance_id=None):
        """线程安全的日志输出"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[实例{instance_id}]" if instance_id else "[主程序]"
        print(f"{timestamp} {prefix} {message}")
    
    def test_single_instance(self, account, instance_id):
        """测试单个实例"""
        self.log(f"启动实例测试", instance_id)
        
        # 创建临时文件来测试文件锁
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
        temp_file.close()
        self.temp_files.append(temp_file.name)
        
        try:
            # 构建命令
            cmd = [
                self.exe_path,
                "--enrollid", account["enrollid"],
                "--idcard", account["idcard"],
                "--dry-run",
                "--no-ocr"
            ]
            
            self.log(f"命令: {' '.join(cmd)}", instance_id)
            
            start_time = time.time()
            
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
            
            # 检查是否有错误输出
            has_errors = bool(result.stderr) and len(result.stderr.strip()) > 0
            
            # 记录结果
            test_result = {
                "instance_id": instance_id,
                "account": account["name"],
                "enrollid": account["enrollid"],
                "execution_time": execution_time,
                "success": success,
                "return_code": result.returncode,
                "has_errors": has_errors,
                "output_lines": len(result.stdout.split('\n')) if result.stdout else 0,
                "error_lines": len(result.stderr.split('\n')) if result.stderr else 0,
                "start_time": start_time,
                "end_time": time.time(),
                "temp_file": temp_file.name
            }
            
            with self.lock:
                self.results.append(test_result)
            
            status = "成功" if success else "失败"
            self.log(f"测试完成 - 耗时: {execution_time:.3f}秒, 状态: {status}", instance_id)
            
            # 输出关键日志
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if any(key in line for key in ['[LOGIN]', '[DORM]', '[TIME]', '[DRY-RUN]', '[ERROR]', '[WARN]']):
                        self.log(f"  {line}", instance_id)
            
            # 输出错误信息
            if result.stderr:
                error_lines = [line for line in result.stderr.split('\n') if line.strip()]
                if error_lines:
                    self.log(f"  错误信息: {error_lines[0]}", instance_id)
            
            return success
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            self.log(f"测试超时 ({execution_time:.3f}秒)", instance_id)
            
            with self.lock:
                self.results.append({
                    "instance_id": instance_id,
                    "account": account["name"],
                    "enrollid": account["enrollid"],
                    "execution_time": execution_time,
                    "success": False,
                    "return_code": -1,
                    "has_errors": True,
                    "output_lines": 0,
                    "error_lines": 0,
                    "start_time": start_time,
                    "end_time": time.time(),
                    "temp_file": temp_file.name,
                    "error": "超时"
                })
            
            return False
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.log(f"测试异常: {e}", instance_id)
            
            with self.lock:
                self.results.append({
                    "instance_id": instance_id,
                    "account": account["name"],
                    "enrollid": account["enrollid"],
                    "execution_time": execution_time,
                    "success": False,
                    "return_code": -1,
                    "has_errors": True,
                    "output_lines": 0,
                    "error_lines": 0,
                    "start_time": start_time,
                    "end_time": time.time(),
                    "temp_file": temp_file.name,
                    "error": str(e)
                })
            
            return False
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass
    
    def run_conflict_test(self, accounts, test_count=3):
        """运行冲突测试"""
        self.log("="*80)
        self.log("V0.0.9c版本详细多开冲突测试")
        self.log("="*80)
        self.log(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"测试版本: V0.0.9c")
        self.log(f"测试实例数: {len(accounts)}")
        self.log(f"每个实例测试次数: {test_count}")
        
        # 检查exe文件
        if not os.path.exists(self.exe_path):
            self.log(f"[FAIL] exe文件不存在: {self.exe_path}")
            return False
        
        self.log(f"[OK] exe文件存在: {self.exe_path}")
        self.log(f"    文件大小: {os.path.getsize(self.exe_path):,} bytes")
        
        try:
            # 测试每个实例
            for test_round in range(test_count):
                self.log(f"\n第{test_round + 1}轮测试开始")
                
                # 为每个账号创建线程
                threads = []
                for i, account in enumerate(accounts, 1):
                    instance_id = f"{test_round + 1}-{i}"
                    thread = threading.Thread(
                        target=self.test_single_instance,
                        args=(account, instance_id),
                        name=f"实例{instance_id}"
                    )
                    threads.append(thread)
                
                # 同时启动所有实例
                self.log(f"同时启动{len(threads)}个实例...")
                start_time = time.time()
                
                for thread in threads:
                    thread.start()
                
                # 等待所有线程完成
                for thread in threads:
                    thread.join()
                
                round_time = time.time() - start_time
                self.log(f"第{test_round + 1}轮测试完成，耗时: {round_time:.3f}秒")
                
                # 等待一段时间再进行下一轮
                if test_round < test_count - 1:
                    self.log("等待3秒后进行下一轮测试...")
                    time.sleep(3)
            
            # 生成报告
            self.generate_report()
            
            return True
            
        finally:
            # 清理临时文件
            self.cleanup_temp_files()
    
    def generate_report(self):
        """生成测试报告"""
        self.log("\n" + "="*80)
        self.log("详细冲突测试报告")
        self.log("="*80)
        
        if not self.results:
            self.log("没有测试结果")
            return
        
        # 统计结果
        total_tests = len(self.results)
        success_count = sum(1 for r in self.results if r["success"])
        failed_count = total_tests - success_count
        
        # 计算时间统计
        execution_times = [r["execution_time"] for r in self.results]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
        min_time = min(execution_times) if execution_times else 0
        max_time = max(execution_times) if execution_times else 0
        
        # 检查错误统计
        error_count = sum(1 for r in self.results if r["has_errors"])
        
        # 检查并发冲突
        overlaps = []
        for i in range(len(self.results)):
            for j in range(i + 1, len(self.results)):
                # 检查时间重叠
                if (self.results[i]["start_time"] < self.results[j]["end_time"] and 
                    self.results[j]["start_time"] < self.results[i]["end_time"]):
                    overlaps.append((i, j))
        
        # 检查同一账号并发
        same_account_concurrent = []
        for i in range(len(self.results)):
            for j in range(i + 1, len(self.results)):
                if (self.results[i]["enrollid"] == self.results[j]["enrollid"] and
                    self.results[i]["start_time"] < self.results[j]["end_time"] and
                    self.results[j]["start_time"] < self.results[i]["end_time"]):
                    same_account_concurrent.append((i, j))
        
        # 输出统计信息
        self.log(f"总测试数: {total_tests}")
        self.log(f"成功数: {success_count}")
        self.log(f"失败数: {failed_count}")
        self.log(f"成功率: {success_count/total_tests*100:.1f}%")
        self.log(f"有错误输出的实例数: {error_count}")
        self.log(f"平均耗时: {avg_time:.3f}秒")
        self.log(f"最快耗时: {min_time:.3f}秒")
        self.log(f"最慢耗时: {max_time:.3f}秒")
        self.log(f"耗时波动: {max_time - min_time:.3f}秒")
        
        # 输出冲突分析
        self.log(f"\n冲突分析:")
        self.log(f"时间重叠对数: {len(overlaps)}")
        self.log(f"同一账号并发对数: {len(same_account_concurrent)}")
        
        if overlaps:
            self.log("发现时间重叠（可能表示并发执行）:")
            for i, j in overlaps[:5]:  # 只显示前5个
                self.log(f"  实例{i+1} ({self.results[i]['account']}) 与 实例{j+1} ({self.results[j]['account']})")
        else:
            self.log("未发现时间重叠")
        
        if same_account_concurrent:
            self.log("发现同一账号并发（可能导致冲突）:")
            for i, j in same_account_concurrent[:5]:  # 只显示前5个
                self.log(f"  实例{i+1} ({self.results[i]['account']}) 与 实例{j+1} ({self.results[j]['account']})")
        else:
            self.log("未发现同一账号并发")
        
        # 输出详细结果
        self.log(f"\n详细结果:")
        for result in self.results:
            status = "成功" if result["success"] else "失败"
            error_info = ", 有错误输出" if result["has_errors"] else ""
            self.log(f"  实例{result['instance_id']} ({result['account']}): "
                    f"耗时{result['execution_time']:.3f}秒, 状态{status}{error_info}")
        
        # 保存详细报告
        report_file = f"V0.0.9c详细冲突测试报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "test_info": {
                "version": "V0.0.9c",
                "test_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_tests": total_tests,
                "success_count": success_count,
                "failed_count": failed_count,
                "success_rate": success_count/total_tests*100,
                "error_count": error_count
            },
            "time_stats": {
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "time_variance": max_time - min_time
            },
            "conflict_analysis": {
                "overlap_count": len(overlaps),
                "same_account_concurrent_count": len(same_account_concurrent),
                "overlaps": overlaps[:10],  # 只保存前10个
                "same_account_concurrent": same_account_concurrent[:10]
            },
            "detailed_results": self.results
        }
        
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            self.log(f"\n详细报告已保存到: {report_file}")
        except Exception as e:
            self.log(f"保存报告失败: {e}")
        
        # 输出结论
        self.log(f"\n结论:")
        if failed_count == 0:
            self.log("[OK] 所有实例都成功运行，未发现明显冲突")
        else:
            self.log(f"[FAIL] 有{failed_count}个实例失败，可能存在冲突或资源竞争")
        
        if len(overlaps) > 0:
            self.log(f"[OK] 发现{len(overlaps)}对时间重叠，表示实例确实在并发执行")
        else:
            self.log("[FAIL] 未发现时间重叠，实例可能是顺序执行")
        
        if len(same_account_concurrent) > 0:
            self.log(f"[WARN] 发现{len(same_account_concurrent)}对同一账号并发，可能导致冲突")
        else:
            self.log("[OK] 未发现同一账号并发")

def main():
    """主函数"""
    print("V0.0.9c版本详细多开冲突测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建测试器
    tester = ConflictTester()
    
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
    
    # 运行冲突测试
    print(f"准备测试{len(accounts)}个账号的多开冲突...")
    print("注意：将同时启动多个实例进行测试")
    
    # 运行测试（每个账号测试3轮）
    tester.run_conflict_test(accounts, test_count=3)
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()