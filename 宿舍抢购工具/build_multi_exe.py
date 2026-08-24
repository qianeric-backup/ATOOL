# -*- coding: utf-8 -*-
"""
多开exe打包脚本
将多开脚本打包成exe
"""
import os
import sys
import subprocess
import shutil

def build_multi_exe():
    """打包多开exe"""
    print("多开exe打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 源文件路径
    source_file = "multi_instance.py"
    output_dir = "releases/multi_instance"
    exe_name = "multi_instance.exe"
    
    # 检查源文件
    if not os.path.exists(source_file):
        print(f"[FAIL] 源文件不存在: {source_file}")
        return False
    
    print(f"[OK] 源文件存在: {source_file}")
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[OK] 创建输出目录: {output_dir}")
    
    # 清理旧文件
    exe_path = os.path.join(output_dir, exe_name)
    if os.path.exists(exe_path):
        os.remove(exe_path)
        print(f"[OK] 清理旧文件: {exe_path}")
    
    # 使用pyarmor打包
    print(f"\n使用pyarmor打包...")
    
    try:
        # pyarmor命令
        cmd = [
            "pyarmor", "gen",
            "-O", output_dir,
            "--pack", "onefile",
            source_file
        ]
        
        print(f"命令: {' '.join(cmd)}")
        
        # 执行打包
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print(f"[OK] pyarmor打包成功")
            print(f"输出目录: {output_dir}")
            
            # 检查生成的文件
            generated_files = os.listdir(output_dir)
            print(f"生成的文件: {generated_files}")
            
            # 复制配置文件
            print(f"\n复制配置文件...")
            config_file = "config_multi.json"
            if os.path.exists(config_file):
                shutil.copy(config_file, output_dir)
                print(f"  复制配置文件: {config_file}")
            
            # 创建README文件
            readme_content = f"""# 多开实例脚本

## 版本信息
- **版本号**: v1.0
- **打包时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **打包工具**: pyarmor

## 使用方法
1. 编辑config_multi.json配置账号信息
2. 双击multi_instance.exe运行
3. 或者使用命令行: multi_instance.exe

## 配置文件
- config_multi.json: 多开配置文件

## 功能说明
1. 检测到有几个账密就开启几个窗口
2. 每个账号在独立窗口中运行
3. 支持多账号并发抢购

## 注意事项
1. 确保V0.0.9版本的grab_dorm.exe存在
2. 确保配置文件格式正确
3. 确保网络连接正常
"""
            
            readme_path = os.path.join(output_dir, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)
            print(f"  创建README文件: {readme_path}")
            
            # 检查exe文件是否存在
            exe_files = [f for f in generated_files if f.endswith('.exe')]
            if exe_files:
                print(f"\n[OK] 打包完成!")
                print(f"exe文件: {os.path.join(output_dir, exe_files[0])}")
                return True
            else:
                print(f"[FAIL] 未找到exe文件")
                return False
        
        else:
            print(f"[FAIL] pyarmor打包失败")
            print(f"错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAIL] pyarmor打包超时")
        return False
    except Exception as e:
        print(f"[FAIL] pyarmor打包异常: {e}")
        return False

def main():
    """主函数"""
    print("多开exe打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行打包
    result = build_multi_exe()
    
    # 总结
    print("\n" + "="*80)
    print("打包总结")
    print("="*80)
    
    if result:
        print("[OK] 打包成功")
        print("  - pyarmor打包完成")
        print("  - 配置文件已复制")
        print("  - README文件已创建")
        print("  - exe文件已生成")
    else:
        print("[FAIL] 打包失败")
    
    print("\n使用说明:")
    print("1. 进入releases/multi_instance目录")
    print("2. 编辑config_multi.json配置账号信息")
    print("3. 双击multi_instance.exe运行")

if __name__ == "__main__":
    import time
    main()